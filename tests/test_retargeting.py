import math
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from surgisabre.retargeting import (  # noqa: E402
    AbsoluteHingedPoseConfig,
    AbsoluteHingedPoseStateMachine,
    DirectTriggerJawConfig,
    DirectTriggerJawStateMachine,
)


def _kernel() -> AbsoluteHingedPoseStateMachine:
    return AbsoluteHingedPoseStateMachine(
        AbsoluteHingedPoseConfig(
            pivot_position_w=(0.0, 0.0, 0.0),
            home_position_w=(0.0, 0.0, -0.2),
            home_orientation_xyzw=(0.0, 0.0, 0.0, 1.0),
            shaft_length_m=0.2,
        )
    )


def _proximal_direction(yaw: float, pitch: float) -> np.ndarray:
    return np.asarray(
        (
            math.sin(yaw) * math.cos(pitch),
            -math.sin(pitch),
            -math.cos(yaw) * math.cos(pitch),
        ),
        dtype=np.float64,
    )


def _orientation_for_direction(direction: np.ndarray) -> tuple[float, ...]:
    source = np.asarray((0.0, 0.0, -1.0), dtype=np.float64)
    target = np.asarray(direction, dtype=np.float64)
    target /= np.linalg.norm(target)
    quaternion = np.asarray(
        (*np.cross(source, target), 1.0 + float(np.dot(source, target))),
        dtype=np.float64,
    )
    quaternion /= np.linalg.norm(quaternion)
    return tuple(float(value) for value in quaternion)


def _orientation_for_yaw(yaw: float) -> tuple[float, float, float, float]:
    half_angle = -yaw / 2.0
    return (0.0, math.sin(half_angle), 0.0, math.cos(half_angle))


def _quaternion_angular_distance(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=np.float64)
    right = np.asarray(right, dtype=np.float64)
    left /= np.linalg.norm(left)
    right /= np.linalg.norm(right)
    dot = abs(float(np.dot(left, right)))
    return 2.0 * math.acos(float(np.clip(dot, -1.0, 1.0)))


def _limited_kernel() -> AbsoluteHingedPoseStateMachine:
    return AbsoluteHingedPoseStateMachine(
        AbsoluteHingedPoseConfig(
            pivot_position_w=(0.0, 0.0, 0.0),
            home_position_w=(0.0, 0.0, -0.2),
            home_orientation_xyzw=(0.0, 0.0, 0.0, 1.0),
            shaft_length_m=0.2,
            yaw_limit_rad=math.radians(85.0),
            pitch_limit_rad=math.radians(48.0),
            pole_horizontal_norm_threshold=0.02,
            reacquisition_orientation_step_limit_rad=math.radians(45.0),
        )
    )


def _step(
    kernel: AbsoluteHingedPoseStateMachine,
    orientation: tuple[float, float, float, float],
    *,
    position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    squeeze: float = 1.0,
) -> np.ndarray:
    return kernel.step(
        controller_position=position,
        controller_orientation=orientation,
        squeeze=squeeze,
        tracking_valid=True,
        session_active=True,
    )


def test_absolute_orientation_places_tip_on_fixed_radius() -> None:
    kernel = _kernel()
    _step(kernel, (0.0, 0.0, 0.0, 1.0))
    half_angle = math.pi / 4.0
    pose = _step(kernel, (0.0, math.sin(half_angle), 0.0, math.cos(half_angle)))

    assert pose[:3] == pytest.approx((-0.2, 0.0, 0.0), abs=1.0e-7)
    assert np.linalg.norm(pose[:3] - kernel.pivot_position_w) == pytest.approx(0.2)
    assert pose[3:7] == pytest.approx((0.0, math.sqrt(0.5), 0.0, math.sqrt(0.5)))


def test_only_controller_translation_along_current_shaft_changes_insertion() -> None:
    kernel = _kernel()
    home = _step(kernel, (0.0, 0.0, 0.0, 1.0))

    advanced = _step(
        kernel,
        (0.0, 0.0, 0.0, 1.0),
        position=(0.0, 0.0, -0.01),
    )
    lateral = _step(
        kernel,
        (0.0, 0.0, 0.0, 1.0),
        position=(0.40, -0.25, -0.01),
    )

    assert home[:3] == pytest.approx((0.0, 0.0, -0.2))
    assert advanced[:3] == pytest.approx((0.0, 0.0, -0.21))
    assert lateral == pytest.approx(advanced)
    assert kernel.shaft_length_m == pytest.approx(0.21)
    assert kernel.last_axial_controller_delta_m == pytest.approx(0.0)
    assert kernel.controller_translation_used is True
    assert kernel.squeeze_controls_pose is True


def test_axial_projection_uses_the_rotated_current_shaft_and_configured_scale() -> None:
    kernel = AbsoluteHingedPoseStateMachine(
        AbsoluteHingedPoseConfig(
            pivot_position_w=(0.0, 0.0, 0.0),
            home_position_w=(0.0, 0.0, -0.2),
            home_orientation_xyzw=(0.0, 0.0, 0.0, 1.0),
            shaft_length_m=0.2,
            axial_translation_scale=2.0,
        )
    )
    identity = (0.0, 0.0, 0.0, 1.0)
    _step(kernel, identity, position=(0.0, 0.0, 0.0))
    half_angle = math.pi / 4.0
    rotated = (0.0, math.sin(half_angle), 0.0, math.cos(half_angle))
    _step(kernel, rotated, position=(0.0, 0.0, 0.0))

    advanced = _step(kernel, rotated, position=(-0.01, 0.0, 0.0))
    lateral = _step(kernel, rotated, position=(-0.01, 0.25, 0.0))

    assert advanced[:3] == pytest.approx((-0.22, 0.0, 0.0), abs=1.0e-7)
    assert lateral == pytest.approx(advanced)
    assert kernel.shaft_length_m == pytest.approx(0.22)
    assert kernel.axial_translation_scale == pytest.approx(2.0)


def test_absolute_orientation_does_not_rebase_between_samples() -> None:
    kernel = _kernel()
    first = _step(kernel, (0.0, 0.0, 0.0, 1.0))
    half_angle = math.pi / 8.0
    second = _step(
        kernel,
        (math.sin(half_angle), 0.0, 0.0, math.cos(half_angle)),
    )

    assert first[:3] == pytest.approx((0.0, 0.0, -0.2))
    assert second[:3] == pytest.approx(
        (0.0, 0.2 * math.sqrt(0.5), -0.2 * math.sqrt(0.5)),
        abs=1.0e-7,
    )
    assert second[3:7] == pytest.approx(
        (math.sin(half_angle), 0.0, 0.0, math.cos(half_angle))
    )


def test_tracking_loss_and_inactive_session_hold_last_complete_pose() -> None:
    kernel = _kernel()
    _step(kernel, (0.0, 0.0, 0.0, 1.0))
    moved = _step(kernel, (0.0, math.sqrt(0.5), 0.0, math.sqrt(0.5)))

    tracking_hold = kernel.step(
        controller_position=None,
        controller_orientation=None,
        squeeze=None,
        tracking_valid=False,
        session_active=True,
    )
    inactive_hold = kernel.step(
        controller_position=(0.0, 0.0, 0.0),
        controller_orientation=(0.0, 0.0, 0.0, 1.0),
        squeeze=1.0,
        tracking_valid=True,
        session_active=False,
    )

    assert tracking_hold == pytest.approx(moved)
    assert inactive_hold == pytest.approx(moved)


def test_tracking_recovery_reclutches_at_the_held_pose_without_a_jump() -> None:
    kernel = _kernel()
    _step(kernel, (0.0, 0.0, 0.0, 1.0), position=(0.1, 0.2, 0.3))
    moved_orientation = (0.0, math.sqrt(0.5), 0.0, math.sqrt(0.5))
    moved = _step(kernel, moved_orientation, position=(0.1, 0.2, 0.3))
    kernel.step(
        controller_position=None,
        controller_orientation=None,
        squeeze=None,
        tracking_valid=False,
        session_active=False,
    )

    recovered = _step(
        kernel,
        (0.0, 0.0, 1.0, 0.0),
        position=(-4.0, 7.0, 2.0),
    )

    assert recovered == pytest.approx(moved)
    assert kernel.engaged is True
    assert kernel.registered is True
    assert kernel.reacquisition_slew_active is False


def test_release_and_reengagement_rebase_without_losing_absolute_orientation() -> None:
    kernel = _kernel()
    identity = (0.0, 0.0, 0.0, 1.0)
    _step(kernel, identity, position=(0.0, 0.0, 0.0))
    advanced = _step(kernel, identity, position=(0.0, 0.0, -0.01))

    released = _step(
        kernel,
        (0.0, 0.0, 1.0, 0.0),
        position=(5.0, -3.0, 2.0),
        squeeze=0.0,
    )
    assert released == pytest.approx(advanced)
    assert kernel.engaged is False
    assert kernel.registered is False

    quarter_turn_z = (0.0, 0.0, math.sqrt(0.5), math.sqrt(0.5))
    reclutched = _step(
        kernel,
        quarter_turn_z,
        position=(5.0, -3.0, 2.0),
    )
    assert reclutched == pytest.approx(advanced)

    angle = math.radians(120.0)
    moved_controller = (0.0, 0.0, math.sin(angle / 2.0), math.cos(angle / 2.0))
    resumed = _step(
        kernel,
        moved_controller,
        position=(5.0, -3.0, 2.0),
    )
    expected_angle = math.radians(30.0)
    assert resumed[3:7] == pytest.approx(
        (
            0.0,
            0.0,
            math.sin(expected_angle / 2.0),
            math.cos(expected_angle / 2.0),
        ),
        abs=1.0e-7,
    )
    assert kernel.shaft_length_m == pytest.approx(0.21)


def test_clutch_threshold_is_inclusive_and_first_engagement_is_a_no_op() -> None:
    kernel = _kernel()
    arbitrary_orientation = (0.4, -0.3, 0.2, 0.8)

    held = _step(
        kernel,
        arbitrary_orientation,
        position=(8.0, -3.0, 4.0),
        squeeze=0.499,
    )
    engaged = _step(
        kernel,
        arbitrary_orientation,
        position=(8.0, -3.0, 4.0),
        squeeze=0.5,
    )

    assert held == pytest.approx((0.0, 0.0, -0.2, 0.0, 0.0, 0.0, 1.0))
    assert engaged == pytest.approx(held)
    assert kernel.engaged is True
    assert kernel.clutch_threshold == pytest.approx(0.5)


def test_asset_derived_insertion_bounds_clip_without_a_reversal_dead_zone() -> None:
    kernel = _kernel()
    identity = (0.0, 0.0, 0.0, 1.0)
    _step(kernel, identity, position=(0.0, 0.0, 0.0))

    maximum = _step(kernel, identity, position=(0.0, 0.0, -1.0))
    still_maximum = _step(kernel, identity, position=(0.0, 0.0, -2.0))
    reversed_from_limit = _step(
        kernel,
        identity,
        position=(0.0, 0.0, -1.99),
    )
    minimum = _step(kernel, identity, position=(0.0, 0.0, 1.0))

    assert kernel.shaft_length_bounds_m == pytest.approx((0.0593, 0.2428))
    assert np.linalg.norm(maximum[:3]) == pytest.approx(0.2428)
    assert still_maximum == pytest.approx(maximum)
    assert np.linalg.norm(reversed_from_limit[:3]) == pytest.approx(0.2328)
    assert np.linalg.norm(minimum[:3]) == pytest.approx(0.0593)


def test_reset_restores_the_exact_home_pose() -> None:
    kernel = _kernel()
    identity = (0.0, 0.0, 0.0, 1.0)
    _step(kernel, identity, position=(0.0, 0.0, 0.0))
    _step(kernel, identity, position=(0.0, 0.0, -0.02))

    assert kernel.reset() == pytest.approx((0.0, 0.0, -0.2, 0.0, 0.0, 0.0, 1.0))
    assert kernel.shaft_length_m == pytest.approx(0.2)
    assert kernel.engaged is False
    assert kernel.registered is False


def test_quaternion_sign_is_continuous() -> None:
    kernel = _kernel()
    first = _step(kernel, (0.0, 0.0, 0.0, 1.0))
    second = _step(kernel, (0.0, 0.0, 0.0, -1.0))

    assert second == pytest.approx(first)


def test_first_valid_sample_registers_to_home_without_a_jump() -> None:
    kernel = _kernel()
    arbitrary_controller_orientation = (0.4, -0.3, 0.2, 0.8)

    first = _step(kernel, arbitrary_controller_orientation)
    second = _step(kernel, arbitrary_controller_orientation)

    assert first == pytest.approx((0.0, 0.0, -0.2, 0.0, 0.0, 0.0, 1.0))
    assert second == pytest.approx(first)
    assert kernel.registered is True


def test_proximal_angles_are_clamped_without_breaking_the_hinge() -> None:
    yaw_limit = math.radians(30.0)
    pitch_limit = math.radians(20.0)
    kernel = AbsoluteHingedPoseStateMachine(
        AbsoluteHingedPoseConfig(
            pivot_position_w=(0.0, 0.0, 0.0),
            home_position_w=(0.0, 0.0, -0.2),
            home_orientation_xyzw=(0.0, 0.0, 0.0, 1.0),
            shaft_length_m=0.2,
            yaw_limit_rad=yaw_limit,
            pitch_limit_rad=pitch_limit,
        )
    )
    _step(kernel, (0.0, 0.0, 0.0, 1.0))
    half_angle = math.pi / 4.0

    pose = _step(
        kernel,
        (0.0, math.sin(half_angle), 0.0, math.cos(half_angle)),
    )

    requested_yaw, requested_pitch = kernel.last_requested_proximal_angles_rad
    constrained_yaw, constrained_pitch = kernel.last_constrained_proximal_angles_rad
    assert abs(requested_yaw) == pytest.approx(math.pi / 2.0)
    assert requested_pitch == pytest.approx(0.0)
    assert abs(constrained_yaw) == pytest.approx(yaw_limit)
    assert constrained_pitch == pytest.approx(0.0)
    assert np.linalg.norm(pose[:3] - kernel.pivot_position_w) == pytest.approx(0.2)
    assert kernel.last_hinge_residual_m <= 1.0e-12


def test_yaw_unwrap_prevents_a_limit_flip_across_the_branch_cut() -> None:
    kernel = _limited_kernel()
    _step(kernel, (0.0, 0.0, 0.0, 1.0))
    before = _step(
        kernel,
        _orientation_for_direction(
            _proximal_direction(math.radians(179.9), 0.0)
        ),
    )
    before_yaw = kernel.last_constrained_proximal_angles_rad[0]
    after = _step(
        kernel,
        _orientation_for_direction(
            _proximal_direction(math.radians(-179.9), 0.0)
        ),
    )
    after_yaw = kernel.last_constrained_proximal_angles_rad[0]

    assert math.degrees(before_yaw) == pytest.approx(85.0)
    assert math.degrees(after_yaw) == pytest.approx(85.0)
    assert np.linalg.norm(after[:3] - before[:3]) <= 1.0e-7


def test_antipodal_direction_projection_preserves_orientation_continuity() -> None:
    kernel = _limited_kernel()
    _step(kernel, (0.0, 0.0, 0.0, 1.0))
    for yaw_degrees in range(5, 265, 5):
        _step(kernel, _orientation_for_yaw(math.radians(yaw_degrees)))

    before = _step(kernel, _orientation_for_yaw(math.radians(264.99)))
    antipodal = _step(kernel, _orientation_for_yaw(math.radians(265.0)))
    after = _step(kernel, _orientation_for_yaw(math.radians(265.01)))

    assert math.degrees(
        _quaternion_angular_distance(before[3:7], antipodal[3:7])
    ) < 0.1
    assert math.degrees(
        _quaternion_angular_distance(antipodal[3:7], after[3:7])
    ) < 0.1
    assert antipodal[:3] == pytest.approx(before[:3], abs=1.0e-7)
    assert after[:3] == pytest.approx(before[:3], abs=1.0e-7)


def test_pole_guard_holds_yaw_and_slews_when_azimuth_becomes_defined() -> None:
    kernel = _limited_kernel()
    _step(kernel, (0.0, 0.0, 0.0, 1.0))
    _step(
        kernel,
        _orientation_for_direction(
            _proximal_direction(math.radians(60.0), math.radians(89.5))
        ),
    )
    first_pole_yaw = kernel.last_requested_proximal_angles_rad[0]
    at_pole = _step(
        kernel,
        _orientation_for_direction(
            _proximal_direction(math.radians(-120.0), math.radians(89.5))
        ),
    )
    second_pole_yaw = kernel.last_requested_proximal_angles_rad[0]
    leaving_pole = _step(
        kernel,
        _orientation_for_direction(
            _proximal_direction(math.radians(-120.0), math.radians(80.0))
        ),
    )
    leaving_pole_yaw = kernel.last_constrained_proximal_angles_rad[0]

    assert first_pole_yaw == pytest.approx(0.0)
    assert second_pole_yaw == pytest.approx(0.0)
    direction_step = 2.0 * math.asin(
        min(
            1.0,
            float(np.linalg.norm(leaving_pole[:3] - at_pole[:3])) / 0.4,
        )
    )
    assert -85.0 < math.degrees(leaving_pole_yaw) < 0.0
    assert math.degrees(direction_step) <= 45.0 + 1.0e-5
    assert kernel.reacquisition_slew_active is True


def test_home_and_reset_angle_state_matches_the_configured_home() -> None:
    home_yaw = math.radians(30.0)
    home_pitch = math.radians(-20.0)
    home_direction = _proximal_direction(home_yaw, home_pitch)
    home_orientation = _orientation_for_direction(home_direction)
    kernel = AbsoluteHingedPoseStateMachine(
        AbsoluteHingedPoseConfig(
            pivot_position_w=(0.0, 0.0, 0.0),
            home_position_w=tuple(0.2 * home_direction),
            home_orientation_xyzw=home_orientation,
            shaft_length_m=0.2,
            yaw_limit_rad=math.radians(85.0),
            pitch_limit_rad=math.radians(48.0),
        )
    )

    assert kernel.last_requested_proximal_angles_rad == pytest.approx(
        (home_yaw, home_pitch)
    )
    _step(kernel, home_orientation)
    _step(kernel, (0.0, 0.0, 0.0, 1.0))
    kernel.reset()

    assert kernel.last_requested_proximal_angles_rad == pytest.approx(
        (home_yaw, home_pitch)
    )
    assert kernel.last_constrained_proximal_angles_rad == pytest.approx(
        (home_yaw, home_pitch)
    )


def test_constructor_rejects_inconsistent_home_geometry() -> None:
    with pytest.raises(ValueError, match="home pose is inconsistent"):
        AbsoluteHingedPoseStateMachine(
            AbsoluteHingedPoseConfig(
                pivot_position_w=(0.0, 0.0, 0.0),
                home_position_w=(0.1, 0.0, -0.2),
                home_orientation_xyzw=(0.0, 0.0, 0.0, 1.0),
                shaft_length_m=0.2,
            )
        )


def test_direct_trigger_jaws_ignore_squeeze_and_track_absolute_trigger() -> None:
    jaws = DirectTriggerJawStateMachine(
        DirectTriggerJawConfig(
            jaw_open=(-0.5, 0.5),
            jaw_closed=(0.0, 0.0),
        )
    )

    half_closed = jaws.step(
        trigger=0.5,
        squeeze=0.0,
        tracking_valid=True,
        session_active=True,
        dt_seconds=0.0,
    )
    closed = jaws.step(
        trigger=1.0,
        squeeze=0.0,
        tracking_valid=True,
        session_active=True,
        dt_seconds=0.1,
    )

    assert half_closed == pytest.approx((-0.25, 0.25))
    assert closed == pytest.approx((0.0, 0.0))
    assert jaws.squeeze_controls_jaws is False


def test_direct_trigger_jaws_hold_on_tracking_loss() -> None:
    jaws = DirectTriggerJawStateMachine(
        DirectTriggerJawConfig(
            jaw_open=(-0.5, 0.5),
            jaw_closed=(0.0, 0.0),
        )
    )
    commanded = jaws.step(
        trigger=0.6,
        squeeze=0.0,
        tracking_valid=True,
        session_active=True,
        dt_seconds=0.0,
    )

    held = jaws.step(
        trigger=0.0,
        squeeze=1.0,
        tracking_valid=False,
        session_active=True,
        dt_seconds=1.0,
    )

    assert held == pytest.approx(commanded)
