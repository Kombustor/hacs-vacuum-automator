"""Tests for data models."""

from __future__ import annotations

from datetime import datetime, time

from custom_components.vacuum_scheduler.const import (
    CONF_CLEANING_AREA_ID,
    CONF_DOOR_SENSOR,
    CONF_FAN_SPEED,
    CONF_MOP_FREQUENCY_DAYS,
    CONF_MOP_INTENSITY,
    CONF_ROOM_NAME,
    CONF_TIME_WINDOW_END,
    CONF_TIME_WINDOW_START,
    CONF_VACUUM_ENTITY,
    CONF_VACUUM_FREQUENCY_DAYS,
    CONF_WINDOW_SENSOR,
)
from custom_components.vacuum_scheduler.data import GlobalConfig, RoomConfig, RoomState
from homeassistant.util import dt as dt_util


class TestRoomConfig:
    """Tests for RoomConfig dataclass."""

    def test_from_subentry_data_parses_correctly(self):
        """Test RoomConfig is created correctly from subentry data."""
        data = {
            CONF_ROOM_NAME: "Living Room",
            CONF_VACUUM_ENTITY: "vacuum.xiaomi",
            CONF_DOOR_SENSOR: "binary_sensor.living_room_door",
            CONF_WINDOW_SENSOR: None,
            CONF_CLEANING_AREA_ID: ["living_room"],
            CONF_FAN_SPEED: "max",
            CONF_MOP_INTENSITY: "medium",
            CONF_VACUUM_FREQUENCY_DAYS: 2,
            CONF_MOP_FREQUENCY_DAYS: 2,
            CONF_TIME_WINDOW_START: "09:00",
            CONF_TIME_WINDOW_END: "21:00",
        }

        config = RoomConfig.from_subentry_data("sub_001", data)

        assert config.subentry_id == "sub_001"
        assert config.room_name == "Living Room"
        assert config.vacuum_entity == "vacuum.xiaomi"
        assert config.door_sensor == "binary_sensor.living_room_door"
        assert config.window_sensor is None
        assert config.vacuum_frequency_days == 2
        assert config.mop_frequency_days == 2
        assert config.fan_speed == "max"
        assert config.mop_intensity == "medium"

    def test_from_subentry_data_treats_zero_mop_frequency_as_disabled(self):
        """Test RoomConfig treats a mop frequency of 0 as disabled."""
        data = {
            CONF_ROOM_NAME: "Kitchen",
            CONF_VACUUM_ENTITY: "vacuum.test",
            CONF_DOOR_SENSOR: None,
            CONF_WINDOW_SENSOR: None,
            CONF_CLEANING_AREA_ID: ["kitchen"],
            CONF_FAN_SPEED: None,
            CONF_MOP_INTENSITY: None,
            CONF_VACUUM_FREQUENCY_DAYS: 3,
            CONF_MOP_FREQUENCY_DAYS: 0,
            CONF_TIME_WINDOW_START: "09:00",
            CONF_TIME_WINDOW_END: "21:00",
        }

        config = RoomConfig.from_subentry_data("sub_004", data)

        assert config.mop_frequency_days is None

    def test_from_subentry_data_handles_time_objects(self):
        """Test RoomConfig handles time objects in data."""
        data = {
            CONF_ROOM_NAME: "Kitchen",
            CONF_VACUUM_ENTITY: "vacuum.test",
            CONF_DOOR_SENSOR: None,
            CONF_WINDOW_SENSOR: None,
            CONF_CLEANING_AREA_ID: ["kitchen"],
            CONF_FAN_SPEED: None,
            CONF_MOP_INTENSITY: None,
            CONF_VACUUM_FREQUENCY_DAYS: 3,
            CONF_MOP_FREQUENCY_DAYS: None,
            CONF_TIME_WINDOW_START: time(8, 30),
            CONF_TIME_WINDOW_END: time(20, 0),
        }

        config = RoomConfig.from_subentry_data("sub_002", data)

        assert config.time_window_start == time(8, 30)
        assert config.time_window_end == time(20, 0)

    def test_from_subentry_data_parses_time_strings(self):
        """Test RoomConfig parses time strings correctly."""
        data = {
            CONF_ROOM_NAME: "Bedroom",
            CONF_VACUUM_ENTITY: "vacuum.test",
            CONF_DOOR_SENSOR: None,
            CONF_WINDOW_SENSOR: None,
            CONF_CLEANING_AREA_ID: ["bedroom"],
            CONF_FAN_SPEED: None,
            CONF_MOP_INTENSITY: None,
            CONF_VACUUM_FREQUENCY_DAYS: 7,
            CONF_MOP_FREQUENCY_DAYS: None,
            CONF_TIME_WINDOW_START: "10:30",
            CONF_TIME_WINDOW_END: "22:00",
        }

        config = RoomConfig.from_subentry_data("sub_003", data)

        assert config.time_window_start == time(10, 30)
        assert config.time_window_end == time(22, 0)
        """Test RoomState serializes to dict correctly."""
        state = RoomState(
            last_vacuumed=datetime(2024, 1, 15, 10, 30, 0),
            last_mopped=datetime(2024, 1, 14, 14, 0, 0),
            enabled=True,
        )

        result = state.to_dict()

        assert result["enabled"] is True
        assert result["last_vacuumed"] == "2024-01-15T10:30:00"
        assert result["last_mopped"] == "2024-01-14T14:00:00"

    def test_to_dict_handles_none_values(self):
        """Test RoomState handles None datetime values."""
        state = RoomState(
            last_vacuumed=None,
            last_mopped=None,
            enabled=False,
        )

        result = state.to_dict()

        assert result["enabled"] is False
        assert result["last_vacuumed"] is None
        assert result["last_mopped"] is None

    def test_from_dict_deserializes_correctly(self):
        """Test RoomState deserializes from dict correctly."""
        data = {
            "last_vacuumed": "2024-01-15T10:30:00",
            "last_mopped": "2024-01-14T14:00:00",
            "enabled": True,
        }

        state = RoomState.from_dict(data)

        assert state.enabled is True
        # Timestamps are always tz-aware (naive input is localized).
        assert state.last_vacuumed == dt_util.as_local(datetime(2024, 1, 15, 10, 30, 0))
        assert state.last_mopped == dt_util.as_local(datetime(2024, 1, 14, 14, 0, 0))
        assert state.last_vacuumed.tzinfo is not None

    def test_from_dict_handles_none_values(self):
        """Test RoomState handles None values in dict."""
        data = {
            "last_vacuumed": None,
            "last_mopped": None,
            "enabled": False,
        }

        state = RoomState.from_dict(data)

        assert state.enabled is False
        assert state.last_vacuumed is None
        assert state.last_mopped is None

    def test_from_dict_handles_missing_keys(self):
        """Test RoomState handles missing keys in dict."""
        data = {"enabled": True}

        state = RoomState.from_dict(data)

        assert state.enabled is True
        assert state.last_vacuumed is None
        assert state.last_mopped is None


class TestGlobalConfig:
    """Tests for GlobalConfig dataclass."""

    def test_from_entry_data_parses_correctly(self):
        """Test GlobalConfig is created correctly from entry data."""
        data = {
            "notify_entity": "notify.mobile_app_phone",
            "global_dry_run": True,
            "max_rooms_per_batch": 3,
            "allow_cleaning_when_window_open": True,
            "critical_overdue_days": 1,
        }

        config = GlobalConfig.from_entry_data(data)

        assert config.notify_entity == "notify.mobile_app_phone"
        assert config.global_dry_run is True
        assert config.max_rooms_per_batch == 3
        assert config.allow_cleaning_when_window_open is True
        assert config.critical_overdue_days == 1

    def test_from_entry_data_uses_defaults(self):
        """Test GlobalConfig uses defaults for missing values."""
        data = {}

        config = GlobalConfig.from_entry_data(data)

        assert config.notify_entity is None
        assert config.global_dry_run is False
        assert config.max_rooms_per_batch == 5
        assert config.allow_cleaning_when_window_open is False
        assert config.critical_overdue_days == 2
