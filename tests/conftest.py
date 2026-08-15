"""Shared fixtures for vacuum_scheduler tests."""

from __future__ import annotations

from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.vacuum_scheduler.data import GlobalConfig, RoomConfig, RoomState, VacuumSchedulerData


@pytest.fixture
def mock_hass() -> MagicMock:
    """Return a mocked Home Assistant instance."""
    hass = MagicMock()
    hass.config.time_zone = "UTC"
    hass.config.language = "en"
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    return hass


@pytest.fixture(autouse=True)
def mock_translations():
    """Patch async_get_translations to return a dict (no real translations in tests)."""
    with (
        patch(
            "homeassistant.helpers.translation.async_get_translations",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "custom_components.vacuum_scheduler.utils.translate.async_get_translations",
            new=AsyncMock(return_value={}),
        ),
    ):
        yield


@pytest.fixture
def sample_room_config() -> RoomConfig:
    """Return a sample RoomConfig."""
    return RoomConfig(
        subentry_id="room_001",
        room_name="Kitchen",
        vacuum_entity="vacuum.xiaomi",
        door_sensor="binary_sensor.kitchen_door",
        window_sensor=None,
        cleaning_area_id=["kitchen"],
        fan_speed="max",
        mop_intensity="medium",
        vacuum_frequency_days=3,
        mop_frequency_days=3,
        time_window_start=time(9, 0),
        time_window_end=time(21, 0),
    )


@pytest.fixture
def sample_room_state() -> RoomState:
    """Return a sample RoomState."""
    return RoomState(
        last_vacuumed=datetime(2024, 1, 1, 10, 0, 0),
        last_mopped=datetime(2024, 1, 2, 10, 0, 0),
        enabled=True,
    )


@pytest.fixture
def sample_global_config() -> GlobalConfig:
    """Return a sample GlobalConfig."""
    return GlobalConfig(
        notify_entity="notify.mobile_app_phone",
        global_dry_run=False,
        max_rooms_per_batch=5,
        allow_cleaning_when_window_open=False,
        critical_overdue_days=2,
        stabilization_period=5,
    )


@pytest.fixture
def sample_runtime_data(sample_global_config: GlobalConfig) -> VacuumSchedulerData:
    """Return sample runtime data with rooms."""
    room_config = RoomConfig(
        subentry_id="room_001",
        room_name="Kitchen",
        vacuum_entity="vacuum.xiaomi",
        door_sensor="binary_sensor.kitchen_door",
        window_sensor=None,
        cleaning_area_id=["kitchen"],
        fan_speed=None,
        mop_intensity=None,
        vacuum_frequency_days=3,
        mop_frequency_days=None,
        time_window_start=time(8, 0),
        time_window_end=time(22, 0),
    )

    room_state = RoomState(
        last_vacuumed=datetime(2024, 1, 1, 10, 0, 0),
        last_mopped=datetime(2024, 1, 2, 10, 0, 0),
        enabled=True,
    )

    storage_mock = MagicMock()
    storage_mock.async_load = AsyncMock(return_value={})
    storage_mock.async_save = AsyncMock(return_value=True)

    coordinator_mock = MagicMock()
    coordinator_mock.async_request_refresh = AsyncMock()

    return VacuumSchedulerData(
        global_config=sample_global_config,
        rooms={"room_001": room_config},
        room_states={"room_001": room_state},
        storage=storage_mock,
        coordinator=coordinator_mock,
    )


@pytest.fixture
def mock_storage():
    """Return a mocked Store instance."""
    store = MagicMock()
    store.async_load = AsyncMock(return_value={})
    store.async_save = AsyncMock(return_value=None)
    return store


@pytest.fixture
def mock_coordinator():
    """Return a mocked coordinator."""
    coordinator = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.data = {}
    return coordinator
