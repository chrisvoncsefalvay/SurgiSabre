"""Pure state machine for the project-local two-lane sabre brick game."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, TypeAlias

Hand = Literal["left", "right"]
Vector3 = tuple[float, float, float]
Colour3 = tuple[float, float, float]

BRICK_PASS_RANDOMISATION_ALGORITHM = "sha256_session_ranked_course_v1"


def _finite_float(value: float, field: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def _finite_vector3(value: Vector3, field: str) -> Vector3:
    result = tuple(_finite_float(item, field) for item in value)
    if len(result) != 3:
        raise ValueError(f"{field} must contain three values")
    return result


class BrickState(StrEnum):
    """Lifecycle states for one brick pass."""

    APPROACHING = "approaching"
    FALLING = "falling"
    RECYCLE_READY = "recycle_ready"


@dataclass(frozen=True)
class BrickSpec:
    """Immutable lane geometry and scripted approach motion for one brick."""

    brick_id: str
    lane: Hand
    spawn_position_m: Vector3
    approach_velocity_m_s: Vector3
    approach_end_y_m: float
    size_m: Vector3 = (0.040, 0.040, 0.050)
    display_colour_rgb: Colour3 = (0.80, 0.80, 0.80)

    def __post_init__(self) -> None:
        if not self.brick_id or any(character.isspace() for character in self.brick_id):
            raise ValueError("brick_id must be non-empty and contain no whitespace")
        if self.lane not in {"left", "right"}:
            raise ValueError("lane must be left or right")
        spawn = _finite_vector3(self.spawn_position_m, "spawn_position_m")
        velocity = _finite_vector3(
            self.approach_velocity_m_s,
            "approach_velocity_m_s",
        )
        size = _finite_vector3(self.size_m, "size_m")
        colour = _finite_vector3(self.display_colour_rgb, "display_colour_rgb")
        end_y = _finite_float(self.approach_end_y_m, "approach_end_y_m")
        if any(value <= 0.0 for value in size):
            raise ValueError("size_m values must be positive")
        if any(not 0.0 <= value <= 1.0 for value in colour):
            raise ValueError("display_colour_rgb values must be between zero and one")
        if not math.isclose(velocity[0], 0.0, abs_tol=1.0e-12) or not math.isclose(
            velocity[2], 0.0, abs_tol=1.0e-12
        ):
            raise ValueError(
                "scripted approach motion must be collinear with the Y lane"
            )
        if velocity[1] >= 0.0:
            raise ValueError("approach_velocity_m_s must move towards decreasing Y")
        if spawn[1] <= end_y:
            raise ValueError("spawn_position_m must start before approach_end_y_m")
        if self.lane == "left" and spawn[0] >= 0.0:
            raise ValueError("left-lane bricks must start at negative X")
        if self.lane == "right" and spawn[0] <= 0.0:
            raise ValueError("right-lane bricks must start at positive X")
        object.__setattr__(self, "spawn_position_m", spawn)
        object.__setattr__(self, "approach_velocity_m_s", velocity)
        object.__setattr__(self, "approach_end_y_m", end_y)
        object.__setattr__(self, "size_m", size)
        object.__setattr__(self, "display_colour_rgb", colour)


@dataclass(frozen=True)
class BrickPassSpec:
    """Exact deterministic appearance and motion for one target pass."""

    brick_id: str
    pass_index: int
    lane: Hand
    spawn_position_m: Vector3
    approach_velocity_m_s: Vector3
    approach_end_y_m: float
    size_m: Vector3
    display_colour_rgb: Colour3
    speed_palette_index: int | None
    height_palette_index: int | None
    colour_palette_index: int | None
    randomisation_token: str

    def __post_init__(self) -> None:
        if self.pass_index < 0:
            raise ValueError("pass_index must be non-negative")
        if self.lane not in {"left", "right"}:
            raise ValueError("lane must be left or right")
        for field in (
            "speed_palette_index",
            "height_palette_index",
            "colour_palette_index",
        ):
            value = getattr(self, field)
            if value is not None and value < 0:
                raise ValueError(f"{field} must be non-negative when present")
        if not self.randomisation_token:
            raise ValueError("randomisation_token must be non-empty")

    def to_dict(self) -> dict[str, object]:
        """Return the JSON-compatible pass contract used by runtime evidence."""
        return {
            "brick_id": self.brick_id,
            "pass_index": self.pass_index,
            "lane": self.lane,
            "spawn_position_m": list(self.spawn_position_m),
            "approach_velocity_m_s": list(self.approach_velocity_m_s),
            "approach_end_y_m": self.approach_end_y_m,
            "size_m": list(self.size_m),
            "display_colour_rgb": list(self.display_colour_rgb),
            "speed_palette_index": self.speed_palette_index,
            "height_palette_index": self.height_palette_index,
            "colour_palette_index": self.colour_palette_index,
            "randomisation_token": self.randomisation_token,
        }


@dataclass(frozen=True)
class BrickPassRandomisation:
    """Stateless session-seeded selector for per-pass target variation."""

    seed: str
    speed_choices_m_s: tuple[float, ...]
    height_choices_m: tuple[float, ...]
    colour_choices_rgb: tuple[Colour3, ...]
    brick_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.seed:
            raise ValueError("brick pass randomisation seed must be non-empty")
        speeds = tuple(
            _finite_float(value, "speed_choices_m_s")
            for value in self.speed_choices_m_s
        )
        heights = tuple(
            _finite_float(value, "height_choices_m")
            for value in self.height_choices_m
        )
        colours = tuple(
            _finite_vector3(value, "colour_choices_rgb")
            for value in self.colour_choices_rgb
        )
        brick_ids = tuple(str(value) for value in self.brick_ids)
        if not speeds or any(value <= 0.0 for value in speeds):
            raise ValueError("speed_choices_m_s must contain positive values")
        if not heights:
            raise ValueError("height_choices_m must not be empty")
        if not colours or any(
            not 0.0 <= component <= 1.0
            for colour in colours
            for component in colour
        ):
            raise ValueError("colour_choices_rgb must contain normalised colours")
        if len(brick_ids) != len(set(brick_ids)):
            raise ValueError("brick_ids must be unique")
        if any(
            not brick_id or any(character.isspace() for character in brick_id)
            for brick_id in brick_ids
        ):
            raise ValueError("brick_ids must contain valid brick identifiers")
        object.__setattr__(self, "speed_choices_m_s", speeds)
        object.__setattr__(self, "height_choices_m", heights)
        object.__setattr__(self, "colour_choices_rgb", colours)
        object.__setattr__(self, "brick_ids", brick_ids)

    @property
    def seed_fingerprint(self) -> str:
        return hashlib.sha256(self.seed.encode("utf-8")).hexdigest()[:16]

    def select(self, spec: BrickSpec, pass_index: int) -> BrickPassSpec:
        """Select one pass independently of call order or mutable RNG state."""
        if pass_index < 0:
            raise ValueError("pass_index must be non-negative")
        speed_index = self._palette_index(spec.brick_id, pass_index, "speed", len(self.speed_choices_m_s))
        height_index = self._palette_index(
            spec.brick_id,
            pass_index,
            "height",
            len(self.height_choices_m),
        )
        colour_index = self._palette_index(
            spec.brick_id,
            pass_index,
            "colour",
            len(self.colour_choices_rgb),
        )
        token_source = (
            f"{BRICK_PASS_RANDOMISATION_ALGORITHM}|{self.seed}|"
            f"{spec.brick_id}|{pass_index}"
        )
        token = hashlib.sha256(token_source.encode("utf-8")).hexdigest()[:16]
        return BrickPassSpec(
            brick_id=spec.brick_id,
            pass_index=pass_index,
            lane=spec.lane,
            spawn_position_m=(
                spec.spawn_position_m[0],
                spec.spawn_position_m[1],
                self.height_choices_m[height_index],
            ),
            approach_velocity_m_s=(
                0.0,
                -self.speed_choices_m_s[speed_index],
                0.0,
            ),
            approach_end_y_m=spec.approach_end_y_m,
            size_m=spec.size_m,
            display_colour_rgb=self.colour_choices_rgb[colour_index],
            speed_palette_index=speed_index,
            height_palette_index=height_index,
            colour_palette_index=colour_index,
            randomisation_token=token,
        )

    def report(self) -> dict[str, object]:
        return {
            "algorithm": BRICK_PASS_RANDOMISATION_ALGORITHM,
            "seed_fingerprint": self.seed_fingerprint,
            "speed_choices_m_s": list(self.speed_choices_m_s),
            "height_choices_m": list(self.height_choices_m),
            "colour_choices_rgb": [list(colour) for colour in self.colour_choices_rgb],
            "brick_ids": list(self.brick_ids),
            "diversity_policy": (
                "session_ranked_colour_height_per_pass_speed"
                if self.brick_ids
                else "independent_hash_modulo"
            ),
            "session_ranked_fields": (
                ["height", "colour"] if self.brick_ids else []
            ),
            "per_pass_ranked_fields": (
                ["speed"] if self.brick_ids else ["speed", "height", "colour"]
            ),
            "physical_length_policy": "fixed_preauthored_colliders",
        }

    def _palette_index(
        self,
        brick_id: str,
        pass_index: int,
        field: str,
        size: int,
    ) -> int:
        if self.brick_ids:
            if brick_id not in self.brick_ids:
                raise ValueError(
                    f"brick_id {brick_id!r} is absent from the randomisation set"
                )
            ranking_pass_index = pass_index if field == "speed" else 0
            ranked_ids = sorted(
                self.brick_ids,
                key=lambda candidate: hashlib.sha256(
                    (
                        f"{BRICK_PASS_RANDOMISATION_ALGORITHM}|{self.seed}|"
                        f"{ranking_pass_index}|{field}|{candidate}"
                    ).encode()
                ).digest(),
            )
            return ranked_ids.index(brick_id) % size
        source = (
            f"{BRICK_PASS_RANDOMISATION_ALGORITHM}|{self.seed}|"
            f"{brick_id}|{pass_index}|{field}"
        )
        digest = hashlib.sha256(source.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") % size


def _fixed_pass_spec(spec: BrickSpec, pass_index: int) -> BrickPassSpec:
    return BrickPassSpec(
        brick_id=spec.brick_id,
        pass_index=pass_index,
        lane=spec.lane,
        spawn_position_m=spec.spawn_position_m,
        approach_velocity_m_s=spec.approach_velocity_m_s,
        approach_end_y_m=spec.approach_end_y_m,
        size_m=spec.size_m,
        display_colour_rgb=spec.display_colour_rgb,
        speed_palette_index=None,
        height_palette_index=None,
        colour_palette_index=None,
        randomisation_token="fixed",
    )


@dataclass(frozen=True)
class BrickGameConfig:
    """Shared fall, recycle and haptic settings for the course."""

    fall_z_threshold_m: float = -0.30
    fall_timeout_s: float = 2.0
    haptic_amplitude: float = 0.80
    haptic_duration_s: float = 0.080
    haptic_frequency_hz: float = 0.0

    def __post_init__(self) -> None:
        threshold = _finite_float(self.fall_z_threshold_m, "fall_z_threshold_m")
        timeout = _finite_float(self.fall_timeout_s, "fall_timeout_s")
        amplitude = _finite_float(self.haptic_amplitude, "haptic_amplitude")
        duration = _finite_float(self.haptic_duration_s, "haptic_duration_s")
        frequency = _finite_float(self.haptic_frequency_hz, "haptic_frequency_hz")
        if timeout <= 0.0:
            raise ValueError("fall_timeout_s must be positive")
        if not 0.0 <= amplitude <= 1.0:
            raise ValueError("haptic_amplitude must be between zero and one")
        if duration < 0.0:
            raise ValueError("haptic_duration_s must be non-negative")
        if frequency < 0.0:
            raise ValueError("haptic_frequency_hz must be non-negative")
        object.__setattr__(self, "fall_z_threshold_m", threshold)
        object.__setattr__(self, "fall_timeout_s", timeout)
        object.__setattr__(self, "haptic_amplitude", amplitude)
        object.__setattr__(self, "haptic_duration_s", duration)
        object.__setattr__(self, "haptic_frequency_hz", frequency)


@dataclass(frozen=True)
class InstrumentContact:
    """A PSM contact already classified by the Isaac adapter."""

    brick_id: str
    pass_index: int
    hitter: Hand
    position_m: Vector3 | None = None

    def __post_init__(self) -> None:
        if self.pass_index < 0:
            raise ValueError("pass_index must be non-negative")
        if self.hitter not in {"left", "right"}:
            raise ValueError("hitter must be left or right")
        if self.position_m is not None:
            object.__setattr__(
                self,
                "position_m",
                _finite_vector3(self.position_m, "position_m"),
            )


@dataclass(frozen=True)
class ScriptedPoseRequest:
    """Request an adapter-owned, gravity-free approach pose."""

    brick_id: str
    pass_index: int
    position_m: Vector3
    gravity_enabled: bool = False
    scripted_motion_enabled: bool = True


@dataclass(frozen=True)
class ReleaseToPhysicsRequest:
    """Stop scripted drive and let gravity own the brick."""

    brick_id: str
    pass_index: int
    gravity_enabled: bool = True
    scripted_motion_enabled: bool = False
    clear_velocity: bool = True


@dataclass(frozen=True)
class RecycleRequest:
    """Reset a completed pass at its deterministic spawn pose."""

    brick_id: str
    completed_pass_index: int
    next_pass_index: int
    position_m: Vector3
    next_pass_spec: BrickPassSpec
    gravity_enabled: bool = False
    scripted_motion_enabled: bool = True
    clear_velocity: bool = True


BrickCommand: TypeAlias = ScriptedPoseRequest | ReleaseToPhysicsRequest | RecycleRequest


@dataclass(frozen=True)
class HapticHitEvent:
    """One controller pulse caused by the first instrument hit in a pass."""

    brick_id: str
    pass_index: int
    hand: Hand
    amplitude: float
    duration_s: float
    frequency_hz: float
    contact_position_m: Vector3 | None


@dataclass(frozen=True)
class BrickStateEvent:
    """A state transition suitable for structured runtime telemetry."""

    brick_id: str
    pass_index: int
    lane: Hand
    previous_state: BrickState
    state: BrickState
    reason: str
    position_m: Vector3
    hitter: Hand | None = None
    pass_spec: BrickPassSpec | None = None


@dataclass(frozen=True)
class BrickUpdate:
    """Adapter commands and one-shot events produced by a state-machine call."""

    commands: tuple[BrickCommand, ...] = ()
    haptic_events: tuple[HapticHitEvent, ...] = ()
    state_events: tuple[BrickStateEvent, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (self.commands or self.haptic_events or self.state_events)


@dataclass(frozen=True)
class BrickSnapshot:
    """Read-only state for validation and telemetry."""

    brick_id: str
    lane: Hand
    pass_index: int
    state: BrickState
    position_m: Vector3
    fall_elapsed_s: float
    hitter: Hand | None
    pass_spec: BrickPassSpec


@dataclass
class _BrickRuntime:
    base_spec: BrickSpec
    pass_spec: BrickPassSpec
    pass_index: int
    state: BrickState
    position_m: Vector3
    fall_elapsed_s: float = 0.0
    hitter: Hand | None = None
    recycle_reason: str | None = None


class TwoLaneBrickStateMachine:
    """Drive deterministic approaches while leaving all falling motion to physics.

    The Isaac adapter owns USD paths, collision decoding, body modes and gravity
    attributes. It should call :meth:`record_instrument_contact` only after a
    contact has been classified as brick against left or right PSM geometry.
    """

    def __init__(
        self,
        specs: tuple[BrickSpec, ...],
        config: BrickGameConfig | None = None,
        pass_randomisation: BrickPassRandomisation | None = None,
    ) -> None:
        if not specs:
            raise ValueError("two-lane brick game requires at least one brick")
        identifiers = [spec.brick_id for spec in specs]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("brick_id values must be unique")
        lanes = {spec.lane for spec in specs}
        if lanes != {"left", "right"}:
            raise ValueError("two-lane brick game requires left and right bricks")
        self.config = config or BrickGameConfig()
        self.pass_randomisation = pass_randomisation
        self._order = tuple(identifiers)
        self._bricks: dict[str, _BrickRuntime] = {}
        for spec in specs:
            pass_spec = self._select_pass(spec, 0)
            self._bricks[spec.brick_id] = _BrickRuntime(
                base_spec=spec,
                pass_spec=pass_spec,
                pass_index=0,
                state=BrickState.APPROACHING,
                position_m=pass_spec.spawn_position_m,
            )

    def snapshot(self, brick_id: str) -> BrickSnapshot:
        runtime = self._require_brick(brick_id)
        return BrickSnapshot(
            brick_id=runtime.base_spec.brick_id,
            lane=runtime.base_spec.lane,
            pass_index=runtime.pass_index,
            state=runtime.state,
            position_m=runtime.position_m,
            fall_elapsed_s=runtime.fall_elapsed_s,
            hitter=runtime.hitter,
            pass_spec=runtime.pass_spec,
        )

    def snapshots(self) -> tuple[BrickSnapshot, ...]:
        return tuple(self.snapshot(brick_id) for brick_id in self._order)

    def step(
        self,
        dt_s: float,
        observed_positions_m: Mapping[str, Vector3] | None = None,
    ) -> BrickUpdate:
        """Advance one physics interval and return requests for the adapter."""

        dt_s = _finite_float(dt_s, "dt_s")
        if dt_s <= 0.0:
            raise ValueError("dt_s must be positive")
        observed = dict(observed_positions_m or {})
        unknown = sorted(set(observed) - set(self._bricks))
        if unknown:
            raise KeyError(f"observed positions contain unknown bricks: {unknown}")
        observed = {
            brick_id: _finite_vector3(position, f"observed_positions_m[{brick_id!r}]")
            for brick_id, position in observed.items()
        }

        commands: list[BrickCommand] = []
        state_events: list[BrickStateEvent] = []
        for brick_id in self._order:
            runtime = self._bricks[brick_id]
            if runtime.state is BrickState.APPROACHING:
                next_position = tuple(
                    position + velocity * dt_s
                    for position, velocity in zip(
                        runtime.position_m,
                        runtime.pass_spec.approach_velocity_m_s,
                        strict=True,
                    )
                )
                if next_position[1] <= runtime.pass_spec.approach_end_y_m:
                    runtime.position_m = (
                        next_position[0],
                        runtime.pass_spec.approach_end_y_m,
                        next_position[2],
                    )
                    previous = runtime.state
                    runtime.state = BrickState.RECYCLE_READY
                    runtime.recycle_reason = "missed"
                    commands.append(self._recycle_request(runtime))
                    state_events.append(
                        BrickStateEvent(
                            brick_id=runtime.base_spec.brick_id,
                            pass_index=runtime.pass_index,
                            lane=runtime.base_spec.lane,
                            previous_state=previous,
                            state=runtime.state,
                            reason="missed",
                            position_m=runtime.position_m,
                            pass_spec=runtime.pass_spec,
                        )
                    )
                else:
                    runtime.position_m = next_position
                    commands.append(self._scripted_pose(runtime))
            elif runtime.state is BrickState.FALLING:
                if brick_id in observed:
                    runtime.position_m = observed[brick_id]
                runtime.fall_elapsed_s += dt_s
                below_threshold = (
                    runtime.position_m[2] <= self.config.fall_z_threshold_m
                )
                timed_out = runtime.fall_elapsed_s >= self.config.fall_timeout_s
                if below_threshold or timed_out:
                    previous = runtime.state
                    runtime.state = BrickState.RECYCLE_READY
                    runtime.recycle_reason = (
                        "fall_threshold" if below_threshold else "fall_timeout"
                    )
                    commands.append(self._recycle_request(runtime))
                    state_events.append(
                        BrickStateEvent(
                            brick_id=runtime.base_spec.brick_id,
                            pass_index=runtime.pass_index,
                            lane=runtime.base_spec.lane,
                            previous_state=previous,
                            state=runtime.state,
                            reason=runtime.recycle_reason,
                            position_m=runtime.position_m,
                            hitter=runtime.hitter,
                            pass_spec=runtime.pass_spec,
                        )
                    )
            else:
                commands.append(self._recycle_request(runtime))

        return BrickUpdate(commands=tuple(commands), state_events=tuple(state_events))

    def record_instrument_contact(self, contact: InstrumentContact) -> BrickUpdate:
        """Release and pulse once for the first current-pass PSM contact."""

        runtime = self._require_brick(contact.brick_id)
        if contact.pass_index != runtime.pass_index:
            return BrickUpdate()
        if runtime.state is not BrickState.APPROACHING:
            return BrickUpdate()

        runtime.hitter = contact.hitter
        if contact.position_m is not None:
            runtime.position_m = contact.position_m
        release, event = self._begin_fall(runtime, reason="instrument_hit")
        haptic = HapticHitEvent(
            brick_id=runtime.base_spec.brick_id,
            pass_index=runtime.pass_index,
            hand=contact.hitter,
            amplitude=self.config.haptic_amplitude,
            duration_s=self.config.haptic_duration_s,
            frequency_hz=self.config.haptic_frequency_hz,
            contact_position_m=contact.position_m,
        )
        return BrickUpdate(
            commands=(release,),
            haptic_events=(haptic,),
            state_events=(event,),
        )

    def acknowledge_recycle(
        self,
        brick_id: str,
        next_pass_index: int,
    ) -> BrickUpdate:
        """Confirm that the adapter applied a recycle request successfully."""

        runtime = self._require_brick(brick_id)
        if runtime.state is not BrickState.RECYCLE_READY:
            raise RuntimeError(f"brick {brick_id!r} is not ready to recycle")
        expected_index = runtime.pass_index + 1
        if next_pass_index != expected_index:
            raise ValueError(
                f"next_pass_index is {next_pass_index}, expected {expected_index}"
            )
        previous = runtime.state
        previous_pass = runtime.pass_index
        reason = runtime.recycle_reason or "recycled"
        next_pass = self._select_pass(runtime.base_spec, next_pass_index)
        runtime.pass_index = next_pass_index
        runtime.pass_spec = next_pass
        runtime.state = BrickState.APPROACHING
        runtime.position_m = next_pass.spawn_position_m
        runtime.fall_elapsed_s = 0.0
        runtime.hitter = None
        runtime.recycle_reason = None
        return BrickUpdate(
            state_events=(
                BrickStateEvent(
                    brick_id=runtime.base_spec.brick_id,
                    pass_index=runtime.pass_index,
                    lane=runtime.base_spec.lane,
                    previous_state=previous,
                    state=runtime.state,
                    reason=f"{reason}_recycled_from_pass_{previous_pass}",
                    position_m=runtime.position_m,
                    pass_spec=runtime.pass_spec,
                ),
            )
        )

    def _require_brick(self, brick_id: str) -> _BrickRuntime:
        try:
            return self._bricks[brick_id]
        except KeyError as error:
            raise KeyError(f"unknown brick: {brick_id!r}") from error

    @staticmethod
    def _scripted_pose(runtime: _BrickRuntime) -> ScriptedPoseRequest:
        return ScriptedPoseRequest(
            brick_id=runtime.base_spec.brick_id,
            pass_index=runtime.pass_index,
            position_m=runtime.position_m,
        )

    @staticmethod
    def _begin_fall(
        runtime: _BrickRuntime,
        *,
        reason: str,
    ) -> tuple[ReleaseToPhysicsRequest, BrickStateEvent]:
        previous = runtime.state
        runtime.state = BrickState.FALLING
        runtime.fall_elapsed_s = 0.0
        return (
            ReleaseToPhysicsRequest(
                brick_id=runtime.base_spec.brick_id,
                pass_index=runtime.pass_index,
            ),
            BrickStateEvent(
                brick_id=runtime.base_spec.brick_id,
                pass_index=runtime.pass_index,
                lane=runtime.base_spec.lane,
                previous_state=previous,
                state=runtime.state,
                reason=reason,
                position_m=runtime.position_m,
                hitter=runtime.hitter,
                pass_spec=runtime.pass_spec,
            ),
        )

    def _recycle_request(self, runtime: _BrickRuntime) -> RecycleRequest:
        next_pass = self._select_pass(
            runtime.base_spec,
            runtime.pass_index + 1,
        )
        return RecycleRequest(
            brick_id=runtime.base_spec.brick_id,
            completed_pass_index=runtime.pass_index,
            next_pass_index=runtime.pass_index + 1,
            position_m=next_pass.spawn_position_m,
            next_pass_spec=next_pass,
        )

    def _select_pass(self, spec: BrickSpec, pass_index: int) -> BrickPassSpec:
        if self.pass_randomisation is None:
            return _fixed_pass_spec(spec, pass_index)
        return self.pass_randomisation.select(spec, pass_index)


def default_two_lane_brick_specs() -> tuple[BrickSpec, ...]:
    """Return four staggered bricks with no random or wall-clock state."""

    speed_m_s = -0.035
    end_y_m = -0.10
    spawn_z_m = -0.035
    return (
        BrickSpec(
            brick_id="left_0",
            lane="left",
            spawn_position_m=(-0.055, 0.24, spawn_z_m),
            approach_velocity_m_s=(0.0, speed_m_s, 0.0),
            approach_end_y_m=end_y_m,
        ),
        BrickSpec(
            brick_id="right_0",
            lane="right",
            spawn_position_m=(0.055, 0.32, spawn_z_m),
            approach_velocity_m_s=(0.0, speed_m_s, 0.0),
            approach_end_y_m=end_y_m,
        ),
        BrickSpec(
            brick_id="left_1",
            lane="left",
            spawn_position_m=(-0.055, 0.40, spawn_z_m),
            approach_velocity_m_s=(0.0, speed_m_s, 0.0),
            approach_end_y_m=end_y_m,
        ),
        BrickSpec(
            brick_id="right_1",
            lane="right",
            spawn_position_m=(0.055, 0.48, spawn_z_m),
            approach_velocity_m_s=(0.0, speed_m_s, 0.0),
            approach_end_y_m=end_y_m,
        ),
    )


__all__ = [
    "BRICK_PASS_RANDOMISATION_ALGORITHM",
    "BrickCommand",
    "BrickGameConfig",
    "BrickPassRandomisation",
    "BrickPassSpec",
    "BrickSnapshot",
    "BrickSpec",
    "BrickState",
    "BrickStateEvent",
    "BrickUpdate",
    "HapticHitEvent",
    "InstrumentContact",
    "RecycleRequest",
    "ReleaseToPhysicsRequest",
    "ScriptedPoseRequest",
    "TwoLaneBrickStateMachine",
    "default_two_lane_brick_specs",
]
