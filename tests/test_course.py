import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from surgisabre.course import (  # noqa: E402
    BRICK_PASS_RANDOMISATION_ALGORITHM,
    BrickGameConfig,
    BrickPassRandomisation,
    BrickSpec,
    BrickState,
    InstrumentContact,
    RecycleRequest,
    ReleaseToPhysicsRequest,
    ScriptedPoseRequest,
    TwoLaneBrickStateMachine,
    default_two_lane_brick_specs,
)

RANDOM_SPEEDS_M_S = (0.160, 0.176, 0.192, 0.208, 0.224, 0.240)
RANDOM_HEIGHTS_M = (-0.040, -0.018, 0.004, 0.026)
RANDOM_COLOURS_RGB = (
    (0.92, 0.12, 0.56),
    (0.08, 0.28, 1.00),
    (0.55, 0.12, 0.92),
    (1.00, 0.35, 0.65),
    (0.04, 0.78, 0.94),
    (0.18, 0.05, 0.56),
)


def _specs() -> tuple[BrickSpec, ...]:
    return (
        BrickSpec(
            brick_id="left",
            lane="left",
            spawn_position_m=(-0.05, 0.20, -0.03),
            approach_velocity_m_s=(0.0, -0.05, 0.0),
            approach_end_y_m=-0.10,
        ),
        BrickSpec(
            brick_id="right",
            lane="right",
            spawn_position_m=(0.05, 0.30, -0.03),
            approach_velocity_m_s=(0.0, -0.05, 0.0),
            approach_end_y_m=-0.10,
        ),
    )


def _game(**config_values: float) -> TwoLaneBrickStateMachine:
    return TwoLaneBrickStateMachine(
        _specs(),
        BrickGameConfig(**config_values),
    )


def _ranked_specs() -> tuple[BrickSpec, ...]:
    return tuple(
        BrickSpec(
            brick_id=f"{lane}_{index}",
            lane=lane,
            spawn_position_m=(
                -0.05 if lane == "left" else 0.05,
                0.20 + index * 0.05,
                -0.03,
            ),
            approach_velocity_m_s=(0.0, -0.05, 0.0),
            approach_end_y_m=-0.10,
            size_m=(0.04 + index * 0.005, 0.038, 0.038),
        )
        for index, lane in enumerate(
            ("left", "right", "left", "right", "left", "right"),
            start=1,
        )
    )


def _randomisation(
    seed: str = "session-a",
    *,
    brick_ids: tuple[str, ...] = ("left", "right"),
) -> BrickPassRandomisation:
    return BrickPassRandomisation(
        seed=seed,
        speed_choices_m_s=RANDOM_SPEEDS_M_S,
        height_choices_m=RANDOM_HEIGHTS_M,
        colour_choices_rgb=RANDOM_COLOURS_RGB,
        brick_ids=brick_ids,
    )


def test_default_course_is_deterministic_and_contains_both_lanes() -> None:
    first = default_two_lane_brick_specs()
    second = default_two_lane_brick_specs()

    assert first == second
    assert [spec.brick_id for spec in first] == [
        "left_0",
        "right_0",
        "left_1",
        "right_1",
    ]
    assert {spec.lane for spec in first} == {"left", "right"}
    assert all(spec.approach_velocity_m_s == (0.0, -0.035, 0.0) for spec in first)


def test_ranked_pass_randomisation_guarantees_diversity_and_fixed_colliders() -> None:
    specs = _ranked_specs()
    brick_ids = tuple(spec.brick_id for spec in specs)
    first = _randomisation(brick_ids=brick_ids)
    second = _randomisation(brick_ids=brick_ids)
    initial = [first.select(spec, pass_index=0) for spec in specs]
    initial_heights = {
        pass_spec.brick_id: pass_spec.height_palette_index
        for pass_spec in initial
    }
    initial_colours = {
        pass_spec.brick_id: pass_spec.colour_palette_index
        for pass_spec in initial
    }
    speed_assignments: set[tuple[int | None, ...]] = set()

    for pass_index in range(64):
        selected = [first.select(spec, pass_index) for spec in specs]
        selected_in_reverse = {
            spec.brick_id: second.select(spec, pass_index)
            for spec in reversed(specs)
        }

        assert all(
            pass_spec == selected_in_reverse[pass_spec.brick_id]
            for pass_spec in selected
        )
        assert {pass_spec.speed_palette_index for pass_spec in selected} == set(
            range(len(RANDOM_SPEEDS_M_S))
        )
        assert {pass_spec.height_palette_index for pass_spec in selected} == set(
            range(len(RANDOM_HEIGHTS_M))
        )
        assert {pass_spec.colour_palette_index for pass_spec in selected} == set(
            range(len(RANDOM_COLOURS_RGB))
        )
        assert {
            pass_spec.brick_id: pass_spec.height_palette_index
            for pass_spec in selected
        } == initial_heights
        assert {
            pass_spec.brick_id: pass_spec.colour_palette_index
            for pass_spec in selected
        } == initial_colours
        speed_assignments.add(
            tuple(pass_spec.speed_palette_index for pass_spec in selected)
        )
        for spec, pass_spec in zip(specs, selected, strict=True):
            assert pass_spec.spawn_position_m[:2] == spec.spawn_position_m[:2]
            assert pass_spec.spawn_position_m[2] in RANDOM_HEIGHTS_M
            assert pass_spec.approach_velocity_m_s[0] == 0.0
            assert -pass_spec.approach_velocity_m_s[1] in RANDOM_SPEEDS_M_S
            assert pass_spec.approach_velocity_m_s[2] == 0.0
            assert pass_spec.approach_end_y_m == spec.approach_end_y_m
            assert pass_spec.size_m == spec.size_m
            assert pass_spec.display_colour_rgb in RANDOM_COLOURS_RGB
            assert len(pass_spec.randomisation_token) == 16

    assert len(speed_assignments) > 1


def test_pass_randomisation_report_exposes_replay_contract_without_raw_seed() -> None:
    randomisation = _randomisation(seed="private-session-id")

    report = randomisation.report()

    assert report == {
        "algorithm": BRICK_PASS_RANDOMISATION_ALGORITHM,
        "seed_fingerprint": randomisation.seed_fingerprint,
        "speed_choices_m_s": list(RANDOM_SPEEDS_M_S),
        "height_choices_m": list(RANDOM_HEIGHTS_M),
        "colour_choices_rgb": [list(colour) for colour in RANDOM_COLOURS_RGB],
        "brick_ids": ["left", "right"],
        "diversity_policy": "session_ranked_colour_height_per_pass_speed",
        "session_ranked_fields": ["height", "colour"],
        "per_pass_ranked_fields": ["speed"],
        "physical_length_policy": "fixed_preauthored_colliders",
    }
    assert len(randomisation.seed_fingerprint) == 16
    assert "private-session-id" not in str(report)


def test_randomised_recycle_request_is_stable_and_installed_on_acknowledgement() -> None:
    randomisation = _randomisation()
    game = TwoLaneBrickStateMachine(
        _specs(),
        BrickGameConfig(fall_z_threshold_m=-0.20),
        pass_randomisation=randomisation,
    )
    initial = randomisation.select(_specs()[0], pass_index=0)

    assert game.snapshot("left").pass_spec == initial
    assert game.snapshot("left").position_m == initial.spawn_position_m

    game.record_instrument_contact(
        InstrumentContact(brick_id="left", pass_index=0, hitter="left")
    )
    first_recycle = game.step(0.1, {"left": (-0.05, 0.10, -0.21)})
    repeated_recycle = game.step(0.1)
    first_request = next(
        command
        for command in first_recycle.commands
        if isinstance(command, RecycleRequest) and command.brick_id == "left"
    )
    repeated_request = next(
        command
        for command in repeated_recycle.commands
        if isinstance(command, RecycleRequest) and command.brick_id == "left"
    )
    expected_next = randomisation.select(_specs()[0], pass_index=1)

    assert first_request.next_pass_spec == expected_next
    assert repeated_request.next_pass_spec == expected_next
    assert first_request.position_m == expected_next.spawn_position_m

    acknowledgement = game.acknowledge_recycle("left", next_pass_index=1)
    snapshot = game.snapshot("left")

    assert snapshot.pass_spec == expected_next
    assert snapshot.position_m == expected_next.spawn_position_m
    assert acknowledgement.state_events[0].pass_spec == expected_next
    assert acknowledgement.state_events[0].position_m == expected_next.spawn_position_m


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"seed": ""}, "seed"),
        ({"speed_choices_m_s": ()}, "positive"),
        ({"speed_choices_m_s": (0.0,)}, "positive"),
        ({"height_choices_m": ()}, "must not be empty"),
        ({"colour_choices_rgb": ()}, "normalised"),
        ({"colour_choices_rgb": ((1.1, 0.0, 0.0),)}, "normalised"),
        ({"brick_ids": ("left", "left")}, "unique"),
        ({"brick_ids": ("left", "bad id")}, "valid brick identifiers"),
    ],
)
def test_pass_randomisation_validation_fails_closed(
    changes: dict[str, object],
    message: str,
) -> None:
    values: dict[str, object] = {
        "seed": "session-a",
        "speed_choices_m_s": RANDOM_SPEEDS_M_S,
        "height_choices_m": RANDOM_HEIGHTS_M,
        "colour_choices_rgb": RANDOM_COLOURS_RGB,
        "brick_ids": ("left", "right"),
    }
    values.update(changes)

    with pytest.raises(ValueError, match=message):
        BrickPassRandomisation(**values)


def test_ranked_randomisation_rejects_a_brick_outside_its_course() -> None:
    with pytest.raises(ValueError, match="absent from the randomisation set"):
        _randomisation().select(_ranked_specs()[0], pass_index=0)


def test_approach_is_scripted_collinear_and_gravity_free() -> None:
    game = _game()

    update = game.step(0.5)
    left_request = next(
        command
        for command in update.commands
        if isinstance(command, ScriptedPoseRequest) and command.brick_id == "left"
    )

    assert left_request.position_m == pytest.approx((-0.05, 0.175, -0.03))
    assert left_request.scripted_motion_enabled is True
    assert left_request.gravity_enabled is False
    assert game.snapshot("left").state is BrickState.APPROACHING


@pytest.mark.parametrize("hitter", ["left", "right"])
def test_first_psm_contact_releases_once_and_pulses_the_hitter(hitter: str) -> None:
    game = _game(
        haptic_amplitude=0.75,
        haptic_duration_s=0.06,
        haptic_frequency_hz=90.0,
    )
    contact = InstrumentContact(
        brick_id="left",
        pass_index=0,
        hitter=hitter,
        position_m=(-0.04, 0.10, -0.02),
    )

    first = game.record_instrument_contact(contact)
    duplicate = game.record_instrument_contact(contact)

    assert len(first.commands) == 1
    release = first.commands[0]
    assert isinstance(release, ReleaseToPhysicsRequest)
    assert release.scripted_motion_enabled is False
    assert release.gravity_enabled is True
    assert release.clear_velocity is True
    assert len(first.haptic_events) == 1
    pulse = first.haptic_events[0]
    assert pulse.hand == hitter
    assert pulse.amplitude == 0.75
    assert pulse.duration_s == 0.06
    assert pulse.frequency_hz == 90.0
    assert pulse.contact_position_m == pytest.approx((-0.04, 0.10, -0.02))
    assert first.state_events[0].reason == "instrument_hit"
    assert game.snapshot("left").state is BrickState.FALLING
    assert duplicate.is_empty


def test_falling_is_physics_owned_until_below_threshold() -> None:
    game = _game(fall_z_threshold_m=-0.25, fall_timeout_s=2.0)
    game.record_instrument_contact(
        InstrumentContact(brick_id="left", pass_index=0, hitter="right")
    )

    above = game.step(0.1, {"left": (-0.04, 0.08, -0.20)})
    below = game.step(0.1, {"left": (-0.03, 0.08, -0.26)})

    assert not any(
        isinstance(command, ScriptedPoseRequest) and command.brick_id == "left"
        for command in above.commands
    )
    assert game.snapshot("left").state is BrickState.RECYCLE_READY
    recycle = next(
        command
        for command in below.commands
        if isinstance(command, RecycleRequest) and command.brick_id == "left"
    )
    assert recycle.completed_pass_index == 0
    assert recycle.next_pass_index == 1
    assert recycle.gravity_enabled is False
    assert recycle.scripted_motion_enabled is True
    assert below.state_events[0].reason == "fall_threshold"


def test_fall_timeout_requests_recycle_without_a_height_sample() -> None:
    game = _game(fall_z_threshold_m=-0.50, fall_timeout_s=0.20)
    game.record_instrument_contact(
        InstrumentContact(brick_id="right", pass_index=0, hitter="left")
    )

    first = game.step(0.10)
    second = game.step(0.10)

    assert not any(
        isinstance(command, RecycleRequest) and command.brick_id == "right"
        for command in first.commands
    )
    assert any(
        isinstance(command, RecycleRequest) and command.brick_id == "right"
        for command in second.commands
    )
    assert game.snapshot("right").state is BrickState.RECYCLE_READY
    assert second.state_events[0].reason == "fall_timeout"


def test_recycle_request_repeats_until_acknowledged_then_starts_next_pass() -> None:
    game = _game(fall_z_threshold_m=-0.20)
    game.record_instrument_contact(
        InstrumentContact(brick_id="left", pass_index=0, hitter="left")
    )
    game.step(0.1, {"left": (-0.05, 0.10, -0.21)})

    repeated = game.step(0.1)
    acknowledgement = game.acknowledge_recycle("left", next_pass_index=1)
    next_step = game.step(0.1)

    assert any(
        isinstance(command, RecycleRequest) and command.brick_id == "left"
        for command in repeated.commands
    )
    assert acknowledgement.state_events[0].state is BrickState.APPROACHING
    assert game.snapshot("left").pass_index == 1
    assert game.snapshot("left").hitter is None
    next_pose = next(
        command
        for command in next_step.commands
        if isinstance(command, ScriptedPoseRequest) and command.brick_id == "left"
    )
    assert next_pose.pass_index == 1
    assert next_pose.position_m == pytest.approx((-0.05, 0.195, -0.03))


def test_stale_contact_from_previous_pass_is_ignored() -> None:
    game = _game(fall_z_threshold_m=-0.20)
    game.record_instrument_contact(
        InstrumentContact(brick_id="left", pass_index=0, hitter="left")
    )
    game.step(0.1, {"left": (-0.05, 0.10, -0.21)})
    game.acknowledge_recycle("left", next_pass_index=1)

    stale = game.record_instrument_contact(
        InstrumentContact(brick_id="left", pass_index=0, hitter="right")
    )

    assert stale.is_empty
    assert game.snapshot("left").state is BrickState.APPROACHING


def test_unhit_brick_recycles_at_lane_end_without_gravity_or_haptics() -> None:
    specs = (
        BrickSpec(
            brick_id="left",
            lane="left",
            spawn_position_m=(-0.05, -0.09, -0.03),
            approach_velocity_m_s=(0.0, -0.05, 0.0),
            approach_end_y_m=-0.10,
        ),
        _specs()[1],
    )
    game = TwoLaneBrickStateMachine(specs)

    update = game.step(0.5)

    left_commands = [
        command for command in update.commands if command.brick_id == "left"
    ]
    assert len(left_commands) == 1
    assert isinstance(left_commands[0], RecycleRequest)
    assert left_commands[0].gravity_enabled is False
    assert left_commands[0].scripted_motion_enabled is True
    assert not update.haptic_events
    assert update.state_events[0].reason == "missed"
    assert game.snapshot("left").state is BrickState.RECYCLE_READY


def test_course_and_configuration_validation_fail_closed() -> None:
    with pytest.raises(ValueError, match="left and right"):
        TwoLaneBrickStateMachine((_specs()[0],))
    with pytest.raises(ValueError, match="unique"):
        TwoLaneBrickStateMachine((_specs()[0], _specs()[0], _specs()[1]))
    with pytest.raises(ValueError, match="decreasing Y"):
        BrickSpec(
            brick_id="bad",
            lane="left",
            spawn_position_m=(-0.05, 0.2, 0.0),
            approach_velocity_m_s=(0.0, 0.01, 0.0),
            approach_end_y_m=-0.1,
        )
    with pytest.raises(ValueError, match="between zero and one"):
        BrickGameConfig(haptic_amplitude=1.1)


def test_step_rejects_invalid_time_and_unknown_observed_bricks() -> None:
    game = _game()

    with pytest.raises(ValueError, match="positive"):
        game.step(0.0)
    with pytest.raises(KeyError, match="unknown"):
        game.step(0.1, {"missing": (0.0, 0.0, 0.0)})
