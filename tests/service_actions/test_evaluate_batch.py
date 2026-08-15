"""Tests for service_actions.evaluate_batch module."""

from __future__ import annotations

from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.vacuum_scheduler.data import RoomConfig, RoomState, VacuumSchedulerData
from custom_components.vacuum_scheduler.service_actions.evaluate_batch import async_handle_evaluate_batch


class TestAsyncHandleEvaluateBatch:
    """Tests for async_handle_evaluate_batch function."""

    @pytest.fixture
    def fixed_now(self):
        """Patch dt_util.now() to a deterministic time within the default window."""
        fixed = datetime(2024, 1, 6, 12, 0, 0, tzinfo=datetime.now().astimezone().tzinfo)
        with patch(
            "custom_components.vacuum_scheduler.service_actions.evaluate_batch.dt_util.now",
            return_value=fixed,
        ):
            yield fixed

    @pytest.fixture
    def mock_call(self):
        """Return a mocked service call."""
        call = MagicMock()
        call.data = {
            "entity_id": None,
            "dry_run": None,
        }
        return call

    @pytest.fixture
    def sample_entry(self, mock_hass):
        """Return a sample config entry with runtime data."""
        entry = MagicMock()
        global_config = MagicMock()
        global_config.global_dry_run = False
        global_config.max_rooms_per_batch = 5
        global_config.notify_entity = "notify.mobile_app_phone"
        global_config.allow_cleaning_when_window_open = False

        room_config = RoomConfig(
            subentry_id="room_001",
            room_name="Kitchen",
            vacuum_entity="vacuum.xiaomi",
            door_sensor="binary_sensor.door",
            window_sensor=None,
            cleaning_area_id=["kitchen"],
            fan_speed=None,
            mop_intensity=None,
            vacuum_frequency_days=3,
            mop_frequency_days=None,
            time_window_start=time(8, 0),
            time_window_end=time(22, 0),
        )
        # Overdue room (last cleaned 5 days ago)
        room_state = RoomState(
            last_vacuumed=datetime(2024, 1, 1, 10, 0, 0),
            last_mopped=None,
            enabled=True,
        )

        # Door is open so the room can be evaluated
        door_state = MagicMock()
        door_state.state = "on"
        mock_hass.states = MagicMock()
        mock_hass.states.get = MagicMock(
            side_effect=lambda entity_id: door_state if entity_id == "binary_sensor.door" else None,
        )

        storage_mock = MagicMock()
        coordinator_mock = MagicMock()
        coordinator_mock.async_request_refresh = MagicMock()

        entry.runtime_data = VacuumSchedulerData(
            global_config=global_config,
            rooms={"room_001": room_config},
            room_states={"room_001": room_state},
            storage=storage_mock,
            coordinator=coordinator_mock,
        )
        return entry

    async def test_returns_overdue_rooms(self, fixed_now, mock_hass, sample_entry, mock_call):
        """Test returns list of overdue rooms."""
        result = await async_handle_evaluate_batch(mock_hass, sample_entry, mock_call)

        assert "rooms" in result
        assert result["rooms_overdue"] == 1
        assert "Kitchen" in result["rooms"][0]["rooms"]

    async def test_respects_dry_run_parameter(self, fixed_now, mock_hass, sample_entry, mock_call):
        """Test dry_run parameter prevents actual cleaning."""
        mock_call.data["dry_run"] = True

        result = await async_handle_evaluate_batch(mock_hass, sample_entry, mock_call)

        assert result["dry_run"] is True

    async def test_uses_global_dry_run_when_not_specified(self, fixed_now, mock_hass, sample_entry, mock_call):
        """Test global dry_run is used when service param not specified."""
        sample_entry.runtime_data.global_config.global_dry_run = True
        mock_call.data["dry_run"] = None

        result = await async_handle_evaluate_batch(mock_hass, sample_entry, mock_call)

        assert result["dry_run"] is True

    async def test_filters_by_vacuum_entity(self, fixed_now, mock_hass, sample_entry, mock_call):
        """Test filtering rooms by vacuum entity."""
        mock_call.data["vacuum_entity"] = "vacuum.other_vacuum"  # Different vacuum

        result = await async_handle_evaluate_batch(mock_hass, sample_entry, mock_call)

        assert result["rooms_overdue"] == 0

    async def test_respects_max_rooms_per_batch(self, fixed_now, mock_hass, sample_entry, mock_call):
        """Test that max_rooms_per_batch limits results."""
        # Add more overdue rooms
        for i in range(2, 8):
            room_config = RoomConfig(
                subentry_id=f"room_{i:03d}",
                room_name=f"Room{i}",
                vacuum_entity="vacuum.xiaomi",
                door_sensor="binary_sensor.door",
                window_sensor=None,
                cleaning_area_id=[str(i)],
                fan_speed=None,
                mop_intensity=None,
                vacuum_frequency_days=3,
                mop_frequency_days=None,
                time_window_start=time(8, 0),
                time_window_end=time(22, 0),
            )
            room_state = RoomState(
                last_vacuumed=datetime(2024, 1, 1, 10, 0, 0),
                last_mopped=None,
                enabled=True,
            )
            sample_entry.runtime_data.rooms[f"room_{i:03d}"] = room_config
            sample_entry.runtime_data.room_states[f"room_{i:03d}"] = room_state
        sample_entry.runtime_data.global_config.max_rooms_per_batch = 3

        result = await async_handle_evaluate_batch(mock_hass, sample_entry, mock_call)

        assert result["rooms_overdue"] == 3

    async def test_sends_notification_when_overdue_rooms_found(self, fixed_now, mock_hass, sample_entry, mock_call):
        """Test notification is sent when overdue rooms found."""
        await async_handle_evaluate_batch(mock_hass, sample_entry, mock_call)

        mock_hass.services.async_call.assert_called()
        # Check that notify service was called
        calls = mock_hass.services.async_call.call_args_list
        notify_calls = [c for c in calls if c[0][0] == "notify"]
        assert len(notify_calls) > 0

    async def test_uses_translation_for_notification(self, fixed_now, mock_hass, sample_entry, mock_call):
        """Test that translation function is called for notification strings."""
        with patch(
            "custom_components.vacuum_scheduler.service_actions.evaluate_batch.async_translate",
            new=AsyncMock(return_value="translated"),
        ) as mock_translate:
            await async_handle_evaluate_batch(mock_hass, sample_entry, mock_call)

        # Verify translate was called with notification keys
        translate_keys = list(mock_translate.call_args_list)
        translate_key_args = [c[0][1] for c in translate_keys]
        assert "cleaning_started_title" in translate_key_args
        assert "cleaning_started_message" in translate_key_args
