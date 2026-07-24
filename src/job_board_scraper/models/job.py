"""Job domain model.

Pydantic v2 schema for a normalized job record and its raw source variant.
Includes URL canonicalization, date parsing, and status validation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# JobStatus enum
# ---------------------------------------------------------------------------

# Alias sets defined outside enum to avoid being treated as enum members
_OPEN_ALIASES = frozenset({"open", "active", "live"})
_CLOSED_ALIASES = frozenset({"closed", "inactive", "expired", "filled"})
_UNKNOWN_ALIASES = frozenset({"unknown", "n/a", "na", "null"})


class JobStatus(str, Enum):
    """Job lifecycle enum with case-insensitive alias support.

    Common synonyms normalize to one of these three values:
    - open  / active / live / OPEN / Open
    - closed / inactive / expired / filled / CLOSED
    - unknown / UNKNOWN / n/a / na / null
    """

    open = "open"
    closed = "closed"
    unknown = "unknown"

    @classmethod
    def _missing_(cls, value: str) -> JobStatus | None:
        normalized = value.lower().strip()
        if normalized in _OPEN_ALIASES:
            return cls.open
        if normalized in _CLOSED_ALIASES:
            return cls.closed
        if normalized in _UNKNOWN_ALIASES:
            return cls.unknown
        return None


# ---------------------------------------------------------------------------
# URL canonicalization (ADR-0003 rules)
# ---------------------------------------------------------------------------

# Tracking parameters to strip per ADR-0003
_TRACKING_PARAMS = frozenset(
    {
        # UTM parameters
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        # Other tracking
        "ref",
        "fbclid",
        "gclid",
        "msclkid",
        "_ga",
        "mc_cid",
        "oly_enc_id",
        "vero_id",
        "wickedid",
        # Social shares
        "share_source",
        "share_medium",
        "share_campaign",
    }
)

# Default ports to strip
_DEFAULT_PORTS = {
    "https": "443",
    "http": "80",
}


def canonicalize_url(url: str) -> str:
    """Canonicalize a job URL per ADR-0003.

    Rules applied in order:
    1. Lowercase scheme and host
    2. Strip default port (:443 for https, :80 for http)
    3. Strip fragment
    4. Strip UTM / tracking parameters (utm_*, ref, fbclid, gclid, etc.)
    5. Sort remaining query parameters alphabetically
    6. Strip trailing slash on non-root paths
    7. Fail on invalid/missing scheme (no-op URLs rejected)

    The function is:
    - Pure: no side effects
    - Deterministic: same input always produces same output
    - Idempotent: canonicalize(canonicalize(x)) == canonicalize(x)
    """
    if not url or not url.strip():
        raise ValueError("URL cannot be empty")

    url = url.strip()

    parsed = urlparse(url)

    # Reject URLs without scheme or netloc
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL: {url!r}")

    # Lowercase scheme and host
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Strip default port
    host_port = netloc
    if ":" in host_port:
        host, port = host_port.rsplit(":", 1)
        default_port = _DEFAULT_PORTS.get(scheme)
        if default_port and port == default_port:
            netloc = host
        else:
            netloc = f"{host}:{port}"
    else:
        netloc = host_port

    # Strip fragment
    path = parsed.path
    query = parsed.query

    # Build base URL without fragment
    result = urljoin(f"{scheme}://{netloc}", path)

    # Strip tracking parameters from query
    if query:
        params = parse_qsl(query, keep_blank_values=True)
        filtered = [(k, v) for k, v in params if k.lower() not in _TRACKING_PARAMS]
        # Sort alphabetically by key
        filtered_sorted = sorted(filtered, key=lambda x: x[0])
        if filtered_sorted:
            query = urlencode(filtered_sorted)
            result = f"{result}?{query}"

    # Strip trailing slash on non-root paths
    if result != f"{scheme}://{netloc}" and result.endswith("/"):
        result = result.rstrip("/")

    return result


# ---------------------------------------------------------------------------
# RawJobData — adapter-emitted shape (before transformation)
# ---------------------------------------------------------------------------


class RawJobData(BaseModel):
    """Unstructured payload emitted by an adapter before transformation.

    Adapters extract raw data from their source and emit RawJobData.
    This model is intentionally flexible: extra fields are allowed via
    ``raw_data`` JSON field. URL validation is strict to fail fast on bad data.

    Required fields: source_company_id, title, url
    Optional fields: source_job_id, location, date_posted, raw_data
    """

    model_config = ConfigDict(
        extra="allow",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    source_company_id: str = Field(
        ...,
        description="Company slug (e.g., 'opswat', 'vancity')",
        min_length=1,
    )
    title: str = Field(
        ...,
        description="Job title from source",
        min_length=1,
    )
    url: str = Field(
        ...,
        description="Raw source URL (may contain tracking params)",
        min_length=1,
    )
    location: str | None = Field(
        default="Remote",
        description="Job location (defaults to 'Remote' if not specified)",
    )
    source_job_id: str | None = Field(
        default=None,
        description="Source system job ID (e.g., Greenhouse job ID)",
    )
    date_posted: str | datetime | None = Field(
        default=None,
        description="Date posted in source format (ISO 8601 preferred)",
    )
    raw_data: dict[str, Any] | None = Field(
        default=None,
        description="Additional raw fields from source as JSON",
    )

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title_whitespace(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("url", mode="before")
    @classmethod
    def _validate_url_format(cls, v: str) -> str:
        if isinstance(v, str):
            v = v.strip()
        parsed = urlparse(v)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL format: {v!r}")
        return v


# ---------------------------------------------------------------------------
# JobRecord — normalized post-transformer shape (stored in DB)
# ---------------------------------------------------------------------------


class JobRecord(BaseModel):
    """Normalized job record stored in the database after transformation.

    This is the canonical form: all source-specific quirks have been resolved.
    URL is canonicalized, dates are UTC, status is normalized.

    Required fields: company_id, title, url, canonical_url
    Optional fields: location, date_posted, source_job_id, status, raw_data
    """

    model_config = ConfigDict(
        validate_assignment=True,
        use_enum_values=False,
    )

    id: int | None = Field(
        default=None,
        description="Primary key (None before insert)",
    )
    company_id: int = Field(
        ...,
        description="FK to companies table",
        gt=0,
    )
    title: str = Field(
        ...,
        description="Canonical job title",
        min_length=1,
    )
    location: str = Field(
        default="Remote",
        description="Job location (defaults to 'Remote')",
    )
    url: str = Field(
        ...,
        description="Original source URL (may contain tracking params)",
        min_length=1,
    )
    canonical_url: str = Field(
        ...,
        description="Canonical URL for deduping (ADR-0003)",
        min_length=1,
    )
    date_posted: datetime | None = Field(
        default=None,
        description="Date posted in UTC (None if unknown)",
    )
    status: JobStatus = Field(
        default=JobStatus.open,
        description="Job status (defaults to open)",
    )
    source_job_id: str | None = Field(
        default=None,
        description="Source system job ID",
    )
    raw_data: dict[str, Any] | None = Field(
        default=None,
        description="Full raw data as JSON for debugging",
    )

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title_whitespace(cls, v: str) -> str:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("Title cannot be empty or whitespace-only")
            return stripped
        return v

    @field_validator("canonical_url", mode="before")
    @classmethod
    def _validate_canonical_url(cls, v: str) -> str:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("canonical_url cannot be empty")
        return v

    @field_validator("date_posted", mode="before")
    @classmethod
    def _parse_date_to_utc(cls, v: str | datetime | None) -> datetime | None:
        if v is None:
            return None

        if isinstance(v, datetime):
            # Reject naive datetimes per ADR-0005
            if v.tzinfo is None:
                raise ValueError(
                    "Naive datetime rejected. All timestamps must be UTC-aware. "
                    f"Got: {v!r}. Use datetime.now(timezone.utc) or add timezone info."
                )
            # Normalize to UTC
            return v.astimezone(UTC)

        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None

            # Try ISO 8601 with timezone first
            for fmt in (
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%S+00:00",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    parsed = datetime.strptime(v, fmt)
                    if parsed.tzinfo is None:
                        # Assume UTC if no timezone info
                        parsed = parsed.replace(tzinfo=UTC)
                    else:
                        parsed = parsed.astimezone(UTC)
                    return parsed
                except ValueError:
                    continue

            # Try ISO format with fromisoformat (handles various offsets)
            try:
                parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                else:
                    parsed = parsed.astimezone(UTC)
                return parsed
            except ValueError:
                pass

            raise ValueError(f"Cannot parse date string: {v!r}")

        raise ValueError(f"date_posted must be str or datetime, got {type(v).__name__}")

    @model_validator(mode="after")
    def _validate_url_consistency(self) -> JobRecord:
        """Ensure url and canonical_url are both valid and consistent."""
        for field_name, url_val in [
            ("url", self.url),
            ("canonical_url", self.canonical_url),
        ]:
            parsed = urlparse(url_val)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"Invalid {field_name}: {url_val!r}")
        return self
