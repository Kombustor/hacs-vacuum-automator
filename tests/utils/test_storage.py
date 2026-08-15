"""Tests for utils.storage module."""

from __future__ import annotations

from datetime import datetime

from custom_components.vacuum_scheduler.data import RoomState
from custom_components.vacuum_scheduler.utils.storage import (
    async_load_room_states,
    async_save_room_states,
    room_state_from_dict,
    room_state_to_dict,
)


class TestAsyncLoadRoomStates:
    """Tests for async_load_room_states function."""

    async def test_returns_empty_dict_when_no_data(self, mock_storage):
        """Test returns empty dict when store has no data."""
        mock_storage.async_load.return_value = None

        result = await async_load_room_states(mock_storage)

        assert result == {}

    async def test_returns_rooms_from_storage(self, mock_storage):
        """Test returns rooms dict from storage."""
        stored_data = {
            "rooms": {
                "room_001": {
                    "last_vacuumed": "2024-01-01T10:00:00",
                    "last_mopped": "2024-01-02T10:00:00",
                    "enabled": True,
                }
            }
        }
        mock_storage.async_load.return_value = stored_data

        result = await async_load_room_states(mock_storage)

        assert result == stored_data["rooms"]

    async def test_returns_empty_dict_on_exception(self, mock_storage):
        """Test returns empty dict when storage load fails."""
        mock_storage.async_load.side_effect = Exception("Storage error")

        result = await async_load_room_states(mock_storage)

        assert result == {}


class TestAsyncSaveRoomStates:
    """Tests for async_save_room_states function."""

    async def test_saves_room_states_successfully(self, mock_storage):
        """Test saving room states to storage."""
        states = {
            "room_001": {
                "last_vacuumed": "2024-01-01T10:00:00",
                "last_mopped": None,
                "enabled": True,
            }
        }

        result = await async_save_room_states(mock_storage, states)

        assert result is True
        mock_storage.async_save.assert_called_once()
        saved_data = mock_storage.async_save.call_args[0][0]
        assert saved_data["version"] == 1
        assert saved_data["rooms"] == states

    async def test_converts_roomstate_objects_to_dicts(self, mock_storage):
        """Test that RoomState objects are converted to dicts."""
        room_state = RoomState(
            last_vacuumed=datetime(2024, 1, 1, 10, 0, 0),
            last_mopped=None,
            enabled=True,
        )
        states = {"room_001": room_state}

        await async_save_room_states(mock_storage, states)

        saved_data = mock_storage.async_save.call_args[0][0]
        assert saved_data["rooms"]["room_001"]["enabled"] is True

    async def test_returns_false_on_exception(self, mock_storage):
        """Test returns False when storage save fails."""
        mock_storage.async_save.side_effect = Exception("Save error")

        result = await async_save_room_states(mock_storage, {})

        assert result is False


class TestRoomStateToDict:
    """Tests for room_state_to_dict function."""

    def test_converts_room_state_to_dict(self):
        """Test RoomState is converted to dict correctly."""
        state = RoomState(
            last_vacuumed=datetime(2024, 1, 1, 10, 0, 0),
            last_mopped=datetime(2024, 1, 2, 10, 0, 0),
            enabled=True,
        )

        result = room_state_to_dict(state)

        assert result["enabled"] is True
        assert result["last_vacuumed"] == "2024-01-01T10:00:00"
        assert result["last_mopped"] == "2024-01-02T10:00:00"

    def test_handles_none_datetimes(self):
        """Test conversion handles None datetimes."""
        state = RoomState(
            last_vacuumed=None,
            last_mopped=None,
            enabled=False,
        )

        result = room_state_to_dict(state)

        assert result["enabled"] is False
        assert result["last_vacuumed"] is None
        assert result["last_mopped"] is None


class TestRoomStateFromDict:
    """Tests for room_state_from_dict function."""

    def test_converts_dict_to_room_state(self):
        """Test dict is converted to RoomState correctly."""
        data = {
            "last_vacuumed": "2024-01-01T10:00:00",
            "last_mopped": "2024-01-02T10:00:00",
            "enabled": True,
        }

        result = room_state_from_dict(data)

        assert isinstance(result, RoomState)
        assert result.enabled is True
        assert result.last_vacuumed == datetime(2024, 1, 1, 10, 0, 0)
        assert result.last_mopped == datetime(2024, 1, 2, 10, 0, 0)

    def test_handles_missing_optional_fields(self):
        """Test conversion handles missing optional fields."""
        data = {"enabled": True}

        result = room_state_from_dict(data)

        assert result.enabled is True
        assert result.last_vacuumed is None
        assert result.last_mopped is None
