"""Unit tests for ``adapters/implementations/tiktok_adapter.py``."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from job_board_scraper.adapters.implementations.tiktok_adapter import (
    COMPLIANCE_STATUS,
    TiktokAdapter,
    get_compliance_status,
    is_compliance_blocked,
)
from job_board_scraper.utils.browser import AntiBotDetection


class TestTikTokTopLevel:
    def test_compliance_status_is_needs_review(self) -> None:
        assert COMPLIANCE_STATUS == "needs-review"
        assert is_compliance_blocked() is False
        assert get_compliance_status() == "needs-review"


class TestTikTokAdapter:
    def test_init_defaults(self) -> None:
        a = TiktokAdapter()
        assert a.slug == "tiktok"
        assert a.base_url == "https://careers.tiktok.com"
        assert a.adapter_type == "browser"
        assert a.is_started is False

    def test_get_listing_url(self) -> None:
        a = TiktokAdapter()
        assert a._get_listing_url() == "https://careers.tiktok.com/search?page=1"
        assert a._get_listing_url(page=3) == "https://careers.tiktok.com/search?page=3"

    def test_parse_jobs_empty(self) -> None:
        a = TiktokAdapter()
        assert a._parse_jobs("<html></html>") == []

    def test_parse_jobs_with_card(self) -> None:
        a = TiktokAdapter()
        html = """
        <html>
          <body>
            <div data-job-id="t1">
              <a href="/position/123">Staff Engineer</a>
              <span class="location">Singapore</span>
            </div>
          </body>
        </html>
        """
        jobs = a._parse_jobs(html)
        assert len(jobs) == 1
        assert jobs[0].title == "Staff Engineer"
        assert jobs[0].url == "https://careers.tiktok.com/position/123"
        assert jobs[0].location == "Singapore"
        assert jobs[0].source_job_id == "t1"
        assert jobs[0].source_company_id == "tiktok"

    def test_parse_jobs_absolute_url(self) -> None:
        a = TiktokAdapter()
        html = """
        <div class="jobCard">
          <a href="https://careers.tiktok.com/position/999">Senior PM</a>
        </div>
        """
        jobs = a._parse_jobs(html)
        assert len(jobs) == 1
        assert jobs[0].url == "https://careers.tiktok.com/position/999"

    def test_parse_jobs_default_location(self) -> None:
        a = TiktokAdapter()
        html = """
        <article class="job">
          <a href="/position/1">SWE</a>
        </article>
        """
        jobs = a._parse_jobs(html)
        assert jobs[0].location == "Singapore"

    def test_parse_jobs_skips_card_without_link(self) -> None:
        a = TiktokAdapter()
        html = """
        <div data-job-id="t1">
          <h3>No link</h3>
        </div>
        """
        jobs = a._parse_jobs(html)
        assert jobs == []

    def test_parse_jobs_supports_playwright_like_object(self) -> None:
        a = TiktokAdapter()
        page = MagicMock()
        page.content = MagicMock(return_value='<div data-job-id="x"><a href="/p/1">Hello</a></div>')
        jobs = a._parse_jobs(page)
        assert len(jobs) == 1
        # content() should have been called once
        page.content.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_navigation_logs_warning_on_timeout(self) -> None:
        a = TiktokAdapter()
        page = MagicMock()
        page.wait_for_selector = AsyncMock(side_effect=Exception("timeout"))
        # Should swallow the exception (best-effort)
        await a._post_navigation(page)

    @pytest.mark.asyncio
    async def test_handle_anti_bot_returns_false(self) -> None:
        a = TiktokAdapter()
        detection = AntiBotDetection(detected=True, challenge_type="cloudflare")
        result = await a._handle_anti_bot(detection)
        assert result is False
