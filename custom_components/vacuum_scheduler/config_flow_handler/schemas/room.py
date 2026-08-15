"""Room subentry flow schemas."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from custom_components.vacuum_scheduler.const import (
    CONF_CLEANING_AREA_ID,
    CONF_DOOR_SENSOR,
    CONF_FAN_SPEED,
    CONF_MOP_FREQUENCY_DAYS,
    CONF_MOP_INTENSITY,
    CONF_ROOM_NAME,
    CONF_TIME_WINDOW_END,
    CONF_TIME_WINDOW_START,
    CONF_VACUUM_ENTITY,
    CONF_VACUUM_FREQUENCY_DAYS,
    CONF_WINDOW_SENSOR,
    MOP_INTENSITY_OPTIONS,
)
from homeassistant.helpers import selector


def _optional(key: str, defaults: Mapping[str, Any]) -> vol.Optional:
    """Return an optional schema key, prefilling the existing value if any.

    A ``default=None`` (or empty string) on a selector field makes voluptuous
    validate the default against the selector, which fails; only set a default
    when there is a real value to prefill.
    """
    value = defaults.get(key)
    if value:
        return vol.Optional(key, default=value)
    return vol.Optional(key)


def get_room_schema(
    defaults: Mapping[str, Any] | None = None,
    existing_room_names: set[str] | None = None,
) -> vol.Schema:
    """Get schema for room subentry flow.

    Args:
        defaults: Optional dictionary of current values.
        existing_room_names: Set of existing room names to check for duplicates.

    Returns:
        Voluptuous schema for room configuration.

    """
    defaults = defaults or {}

    return vol.Schema(
        {
            vol.Required(
                CONF_ROOM_NAME,
                default=defaults.get(CONF_ROOM_NAME),
            ): str,
            vol.Required(
                CONF_VACUUM_ENTITY,
                default=defaults.get(CONF_VACUUM_ENTITY),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="vacuum"),
            ),
            _optional(CONF_DOOR_SENSOR, defaults): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor"),
            ),
            _optional(CONF_WINDOW_SENSOR, defaults): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor"),
            ),
            vol.Required(
                CONF_CLEANING_AREA_ID,
                default=defaults.get(CONF_CLEANING_AREA_ID, []),
            ): selector.AreaSelector(
                selector.AreaSelectorConfig(
                    multiple=True,
                ),
            ),
            vol.Required(
                CONF_VACUUM_FREQUENCY_DAYS,
                default=defaults.get(CONF_VACUUM_FREQUENCY_DAYS, 3),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=30,
                    step=1,
                    unit_of_measurement="days",
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
            vol.Optional(
                CONF_MOP_FREQUENCY_DAYS,
                default=defaults.get(CONF_MOP_FREQUENCY_DAYS) or 0,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=30,
                    step=1,
                    unit_of_measurement="days",
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
            vol.Required(
                CONF_TIME_WINDOW_START,
                default=defaults.get(CONF_TIME_WINDOW_START, "08:00"),
            ): selector.TimeSelector(),
            vol.Optional(
                CONF_TIME_WINDOW_END,
                default=defaults.get(CONF_TIME_WINDOW_END, "20:00"),
            ): selector.TimeSelector(),
            _optional(CONF_FAN_SPEED, defaults): str,
            _optional(CONF_MOP_INTENSITY, defaults): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=MOP_INTENSITY_OPTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            ),
        },
    )


def get_room_reconfigure_schema(
    defaults: Mapping[str, Any],
    existing_room_names: set[str] | None = None,
) -> vol.Schema:
    """Get schema for room reconfigure flow.

    Args:
        defaults: Dictionary of current values.
        existing_room_names: Set of existing room names to check for duplicates.

    Returns:
        Voluptuous schema for room configuration.

    """
    return get_room_schema(defaults, existing_room_names)
