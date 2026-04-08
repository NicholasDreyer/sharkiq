"""Select entities for Shark IQ Dev (water flow mode for mopping)."""

from __future__ import annotations

from typing import Any

from .sharkiq import SharkIqVacuum

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .ayla_api_ext import SharkExtendedMixin
from .const import DOMAIN, FLOW_MODE_NAMES, LOGGER
from .coordinator import SharkIqUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Shark IQ Dev select entities."""
    coordinator: SharkIqUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        SharkFlowModeSelect(vac, coordinator.extended_vacs[dsn], coordinator)
        for dsn, vac in coordinator.shark_vacs.items()
    ]
    async_add_entities(entities)


class SharkFlowModeSelect(CoordinatorEntity[SharkIqUpdateCoordinator], SelectEntity):
    """Select entity for water flow mode during mopping."""

    _attr_has_entity_name = True
    _attr_name = "Water Flow"
    _attr_icon = "mdi:water"
    _attr_options = list(FLOW_MODE_NAMES.values())

    def __init__(
        self,
        sharkiq: SharkIqVacuum,
        ext_vac: SharkExtendedMixin,
        coordinator: SharkIqUpdateCoordinator,
    ) -> None:
        """Initialize the flow mode select entity."""
        super().__init__(coordinator)
        self.sharkiq = sharkiq
        self.ext_vac = ext_vac
        self._attr_unique_id = f"{sharkiq.serial_number}_flow_mode"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sharkiq.serial_number)},
        )

    @property
    def current_option(self) -> str | None:
        """Return the current flow mode as a human-readable string."""
        val = self.sharkiq.properties_full.get("Flow_Mode", {}).get("value")
        if val is not None:
            return FLOW_MODE_NAMES.get(int(val), "Off")
        return "Off"

    async def async_select_option(self, option: str) -> None:
        """Set the flow mode by name."""
        level = next(
            (k for k, v in FLOW_MODE_NAMES.items() if v == option),
            0,
        )
        LOGGER.info("Setting flow mode to %s (%d)", option, level)
        await self.ext_vac.async_set_flow_mode(level)
        await self.coordinator.async_refresh()
