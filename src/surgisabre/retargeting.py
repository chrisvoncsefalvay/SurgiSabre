"""Application-local absolute hinged retargeting for pure dVRK teleoperation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

_MIN_QUATERNION_NORM = 1.0e-9
_HOME_GEOMETRY_TOLERANCE_M = 1.0e-5


def _finite_vector(value: Any, length: int, name: str) -> np.ndarray:
    vector = np.asarray(value, dtype=np.float64)
    if vector.shape != (length,) or not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must be a finite vector with shape ({length},)")
    return vector.copy()


def _normalise_quaternion_xyzw(value: Any, name: str) -> np.ndarray:
    quaternion = _finite_vector(value, 4, name)
    scale = float(np.max(np.abs(quaternion)))
    if scale == 0.0:
        raise ValueError(f"{name} must be non-zero")
    scaled_norm = float(np.linalg.norm(quaternion / scale))
    if not np.isfinite(scaled_norm) or scale < _MIN_QUATERNION_NORM / scaled_norm:
        raise ValueError(f"{name} must be normalisable")
    return quaternion / (scale * scaled_norm)


def _quaternion_multiply_xyzw(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    return np.asarray(
        (
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
            lw * rw - lx * rx - ly * ry - lz * rz,
        ),
        dtype=np.float64,
    )


def _quaternion_conjugate_xyzw(quaternion: np.ndarray) -> np.ndarray:
    return np.asarray(
        (-quaternion[0], -quaternion[1], -quaternion[2], quaternion[3]),
        dtype=np.float64,
    )


def _rotate_vector_xyzw(quaternion: np.ndarray, vector: np.ndarray) -> np.ndarray:
    imaginary = quaternion[:3]
    twice_cross = 2.0 * np.cross(imaginary, vector)
    return vector + quaternion[3] * twice_cross + np.cross(imaginary, twice_cross)


def _rotation_between_unit_vectors_xyzw(
    source: np.ndarray,
    target: np.ndarray,
    preferred_adjustment_xyzw: np.ndarray | None = None,
) -> np.ndarray:
    dot = float(np.clip(np.dot(source, target), -1.0, 1.0))
    if dot > 1.0 - 1.0e-12:
        return np.asarray((0.0, 0.0, 0.0, 1.0), dtype=np.float64)
    if dot < -1.0 + 1.0e-12:
        axis: np.ndarray | None = None
        if preferred_adjustment_xyzw is not None:
            preferred_axis = preferred_adjustment_xyzw[:3]
            projected_axis = preferred_axis - source * float(
                np.dot(preferred_axis, source)
            )
            projected_norm = float(np.linalg.norm(projected_axis))
            if projected_norm > 1.0e-12:
                axis = projected_axis / projected_norm
        reference = (
            np.asarray((1.0, 0.0, 0.0), dtype=np.float64)
            if abs(source[0]) < 0.9
            else np.asarray((0.0, 1.0, 0.0), dtype=np.float64)
        )
        if axis is None:
            axis = np.cross(source, reference)
            axis /= np.linalg.norm(axis)
        return np.asarray((*axis, 0.0), dtype=np.float64)
    quaternion = np.asarray(
        (*np.cross(source, target), 1.0 + dot),
        dtype=np.float64,
    )
    return _normalise_quaternion_xyzw(quaternion, "direction adjustment")


def _unwrap_angle_near(angle: float, reference: float) -> float:
    """Return one equivalent angle on the continuous branch nearest reference."""
    raw_delta = angle - reference
    delta = (raw_delta + math.pi) % (2.0 * math.pi) - math.pi
    if math.isclose(delta, -math.pi, abs_tol=1.0e-12) and raw_delta > 0.0:
        delta = math.pi
    return reference + delta


def _proximal_direction(yaw: float, pitch: float) -> np.ndarray:
    return np.asarray(
        (
            math.sin(yaw) * math.cos(pitch),
            -math.sin(pitch),
            -math.cos(yaw) * math.cos(pitch),
        ),
        dtype=np.float64,
    )


def _limit_unit_direction_step(
    source: np.ndarray,
    target: np.ndarray,
    maximum_angle_rad: float,
) -> tuple[np.ndarray, bool]:
    """Advance from source towards target by one bounded great-circle step."""
    dot = float(np.clip(np.dot(source, target), -1.0, 1.0))
    angle = math.acos(dot)
    if angle <= maximum_angle_rad + 1.0e-12:
        return target.copy(), True
    axis = np.cross(source, target)
    axis_norm = float(np.linalg.norm(axis))
    if axis_norm <= 1.0e-12:
        reference = (
            np.asarray((1.0, 0.0, 0.0), dtype=np.float64)
            if abs(source[0]) < 0.9
            else np.asarray((0.0, 1.0, 0.0), dtype=np.float64)
        )
        axis = np.cross(source, reference)
        axis_norm = float(np.linalg.norm(axis))
    axis /= axis_norm
    cosine = math.cos(maximum_angle_rad)
    sine = math.sin(maximum_angle_rad)
    limited = (
        source * cosine
        + np.cross(axis, source) * sine
        + axis * float(np.dot(axis, source)) * (1.0 - cosine)
    )
    limited /= np.linalg.norm(limited)
    return limited, False


@dataclass(frozen=True)
class AbsoluteHingedPoseConfig:
    """Geometry and proximal limits for one controller-driven PSM shaft."""

    pivot_position_w: tuple[float, float, float]
    home_position_w: tuple[float, float, float]
    home_orientation_xyzw: tuple[float, float, float, float]
    shaft_length_m: float
    shaft_length_min_m: float = 0.0593
    shaft_length_max_m: float = 0.2428
    axial_translation_scale: float = 1.0
    clutch_threshold: float = 0.5
    base_orientation_xyzw: tuple[float, float, float, float] = (
        0.0,
        0.0,
        0.0,
        1.0,
    )
    tool_tip_axis: tuple[float, float, float] = (0.0, 0.0, -1.0)
    yaw_limit_rad: float = math.pi
    pitch_limit_rad: float = math.pi / 2.0
    pole_horizontal_norm_threshold: float = 0.02
    reacquisition_orientation_step_limit_rad: float = math.pi / 4.0


class AbsoluteHingedPoseStateMachine:
    """Map a clutched OpenXR grip pose onto an RCM-constrained PSM shaft.

    Squeeze is a hold-to-move arm clutch. Its first valid engaged sample
    registers the current controller pose to the exact held tool pose and is a
    no-op. While engaged, orientation remains an absolute rigid registration
    and only controller translation collinear with the current shaft changes
    insertion. Clutch release, tracking loss and an inactive session hold the
    exact pose and require a fresh no-jump registration. Reset restores home.
    """

    def __init__(self, config: AbsoluteHingedPoseConfig) -> None:
        self._pivot = _finite_vector(
            config.pivot_position_w,
            3,
            "pivot_position_w",
        )
        self._home_position = _finite_vector(
            config.home_position_w,
            3,
            "home_position_w",
        )
        self._home_orientation = _normalise_quaternion_xyzw(
            config.home_orientation_xyzw,
            "home_orientation_xyzw",
        )
        self._base_orientation = _normalise_quaternion_xyzw(
            config.base_orientation_xyzw,
            "base_orientation_xyzw",
        )
        self._controller_to_tool: np.ndarray | None = None
        self._last_controller_position: np.ndarray | None = None
        self._engaged = False
        self._tool_tip_axis = _finite_vector(
            config.tool_tip_axis,
            3,
            "tool_tip_axis",
        )
        axis_norm = float(np.linalg.norm(self._tool_tip_axis))
        if axis_norm <= 0.0:
            raise ValueError("tool_tip_axis must be non-zero")
        self._tool_tip_axis /= axis_norm
        self._home_shaft_length_m = float(config.shaft_length_m)
        if (
            not np.isfinite(self._home_shaft_length_m)
            or self._home_shaft_length_m <= 0.0
        ):
            raise ValueError("shaft_length_m must be finite and positive")
        self._shaft_length_min_m = float(config.shaft_length_min_m)
        self._shaft_length_max_m = float(config.shaft_length_max_m)
        if not np.isfinite(self._shaft_length_min_m) or not np.isfinite(
            self._shaft_length_max_m
        ):
            raise ValueError("shaft length bounds must be finite")
        if not (
            0.0
            < self._shaft_length_min_m
            <= self._home_shaft_length_m
            <= self._shaft_length_max_m
        ):
            raise ValueError(
                "shaft lengths must satisfy 0 < minimum <= home <= maximum"
            )
        self._shaft_length_m = self._home_shaft_length_m
        self._axial_translation_scale = float(config.axial_translation_scale)
        if (
            not np.isfinite(self._axial_translation_scale)
            or self._axial_translation_scale <= 0.0
        ):
            raise ValueError("axial_translation_scale must be finite and positive")
        self._clutch_threshold = float(config.clutch_threshold)
        if not np.isfinite(self._clutch_threshold) or not (
            0.0 <= self._clutch_threshold <= 1.0
        ):
            raise ValueError("clutch_threshold must be finite and in [0, 1]")
        self._yaw_limit_rad = float(config.yaw_limit_rad)
        self._pitch_limit_rad = float(config.pitch_limit_rad)
        if not np.isfinite(self._yaw_limit_rad) or not (
            0.0 < self._yaw_limit_rad <= math.pi
        ):
            raise ValueError("yaw_limit_rad must be finite and in (0, pi]")
        if not np.isfinite(self._pitch_limit_rad) or not (
            0.0 < self._pitch_limit_rad <= math.pi / 2.0
        ):
            raise ValueError("pitch_limit_rad must be finite and in (0, pi/2]")
        self._pole_horizontal_norm_threshold = float(
            config.pole_horizontal_norm_threshold
        )
        if not np.isfinite(self._pole_horizontal_norm_threshold) or not (
            0.0 < self._pole_horizontal_norm_threshold < 1.0
        ):
            raise ValueError(
                "pole_horizontal_norm_threshold must be finite and in (0, 1)"
            )
        self._reacquisition_orientation_step_limit_rad = float(
            config.reacquisition_orientation_step_limit_rad
        )
        if not np.isfinite(self._reacquisition_orientation_step_limit_rad) or not (
            0.0 < self._reacquisition_orientation_step_limit_rad <= math.pi
        ):
            raise ValueError(
                "reacquisition_orientation_step_limit_rad must be finite and in "
                "(0, pi]"
            )

        home_direction_w = _rotate_vector_xyzw(
            self._home_orientation,
            self._tool_tip_axis,
        )
        expected_home = self._pivot + self._home_shaft_length_m * home_direction_w
        home_error_m = float(np.linalg.norm(expected_home - self._home_position))
        if home_error_m > _HOME_GEOMETRY_TOLERANCE_M:
            raise ValueError(
                "home pose is inconsistent with the configured pivot, shaft length "
                f"and tool axis by {home_error_m:.9f} m"
            )
        home_direction_b = _rotate_vector_xyzw(
            _quaternion_conjugate_xyzw(self._base_orientation),
            home_direction_w,
        )
        home_yaw, home_pitch, home_at_pole = self._requested_proximal_angles(
            home_direction_b,
            reference_yaw=0.0,
        )
        if abs(home_yaw) > self._yaw_limit_rad + 1.0e-12 or abs(
            home_pitch
        ) > self._pitch_limit_rad + 1.0e-12:
            raise ValueError(
                "home pose exceeds the configured proximal yaw or pitch limits"
            )

        self._home_pose = np.concatenate(
            (self._home_position, self._home_orientation)
        ).astype(np.float32)
        self._last_pose = self._home_pose.copy()
        self._home_proximal_angles_rad = (home_yaw, home_pitch)
        self._home_at_pole = home_at_pole
        self._last_requested_proximal_angles_rad = self._home_proximal_angles_rad
        self._last_constrained_proximal_angles_rad = self._home_proximal_angles_rad
        self._last_hinge_residual_m = 0.0
        self._last_axial_controller_delta_m = 0.0
        self._last_axial_tool_delta_m = 0.0
        self._pole_guard_active = home_at_pole
        self._reacquisition_slew_active = False

    @property
    def pose(self) -> np.ndarray:
        return self._last_pose.copy()

    @property
    def pivot_position_w(self) -> np.ndarray:
        return self._pivot.copy()

    @property
    def shaft_length_m(self) -> float:
        return self._shaft_length_m

    @property
    def shaft_length_bounds_m(self) -> tuple[float, float]:
        return self._shaft_length_min_m, self._shaft_length_max_m

    @property
    def axial_translation_scale(self) -> float:
        return self._axial_translation_scale

    @property
    def clutch_threshold(self) -> float:
        return self._clutch_threshold

    @property
    def controller_translation_used(self) -> bool:
        return True

    @property
    def squeeze_controls_pose(self) -> bool:
        return True

    @property
    def engaged(self) -> bool:
        return self._engaged

    @property
    def registered(self) -> bool:
        return self._controller_to_tool is not None

    @property
    def last_requested_proximal_angles_rad(self) -> tuple[float, float]:
        return self._last_requested_proximal_angles_rad

    @property
    def last_constrained_proximal_angles_rad(self) -> tuple[float, float]:
        return self._last_constrained_proximal_angles_rad

    @property
    def last_hinge_residual_m(self) -> float:
        return self._last_hinge_residual_m

    @property
    def last_axial_controller_delta_m(self) -> float:
        return self._last_axial_controller_delta_m

    @property
    def last_axial_tool_delta_m(self) -> float:
        return self._last_axial_tool_delta_m

    @property
    def reacquisition_slew_active(self) -> bool:
        return self._reacquisition_slew_active

    @property
    def reacquisition_orientation_step_limit_rad(self) -> float:
        return self._reacquisition_orientation_step_limit_rad

    @property
    def pole_horizontal_norm_threshold(self) -> float:
        return self._pole_horizontal_norm_threshold

    def _disengage(self) -> None:
        self._engaged = False
        self._controller_to_tool = None
        self._last_controller_position = None
        self._last_axial_controller_delta_m = 0.0
        self._last_axial_tool_delta_m = 0.0
        self._reacquisition_slew_active = False

    def reset(self) -> np.ndarray:
        self._last_pose = self._home_pose.copy()
        self._shaft_length_m = self._home_shaft_length_m
        self._disengage()
        self._last_requested_proximal_angles_rad = self._home_proximal_angles_rad
        self._last_constrained_proximal_angles_rad = self._home_proximal_angles_rad
        self._last_hinge_residual_m = 0.0
        self._pole_guard_active = self._home_at_pole
        self._reacquisition_slew_active = False
        return self.pose

    def _requested_proximal_angles(
        self,
        direction_b: np.ndarray,
        *,
        reference_yaw: float,
    ) -> tuple[float, float, bool]:
        requested_pitch = -math.asin(
            float(np.clip(direction_b[1], -1.0, 1.0))
        )
        horizontal_norm = math.hypot(
            float(direction_b[0]),
            float(direction_b[2]),
        )
        pole_guard_active = (
            horizontal_norm < self._pole_horizontal_norm_threshold
        )
        if pole_guard_active:
            requested_yaw = reference_yaw
        else:
            requested_yaw = _unwrap_angle_near(
                math.atan2(float(direction_b[0]), float(-direction_b[2])),
                reference_yaw,
            )
        return requested_yaw, requested_pitch, pole_guard_active

    def _constrain_tool_orientation(
        self,
        tool_quaternion: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        previous_orientation = _normalise_quaternion_xyzw(
            self._last_pose[3:7],
            "previous tool orientation",
        )
        previous_direction_w = _rotate_vector_xyzw(
            previous_orientation,
            self._tool_tip_axis,
        )
        raw_direction_w = _rotate_vector_xyzw(
            tool_quaternion,
            self._tool_tip_axis,
        )
        direction_b = _rotate_vector_xyzw(
            _quaternion_conjugate_xyzw(self._base_orientation),
            raw_direction_w,
        )
        requested_yaw, requested_pitch, pole_guard_active = (
            self._requested_proximal_angles(
                direction_b,
                reference_yaw=self._last_requested_proximal_angles_rad[0],
            )
        )
        if self._pole_guard_active and not pole_guard_active:
            self._reacquisition_slew_active = True
        self._pole_guard_active = pole_guard_active
        desired_yaw = float(
            np.clip(requested_yaw, -self._yaw_limit_rad, self._yaw_limit_rad)
        )
        desired_pitch = float(
            np.clip(
                requested_pitch,
                -self._pitch_limit_rad,
                self._pitch_limit_rad,
            )
        )
        self._last_requested_proximal_angles_rad = (
            requested_yaw,
            requested_pitch,
        )
        constrained_yaw = desired_yaw
        constrained_pitch = desired_pitch
        constrained_direction_b = _proximal_direction(
            constrained_yaw,
            constrained_pitch,
        )
        direction_reached = True
        if self._reacquisition_slew_active:
            previous_yaw, previous_pitch = (
                self._last_constrained_proximal_angles_rad
            )
            previous_direction_b = _proximal_direction(
                previous_yaw,
                previous_pitch,
            )
            constrained_direction_b, direction_reached = (
                _limit_unit_direction_step(
                    previous_direction_b,
                    constrained_direction_b,
                    self._reacquisition_orientation_step_limit_rad,
                )
            )
            constrained_yaw, constrained_pitch, _ = (
                self._requested_proximal_angles(
                    constrained_direction_b,
                    reference_yaw=previous_yaw,
                )
            )
        self._last_constrained_proximal_angles_rad = (
            constrained_yaw,
            constrained_pitch,
        )
        constrained_direction_w = _rotate_vector_xyzw(
            self._base_orientation,
            constrained_direction_b,
        )
        preferred_adjustment = _normalise_quaternion_xyzw(
            _quaternion_multiply_xyzw(
                previous_orientation,
                _quaternion_conjugate_xyzw(tool_quaternion),
            ),
            "preferred direction adjustment",
        )
        direction_adjustment = _rotation_between_unit_vectors_xyzw(
            raw_direction_w,
            constrained_direction_w,
            preferred_adjustment,
        )
        desired_orientation = _normalise_quaternion_xyzw(
            _quaternion_multiply_xyzw(direction_adjustment, tool_quaternion),
            "constrained tool orientation",
        )
        constrained_orientation = desired_orientation
        if self._reacquisition_slew_active:
            transport = _rotation_between_unit_vectors_xyzw(
                previous_direction_w,
                constrained_direction_w,
            )
            transported_orientation = _normalise_quaternion_xyzw(
                _quaternion_multiply_xyzw(transport, previous_orientation),
                "transported previous orientation",
            )
            relative_orientation = _normalise_quaternion_xyzw(
                _quaternion_multiply_xyzw(
                    desired_orientation,
                    _quaternion_conjugate_xyzw(transported_orientation),
                ),
                "reacquisition relative orientation",
            )
            projected_twist = constrained_direction_w * float(
                np.dot(relative_orientation[:3], constrained_direction_w)
            )
            twist = _normalise_quaternion_xyzw(
                np.asarray((*projected_twist, relative_orientation[3])),
                "reacquisition axial twist",
            )
            if twist[3] < 0.0:
                twist = -twist
            signed_twist_angle = 2.0 * math.atan2(
                float(np.dot(twist[:3], constrained_direction_w)),
                float(twist[3]),
            )
            direction_step_angle = math.acos(
                float(
                    np.clip(
                        np.dot(previous_direction_w, constrained_direction_w),
                        -1.0,
                        1.0,
                    )
                )
            )
            cosine_ratio = math.cos(
                self._reacquisition_orientation_step_limit_rad / 2.0
            ) / max(math.cos(direction_step_angle / 2.0), 1.0e-12)
            maximum_twist_angle = 2.0 * math.acos(
                float(np.clip(cosine_ratio, -1.0, 1.0))
            )
            twist_reached = (
                abs(signed_twist_angle) <= maximum_twist_angle + 1.0e-12
            )
            if twist_reached:
                bounded_twist = twist
            else:
                bounded_angle = math.copysign(
                    maximum_twist_angle,
                    signed_twist_angle,
                )
                bounded_twist = np.asarray(
                    (
                        *(
                            constrained_direction_w
                            * math.sin(bounded_angle / 2.0)
                        ),
                        math.cos(bounded_angle / 2.0),
                    ),
                    dtype=np.float64,
                )
            constrained_orientation = _normalise_quaternion_xyzw(
                _quaternion_multiply_xyzw(
                    bounded_twist,
                    transported_orientation,
                ),
                "bounded reacquisition orientation",
            )
            self._reacquisition_slew_active = not (
                direction_reached and twist_reached
            )
        return constrained_orientation, constrained_direction_w

    def step(
        self,
        *,
        controller_position: object | None,
        controller_orientation: object | None,
        squeeze: float | None,
        tracking_valid: bool,
        session_active: bool,
    ) -> np.ndarray:
        try:
            squeeze_value = float(squeeze) if squeeze is not None else None
        except (TypeError, ValueError):
            squeeze_value = None
        if (
            not session_active
            or not tracking_valid
            or squeeze_value is None
            or not np.isfinite(squeeze_value)
            or squeeze_value < self._clutch_threshold
        ):
            self._disengage()
            return self.pose
        try:
            position = _finite_vector(
                controller_position,
                3,
                "controller_position",
            )
            controller_quaternion = _normalise_quaternion_xyzw(
                controller_orientation,
                "controller_orientation",
            )
        except (TypeError, ValueError):
            self._disengage()
            return self.pose
        if not self._engaged:
            held_orientation = _normalise_quaternion_xyzw(
                self._last_pose[3:7],
                "held tool orientation",
            )
            self._controller_to_tool = _normalise_quaternion_xyzw(
                _quaternion_multiply_xyzw(
                    _quaternion_conjugate_xyzw(controller_quaternion),
                    held_orientation,
                ),
                "clutch controller-to-tool registration",
            )
            self._last_controller_position = position
            self._engaged = True
            self._reacquisition_slew_active = False
            return self.pose

        assert self._controller_to_tool is not None
        assert self._last_controller_position is not None
        tool_quaternion = _normalise_quaternion_xyzw(
            _quaternion_multiply_xyzw(
                controller_quaternion,
                self._controller_to_tool,
            ),
            "tool_orientation",
        )
        tool_quaternion, tool_direction = self._constrain_tool_orientation(
            tool_quaternion
        )
        if float(np.dot(tool_quaternion, self._last_pose[3:7])) < 0.0:
            tool_quaternion = -tool_quaternion
        controller_delta = position - self._last_controller_position
        axial_controller_delta = float(np.dot(controller_delta, tool_direction))
        requested_tool_delta = (
            self._axial_translation_scale * axial_controller_delta
        )
        previous_shaft_length = self._shaft_length_m
        self._shaft_length_m = float(
            np.clip(
                previous_shaft_length + requested_tool_delta,
                self._shaft_length_min_m,
                self._shaft_length_max_m,
            )
        )
        self._last_controller_position = position
        self._last_axial_controller_delta_m = axial_controller_delta
        self._last_axial_tool_delta_m = (
            self._shaft_length_m - previous_shaft_length
        )
        tool_position = self._pivot + self._shaft_length_m * tool_direction
        self._last_hinge_residual_m = abs(
            float(np.linalg.norm(tool_position - self._pivot))
            - self._shaft_length_m
        )
        self._last_pose = np.concatenate((tool_position, tool_quaternion)).astype(
            np.float32
        )
        return self.pose


@dataclass(frozen=True)
class DirectTriggerJawConfig:
    jaw_open: tuple[float, float]
    jaw_closed: tuple[float, float]
    initial_closedness: float = 0.0


class DirectTriggerJawStateMachine:
    """Map the absolute Quest trigger directly to the paired jaw targets."""

    def __init__(self, config: DirectTriggerJawConfig) -> None:
        self._jaw_open = _finite_vector(config.jaw_open, 2, "jaw_open")
        self._jaw_closed = _finite_vector(config.jaw_closed, 2, "jaw_closed")
        self._initial_closedness = float(config.initial_closedness)
        if not np.isfinite(self._initial_closedness) or not (
            0.0 <= self._initial_closedness <= 1.0
        ):
            raise ValueError("initial_closedness must be finite and in [0, 1]")
        self._last_targets = self._targets(self._initial_closedness)

    @property
    def targets(self) -> np.ndarray:
        return self._last_targets.copy()

    @property
    def squeeze_controls_jaws(self) -> bool:
        return False

    def _targets(self, closedness: float) -> np.ndarray:
        return np.asarray(
            self._jaw_open
            + float(np.clip(closedness, 0.0, 1.0))
            * (self._jaw_closed - self._jaw_open),
            dtype=np.float32,
        )

    def reset(self) -> np.ndarray:
        self._last_targets = self._targets(self._initial_closedness)
        return self.targets

    def step(
        self,
        *,
        trigger: float | None,
        squeeze: float | None,
        tracking_valid: bool,
        session_active: bool,
        dt_seconds: float,
    ) -> np.ndarray:
        del squeeze, dt_seconds
        if not session_active or not tracking_valid or trigger is None:
            return self.targets
        try:
            trigger_value = float(trigger)
        except (TypeError, ValueError):
            return self.targets
        if not np.isfinite(trigger_value):
            return self.targets
        self._last_targets = self._targets(trigger_value)
        return self.targets


__all__ = [
    "AbsoluteHingedPoseConfig",
    "AbsoluteHingedPoseStateMachine",
    "DirectTriggerJawConfig",
    "DirectTriggerJawStateMachine",
]
