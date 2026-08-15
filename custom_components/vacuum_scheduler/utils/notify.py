"""Notification helpers for vacuum_scheduler."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.vacuum_scheduler.const import LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def async_send_notification(
    hass: HomeAssistant,
    notify_entity: str | None,
    message: str,
    title: str = "Vacuum Scheduler",
) -> None:
    """Send a notification to the configured notify entity.

    Args:
        hass: The Home Assistant instance.
        notify_entity: The notify entity ID (e.g., "notify.mobile_app_phone").
        message: The notification message.
        title: The notification title.

    """
    if not notify_entity:
        LOGGER.debug("No notify entity configured, skipping notification: %s", message)
        return

    try:
        await hass.services.async_call(
            "notify",
            notify_entity.removeprefix("notify."),
            {
                "message": message,
                "title": title,
            },
        )
        LOGGER.debug("Sent notification to %s: %s", notify_entity, message)
    except Exception:  # noqa: BLE001
        LOGGER.exception("Failed to send notification to %s", notify_entity)
