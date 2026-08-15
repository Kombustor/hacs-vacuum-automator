"""Service to record a cleaning completion."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from custom_components.vacuum_scheduler.const import (
    CLEANING_MODE_MOP,
    CLEANING_MODE_VACUUM,
    CLEANING_MODE_VACUUM_AND_MOP,
    LOGGER,
)
from custom_components.vacuum_scheduler.data import VacuumSchedulerConfigEntry
from custom_components.vacuum_scheduler.utils import async_save_room_states
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.util import dt as dt_util

# Service call attributes
ATTR_ROOM_NAME = "room_name"
ATTR_MODE = "mode"
ATTR_TIMESTAMP = "timestamp"


async def async_handle_record_cleaning(
    hass: HomeAssistant,
    entry: VacuumSchedulerConfigEntry,
    call: ServiceCall,
) -> dict[str, Any]:
    """Handle record_cleaning service call.

    Service fields:
    - room_name: str (required)
    - mode: str (required) — "vacuum", "mop", or "vacuum_and_mop"
    - timestamp: str | None — ISO format, defaults to now

    Args:
        hass: The Home Assistant instance.
        entry: The config entry.
        call: The service call.

    Returns:
        Dict with "success": True and recorded timestamp on success,
        or "success": False with "error" on failure.

    """
    runtime_data = entry.runtime_data

    room_name = call.data[ATTR_ROOM_NAME]
    mode = call.data[ATTR_MODE]
    timestamp_str = call.data.get(ATTR_TIMESTAMP)

    # Parse timestamp or use now
    if timestamp_str:
        timestamp = datetime.fromisoformat(timestamp_str)
    else:
        timestamp = dt_util.now()

    # Find room by name
    target_subentry_id = None
    for subentry_id, config in runtime_data.rooms.items():
        if config.room_name == room_name:
            target_subentry_id = subentry_id
            break

    if target_subentry_id is None:
        LOGGER.error("Room '%s' not found", room_name)
        return {"success": False, "error": f"Room '{room_name}' not found"}

    room_state = runtime_data.room_states[target_subentry_id]

    # Update appropriate timestamp based on mode
    if mode in (CLEANING_MODE_VACUUM, CLEANING_MODE_VACUUM_AND_MOP):
        room_state.last_vacuumed = timestamp
        LOGGER.debug("Recorded vacuum for room '%s' at %s", room_name, timestamp)

    if mode in (CLEANING_MODE_MOP, CLEANING_MODE_VACUUM_AND_MOP):
        room_state.last_mopped = timestamp
        LOGGER.debug("Recorded mop for room '%s' at %s", room_name, timestamp)

    # Persist to storage
    states_to_save = {sid: state.to_dict() for sid, state in runtime_data.room_states.items()}
    await async_save_room_states(runtime_data.storage, states_to_save)

    # Trigger coordinator refresh to update entities
    await runtime_data.coordinator.async_request_refresh()

    return {
        "success": True,
        "room": room_name,
        "mode": mode,
        "timestamp": timestamp.isoformat(),
    }
