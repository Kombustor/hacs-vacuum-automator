"""Binary sensor for room overdue state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.vacuum_scheduler.entity import VacuumSchedulerRoomEntity
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

if TYPE_CHECKING:
    from custom_components.vacuum_scheduler.coordinator import VacuumSchedulerCoordinator
    from custom_components.vacuum_scheduler.data import RoomConfig, RoomState


class VacuumSchedulerOverdueSensor(
    BinarySensorEntity,
    VacuumSchedulerRoomEntity,
):
    """Binary sensor for room overdue state."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: VacuumSchedulerCoordinator,
        room_config: RoomConfig,
        room_state: RoomState,
        entry_id: str,
    ) -> None:
        """Initialize the overdue sensor.

        Args:
            coordinator: The coordinator instance.
            room_config: The room configuration.
            room_state: The current room state.
            entry_id: The config entry ID.

        """
        entity_desc = BinarySensorEntityDescription(
            key="room_overdue",
            translation_key="room_overdue",
            device_class=BinarySensorDeviceClass.PROBLEM,
            has_entity_name=True,
        )
        super().__init__(coordinator, entry_id, room_config.subentry_id, entity_desc)
        self._room_config = room_config
        self._room_state = room_state
        self._attr_translation_placeholders = {"room_name": room_config.room_name}

    @property
    def is_on(self) -> bool:
        """Return True if the room is overdue for cleaning."""
        data = self.coordinator.data.get(self._room_config.subentry_id, {})
        return data.get("is_overdue", False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        data = self.coordinator.data.get(self._room_config.subentry_id, {})
        return {
            "last_vacuumed": data.get("last_vacuumed"),
            "last_mopped": data.get("last_mopped"),
            "days_since_vacuum": data.get("days_since_vacuum"),
            "days_since_mop": data.get("days_since_mop"),
            "overdue_details": data.get("overdue_details"),
        }
