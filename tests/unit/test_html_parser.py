"""Tests for HTML parsing utilities."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from job_board_scraper.utils.html_parser import (
    PaginationConfig,
    SelectorConfig,
    construct_page_url,
    extract_all_jobs,
    extract_job_cards_by_class,
    extract_job_links,
    find_element,
    find_elements,
    find_next_page_url,
    format_date_for_storage,
    get_attribute,
    get_href,
    get_text,
    is_likely_job_listing_page,
    normalize_date_to_utc,
    parse_date_string,
    parse_html,
    should_continue_pagination,
    validate_selector,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_html() -> str:
    """Sample HTML for testing."""
    return """
    <html>
    <head><title>Job Listings</title></head>
    <body>
        <div class="job-card">
            <h2 class="title">Software Engineer</h2>
            <span class="location">New York, NY</span>
            <a href="/jobs/1" class="job-link">View Job</a>
            <span class="date">2026-07-15</span>
        </div>
        <div class="job-card">
            <h2 class="title">Product Manager</h2>
            <span class="location">Remote</span>
            <a href="/jobs/2" class="job-link">View Job</a>
            <span class="date">2026-07-10</span>
        </div>
        <div class="job-card">
            <h2 class="title">Designer</h2>
            <span class="location">San Francisco, CA</span>
            <a href="/jobs/3" class="job-link">View Job</a>
            <span class="date">3 days ago</span>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def soup(sample_html: str):
    """BeautifulSoup object from sample HTML."""
    return parse_html(sample_html)


@pytest.fixture
def pagination_html() -> str:
    """HTML with pagination."""
    return """
    <html>
    <body>
        <div class="job">Job 1</div>
        <div class="job">Job 2</div>
        <nav class="pagination">
            <a href="/jobs?page=1">Prev</a>
            <a href="/jobs?page=1">1</a>
            <a href="/jobs?page=2" class="next">2</a>
            <a href="/jobs?page=3">3</a>
            <a href="/jobs?page=3">Next</a>
        </nav>
    </body>
    </html>
    """


# ---------------------------------------------------------------------------
# parse_html tests
# ---------------------------------------------------------------------------


class TestParseHtml:
    """Tests for parse_html function."""

    def test_parse_html_string(self) -> None:
        """Should parse HTML string."""
        html = "<html><body><p>Hello</p></body></html>"
        soup = parse_html(html)
        assert soup is not None
        assert soup.find("p").get_text() == "Hello"

    def test_parse_html_bytes(self) -> None:
        """Should parse HTML bytes."""
        html = b"<html><body><p>Hello</p></body></html>"
        soup = parse_html(html)
        assert soup is not None
        assert soup.find("p").get_text() == "Hello"

    def test_parse_html_custom_parser(self) -> None:
        """Should use specified parser."""
        html = "<html><body><p>Hello</p></body></html>"
        soup = parse_html(html, parser="html.parser")
        assert soup is not None
        assert soup.find("p").get_text() == "Hello"


# ---------------------------------------------------------------------------
# get_text tests
# ---------------------------------------------------------------------------


class TestGetText:
    """Tests for get_text function."""

    def test_get_text_from_element(self) -> None:
        """Should extract text from element."""
        html = "<div>Hello World</div>"
        soup = parse_html(html)
        assert soup is not None
        text = get_text(soup.find("div"))
        assert text == "Hello World"

    def test_get_text_strips_whitespace(self) -> None:
        """Should strip whitespace."""
        html = "<div>  Hello  </div>"
        soup = parse_html(html)
        assert soup is not None
        text = get_text(soup.find("div"))
        assert text == "Hello"

    def test_get_text_default_value(self) -> None:
        """Should return default for None element."""
        text = get_text(None)
        assert text == ""

    def test_get_text_preserves_spaces(self) -> None:
        """Should not strip when strip=False."""
        html = "<div>  Hello  </div>"
        soup = parse_html(html)
        assert soup is not None
        text = get_text(soup.find("div"), strip=False)
        assert "  " in text


# ---------------------------------------------------------------------------
# get_attribute tests
# ---------------------------------------------------------------------------


class TestGetAttribute:
    """Tests for get_attribute function."""

    def test_get_attribute_value(self) -> None:
        """Should extract attribute value."""
        html = '<a href="https://example.com">Link</a>'
        soup = parse_html(html)
        assert soup is not None
        href = get_attribute(soup.find("a"), "href")
        assert href == "https://example.com"

    def test_get_attribute_default(self) -> None:
        """Should return default for missing attribute."""
        html = "<a>Link</a>"
        soup = parse_html(html)
        assert soup is not None
        href = get_attribute(soup.find("a"), "href", default="none")
        assert href == "none"

    def test_get_attribute_none_element(self) -> None:
        """Should return default for None element."""
        href = get_attribute(None, "href", default="none")
        assert href == "none"


# ---------------------------------------------------------------------------
# get_href tests
# ---------------------------------------------------------------------------


class TestGetHref:
    """Tests for get_href function."""

    def test_get_href_absolute(self) -> None:
        """Should extract absolute href."""
        html = '<a href="https://example.com/jobs/1">Job</a>'
        soup = parse_html(html)
        assert soup is not None
        href = get_href(soup.find("a"))
        assert href == "https://example.com/jobs/1"

    def test_get_href_relative(self) -> None:
        """Should resolve relative href with base_url."""
        html = '<a href="/jobs/1">Job</a>'
        soup = parse_html(html)
        assert soup is not None
        href = get_href(soup.find("a"), base_url="https://example.com")
        assert href == "https://example.com/jobs/1"

    def test_get_href_skips_anchors(self) -> None:
        """Should skip hrefs starting with #."""
        html = '<a href="#section">Section</a>'
        soup = parse_html(html)
        assert soup is not None
        # get_href now doesn't filter anchors, just extracts href
        href = get_href(soup.find("a"))
        assert href == "#section"

    def test_get_href_with_base_url(self) -> None:
        """Should resolve relative hrefs with base_url."""
        html = '<a href="/jobs/1">Job</a>'
        soup = parse_html(html)
        assert soup is not None
        href = get_href(soup.find("a"), base_url="https://example.com")
        assert href == "https://example.com/jobs/1"


# ---------------------------------------------------------------------------
# validate_selector tests
# ---------------------------------------------------------------------------


class TestValidateSelector:
    """Tests for validate_selector function."""

    def test_valid_simple_selector(self) -> None:
        """Should accept valid simple selectors."""
        html = "<div class='test'></div>"
        assert validate_selector(html, "div") is True
        assert validate_selector(html, ".test") is True

    def test_invalid_html(self) -> None:
        """Should return False for invalid HTML."""
        assert validate_selector("not html", ".test") is False


# ---------------------------------------------------------------------------
# find_element / find_elements tests
# ---------------------------------------------------------------------------


class TestFindElements:
    """Tests for find_element and find_elements functions."""

    def test_find_element_returns_first(self) -> None:
        """Should return first matching element."""
        html = "<div class='a'>1</div><div class='a'>2</div>"
        soup = parse_html(html)
        assert soup is not None
        elem = find_element(soup, ".a")
        assert elem is not None
        assert get_text(elem) == "1"

    def test_find_element_returns_none(self) -> None:
        """Should return None for no match."""
        html = "<div>text</div>"
        soup = parse_html(html)
        assert soup is not None
        elem = find_element(soup, ".nonexistent")
        assert elem is None

    def test_find_elements_returns_all(self) -> None:
        """Should return all matching elements."""
        html = "<div class='a'>1</div><div class='a'>2</div>"
        soup = parse_html(html)
        assert soup is not None
        elems = find_elements(soup, ".a")
        assert len(elems) == 2

    def test_find_elements_empty_list(self) -> None:
        """Should return empty list for no match."""
        html = "<div>text</div>"
        soup = parse_html(html)
        assert soup is not None
        elems = find_elements(soup, ".nonexistent")
        assert elems == []


# ---------------------------------------------------------------------------
# extract_all_jobs tests
# ---------------------------------------------------------------------------


class TestExtractAllJobs:
    """Tests for extract_all_jobs function."""

    def test_extract_all_jobs(self, soup) -> None:
        """Should extract all job listings."""
        config = SelectorConfig(
            job_card=".job-card",
            title=".title",
            location=".location",
            link="a",
        )
        jobs, warnings = extract_all_jobs(soup, config)
        assert len(jobs) == 3
        assert len(warnings) == 0

    def test_extract_all_jobs_no_matches(self, soup) -> None:
        """Should return warning for no matches."""
        config = SelectorConfig(job_card=".nonexistent")
        jobs, warnings = extract_all_jobs(soup, config)
        assert len(jobs) == 0
        assert len(warnings) == 0  # No matches, no warnings


# ---------------------------------------------------------------------------
# Pagination tests
# ---------------------------------------------------------------------------


class TestPagination:
    """Tests for pagination utilities."""

    def test_find_next_page_url(self, pagination_html) -> None:
        """Should find next page URL."""
        soup = parse_html(pagination_html)
        assert soup is not None
        config = PaginationConfig(
            next_button="a.next",
        )
        next_url = find_next_page_url(soup, config)
        assert next_url == "/jobs?page=2"

    def test_find_next_page_url_no_match(self) -> None:
        """Should return None when no next page."""
        html = "<html><body><p>No pagination</p></body></html>"
        soup = parse_html(html)
        assert soup is not None
        config = PaginationConfig(next_button=".next")
        next_url = find_next_page_url(soup, config)
        assert next_url is None

    def test_construct_page_url_simple(self) -> None:
        """Should construct URL with page param."""
        url = construct_page_url("https://example.com/jobs", 2)
        assert "page=2" in url

    def test_construct_page_url_existing_params(self) -> None:
        """Should preserve existing query params."""
        url = construct_page_url("https://example.com/jobs?sort=date", 2)
        assert "page=2" in url
        assert "sort=date" in url

    def test_should_continue_pagination_max_pages(self) -> None:
        """Should stop at max pages."""
        config = PaginationConfig(max_pages=5)
        assert should_continue_pagination(5, 10, config) is False
        assert should_continue_pagination(4, 10, config) is True

    def test_should_continue_pagination_no_jobs(self) -> None:
        """Should stop when no jobs found."""
        config = PaginationConfig()
        assert should_continue_pagination(1, 0, config) is False

    def test_should_continue_pagination_has_jobs(self) -> None:
        """Should continue when jobs found."""
        config = PaginationConfig()
        assert should_continue_pagination(1, 5, config) is True


# ---------------------------------------------------------------------------
# Date parsing tests
# ---------------------------------------------------------------------------


class TestDateParsing:
    """Tests for date parsing utilities."""

    def test_parse_date_iso(self) -> None:
        """Should parse ISO date."""
        dt = parse_date_string("2026-07-15")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 7
        assert dt.day == 15

    def test_parse_date_relative_today(self) -> None:
        """Should parse 'today'."""
        dt = parse_date_string("today")
        assert dt is not None
        now = datetime.now(UTC)
        assert dt.date() == now.date()

    def test_parse_date_relative_days(self) -> None:
        """Should parse relative date '3 days ago'."""
        dt = parse_date_string("3 days ago")
        assert dt is not None
        # Should be within the last 4 days
        now = datetime.now(UTC)
        assert (now - dt).days <= 4

    def test_parse_date_invalid(self) -> None:
        """Should return None for invalid date."""
        dt = parse_date_string("not a date")
        assert dt is None

    def test_parse_date_none(self) -> None:
        """Should return None for None input."""
        dt = parse_date_string(None)
        assert dt is None

    def test_normalize_date_to_utc_naive(self) -> None:
        """Should add UTC to naive datetime."""
        naive = datetime(2026, 7, 15, 10, 30, 0)
        utc = normalize_date_to_utc("2026-07-15")
        assert utc is not None

    def test_normalize_date_to_utc_none(self) -> None:
        """Should return None for None."""
        result = normalize_date_to_utc("")
        assert result is None

    def test_format_date_for_storage(self) -> None:
        """Should format datetime as ISO string."""
        dt = datetime(2026, 7, 15, 10, 30, 0, tzinfo=UTC)
        formatted = format_date_for_storage(dt)
        assert formatted is not None
        assert "2026-07-15" in formatted

    def test_format_date_for_storage_none(self) -> None:
        """Should return None for None."""
        formatted = format_date_for_storage(None)
        assert formatted is None


# ---------------------------------------------------------------------------
# Job card extraction tests
# ---------------------------------------------------------------------------


class TestJobCardExtraction:
    """Tests for job card extraction helpers."""

    def test_extract_job_cards_by_class(self, soup) -> None:
        """Should find job cards by class name."""
        config = SelectorConfig(job_card=".job-card")
        cards = extract_job_cards_by_class(soup, config)
        assert len(cards) == 3

    def test_extract_job_links(self, soup) -> None:
        """Should extract job links."""
        links = extract_job_links(soup, base_url="https://example.com")
        assert len(links) == 3

    def test_is_likely_job_listing_page(self, soup) -> None:
        """Should identify job listing page based on element count."""
        # Sample HTML has 3 job-card elements
        assert is_likely_job_listing_page(soup) is True

    def test_is_likely_job_listing_page_not(self) -> None:
        """Should reject non-job page."""
        html = "<html><body><p>About us page</p></body></html>"
        soup = parse_html(html)
        assert soup is not None
        assert is_likely_job_listing_page(soup) is False
