"""Browser automation adapter protocol.

Concrete adapter base for sources that require headless browser
automation to render client-side JavaScript or to bypass anti-bot
challenges. Per ADR-0007 this is constrained to loading only public
pages that the source serves to unauthenticated visitors.

Real implementation lands in Phase 7 (P7-01..P7-05).
"""

from __future__ import annotations
