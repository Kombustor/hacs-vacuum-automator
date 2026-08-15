"""Service to evaluate and trigger batch cleaning."""

from __future__ import annotations

from typing import Any

from custom_components.vacuum_scheduler.const import LOGGER, MOP_INTENSITY_COMMAND_MAP, MOP_INTENSITY_OFF
from custom_components.vacuum_scheduler.coordinator.base import _urgency, is_overdue, is_within_time_window
from custom_components.vacuum_scheduler.data import RoomConfig, RoomState, VacuumSchedulerConfigEntry
from custom_components.vacuum_scheduler.utils import async_save_room_states, async_send_notification, async_translate
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

# Service call attributes
ATTR_VACUUM_ENTITY = "vacuum_entity"
ATTR_DRY_RUN = "dry_run"


async def async_trigger_room_cleaning(
    hass: HomeAssistant,
    vacuum_entity: str,
    area_ids: list[str],
    needs_mopping: bool,
    fan_speed: str | None,
    mop_intensity: str | None,
) -> None:
    """Trigger vacuum cleaning for the specified areas.

    Sets mop mode and fan speed before starting the cleaning job.
    Always sets fan speed if a value is provided (global default or room override).
    Manages the water box mode whenever mopping is configured (mop_intensity
    is not None): arms the configured intensity when mopping is needed, and
    resets the water box to OFF for vacuum-only runs so the vacuum does not
    inherit a previously armed mop mode.

    Args:
        hass: The Home Assistant instance.
        vacuum_entity: The vacuum entity ID.
        area_ids: List of HA area IDs to clean.
        needs_mopping: Whether mopping is needed (determines mop mode command).
        fan_speed: Optional fan speed preset (global default or room override).
        mop_intensity: Optional mop intensity preset (global default or room override).

    """
    # Set mopping behavior if the vacuum is configured for mopping.
    # This is best-effort: if the vacuum does not support the send_command
    # service or the specific command, we log a warning and proceed.
    if mop_intensity:
        if needs_mopping:
            mop_command_value = MOP_INTENSITY_COMMAND_MAP.get(mop_intensity)
        else:
            # Vacuum-only run: reset the water box so a previously armed mop
            # mode does not make clean_area run vacuum+mop.
            mop_command_value = MOP_INTENSITY_COMMAND_MAP[MOP_INTENSITY_OFF]
        if mop_command_value is not None:
            LOGGER.debug(
                "Setting water box custom mode to %s (%d) for %s",
                MOP_INTENSITY_OFF if not needs_mopping else mop_intensity,
                mop_command_value,
                vacuum_entity,
            )
            try:
                await hass.services.async_call(
                    "vacuum",
                    "send_command",
                    {
                        "entity_id": vacuum_entity,
                        "command": "set_water_box_custom_mode",
                        "params": [mop_command_value],
                    },
                    blocking=True,
                )
            except Exception:  # noqa: BLE001
                LOGGER.warning(
                    "Failed to set mop mode for %s — continuing with clean_area",
                    vacuum_entity,
                )

    # Set fan speed if specified (global default or room override).
    # This is best-effort: if the vacuum does not support set_fan_speed,
    # we log a warning and proceed.
    if fan_speed:
        LOGGER.debug("Setting fan speed to %s for %s", fan_speed, vacuum_entity)
        try:
            await hass.services.async_call(
                "vacuum",
                "set_fan_speed",
                {
                    "entity_id": vacuum_entity,
                    "fan_speed": fan_speed,
                },
                blocking=True,
            )
        except Exception:  # noqa: BLE001
            LOGGER.warning(
                "Failed to set fan speed for %s — continuing with clean_area",
                vacuum_entity,
            )

    # Start area cleaning — this is the critical call.
    # If this fails the exception propagates to the caller (batch handler or
    # door trigger), which has its own per-group error handling.
    LOGGER.info(
        "Starting cleaning for areas %s on %s",
        area_ids,
        vacuum_entity,
    )
    await hass.services.async_call(
        "vacuum",
        "clean_area",
        {
            "entity_id": vacuum_entity,
            "cleaning_area_id": area_ids,
        },
        blocking=True,
    )


async def _async_notify_evaluated(
    hass: HomeAssistant,
    notify_entity: str | None,
    overdue_rooms: list[tuple[str, RoomConfig, dict[str, bool]]],
    dry_run: bool,
) -> None:
    """Send a notification summarising the evaluated batch."""
    room_names = [config.room_name for _, config, _ in overdue_rooms]
    rooms_str = ", ".join(room_names)
    placeholders = {
        "count": str(len(overdue_rooms)),
        "rooms": rooms_str,
    }
    if dry_run:
        notify_title = await async_translate(hass, "dry_run_title")
        notify_message = await async_translate(hass, "dry_run_message", placeholders)
    else:
        notify_title = await async_translate(hass, "cleaning_started_title")
        notify_message = await async_translate(hass, "cleaning_started_message", placeholders)

    await async_send_notification(
        hass,
        notify_entity,
        notify_message,
        notify_title,
    )


async def async_handle_evaluate_batch(
    hass: HomeAssistant,
    entry: VacuumSchedulerConfigEntry,
    call: ServiceCall,
) -> dict[str, Any]:
    """Handle evaluate_batch service call.

    Evaluates all rooms and triggers cleaning for overdue rooms that have
    their door open. Groups rooms by vacuum entity and cleaning settings
    (fan speed, mop intensity, needs mopping) so that vacuum-only rooms
    are not mopped when batched with rooms that need mopping.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry.
        call: The service call.

    Returns:
        Dict with evaluation results.

    """
    runtime_data = entry.runtime_data
    global_config = runtime_data.global_config

    # Get service call parameters
    vacuum_entity = call.data.get(ATTR_VACUUM_ENTITY)
    # Use service call dry_run if specified, otherwise use global setting
    service_dry_run = call.data.get(ATTR_DRY_RUN)
    if service_dry_run is not None:
        dry_run = service_dry_run
    else:
        dry_run = global_config.global_dry_run

    now = dt_util.now()
    # Build rooms dict for evaluation.
    # Filters are applied before the scheduling engine to avoid including
    # rooms that cannot be cleaned right now (blocked doors/windows).
    rooms: dict[str, tuple[RoomConfig, RoomState]] = {}
    skipped_doors: list[str] = []
    for subentry_id, config in runtime_data.rooms.items():
        # Filter by vacuum entity if specified
        if vacuum_entity and config.vacuum_entity != vacuum_entity:
            continue

        state = runtime_data.room_states[subentry_id]
        if not state.enabled:
            continue

        # Skip rooms with no cleaning areas configured
        if not config.cleaning_area_id:
            LOGGER.warning(
                "Skipping room '%s' — no cleaning_area_id configured",
                config.room_name,
            )
            continue

        # Check door sensor if configured: batch evaluation requires the door open
        # (consistent with services.yaml: "overdue rooms with open doors")
        if config.door_sensor:
            door_state = hass.states.get(config.door_sensor)
            if door_state is None or door_state.state != STATE_ON:
                LOGGER.debug(
                    "Skipping room '%s' — door sensor %s is not open",
                    config.room_name,
                    config.door_sensor,
                )
                skipped_doors.append(config.room_name)
                continue

        # Check window sensor if configured and not allowed to clean when open
        if config.window_sensor and not global_config.allow_cleaning_when_window_open:
            window_state = hass.states.get(config.window_sensor)
            if window_state and window_state.state == STATE_ON:
                LOGGER.debug("Skipping room '%s' - window is open", config.room_name)
                continue

        rooms[subentry_id] = (config, state)

    # Evaluate each room: check overdue status + time window.
    # Sorted by urgency (most overdue first) before capping.
    overdue_rooms: list[tuple[str, RoomConfig, dict[str, bool]]] = []
    for subentry_id, (config, state) in rooms.items():
        vacuum_overdue = is_overdue(state.last_vacuumed, config.vacuum_frequency_days, now)
        mop_overdue = bool(
            config.mop_frequency_days is not None and is_overdue(state.last_mopped, config.mop_frequency_days, now)
        )
        if mop_overdue:
            vacuum_overdue = True

        if not (vacuum_overdue or mop_overdue):
            continue

        if not is_within_time_window(config.time_window_start, config.time_window_end, now):
            continue

        overdue_details: dict[str, bool] = {"vacuum": vacuum_overdue}
        if config.mop_frequency_days is not None:
            overdue_details["mop"] = mop_overdue

        overdue_rooms.append((subentry_id, config, overdue_details))

    # Sort by urgency: most overdue first. Only consider mop urgency for rooms
    # that actually have mopping configured.
    overdue_rooms.sort(
        key=lambda item: max(
            _urgency(
                rooms[item[0]][1].last_vacuumed,
                item[1].vacuum_frequency_days,
                now,
            ),
            (
                _urgency(
                    rooms[item[0]][1].last_mopped,
                    item[1].mop_frequency_days,
                    now,
                )
                if item[1].mop_frequency_days is not None
                else 0.0
            ),
        ),
        reverse=True,
    )

    # Apply max rooms per batch limit
    max_rooms = global_config.max_rooms_per_batch
    if len(overdue_rooms) > max_rooms:
        LOGGER.info(
            "Limiting batch from %d to %d rooms (max_rooms_per_batch)",
            len(overdue_rooms),
            max_rooms,
        )
        overdue_rooms = overdue_rooms[:max_rooms]

    result: dict[str, Any] = {
        "dry_run": dry_run,
        "rooms_evaluated": len(rooms),
        "rooms_overdue": len(overdue_rooms),
        "rooms_skipped_door_closed": len(skipped_doors),
        "skipped_door_closed": skipped_doors,
        "rooms": [],
        "errors": [],
    }

    # Group overdue rooms by vacuum entity and cleaning settings.
    # Rooms with different fan speeds or mop requirements are separated
    # so that vacuum-only rooms are not mopped alongside mopping rooms.
    # key: (vacuum_entity, effective_fan, needs_mopping, effective_mop)
    cleaning_groups: dict[
        tuple[str, str | None, bool, str | None],
        list[tuple[str, RoomConfig, dict[str, bool]]],
    ] = {}

    for subentry_id, config, overdue_details in overdue_rooms:
        effective_fan = config.fan_speed or global_config.default_fan_speed
        needs_mopping = bool(overdue_details.get("mop"))
        effective_mop = (config.mop_intensity or global_config.default_mop_intensity) if needs_mopping else None

        group_key = (config.vacuum_entity, effective_fan, needs_mopping, effective_mop)
        cleaning_groups.setdefault(group_key, []).append((subentry_id, config, overdue_details))

    # Trigger cleaning for each group, catching errors per group so one
    # failing vacuum call does not prevent the remaining groups.
    for (vacuum_ent, fan_speed, grp_needs_mopping, mop_intensity), room_group in cleaning_groups.items():
        # Collect all area IDs for this group
        all_area_ids: list[str] = []
        room_names: list[str] = []
        for _sid, config, _overdue in room_group:
            all_area_ids.extend(config.cleaning_area_id)
            room_names.append(config.room_name)

        room_result: dict[str, Any] = {
            "vacuum_entity": vacuum_ent,
            "needs_mopping": grp_needs_mopping,
            "fan_speed": fan_speed,
            "mop_intensity": mop_intensity,
            "area_ids": all_area_ids,
            "rooms": room_names,
        }
        result["rooms"].append(room_result)

        # Vacuum-only group: if any room has mopping configured (room override
        # or global default), reset the water box to OFF so the vacuum does
        # not run vacuum+mop from a previously armed mop mode.
        trigger_mop_intensity = mop_intensity
        if not grp_needs_mopping:
            trigger_mop_intensity = next(
                (
                    config.mop_intensity or global_config.default_mop_intensity
                    for _sid, config, _overdue in room_group
                    if config.mop_intensity or global_config.default_mop_intensity
                ),
                None,
            )

        if dry_run:
            continue

        LOGGER.info(
            "Triggering cleaning for rooms %s on %s (areas: %s, mopping: %s, fan: %s)",
            room_names,
            vacuum_ent,
            all_area_ids,
            grp_needs_mopping,
            fan_speed,
        )
        try:
            await async_trigger_room_cleaning(
                hass,
                vacuum_ent,
                all_area_ids,
                needs_mopping=grp_needs_mopping,
                fan_speed=fan_speed,
                mop_intensity=trigger_mop_intensity,
            )
        except HomeAssistantError as exc:
            error_msg = f"Failed to trigger cleaning for {room_names} on {vacuum_ent}: {exc}"
            LOGGER.error(error_msg)
            room_result["error"] = str(exc)
            result["errors"].append(error_msg)
            continue

        # Record that the rooms were cleaned now (vacuum always runs; mop only
        # when the group required it).
        for sid, _config, overdue in room_group:
            state = runtime_data.room_states[sid]
            state.last_vacuumed = now
            if overdue.get("mop"):
                state.last_mopped = now

    # Persist updated timestamps so they survive a restart.
    states_to_save = {sid: state.to_dict() for sid, state in runtime_data.room_states.items()}
    await async_save_room_states(runtime_data.storage, states_to_save)

    # Notify when rooms were evaluated, using a different message for dry runs.
    if result["rooms"]:
        await _async_notify_evaluated(
            hass,
            global_config.notify_entity,
            overdue_rooms,
            dry_run,
        )

    return result
