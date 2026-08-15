"""Integration tests for the setup chain: services, entities, storage, unload."""

from __future__ import annotations

import pytest

from custom_components.vacuum_scheduler.const import DOMAIN, STORAGE_VERSION
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
import homeassistant.helpers.device_registry as dr
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.storage import Store

from .conftest import entity_id_for

pytestmark = pytest.mark.integration


async def test_services_registered(hass, entry_with_rooms):
    """The component-level services are registered by async_setup."""
    assert hass.services.has_service(DOMAIN, "evaluate_batch")
    assert hass.services.has_service(DOMAIN, "record_cleaning")


async def test_entities_created_for_each_room(hass, entry_with_rooms):
    """Each room has an overdue binary sensor and an enabled switch."""
    entry, kitchen_sid, living_sid = entry_with_rooms

    kitchen_overdue = entity_id_for(hass, entry.entry_id, kitchen_sid, "binary_sensor", "room_overdue")
    # Entity ids are prefixed with the device (hub) name: device + entity name.
    assert kitchen_overdue == "binary_sensor.vacuum_scheduler_kitchen_overdue"
    kitchen_enabled = entity_id_for(hass, entry.entry_id, kitchen_sid, "switch", "room_enabled")
    assert kitchen_enabled == "switch.vacuum_scheduler_kitchen_enabled"
    living_overdue = entity_id_for(hass, entry.entry_id, living_sid, "binary_sensor", "room_overdue")
    assert living_overdue == "binary_sensor.vacuum_scheduler_living_room_overdue"
    living_enabled = entity_id_for(hass, entry.entry_id, living_sid, "switch", "room_enabled")
    assert living_enabled == "switch.vacuum_scheduler_living_room_enabled"

    # Freshly cleaned rooms are not overdue; scheduling is enabled.
    assert hass.states.get(kitchen_overdue).state == STATE_OFF
    assert hass.states.get(kitchen_enabled).state == STATE_ON
    assert hass.states.get(living_overdue).state == STATE_OFF
    assert hass.states.get(living_enabled).state == STATE_ON


async def test_entities_have_device_info(hass, entry_with_rooms):
    """All room entities are attached to the hub device."""
    entry, kitchen_sid, _living_sid = entry_with_rooms
    kitchen_overdue = entity_id_for(hass, entry.entry_id, kitchen_sid, "binary_sensor", "room_overdue")

    entity_reg = er.async_get(hass)
    registry_entry = entity_reg.async_get(kitchen_overdue)
    assert registry_entry is not None

    device_reg = dr.async_get(hass)
    device = device_reg.async_get(registry_entry.device_id)
    assert device is not None
    assert device.identifiers == {(DOMAIN, entry.entry_id)}


async def test_storage_persists_room_states(hass, entry_with_rooms):
    """record_cleaning writes room states through the real Store."""
    entry, kitchen_sid, _living_sid = entry_with_rooms

    await hass.services.async_call(
        DOMAIN,
        "record_cleaning",
        {"room_name": "Kitchen", "mode": "vacuum"},
        blocking=True,
    )

    store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
    data = await store.async_load()
    assert data is not None
    assert data["version"] == 1
    assert kitchen_sid in data["rooms"]
    assert data["rooms"][kitchen_sid]["last_vacuumed"] is not None


async def test_unload_removes_entities_and_coordinator(hass, entry_with_rooms):
    """Unloading the entry deactivates all four room entities without errors."""
    entry, kitchen_sid, living_sid = entry_with_rooms
    entity_ids = [
        entity_id_for(hass, entry.entry_id, sid, platform, key)
        for sid in (kitchen_sid, living_sid)
        for platform, key in (("binary_sensor", "room_overdue"), ("switch", "room_enabled"))
    ]
    assert all(hass.states.get(entity_id) is not None for entity_id in entity_ids)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Entities are gone; HA's restore machinery keeps unavailable placeholders.
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state is not None and state.state == STATE_UNAVAILABLE
        assert state.attributes.get("restored") is True
