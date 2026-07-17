"""Deterministic aggregate scoring for Surg Sabre brick passes."""

from __future__ import annotations

from dataclasses import dataclass

from .course import BrickState, BrickStateEvent


@dataclass(frozen=True)
class SabreScoreSnapshot:
    """Read-only counts for the current Surg Sabre session."""

    successful_instances: int
    failed_instances: int

    @property
    def total_instances(self) -> int:
        """Return the number of completed scoring instances."""

        return self.successful_instances + self.failed_instances


class SabreScoreCounter:
    """Count each brick pass once from its first scoring transition."""

    def __init__(self) -> None:
        self._successful_instances = 0
        self._failed_instances = 0
        self._scored_passes: set[tuple[str, int]] = set()

    def record_event(self, event: BrickStateEvent) -> bool:
        """Record a scoring transition and report whether the score changed."""

        outcome = self._scoring_outcome(event)
        if outcome is None:
            return False

        pass_key = (event.brick_id, event.pass_index)
        if pass_key in self._scored_passes:
            return False

        self._scored_passes.add(pass_key)
        if outcome == "successful":
            self._successful_instances += 1
        else:
            self._failed_instances += 1
        return True

    def snapshot(self) -> SabreScoreSnapshot:
        """Return immutable aggregate counts for display or telemetry."""

        return SabreScoreSnapshot(
            successful_instances=self._successful_instances,
            failed_instances=self._failed_instances,
        )

    def reset(self) -> None:
        """Clear counts and per-pass duplicate tracking."""

        self._successful_instances = 0
        self._failed_instances = 0
        self._scored_passes.clear()

    @staticmethod
    def _scoring_outcome(event: BrickStateEvent) -> str | None:
        if (
            event.previous_state is BrickState.APPROACHING
            and event.state is BrickState.FALLING
            and event.reason == "instrument_hit"
        ):
            return "successful"
        if (
            event.previous_state is BrickState.APPROACHING
            and event.state is BrickState.RECYCLE_READY
            and event.reason == "missed"
        ):
            return "failed"
        return None


__all__ = ["SabreScoreCounter", "SabreScoreSnapshot"]
