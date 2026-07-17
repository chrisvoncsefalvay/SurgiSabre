import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from surgisabre.course import (  # noqa: E402
    BrickState,
    BrickStateEvent,
)
from surgisabre.score import (  # noqa: E402
    SabreScoreCounter,
    SabreScoreSnapshot,
)


def _event(
    *,
    brick_id: str = "left_0",
    pass_index: int = 0,
    previous_state: BrickState = BrickState.APPROACHING,
    state: BrickState = BrickState.FALLING,
    reason: str = "instrument_hit",
) -> BrickStateEvent:
    return BrickStateEvent(
        brick_id=brick_id,
        pass_index=pass_index,
        lane="left",
        previous_state=previous_state,
        state=state,
        reason=reason,
        position_m=(-0.05, 0.10, -0.03),
        hitter="left" if reason == "instrument_hit" else None,
    )


def test_counts_successful_and_failed_instances() -> None:
    score = SabreScoreCounter()

    successful_changed = score.record_event(_event())
    failed_changed = score.record_event(
        _event(
            brick_id="right_0",
            state=BrickState.RECYCLE_READY,
            reason="missed",
        )
    )

    assert successful_changed is True
    assert failed_changed is True
    assert score.snapshot() == SabreScoreSnapshot(
        successful_instances=1,
        failed_instances=1,
    )
    assert score.snapshot().total_instances == 2


def test_duplicate_and_conflicting_transitions_do_not_score_twice() -> None:
    score = SabreScoreCounter()
    success = _event()
    conflicting_failure = _event(
        state=BrickState.RECYCLE_READY,
        reason="missed",
    )

    assert score.record_event(success) is True
    assert score.record_event(success) is False
    assert score.record_event(conflicting_failure) is False
    assert score.snapshot() == SabreScoreSnapshot(
        successful_instances=1,
        failed_instances=0,
    )


def test_non_scoring_transitions_are_ignored() -> None:
    score = SabreScoreCounter()
    events = (
        _event(reason="unexpected_contact"),
        _event(
            previous_state=BrickState.FALLING,
            state=BrickState.RECYCLE_READY,
            reason="fall_threshold",
        ),
        _event(
            previous_state=BrickState.RECYCLE_READY,
            state=BrickState.APPROACHING,
            reason="missed_recycled_from_pass_0",
        ),
    )

    assert all(score.record_event(event) is False for event in events)
    assert score.snapshot() == SabreScoreSnapshot(
        successful_instances=0,
        failed_instances=0,
    )


def test_new_pass_for_same_brick_is_a_new_instance() -> None:
    score = SabreScoreCounter()

    score.record_event(_event(pass_index=0))
    score.record_event(_event(pass_index=1))

    assert score.snapshot() == SabreScoreSnapshot(
        successful_instances=2,
        failed_instances=0,
    )


def test_reset_clears_counts_and_duplicate_tracking() -> None:
    score = SabreScoreCounter()
    event = _event()
    score.record_event(event)

    score.reset()

    assert score.snapshot() == SabreScoreSnapshot(
        successful_instances=0,
        failed_instances=0,
    )
    assert score.record_event(event) is True
    assert score.snapshot().successful_instances == 1
