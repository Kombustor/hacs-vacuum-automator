"""Config flow schemas for vacuum_scheduler."""

from __future__ import annotations

from .room import get_room_reconfigure_schema, get_room_schema

__all__ = [
    "get_room_reconfigure_schema",
    "get_room_schema",
]
