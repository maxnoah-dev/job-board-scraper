"""Unit tests for the Vilao integration in the ETL pipeline."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from job_board_scraper.etl.pipeline import ScrapingPipeline


def _make_raw(title: str):
    from job_board_scraper.models.job import RawJobData

    return RawJobData(
        source_company_id="opswat",
        title=title,
        url=f"https://example.com/{title.replace(' ', '-').lower()}",
    )


class TestTransformerWithVilao:
    @pytest.mark.asyncio
    async def test_transform_async_injects_title_vi(self) -> None:
        from job_board_scraper.etl.transformer import Transformer

        translator = MagicMock()
        translator.translate = AsyncMock(return_value="Kỹ sư")
        transformer = Transformer(vilao_translator=translator)

        record = await transformer.transform_async(_make_raw("Engineer"), company_id=1)
        assert record.title_vi == "Kỹ sư"
        assert record.title == "Engineer"

    @pytest.mark.asyncio
    async def test_transform_async_handles_translator_failure(self) -> None:
        from job_board_scraper.etl.transformer import Transformer

        translator = MagicMock()
        translator.translate = AsyncMock(side_effect=RuntimeError("boom"))
        transformer = Transformer(vilao_translator=translator)
        record = await transformer.transform_async(_make_raw("Engineer"), company_id=1)
        assert record.title_vi is None

    @pytest.mark.asyncio
    async def test_transform_async_without_translator(self) -> None:
        from job_board_scraper.etl.transformer import Transformer

        transformer = Transformer()
        record = await transformer.transform_async(_make_raw("Engineer"), company_id=1)
        assert record.title == "Engineer"
        assert record.title_vi is None

    @pytest.mark.asyncio
    async def test_transform_batch_async_mixed_results(self) -> None:
        from job_board_scraper.etl.transformer import Transformer

        translator = MagicMock()
        translator.translate = AsyncMock(
            side_effect=[None, "Kỹ sư", "Quản lý"]
        )
        transformer = Transformer(vilao_translator=translator)
        records, errors = await transformer.transform_batch_async(
            [_make_raw("A"), _make_raw("B"), _make_raw("C")],
            company_id=1,
        )
        assert len(records) == 3
        assert records[0].title_vi is None
        assert records[1].title_vi == "Kỹ sư"
        assert records[2].title_vi == "Quản lý"
        assert errors == []


class TestPipelineVilaoWiring:
    def test_build_vilao_translator_disabled_when_off(self, monkeypatch) -> None:
        # Force a fresh config so the singleton doesn't leak across tests.
        import job_board_scraper.core.config as cfg_mod

        cfg_mod._settings = None
        monkeypatch.setattr(
            "job_board_scraper.core.config.get_settings",
            lambda: SimpleNamespace(
                VILAO_ENABLED=False,
                VILAO_API_KEY="",
                VILAO_BASE_URL="",
                VILAO_MODEL="",
                VILAO_TIMEOUT_S=15.0,
                VILAO_RATE_LIMIT_PER_MIN=60,
                VILAO_FAIL_THRESHOLD=3,
            ),
        )
        result = ScrapingPipeline._build_vilao_translator(enable_vilao=False)
        assert result is None

    def test_build_vilao_translator_enabled(self, monkeypatch) -> None:
        import job_board_scraper.core.config as cfg_mod
        from job_board_scraper.llm.translator import TitleTranslator  # noqa: N817
        from job_board_scraper.llm.vilao_client import VilaoClient  # noqa: N817

        cfg_mod._settings = None
        monkeypatch.setattr(
            "job_board_scraper.core.config.get_settings",
            lambda: SimpleNamespace(
                VILAO_ENABLED=True,
                VILAO_API_KEY="sk-test",
                VILAO_BASE_URL="https://api.vilao.ai/v1",
                VILAO_MODEL="gx/gpt-5.4",
                VILAO_TIMEOUT_S=15.0,
                VILAO_RATE_LIMIT_PER_MIN=60,
                VILAO_FAIL_THRESHOLD=3,
            ),
        )
        result = ScrapingPipeline._build_vilao_translator(enable_vilao=True)
        assert isinstance(result, TitleTranslator)
        assert isinstance(result._vilao, VilaoClient)
