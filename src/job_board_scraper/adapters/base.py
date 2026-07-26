"""Abstract base adapter.

All company adapters inherit from ``BaseAdapter``. Defines the contract:
``fetch_jobs()`` → list of raw job dicts and typed ``ExtractionResult``.

Real implementation lands in Phase 3 (P3-01..P3-06).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    pass


class ExtractionStatus(Enum):
    """Outcome of an extraction run."""

    SUCCESS = "success"
    """All pages fetched successfully."""

    PARTIAL = "partial"
    """Some pages failed; results returned with warnings."""

    FAILED = "failed"
    """Extraction failed entirely; check ``error`` field."""


@dataclass
class ExtractionResult:
    """Typed result from adapter extraction.

    All adapters return this shape so the ETL pipeline can consume results
    uniformly regardless of the underlying scraping method (API, HTML, Browser).

    Attributes:
        jobs: Normalised adapter output. Modern adapters (e.g. OPSWAT)
            emit ``RawJobData`` Pydantic models directly; legacy adapters
            emit raw dicts which the extractor then validates. The extractor
            handles both shapes.
        status: One of ``success``, ``partial``, ``failed`` (coerced to
            ``ExtractionStatus`` regardless of whether callers pass an enum
            member or a plain string).
        warnings: Non-fatal issues encountered (e.g. skipped page, malformed item).
        error: Fatal error message when ``status`` is ``failed``.
        pages_fetched: Number of pages/requests successfully fetched.
        requests_made: Total number of HTTP requests attempted.
    """

    jobs: list[Any] = field(default_factory=list)
    status: ExtractionStatus = ExtractionStatus.SUCCESS
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    pages_fetched: int = 0
    requests_made: int = 0

    def __post_init__(self) -> None:
        """Coerce ``status`` to ``ExtractionStatus`` if a plain string slipped in.

        Adapter protocols historically constructed ``ExtractionResult(status="failed")``
        with a bare string. The dataclass accepted it because there was no validator,
        which then crashed downstream code that read ``result.status.value``.
        Normalising here makes the rest of the pipeline safe regardless of input.
        """
        if not isinstance(self.status, ExtractionStatus):
            self.status = ExtractionStatus(self.status)

    def model_dump(self) -> dict:
        """Serialize to a plain dict for logging and testing."""
        return {
            "jobs": self.jobs,
            "status": self.status.value,
            "warnings": self.warnings,
            "error": self.error,
            "pages_fetched": self.pages_fetched,
            "requests_made": self.requests_made,
        }


@runtime_checkable
class BaseAdapter(Protocol):
    """Protocol for all job scraper adapters.

    Adapters are the "plugin" layer of the ETL pipeline. Each company gets
    its own adapter implementing this protocol. The protocol is enforced at
    runtime via ``@runtime_checkable`` so broken adapters fail fast at startup.

    Attributes:
        slug: Unique identifier for this adapter (matches ``Company.slug``).
        adapter_type: One of ``"api"``, ``"html"``, ``"browser"``.
        base_url: Root URL for this company's career page or API.

    Example:
        ```python
        class OpswatAdapter:
            slug = "opswat"
            adapter_type = "api"
            base_url = "https://api.opswat.com"

            async def fetch_jobs(self) -> ExtractionResult: ...

            async def close(self) -> None: ...
        ```
    """

    slug: str
    adapter_type: str
    base_url: str

    @abstractmethod
    async def fetch_jobs(self) -> ExtractionResult:
        """Fetch all jobs from the source.

        Returns:
            An ``ExtractionResult`` containing raw job dictionaries and metadata.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release any resources held by the adapter.

        Called once when the adapter is deregistered or the application shuts down.
        Implementations should close HTTP sessions, browser contexts, or any
        other resources that require explicit cleanup.
        """
        ...


class BaseAdapterImpl(ABC):
    """Abstract base class for concrete adapter implementations.

    Unlike ``BaseAdapter`` (which is a Protocol for duck-typing), this class
    provides shared infrastructure that most adapters need. Subclasses must
    implement the abstract methods ``_get_listing_url`` and ``_parse_jobs``.

    Attributes:
        slug: Unique adapter identifier (set by subclass).
        adapter_type: Type of scraping method (set by subclass).
        base_url: Root URL for the source (set by subclass).
    """

    slug: str = ""
    adapter_type: str = ""
    base_url: str = ""

    def __init__(self) -> None:
        """Initialize the adapter."""
        if not self.slug:
            raise ValueError("Adapter must have a slug")
        if not self.adapter_type:
            raise ValueError("Adapter must have an adapter_type")
        if not self.base_url:
            raise ValueError("Adapter must have a base_url")

    @abstractmethod
    async def fetch_jobs(self) -> ExtractionResult:
        """Fetch all jobs from the source.

        Returns:
            ``ExtractionResult`` with jobs and metadata.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release resources. Override in subclasses if needed."""
        ...
