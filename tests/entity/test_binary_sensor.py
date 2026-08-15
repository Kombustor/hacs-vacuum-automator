"""Tests for binary_sensor.overdue module."""

from __future__ import annotations

from datetime import datetime, time
from unittest.mock import MagicMock

import pytest

from custom_components.vacuum_scheduler.binary_sensor.overdue import VacuumSchedulerOverdueSensor
from custom_components.vacuum_scheduler.data import RoomConfig, RoomState
from homeassistant.components.binary_sensor import BinarySensorDeviceClass


class TestVacuumSchedulerOverdueSensor:
    """Tests for VacuumSchedulerOverdueSensor entity."""

    @pytest.fixture
    def room_config(self):
        """Return a sample room config."""
        return RoomConfig(
            subentry_id="room_001",
            room_name="Kitchen",
            vacuum_entity="vacuum.test",
            door_sensor="binary_sensor.door",
            window_sensor=None,
            cleaning_area_id=["kitchen"],
            fan_speed=None,
            mop_intensity=None,
            vacuum_frequency_days=3,
            mop_frequency_days=3,
            time_window_start=time(9, 0),
            time_window_end=time(21, 0),
        )

    @pytest.fixture
    def room_state(self):
        """Return a sample room state."""
        return RoomState(
            last_vacuumed=datetime(2024, 1, 1, 10, 0, 0),
            last_mopped=datetime(2024, 1, 2, 10, 0, 0),
            enabled=True,
        )

    @pytest.fixture
    def coordinator_with_data(self):
        """Return a mocked coordinator with data."""
        coordinator = MagicMock()
        coordinator.data = {
            "room_001": {
                "is_overdue": True,
                "last_vacuumed": "2024-01-01T10:00:00",
                "last_mopped": "2024-01-02T10:00:00",
                "days_since_vacuum": 5,
                "days_since_mop": 4,
                "overdue_details": {"vacuum": True, "mop": False},
            }
        }
        coordinator.config_entry = MagicMock()
        coordinator.config_entry.domain = "vacuum_scheduler"
        coordinator.config_entry.title = "Test"
        return coordinator

    @pytest.fixture
    def sensor_entity(self, coordinator_with_data, room_config, room_state):
        """Return an overdue sensor entity."""
        return VacuumSchedulerOverdueSensor(
            coordinator=coordinator_with_data,
            room_config=room_config,
            room_state=room_state,
            entry_id="entry_123",
        )

    def test_unique_id_format(self, sensor_entity):
        """Test unique_id follows {entry_id}_{subentry_id}_{key} format."""
        assert sensor_entity.unique_id == "entry_123_room_001_room_overdue"

    def test_translation_key_set(self, sensor_entity):
        """Test translation key is set."""
        assert sensor_entity.entity_description.translation_key == "room_overdue"
        assert sensor_entity.entity_description.has_entity_name is True

    def test_device_class_is_problem(self, sensor_entity):
        """Test device class is PROBLEM."""
        assert sensor_entity._attr_device_class == BinarySensorDeviceClass.PROBLEM

    def test_is_on_returns_true_when_overdue(self, sensor_entity):
        """Test is_on returns True when room is overdue."""
        assert sensor_entity.is_on is True

    def test_is_on_returns_false_when_not_overdue(self, coordinator_with_data, room_config, room_state):
        """Test is_on returns False when room is not overdue."""
        coordinator_with_data.data = {"room_001": {"is_overdue": False}}
        sensor = VacuumSchedulerOverdueSensor(
            coordinator=coordinator_with_data,
            room_config=room_config,
            room_state=room_state,
            entry_id="entry_123",
        )
        assert sensor.is_on is False

    def test_is_on_returns_false_when_no_data(self, coordinator_with_data, room_config, room_state):
        """Test is_on returns False when no coordinator data for subentry."""
        coordinator_with_data.data = {}
        sensor = VacuumSchedulerOverdueSensor(
            coordinator=coordinator_with_data,
            room_config=room_config,
            room_state=room_state,
            entry_id="entry_123",
        )
        assert sensor.is_on is False

    def test_extra_state_attributes_contains_data(self, sensor_entity):
        """Test extra_state_attributes contains room data."""
        attrs = sensor_entity.extra_state_attributes

        assert attrs["last_vacuumed"] == "2024-01-01T10:00:00"
        assert attrs["last_mopped"] == "2024-01-02T10:00:00"
        assert attrs["days_since_vacuum"] == 5
        assert attrs["days_since_mop"] == 4
        assert attrs["overdue_details"] == {"vacuum": True, "mop": False}

    def test_extra_state_attributes_handles_missing_data(self, coordinator_with_data, room_config, room_state):
        """Test extra_state_attributes handles missing data gracefully."""
        coordinator_with_data.data = {}
        sensor = VacuumSchedulerOverdueSensor(
            coordinator=coordinator_with_data,
            room_config=room_config,
            room_state=room_state,
            entry_id="entry_123",
        )
        attrs = sensor.extra_state_attributes

        assert attrs["last_vacuumed"] is None
        assert attrs["last_mopped"] is None
        assert attrs["days_since_vacuum"] is None
