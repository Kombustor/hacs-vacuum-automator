"""Vacuum Scheduler integration for Home Assistant.

This integration provides room-based vacuum scheduling with:
- Per-room cleaning frequency configuration
- Door/window sensor gating
- Automatic cleaning triggers
- Batch evaluation service
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.vacuum_scheduler.const import DOMAIN, LOGGER, PLATFORMS, STORAGE_VERSION
from custom_components.vacuum_scheduler.coordinator import VacuumSchedulerCoordinator
from custom_components.vacuum_scheduler.data import (
    GlobalConfig,
    RoomConfig,
    RoomState,
    VacuumSchedulerConfigEntry,
    VacuumSchedulerData,
)
from custom_components.vacuum_scheduler.service_actions import async_setup_services
from custom_components.vacuum_scheduler.utils import async_load_room_states
from custom_components.vacuum_scheduler.utils.listeners import async_setup_door_listeners
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.storage import Store

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# This integration is configured via config entries only
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration.

    This is called once at Home Assistant startup to register service actions.
    Service actions must be registered here (not in async_setup_entry).

    Args:
        hass: The Home Assistant instance.
        config: The Home Assistant configuration.

    Returns:
        True if setup was successful.

    """
    await async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VacuumSchedulerConfigEntry,
) -> bool:
    """Set up this integration using UI.

    This is called when a config entry is loaded. It:
    1. Initializes storage for persisting room states
    2. Loads persisted room states
    3. Collects RoomConfig from all subentries
    4. Initializes the coordinator
    5. Sets up door-open listeners for monitored rooms
    6. Performs the first data refresh
    7. Sets up all platforms

    Args:
        hass: The Home Assistant instance.
        entry: The config entry being set up.

    Returns:
        True if setup was successful.

    """
    # Initialize storage
    store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")

    # Load persisted room states
    persisted_states = await async_load_room_states(store)

    # Collect RoomConfig from all subentries
    rooms: dict[str, RoomConfig] = {}
    room_states: dict[str, RoomState] = {}

    for subentry in entry.subentries.values():
        cfg = RoomConfig.from_subentry_data(subentry.subentry_id, dict(subentry.data))
        rooms[subentry.subentry_id] = cfg

        # Load persisted state or create new
        persisted = persisted_states.get(subentry.subentry_id, {})  # type: ignore[attr-defined]
        room_states[subentry.subentry_id] = RoomState.from_dict(persisted)  # type: ignore[attr-defined]

    LOGGER.debug(
        "Loaded %d rooms for entry %s",
        len(rooms),
        entry.entry_id,
    )
    # Load global config from entry data merged with options
    global_config = GlobalConfig.from_entry_data({**entry.data, **entry.options})

    # Initialize coordinator
    coordinator = VacuumSchedulerCoordinator(hass, entry)

    # Store runtime data
    entry.runtime_data = VacuumSchedulerData(
        storage=store,
        global_config=global_config,
        rooms=rooms,
        room_states=room_states,
        coordinator=coordinator,
    )

    # Set up door-open listeners and wire cleanup
    entry.async_on_unload(await async_setup_door_listeners(hass, entry))

    # First refresh and forward platforms
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: VacuumSchedulerConfigEntry,
) -> bool:
    """Unload a config entry.

    This is called when the integration is being removed or reloaded.
    It ensures proper cleanup of:
    - All platform entities
    - Update listeners

    Args:
        hass: The Home Assistant instance.
        entry: The config entry being unloaded.

    Returns:
        True if unload was successful.

    """
    # Shut down coordinator polling loop
    runtime_data = entry.runtime_data
    await runtime_data.coordinator.async_shutdown()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: VacuumSchedulerConfigEntry,
) -> None:
    """Reload config entry.

    This is called when the integration configuration or options have changed.
    It unloads and then reloads the integration with the new configuration.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry being reloaded.

    """
    await hass.config_entries.async_reload(entry.entry_id)
