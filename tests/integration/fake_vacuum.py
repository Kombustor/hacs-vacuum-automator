"""Fake vacuum platform used by the integration tests.

Registers real vacuum entities through HA's test platform helper so that
service calls made by the integration (`vacuum.clean_area`,
`vacuum.send_command`, `vacuum.set_fan_speed`) are routed through HA's
entity-service machinery and recorded in a shared calls list.

In HA 2026.4 `vacuum.clean_area` maps area ids to segments through the entity
registry `area_mapping` option and then calls `async_clean_segments`, so the
fake entity records segment ids. The setup helper installs a 1:1
area -> segment mapping for the fixture areas.
"""

from __future__ import annotations

from typing import Any

from pytest_homeassistant_custom_component.common import setup_test_component_platform

from homeassistant.components.vacuum import StateVacuumEntity, VacuumEntityFeature
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er
from homeassistant.setup import async_setup_component

AREA_TO_SEGMENT = {
    "area_kitchen": "segment_kitchen",
    "area_living": "segment_living",
}

# Entity ids expected after platform setup (derived from _attr_name).
KITCHEN_VACUUM_ENTITY = "vacuum.kitchen_robot"
LIVING_ROOM_VACUUM_ENTITY = "vacuum.living_room_robot"


async def setup_fake_vacuum(hass: HomeAssistant, calls: list[dict[str, Any]]) -> None:
    """Register the fake vacuum platform and its two robots."""
    entities = [
        FakeVacuumEntity("Kitchen Robot", "fake_kitchen_robot", calls),
        FakeVacuumEntity("Living Room Robot", "fake_living_room_robot", calls),
    ]
    # Config entries are not used here: the vacuum component's config_flow
    # module is not shipped in the HA wheel, which would make entry setup fail.
    setup_test_component_platform(hass, "vacuum", entities)
    await async_setup_component(hass, "vacuum", {"vacuum": [{"platform": "test"}]})
    await hass.async_block_till_done()

    # Install area -> segment mappings so the real vacuum.clean_area service
    # can route cleaning_area_id to async_clean_segments. Both robots map all
    # fixture areas so rooms batched onto one vacuum clean correctly.
    area_mapping = {area: [segment] for area, segment in AREA_TO_SEGMENT.items()}
    entity_reg = er.async_get(hass)
    for entity_id in (KITCHEN_VACUUM_ENTITY, LIVING_ROOM_VACUUM_ENTITY):
        entity_reg.async_update_entity_options(entity_id, "vacuum", {"area_mapping": area_mapping})
    await hass.async_block_till_done()


class FakeVacuumEntity(StateVacuumEntity):
    """A vacuum entity that records service calls instead of cleaning."""

    def __init__(self, name: str, unique_id: str, calls: list[dict[str, Any]]) -> None:
        """Initialize the entity."""
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_supported_features = (
            VacuumEntityFeature.STATE
            | VacuumEntityFeature.START
            | VacuumEntityFeature.FAN_SPEED
            | VacuumEntityFeature.SEND_COMMAND
            | VacuumEntityFeature.CLEAN_AREA
        )
        self._attr_fan_speed_list = ["max", "balanced", "quiet"]
        self._calls = calls

    async def async_start(self, **_: Any) -> None:
        """Record a start call."""
        self._calls.append({"service": "start", "entity_id": self.entity_id})

    async def async_set_fan_speed(self, fan_speed: str, **_: Any) -> None:
        """Record a set_fan_speed call."""
        self._calls.append({"service": "set_fan_speed", "entity_id": self.entity_id, "fan_speed": fan_speed})

    async def async_send_command(self, command: str, params: Any = None, **_: Any) -> None:
        """Record a send_command call."""
        self._calls.append(
            {
                "service": "send_command",
                "entity_id": self.entity_id,
                "command": command,
                "params": params,
            }
        )

    async def async_clean_segments(self, segments: list[str], **_: Any) -> None:
        """Record a clean_area call (areas were mapped to segments by HA)."""
        self._calls.append({"service": "clean_area", "entity_id": self.entity_id, "segments": list(segments)})
