"""Service actions package for vacuum_scheduler."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.vacuum_scheduler.const import DOMAIN, LOGGER, SERVICE_EVALUATE_BATCH, SERVICE_RECORD_CLEANING
from custom_components.vacuum_scheduler.service_actions.evaluate_batch import async_handle_evaluate_batch
from custom_components.vacuum_scheduler.service_actions.record_cleaning import async_handle_record_cleaning
from homeassistant.core import ServiceCall
from homeassistant.exceptions import ServiceValidationError

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for the integration.

    Services are registered at component level (in async_setup) rather than
    per config entry. This ensures:
    - Service validation works correctly
    - Services are available even without config entries
    - Helpful error messages are provided

    """

    async def handle_evaluate_batch(call: ServiceCall) -> dict[str, Any]:
        """Handle the evaluate_batch service call.

        If a vacuum_entity is specified, only rooms on that vacuum are evaluated.
        Otherwise, all config entries are evaluated.

        Returns a dict with combined results across all matching entries.
        """
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise ServiceValidationError(f"No {DOMAIN} config entries found")

        vacuum_entity = call.data.get("vacuum_entity")

        aggregated: dict[str, Any] = {
            "entries_evaluated": 0,
            "rooms_evaluated": 0,
            "rooms_overdue": 0,
            "rooms_skipped_door_closed": 0,
            "rooms": [],
            "errors": [],
        }

        for entry in entries:
            try:
                runtime_data = entry.runtime_data
            except AttributeError:
                continue

            if vacuum_entity:
                has_matching_room = any(config.vacuum_entity == vacuum_entity for config in runtime_data.rooms.values())
                if not has_matching_room:
                    continue

            result = await async_handle_evaluate_batch(hass, entry, call)
            LOGGER.debug("evaluate_batch result for entry %s: %s", entry.entry_id, result)

            aggregated["entries_evaluated"] += 1
            aggregated["rooms_evaluated"] += result.get("rooms_evaluated", 0)
            aggregated["rooms_overdue"] += result.get("rooms_overdue", 0)
            aggregated["rooms_skipped_door_closed"] += result.get("rooms_skipped_door_closed", 0)
            aggregated["rooms"].extend(result.get("rooms", []))
            aggregated["errors"].extend(result.get("errors", []))

        return aggregated

    async def handle_record_cleaning(call: ServiceCall) -> dict[str, Any]:
        """Handle the record_cleaning service call."""
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise ServiceValidationError(f"No {DOMAIN} config entries found")

        room_name = call.data.get("room_name")
        for entry in entries:
            try:
                runtime_data = entry.runtime_data
            except AttributeError:
                continue

            for config in runtime_data.rooms.values():
                if config.room_name == room_name:
                    return await async_handle_record_cleaning(hass, entry, call)

        raise ServiceValidationError(f"Room '{room_name}' not found in any config entry")

    # Register services (only once at component level)
    if not hass.services.has_service(DOMAIN, SERVICE_EVALUATE_BATCH):
        hass.services.async_register(
            DOMAIN,
            SERVICE_EVALUATE_BATCH,
            handle_evaluate_batch,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_RECORD_CLEANING):
        hass.services.async_register(
            DOMAIN,
            SERVICE_RECORD_CLEANING,
            handle_record_cleaning,
        )

    LOGGER.debug("Services registered for %s", DOMAIN)
