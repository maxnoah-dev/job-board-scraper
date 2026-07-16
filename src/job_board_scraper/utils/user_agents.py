"""User-agent rotation.

Pool of realistic browser User-Agent strings and a round-robin
picker that avoids repeating the same UA on consecutive requests
to the same host.

Real implementation lands in Phase 3.
"""

from __future__ import annotations
