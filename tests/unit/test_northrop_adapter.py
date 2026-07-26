"""Unit tests for ``adapters/implementations/northrop_adapter.py``."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from job_board_scraper.adapters.implementations.northrop_adapter import (
    COMPLIANCE_STATUS,
    NorthropAdapter,
    get_compliance_status,
    is_compliance_blocked,
)
from job_board_scraper.utils.browser import AntiBotDetection


class TestNorthropTopLevel:
    def test_compliance_status_is_needs_review(self) -> None:
        assert COMPLIANCE_STATUS == "needs-review"
        assert is_compliance_blocked() is False
        assert get_compliance_status() == "needs-review"


class TestNorthropAdapter:
    def test_init_defaults(self) -> None:
        a = NorthropAdapter()
        assert a.slug == "northrop"
        assert a.base_url == "https://www.northropgrumman.com/careers"
        assert a.adapter_type == "browser"
        assert a.is_started is False

    def test_get_listing_url(self) -> None:
        a = NorthropAdapter()
        assert a._get_listing_url() == "https://www.northropgrumman.com/careers?page=1"
        assert a._get_listing_url(page=2) == "https://www.northropgrumman.com/careers?page=2"

    def test_parse_jobs_empty(self) -> None:
        a = NorthropAdapter()
        assert a._parse_jobs("<html></html>") == []

    def test_parse_jobs_with_list_item(self) -> None:
        a = NorthropAdapter()
        html = """
        <html>
          <body>
            <li data-automation-id="jobListItem">
              <a data-automation-id="jobTitle" href="/job/123">Software Engineer</a>
              <div data-automation-id="jobLocation">Falls Church, VA</div>
            </li>
          </body>
        </html>
        """
        jobs = a._parse_jobs(html)
        assert len(jobs) == 1
        assert jobs[0].title == "Software Engineer"
        assert jobs[0].url == "https://www.northropgrumman.com/job/123"
        assert jobs[0].location == "Falls Church, VA"

    def test_parse_jobs_default_location(self) -> None:
        a = NorthropAdapter()
        html = """
        <li data-automation-id="job">
          <a href="/job/9">Cyber Analyst</a>
        </li>
        """
        jobs = a._parse_jobs(html)
        assert jobs[0].location == "Falls Church, VA"

    def test_parse_jobs_absolute_url(self) -> None:
        a = NorthropAdapter()
        html = """
        <li data-automation-id="job">
          <a href="https://careers.northropgrumman.com/job/9">Cyber Analyst</a>
        </li>
        """
        jobs = a._parse_jobs(html)
        assert jobs[0].url == "https://careers.northropgrumman.com/job/9"

    def test_parse_jobs_skips_card_without_link(self) -> None:
        a = NorthropAdapter()
        html = """
        <li data-automation-id="job">
          <h3>No link here</h3>
        </li>
        """
        jobs = a._parse_jobs(html)
        assert jobs == []

    def test_parse_jobs_supports_playwright_like_object(self) -> None:
        a = NorthropAdapter()
        page = MagicMock()
        page.content = MagicMock(return_value='<li data-automation-id="job"><a href="/job/1">Hello</a></li>')
        jobs = a._parse_jobs(page)
        assert len(jobs) == 1
        page.content.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_navigation_swallows_timeout(self) -> None:
        a = NorthropAdapter()
        page = MagicMock()
        page.wait_for_selector = AsyncMock(side_effect=Exception("timeout"))
        await a._post_navigation(page)  # must not raise

    @pytest.mark.asyncio
    async def test_handle_anti_bot_returns_false(self) -> None:
        a = NorthropAdapter()
        detection = AntiBotDetection(detected=True, challenge_type="cloudflare")
        result = await a._handle_anti_bot(detection)
        assert result is False
