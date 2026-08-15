"""Door sensor listeners for vacuum_scheduler.

When a monitored door opens we wait for the configured stabilization period
and then evaluate the batch for the vacuum entities tied to that door.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from custom_components.vacuum_scheduler.const import DOMAIN, LOGGER, SERVICE_EVALUATE_BATCH
from custom_components.vacuum_scheduler.data import VacuumSchedulerConfigEntry
from custom_components.vacuum_scheduler.service_actions.evaluate_batch import (
    ATTR_DRY_RUN,
    ATTR_VACUUM_ENTITY,
    async_handle_evaluate_batch,
)
from homeassistant.const import STATE_ON
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, ServiceCall, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event


async def async_setup_door_listeners(
    hass: HomeAssistant,
    entry: VacuumSchedulerConfigEntry,
) -> Callable[[], None]:
    """Set up listeners that trigger batch evaluation when a door opens.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry whose rooms should be monitored.

    Returns:
        A callback that unsubscribes all listeners and cancels pending timers.

    """
    runtime_data = entry.runtime_data
    stabilization = timedelta(minutes=runtime_data.global_config.stabilization_period)

    # Map each door sensor to the vacuum entities used by rooms behind that door.
    door_to_vacuums: dict[str, set[str]] = {}
    for config in runtime_data.rooms.values():
        if not config.door_sensor:
            continue
        door_to_vacuums.setdefault(config.door_sensor, set()).add(config.vacuum_entity)

    if not door_to_vacuums:
        return lambda: None

    timers: dict[str, Callable[[], None]] = {}

    async def _evaluate_for_door(door_sensor: str) -> None:
        """Trigger evaluation for all vacuums behind this door."""
        timers.pop(door_sensor, None)
        vacuum_entities = door_to_vacuums.get(door_sensor, set())
        if not vacuum_entities:
            return

        for vacuum_entity in vacuum_entities:
            call = ServiceCall(
                hass=hass,
                domain=DOMAIN,
                service=SERVICE_EVALUATE_BATCH,
                data={ATTR_VACUUM_ENTITY: vacuum_entity, ATTR_DRY_RUN: False},
            )
            try:
                await async_handle_evaluate_batch(hass, entry, call)
            except Exception:  # noqa: BLE001
                LOGGER.exception(
                    "Failed to evaluate batch for door %s vacuum %s",
                    door_sensor,
                    vacuum_entity,
                )

    async def _on_door_change(event: Event[EventStateChangedData]) -> None:
        """Handle door sensor state changes."""
        door_sensor = event.data["entity_id"]
        new_state = event.data["new_state"]

        cancel = timers.pop(door_sensor, None)
        if cancel is not None:
            cancel()

        if new_state is None or new_state.state != STATE_ON:
            return

        if stabilization.total_seconds() <= 0:
            await _evaluate_for_door(door_sensor)
            return

        @callback
        def _timer_fired(_now: datetime) -> None:
            hass.async_create_task(_evaluate_for_door(door_sensor))

        timers[door_sensor] = async_call_later(hass, stabilization, _timer_fired)

    unsubscribes = [
        async_track_state_change_event(hass, door_sensor, _on_door_change) for door_sensor in door_to_vacuums
    ]

    def _cleanup() -> None:
        """Unsubscribe listeners and cancel pending timers."""
        for unsub in unsubscribes:
            unsub()
        for cancel in timers.values():
            cancel()
        timers.clear()

    return _cleanup
