from __future__ import annotations

import pytest

from underprice.models import Candidate, ScoreResult, Signal
from underprice.specialists.fine_tuned import list_price_prompt


def test_candidate_rejects_non_positive_ask() -> None:
    with pytest.raises(ValueError):
        Candidate(title="x", ask=0)


def test_list_price_prompt_contract() -> None:
    prompt = list_price_prompt("Sony WH-1000XM5")
    assert prompt.startswith("What does this cost")
    assert prompt.endswith("Price is $")


def test_fuse_prefers_fine_tuned() -> None:
    c = Candidate(title="x", ask=50)
    result = ScoreResult.fuse(
        candidate=c,
        signals={
            "median": Signal(source="median", value=100),
            "fine_tuned": Signal(source="fine_tuned", value=80),
        },
        stages_run=["median", "fine_tuned"],
        early_exit_reason=None,
        hot_deal=0.7,
        model_revision="v0.1.0",
    )
    assert result.fair_value == 80
    assert result.deal_score == round(50 / 80, 4)
    assert result.messenger_eligible is True
