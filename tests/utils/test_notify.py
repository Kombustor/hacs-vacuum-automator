"""Tests for utils.notify module."""

from __future__ import annotations

from custom_components.vacuum_scheduler.utils.notify import async_send_notification


class TestAsyncSendNotification:
    """Tests for async_send_notification function."""

    async def test_sends_notification_successfully(self, mock_hass):
        """Test notification is sent successfully."""
        await async_send_notification(mock_hass, "notify.mobile_app_phone", "Test message", "Test Title")

        mock_hass.services.async_call.assert_called_once_with(
            "notify",
            "mobile_app_phone",
            {"message": "Test message", "title": "Test Title"},
        )

    async def test_skips_when_no_notify_entity(self, mock_hass):
        """Test notification is skipped when no entity configured."""
        await async_send_notification(mock_hass, None, "Test message")

        mock_hass.services.async_call.assert_not_called()

    async def test_handles_exception_gracefully(self, mock_hass):
        """Test exception is handled gracefully."""
        mock_hass.services.async_call.side_effect = Exception("Service error")

        # Should not raise
        await async_send_notification(mock_hass, "notify.mobile_app_phone", "Test message")

    async def test_uses_default_title(self, mock_hass):
        """Test default title is used when not specified."""
        await async_send_notification(mock_hass, "notify.test", "Test message")

        call_args = mock_hass.services.async_call.call_args
        assert call_args[0][2]["title"] == "Vacuum Scheduler"

    async def test_strips_notify_prefix(self, mock_hass):
        """Test that notify. prefix is stripped from entity."""
        await async_send_notification(mock_hass, "notify.my_phone", "Test")

        call_args = mock_hass.services.async_call.call_args
        assert call_args[0][1] == "my_phone"
