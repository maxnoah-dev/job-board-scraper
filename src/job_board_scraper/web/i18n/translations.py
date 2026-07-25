"""Translation loader and lookup helpers.

Translations are stored as nested JSON dictionaries under
``web/i18n/locales/<locale>.json``. Keys use dotted notation
(e.g. ``"nav.dashboard"``) so templates and JS can reference a stable
identifier without worrying about the underlying JSON structure.

Example translations file::

    {
        "nav": {
            "dashboard": "Dashboard",
            "runs": "Runs"
        }
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LOCALES_DIR = Path(__file__).parent / "locales"

SUPPORTED_LOCALES: tuple[str, ...] = ("en", "vi")
DEFAULT_LOCALE: str = "en"


def _load_locale(locale: str) -> dict[str, Any]:
    """Load a single locale dictionary from its JSON file.

    Args:
        locale: Locale code (e.g. ``"en"`` or ``"vi"``).

    Returns:
        The parsed dictionary, or an empty dict if the file is missing
        or invalid. Errors are intentionally non-fatal so the app can
        still boot with a partial translation set.
    """
    path = LOCALES_DIR / f"{locale}.json"
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _resolve_key(data: dict[str, Any], key: str) -> str | None:
    """Resolve a dotted key (e.g. ``"nav.dashboard"``) in a nested dict.

    Args:
        data: Translation dictionary.
        key: Dotted key path.

    Returns:
        The resolved string, or ``None`` if any segment is missing.
    """
    current: Any = data
    for segment in key.split("."):
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current if isinstance(current, str) else None


def get_translation(locale: str, key: str) -> str:
    """Look up a translation for a single key.

    Falls back to English when the locale or the key is missing, then
    to the key itself so the UI never renders empty.

    Args:
        locale: Requested locale code.
        key: Dotted translation key.

    Returns:
        The translated string, the English fallback, or the key on miss.
    """
    if locale in SUPPORTED_LOCALES:
        value = _resolve_key(_load_locale(locale), key)
        if value is not None:
            return value

    if locale != DEFAULT_LOCALE:
        value = _resolve_key(_load_locale(DEFAULT_LOCALE), key)
        if value is not None:
            return value

    return key


def get_translator(locale: str):
    """Return a ``t(key)`` callable bound to a specific locale.

    Useful for registering as a Jinja global so templates can write
    ``{{ t('nav.dashboard') }}`` without passing the locale every time.

    Args:
        locale: Locale code to bind.

    Returns:
        A function that takes a translation key and returns the string.
    """
    def t(key: str) -> str:
        return get_translation(locale, key)

    return t
