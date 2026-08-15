"""Tests for utils.translate module."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from custom_components.vacuum_scheduler.utils.translate import async_translate


class TestAsyncTranslate:
    """Tests for async_translate function."""

    async def test_translates_key(self, mock_hass):
        """Test that key is translated."""
        mock_hass.config.language = "en"
        mock_translations = {
            "component.vacuum_scheduler.notify.dry_run_title": "Test Title",
        }

        with patch(
            "custom_components.vacuum_scheduler.utils.translate.async_get_translations",
            new=AsyncMock(return_value=mock_translations),
        ):
            result = await async_translate(mock_hass, "dry_run_title")

        assert result == "Test Title"

    async def test_returns_key_when_not_found(self, mock_hass):
        """Test returns key when translation not found."""
        mock_hass.config.language = "en"

        with patch(
            "custom_components.vacuum_scheduler.utils.translate.async_get_translations",
            new=AsyncMock(return_value={}),
        ):
            result = await async_translate(mock_hass, "unknown_key")

        assert result == "unknown_key"

    async def test_replaces_placeholders(self, mock_hass):
        """Test placeholders are replaced in translation."""
        mock_hass.config.language = "en"
        mock_translations = {
            "component.vacuum_scheduler.notify.dry_run_message": "Would clean {count} room(s): {rooms}",
        }

        with patch(
            "custom_components.vacuum_scheduler.utils.translate.async_get_translations",
            new=AsyncMock(return_value=mock_translations),
        ):
            result = await async_translate(
                mock_hass,
                "dry_run_message",
                {"count": "3", "rooms": "Kitchen, Living Room"},
            )

        assert result == "Would clean 3 room(s): Kitchen, Living Room"

    async def test_uses_specified_language(self, mock_hass):
        """Test that specified language is used."""
        mock_hass.config.language = "en"

        with patch(
            "custom_components.vacuum_scheduler.utils.translate.async_get_translations",
            new=AsyncMock(return_value={}),
        ) as mock_get:
            await async_translate(mock_hass, "key", language="de")

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[0][1] == "de"  # language is the second positional arg
