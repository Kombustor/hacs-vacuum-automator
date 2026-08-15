"""Tests for switch.enabled module."""

from __future__ import annotations

from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.vacuum_scheduler.const import DOMAIN
from custom_components.vacuum_scheduler.data import RoomConfig, RoomState
from custom_components.vacuum_scheduler.switch.enabled import VacuumSchedulerEnabledSwitch


class TestVacuumSchedulerEnabledSwitch:
    """Tests for VacuumSchedulerEnabledSwitch entity."""

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
            mop_frequency_days=None,
            time_window_start=time(9, 0),
            time_window_end=time(21, 0),
        )

    @pytest.fixture
    def room_state(self):
        """Return a sample room state."""
        return RoomState(
            last_vacuumed=datetime(2024, 1, 1, 10, 0, 0),
            last_mopped=None,
            enabled=True,
        )

    @pytest.fixture
    def mock_coordinator_for_switch(self):
        """Return a mocked coordinator with proper config_entry."""
        config_entry = MagicMock()
        config_entry.entry_id = "entry_123"
        config_entry.domain = DOMAIN
        config_entry.title = "Test"
        config_entry.runtime_data = MagicMock()
        config_entry.runtime_data.room_states = {}
        config_entry.runtime_data.storage = MagicMock()

        coordinator = MagicMock()
        coordinator.config_entry = config_entry
        return coordinator

    @pytest.fixture
    def switch_entity(self, mock_coordinator_for_switch, room_config, room_state):
        """Return a switch entity."""
        mock_coordinator_for_switch.config_entry.runtime_data.room_states = {"room_001": room_state}
        return VacuumSchedulerEnabledSwitch(
            coordinator=mock_coordinator_for_switch,
            room_config=room_config,
            room_state=room_state,
            entry_id="entry_123",
        )

    def test_unique_id_format(self, switch_entity):
        """Test unique_id follows {entry_id}_{subentry_id}_{key} format."""
        assert switch_entity.unique_id == "entry_123_room_001_room_enabled"

    def test_translation_key_set(self, switch_entity):
        """Test translation key is set."""
        assert switch_entity.entity_description.translation_key == "room_enabled"
        assert switch_entity.entity_description.has_entity_name is True

    def test_translation_placeholders_contain_room_name(self, switch_entity):
        """Test translation placeholders include room_name."""
        assert switch_entity._attr_translation_placeholders == {"room_name": "Kitchen"}

    def test_is_on_returns_state_enabled(self, switch_entity):
        """Test is_on returns room state enabled value."""
        assert switch_entity.is_on is True

        switch_entity._room_state.enabled = False
        assert switch_entity.is_on is False

    def test_device_info_uses_entry_id(self, switch_entity):
        """Test device info uses config entry domain and entry id."""
        identifiers = switch_entity._attr_device_info["identifiers"]
        assert (DOMAIN, "entry_123") in identifiers

    async def test_turn_on_enables_room(self, switch_entity):
        """Test turn_on enables the room."""
        switch_entity._room_state.enabled = False
        switch_entity.async_write_ha_state = MagicMock()

        with patch(
            "custom_components.vacuum_scheduler.switch.enabled.async_save_room_states",
            new=AsyncMock(),
        ):
            await switch_entity.async_turn_on()

        assert switch_entity._room_state.enabled is True
        switch_entity.async_write_ha_state.assert_called_once()

    async def test_turn_off_disables_room(self, switch_entity):
        """Test turn_off disables the room."""
        switch_entity._room_state.enabled = True
        switch_entity.async_write_ha_state = MagicMock()

        with patch(
            "custom_components.vacuum_scheduler.switch.enabled.async_save_room_states",
            new=AsyncMock(),
        ):
            await switch_entity.async_turn_off()

        assert switch_entity._room_state.enabled is False
        switch_entity.async_write_ha_state.assert_called_once()

    async def test_turn_on_persists_state(self, switch_entity):
        """Test turn_on persists state to storage."""
        switch_entity._room_state.enabled = False
        switch_entity.async_write_ha_state = MagicMock()

        mock_save = AsyncMock()
        with patch(
            "custom_components.vacuum_scheduler.switch.enabled.async_save_room_states",
            new=mock_save,
        ):
            await switch_entity.async_turn_on()

        mock_save.assert_called_once()
