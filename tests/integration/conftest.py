"""Shared fixtures and helpers for the vacuum_scheduler integration tests.

These tests run a real in-memory Home Assistant (pytest-homeassistant-custom-component)
with a fake vacuum platform, fake door/window binary sensors, a fake notify
service and frozen wall-clock time. The whole config-entry -> subentry ->
coordinator -> entities -> services chain is exercised end to end.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun import freeze_time as freeze_time_cls
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.vacuum_scheduler.const import DOMAIN
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .fake_vacuum import setup_fake_vacuum

pytestmark = pytest.mark.integration

# ── Fixture data ────────────────────────────────────────────────────────────

# Stored in entry.data; keys per GlobalConfig.from_entry_data.
GLOBAL_CONFIG: dict[str, Any] = {
    "notify_entity": "notify.mobile_app_phone",
    "global_dry_run": False,
    "max_rooms_per_batch": 5,
    "allow_cleaning_when_window_open": False,
    "critical_overdue_days": 2,
    "default_fan_speed": None,
    "default_mop_intensity": None,
}

# Stored per room subentry; keys per RoomConfig.from_subentry_data.
ROOM_KITCHEN: dict[str, Any] = {
    "room_name": "Kitchen",
    "vacuum_entity": "vacuum.kitchen_robot",
    "door_sensor": "binary_sensor.kitchen_door",
    "cleaning_area_id": ["area_kitchen"],
    "vacuum_frequency_days": 3,
    "mop_frequency_days": 3,
    "fan_speed": "max",
    "mop_intensity": "medium",
    "time_window_start": "08:00",
    "time_window_end": "20:00",
}

ROOM_LIVING_ROOM: dict[str, Any] = {
    "room_name": "Living Room",
    "vacuum_entity": "vacuum.living_room_robot",
    "door_sensor": "binary_sensor.living_room_door",
    "cleaning_area_id": ["area_living"],
    "vacuum_frequency_days": 5,
    "mop_frequency_days": 0,  # 0 = mopping disabled
    "time_window_start": "08:00",
    "time_window_end": "20:00",
}

# Persisted room state seeded before setup: rooms were last cleaned 1 h ago,
# so they start out NOT overdue (never-cleaned rooms would be overdue at once).
ROOM_STATE_SEED: dict[str, Any] = {
    "last_vacuumed": "2026-06-15T09:00:00+00:00",
    "last_mopped": "2026-06-15T09:00:00+00:00",
    "enabled": True,
}

# ── Autouse overrides ───────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_translations() -> None:
    """Override the unit-suite autouse fixture: use real translations."""
    return


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Autouse: let HA load custom_components.vacuum_scheduler from this repo."""
    return


@pytest.fixture(autouse=True)
def freeze_time() -> None:
    """Freeze wall-clock time; an inner freeze_time wins.

    The test framework pins HA's time zone to US/Pacific, so frozen times are
    expressed in that zone: 10:00 local is inside the default room time
    window, 22:00 local is outside.
    """
    with freeze_time_cls("2026-06-15T10:00:00-07:00"):
        yield


# ── Shared helpers (plain functions, not fixtures) ──────────────────────────


async def fire_refresh(hass: HomeAssistant) -> None:
    """Trigger the coordinator's 60 s refresh."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done()


async def fire_after(hass: HomeAssistant, delta: timedelta) -> None:
    """Advance mocked time by delta, firing any due timers."""
    async_fire_time_changed(hass, dt_util.utcnow() + delta)
    await hass.async_block_till_done()


def set_state(hass: HomeAssistant, entity_id: str, state: str) -> None:
    """Set an entity state, firing state_changed for the door listeners."""
    hass.states.async_set(entity_id, state)


def entity_id_for(
    hass: HomeAssistant,
    entry_id: str,
    subentry_id: str,
    platform: str,
    key: str,
) -> str:
    """Resolve a concrete entity id via the registry (unique_id-based)."""
    entity_reg = er.async_get(hass)
    entity_id = entity_reg.async_get_entity_id(platform, DOMAIN, f"{entry_id}_{subentry_id}_{key}")
    assert entity_id is not None, f"No entity for {platform}.{key} of subentry {subentry_id}"
    return entity_id


# ── Fake external world ─────────────────────────────────────────────────────


@pytest.fixture
def vacuum_calls() -> list[dict[str, Any]]:
    """Shared recorder for fake vacuum service calls."""
    return []


@pytest.fixture
async def fake_vacuum(hass: HomeAssistant, vacuum_calls: list[dict[str, Any]]) -> None:
    """Load the fake vacuum platform with vacuum.kitchen_robot / vacuum.living_room_robot."""
    await setup_fake_vacuum(hass, vacuum_calls)


@pytest.fixture
async def notify_calls(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Register a fake notify service that records message/title pairs."""

    calls: list[dict[str, Any]] = []

    async def _handler(call: ServiceCall) -> None:
        calls.append({"message": call.data.get("message"), "title": call.data.get("title")})

    hass.services.async_register("notify", "mobile_app_phone", _handler)
    return calls


# ── Config entry fixtures ───────────────────────────────────────────────────


async def _create_room_subentry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    room_data: dict[str, Any],
) -> str:
    """Create a room subentry through the real subentry flow; return its id."""
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "room"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], room_data)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    for subentry in entry.subentries.values():
        if subentry.title == room_data["room_name"]:
            return subentry.subentry_id
    raise AssertionError(f"Room subentry '{room_data['room_name']}' not found after flow")


async def _setup_entry(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    stabilization_period: int,
) -> tuple[ConfigEntry, str, str]:
    """Set up a real config entry with the two fixture rooms.

    Returns (entry, kitchen_subentry_id, living_room_subentry_id).
    """
    await async_setup_component(hass, DOMAIN, {})

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="vacuum scheduler",
        title="Vacuum Scheduler",
        data=dict(GLOBAL_CONFIG),
        options={"stabilization_period": stabilization_period},
    )
    entry.add_to_hass(hass)

    # Doors start closed, set before setup so no listener sees a transition.
    set_state(hass, "binary_sensor.kitchen_door", "off")
    set_state(hass, "binary_sensor.living_room_door", "off")
    await hass.async_block_till_done()

    kitchen_sid = await _create_room_subentry(hass, entry, ROOM_KITCHEN)
    living_sid = await _create_room_subentry(hass, entry, ROOM_LIVING_ROOM)

    # Seed persisted room states so both rooms start recently cleaned.
    hass_storage[f"vacuum_scheduler.{entry.entry_id}"] = {
        "version": 1,
        "data": {
            "rooms": {
                kitchen_sid: dict(ROOM_STATE_SEED),
                living_sid: dict(ROOM_STATE_SEED),
            }
        },
    }

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, kitchen_sid, living_sid


@pytest.fixture
async def entry_with_rooms(
    hass: HomeAssistant,
    fake_vacuum: None,
    notify_calls: list[dict[str, Any]],
    hass_storage: dict[str, Any],
) -> tuple[ConfigEntry, str, str]:
    """Entry with a 5-minute door stabilization period (delayed door trigger)."""
    return await _setup_entry(hass, hass_storage, stabilization_period=5)


@pytest.fixture
async def entry_immediate(
    hass: HomeAssistant,
    fake_vacuum: None,
    notify_calls: list[dict[str, Any]],
    hass_storage: dict[str, Any],
) -> tuple[ConfigEntry, str, str]:
    """Entry with no stabilization period (door trigger cleans immediately)."""
    return await _setup_entry(hass, hass_storage, stabilization_period=0)
