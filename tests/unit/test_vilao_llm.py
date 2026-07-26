"""Unit tests for the Vilao LLM integration (llm/)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from job_board_scraper.llm import (
    TRANSLATION_SYSTEM_PROMPT,
    TitleTranslator,
    VilaoClient,
    VilaoClientConfig,
    VilaoError,
    VilaoUnavailableError,
    translate_title_to_vietnamese,
)

# ---------------------------------------------------------------------------
# VilaoClientConfig
# ---------------------------------------------------------------------------


class TestVilaoClientConfig:
    def test_is_configured_false_when_empty(self) -> None:
        cfg = VilaoClientConfig()
        assert cfg.is_configured is False

    def test_is_configured_false_when_whitespace(self) -> None:
        cfg = VilaoClientConfig(api_key="   ")
        assert cfg.is_configured is False

    def test_is_configured_true_when_key_present(self) -> None:
        cfg = VilaoClientConfig(api_key="sk-abc")
        assert cfg.is_configured is True


# ---------------------------------------------------------------------------
# VilaoClient
# ---------------------------------------------------------------------------


def _make_response(content: str) -> SimpleNamespace:
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


class TestVilaoClientChat:
    @pytest.mark.asyncio
    async def test_chat_returns_stripped_text(self) -> None:
        cfg = VilaoClientConfig(api_key="sk-test", fail_threshold=3)
        client = VilaoClient(cfg)

        mock_openai = MagicMock()
        mock_openai.chat.completions.create = AsyncMock(
            return_value=_make_response("  Kỹ sư phần mềm  \n")
        )
        client._client = mock_openai  # bypass _ensure_client

        result = await client.chat("Software Engineer", system="sys")

        assert result == "Kỹ sư phần mềm"
        mock_openai.chat.completions.create.assert_awaited_once()
        kwargs = mock_openai.chat.completions.create.await_args.kwargs
        assert kwargs["model"] == cfg.model
        assert kwargs["messages"][0]["role"] == "system"
        assert kwargs["messages"][1]["content"] == "Software Engineer"
        await client.close()

    @pytest.mark.asyncio
    async def test_chat_raises_when_not_configured(self) -> None:
        client = VilaoClient(VilaoClientConfig(api_key=""))
        with pytest.raises(VilaoUnavailableError, match="not configured"):
            await client.chat("hello")

    @pytest.mark.asyncio
    async def test_chat_circuit_breaker_after_threshold(self) -> None:
        cfg = VilaoClientConfig(api_key="sk-test", fail_threshold=2)
        client = VilaoClient(cfg)

        mock_openai = MagicMock()
        mock_openai.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("network down")
        )
        client._client = mock_openai

        with pytest.raises(VilaoError):
            await client.chat("a")
        with pytest.raises(VilaoError):
            await client.chat("b")

        assert client.circuit_open is True
        with pytest.raises(VilaoUnavailableError, match="circuit breaker is OPEN"):
            await client.chat("c")
        await client.close()

    @pytest.mark.asyncio
    async def test_chat_resets_failures_on_success(self) -> None:
        cfg = VilaoClientConfig(api_key="sk-test", fail_threshold=3)
        client = VilaoClient(cfg)

        mock_openai = MagicMock()
        mock_openai.chat.completions.create = AsyncMock(
            side_effect=[
                RuntimeError("boom"),
                RuntimeError("boom"),
                _make_response("ok"),
            ]
        )
        client._client = mock_openai

        with pytest.raises(VilaoError):
            await client.chat("a")
        with pytest.raises(VilaoError):
            await client.chat("b")
        assert client.circuit_open is False
        result = await client.chat("c")
        assert result == "ok"
        assert client.circuit_open is False
        await client.close()

    @pytest.mark.asyncio
    async def test_chat_uses_passed_cache(self) -> None:
        cfg = VilaoClientConfig(api_key="sk-test", fail_threshold=3)
        client = VilaoClient(cfg)
        mock_openai = MagicMock()
        mock_openai.chat.completions.create = AsyncMock(
            return_value=_make_response("Kết quả")
        )
        client._client = mock_openai

        cache: dict[str, str] = {}
        first = await translate_title_to_vietnamese(
            "Senior Engineer", client, cache=cache
        )
        second = await translate_title_to_vietnamese(
            "Senior Engineer", client, cache=cache
        )

        assert first == "Kết quả"
        assert second == "Kết quả"
        # Second call must come from cache, not from OpenAI.
        assert mock_openai.chat.completions.create.await_count == 1
        await client.close()

    @pytest.mark.asyncio
    async def test_chat_returns_empty_string_when_no_choices(self) -> None:
        client = VilaoClient(VilaoClientConfig(api_key="sk-test"))
        mock_openai = MagicMock()
        mock_openai.chat.completions.create = AsyncMock(
            return_value=SimpleNamespace(choices=[])
        )
        client._client = mock_openai
        assert await client.chat("hello") == ""
        await client.close()


# ---------------------------------------------------------------------------
# translate_title_to_vietnamese
# ---------------------------------------------------------------------------


class TestTranslateTitle:
    @pytest.mark.asyncio
    async def test_returns_none_when_client_unavailable(self) -> None:
        client = VilaoClient(VilaoClientConfig(api_key=""))
        assert await translate_title_to_vietnamese("anything", client) is None

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_title(self) -> None:
        client = VilaoClient(VilaoClientConfig(api_key="sk-test"))
        assert await translate_title_to_vietnamese("", client) is None
        assert await translate_title_to_vietnamese("   ", client) is None

    @pytest.mark.asyncio
    async def test_returns_none_when_api_fails(self) -> None:
        cfg = VilaoClientConfig(api_key="sk-test", fail_threshold=3)
        client = VilaoClient(cfg)
        mock_openai = MagicMock()
        mock_openai.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("api down")
        )
        client._client = mock_openai

        result = await translate_title_to_vietnamese("Engineer", client)
        assert result is None
        await client.close()


# ---------------------------------------------------------------------------
# TitleTranslator
# ---------------------------------------------------------------------------


class TestTitleTranslator:
    @pytest.mark.asyncio
    async def test_caches_translations(self) -> None:
        cfg = VilaoClientConfig(api_key="sk-test", fail_threshold=3)
        client = VilaoClient(cfg)
        mock_openai = MagicMock()
        mock_openai.chat.completions.create = AsyncMock(
            return_value=_make_response("Kỹ sư")
        )
        client._client = mock_openai

        translator = TitleTranslator(client)
        first = await translator.translate("Software Engineer")
        second = await translator.translate("Software Engineer")
        third = await translator.translate("Data Engineer")

        assert first == "Kỹ sư"
        assert second == "Kỹ sư"
        assert third == "Kỹ sư"
        assert translator.call_count == 2
        assert translator.cache_hits == 1
        await client.close()

    @pytest.mark.asyncio
    async def test_returns_none_when_unavailable(self) -> None:
        client = VilaoClient(VilaoClientConfig(api_key=""))
        translator = TitleTranslator(client)
        assert await translator.translate("anything") is None
        assert translator.call_count == 0


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


def test_system_prompt_is_vietnamese() -> None:
    assert "tiếng Việt" in TRANSLATION_SYSTEM_PROMPT
    assert "không giải thích" in TRANSLATION_SYSTEM_PROMPT
