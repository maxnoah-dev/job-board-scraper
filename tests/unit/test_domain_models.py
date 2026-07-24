"""P2-01 — Domain model RED tests for ``JobRecord`` and ``RawJobData``.

These tests define the Pydantic contract for normalized job records before
implementation lands. They follow:

- **PLAN.md §2.A** — required normalized fields: ``company_name``, ``title``,
  ``location``, ``job_url``, optional ``date_posted``, status.
- **ADR-0003** — canonical URL rules: lowercase host, drop default port, drop
  fragment, drop UTM / tracking parameters, sort remaining query keys, strip
  trailing slash.
- **ADR-0005** — all timestamps stored in UTC; Pydantic models reject naive
  datetimes.

Each test class is grouped by behaviour. Tests must FAIL until P2-02 implements
the model. Failures for these tests must be ``ImportError`` (module has no
symbols yet) or ``ValidationError`` (model raises), **never** AttributeError on
existing symbols — that would mean we wrote the wrong API surface.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def valid_raw_payload() -> dict:
    """A typical adapter-emitted payload for an HTML/API source."""
    return {
        "source_company_id": "opswat",
        "source_job_id": "REQ-12345",
        "title": "Senior Backend Engineer",
        "location": "Ho Chi Minh City, Vietnam",
        "url": "https://jobs.opswat.com/job/senior-backend-engineer?ref=linkedin&utm_source=share",
        "date_posted": "2026-07-15T10:30:00+07:00",
        "raw_data": {"department": "Engineering", "employment_type": "Full-time"},
    }


# ---------------------------------------------------------------------------
# JobStatus enum
# ---------------------------------------------------------------------------


class TestJobStatus:
    """``JobStatus`` is the lifecycle enum: ``open`` | ``closed`` | ``unknown``."""

    def test_module_exposes_job_status_symbol(self) -> None:
        from job_board_scraper.models.job import JobStatus

        assert JobStatus is not None

    def test_status_has_open_value(self) -> None:
        from job_board_scraper.models.job import JobStatus

        assert hasattr(JobStatus, "open")
        assert JobStatus.open.value == "open"

    def test_status_has_closed_value(self) -> None:
        from job_board_scraper.models.job import JobStatus

        assert hasattr(JobStatus, "closed")
        assert JobStatus.closed.value == "closed"

    def test_status_has_unknown_value(self) -> None:
        from job_board_scraper.models.job import JobStatus

        assert hasattr(JobStatus, "unknown")
        assert JobStatus.unknown.value == "unknown"

    def test_status_count_is_three(self) -> None:
        """Open / Closed / Unknown — no more, no less."""
        from job_board_scraper.models.job import JobStatus

        members = list(JobStatus)
        assert len(members) == 3, (
            f"expected 3 statuses, got: {[m.name for m in members]}"
        )

    def test_normalising_aliases(self) -> None:
        """``JobStatus("OPEN")`` and ``JobStatus("active")`` should map to ``open``."""
        from job_board_scraper.models.job import JobStatus

        # Common synonyms must map deterministically.
        for alias in ("open", "OPEN", "active", "live"):
            assert JobStatus(alias) is JobStatus.open  # type: ignore[arg-type]

        for alias in ("closed", "CLOSED", "inactive", "expired", "filled"):
            assert JobStatus(alias) is JobStatus.closed  # type: ignore[arg-type]

        for alias in ("unknown", "UNKNOWN", "n/a", "na", "null"):
            assert JobStatus(alias) is JobStatus.unknown  # type: ignore[arg-type]

    def test_status_rejects_unknown_string(self) -> None:
        """Strings outside the vocab must raise ``ValueError``."""
        from job_board_scraper.models.job import JobStatus

        with pytest.raises(ValueError):
            JobStatus("banana")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RawJobData — adapter-emitted shape
# ---------------------------------------------------------------------------


class TestRawJobData:
    """``RawJobData`` is the adapter-emitted payload before transformer runs."""

    def test_module_exposes_raw_job_data_class(self) -> None:
        from job_board_scraper.models.job import RawJobData

        assert RawJobData is not None

    def test_construction_with_valid_payload(self, valid_raw_payload: dict) -> None:
        from job_board_scraper.models.job import RawJobData

        record = RawJobData(**valid_raw_payload)
        assert record.title == "Senior Backend Engineer"
        assert record.location == "Ho Chi Minh City, Vietnam"
        assert record.url.startswith("https://jobs.opswat.com/")
        # Raw data layer: canonical_url MUST NOT exist on RawJobData
        assert not hasattr(record, "canonical_url")

    def test_url_is_required(self) -> None:
        """Missing ``url`` is a hard adapter error, not a 'fix later' case."""
        from job_board_scraper.models.job import RawJobData

        with pytest.raises(Exception):
            RawJobData(source_company_id="x", title="t", location="l")  # no url

    def test_title_is_required(self) -> None:
        """Empty title must be rejected."""
        from job_board_scraper.models.job import RawJobData

        with pytest.raises(Exception):
            RawJobData(
                source_company_id="x",
                title="",
                location="l",
                url="https://example.com/jobs/1",
            )

    def test_location_default_is_remote_or_unknown(self) -> None:
        """Missing location defaults to a non-empty placeholder, never ``None``."""
        from job_board_scraper.models.job import RawJobData

        record = RawJobData(
            source_company_id="opswat",
            title="Engineer",
            url="https://jobs.opswat.com/job/abc",
        )
        assert record.location, "location must default to a non-empty placeholder"
        assert isinstance(record.location, str)

    def test_optional_fields_default_safely(self) -> None:
        """Adapter may omit ``date_posted``, ``source_job_id``, ``raw_data``."""
        from job_board_scraper.models.job import RawJobData

        record = RawJobData(
            source_company_id="opswat",
            title="Engineer",
            url="https://jobs.opswat.com/job/abc",
        )
        # date_posted may be None or some sentinel; either way must NOT raise.
        assert record.title == "Engineer"
        # No crash on .model_dump()
        dumped = record.model_dump()
        assert "url" in dumped


# ---------------------------------------------------------------------------
# JobRecord — normalized post-transformer shape
# ---------------------------------------------------------------------------


class TestJobRecord:
    """``JobRecord`` is the canonical job stored in the DB after transformer runs."""

    def test_module_exposes_job_record_class(self) -> None:
        from job_board_scraper.models.job import JobRecord

        assert JobRecord is not None

    def test_canonical_url_field_is_required(self) -> None:
        """``JobRecord`` has ``canonical_url`` (validated, distinct from raw)."""
        from job_board_scraper.models.job import JobRecord

        assert "canonical_url" in JobRecord.model_fields

    def test_company_id_is_required(self) -> None:
        """No ``JobRecord`` without ``company_id`` (FK to companies table)."""
        from job_board_scraper.models.job import JobRecord

        with pytest.raises(Exception):
            JobRecord(
                title="t",
                location="l",
                url="https://example.com/jobs/1",
            )

    def test_title_is_required(self) -> None:
        """Whitespace-only titles are rejected."""
        from job_board_scraper.models.job import JobRecord

        with pytest.raises(Exception):
            JobRecord(
                company_id=1,
                title="   ",
                location="l",
                url="https://example.com/jobs/1",
            )

    def test_canonical_url_cannot_be_empty(self) -> None:
        """``canonical_url`` must be non-empty."""
        from job_board_scraper.models.job import JobRecord

        with pytest.raises(Exception):
            JobRecord(
                company_id=1,
                title="t",
                location="l",
                url="https://example.com/jobs/1",
                canonical_url="",
            )

    def test_status_defaults_to_open(self) -> None:
        """Default status is ``open`` (matches PLAN §2.A)."""
        from job_board_scraper.models.job import JobRecord, JobStatus

        record = JobRecord(
            company_id=1,
            title="Engineer",
            location="Remote",
            url="https://example.com/jobs/1",
            canonical_url="https://example.com/jobs/1",
        )
        assert record.status is JobStatus.open

    def test_date_posted_is_normalised_to_utc(self) -> None:
        """Per ADR-0005: even if a +07:00 date arrives, stored value is UTC."""
        from job_board_scraper.models.job import JobRecord

        record = JobRecord(
            company_id=1,
            title="t",
            location="l",
            url="https://example.com/jobs/1",
            canonical_url="https://example.com/jobs/1",
            date_posted="2026-07-15T10:30:00+07:00",
        )
        assert record.date_posted.tzinfo is not None
        # tzinfo must be UTC after normalization
        assert record.date_posted.utcoffset().total_seconds() == 0
        # 10:30 +07:00 == 03:30 UTC
        assert record.date_posted.hour == 3
        assert record.date_posted.minute == 30
        assert record.date_posted.year == 2026
        assert record.date_posted.month == 7
        assert record.date_posted.day == 15

    def test_naive_datetime_is_rejected(self) -> None:
        """Per ADR-0005: naive datetimes are an error, not silent UTC assumption."""
        from pydantic import ValidationError

        from job_board_scraper.models.job import JobRecord

        naive = datetime(2026, 7, 15, 10, 30, 0)
        with pytest.raises(ValidationError):
            JobRecord(
                company_id=1,
                title="t",
                location="l",
                url="https://example.com/jobs/1",
                canonical_url="https://example.com/jobs/1",
                date_posted=naive,  # type: ignore[arg-type]
            )

    def test_iso_string_with_utc_offset_accepted(self) -> None:
        """The most common adapter format: ISO string with explicit offset."""
        from job_board_scraper.models.job import JobRecord

        record = JobRecord(
            company_id=1,
            title="t",
            location="l",
            url="https://example.com/jobs/1",
            canonical_url="https://example.com/jobs/1",
            date_posted="2026-07-15T10:30:00Z",
        )
        assert record.date_posted.tzinfo is not None

    def test_garbage_date_string_is_rejected(self) -> None:
        """``date_posted = "yesterday"`` is rejected."""
        from job_board_scraper.models.job import JobRecord

        with pytest.raises(Exception):
            JobRecord(
                company_id=1,
                title="t",
                location="l",
                url="https://example.com/jobs/1",
                canonical_url="https://example.com/jobs/1",
                date_posted="yesterday",
            )


# ---------------------------------------------------------------------------
# canonicalize_url — ADR-0003 rules
# ---------------------------------------------------------------------------


class TestCanonicalUrl:
    """``canonicalize_url`` enforces ADR-0003 rules.

    Tests below are the authoritative behaviour reference; the canonicalizer
    must obey every bullet — see ADR-0003 "Decision" section.
    """

    def test_function_exists(self) -> None:
        from job_board_scraper.models.job import canonicalize_url

        assert canonicalize_url is not None

    def test_lowercase_host(self) -> None:
        from job_board_scraper.models.job import canonicalize_url

        out = canonicalize_url("HTTPS://Jobs.Opswat.com/Job/1")
        assert out.startswith("https://jobs.opswat.com/")

    def test_strip_default_https_port(self) -> None:
        from job_board_scraper.models.job import canonicalize_url

        assert canonicalize_url("https://example.com:443/x") == "https://example.com/x"

    def test_strip_default_http_port(self) -> None:
        from job_board_scraper.models.job import canonicalize_url

        assert canonicalize_url("http://example.com:80/x") == "http://example.com/x"

    def test_keeps_non_default_port(self) -> None:
        from job_board_scraper.models.job import canonicalize_url

        assert (
            canonicalize_url("https://example.com:8443/x")
            == "https://example.com:8443/x"
        )

    def test_strip_fragment(self) -> None:
        from job_board_scraper.models.job import canonicalize_url

        out = canonicalize_url("https://example.com/x#about")
        assert "#" not in out
        assert out == "https://example.com/x"

    def test_strip_tracking_query(self) -> None:
        from job_board_scraper.models.job import canonicalize_url

        # ADR-0003 specifies UTM, ref, fbclid, gclid as tracking to drop
        out = canonicalize_url(
            "https://example.com/x?utm_source=li&utm_medium=social&ref=hi&fbclid=abc&gclid=xyz&keep=1",
        )
        assert "utm_source" not in out
        assert "utm_medium" not in out
        assert "ref=hi" not in out
        assert "fbclid=" not in out
        assert "gclid=" not in out
        assert "keep=1" in out

    def test_sorted_remaining_query(self) -> None:
        """Remaining query keys are sorted by name for cross-run determinism."""
        from job_board_scraper.models.job import canonicalize_url

        a = canonicalize_url("https://example.com/x?z=1&a=2&m=3")
        b = canonicalize_url("https://example.com/x?a=2&m=3&z=1")
        assert a == b
        assert a == "https://example.com/x?a=2&m=3&z=1"

    def test_strip_trailing_slash_on_path(self) -> None:
        from job_board_scraper.models.job import canonicalize_url

        assert canonicalize_url("https://example.com/x/") == "https://example.com/x"

    def test_keep_root_path_trailing_slash(self) -> None:
        """``https://example.com/`` keeps the slash for root."""
        from job_board_scraper.models.job import canonicalize_url

        # We canonicalize ``/`` as root. Apache/Nginx treat both the same,
        # so either representation is OK; we pick the bare host.
        assert canonicalize_url("https://example.com/") in {
            "https://example.com",
            "https://example.com/",
        }

    def test_idempotent(self) -> None:
        """canonicalize(canonicalize(x)) == canonicalize(x)."""
        from job_board_scraper.models.job import canonicalize_url

        url = "HTTPS://Jobs.Opswat.com/Job/1?utm_source=x&a=2#frag"
        once = canonicalize_url(url)
        twice = canonicalize_url(once)
        assert once == twice

    def test_real_world_utm_disambiguation(self) -> None:
        """Two social shares of the same job produce identical canonical URLs."""
        from job_board_scraper.models.job import canonicalize_url

        linkedin = (
            "https://jobs.opswat.com/job/senior-engineer?utm_source=linkedin&fbclid=abc"
        )
        twitter = (
            "https://jobs.opswat.com/job/senior-engineer?utm_source=twitter&gclid=xyz"
        )
        assert canonicalize_url(linkedin) == canonicalize_url(twitter)
        # And the canonical version has no tracking params.
        canon = canonicalize_url(linkedin)
        assert "utm_" not in canon
        assert "fbclid" not in canon
        assert "gclid" not in canon

    def test_rejects_invalid_url(self) -> None:
        """Non-URL strings raise ``ValueError`` (or pydantic ``ValidationError``)."""
        from job_board_scraper.models.job import canonicalize_url

        with pytest.raises(Exception):
            canonicalize_url("not a url at all")

    def test_rejects_empty_url(self) -> None:
        from job_board_scraper.models.job import canonicalize_url

        with pytest.raises(Exception):
            canonicalize_url("")


# ---------------------------------------------------------------------------
# Malformed payloads — adapter did something stupid
# ---------------------------------------------------------------------------


class TestMalformedPayloads:
    """The transformer must fail closed on impossible input.

    Per PLAN §2.A: required fields are ``title`` / ``location`` / ``job_url``.
    Adapters that produce garbage must be visible — silent defaults hide bugs.
    """

    def test_raw_job_data_rejects_non_dict_input(self) -> None:
        from job_board_scraper.models.job import RawJobData

        with pytest.raises(Exception):
            RawJobData.model_validate([1, 2, 3])  # not a dict

    def test_raw_job_data_strips_whitespace_in_title(self) -> None:
        """Leading/trailing whitespace stripped so dedupe keys are stable."""
        from job_board_scraper.models.job import RawJobData

        record = RawJobData(
            source_company_id="opswat",
            title="  Senior Engineer  ",
            location="HCMC",
            url="https://jobs.opswat.com/job/abc",
        )
        assert record.title == "Senior Engineer"

    def test_job_record_rejects_non_url_in_url_field(self) -> None:
        from job_board_scraper.models.job import JobRecord

        with pytest.raises(Exception):
            JobRecord(
                company_id=1,
                title="t",
                location="l",
                url="https://",
                canonical_url="https://example.com/x",
            )

    def test_job_record_distinguishes_url_and_canonical_url(self) -> None:
        """``url`` preserves raw source URL; ``canonical_url`` is the dedupe key."""
        from job_board_scraper.models.job import JobRecord

        record = JobRecord(
            company_id=1,
            title="t",
            location="l",
            url="https://Example.com:443/X/?utm_source=x#frag",
            canonical_url="https://example.com/x",
        )
        assert record.url.startswith("https://Example.com")
        assert record.canonical_url == "https://example.com/x"

    def test_unknown_extra_fields_ignored_in_raw_data(self) -> None:
        """``raw_data`` (JSON) accepts arbitrary extra fields."""
        from job_board_scraper.models.job import RawJobData

        record = RawJobData(
            source_company_id="x",
            title="t",
            location="l",
            url="https://example.com/x",
            raw_data={"salary_range": "$100k", "level": "L5", "extra_noise": [1, 2, 3]},
        )
        assert record.raw_data["level"] == "L5"
