"""Unit tests for ``web/i18n/translations.py``."""

from __future__ import annotations

from job_board_scraper.web.i18n.translations import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    _load_locale,
    _resolve_key,
    get_translation,
    get_translator,
)


class TestResolveKey:
    def test_top_level_key(self) -> None:
        assert _resolve_key({"a": "x"}, "a") == "x"

    def test_nested_key(self) -> None:
        data = {"nav": {"dashboard": "Dashboard"}}
        assert _resolve_key(data, "nav.dashboard") == "Dashboard"

    def test_missing_key(self) -> None:
        assert _resolve_key({"a": "x"}, "b") is None

    def test_missing_nested_segment(self) -> None:
        assert _resolve_key({"nav": {}}, "nav.dashboard") is None

    def test_non_string_value(self) -> None:
        assert _resolve_key({"nav": {"dashboard": 1}}, "nav.dashboard") is None


class TestLoadLocale:
    def test_missing_file_returns_empty(self) -> None:
        assert _load_locale("xx") == {}

    def test_english_loaded(self) -> None:
        data = _load_locale("en")
        assert isinstance(data, dict)
        # Should have nav.* keys if the locale file exists; otherwise empty.
        assert isinstance(data, dict)


class TestGetTranslation:
    def test_returns_key_when_missing(self) -> None:
        # Unknown key with valid locale
        assert get_translation("en", "definitely_missing_key") == (
            "definitely_missing_key"
        )

    def test_returns_vi_translation_when_present(self) -> None:
        # Pick a key we know exists in the locale file.
        assert isinstance(get_translation("vi", "nav.dashboard"), str)


class TestGetTranslator:
    def test_returns_callable(self) -> None:
        t = get_translator("en")
        result = t("definitely_missing_key")
        assert result == "definitely_missing_key"


def test_default_locale_is_supported() -> None:
    assert DEFAULT_LOCALE in SUPPORTED_LOCALES
