from __future__ import annotations

from underprice.cache.estimate_cache import EstimateCache
from underprice.models import Candidate, Confidence, ScoreResult


class FakeSharedDict(dict):
    """Minimal Modal Dict stand-in."""

    def pop(self, key, default=None):  # noqa: ANN001
        return super().pop(key, default)


def test_shared_cache_roundtrip() -> None:
    shared: FakeSharedDict = FakeSharedDict()
    a = EstimateCache(ttl_days=14, shared=shared)
    b = EstimateCache(ttl_days=14, shared=shared)

    result = ScoreResult(
        candidate_id="c1",
        ask=40.0,
        fair_value=100.0,
        deal_score=0.4,
        confidence=Confidence.HIGH,
        stages_run=["median", "fine_tuned"],
    )
    key = "abc123"
    a.put(key, result)

    hit = b.get(key)
    assert hit is not None
    assert hit.cached is True
    assert hit.fair_value == 100.0
    assert hit.content_hash == key


def test_content_hash_stable() -> None:
    from underprice.cache.estimate_cache import content_hash

    c1 = Candidate(title="A", description="B", ask=10.0)
    c2 = Candidate(title="A", description="B", ask=10.0)
    assert content_hash(c1) == content_hash(c2)
