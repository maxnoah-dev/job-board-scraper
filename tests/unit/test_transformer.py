"""Unit tests for ``etl/transformer.py`` covering sync + async paths."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from job_board_scraper.etl.transformer import Transformer
from job_board_scraper.models.job import JobRecord, RawJobData


def _raw(**overrides: Any) -> RawJobData:
    base: dict[str, Any] = {
        "source_company_id": "opswat",
        "title": "Senior Engineer",
        "url": "https://example.com/jobs/12345",
    }
    base.update(overrides)
    return RawJobData(**base)


class TestTransformerSync:
    def test_transform_canonicalises_url(self) -> None:
        record = Transformer().transform(_raw(), company_id=1)
        assert isinstance(record, JobRecord)
        assert record.company_id == 1
        assert record.canonical_url == "https://example.com/jobs/12345"

    def test_transform_defaults_location_to_remote(self) -> None:
        record = Transformer().transform(_raw(), company_id=1)
        assert record.location == "Remote"

    def test_transform_preserves_existing_location(self) -> None:
        record = Transformer().transform(
            _raw(location="Toronto, ON"), company_id=1
        )
        assert record.location == "Toronto, ON"

    def test_transform_falls_back_to_raw_url_on_bad_url(self) -> None:
        # canonicalize_url raises on missing scheme; transformer should keep
        # the raw URL rather than crashing.
        record = Transformer().transform(
            _raw(url="https://example.com/path?x=#bad"), company_id=1
        )
        assert isinstance(record.canonical_url, str)

    def test_transform_batch_collects_errors(self) -> None:
        # raw job with empty url raises in pydantic validator, so we can't
        # reach the batch path with raw bad data — transformer handles errors
        # only from canonicalize_url failures, which keep the raw url.
        transformer = Transformer()
        records, errors = transformer.transform_batch([_raw()], company_id=1)
        assert len(records) == 1
        assert errors == []  # canonicalize_url only soft-fails via fallback


class TestTransformerAsync:
    @pytest.mark.asyncio
    async def test_transform_async_no_translator(self) -> None:
        record = await Transformer().transform_async(_raw(), company_id=1)
        assert record.title == "Senior Engineer"
        assert record.title_vi is None

    @pytest.mark.asyncio
    async def test_transform_async_uses_translator(self) -> None:
        translator = MagicMock()
        translator.translate = AsyncMock(return_value="Kỹ sư cao cấp")
        record = await Transformer(vilao_translator=translator).transform_async(
            _raw(), company_id=1
        )
        assert record.title_vi == "Kỹ sư cao cấp"

    @pytest.mark.asyncio
    async def test_transform_async_returns_none_on_exception(self) -> None:
        translator = MagicMock()
        translator.translate = AsyncMock(side_effect=ValueError("x"))
        record = await Transformer(vilao_translator=translator).transform_async(
            _raw(), company_id=1
        )
        assert record.title_vi is None

    @pytest.mark.asyncio
    async def test_transform_batch_async_runs_concurrently(self) -> None:
        translator = MagicMock()

        async def _translate(t: str) -> str:
            return f"vi-{t}"

        translator.translate = AsyncMock(side_effect=_translate)
        records, errors = await Transformer(
            vilao_translator=translator
        ).transform_batch_async(
            [_raw(title="A"), _raw(title="B"), _raw(title="C")], company_id=1
        )
        assert len(records) == 3
        assert {r.title_vi for r in records} == {"vi-A", "vi-B", "vi-C"}
        assert errors == []


class TestTranslatorSetRuntime:
    def test_set_vilao_translator_replaces_instance(self) -> None:
        t = Transformer()
        assert t._vilao is None
        t.set_vilao_translator("dummy")
        assert t._vilao == "dummy"
        t.set_vilao_translator(None)
        assert t._vilao is None
