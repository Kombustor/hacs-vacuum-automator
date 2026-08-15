"""Integration tests for the record_cleaning service."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from custom_components.vacuum_scheduler.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .conftest import entity_id_for, fire_refresh

pytestmark = pytest.mark.integration


async def test_record_vacuum_updates_only_last_vacuumed(hass, entry_with_rooms):
    """mode=vacuum updates last_vacuumed and leaves last_mopped untouched."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    now = dt_util.now()
    state = entry.runtime_data.room_states[kitchen_sid]
    previous_mop = state.last_mopped

    await hass.services.async_call(
        DOMAIN,
        "record_cleaning",
        {"room_name": "Kitchen", "mode": "vacuum"},
        blocking=True,
    )

    assert state.last_vacuumed is not None
    assert abs((dt_util.now() - state.last_vacuumed).total_seconds()) < 5
    assert state.last_mopped == previous_mop
    assert now - state.last_vacuumed < timedelta(seconds=5)


async def test_record_mop_updates_only_last_mopped(hass, entry_with_rooms):
    """mode=mop updates last_mopped and leaves last_vacuumed untouched."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    state = entry.runtime_data.room_states[kitchen_sid]
    previous_vacuum = state.last_vacuumed

    await hass.services.async_call(
        DOMAIN,
        "record_cleaning",
        {"room_name": "Kitchen", "mode": "mop"},
        blocking=True,
    )

    assert state.last_mopped is not None
    assert abs((dt_util.now() - state.last_mopped).total_seconds()) < 5
    assert state.last_vacuumed == previous_vacuum


async def test_record_vacuum_and_mop_updates_both(hass, entry_with_rooms):
    """mode=vacuum_and_mop updates both timestamps."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    state = entry.runtime_data.room_states[kitchen_sid]

    await hass.services.async_call(
        DOMAIN,
        "record_cleaning",
        {"room_name": "Kitchen", "mode": "vacuum_and_mop"},
        blocking=True,
    )

    assert state.last_vacuumed is not None
    assert state.last_mopped is not None
    assert abs((dt_util.now() - state.last_vacuumed).total_seconds()) < 5
    assert abs((dt_util.now() - state.last_mopped).total_seconds()) < 5


async def test_record_explicit_timestamp(hass, entry_with_rooms):
    """An explicit ISO timestamp is honored exactly."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    timestamp = "2026-06-14T07:30:00+00:00"

    await hass.services.async_call(
        DOMAIN,
        "record_cleaning",
        {"room_name": "Kitchen", "mode": "vacuum", "timestamp": timestamp},
        blocking=True,
    )

    assert entry.runtime_data.room_states[kitchen_sid].last_vacuumed == datetime.fromisoformat(timestamp)


async def test_unknown_room_raises_validation_error(hass, entry_with_rooms):
    """Recording for an unknown room raises ServiceValidationError."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "record_cleaning",
            {"room_name": "Bathroom", "mode": "vacuum"},
            blocking=True,
        )


async def test_recording_flips_overdue_sensor_off(hass, entry_with_rooms):
    """A stale room shows overdue until a cleaning is recorded."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    overdue = entity_id_for(hass, entry.entry_id, kitchen_sid, "binary_sensor", "room_overdue")

    state = entry.runtime_data.room_states[kitchen_sid]
    state.last_vacuumed = dt_util.now() - timedelta(days=10)
    await fire_refresh(hass)
    assert hass.states.get(overdue).state == STATE_ON

    await hass.services.async_call(
        DOMAIN,
        "record_cleaning",
        {"room_name": "Kitchen", "mode": "vacuum"},
        blocking=True,
    )
    await fire_refresh(hass)
    assert hass.states.get(overdue).state == STATE_OFF
