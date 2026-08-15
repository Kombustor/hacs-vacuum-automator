"""Core DataUpdateCoordinator for vacuum_scheduler.

Evaluates room overdue status every 60 seconds and distributes
updates to all entities. Does not fetch from an external API.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING, Any

from custom_components.vacuum_scheduler.const import DOMAIN, EVENT_CRITICAL_OVERDUE, LOGGER, UPDATE_INTERVAL
from custom_components.vacuum_scheduler.data import RoomConfig, RoomState, VacuumSchedulerConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


# ── Shared scheduling helpers ────────────────────────────────────────────────
# Also imported by service_actions/evaluate_batch.py to avoid duplicating
# the overdue and time-window checks.


def is_overdue(last_cleaned: datetime | None, frequency_days: int, now: datetime) -> bool:
    """Return True if cleaning is overdue (or never cleaned)."""
    if last_cleaned is None:
        return True
    # Normalise timezone awareness so comparisons are safe
    if last_cleaned.tzinfo is not None and now.tzinfo is None:
        last_cleaned = last_cleaned.replace(tzinfo=None)
    elif now.tzinfo is not None and last_cleaned.tzinfo is None:
        now = now.replace(tzinfo=None)
    return now >= last_cleaned + timedelta(days=frequency_days)


def is_within_time_window(start: time, end: time, now: datetime) -> bool:
    """Return True if now is within [start, end] (handles overnight windows)."""
    t = now.time()
    if start <= end:
        return start <= t <= end
    return t >= start or t <= end


def _urgency(last_cleaned: datetime | None, frequency_days: int, now: datetime) -> float:
    """Days past the frequency threshold (inf if never cleaned, 0 if not overdue)."""
    if last_cleaned is None:
        return float("inf")
    if last_cleaned.tzinfo is not None and now.tzinfo is None:
        last_cleaned = last_cleaned.replace(tzinfo=None)
    elif now.tzinfo is not None and last_cleaned.tzinfo is None:
        now = now.replace(tzinfo=None)
    threshold = last_cleaned + timedelta(days=frequency_days)
    if now < threshold:
        return 0.0
    return (now - threshold).total_seconds() / 86400.0


# ── Coordinator ──────────────────────────────────────────────────────────────


class VacuumSchedulerCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Evaluates room overdue status and fires critical-overdue events.

    Runs every UPDATE_INTERVAL (60 s). The data dict (keyed by subentry_id)
    feeds the binary_sensor and switch entities.
    """

    config_entry: VacuumSchedulerConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: VacuumSchedulerConfigEntry) -> None:
        """Initialize the coordinator with a 60-second update interval."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=config_entry,
            always_update=True,
        )

    async def _async_setup(self) -> None:
        LOGGER.debug("Coordinator setup complete for %s", self.config_entry.entry_id)

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        now = dt_util.now()
        runtime_data = self.config_entry.runtime_data
        result: dict[str, dict[str, Any]] = {}

        for subentry_id, config in runtime_data.rooms.items():
            state = runtime_data.room_states.get(subentry_id)
            if state is None:
                LOGGER.warning("Missing state for room subentry %s, skipping", subentry_id)
                continue

            vacuum_overdue = is_overdue(state.last_vacuumed, config.vacuum_frequency_days, now)
            mop_overdue = bool(
                config.mop_frequency_days is not None and is_overdue(state.last_mopped, config.mop_frequency_days, now)
            )
            # Mopping implies vacuuming
            if mop_overdue:
                vacuum_overdue = True

            overdue_details: dict[str, bool] = {"vacuum": vacuum_overdue}
            if config.mop_frequency_days is not None:
                overdue_details["mop"] = mop_overdue

            if state.enabled:
                self._maybe_fire_critical_event(subentry_id, config, state, now)

            result[subentry_id] = {
                "room_name": config.room_name,
                "is_overdue": any(overdue_details.values()),
                "overdue_details": overdue_details,
                "last_vacuumed": state.last_vacuumed,
                "last_mopped": state.last_mopped,
                "days_since_vacuum": (now - state.last_vacuumed).days if state.last_vacuumed else None,
                "days_since_mop": (now - state.last_mopped).days if state.last_mopped else None,
                "enabled": state.enabled,
            }

        return result

    # ── critical-overdue events ──────────────────────────────────────────

    def _maybe_fire_critical_event(
        self,
        subentry_id: str,
        config: RoomConfig,
        state: RoomState,
        now: datetime,
    ) -> None:
        """Fire vac_scheduler_critical_overdue once per critical-overdue period."""
        runtime_data = self.config_entry.runtime_data
        critical_days = runtime_data.global_config.critical_overdue_days
        fired: set[str] = runtime_data._fired_critical_events.get(subentry_id, set())  # noqa: SLF001

        def _check(mode: str, last_cleaned: datetime | None, freq_days: int) -> None:
            if last_cleaned is None:
                is_critical = True
            else:
                threshold = last_cleaned + timedelta(days=freq_days + critical_days)
                is_critical = now >= threshold
            if is_critical and mode not in fired:
                fired.add(mode)
                self.hass.bus.async_fire(
                    EVENT_CRITICAL_OVERDUE,
                    {
                        "room_name": config.room_name,
                        "mode": mode,
                        "entry_id": self.config_entry.entry_id,
                    },
                )
            elif not is_critical:
                fired.discard(mode)

        _check("vacuum", state.last_vacuumed, config.vacuum_frequency_days)
        if config.mop_frequency_days is not None:
            _check("mop", state.last_mopped, config.mop_frequency_days)

        if fired:
            runtime_data._fired_critical_events[subentry_id] = fired  # noqa: SLF001
        else:
            runtime_data._fired_critical_events.pop(subentry_id, None)  # noqa: SLF001
