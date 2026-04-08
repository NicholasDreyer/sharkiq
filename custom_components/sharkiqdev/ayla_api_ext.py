"""Extended Ayla Networks API client with V3 room cleaning support.

This module provides a mixin that wraps SharkIqVacuum to add:
- AreasToClean V3 (JSON-based room selection with floor ID, clean type, pass count)
- Flow mode control (water level for mopping)
- Mobile App Room Definition parsing (room map with polygons)
- Extended property accessors (mop plate, cleaning params, dock sensors)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .const import (
    CLEAN_TYPE_DRY,
    PROP_AREAS_TO_CLEAN_V3,
    PROP_FLOW_MODE,
    PROP_MOBILE_APP_ROOM_DEFINITION,
)

_LOGGER = logging.getLogger(__name__)


class SharkExtendedMixin:
    """Mixin that adds V3 API methods to a SharkIqVacuum instance.

    Designed to wrap an existing SharkIqVacuum object rather than subclassing,
    since the bundled sharkiq library constructs instances internally.
    """

    def __init__(self, vacuum) -> None:
        """Wrap an existing SharkIqVacuum."""
        self._vacuum = vacuum
        self._room_map: dict[str, dict] | None = None

    @property
    def vacuum(self):
        """Return the underlying SharkIqVacuum."""
        return self._vacuum

    @property
    def room_map(self) -> dict[str, dict] | None:
        """Return the cached room map (room_name -> room_info dict)."""
        return self._room_map

    # --- V3 Room Cleaning ---

    def _get_floor_id(self) -> str | None:
        """Extract the floor ID from the room map."""
        if self._room_map:
            for room_info in self._room_map.values():
                return room_info.get("floor_id")
        return None

    def _room_names_to_ids(self, room_names: list[str]) -> list[str]:
        """Convert user-friendly room names to robot room IDs (e.g. AZ_X)."""
        if not self._room_map:
            raise ValueError("Room map not loaded. Ensure async_load_room_map has run.")

        ids = []
        for name in room_names:
            name_lower = name.lower()
            for room_name, room_info in self._room_map.items():
                if room_name.lower() == name_lower:
                    ids.append(room_info["robot_room_name"])
                    break
            else:
                available = ", ".join(self._room_map.keys())
                raise ValueError(f"Room '{name}' not found. Available: {available}")
        return ids

    async def async_clean_rooms_v3(
        self,
        room_names: list[str],
        clean_type: str = CLEAN_TYPE_DRY,
        clean_count: int = 1,
    ) -> None:
        """Start cleaning specific rooms using the V3 API.

        Args:
            room_names: List of user-friendly room names.
            clean_type: "dry" or "wet".
            clean_count: Number of cleaning passes (1-3).
        """
        room_ids = self._room_names_to_ids(room_names)
        floor_id = self._get_floor_id()

        if not floor_id:
            raise ValueError("No floor ID available. Load room map first.")

        payload = json.dumps({
            "areas_to_clean": {"UserRoom": room_ids},
            "clean_count": clean_count,
            "floor_id": floor_id,
            "cleantype": clean_type,
        })

        _LOGGER.debug("V3 clean payload: %s", payload)

        # Build the batch datapoints endpoint from the property endpoint
        vac = self._vacuum
        prop_endpoint = vac.set_property_endpoint(PROP_AREAS_TO_CLEAN_V3)
        base_url = prop_endpoint.rsplit("/properties/", 1)[0]
        batch_url = base_url.rsplit("/dsns/", 1)[0] + "/batch_datapoints.json"

        data = {
            "batch_datapoints": [
                {
                    "datapoint": {"value": payload},
                    "dsn": vac.serial_number,
                    "name": PROP_AREAS_TO_CLEAN_V3,
                }
            ]
        }

        async with await vac.ayla_api.async_request("post", batch_url, json=data) as resp:
            result = await resp.json()
            _LOGGER.debug("V3 clean response: %s", result)

    async def async_set_flow_mode(self, level: int) -> None:
        """Set the water flow mode.

        Args:
            level: 0=off, 1=low, 2=medium, 3=high.
        """
        if level < 0 or level > 3:
            raise ValueError(f"Flow level must be 0-3, got {level}")

        end_point = self._vacuum.set_property_endpoint(PROP_FLOW_MODE)
        data = {"datapoint": {"value": level}}

        async with await self._vacuum.ayla_api.async_request("post", end_point, json=data) as resp:
            await resp.json()
            _LOGGER.debug("Set flow mode to %d", level)

    # --- Room Map ---

    async def async_load_room_map(self) -> dict[str, dict]:
        """Download and parse the Mobile_App_Room_Definition file property.

        Returns:
            dict of {user_room_name: {robot_room_name, area_size, floor_id, points, ...}}
            or empty dict if unavailable.
        """
        try:
            room_def_bytes = await self._vacuum.async_get_file_property(
                PROP_MOBILE_APP_ROOM_DEFINITION
            )
        except Exception:
            _LOGGER.debug(
                "Room definition not available for %s (device may not support V3 API)",
                self._vacuum.name,
            )
            return {}

        try:
            room_def = json.loads(room_def_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError):
            _LOGGER.warning("Failed to parse room definition JSON for %s", self._vacuum.name)
            return {}

        room_map: dict[str, dict] = {}
        floor_id = room_def.get("floor_id", "")

        for area in room_def.get("areas", []):
            name = area.get("user_room_name", "Unknown")
            room_map[name] = {
                "robot_room_name": area.get("robot_room_name", area.get("uuid", "")),
                "uuid": area.get("uuid", ""),
                "area_size": area.get("area_size", 0),
                "floor_type": area.get("floor_type", "none"),
                "area_type": area.get("area_type", ""),
                "cleaning_parameter_set": area.get("cleaning_parameter_set", 1),
                "points": area.get("points", []),
                "floor_id": floor_id,
            }

        self._room_map = room_map
        _LOGGER.info(
            "Loaded room map for %s: %d room(s): %s",
            self._vacuum.name,
            len(room_map),
            ", ".join(room_map.keys()),
        )
        return room_map

    # --- Extended Property Accessors ---

    def get_mop_plate_attached(self) -> bool | None:
        """Return whether the mop plate is currently attached."""
        val = self._vacuum.properties_full.get("MopPlateAttached", {}).get("value")
        if val is not None:
            return bool(val)
        return None

    def get_cleaning_parameters(self) -> dict | None:
        """Return the current cleaning parameters as a dict."""
        val = self._vacuum.properties_full.get("CleaningParameters", {}).get("value")
        if val and isinstance(val, str):
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return None
        return val if isinstance(val, dict) else None

    def get_dock_sensor_data(self) -> dict | None:
        """Return dock sensor data (e.g. tank levels)."""
        val = self._vacuum.properties_full.get("DockSensorData", {}).get("value")
        if val and isinstance(val, str):
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return None
        return val if isinstance(val, dict) else None

    def get_available_rooms(self) -> list[str]:
        """Return list of available room names from V3 map, falling back to legacy property."""
        if self._room_map:
            return list(self._room_map.keys())
        # Fall back to legacy Robot_Room_List property
        room_list = self._vacuum.get_property_value("Robot_Room_List")
        if room_list and ":" in str(room_list):
            return str(room_list).split(":")[1:]
        return []
