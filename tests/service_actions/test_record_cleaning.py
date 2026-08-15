"""Tests for service_actions.record_cleaning module."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.vacuum_scheduler.const import (
    CLEANING_MODE_MOP,
    CLEANING_MODE_VACUUM,
    CLEANING_MODE_VACUUM_AND_MOP,
)
from custom_components.vacuum_scheduler.data import RoomConfig, RoomState, VacuumSchedulerData
from custom_components.vacuum_scheduler.service_actions.record_cleaning import async_handle_record_cleaning


class TestAsyncHandleRecordCleaning:
    """Tests for async_handle_record_cleaning function."""

    @pytest.fixture
    def mock_call(self):
        """Return a mocked service call."""
        call = MagicMock()
        call.data = {
            "room_name": "Kitchen",
            "mode": None,
            "timestamp": None,
        }
        return call

    @pytest.fixture
    def sample_entry(self, mock_hass):
        """Return a sample config entry with runtime data."""
        entry = MagicMock()
        room_config = RoomConfig(
            subentry_id="room_001",
            room_name="Kitchen",
            vacuum_entity="vacuum.test",
            door_sensor=None,
            window_sensor=None,
            cleaning_area_id=["kitchen"],
            fan_speed=None,
            mop_intensity=None,
            vacuum_frequency_days=3,
            mop_frequency_days=3,
            time_window_start=datetime.strptime("09:00", "%H:%M").time(),
            time_window_end=datetime.strptime("21:00", "%H:%M").time(),
        )
        room_state = RoomState(
            last_vacuumed=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            last_mopped=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            enabled=True,
        )
        storage_mock = MagicMock()
        storage_mock.async_load = AsyncMock(return_value={})
        storage_mock.async_save = AsyncMock(return_value=True)
        coordinator_mock = MagicMock()
        coordinator_mock.async_request_refresh = AsyncMock()

        entry.runtime_data = VacuumSchedulerData(
            global_config=MagicMock(),
            rooms={"room_001": room_config},
            room_states={"room_001": room_state},
            storage=storage_mock,
            coordinator=coordinator_mock,
        )
        return entry

    async def test_records_vacuum_cleaning(self, mock_hass, sample_entry, mock_call):
        """Test recording vacuum cleaning updates timestamp."""
        mock_call.data["mode"] = CLEANING_MODE_VACUUM

        result = await async_handle_record_cleaning(mock_hass, sample_entry, mock_call)

        assert result["success"] is True
        room_state = sample_entry.runtime_data.room_states["room_001"]
        assert room_state.last_vacuumed is not None
        assert room_state.last_vacuumed > datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)

    async def test_records_mop_cleaning(self, mock_hass, sample_entry, mock_call):
        """Test recording mop cleaning updates timestamp."""
        mock_call.data["mode"] = CLEANING_MODE_MOP

        result = await async_handle_record_cleaning(mock_hass, sample_entry, mock_call)

        assert result["success"] is True
        room_state = sample_entry.runtime_data.room_states["room_001"]
        assert room_state.last_mopped is not None
        assert room_state.last_mopped > datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)

    async def test_records_vacuum_and_mop_cleaning(self, mock_hass, sample_entry, mock_call):
        """Test recording vacuum_and_mop cleaning updates both timestamps."""
        mock_call.data["mode"] = CLEANING_MODE_VACUUM_AND_MOP

        result = await async_handle_record_cleaning(mock_hass, sample_entry, mock_call)

        assert result["success"] is True
        room_state = sample_entry.runtime_data.room_states["room_001"]
        assert room_state.last_vacuumed is not None
        assert room_state.last_mopped is not None

    async def test_uses_provided_timestamp(self, mock_hass, sample_entry, mock_call):
        """Test using provided timestamp instead of now."""
        custom_timestamp = "2024-06-15T14:30:00"
        mock_call.data["timestamp"] = custom_timestamp
        mock_call.data["mode"] = CLEANING_MODE_VACUUM

        result = await async_handle_record_cleaning(mock_hass, sample_entry, mock_call)

        assert result["success"] is True
        room_state = sample_entry.runtime_data.room_states["room_001"]
        assert room_state.last_vacuumed == datetime(2024, 6, 15, 14, 30, 0)

    async def test_returns_false_when_room_not_found(self, mock_hass, sample_entry, mock_call):
        """Test returns False when room name not found."""
        mock_call.data["room_name"] = "NonExistentRoom"

        result = await async_handle_record_cleaning(mock_hass, sample_entry, mock_call)

        assert result == {"success": False, "error": "Room 'NonExistentRoom' not found"}

    async def test_triggers_coordinator_refresh(self, mock_hass, sample_entry, mock_call):
        """Test that coordinator refresh is triggered after recording."""
        await async_handle_record_cleaning(mock_hass, sample_entry, mock_call)

        sample_entry.runtime_data.coordinator.async_request_refresh.assert_called_once()

    async def test_saves_states_to_storage(self, mock_hass, sample_entry, mock_call):
        """Test that room states are saved to storage."""
        await async_handle_record_cleaning(mock_hass, sample_entry, mock_call)

        sample_entry.runtime_data.storage.async_save.assert_called_once()
