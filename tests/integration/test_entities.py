"""Integration tests for room entities: overdue sensor, enabled switch, events."""

from __future__ import annotations

from datetime import timedelta

import pytest

from custom_components.vacuum_scheduler.const import DOMAIN, EVENT_CRITICAL_OVERDUE
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.util import dt as dt_util

from .conftest import entity_id_for, fire_refresh, set_state

pytestmark = pytest.mark.integration

KITCHEN_ROBOT = "vacuum.kitchen_robot"


async def test_overdue_sensor_transitions(hass, entry_with_rooms):
    """The overdue sensor follows the coordinator's evaluation."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    overdue = entity_id_for(hass, entry.entry_id, kitchen_sid, "binary_sensor", "room_overdue")

    assert hass.states.get(overdue).state == STATE_OFF

    entry.runtime_data.room_states[kitchen_sid].last_vacuumed = dt_util.now() - timedelta(days=10)
    await fire_refresh(hass)
    state = hass.states.get(overdue)
    assert state.state == STATE_ON
    assert "days_since_vacuum" in state.attributes
    assert state.attributes["days_since_vacuum"] == 10

    await hass.services.async_call(
        DOMAIN,
        "record_cleaning",
        {"room_name": "Kitchen", "mode": "vacuum"},
        blocking=True,
    )
    await fire_refresh(hass)
    assert hass.states.get(overdue).state == STATE_OFF


async def test_enabled_switch_controls_evaluation(hass, entry_with_rooms, vacuum_calls):
    """Turning the enabled switch off makes evaluate_batch skip the room."""
    entry, kitchen_sid, living_sid = entry_with_rooms
    switch = entity_id_for(hass, entry.entry_id, kitchen_sid, "switch", "room_enabled")
    assert hass.states.get(switch).state == STATE_ON

    await hass.services.async_call("switch", "turn_off", {"entity_id": switch}, blocking=True)
    assert hass.states.get(switch).state == STATE_OFF
    assert entry.runtime_data.room_states[kitchen_sid].enabled is False

    set_state(hass, "binary_sensor.kitchen_door", "on")
    set_state(hass, "binary_sensor.living_room_door", "on")
    await hass.async_block_till_done()
    now = dt_util.now()
    entry.runtime_data.room_states[kitchen_sid].last_vacuumed = now - timedelta(days=10)
    entry.runtime_data.room_states[living_sid].last_vacuumed = now - timedelta(days=6)

    await hass.services.async_call(DOMAIN, "evaluate_batch", {}, blocking=True)
    assert all(call["entity_id"] != KITCHEN_ROBOT for call in vacuum_calls)

    await hass.services.async_call("switch", "turn_on", {"entity_id": switch}, blocking=True)
    assert hass.states.get(switch).state == STATE_ON
    assert entry.runtime_data.room_states[kitchen_sid].enabled is True


async def test_critical_overdue_event_fires_once_and_refires(hass, entry_with_rooms):
    """The critical-overdue event fires once per critical period, then refires."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    events = []

    def _listen(event) -> None:
        events.append(event)

    hass.bus.async_listen(EVENT_CRITICAL_OVERDUE, _listen)

    state = entry.runtime_data.room_states[kitchen_sid]
    now = dt_util.now()
    state.last_vacuumed = now - timedelta(days=10)  # 3d frequency + 2d critical
    state.last_mopped = now - timedelta(hours=2)  # mopping not critical

    await fire_refresh(hass)
    assert len(events) == 1
    assert events[0].data == {"room_name": "Kitchen", "mode": "vacuum", "entry_id": entry.entry_id}

    # No duplicate while still critically overdue.
    await fire_refresh(hass)
    assert len(events) == 1

    # Recording a cleaning clears the critical state.
    await hass.services.async_call(
        DOMAIN,
        "record_cleaning",
        {"room_name": "Kitchen", "mode": "vacuum"},
        blocking=True,
    )
    await fire_refresh(hass)
    assert len(events) == 1

    # Becoming critical again fires the event once more.
    state.last_vacuumed = now - timedelta(days=10)
    await fire_refresh(hass)
    assert len(events) == 2
