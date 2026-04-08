"""Shark IQ Constants."""

from datetime import timedelta
import logging

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)

API_TIMEOUT = 20
PLATFORMS = [Platform.VACUUM, Platform.SENSOR, Platform.SELECT]
DOMAIN = "sharkiqdev"
SHARK = "Shark"
UPDATE_INTERVAL = timedelta(seconds=30)
SERVICE_CLEAN_ROOM = "clean_room"
SERVICE_CLEAN_ROOMS_V3 = "clean_rooms_v3"
SERVICE_SET_FLOW_MODE = "set_flow_mode"

SHARKIQ_REGION_EUROPE = "europe"
SHARKIQ_REGION_ELSEWHERE = "elsewhere"
SHARKIQ_REGION_DEFAULT = SHARKIQ_REGION_ELSEWHERE
SHARKIQ_REGION_OPTIONS = [SHARKIQ_REGION_EUROPE, SHARKIQ_REGION_ELSEWHERE]

AUTH0_REFRESH_TOKEN_KEY = "auth0_refresh_token"

# --- Attributes ---
ATTR_ROOMS = "rooms"
ATTR_ROOM_MAP = "room_map"
ATTR_MOP_ATTACHED = "mop_plate_attached"
ATTR_DOCK_SENSORS = "dock_sensor_data"
ATTR_CLEANING_PARAMS = "cleaning_parameters"
ATTR_FLOW_MODE = "flow_mode"

# --- Flow modes (water level for mopping) ---
FLOW_MODE_OFF = 0
FLOW_MODE_LOW = 1
FLOW_MODE_MEDIUM = 2
FLOW_MODE_HIGH = 3

FLOW_MODE_NAMES = {
    FLOW_MODE_OFF: "Off",
    FLOW_MODE_LOW: "Low",
    FLOW_MODE_MEDIUM: "Medium",
    FLOW_MODE_HIGH: "High",
}

# --- Clean types ---
CLEAN_TYPE_DRY = "dry"
CLEAN_TYPE_WET = "wet"

# --- Ayla property names (V3 / extended) ---
PROP_AREAS_TO_CLEAN_V3 = "SET_AreasToClean_V3"
PROP_GET_AREAS_TO_CLEAN_V3 = "GET_AreasToClean_V3"
PROP_FLOW_MODE = "SET_Flow_Mode"
PROP_GET_CLEANING_PARAMS = "GET_CleaningParameters"
PROP_GET_DOCK_SENSOR_DATA = "GET_DockSensorData"
PROP_GET_MOP_PLATE_ATTACHED = "GET_MopPlateAttached"
PROP_MOBILE_APP_ROOM_DEFINITION = "Mobile_App_Room_Definition"
