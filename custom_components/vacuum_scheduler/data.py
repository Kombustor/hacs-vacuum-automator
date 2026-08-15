"""Data models for the Vacuum Scheduler integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.storage import Store

if TYPE_CHECKING:
    from .coordinator import VacuumSchedulerCoordinator


def _parse_time_value(value: Any, default: str) -> time:
    """Parse a time value into a ``time`` object.

    Accepts ``time`` objects and strings in ``HH:MM`` or ``HH:MM:SS`` format
    (the time selector stores the latter), falling back to ``default`` when
    the value is missing.
    """
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        return time.fromisoformat(value)
    return time.fromisoformat(default)


@dataclass
class RoomConfig:
    """Per-room configuration from a subentry."""

    subentry_id: str
    room_name: str
    vacuum_entity: str
    door_sensor: str | None
    window_sensor: str | None
    cleaning_area_id: list[str]
    vacuum_frequency_days: int
    mop_frequency_days: int | None
    fan_speed: str | None
    mop_intensity: str | None
    time_window_start: time
    time_window_end: time

    @classmethod
    def from_subentry_data(cls, subentry_id: str, data: dict[str, Any]) -> RoomConfig:
        """Create RoomConfig from subentry data dict."""
        start_time = _parse_time_value(data.get("time_window_start"), "08:00")
        end_time = _parse_time_value(data.get("time_window_end"), "20:00")

        return cls(
            subentry_id=subentry_id,
            room_name=data["room_name"],
            vacuum_entity=data["vacuum_entity"],
            door_sensor=data.get("door_sensor"),
            window_sensor=data.get("window_sensor"),
            cleaning_area_id=data.get("cleaning_area_id", []),
            vacuum_frequency_days=data["vacuum_frequency_days"],
            mop_frequency_days=data.get("mop_frequency_days") or None,
            fan_speed=data.get("fan_speed"),
            mop_intensity=data.get("mop_intensity"),
            time_window_start=start_time,
            time_window_end=end_time,
        )


@dataclass
class RoomState:
    """Runtime state for a single room (persisted + memory)."""

    last_vacuumed: datetime | None = None
    last_mopped: datetime | None = None
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            "last_vacuumed": self.last_vacuumed.isoformat() if self.last_vacuumed else None,
            "last_mopped": self.last_mopped.isoformat() if self.last_mopped else None,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoomState:
        """Deserialize from storage."""
        last_vacuumed = None
        last_mopped = None

        if data.get("last_vacuumed"):
            last_vacuumed = datetime.fromisoformat(data["last_vacuumed"])
        if data.get("last_mopped"):
            last_mopped = datetime.fromisoformat(data["last_mopped"])

        return cls(
            last_vacuumed=last_vacuumed,
            last_mopped=last_mopped,
            enabled=data.get("enabled", True),
        )


@dataclass
class GlobalConfig:
    """Global configuration for the vacuum scheduler."""

    notify_entity: str | None = None
    global_dry_run: bool = False
    max_rooms_per_batch: int = 5
    allow_cleaning_when_window_open: bool = False
    critical_overdue_days: int = 2
    default_fan_speed: str | None = None
    default_mop_intensity: str | None = None
    stabilization_period: int = 0

    @classmethod
    def from_entry_data(cls, data: Mapping[str, Any]) -> GlobalConfig:
        """Create GlobalConfig from entry data dict."""
        from custom_components.vacuum_scheduler.const import (  # noqa: PLC0415
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
        )

        return cls(
            notify_entity=data.get(CONF_NOTIFY_ENTITY),
            global_dry_run=data.get(CONF_GLOBAL_DRY_RUN, False),
            max_rooms_per_batch=data.get(CONF_MAX_ROOMS_PER_BATCH, DEFAULT_MAX_ROOMS_PER_BATCH),
            allow_cleaning_when_window_open=data.get(
                CONF_ALLOW_CLEANING_WHEN_WINDOW_OPEN,
                DEFAULT_ALLOW_CLEANING_WHEN_WINDOW_OPEN,
            ),
            critical_overdue_days=data.get(
                CONF_CRITICAL_OVERDUE_DAYS,
                DEFAULT_CRITICAL_OVERDUE_DAYS,
            ),
            default_fan_speed=data.get(CONF_DEFAULT_FAN_SPEED),
            default_mop_intensity=data.get(CONF_DEFAULT_MOP_INTENSITY),
            stabilization_period=data.get(CONF_STABILIZATION_PERIOD, DEFAULT_STABILIZATION_PERIOD),
        )


@dataclass
class VacuumSchedulerData:
    """Runtime data stored on entry.runtime_data."""

    storage: Store
    global_config: GlobalConfig
    rooms: dict[str, RoomConfig]  # subentry_id -> RoomConfig
    room_states: dict[str, RoomState]  # subentry_id -> RoomState
    coordinator: VacuumSchedulerCoordinator
    # Cleared when the room is no longer critically overdue, preventing event spam.
    # subentry_id -> set of mode strings (e.g. {"vacuum", "mop"})
    _fired_critical_events: dict[str, set[str]] = field(default_factory=dict)


# Type alias for config entry
VacuumSchedulerConfigEntry = ConfigEntry[VacuumSchedulerData]
