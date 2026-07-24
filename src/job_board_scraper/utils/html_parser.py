"""HTML parsing utilities for static HTML scraping.

Provides BeautifulSoup helpers, selector validation, pagination utilities,
and job listing extraction helpers.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup as BSBeautifulSoup

    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    BSBeautifulSoup = None

try:
    from dateparser import parse as parse_date

    DATEPARSER_AVAILABLE = True
except ImportError:
    DATEPARSER_AVAILABLE = False
    parse_date = None


# ---------------------------------------------------------------------------
# Config dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SelectorConfig:
    """Configuration for CSS selectors used in HTML parsing."""

    job_card: str = "article.job, div.job-listing, .job-card"
    title: str = "h2.title, h3.title, .job-title"
    location: str = ".location, .job-location, [data-location]"
    date_posted: str = ".date, .posted-date, time"
    link: str = "a[href], .job-link"


@dataclass
class PaginationConfig:
    """Configuration for pagination handling."""

    next_button: str = "a.next, .pagination-next, a[rel='next']"
    page_param: str = "page"
    max_pages: int = 10
    base_url: str | None = None


# ---------------------------------------------------------------------------
# Enhanced config dataclasses (Phase 6 additions)
# ---------------------------------------------------------------------------


@dataclass
class JobListingConfig:
    """Configuration for extracting job listings from an HTML page.

    Attributes:
        container_selector: CSS selector for the job listing container.
        job_selectors: Dict mapping field names to selector strings.
        url_patterns: Regex patterns for constructing job URLs.
    """

    container_selector: str
    title_selector: str = "h2.title, h3.title, .job-title"
    url_selector: str = "a[href]"
    location_selector: str | None = None
    date_selector: str | None = None
    url_attribute: str = "href"
    job_selectors: dict[str, str] = field(default_factory=dict)
    url_patterns: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# BeautifulSoup helpers
# ---------------------------------------------------------------------------


def parse_html(html: str | bytes, parser: str = "lxml") -> BeautifulSoup | None:
    """Parse HTML string into BeautifulSoup object.

    Args:
        html: HTML content to parse
        parser: Parser to use ("lxml", "html.parser", "html5lib")

    Returns:
        BeautifulSoup object or None if bs4 not available
    """
    if not BS4_AVAILABLE:
        return None
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")
    return BeautifulSoup(html, parser)


def find_elements(
    soup: BeautifulSoup,
    selector: str,
) -> list[Tag]:
    """Find all elements matching a CSS selector.

    Args:
        soup: BeautifulSoup object
        selector: CSS selector string

    Returns:
        List of matching Tag elements
    """
    if soup is None:
        return []
    try:
        return list(soup.select(selector))
    except Exception as e:
        logger.debug("Selector %r failed: %s", selector, e)
        return []


def find_element(
    soup: BeautifulSoup,
    selector: str,
) -> Tag | None:
    """Find the first element matching a CSS selector.

    Args:
        soup: BeautifulSoup object
        selector: CSS selector string

    Returns:
        First matching Tag element or None
    """
    elements = find_elements(soup, selector)
    return elements[0] if elements else None


def get_text(element: Tag | None, strip: bool = True) -> str:
    """Extract text content from an element.

    Args:
        element: BeautifulSoup Tag element
        strip: Whether to strip whitespace

    Returns:
        Text content with whitespace normalized
    """
    if element is None:
        return ""
    text = element.get_text(separator=" ", strip=strip)
    return " ".join(text.split()) if strip else text


def get_attribute(element: Tag | None, attr: str, default: str = "") -> str:
    """Get an attribute value from an element.

    Args:
        element: BeautifulSoup Tag element
        attr: Attribute name
        default: Default value if attribute not found

    Returns:
        Attribute value or default
    """
    if element is None:
        return default
    return element.get(attr, default)


def get_href(element: Tag | None, base_url: str | None = None) -> str:
    """Extract href attribute from an element.

    Args:
        element: BeautifulSoup Tag element with an anchor tag
        base_url: Optional base URL to resolve relative links

    Returns:
        href value or empty string
    """
    if element is None:
        return ""
    tag = element.find("a") if not element.name == "a" else element
    if tag is None:
        return ""
    href = tag.get("href", "")
    if href and base_url and not href.startswith(("http://", "https://")):
        from urllib.parse import urljoin

        href = urljoin(base_url, href)
    return href


def validate_selector(html: str, selector: str) -> bool:
    """Validate that a CSS selector matches elements in HTML.

    Args:
        html: HTML content
        selector: CSS selector to validate

    Returns:
        True if selector matches at least one element
    """
    soup = parse_html(html)
    if soup is None:
        return False
    return len(find_elements(soup, selector)) > 0


# ---------------------------------------------------------------------------
# Job card extraction helpers
# ---------------------------------------------------------------------------


def extract_job_cards_by_class(
    soup: BeautifulSoup,
    selector_config: SelectorConfig | None = None,
) -> list[Tag]:
    """Extract job card elements from a listing page.

    Args:
        soup: BeautifulSoup object
        selector_config: Selector configuration

    Returns:
        List of job card elements
    """
    config = selector_config or SelectorConfig()
    return find_elements(soup, config.job_card)


def extract_job_links(
    soup: BeautifulSoup,
    base_url: str | None = None,
) -> list[str]:
    """Extract job listing URLs from a page.

    Args:
        soup: BeautifulSoup object
        base_url: Base URL for resolving relative links

    Returns:
        List of absolute job URLs
    """
    links: list[str] = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "")
        if href and ("job" in href.lower() or "/careers/" in href):
            if base_url and not href.startswith("http"):
                from urllib.parse import urljoin

                href = urljoin(base_url, href)
            links.append(href)
    return links


def extract_all_jobs(
    soup: BeautifulSoup | None,
    selector_config: SelectorConfig | JobListingConfig | None = None,
    base_url: str | None = None,
    job_listing_config: JobListingConfig | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Extract all job listings from a page.

    Args:
        soup: BeautifulSoup object (can be None if BS4 unavailable)
        selector_config: SelectorConfig for simple extraction
        base_url: Base URL for resolving relative links
        job_listing_config: JobListingConfig for custom extraction

    Returns:
        Tuple of (list of job dictionaries, list of warnings)
    """
    warnings: list[str] = []
    jobs: list[dict[str, Any]] = []

    if soup is None:
        return jobs, warnings

    if job_listing_config or isinstance(selector_config, JobListingConfig):
        config = job_listing_config or selector_config
        return _extract_with_job_config(soup, config, base_url)

    config = selector_config or SelectorConfig()
    for card in extract_job_cards_by_class(soup, config):
        title_elem = find_element(card, config.title)
        title = get_text(title_elem) if title_elem else ""

        location_elem = find_element(card, config.location)
        location = get_text(location_elem) if location_elem else ""

        url = get_href(card) if base_url else get_attribute(card, config.link)

        date_elem = find_element(card, config.date_posted)
        date_posted = get_text(date_elem) if date_elem else ""

        if title:
            job = {
                "title": title,
                "location": location or "Remote",
                "url": url,
                "date_posted": date_posted,
            }
            jobs.append(job)
        else:
            warnings.append("Skipping card without title")

    return jobs, warnings


def _extract_with_job_config(
    soup: BeautifulSoup,
    config: JobListingConfig,
    base_url: str | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Extract jobs using JobListingConfig.

    Args:
        soup: BeautifulSoup object
        config: JobListingConfig
        base_url: Base URL for resolving links

    Returns:
        Tuple of (jobs list, warnings list)
    """
    warnings: list[str] = []
    jobs: list[dict[str, Any]] = []

    containers = find_elements(soup, config.container_selector)

    if not containers:
        warnings.append(
            f"Container selector '{config.container_selector}' matched no elements"
        )
        return jobs, warnings

    for container in containers:
        title_elem = find_element(container, config.title_selector)
        title = get_text(title_elem) if title_elem else ""

        url_elem = find_element(container, config.url_selector)
        if url_elem:
            if config.url_attribute == "href":
                url = get_href(url_elem, base_url)
            else:
                url = get_attribute(url_elem, config.url_attribute, "")
        else:
            url = ""

        location = ""
        if config.location_selector:
            location_elem = find_element(container, config.location_selector)
            location = get_text(location_elem) if location_elem else ""

        date_posted = ""
        if config.date_selector:
            date_elem = find_element(container, config.date_selector)
            date_posted = get_text(date_elem) if date_elem else ""

        if title and url:
            job = {
                "title": title,
                "location": location or "Remote",
                "url": url,
                "date_posted": date_posted,
            }
            jobs.append(job)
        elif not title:
            warnings.append("Skipping job without title")

    return jobs, warnings


# ---------------------------------------------------------------------------
# Pagination helpers
# ---------------------------------------------------------------------------


def find_next_page_url(
    soup: BeautifulSoup,
    pagination_config: PaginationConfig | None = None,
) -> str | None:
    """Find the URL for the next page of results.

    Args:
        soup: BeautifulSoup object
        pagination_config: Pagination configuration

    Returns:
        URL of next page or None if no more pages
    """
    config = pagination_config or PaginationConfig()
    next_link = find_element(soup, config.next_button)
    if next_link:
        return get_href(next_link)
    return None


def construct_page_url(
    base_url: str,
    page: int,
    page_param: str = "page",
) -> str:
    """Construct a paginated URL.

    Args:
        base_url: Base URL for the listing page
        page: Page number (1-indexed)
        page_param: URL parameter name for page number

    Returns:
        URL with page parameter appended
    """
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{page_param}={page}"


def should_continue_pagination(
    current_page: int,
    jobs_found: int,
    pagination_config: PaginationConfig | None = None,
) -> bool:
    """Determine if pagination should continue.

    Args:
        current_page: Current page number
        jobs_found: Number of jobs found on current page
        pagination_config: Pagination configuration

    Returns:
        True if pagination should continue
    """
    config = pagination_config or PaginationConfig()

    if current_page >= config.max_pages:
        return False

    if jobs_found == 0:
        return False

    return True


# ---------------------------------------------------------------------------
# Date parsing helpers
# ---------------------------------------------------------------------------


def normalize_date_to_utc(date_str: str) -> datetime | None:
    """Normalize a date string to UTC datetime.

    Args:
        date_str: Date string in various formats

    Returns:
        datetime object in UTC or None if parsing fails
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # Try dateparser first if available
    if DATEPARSER_AVAILABLE:
        parsed = parse_date(date_str)
        if parsed:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed

    # Try relative date patterns
    relative_result = _parse_relative_date(date_str.lower())
    if relative_result:
        return relative_result

    # Try common formats
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed
        except ValueError:
            continue

    return None


def _parse_relative_date(date_str: str) -> datetime | None:
    """Parse relative date strings like '3 days ago'.

    Args:
        date_str: Lowercase date string

    Returns:
        Parsed datetime or None
    """
    from datetime import timedelta

    now = datetime.now(UTC)

    if "today" in date_str:
        return now

    if "yesterday" in date_str:
        return now - timedelta(days=1)

    patterns = [
        (r"(\d+)\s+day", "days"),
        (r"(\d+)\s+hour", "hours"),
        (r"(\d+)\s+week", "weeks"),
        (r"(\d+)\s+month", "months"),
    ]

    for pattern, unit in patterns:
        match = re.search(pattern, date_str)
        if match:
            value = int(match.group(1))
            delta_map = {
                "days": timedelta(days=value),
                "hours": timedelta(hours=value),
                "weeks": timedelta(weeks=value),
                "months": timedelta(days=value * 30),
            }
            return now - delta_map[unit]

    return None


def parse_date_string(date_str: str | None) -> datetime | None:
    """Parse a date string into a datetime object.

    Alias for normalize_date_to_utc for API compatibility.

    Args:
        date_str: Date string to parse

    Returns:
        datetime object or None
    """
    if date_str is None:
        return None
    return normalize_date_to_utc(date_str)


def format_date_for_storage(date: datetime | None) -> str | None:
    """Format a datetime for database storage.

    Args:
        date: datetime object

    Returns:
        ISO format date string or None
    """
    if date is None:
        return None
    return date.isoformat()


def is_likely_job_listing_page(soup: BeautifulSoup) -> bool:
    """Check if a page is likely a job listing page.

    Args:
        soup: BeautifulSoup object

    Returns:
        True if page appears to be a job listing
    """
    if soup is None:
        return False

    # Look for common job listing indicators
    job_indicators = [
        "job",
        "career",
        "position",
        "opportunity",
        "employment",
    ]

    page_text = soup.get_text().lower()
    text_matches = sum(1 for indicator in job_indicators if indicator in page_text)

    # Also check for common listing elements
    listing_elements = len(soup.select(".job, .listing, .position, article, .job-card"))
    element_matches = min(listing_elements, 5)

    return text_matches >= 2 or element_matches >= 2


# ---------------------------------------------------------------------------
# HTML adapter helper functions
# ---------------------------------------------------------------------------


def create_job_listing_config(
    container_selector: str,
    title_selector: str,
    url_selector: str,
    location_selector: str | None = None,
    date_selector: str | None = None,
    url_attribute: str = "href",
) -> JobListingConfig:
    """Create a standard job listing configuration.

    Convenience function for creating common selector configurations.

    Args:
        container_selector: Selector for job listing container.
        title_selector: Selector for job title (text content).
        url_selector: Selector for job URL (extracts attribute).
        location_selector: Optional selector for location.
        date_selector: Optional selector for date posted.
        url_attribute: Attribute to extract for URL.

    Returns:
        JobListingConfig ready for use.
    """
    return JobListingConfig(
        container_selector=container_selector,
        title_selector=title_selector,
        url_selector=url_selector,
        location_selector=location_selector,
        date_selector=date_selector,
        url_attribute=url_attribute,
    )


def extract_date_from_string(date_str: str | None) -> str | None:
    """Extract and normalize a date from a string.

    Args:
        date_str: Raw date string from HTML.

    Returns:
        ISO 8601 formatted date string or None.
    """
    if not date_str:
        return None

    dt = normalize_date_to_utc(date_str)
    if dt:
        return dt.isoformat()

    return date_str
