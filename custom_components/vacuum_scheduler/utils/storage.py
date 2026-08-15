"""Storage utilities for persisting room states."""

from __future__ import annotations

from typing import Any

from custom_components.vacuum_scheduler.const import LOGGER, STORAGE_VERSION
from custom_components.vacuum_scheduler.data import RoomState
from homeassistant.helpers.storage import Store


async def async_load_room_states(store: Store) -> dict[str, dict[str, Any]]:
    """Load persisted room states from storage.

    Args:
        store: The Store instance to load from.

    Returns:
        Dict mapping subentry_id to serialized room state dict.
        Returns empty dict if no data exists or on error.

    """
    try:
        data = await store.async_load()
        if data is None:
            return {}
        return data.get("rooms", {})
    except Exception:  # noqa: BLE001
        LOGGER.exception("Failed to load room states from storage")
        return {}


async def async_save_room_states(
    store: Store,
    states: dict[str, Any],
) -> bool:
    """Persist room states to storage.

    Args:
        store: The Store instance to save to.
        states: Dict mapping subentry_id to RoomState or dict.

    Returns:
        True if save succeeded, False otherwise.

    """
    try:
        # Convert RoomState objects to dicts if needed
        serialized = {}
        for subentry_id, state in states.items():
            if isinstance(state, RoomState):
                serialized[subentry_id] = state.to_dict()
            else:
                serialized[subentry_id] = state

        await store.async_save({"version": STORAGE_VERSION, "rooms": serialized})
    except Exception:  # noqa: BLE001
        LOGGER.exception("Failed to save room states to storage")
        return False
    else:
        return True


def room_state_to_dict(state: RoomState) -> dict[str, Any]:
    """Serialize a RoomState for storage.

    Args:
        state: The RoomState to serialize.

    Returns:
        Dict representation of the state.

    """
    return state.to_dict()


def room_state_from_dict(data: dict[str, Any]) -> RoomState:
    """Deserialize a RoomState from storage.

    Args:
        data: The dict to deserialize from.

    Returns:
        A RoomState instance.

    """
    return RoomState.from_dict(data)
