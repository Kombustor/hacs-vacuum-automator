"""Integration tests for the evaluate_batch service."""

from __future__ import annotations

from datetime import timedelta

from freezegun import freeze_time as freeze_time_cls
import pytest

from custom_components.vacuum_scheduler.const import DOMAIN
from custom_components.vacuum_scheduler.service_actions.evaluate_batch import async_handle_evaluate_batch
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.util import dt as dt_util

from .conftest import set_state

pytestmark = pytest.mark.integration

KITCHEN_ROBOT = "vacuum.kitchen_robot"
LIVING_ROOM_ROBOT = "vacuum.living_room_robot"
KITCHEN_SEGMENT = "segment_kitchen"
LIVING_SEGMENT = "segment_living"


async def _open_doors(hass: HomeAssistant) -> None:
    """Open both room doors (evaluate_batch requires open doors)."""
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


def _clean_calls(vacuum_calls: list[dict]) -> list[dict]:
    """Return the recorded clean_area calls."""
    return [call for call in vacuum_calls if call["service"] == "clean_area"]


async def test_full_trigger_single_room(hass, entry_with_rooms, vacuum_calls, notify_calls):
    """Kitchen overdue (vacuum + mop): mop mode, fan speed, then clean_area."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10, mop_days=10)
    # Living Room was cleaned 2 days ago (frequency 5) -> not overdue.

    await hass.services.async_call(DOMAIN, "evaluate_batch", {}, blocking=True)

    assert [call["service"] for call in vacuum_calls] == ["send_command", "set_fan_speed", "clean_area"]
    assert vacuum_calls[0] == {
        "service": "send_command",
        "entity_id": KITCHEN_ROBOT,
        "command": "set_water_box_custom_mode",
        "params": [202],  # MOP_INTENSITY_COMMAND_MAP["medium"]
    }
    assert vacuum_calls[1] == {"service": "set_fan_speed", "entity_id": KITCHEN_ROBOT, "fan_speed": "max"}
    assert vacuum_calls[2] == {
        "service": "clean_area",
        "entity_id": KITCHEN_ROBOT,
        "segments": [KITCHEN_SEGMENT],
    }
    # Living Room's vacuum was never touched.
    assert all(call["entity_id"] == KITCHEN_ROBOT for call in vacuum_calls)

    assert len(notify_calls) == 1
    assert notify_calls[0]["title"] == "Vacuum Scheduler - Cleaning Started"
    assert "Kitchen" in notify_calls[0]["message"]
    assert "1 room" in notify_calls[0]["message"]


async def test_groups_rooms_on_same_vacuum(hass, entry_with_rooms, vacuum_calls):
    """Two overdue rooms on the same vacuum become one clean_area call."""
    entry, kitchen_sid, living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10)
    _stale(entry, living_sid, vacuum_days=6)
    # Same vacuum + same fan speed + no mopping -> one group.
    entry.runtime_data.rooms[living_sid].vacuum_entity = KITCHEN_ROBOT
    entry.runtime_data.rooms[living_sid].fan_speed = "max"

    await hass.services.async_call(DOMAIN, "evaluate_batch", {}, blocking=True)

    clean_calls = _clean_calls(vacuum_calls)
    assert len(clean_calls) == 1
    assert clean_calls[0]["entity_id"] == KITCHEN_ROBOT
    assert clean_calls[0]["segments"] == [KITCHEN_SEGMENT, LIVING_SEGMENT]
    # Vacuum-only group: no mop mode command.
    assert all(call["service"] != "send_command" for call in vacuum_calls)


async def test_separates_mopping_and_vacuum_only_groups(hass, entry_with_rooms, vacuum_calls):
    """Rooms with different mop needs are cleaned in separate groups."""
    entry, kitchen_sid, living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10, mop_days=10)
    _stale(entry, living_sid, vacuum_days=6)
    entry.runtime_data.rooms[living_sid].vacuum_entity = KITCHEN_ROBOT
    entry.runtime_data.rooms[living_sid].mop_frequency_days = 3
    # Living Room mop is not overdue -> vacuum-only group.

    await hass.services.async_call(DOMAIN, "evaluate_batch", {}, blocking=True)

    assert [call["service"] for call in vacuum_calls] == [
        "send_command",
        "set_fan_speed",
        "clean_area",
        "clean_area",
    ]
    assert vacuum_calls[0]["command"] == "set_water_box_custom_mode"
    assert vacuum_calls[2]["segments"] == [KITCHEN_SEGMENT]
    assert vacuum_calls[3]["segments"] == [LIVING_SEGMENT]
    # The vacuum-only group gets no send_command.
    assert all(call["service"] != "send_command" for call in vacuum_calls[3:])


async def test_dry_run_service_argument(hass, entry_with_rooms, vacuum_calls, notify_calls):
    """dry_run=True records nothing on the vacuums and sends a dry-run notice."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10, mop_days=10)

    await hass.services.async_call(DOMAIN, "evaluate_batch", {"dry_run": True}, blocking=True)

    assert vacuum_calls == []
    assert len(notify_calls) == 1
    assert notify_calls[0]["title"] == "Vacuum Scheduler - Dry Run"
    assert "Kitchen" in notify_calls[0]["message"]


async def test_global_dry_run(hass, entry_with_rooms, vacuum_calls, notify_calls):
    """global_config.global_dry_run applies when the service arg is absent."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10, mop_days=10)
    entry.runtime_data.global_config.global_dry_run = True

    await hass.services.async_call(DOMAIN, "evaluate_batch", {}, blocking=True)

    assert vacuum_calls == []
    assert notify_calls[0]["title"] == "Vacuum Scheduler - Dry Run"


async def test_max_rooms_per_batch_cleans_most_urgent_first(hass, entry_with_rooms, vacuum_calls):
    """With max_rooms_per_batch=1 only the most overdue room is cleaned."""
    entry, kitchen_sid, living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10)  # 7 days past the 3-day frequency
    _stale(entry, living_sid, vacuum_days=6)  # 1 day past the 5-day frequency
    entry.runtime_data.global_config.max_rooms_per_batch = 1

    await hass.services.async_call(DOMAIN, "evaluate_batch", {}, blocking=True)

    clean_calls = _clean_calls(vacuum_calls)
    assert len(clean_calls) == 1
    assert clean_calls[0]["entity_id"] == KITCHEN_ROBOT
    assert clean_calls[0]["segments"] == [KITCHEN_SEGMENT]


async def test_vacuum_entity_filter(hass, entry_with_rooms, vacuum_calls):
    """vacuum_entity restricts evaluation to that vacuum's rooms."""
    entry, kitchen_sid, living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10, mop_days=10)
    _stale(entry, living_sid, vacuum_days=6)

    await hass.services.async_call(
        DOMAIN,
        "evaluate_batch",
        {"vacuum_entity": KITCHEN_ROBOT},
        blocking=True,
    )

    clean_calls = _clean_calls(vacuum_calls)
    assert len(clean_calls) == 1
    assert clean_calls[0]["entity_id"] == KITCHEN_ROBOT


async def test_door_closed_skips_room(hass, entry_with_rooms, vacuum_calls):
    """A closed door skips the room and is reported in the result."""
    entry, kitchen_sid, living_sid = entry_with_rooms
    # Kitchen door stays closed; open only the living room door.
    set_state(hass, "binary_sensor.living_room_door", "on")
    await hass.async_block_till_done()
    _stale(entry, kitchen_sid, vacuum_days=10, mop_days=10)
    _stale(entry, living_sid, vacuum_days=6)

    call = ServiceCall(hass=hass, domain=DOMAIN, service="evaluate_batch", data={})
    result = await async_handle_evaluate_batch(hass, entry, call)

    assert result["rooms_skipped_door_closed"] == 1
    assert result["skipped_door_closed"] == ["Kitchen"]
    clean_calls = _clean_calls(vacuum_calls)
    assert len(clean_calls) == 1
    assert clean_calls[0]["entity_id"] == LIVING_ROOM_ROBOT


async def test_window_open_skips_room_unless_allowed(hass, entry_with_rooms, vacuum_calls):
    """An open window blocks cleaning unless allow_cleaning_when_window_open."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10, mop_days=10)
    entry.runtime_data.rooms[kitchen_sid].window_sensor = "binary_sensor.kitchen_window"
    set_state(hass, "binary_sensor.kitchen_window", "on")
    await hass.async_block_till_done()

    await hass.services.async_call(DOMAIN, "evaluate_batch", {}, blocking=True)
    assert vacuum_calls == []

    entry.runtime_data.global_config.allow_cleaning_when_window_open = True
    await hass.services.async_call(DOMAIN, "evaluate_batch", {}, blocking=True)
    assert len(_clean_calls(vacuum_calls)) == 1


async def test_disabled_room_skipped(hass, entry_with_rooms, vacuum_calls):
    """A room with enabled=False is not evaluated at all."""
    entry, kitchen_sid, living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10, mop_days=10)
    _stale(entry, living_sid, vacuum_days=6)
    entry.runtime_data.room_states[kitchen_sid].enabled = False

    await hass.services.async_call(DOMAIN, "evaluate_batch", {}, blocking=True)

    clean_calls = _clean_calls(vacuum_calls)
    assert len(clean_calls) == 1
    assert clean_calls[0]["entity_id"] == LIVING_ROOM_ROBOT


async def test_outside_time_window_no_cleaning(hass, entry_with_rooms, vacuum_calls, notify_calls):
    """Rooms outside their time window are not cleaned."""
    entry, kitchen_sid, living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10, mop_days=10)
    _stale(entry, living_sid, vacuum_days=6)

    with freeze_time_cls("2026-06-15T22:00:00-07:00"):
        call = ServiceCall(hass=hass, domain=DOMAIN, service="evaluate_batch", data={})
        result = await async_handle_evaluate_batch(hass, entry, call)

    assert result["rooms_overdue"] == 0
    assert vacuum_calls == []
    assert notify_calls == []


async def test_missing_cleaning_area_skips_without_error(hass, entry_with_rooms, vacuum_calls):
    """A room without cleaning_area_id is skipped and reported without errors."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10, mop_days=10)
    entry.runtime_data.rooms[kitchen_sid].cleaning_area_id = []

    call = ServiceCall(hass=hass, domain=DOMAIN, service="evaluate_batch", data={})
    result = await async_handle_evaluate_batch(hass, entry, call)

    assert result["errors"] == []
    assert vacuum_calls == []


async def test_send_command_failure_is_best_effort(hass, entry_with_rooms, vacuum_calls):
    """A missing send_command service does not stop the cleaning."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10, mop_days=10)

    hass.services.async_remove("vacuum", "send_command")
    call = ServiceCall(hass=hass, domain=DOMAIN, service="evaluate_batch", data={})
    result = await async_handle_evaluate_batch(hass, entry, call)

    assert result["errors"] == []
    clean_calls = _clean_calls(vacuum_calls)
    assert len(clean_calls) == 1
    assert clean_calls[0]["segments"] == [KITCHEN_SEGMENT]


async def test_clean_area_failure_recorded_and_other_groups_processed(hass, entry_with_rooms, vacuum_calls):
    """A failing clean_area is recorded per group and does not stop the loop."""
    entry, kitchen_sid, living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10, mop_days=10)
    _stale(entry, living_sid, vacuum_days=6)
    # Different vacuums -> two groups; both fail at clean_area.

    hass.services.async_remove("vacuum", "clean_area")
    call = ServiceCall(hass=hass, domain=DOMAIN, service="evaluate_batch", data={})
    result = await async_handle_evaluate_batch(hass, entry, call)

    assert len(result["errors"]) == 2
    # Timestamps are not updated for failed groups.
    assert entry.runtime_data.room_states[kitchen_sid].last_vacuumed < dt_util.now() - timedelta(days=9)
