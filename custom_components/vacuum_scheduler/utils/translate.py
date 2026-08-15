"""Translation helpers for vacuum_scheduler."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.vacuum_scheduler.const import DOMAIN
from homeassistant.helpers.translation import async_get_translations

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def async_translate(
    hass: HomeAssistant,
    key: str,
    placeholders: dict[str, str] | None = None,
    language: str | None = None,
) -> str:
    """Translate a key for this integration.

    Args:
        hass: The Home Assistant instance.
        key: The translation key (e.g., "notify.dry_run_title").
        placeholders: Optional dict of placeholder values for substitution.
        language: Optional language override. Defaults to HA's configured language.

    Returns:
        The translated string, or the key itself if no translation is found.

    """
    if language is None:
        language = hass.config.language

    translations = await async_get_translations(hass, language, "notify", integrations={DOMAIN})

    translation_key = f"component.{DOMAIN}.notify.{key}"
    translated = translations.get(translation_key, key)

    if placeholders:
        for placeholder, value in placeholders.items():
            translated = translated.replace(f"{{{placeholder}}}", str(value))

    return translated
