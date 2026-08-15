"""Integration tests for evaluation edge cases and weird states.

Covers never-cleaned rooms, sensor states that are missing or unavailable,
rooms without door sensors, overnight time windows, window boundaries, clock
skew, disabled rooms, per-mode critical events and a zero batch limit.
"""

from __future__ import annotations

from datetime import time, timedelta

from freezegun import freeze_time as freeze_time_cls
import pytest

from custom_components.vacuum_scheduler.const import DOMAIN, EVENT_CRITICAL_OVERDUE
from custom_components.vacuum_scheduler.service_actions.evaluate_batch import async_handle_evaluate_batch
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.util import dt as dt_util

from .conftest import _create_room_subentry, entity_id_for, fire_refresh, set_state

pytestmark = pytest.mark.integration

KITCHEN_ROBOT = "vacuum.kitchen_robot"
LIVING_ROOM_ROBOT = "vacuum.living_room_robot"
KITCHEN_DOOR = "binary_sensor.kitchen_door"
KITCHEN_SEGMENT = "segment_kitchen"


async def _open_doors(hass: HomeAssistant) -> None:
    """Open all fixture room doors (batch evaluation requires open doors)."""
    set_state(hass, "binary_sensor.kitchen_door", "on")
    set_state(hass, "binary_sensor.living_room_door", "on")
    await hass.async_block_till_done()


def _stale(entry, sid: str, vacuum_days: int, mop_days: int | None = None) -> None:
    """Make a room overdue for vacuuming (and optionally mopping)."""
    now = dt_util.now()
    state = entry.runtime_data.room_states[sid]
    state.last_vacuumed = now - timedelta(days=vacuum_days)
    if mop_days is not None:
        state.last_mopped = now - timedelta(days=mop_days)


async def _evaluate(hass: HomeAssistant, entry, **data) -> dict:
    """Run evaluate_batch and return the result dict."""
    call = ServiceCall(hass=hass, domain=DOMAIN, service="evaluate_batch", data=data)
    return await async_handle_evaluate_batch(hass, entry, call)


def _clean_calls(vacuum_calls: list[dict]) -> list[dict]:
    """Return the recorded clean_area calls."""
    return [call for call in vacuum_calls if call["service"] == "clean_area"]


async def test_never_cleaned_room_is_overdue_and_cleaned(hass, entry_with_rooms, vacuum_calls):
    """A room without any recorded cleaning is overdue and cleaned by the batch."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    state = entry.runtime_data.room_states[kitchen_sid]
    state.last_vacuumed = None
    state.last_mopped = None
    await fire_refresh(hass)

    overdue = entity_id_for(hass, entry.entry_id, kitchen_sid, "binary_sensor", "room_overdue")
    assert hass.states.get(overdue).state == STATE_ON

    await _open_doors(hass)
    result = await _evaluate(hass, entry)

    assert result["rooms_overdue"] == 1
    assert result["errors"] == []
    clean_calls = _clean_calls(vacuum_calls)
    assert len(clean_calls) == 1
    assert clean_calls[0]["entity_id"] == KITCHEN_ROBOT
    assert clean_calls[0]["segments"] == [KITCHEN_SEGMENT]
    assert state.last_vacuumed is not None
    assert state.last_mopped is not None


async def test_never_cleaned_room_added_after_setup(hass, entry_with_rooms, vacuum_calls):
    """A room subentry added later has no persisted state and is overdue at once."""
    entry, _kitchen_sid, _living_sid = entry_with_rooms
    bathroom_sid = await _create_room_subentry(
        hass,
        entry,
        {
            "room_name": "Bathroom",
            "vacuum_entity": KITCHEN_ROBOT,
            "cleaning_area_id": ["area_kitchen"],
            "vacuum_frequency_days": 3,
            "mop_frequency_days": 3,
            "time_window_start": "08:00",
            "time_window_end": "20:00",
        },
    )
    # Reload so the new subentry is picked up without any persisted state.
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    overdue = entity_id_for(hass, entry.entry_id, bathroom_sid, "binary_sensor", "room_overdue")
    assert hass.states.get(overdue).state == STATE_ON

    # No door sensor configured: no door must be open for the new room.
    result = await _evaluate(hass, entry)

    assert result["rooms_overdue"] == 1
    assert result["errors"] == []
    clean_calls = _clean_calls(vacuum_calls)
    assert len(clean_calls) == 1
    assert clean_calls[0]["segments"] == [KITCHEN_SEGMENT]


async def test_missing_door_sensor_entity_skips_room(hass, entry_with_rooms, vacuum_calls):
    """A configured door sensor with no state counts as a closed door."""
    entry, kitchen_sid, living_sid = entry_with_rooms
    entry.runtime_data.rooms[kitchen_sid].door_sensor = "binary_sensor.nonexistent_door"
    _stale(entry, kitchen_sid, vacuum_days=10)
    _stale(entry, living_sid, vacuum_days=6)
    await _open_doors(hass)

    result = await _evaluate(hass, entry)

    assert result["skipped_door_closed"] == ["Kitchen"]
    clean_calls = _clean_calls(vacuum_calls)
    assert len(clean_calls) == 1
    assert clean_calls[0]["entity_id"] == LIVING_ROOM_ROBOT


async def test_unavailable_door_sensor_skips_room(hass, entry_with_rooms, vacuum_calls):
    """An unavailable door sensor is treated like a closed door."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    _stale(entry, kitchen_sid, vacuum_days=10)
    set_state(hass, KITCHEN_DOOR, STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    result = await _evaluate(hass, entry)

    assert "Kitchen" in result["skipped_door_closed"]
    assert vacuum_calls == []


async def test_unknown_door_sensor_skips_room(hass, entry_with_rooms, vacuum_calls):
    """A door sensor reporting unknown (e.g. zigbee down) is treated as closed."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    _stale(entry, kitchen_sid, vacuum_days=10)
    set_state(hass, KITCHEN_DOOR, STATE_UNKNOWN)
    await hass.async_block_till_done()

    result = await _evaluate(hass, entry)

    assert "Kitchen" in result["skipped_door_closed"]
    assert vacuum_calls == []


async def test_room_without_door_sensor_cleans_with_door_closed(hass, entry_with_rooms, vacuum_calls):
    """A room without a door sensor is not gated on any door state."""
    entry, kitchen_sid, living_sid = entry_with_rooms
    entry.runtime_data.rooms[kitchen_sid].door_sensor = None
    _stale(entry, kitchen_sid, vacuum_days=10)
    _stale(entry, living_sid, vacuum_days=6)

    result = await _evaluate(hass, entry)

    assert result["skipped_door_closed"] == ["Living Room"]
    clean_calls = _clean_calls(vacuum_calls)
    assert len(clean_calls) == 1
    assert clean_calls[0]["entity_id"] == KITCHEN_ROBOT


async def test_missing_window_sensor_allows_cleaning(hass, entry_with_rooms, vacuum_calls):
    """A configured window sensor with no state is assumed closed; cleaning runs."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    entry.runtime_data.rooms[kitchen_sid].window_sensor = "binary_sensor.nonexistent_window"
    _stale(entry, kitchen_sid, vacuum_days=10)
    await _open_doors(hass)

    result = await _evaluate(hass, entry)

    assert result["errors"] == []
    assert len(_clean_calls(vacuum_calls)) == 1


@pytest.mark.parametrize("sensor_state", [STATE_UNKNOWN, STATE_UNAVAILABLE])
async def test_non_on_window_sensor_allows_cleaning(hass, entry_with_rooms, vacuum_calls, sensor_state):
    """A window sensor that is unknown or unavailable (zigbee down) is assumed closed."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    entry.runtime_data.rooms[kitchen_sid].window_sensor = "binary_sensor.kitchen_window"
    set_state(hass, "binary_sensor.kitchen_window", sensor_state)
    await hass.async_block_till_done()
    _stale(entry, kitchen_sid, vacuum_days=10)
    await _open_doors(hass)

    result = await _evaluate(hass, entry)

    assert result["errors"] == []
    assert len(_clean_calls(vacuum_calls)) == 1


async def test_overnight_time_window_allows_cleaning_at_night(hass, entry_with_rooms, vacuum_calls):
    """A window spanning midnight allows cleaning after the start time."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    entry.runtime_data.rooms[kitchen_sid].time_window_start = time(22, 0)
    entry.runtime_data.rooms[kitchen_sid].time_window_end = time(6, 0)
    _stale(entry, kitchen_sid, vacuum_days=10)
    await _open_doors(hass)

    with freeze_time_cls("2026-06-15T23:00:00-07:00"):
        result = await _evaluate(hass, entry, dry_run=True)
    assert result["rooms_overdue"] == 1

    with freeze_time_cls("2026-06-15T10:00:00-07:00"):
        result = await _evaluate(hass, entry, dry_run=True)
    assert result["rooms_overdue"] == 0
    assert vacuum_calls == []


async def test_time_window_boundaries_are_inclusive(hass, entry_with_rooms):
    """Evaluation happens at exactly the window start and end times, not before/after."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    _stale(entry, kitchen_sid, vacuum_days=10)
    await _open_doors(hass)

    for boundary in ("2026-06-15T08:00:00-07:00", "2026-06-15T20:00:00-07:00"):
        with freeze_time_cls(boundary):
            result = await _evaluate(hass, entry, dry_run=True)
        assert result["rooms_overdue"] == 1, f"expected overdue at {boundary}"

    for outside in ("2026-06-15T07:59:00-07:00", "2026-06-15T20:01:00-07:00"):
        with freeze_time_cls(outside):
            result = await _evaluate(hass, entry, dry_run=True)
        assert result["rooms_overdue"] == 0, f"expected not overdue at {outside}"


async def test_future_last_cleaned_timestamp_not_overdue(hass, entry_with_rooms, vacuum_calls):
    """A cleaning timestamp in the future (clock skew) never marks the room overdue."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    state = entry.runtime_data.room_states[kitchen_sid]
    state.last_vacuumed = dt_util.now() + timedelta(days=1)
    await fire_refresh(hass)

    overdue = entity_id_for(hass, entry.entry_id, kitchen_sid, "binary_sensor", "room_overdue")
    assert hass.states.get(overdue).state == STATE_OFF

    await _open_doors(hass)
    result = await _evaluate(hass, entry)
    assert result["rooms_overdue"] == 0
    assert vacuum_calls == []


async def test_disabled_room_fires_no_critical_event(hass, entry_with_rooms):
    """Critical-overdue events are suppressed while a room is disabled."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    events = []
    hass.bus.async_listen(EVENT_CRITICAL_OVERDUE, lambda event: events.append(event))

    state = entry.runtime_data.room_states[kitchen_sid]
    state.last_vacuumed = dt_util.now() - timedelta(days=10)
    state.last_mopped = dt_util.now() - timedelta(days=10)
    state.enabled = False
    await fire_refresh(hass)
    assert events == []

    # Re-enabling the room fires the pending critical events.
    state.enabled = True
    await fire_refresh(hass)
    assert {event.data["mode"] for event in events} == {"vacuum", "mop"}


async def test_critical_events_fire_per_mode_and_clear_independently(hass, entry_with_rooms):
    """Vacuum and mop critical events are tracked and cleared separately."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    events = []
    hass.bus.async_listen(EVENT_CRITICAL_OVERDUE, lambda event: events.append(event))

    state = entry.runtime_data.room_states[kitchen_sid]
    now = dt_util.now()
    state.last_vacuumed = now - timedelta(hours=2)  # vacuum fresh
    state.last_mopped = now - timedelta(days=10)  # mop critical (3d + 2d)

    await fire_refresh(hass)
    assert [event.data["mode"] for event in events] == ["mop"]

    # Still critical: no duplicate while fired.
    await fire_refresh(hass)
    assert len(events) == 1

    # Recording the mop clears the mop event; the vacuum becomes critical next.
    await hass.services.async_call(
        DOMAIN,
        "record_cleaning",
        {"room_name": "Kitchen", "mode": "mop"},
        blocking=True,
    )
    state.last_vacuumed = now - timedelta(days=10)
    await fire_refresh(hass)
    assert [event.data["mode"] for event in events] == ["mop", "vacuum"]


async def test_max_rooms_per_batch_zero_cleans_nothing(hass, entry_with_rooms, vacuum_calls, notify_calls):
    """A batch limit of zero prevents cleaning without reporting errors."""
    entry, kitchen_sid, living_sid = entry_with_rooms
    entry.runtime_data.global_config.max_rooms_per_batch = 0
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10)
    _stale(entry, living_sid, vacuum_days=6)

    result = await _evaluate(hass, entry)

    assert result["rooms"] == []
    assert result["errors"] == []
    assert vacuum_calls == []
    assert notify_calls == []


async def test_vacuum_entity_filter_without_matches(hass, entry_with_rooms, vacuum_calls):
    """Filtering for an unknown vacuum evaluates no rooms and cleans nothing."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10)

    result = await _evaluate(hass, entry, vacuum_entity="vacuum.other_robot")

    assert result["rooms_evaluated"] == 0
    assert result["rooms_overdue"] == 0
    assert result["errors"] == []
    assert vacuum_calls == []


async def test_missing_notify_entity_skips_notification(hass, entry_with_rooms, vacuum_calls, notify_calls):
    """Evaluation without a notify entity still cleans and sends no notification."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    entry.runtime_data.global_config.notify_entity = None
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10)

    await hass.services.async_call(DOMAIN, "evaluate_batch", {}, blocking=True)

    assert len(_clean_calls(vacuum_calls)) == 1
    assert notify_calls == []


async def test_dry_run_reports_groups_without_calling_vacuum(hass, entry_with_rooms, vacuum_calls, notify_calls):
    """dry_run returns the planned groups and never touches the vacuum or state."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10, mop_days=10)
    state = entry.runtime_data.room_states[kitchen_sid]
    last_vacuumed_before = state.last_vacuumed

    result = await _evaluate(hass, entry, dry_run=True)

    assert result["dry_run"] is True
    assert result["rooms"] == [
        {
            "vacuum_entity": KITCHEN_ROBOT,
            "needs_mopping": True,
            "fan_speed": "max",
            "mop_intensity": "medium",
            "area_ids": ["area_kitchen"],
            "rooms": ["Kitchen"],
        }
    ]
    assert vacuum_calls == []
    assert len(notify_calls) == 1
    assert notify_calls[0]["title"] == "Vacuum Scheduler - Dry Run"
    assert state.last_vacuumed == last_vacuumed_before
