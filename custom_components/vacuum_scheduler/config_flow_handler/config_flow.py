"""Config flow for vacuum_scheduler.

This module implements the main configuration flow for the hub entry.
Room configuration is handled via subentries in room_subentry_flow.py.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from custom_components.vacuum_scheduler.config_flow_handler.room_subentry_flow import RoomSubentryFlow
from custom_components.vacuum_scheduler.const import (
    CONF_ALLOW_CLEANING_WHEN_WINDOW_OPEN,
    CONF_CRITICAL_OVERDUE_DAYS,
    CONF_DEFAULT_FAN_SPEED,
    CONF_DEFAULT_MOP_INTENSITY,
    CONF_GLOBAL_DRY_RUN,
    CONF_MAX_ROOMS_PER_BATCH,
    CONF_NOTIFY_ENTITY,
    CONF_STABILIZATION_PERIOD,
    DEFAULT_ALLOW_CLEANING_WHEN_WINDOW_OPEN,
    DEFAULT_CRITICAL_OVERDUE_DAYS,
    DEFAULT_MAX_ROOMS_PER_BATCH,
    DEFAULT_STABILIZATION_PERIOD,
    DOMAIN,
    MOP_INTENSITY_OPTIONS,
)
from homeassistant import config_entries
from homeassistant.config_entries import ConfigSubentryFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector


class VacuumSchedulerConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial configuration flow for vacuum_scheduler.

    Room configuration is managed through subentries (see RoomSubentryFlow).
    """

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return VacuumSchedulerOptionsFlowHandler(config_entry)

    @staticmethod
    @callback
    def async_get_supported_subentry_types(
        config_entry: config_entries.ConfigEntry,
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentry types supported by this integration.

        Args:
            config_entry: The config entry being configured.

        Returns:
            Mapping of subentry type to flow handler class.

        """
        return {
            "room": RoomSubentryFlow,
        }

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial user configuration step.

        This creates the hub config entry. Users will add rooms via
        subentries after setup.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result.
        """
        if user_input is not None:
            # Store hub name and proceed to global config
            self._hub_name = user_input[CONF_NAME]
            await self.async_set_unique_id(self._hub_name.lower().strip())
            self._abort_if_unique_id_configured()
            return await self.async_step_global_config()

        # Show form to collect hub name
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Vacuum Scheduler"): str,
            },
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )

    async def async_step_global_config(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle global configuration step.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result.

        """
        if user_input is not None:
            # Create the hub entry with global config
            return self.async_create_entry(
                title=self._hub_name,
                data=user_input,
            )

        # Show form for global configuration
        schema = vol.Schema(
            {
                vol.Optional(CONF_NOTIFY_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="notify"),
                ),
                vol.Optional(
                    CONF_GLOBAL_DRY_RUN,
                    default=False,
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_MAX_ROOMS_PER_BATCH,
                    default=DEFAULT_MAX_ROOMS_PER_BATCH,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=20,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Optional(
                    CONF_ALLOW_CLEANING_WHEN_WINDOW_OPEN,
                    default=DEFAULT_ALLOW_CLEANING_WHEN_WINDOW_OPEN,
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_CRITICAL_OVERDUE_DAYS,
                    default=DEFAULT_CRITICAL_OVERDUE_DAYS,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=7,
                        step=1,
                        unit_of_measurement="days",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Optional(CONF_DEFAULT_FAN_SPEED): str,
                vol.Optional(
                    CONF_DEFAULT_MOP_INTENSITY,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=MOP_INTENSITY_OPTIONS,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
            },
        )

        return self.async_show_form(
            step_id="global_config",
            data_schema=schema,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration of the hub entry.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result.

        """
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                title=entry.title,
                data=user_input,
                reason="reconfigure_successful",
            )

        # Build schema with current values as defaults
        current_data = entry.data
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_NOTIFY_ENTITY,
                    default=current_data.get(CONF_NOTIFY_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="notify"),
                ),
                vol.Optional(
                    CONF_GLOBAL_DRY_RUN,
                    default=current_data.get(CONF_GLOBAL_DRY_RUN, False),
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_MAX_ROOMS_PER_BATCH,
                    default=current_data.get(CONF_MAX_ROOMS_PER_BATCH, DEFAULT_MAX_ROOMS_PER_BATCH),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=20,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Optional(
                    CONF_ALLOW_CLEANING_WHEN_WINDOW_OPEN,
                    default=current_data.get(
                        CONF_ALLOW_CLEANING_WHEN_WINDOW_OPEN,
                        DEFAULT_ALLOW_CLEANING_WHEN_WINDOW_OPEN,
                    ),
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_CRITICAL_OVERDUE_DAYS,
                    default=current_data.get(CONF_CRITICAL_OVERDUE_DAYS, DEFAULT_CRITICAL_OVERDUE_DAYS),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=7,
                        step=1,
                        unit_of_measurement="days",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Optional(
                    CONF_DEFAULT_FAN_SPEED,
                    default=current_data.get(CONF_DEFAULT_FAN_SPEED),
                ): str,
                vol.Optional(
                    CONF_DEFAULT_MOP_INTENSITY,
                    default=current_data.get(CONF_DEFAULT_MOP_INTENSITY),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=MOP_INTENSITY_OPTIONS,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
            },
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
        )


class VacuumSchedulerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for vacuum_scheduler."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__()
        self._config_entry = config_entry

    @property
    def config_entry(self) -> config_entries.ConfigEntry:
        """Return config entry."""
        return self._config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial options step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_STABILIZATION_PERIOD,
                    default=current_options.get(
                        CONF_STABILIZATION_PERIOD,
                        DEFAULT_STABILIZATION_PERIOD,
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=30,
                        step=1,
                        unit_of_measurement="min",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
            },
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )


__all__ = [
    "VacuumSchedulerConfigFlowHandler",
    "VacuumSchedulerOptionsFlowHandler",
]
