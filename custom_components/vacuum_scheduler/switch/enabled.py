"""Switch to enable/disable scheduling for a room."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.vacuum_scheduler.entity import VacuumSchedulerRoomEntity
from custom_components.vacuum_scheduler.utils import async_save_room_states
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError

if TYPE_CHECKING:
    from custom_components.vacuum_scheduler.coordinator import VacuumSchedulerCoordinator
    from custom_components.vacuum_scheduler.data import RoomConfig, RoomState


class VacuumSchedulerEnabledSwitch(SwitchEntity, VacuumSchedulerRoomEntity):
    """Switch to enable/disable scheduling for a room."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: VacuumSchedulerCoordinator,
        room_config: RoomConfig,
        room_state: RoomState,
        entry_id: str,
    ) -> None:
        """Initialize the enabled switch.

        Args:
            coordinator: The coordinator instance.
            room_config: The room configuration.
            room_state: The current room state.
            entry_id: The config entry ID.

        """
        entity_desc = SwitchEntityDescription(
            key="room_enabled",
            translation_key="room_enabled",
            has_entity_name=True,
        )
        super().__init__(coordinator, entry_id, room_config.subentry_id, entity_desc)
        self._room_config = room_config
        self._room_state = room_state
        self._attr_translation_placeholders = {"room_name": room_config.room_name}
        self._attr_device_class = SwitchDeviceClass.SWITCH

    @property
    def is_on(self) -> bool:
        """Return True if scheduling is enabled for this room."""
        return self._room_state.enabled

    async def async_turn_on(self, **_: Any) -> None:
        """Enable scheduling for this room."""
        self._room_state.enabled = True
        if not await self._persist_state():
            raise HomeAssistantError("Failed to save room state")
        self.async_write_ha_state()

    async def async_turn_off(self, **_: Any) -> None:
        """Disable scheduling for this room."""
        self._room_state.enabled = False
        if not await self._persist_state():
            raise HomeAssistantError("Failed to save room state")
        self.async_write_ha_state()

    async def _persist_state(self) -> bool:
        """Persist the current state to storage. Returns True on success."""
        rtd = self.coordinator.config_entry.runtime_data
        states_to_save = {sid: state.to_dict() for sid, state in rtd.room_states.items()}
        return await async_save_room_states(rtd.storage, states_to_save)
