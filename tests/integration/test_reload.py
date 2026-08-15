"""Integration tests for state persistence across config entry reloads."""

from __future__ import annotations

from datetime import timedelta

import pytest

from custom_components.vacuum_scheduler.const import DOMAIN, STORAGE_VERSION
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .conftest import entity_id_for, fire_refresh, set_state

pytestmark = pytest.mark.integration


async def _reload_entry(hass, entry) -> None:
    """Unload and set up the entry again (subentries survive)."""
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_auto_clean_persistence_across_reload(hass, entry_with_rooms, vacuum_calls):
    """Rooms cleaned by evaluate_batch keep their timestamp after a reload.

    This is the regression test for the missing persistence in the batch
    handler: without saving the updated timestamps the room would become
    overdue again after a restart and be cleaned twice.
    """
    entry, kitchen_sid, _living_sid = entry_with_rooms
    state = entry.runtime_data.room_states[kitchen_sid]
    now = dt_util.now()

    # Persist an overdue state first, so that without the batch-handler save
    # the room is overdue again after the reload (duplicate cleaning).
    await hass.services.async_call(
        DOMAIN,
        "record_cleaning",
        {"room_name": "Kitchen", "mode": "vacuum", "timestamp": (now - timedelta(days=10)).isoformat()},
        blocking=True,
    )
    await fire_refresh(hass)
    overdue = entity_id_for(hass, entry.entry_id, kitchen_sid, "binary_sensor", "room_overdue")
    assert hass.states.get(overdue).state == STATE_ON

    set_state(hass, "binary_sensor.kitchen_door", "on")
    await hass.async_block_till_done()

    await hass.services.async_call(DOMAIN, "evaluate_batch", {}, blocking=True)
    assert state.last_vacuumed > now - timedelta(minutes=1)

    await _reload_entry(hass, entry)
    await fire_refresh(hass)

    assert hass.states.get(overdue).state == STATE_OFF


async def test_record_cleaning_persistence_across_reload(hass, entry_with_rooms):
    """record_cleaning timestamps survive a reload and keep the sensor off."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    state = entry.runtime_data.room_states[kitchen_sid]
    now = dt_util.now()
    state.last_mopped = now - timedelta(days=10)  # mopping overdue (frequency 3)
    state.last_vacuumed = now - timedelta(hours=2)
    await fire_refresh(hass)
    overdue = entity_id_for(hass, entry.entry_id, kitchen_sid, "binary_sensor", "room_overdue")
    assert hass.states.get(overdue).state == STATE_ON

    await hass.services.async_call(
        DOMAIN,
        "record_cleaning",
        {"room_name": "Kitchen", "mode": "mop"},
        blocking=True,
    )
    await fire_refresh(hass)
    assert hass.states.get(overdue).state == STATE_OFF

    await _reload_entry(hass, entry)
    await fire_refresh(hass)

    # The recorded mop timestamp survived the reload.
    assert abs((entry.runtime_data.room_states[kitchen_sid].last_mopped - now).total_seconds()) < 60
    assert hass.states.get(overdue).state == STATE_OFF


async def test_storage_survives_reload(hass, entry_with_rooms):
    """The persisted storage blob is intact after a reload."""
    entry, kitchen_sid, _living_sid = entry_with_rooms

    await hass.services.async_call(
        DOMAIN,
        "record_cleaning",
        {"room_name": "Kitchen", "mode": "vacuum"},
        blocking=True,
    )
    await _reload_entry(hass, entry)

    store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
    data = await store.async_load()
    assert data is not None
    assert data["version"] == 1
    assert kitchen_sid in data["rooms"]
    assert data["rooms"][kitchen_sid]["last_vacuumed"] is not None
    assert data["rooms"][kitchen_sid]["enabled"] is True
