"""Sensor entities for Shark IQ Dev."""

from __future__ import annotations

from typing import Any

from .sharkiq import Properties, SharkIqVacuum

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SharkIqUpdateCoordinator

SENSOR_DESCRIPTIONS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="rssi",
        name="WiFi Signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Shark IQ Dev sensor entities."""
    coordinator: SharkIqUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        SharkIqSensor(vac, coordinator, description)
        for vac in coordinator.shark_vacs.values()
        for description in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)


class SharkIqSensor(CoordinatorEntity[SharkIqUpdateCoordinator], SensorEntity):
    """A sensor entity for Shark IQ Dev."""

    _attr_has_entity_name = True

    def __init__(
        self,
        sharkiq: SharkIqVacuum,
        coordinator: SharkIqUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.sharkiq = sharkiq
        self.entity_description = description
        self._attr_unique_id = f"{sharkiq.serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sharkiq.serial_number)},
        )

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if self.entity_description.key == "rssi":
            return self.sharkiq.get_property_value(Properties.RSSI)
        return None
