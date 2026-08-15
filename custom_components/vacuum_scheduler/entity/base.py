"""Base entity class for vacuum_scheduler rooms."""

from __future__ import annotations

from custom_components.vacuum_scheduler.coordinator import VacuumSchedulerCoordinator
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity


class VacuumSchedulerRoomEntity(CoordinatorEntity[VacuumSchedulerCoordinator]):  # noqa: D101
    def __init__(
        self,
        coordinator: VacuumSchedulerCoordinator,
        entry_id: str,
        subentry_id: str,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity.

        Args:
            coordinator: The coordinator instance.
            entry_id: The config entry ID.
            subentry_id: The subentry ID for this room.
            entity_description: The entity description.

        """
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{entry_id}_{subentry_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(coordinator.config_entry.domain, entry_id)},
            name=coordinator.config_entry.title,
            manufacturer="Vacuum Scheduler",
            model="Hub",
        )
