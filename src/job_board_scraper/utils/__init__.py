"""Utilities package."""

from job_board_scraper.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitState,
)
from job_board_scraper.utils.html_parser import (
    JobListingConfig,
    PaginationConfig,
    SelectorConfig,
    construct_page_url,
    extract_all_jobs,
    extract_date_from_string,
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
from job_board_scraper.utils.http import HttpClient, http_client
from job_board_scraper.utils.rate_limiter import (
    API_DELAY_RANGE,
    BROWSER_DELAY_RANGE,
    HTML_DELAY_RANGE,
    RateLimitConfig,
    RateLimiter,
    TokenBucket,
    defaults_for_type,
)
from job_board_scraper.utils.retry import (
    RetryConfig,
    calculate_delay,
    is_retryable_exception,
    is_retryable_http_error,
    retry_with_backoff,
)

__all__ = [
    # HTML Parser
    "JobListingConfig",
    "PaginationConfig",
    "SelectorConfig",
    "construct_page_url",
    "extract_all_jobs",
    "extract_date_from_string",
    "extract_job_cards_by_class",
    "extract_job_links",
    "find_element",
    "find_elements",
    "find_next_page_url",
    "format_date_for_storage",
    "get_attribute",
    "get_href",
    "get_text",
    "is_likely_job_listing_page",
    "normalize_date_to_utc",
    "parse_date_string",
    "parse_html",
    "should_continue_pagination",
    "validate_selector",
    # Retry
    "RetryConfig",
    "calculate_delay",
    "is_retryable_exception",
    "is_retryable_http_error",
    "retry_with_backoff",
    # Rate limiter
    "API_DELAY_RANGE",
    "BROWSER_DELAY_RANGE",
    "HTML_DELAY_RANGE",
    "RateLimiter",
    "RateLimitConfig",
    "TokenBucket",
    "defaults_for_type",
    # Circuit breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerOpenError",
    "CircuitState",
    # HTTP client
    "HttpClient",
    "http_client",
]
