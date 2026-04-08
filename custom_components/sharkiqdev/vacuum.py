"""Shark IQ Wrapper."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .sharkiq import OperatingModes, PowerModes, Properties, SharkIqVacuum
import voluptuous as vol

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .ayla_api_ext import SharkExtendedMixin
from .const import (
    CLEAN_TYPE_DRY,
    CLEAN_TYPE_DRY_THEN_WET,
    CLEAN_TYPE_WET,
    DOMAIN,
    LOGGER,
    SERVICE_CLEAN_ROOM,
    SERVICE_CLEAN_ROOMS_V3,
    SERVICE_SET_FLOW_MODE,
    SHARK,
)
from .coordinator import SharkIqUpdateCoordinator

OPERATING_STATE_MAP = {
    OperatingModes.PAUSE: VacuumActivity.PAUSED,
    OperatingModes.START: VacuumActivity.CLEANING,
    OperatingModes.STOP: VacuumActivity.IDLE,
    OperatingModes.RETURN: VacuumActivity.RETURNING,
}

# Add mop operating modes if this firmware supports them
try:
    OPERATING_STATE_MAP[OperatingModes.MOP] = VacuumActivity.CLEANING
    OPERATING_STATE_MAP[OperatingModes.VACCUM_AND_MOP] = VacuumActivity.CLEANING
except AttributeError:
    pass

FAN_SPEEDS_MAP = {
    "Eco": PowerModes.ECO,
    "Normal": PowerModes.NORMAL,
    "Max": PowerModes.MAX,
}

STATE_RECHARGING_TO_RESUME = "recharging_to_resume"

# Attributes to expose
ATTR_ERROR_CODE = "last_error_code"
ATTR_ERROR_MSG = "last_error_message"
ATTR_LOW_LIGHT = "low_light"
ATTR_RECHARGE_RESUME = "recharge_and_resume"
ATTR_ROOMS = "rooms"
ATTR_ROOM_MAP = "room_map"
ATTR_MOP_ATTACHED = "mop_plate_attached"
ATTR_DOCK_SENSORS = "dock_sensor_data"
ATTR_CLEANING_PARAMS = "cleaning_parameters"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Shark IQ vacuum cleaner."""
    coordinator: SharkIqUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    for dsn, vac in coordinator.shark_vacs.items():
        ext_vac = coordinator.extended_vacs[dsn]
        entities.append(SharkVacuumEntity(vac, ext_vac, coordinator))

    LOGGER.debug(
        "Found %d Shark IQ device(s): %s",
        len(entities),
        ", ".join(e.sharkiq.name for e in entities),
    )
    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()

    # Legacy room cleaning (base64-encoded Areas_To_Clean, older robots)
    platform.async_register_entity_service(
        SERVICE_CLEAN_ROOM,
        {
            vol.Required(ATTR_ROOMS): vol.All(
                cv.ensure_list, vol.Length(min=1), [cv.string]
            ),
        },
        "async_clean_room",
    )

    # V3 room cleaning (JSON-based SET_AreasToClean_V3, newer LiDAR robots)
    platform.async_register_entity_service(
        SERVICE_CLEAN_ROOMS_V3,
        {
            vol.Required(ATTR_ROOMS): vol.All(
                cv.ensure_list, vol.Length(min=1), [cv.string]
            ),
            vol.Optional("clean_type", default=CLEAN_TYPE_DRY): vol.In(
                [CLEAN_TYPE_DRY, CLEAN_TYPE_WET, CLEAN_TYPE_DRY_THEN_WET]
            ),
            vol.Optional("passes", default=1): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=3)
            ),
        },
        "async_clean_rooms_v3",
    )

    # Water flow mode (mopping water level)
    platform.async_register_entity_service(
        SERVICE_SET_FLOW_MODE,
        {
            vol.Required("flow_level"): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=3)
            ),
        },
        "async_set_flow_mode_service",
    )


class SharkVacuumEntity(CoordinatorEntity[SharkIqUpdateCoordinator], StateVacuumEntity):
    """Shark IQ vacuum entity."""

    _attr_fan_speed_list = list(FAN_SPEEDS_MAP)
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.LOCATE
    )
    _unrecorded_attributes = frozenset(
        {ATTR_ROOMS, ATTR_ROOM_MAP, ATTR_DOCK_SENSORS, ATTR_CLEANING_PARAMS}
    )

    def __init__(
        self,
        sharkiq: SharkIqVacuum,
        ext_vac: SharkExtendedMixin,
        coordinator: SharkIqUpdateCoordinator,
    ) -> None:
        """Create a new SharkVacuumEntity."""
        super().__init__(coordinator)
        self.sharkiq = sharkiq
        self.ext_vac = ext_vac
        self._attr_unique_id = sharkiq.serial_number
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sharkiq.serial_number)},
            manufacturer=SHARK,
            model=self.model,
            name=sharkiq.name,
            sw_version=sharkiq.get_property_value(Properties.ROBOT_FIRMWARE_VERSION),
        )

    def clean_spot(self, **kwargs: Any) -> None:
        """Clean a spot. Not yet implemented."""
        raise NotImplementedError

    def send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to the vacuum. Not yet implemented."""
        raise NotImplementedError

    @property
    def is_online(self) -> bool:
        """Tell us if the device is online."""
        return self.coordinator.device_is_online(self.sharkiq.serial_number)

    @property
    def model(self) -> str:
        """Vacuum model number."""
        if self.sharkiq.vac_model_number:
            return self.sharkiq.vac_model_number
        return self.sharkiq.oem_model_number

    @property
    def error_code(self) -> int | None:
        """Return the last observed error code (or None)."""
        return self.sharkiq.error_code

    @property
    def error_message(self) -> str | None:
        """Return the last observed error message (or None)."""
        if not self.error_code:
            return None
        return self.sharkiq.error_text

    @property
    def recharging_to_resume(self) -> int | None:
        """Return True if vacuum set to recharge and resume cleaning."""
        return self.sharkiq.get_property_value(Properties.RECHARGING_TO_RESUME)

    @property
    def activity(self) -> VacuumActivity | None:
        """Get the current vacuum state.

        NB: Currently, we do not return an error state because they can be very, very stale.
        In the app, these are (usually) handled by showing the robot as stopped and sending the
        user a notification.
        """
        if self.sharkiq.get_property_value(Properties.CHARGING_STATUS):
            return VacuumActivity.DOCKED
        op_mode = self.sharkiq.get_property_value(Properties.OPERATING_MODE)
        return OPERATING_STATE_MAP.get(op_mode)

    @property
    def available(self) -> bool:
        """Determine if the sensor is available based on API results."""
        return self.coordinator.last_update_success and self.is_online

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Have the device return to base."""
        await self.sharkiq.async_set_operating_mode(OperatingModes.RETURN)
        await self.coordinator.async_refresh()

    async def async_pause(self) -> None:
        """Pause the cleaning task."""
        await self.sharkiq.async_set_operating_mode(OperatingModes.PAUSE)
        await self.coordinator.async_refresh()

    async def async_start(self) -> None:
        """Start the device."""
        await self.sharkiq.async_set_operating_mode(OperatingModes.START)
        await self.coordinator.async_refresh()

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the device."""
        await self.sharkiq.async_set_operating_mode(OperatingModes.STOP)
        await self.coordinator.async_refresh()

    async def async_locate(self, **kwargs: Any) -> None:
        """Cause the device to generate a loud chirp."""
        await self.sharkiq.async_find_device()

    async def async_clean_room(self, rooms: list[str], **kwargs: Any) -> None:
        """Clean specific rooms using the legacy base64-encoded API (older robots)."""
        rooms_to_clean = []
        valid_rooms = self.available_rooms or []
        rooms = [room.replace("_", " ").title() for room in rooms]
        for room in rooms:
            if room in valid_rooms:
                rooms_to_clean.append(room)
            else:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_room",
                    translation_placeholders={"room": room},
                )

        LOGGER.debug("Cleaning room(s) (legacy): %s", rooms_to_clean)
        await self.sharkiq.async_clean_rooms(rooms_to_clean)
        await self.coordinator.async_refresh()

    async def async_clean_rooms_v3(
        self,
        rooms: list[str],
        clean_type: str = CLEAN_TYPE_DRY,
        passes: int = 1,
        **kwargs: Any,
    ) -> None:
        """Clean specific rooms with wet/dry control.

        Routes to the V3 JSON API if a room map is loaded (newer LiDAR robots),
        otherwise uses the legacy Areas_To_Clean API with operating mode to control
        wet/dry (older robots that use Robot_Room_List).

        clean_type options:
          dry          — vacuum only
          wet          — mop only
          dry_then_wet — vacuum first, then mop (V3: two sequential calls;
                         legacy: VACCUM_AND_MOP operating mode)
        """
        if self.ext_vac.room_map:
            # --- V3 JSON API path ---
            available = self.ext_vac.get_available_rooms()
            for room in rooms:
                if room not in available:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="invalid_room",
                        translation_placeholders={
                            "room": room,
                            "available": ", ".join(available),
                        },
                    )

            if clean_type == CLEAN_TYPE_DRY_THEN_WET:
                LOGGER.info(
                    "V3 dry-then-wet: rooms=%s, passes=%d (dry pass first)", rooms, passes
                )
                await self.ext_vac.async_clean_rooms_v3(rooms, CLEAN_TYPE_DRY, passes)
                await self.ext_vac.async_clean_rooms_v3(rooms, CLEAN_TYPE_WET, passes)
            else:
                LOGGER.info(
                    "V3 room clean: rooms=%s, type=%s, passes=%d", rooms, clean_type, passes
                )
                await self.ext_vac.async_clean_rooms_v3(rooms, clean_type, passes)

        else:
            # --- Legacy Areas_To_Clean path ---
            # Validate against the Robot_Room_List property
            valid_rooms = self.available_rooms or []
            # Normalise the same way async_clean_room does
            rooms = [room.replace("_", " ").title() for room in rooms]
            for room in rooms:
                if room not in valid_rooms:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="invalid_room",
                        translation_placeholders={
                            "room": room,
                            "available": ", ".join(valid_rooms) if valid_rooms else "none",
                        },
                    )

            LOGGER.info(
                "Legacy room clean: rooms=%s, type=%s", rooms, clean_type
            )
            await self.ext_vac.async_clean_rooms_legacy(rooms, clean_type)

        await self.coordinator.async_refresh()

    async def async_set_flow_mode_service(self, flow_level: int, **kwargs: Any) -> None:
        """Set the water flow level for mopping (0=off, 1=low, 2=medium, 3=high)."""
        LOGGER.info("Setting flow mode to %d", flow_level)
        await self.ext_vac.async_set_flow_mode(flow_level)
        await self.coordinator.async_refresh()

    @property
    def fan_speed(self) -> str | None:
        """Return the current fan speed."""
        fan_speed = None
        speed_level = self.sharkiq.get_property_value(Properties.POWER_MODE)
        for k, val in FAN_SPEEDS_MAP.items():
            if val == speed_level:
                fan_speed = k
        return fan_speed

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set the fan speed."""
        await self.sharkiq.async_set_property_value(
            Properties.POWER_MODE, FAN_SPEEDS_MAP.get(fan_speed.capitalize())
        )
        await self.coordinator.async_refresh()

    @property
    def recharge_resume(self) -> bool | None:
        """Recharge and resume mode active."""
        return self.sharkiq.get_property_value(Properties.RECHARGE_RESUME)

    @property
    def rssi(self) -> int | None:
        """Get the WiFi RSSI."""
        return self.sharkiq.get_property_value(Properties.RSSI)

    @property
    def low_light(self):
        """Let us know if the robot is operating in low-light mode."""
        return self.sharkiq.get_property_value(Properties.LOW_LIGHT_MISSION)

    @property
    def available_rooms(self) -> list | None:
        """Return a list of rooms available to clean (legacy Robot_Room_List property)."""
        room_list = self.sharkiq.get_property_value(Properties.ROBOT_ROOM_LIST)
        if room_list:
            return room_list.split(":")[1:]
        return []

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return a dictionary of device state attributes specific to sharkiq."""
        attrs: dict[str, Any] = {
            ATTR_ERROR_CODE: self.error_code,
            ATTR_ERROR_MSG: self.sharkiq.error_text,
            ATTR_LOW_LIGHT: self.low_light,
            ATTR_RECHARGE_RESUME: self.recharge_resume,
            ATTR_ROOMS: self.ext_vac.get_available_rooms(),
        }

        # Extended attributes — only populated on devices that support them
        mop = self.ext_vac.get_mop_plate_attached()
        if mop is not None:
            attrs[ATTR_MOP_ATTACHED] = mop

        clean_params = self.ext_vac.get_cleaning_parameters()
        if clean_params:
            attrs[ATTR_CLEANING_PARAMS] = clean_params

        dock_data = self.ext_vac.get_dock_sensor_data()
        if dock_data:
            attrs[ATTR_DOCK_SENSORS] = dock_data

        # Room map summary (names + sizes only, polygon arrays excluded via _unrecorded_attributes)
        if self.ext_vac.room_map:
            attrs[ATTR_ROOM_MAP] = {
                name: {
                    "id": info["robot_room_name"],
                    "size_m2": round(info["area_size"], 1),
                }
                for name, info in self.ext_vac.room_map.items()
            }

        return attrs
