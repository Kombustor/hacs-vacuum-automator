"""Room subentry flow for vacuum_scheduler.

This module handles adding and configuring individual rooms as subentries.
"""

from __future__ import annotations

from typing import Any

from custom_components.vacuum_scheduler.config_flow_handler.schemas import get_room_reconfigure_schema, get_room_schema
from custom_components.vacuum_scheduler.const import CONF_ROOM_NAME
from homeassistant.config_entries import ConfigSubentryFlow, SubentryFlowResult
from homeassistant.util import slugify


class RoomSubentryFlow(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying rooms."""

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """User flow to add a new room.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The subentry flow result.

        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate room name is unique
            room_name = user_input[CONF_ROOM_NAME]
            if self._room_name_exists(room_name):
                errors["base"] = "room_name_exists"
            else:
                # HA's ConfigSubentryFlow finishes creation through
                # async_create_entry; the flow manager adds the subentry.
                return self.async_create_entry(
                    title=room_name,
                    data=user_input,
                )

        # Get existing room names for validation
        existing_names = self._get_existing_room_names()

        return self.async_show_form(
            step_id="user",
            data_schema=get_room_schema(existing_room_names=existing_names),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """User flow to modify an existing room.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The subentry flow result.

        """
        errors: dict[str, str] = {}
        config_subentry = self._get_reconfigure_subentry()

        if user_input is not None:
            # Validate room name is unique (unless it's the same room)
            room_name = user_input[CONF_ROOM_NAME]
            if room_name != config_subentry.title and self._room_name_exists(room_name):
                errors["base"] = "room_name_exists"
            else:
                # HA's ConfigSubentryFlow updates subentries through
                # async_update_and_abort.
                return self.async_update_and_abort(
                    self._get_entry(),
                    config_subentry,
                    title=room_name,
                    data=user_input,
                )

        # Get existing room names for validation (excluding current room)
        existing_names = self._get_existing_room_names()
        existing_names.discard(config_subentry.title)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=get_room_reconfigure_schema(
                defaults=config_subentry.data,
                existing_room_names=existing_names,
            ),
            errors=errors,
        )

    def _get_existing_room_names(self) -> set[str]:
        """Get set of existing room names for this entry.

        Returns:
            Set of room name slugs.

        """
        entry = self._get_entry()
        names = set()
        for subentry in entry.subentries.values():
            names.add(slugify(subentry.title))
        return names

    def _room_name_exists(self, room_name: str) -> bool:
        """Check if a room name already exists.

        Args:
            room_name: The room name to check.

        Returns:
            True if a room with this name (slugified) already exists.

        """
        existing = self._get_existing_room_names()
        return slugify(room_name) in existing


__all__ = ["RoomSubentryFlow"]
