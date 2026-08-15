"""Tests for the room subentry schema."""

from __future__ import annotations

from voluptuous import Optional

from custom_components.vacuum_scheduler.config_flow_handler.schemas.room import (
    get_room_reconfigure_schema,
    get_room_schema,
)
from custom_components.vacuum_scheduler.const import CONF_MOP_FREQUENCY_DAYS, CONF_VACUUM_FREQUENCY_DAYS


class TestRoomSchema:
    """Tests for get_room_schema."""

    def _find_mop_field(self, schema):
        """Return the voluptuous marker for mop frequency days."""
        for key in schema.schema:
            if getattr(key, "schema", None) == CONF_MOP_FREQUENCY_DAYS:
                return key
        raise AssertionError(f"{CONF_MOP_FREQUENCY_DAYS} not found in schema")

    def test_includes_vacuum_and_mop_frequency_days(self) -> None:
        """Both frequency day fields are present in the schema."""
        schema = get_room_schema()
        keys = list(schema.schema.keys())

        assert CONF_VACUUM_FREQUENCY_DAYS in keys
        assert CONF_MOP_FREQUENCY_DAYS in keys

    def test_mop_frequency_days_is_optional(self) -> None:
        """Mop frequency days remains an optional field."""
        schema = get_room_schema()
        field = self._find_mop_field(schema)

        assert isinstance(field, Optional)

    def test_mop_frequency_days_defaults_to_zero(self) -> None:
        """Mop frequency days renders with a default of 0 (disabled)."""
        schema = get_room_schema()
        field = self._find_mop_field(schema)

        assert field.default() == 0

    def test_reconfigure_schema_preserves_existing_mop_frequency(self) -> None:
        """Reconfigure schema uses the stored mop frequency as the default."""
        schema = get_room_reconfigure_schema(
            defaults={CONF_MOP_FREQUENCY_DAYS: 7},
        )
        field = self._find_mop_field(schema)

        assert field.default() == 7

    def test_reconfigure_schema_defaults_zero_when_no_mop_frequency(self) -> None:
        """Reconfigure schema defaults to 0 when mopping was disabled."""
        schema = get_room_reconfigure_schema(
            defaults={CONF_MOP_FREQUENCY_DAYS: None},
        )
        field = self._find_mop_field(schema)

        assert field.default() == 0
