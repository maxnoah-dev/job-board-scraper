"""Unit tests for the adapter registry (adapters/registry.py).

Covers:
- AdapterRegistry singleton
- register / get / unregister
- DuplicateAdapterError and AdapterNotFoundError
- enable / disable / get_enabled
"""

from __future__ import annotations

import pytest

from job_board_scraper.adapters.base import ExtractionResult
from job_board_scraper.adapters.registry import (
    AdapterNotFoundError,
    AdapterRegistry,
    DuplicateAdapterError,
    reset_registry,
)


class DummyAdapter:
    """Minimal BaseAdapter implementation for testing."""

    def __init__(
        self,
        slug: str,
        adapter_type: str = "api",
        base_url: str = "https://example.com",
    ) -> None:
        self.slug = slug
        self.adapter_type = adapter_type
        self.base_url = base_url

    async def fetch_jobs(self) -> ExtractionResult:
        return ExtractionResult(jobs=[])

    async def close(self) -> None:
        pass


@pytest.fixture(autouse=True)
def clean_registry() -> None:
    """Reset the registry before each test."""
    reset_registry()
    yield
    reset_registry()


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TestAdapterRegistryErrors:
    """AdapterNotFoundError and DuplicateAdapterError carry useful context."""

    def test_not_found_error_contains_slug(self) -> None:
        error = AdapterNotFoundError("missing-slug")
        assert "missing-slug" in str(error)
        assert error.slug == "missing-slug"

    def test_duplicate_error_contains_slug(self) -> None:
        error = DuplicateAdapterError("duplicate-slug")
        assert "duplicate-slug" in str(error)
        assert error.slug == "duplicate-slug"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestAdapterRegistrySingleton:
    """get_instance returns the same object on repeated calls."""

    def test_reset_clears_singleton(self) -> None:
        """reset_registry clears the singleton instance."""
        r1 = AdapterRegistry.get_instance()
        reset_registry()
        r2 = AdapterRegistry.get_instance()
        assert r1 is not r2


# ---------------------------------------------------------------------------
# register / get
# ---------------------------------------------------------------------------


class TestAdapterRegistryRegister:
    """Adapters are registered and retrieved by slug."""

    def test_register_inserts_adapter(self) -> None:
        registry = AdapterRegistry.get_instance()
        adapter = DummyAdapter("greenhouse", "api")
        registry.register(adapter)
        assert "greenhouse" in registry

    def test_get_returns_registered_adapter(self) -> None:
        registry = AdapterRegistry.get_instance()
        adapter = DummyAdapter("greenhouse")
        registry.register(adapter)
        retrieved = registry.get("greenhouse")
        assert retrieved is adapter

    def test_get_raises_on_missing(self) -> None:
        registry = AdapterRegistry.get_instance()
        with pytest.raises(AdapterNotFoundError) as exc_info:
            registry.get("nonexistent")
        assert exc_info.value.slug == "nonexistent"

    def test_get_or_none_returns_none_for_missing(self) -> None:
        registry = AdapterRegistry.get_instance()
        result = registry.get_or_none("nonexistent")
        assert result is None

    def test_duplicate_registration_raises(self) -> None:
        registry = AdapterRegistry.get_instance()
        adapter = DummyAdapter("greenhouse")
        registry.register(adapter)
        with pytest.raises(DuplicateAdapterError):
            registry.register(adapter)

    def test_unregister_removes_adapter(self) -> None:
        registry = AdapterRegistry.get_instance()
        adapter = DummyAdapter("greenhouse")
        registry.register(adapter)
        registry.unregister("greenhouse")
        assert "greenhouse" not in registry

    def test_unregister_raises_on_missing(self) -> None:
        registry = AdapterRegistry.get_instance()
        with pytest.raises(AdapterNotFoundError):
            registry.unregister("nonexistent")


# ---------------------------------------------------------------------------
# list / enable / disable
# ---------------------------------------------------------------------------


class TestAdapterRegistryEnableDisable:
    """Adapters can be enabled and disabled independently of registration."""

    def test_enabled_by_default(self) -> None:
        registry = AdapterRegistry.get_instance()
        adapter = DummyAdapter("greenhouse")
        registry.register(adapter)
        assert registry.get_enabled() == [adapter]

    def test_disable_removes_from_enabled(self) -> None:
        registry = AdapterRegistry.get_instance()
        adapter = DummyAdapter("greenhouse")
        registry.register(adapter)
        registry.disable("greenhouse")
        assert registry.get_enabled() == []

    def test_enable_reenables_adapter(self) -> None:
        registry = AdapterRegistry.get_instance()
        adapter = DummyAdapter("greenhouse")
        registry.register(adapter, enabled=False)
        assert registry.get_enabled() == []
        registry.enable("greenhouse")
        assert registry.get_enabled() == [adapter]

    def test_enable_raises_on_missing(self) -> None:
        registry = AdapterRegistry.get_instance()
        with pytest.raises(AdapterNotFoundError):
            registry.enable("nonexistent")

    def test_disable_raises_on_missing(self) -> None:
        registry = AdapterRegistry.get_instance()
        with pytest.raises(AdapterNotFoundError):
            registry.disable("nonexistent")

    def test_get_enabled_returns_in_slug_order(self) -> None:
        registry = AdapterRegistry.get_instance()
        registry.register(DummyAdapter("zebra"))
        registry.register(DummyAdapter("apple"))
        registry.register(DummyAdapter("mango"))
        enabled_slugs = [a.slug for a in registry.get_enabled()]
        assert enabled_slugs == ["apple", "mango", "zebra"]

    def test_list_adapters_returns_sorted_slugs(self) -> None:
        registry = AdapterRegistry.get_instance()
        registry.register(DummyAdapter("zebra"))
        registry.register(DummyAdapter("apple"))
        slugs = registry.list_adapters()
        assert slugs == ["apple", "zebra"]


# ---------------------------------------------------------------------------
# Iteration
# ---------------------------------------------------------------------------


class TestAdapterRegistryIteration:
    """Registry can be iterated over (slug, adapter) pairs."""

    def test_iter_returns_sorted_items(self) -> None:
        registry = AdapterRegistry.get_instance()
        registry.register(DummyAdapter("zebra"))
        registry.register(DummyAdapter("apple"))
        items = list(registry)
        slugs = [slug for slug, _ in items]
        assert slugs == ["apple", "zebra"]

    def test_len_returns_count(self) -> None:
        registry = AdapterRegistry.get_instance()
        assert len(registry) == 0
        registry.register(DummyAdapter("a"))
        assert len(registry) == 1
        registry.register(DummyAdapter("b"))
        assert len(registry) == 2

    def test_clear_removes_all(self) -> None:
        registry = AdapterRegistry.get_instance()
        registry.register(DummyAdapter("a"))
        registry.register(DummyAdapter("b"))
        registry.clear()
        assert len(registry) == 0
        assert registry.list_adapters() == []
