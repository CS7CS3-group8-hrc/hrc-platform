"""Same scenario + seed => identical event sequence (CLAUDE.md 4.1, 10)."""

import pytest

pytestmark = pytest.mark.skip(reason="TODO milestone 3 (extend after 4 and 8)")


def test_same_seed_same_events() -> None:
    """Build two engines with fresh InMemorySinks, load baseline, step 60 sim minutes each.
    Compare [e.model_dump(mode='json') for e in sink.events] for both sinks: identical
    (UUIDs too, since they come from the seeded RNG)."""


def test_different_seed_different_events() -> None:
    """Sanity check: seed 43 produces a different ADT sequence."""
