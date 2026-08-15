"""Integration tests for the door-sensor trigger."""

from __future__ import annotations

from datetime import timedelta

import pytest

from homeassistant.const import STATE_UNKNOWN
from homeassistant.util import dt as dt_util

from .conftest import fire_after, set_state

pytestmark = pytest.mark.integration

KITCHEN_ROBOT = "vacuum.kitchen_robot"
KITCHEN_DOOR = "binary_sensor.kitchen_door"
KITCHEN_SEGMENT = "segment_kitchen"


def _make_kitchen_stale(entry, kitchen_sid: str) -> None:
    """Make the kitchen overdue so the door trigger has something to clean."""
    now = dt_util.now()
    state = entry.runtime_data.room_states[kitchen_sid]
    state.last_vacuumed = now - timedelta(days=10)
    state.last_mopped = now - timedelta(days=10)


async def test_door_open_triggers_after_stabilization(hass, entry_with_rooms, vacuum_calls):
    """Door open -> nothing until the stabilization period elapses, then clean."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    _make_kitchen_stale(entry, kitchen_sid)

    set_state(hass, KITCHEN_DOOR, "on")
    await hass.async_block_till_done()
    assert vacuum_calls == []

    await fire_after(hass, timedelta(minutes=5))

    clean_calls = [call for call in vacuum_calls if call["service"] == "clean_area"]
    assert len(clean_calls) == 1
    assert clean_calls[0]["entity_id"] == KITCHEN_ROBOT
    assert clean_calls[0]["segments"] == [KITCHEN_SEGMENT]


async def test_door_closed_again_cancels_timer(hass, entry_with_rooms, vacuum_calls):
    """Closing the door before the stabilization period cancels the trigger."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    _make_kitchen_stale(entry, kitchen_sid)

    set_state(hass, KITCHEN_DOOR, "on")
    await hass.async_block_till_done()
    set_state(hass, KITCHEN_DOOR, "off")
    await hass.async_block_till_done()

    await fire_after(hass, timedelta(minutes=5))
    assert vacuum_calls == []


async def test_immediate_stabilization_cleans_on_door_open(hass, entry_immediate, vacuum_calls):
    """With stabilization_period=0 the cleaning starts right away."""
    entry, kitchen_sid, _living_sid = entry_immediate
    _make_kitchen_stale(entry, kitchen_sid)

    set_state(hass, KITCHEN_DOOR, "on")
    await hass.async_block_till_done()

    clean_calls = [call for call in vacuum_calls if call["service"] == "clean_area"]
    assert len(clean_calls) == 1
    assert clean_calls[0]["entity_id"] == KITCHEN_ROBOT


async def test_closed_door_triggers_nothing(hass, entry_with_rooms, vacuum_calls):
    """A door that never opens never triggers cleaning, even when overdue."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    _make_kitchen_stale(entry, kitchen_sid)

    await fire_after(hass, timedelta(minutes=5))
    assert vacuum_calls == []


async def test_door_reopen_after_cancel_rearms_timer(hass, entry_with_rooms, vacuum_calls):
    """Opening a door again after closing it re-arms the stabilization timer."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    _make_kitchen_stale(entry, kitchen_sid)

    set_state(hass, KITCHEN_DOOR, "on")
    await hass.async_block_till_done()
    set_state(hass, KITCHEN_DOOR, "off")
    await hass.async_block_till_done()
    set_state(hass, KITCHEN_DOOR, "on")
    await hass.async_block_till_done()

    await fire_after(hass, timedelta(minutes=5, seconds=1))

    clean_calls = [call for call in vacuum_calls if call["service"] == "clean_area"]
    assert len(clean_calls) == 1
    assert clean_calls[0]["entity_id"] == KITCHEN_ROBOT


async def test_door_reopen_after_cleaning_does_not_reclean(hass, entry_with_rooms, vacuum_calls):
    """A door bouncing after a completed clean does not trigger a second batch."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    _make_kitchen_stale(entry, kitchen_sid)

    set_state(hass, KITCHEN_DOOR, "on")
    await hass.async_block_till_done()
    await fire_after(hass, timedelta(minutes=5))

    set_state(hass, KITCHEN_DOOR, "off")
    await hass.async_block_till_done()
    set_state(hass, KITCHEN_DOOR, "on")
    await hass.async_block_till_done()
    await fire_after(hass, timedelta(minutes=5, seconds=1))

    clean_calls = [call for call in vacuum_calls if call["service"] == "clean_area"]
    assert len(clean_calls) == 1


async def test_door_unknown_during_stabilization_cancels_timer(hass, entry_with_rooms, vacuum_calls):
    """A door going unknown (zigbee down) during stabilization cancels the trigger."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    _make_kitchen_stale(entry, kitchen_sid)

    set_state(hass, KITCHEN_DOOR, "on")
    await hass.async_block_till_done()
    set_state(hass, KITCHEN_DOOR, STATE_UNKNOWN)
    await hass.async_block_till_done()

    await fire_after(hass, timedelta(minutes=5))
    assert vacuum_calls == []
