"""Constants for the Vacuum Scheduler integration."""

from datetime import timedelta
from logging import getLogger

from homeassistant.const import Platform

DOMAIN = "vacuum_scheduler"
LOGGER = getLogger(__package__)

# Config entry / subentry keys
CONF_ROOM_NAME = "room_name"
CONF_VACUUM_ENTITY = "vacuum_entity"
CONF_DOOR_SENSOR = "door_sensor"
CONF_WINDOW_SENSOR = "window_sensor"
CONF_CLEANING_AREA_ID = "cleaning_area_id"
CONF_VACUUM_FREQUENCY_DAYS = "vacuum_frequency_days"
CONF_MOP_FREQUENCY_DAYS = "mop_frequency_days"
CONF_FAN_SPEED = "fan_speed"
CONF_MOP_INTENSITY = "mop_intensity"
CONF_TIME_WINDOW_START = "time_window_start"
CONF_TIME_WINDOW_END = "time_window_end"

# Cleaning mode values (used by services)
CLEANING_MODE_VACUUM = "vacuum"
CLEANING_MODE_MOP = "mop"
CLEANING_MODE_VACUUM_AND_MOP = "vacuum_and_mop"

# Mop intensity values for set_water_box_custom_mode command
MOP_INTENSITY_OFF = "off"
MOP_INTENSITY_LOW = "low"
MOP_INTENSITY_MEDIUM = "medium"
MOP_INTENSITY_HIGH = "high"
MOP_INTENSITY_AUTO = "auto"
MOP_INTENSITY_CUSTOM = "custom"
MOP_INTENSITY_OPTIONS = [
    MOP_INTENSITY_OFF,
    MOP_INTENSITY_LOW,
    MOP_INTENSITY_MEDIUM,
    MOP_INTENSITY_HIGH,
    MOP_INTENSITY_AUTO,
    MOP_INTENSITY_CUSTOM,
]
# Maps mop intensity option to set_water_box_custom_mode parameter value
MOP_INTENSITY_COMMAND_MAP: dict[str, int] = {
    MOP_INTENSITY_OFF: 200,
    MOP_INTENSITY_LOW: 201,
    MOP_INTENSITY_MEDIUM: 202,
    MOP_INTENSITY_HIGH: 203,
    MOP_INTENSITY_AUTO: 204,
    MOP_INTENSITY_CUSTOM: 207,
}

# Options
CONF_STABILIZATION_PERIOD = "stabilization_period"
DEFAULT_STABILIZATION_PERIOD = 0


CONF_DEFAULT_FAN_SPEED = "default_fan_speed"
CONF_DEFAULT_MOP_INTENSITY = "default_mop_intensity"

# Global config (stored in entry.data)
CONF_NOTIFY_ENTITY = "notify_entity"
CONF_GLOBAL_DRY_RUN = "global_dry_run"
CONF_MAX_ROOMS_PER_BATCH = "max_rooms_per_batch"
CONF_ALLOW_CLEANING_WHEN_WINDOW_OPEN = "allow_cleaning_when_window_open"
CONF_CRITICAL_OVERDUE_DAYS = "critical_overdue_days"
DEFAULT_MAX_ROOMS_PER_BATCH = 5
DEFAULT_ALLOW_CLEANING_WHEN_WINDOW_OPEN = False
DEFAULT_CRITICAL_OVERDUE_DAYS = 2

# Storage version
STORAGE_VERSION = 1

# Events
EVENT_CRITICAL_OVERDUE = "vac_scheduler_critical_overdue"

# Services
SERVICE_EVALUATE_BATCH = "evaluate_batch"
SERVICE_RECORD_CLEANING = "record_cleaning"

# Platforms we create entities for
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SWITCH]

# Update interval for coordinator
UPDATE_INTERVAL = timedelta(seconds=60)
