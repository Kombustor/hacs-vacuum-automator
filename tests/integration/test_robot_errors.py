"""Integration tests for robot failures and error recovery during cleaning.

Covers per-robot clean_area failures (isolated to the failing group),
recovery after a robot error, missing vacuum entities, best-effort fan speed
and mop-mode setup, and unknown mop intensities.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from custom_components.vacuum_scheduler.const import DOMAIN
from custom_components.vacuum_scheduler.service_actions.evaluate_batch import async_handle_evaluate_batch
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .conftest import fire_after, set_state
from .fake_vacuum import FakeVacuumEntity

pytestmark = pytest.mark.integration

KITCHEN_ROBOT = "vacuum.kitchen_robot"
LIVING_ROOM_ROBOT = "vacuum.living_room_robot"
KITCHEN_SEGMENT = "segment_kitchen"
LIVING_SEGMENT = "segment_living"


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


def _kitchen_entity(hass: HomeAssistant) -> FakeVacuumEntity:
    """Return the fake kitchen robot entity instance."""
    return hass.data["domain_entities"]["vacuum"][KITCHEN_ROBOT]


async def _failing_clean_segments(segments: list[str], **_: Any) -> None:
    """Stand-in for async_clean_segments that raises like a crashed robot."""
    raise HomeAssistantError("robot crashed")


async def test_robot_clean_error_isolated_to_its_group(hass, entry_with_rooms, vacuum_calls):
    """A failing robot records an error for its group; other robots still clean."""
    entry, kitchen_sid, living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10)
    _stale(entry, living_sid, vacuum_days=6)

    _kitchen_entity(hass).async_clean_segments = _failing_clean_segments  # type: ignore[method-assign]

    result = await _evaluate(hass, entry)

    assert len(result["errors"]) == 1
    assert "Kitchen" in result["errors"][0]
    # The failed room keeps its stale timestamp...
    assert entry.runtime_data.room_states[kitchen_sid].last_vacuumed < dt_util.now() - timedelta(days=9)
    # ...while the successful room is marked cleaned.
    assert entry.runtime_data.room_states[living_sid].last_vacuumed > dt_util.now() - timedelta(minutes=1)
    clean_calls = [call for call in vacuum_calls if call["service"] == "clean_area"]
    assert [call["entity_id"] for call in clean_calls] == [LIVING_ROOM_ROBOT]
    assert clean_calls[0]["segments"] == [LIVING_SEGMENT]


async def test_robot_recovers_after_clean_error(hass, entry_with_rooms, vacuum_calls):
    """Once the robot recovers, the next evaluation cleans the pending room."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10)

    kitchen = _kitchen_entity(hass)
    kitchen.async_clean_segments = _failing_clean_segments  # type: ignore[method-assign]

    result = await _evaluate(hass, entry)
    assert len(result["errors"]) == 1
    assert all(call["service"] != "clean_area" for call in vacuum_calls)

    del kitchen.async_clean_segments  # the robot recovers
    result = await _evaluate(hass, entry)

    assert result["errors"] == []
    clean_calls = [call for call in vacuum_calls if call["service"] == "clean_area"]
    assert len(clean_calls) == 1
    assert clean_calls[0]["segments"] == [KITCHEN_SEGMENT]
    assert entry.runtime_data.room_states[kitchen_sid].last_vacuumed > dt_util.now() - timedelta(minutes=1)


async def test_missing_vacuum_entity_is_silently_skipped(hass, entry_with_rooms, vacuum_calls):
    """A room pointing at a nonexistent vacuum records no call and no error.

    HA's entity services silently skip unknown entity ids (they only log), so
    the batch handler sees success and marks the room cleaned. This
    characterises that behaviour so a validation guard in this integration
    updates the test deliberately.
    """
    entry, kitchen_sid, _living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10)
    entry.runtime_data.rooms[kitchen_sid].vacuum_entity = "vacuum.deleted_robot"

    result = await _evaluate(hass, entry)

    assert result["errors"] == []
    assert vacuum_calls == []
    assert entry.runtime_data.room_states[kitchen_sid].last_vacuumed > dt_util.now() - timedelta(minutes=1)


async def test_unavailable_robot_is_silently_skipped(hass, entry_with_rooms, vacuum_calls):
    """An unavailable robot (e.g. zigbee down) gets no clean call and no error.

    HA's entity services filter out unavailable entities before dispatch, so
    the batch handler sees success and marks the room cleaned. This
    characterises that behaviour, same as for a nonexistent vacuum entity.
    """
    entry, kitchen_sid, _living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10)
    _kitchen_entity(hass)._attr_available = False

    result = await _evaluate(hass, entry)

    assert result["errors"] == []
    assert vacuum_calls == []
    assert entry.runtime_data.room_states[kitchen_sid].last_vacuumed > dt_util.now() - timedelta(minutes=1)


async def test_door_trigger_with_missing_vacuum_does_not_crash(hass, entry_with_rooms, vacuum_calls):
    """A door trigger whose robot is gone completes without raising."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    entry.runtime_data.rooms[kitchen_sid].vacuum_entity = "vacuum.deleted_robot"
    _stale(entry, kitchen_sid, vacuum_days=10)

    set_state(hass, "binary_sensor.kitchen_door", "on")
    await hass.async_block_till_done()
    await fire_after(hass, timedelta(minutes=5))

    assert vacuum_calls == []


async def test_set_fan_speed_failure_is_best_effort(hass, entry_with_rooms, vacuum_calls):
    """A missing set_fan_speed service does not stop the cleaning."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10)

    hass.services.async_remove("vacuum", "set_fan_speed")
    result = await _evaluate(hass, entry)

    assert result["errors"] == []
    clean_calls = [call for call in vacuum_calls if call["service"] == "clean_area"]
    assert len(clean_calls) == 1
    assert clean_calls[0]["segments"] == [KITCHEN_SEGMENT]


async def test_unknown_mop_intensity_skips_mop_command(hass, entry_with_rooms, vacuum_calls):
    """An unrecognised mop intensity value skips send_command, not the clean."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    await _open_doors(hass)
    _stale(entry, kitchen_sid, vacuum_days=10, mop_days=10)
    entry.runtime_data.rooms[kitchen_sid].mop_intensity = "turbo"

    result = await _evaluate(hass, entry)

    assert result["errors"] == []
    assert [call["service"] for call in vacuum_calls] == ["set_fan_speed", "clean_area"]
