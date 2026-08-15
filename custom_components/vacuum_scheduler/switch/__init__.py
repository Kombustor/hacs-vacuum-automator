"""Switch platform for vacuum_scheduler."""

from __future__ import annotations

from custom_components.vacuum_scheduler.data import VacuumSchedulerConfigEntry
from custom_components.vacuum_scheduler.switch.enabled import VacuumSchedulerEnabledSwitch
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VacuumSchedulerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch platform.

    Creates one enabled switch per room (subentry).

    Args:
        hass: The Home Assistant instance.
        entry: The config entry.
        async_add_entities: Callback to add entities.

    """
    runtime_data = entry.runtime_data
    coordinator = runtime_data.coordinator

    entities: list[SwitchEntity] = []

    for subentry_id, room_config in runtime_data.rooms.items():
        room_state = runtime_data.room_states[subentry_id]

        # Create enabled switch for this room
        entities.append(
            VacuumSchedulerEnabledSwitch(
                coordinator=coordinator,
                room_config=room_config,
                room_state=room_state,
                entry_id=entry.entry_id,
            )
        )

    async_add_entities(entities)
