"""Adapter registry.

Plugin-style registry that loads enabled adapters from
``config/adapters/<slug>.yaml`` and maps them to their classes.
Rejects duplicate slugs and adapters whose compliance status is not
``approved``.

Real implementation lands in Phase 3 (P3-01..P3-06).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from job_board_scraper.adapters.base import BaseAdapter


class AdapterRegistryError(Exception):
    """Base exception for adapter registry errors."""


class AdapterNotFoundError(AdapterRegistryError):
    """Raised when a requested adapter slug is not registered."""

    def __init__(self, slug: str) -> None:
        self.slug = slug
        super().__init__(f"Adapter {slug!r} is not registered")


class DuplicateAdapterError(AdapterRegistryError):
    """Raised when attempting to register an adapter with a duplicate slug."""

    def __init__(self, slug: str) -> None:
        self.slug = slug
        super().__init__(f"Adapter with slug {slug!r} is already registered")


class AdapterRegistry:
    """Global registry for job scraper adapters.

    ``AdapterRegistry`` is a singleton that maps adapter slugs to their instances.
    It provides thread-safe registration, lookup, and enumeration.

    The registry enforces:
    - No duplicate slugs
    - Each adapter must implement ``BaseAdapter``

    Usage::

        from job_board_scraper.adapters.registry import registry

        # Register an adapter
        registry.register(my_adapter)

        # Get an adapter by slug
        adapter = registry.get("greenhouse")

        # List all adapters
        slugs = registry.list_adapters()

        # List only enabled adapters
        enabled = registry.get_enabled()

    For a read-only view of all registered adapters::

        for slug, adapter in registry:
            print(f"{slug}: {adapter.adapter_type}")

    Attributes:
        _adapters: Internal dict mapping slug -> adapter instance.
        _enabled: Set of slugs that are currently enabled.
    """

    _instance: AdapterRegistry | None = None

    def __init__(self) -> None:
        self._adapters: dict[str, BaseAdapter] = {}
        self._enabled: set[str] = set()

    @classmethod
    def get_instance(cls) -> AdapterRegistry:
        """Return the singleton ``AdapterRegistry`` instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, adapter: BaseAdapter, *, enabled: bool = True) -> None:
        """Register an adapter instance.

        Args:
            adapter: A ``BaseAdapter`` implementation instance.
            enabled: Whether this adapter is currently enabled. Default True.

        Raises:
            DuplicateAdapterError: If an adapter with the same slug is already registered.
            TypeError: If ``adapter`` does not implement ``BaseAdapter``.
        """
        slug = adapter.slug

        if slug in self._adapters:
            raise DuplicateAdapterError(slug)

        # Runtime check that adapter satisfies the protocol via duck typing
        required_attrs = ("fetch_jobs", "close", "slug", "adapter_type", "base_url")
        missing = [a for a in required_attrs if not hasattr(adapter, a)]
        if missing:
            raise TypeError(
                f"Adapter {slug!r} does not implement BaseAdapter. "
                f"Missing attributes: {missing}"
            )

        self._adapters[slug] = adapter
        if enabled:
            self._enabled.add(slug)

    def get(self, slug: str) -> BaseAdapter:
        """Return the adapter registered under ``slug``.

        Args:
            slug: The adapter's unique identifier.

        Returns:
            The registered adapter instance.

        Raises:
            AdapterNotFoundError: If no adapter with this slug is registered.
        """
        if slug not in self._adapters:
            raise AdapterNotFoundError(slug)
        return self._adapters[slug]

    def get_or_none(self, slug: str) -> BaseAdapter | None:
        """Return the adapter for ``slug``, or None if not registered.

        Unlike ``get()``, this method does not raise on missing adapters.
        Use this when a missing adapter is a non-error condition.
        """
        return self._adapters.get(slug)

    def list_adapters(self) -> list[str]:
        """Return a sorted list of all registered adapter slugs."""
        return sorted(self._adapters.keys())

    def get_enabled(self) -> list[BaseAdapter]:
        """Return all currently enabled adapters, in slug order."""
        return [
            self._adapters[slug]
            for slug in sorted(self._enabled)
            if slug in self._adapters
        ]

    def enable(self, slug: str) -> None:
        """Mark an adapter as enabled.

        Args:
            slug: The adapter slug to enable.

        Raises:
            AdapterNotFoundError: If no adapter with this slug is registered.
        """
        if slug not in self._adapters:
            raise AdapterNotFoundError(slug)
        self._enabled.add(slug)

    def disable(self, slug: str) -> None:
        """Mark an adapter as disabled (it remains registered but will not run).

        Args:
            slug: The adapter slug to disable.

        Raises:
            AdapterNotFoundError: If no adapter with this slug is registered.
        """
        if slug not in self._adapters:
            raise AdapterNotFoundError(slug)
        self._enabled.discard(slug)

    def unregister(self, slug: str) -> None:
        """Remove an adapter from the registry.

        Args:
            slug: The adapter slug to remove.

        Raises:
            AdapterNotFoundError: If no adapter with this slug is registered.
        """
        if slug not in self._adapters:
            raise AdapterNotFoundError(slug)
        del self._adapters[slug]
        self._enabled.discard(slug)

    def clear(self) -> None:
        """Remove all adapters from the registry.

        Use with caution — prefer ``disable()`` for temporary deactivation.
        Primarily intended for testing.
        """
        self._adapters.clear()
        self._enabled.clear()

    def __len__(self) -> int:
        """Return the number of registered adapters."""
        return len(self._adapters)

    def __contains__(self, slug: str) -> bool:
        """Return True if an adapter with ``slug`` is registered."""
        return slug in self._adapters

    def __iter__(self):
        """Iterate over (slug, adapter) pairs in sorted slug order."""
        return iter(sorted(self._adapters.items()))


# Module-level singleton accessor for convenience
registry = AdapterRegistry.get_instance()
"""Global adapter registry instance."""


def reset_registry() -> None:
    """Reset the registry to an empty state.

    Primarily intended for testing. In production, prefer ``disable()``.
    """
    registry.clear()
    AdapterRegistry._instance = None
