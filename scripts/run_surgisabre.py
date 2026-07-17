#!/usr/bin/env python3
"""Run the pinned Isaac Lab teleop agent with SurgiSabre runtime hooks."""

from __future__ import annotations

import importlib.util
import os
import platform
import re
import signal
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

from surgisabre import SessionTelemetryRecorder
from surgisabre.course import (
    BRICK_PASS_RANDOMISATION_ALGORITHM,
)
from surgisabre.layout import (
    PURE_TELEOP_ABSOLUTE_HINGED_RETARGETING_ENABLED,
    PURE_TELEOP_ABSOLUTE_TRIGGER_JAW_ENABLED,
    PURE_TELEOP_ARM_CLUTCH_ENABLED,
    PURE_TELEOP_ARM_CLUTCH_THRESHOLD,
    PURE_TELEOP_AXIAL_TRANSLATION_SCALE,
    PURE_TELEOP_BRICK_APPROACH_SPEEDS_M_S,
    PURE_TELEOP_BRICK_COLOURS,
    PURE_TELEOP_BRICK_CONTACT_FORCE_THRESHOLD_N,
    PURE_TELEOP_BRICK_FALL_TIMEOUT_S,
    PURE_TELEOP_BRICK_FALL_Z_M,
    PURE_TELEOP_BRICK_HAPTIC_DURATION_S,
    PURE_TELEOP_BRICK_HAPTIC_FREQUENCY_HZ,
    PURE_TELEOP_BRICK_HAPTIC_INTENSITY,
    PURE_TELEOP_BRICK_HIT_SPEED_M_S,
    PURE_TELEOP_BRICK_IDS,
    PURE_TELEOP_BRICK_LANES,
    PURE_TELEOP_BRICK_LAYOUT_REVISION,
    PURE_TELEOP_BRICK_MASS_KG,
    PURE_TELEOP_BRICK_MISS_Y_M,
    PURE_TELEOP_BRICK_PRIM_NAMES,
    PURE_TELEOP_BRICK_PSM_CONTACT_FILTERS,
    PURE_TELEOP_BRICK_RANDOM_COLOURS,
    PURE_TELEOP_BRICK_RANDOM_HEIGHTS_M,
    PURE_TELEOP_BRICK_RANDOM_SPEEDS_M_S,
    PURE_TELEOP_BRICK_SIZES_M,
    PURE_TELEOP_BRICK_START_POSITIONS_W,
    PURE_TELEOP_BRICKS_ENABLED,
    PURE_TELEOP_CONTROLLER_TRANSLATION_ENABLED,
    PURE_TELEOP_DECIMATION,
    PURE_TELEOP_JAW_CLOSE_TIME_S,
    PURE_TELEOP_JAW_CLUTCH_ENABLED,
    PURE_TELEOP_JAW_COLLISION_PHYSICS_ENABLED,
    PURE_TELEOP_JAW_VELOCITY_LIMIT_RAD_S,
    PURE_TELEOP_NEEDLE_TASK_ENABLED,
    PURE_TELEOP_PHYSICS_DT_S,
    PURE_TELEOP_PSM_CONTACT_REPORTING_ENABLED,
    PURE_TELEOP_PSM_GRAVITY_ENABLED,
    PURE_TELEOP_PSM_INSERTION_JOINT_LOWER_M,
    PURE_TELEOP_PSM_INSERTION_JOINT_UPPER_M,
    PURE_TELEOP_PSM_TOOL_RADIUS_OFFSET_M,
    PURE_TELEOP_RENDER_INTERVAL,
    PURE_TELEOP_RETARGETING_MODE,
    PURE_TELEOP_SABRE_MAX_SHAFT_LENGTH_M,
    PURE_TELEOP_SABRE_MIN_SHAFT_LENGTH_M,
    PURE_TELEOP_SABRE_PITCH_LIMIT_RAD,
    PURE_TELEOP_SABRE_POLE_HORIZONTAL_NORM_THRESHOLD,
    PURE_TELEOP_SABRE_REACQUISITION_ORIENTATION_STEP_LIMIT_RAD,
    PURE_TELEOP_SABRE_SHAFT_LENGTH_M,
    PURE_TELEOP_SABRE_YAW_LIMIT_RAD,
    PURE_TELEOP_SUTURE_PAD_ENABLED,
    PURE_TELEOP_TRANSLATION_SCALE,
    PURE_TELEOP_TRIGGER_JAW_CONTROL_ENABLED,
)
from surgisabre.profiles import (
    DEFAULT_RUNTIME_PROFILE,
    get_runtime_profile,
)
from surgisabre.runtime import IsaacLabEvidenceInstrumentation


def xr_anchor_position() -> tuple[float, float, float]:
    """Read the project XR anchor position from the launch environment."""
    raw_value = os.environ["SURGISABRE_XR_ANCHOR_POS"]
    try:
        values = tuple(float(value.strip()) for value in raw_value.split(","))
    except ValueError as error:
        raise RuntimeError(f"invalid SURGISABRE_XR_ANCHOR_POS: {raw_value!r}") from error
    if len(values) != 3:
        raise RuntimeError("SURGISABRE_XR_ANCHOR_POS must contain exactly three comma-separated values")
    return values


def xr_near_plane_m() -> float:
    """Read and validate the close-view XR near plane."""
    raw_value = os.environ["SURGISABRE_XR_NEAR_PLANE_M"]
    try:
        value = float(raw_value)
    except ValueError as error:
        raise RuntimeError(f"invalid SURGISABRE_XR_NEAR_PLANE_M: {raw_value!r}") from error
    if not 0.01 <= value <= 0.15:
        raise RuntimeError("SURGISABRE_XR_NEAR_PLANE_M must be between 0.01 and 0.15 metres")
    return value


def isaac_sim_version(lab_root: Path) -> str:
    """Read the release version from the standalone Isaac Sim runtime."""

    runtime_root = Path(os.environ.get("ISAAC_SIM_ROOT", lab_root / "_isaac_sim")).resolve()
    version_file = runtime_root / "VERSION"
    raw_version = version_file.read_text(encoding="utf-8").strip()
    match = re.match(r"^(\d+\.\d+\.\d+)(?:[-+].*)?$", raw_version)
    if match is None:
        raise RuntimeError(f"unrecognised Isaac Sim version in {version_file}: {raw_version!r}")
    return match.group(1)


def main() -> None:
    lab_root = Path(os.environ["ISAACLAB_ROOT"]).resolve()
    source = lab_root / "scripts/environments/teleoperation/teleop_se3_agent.py"
    spec = importlib.util.spec_from_file_location("pinned_isaaclab_teleop_agent", source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load pinned teleoperation runner: {source}")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    import isaaclab
    import isaacteleop

    recorder = SessionTelemetryRecorder.from_environment()
    runtime_profile = get_runtime_profile(
        os.environ.get("SURGISABRE_RUNTIME_PROFILE", DEFAULT_RUNTIME_PROFILE)
    )
    xr_anchor_pos = xr_anchor_position()
    near_plane_m = xr_near_plane_m()
    lab_commit = subprocess.run(
        ["git", "-C", str(lab_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    recorder.record_runtime_identity(
        source="isaac",
        identity={
            "runtime_profile": runtime_profile.name,
            "architecture": platform.machine(),
            "python_version": ".".join(str(part) for part in sys.version_info[:3]),
            "isaac_sim_version": isaac_sim_version(lab_root),
            "isaac_lab_version": isaaclab.__version__,
            "isaac_lab_distribution_version": version("isaaclab"),
            "isaacteleop_version": version("isaacteleop"),
            "isaacteleop_provenance_commit": isaacteleop.__provenance_commit__,
            "isaacteleop_integration_commit": isaacteleop.__integration_commit__,
            "isaac_lab_commit": lab_commit,
            "task": str(runner.args_cli.task),
            "teleop_device": str(runner.args_cli.teleop_device),
            "compute_device": str(runner.args_cli.device),
            "xr": bool(runner.args_cli.xr),
            "pure_teleop": True,
            "pure_teleop_physics_dt_s": PURE_TELEOP_PHYSICS_DT_S,
            "pure_teleop_decimation": PURE_TELEOP_DECIMATION,
            "pure_teleop_render_interval": PURE_TELEOP_RENDER_INTERVAL,
            "pure_teleop_jaw_close_time_s": PURE_TELEOP_JAW_CLOSE_TIME_S,
            "pure_teleop_jaw_velocity_limit_rad_s": PURE_TELEOP_JAW_VELOCITY_LIMIT_RAD_S,
            "pure_teleop_jaw_collision_physics_enabled": PURE_TELEOP_JAW_COLLISION_PHYSICS_ENABLED,
            "pure_teleop_needle_task_enabled": PURE_TELEOP_NEEDLE_TASK_ENABLED,
            "pure_teleop_suture_pad_enabled": PURE_TELEOP_SUTURE_PAD_ENABLED,
            "pure_teleop_psm_contact_reporting_enabled": PURE_TELEOP_PSM_CONTACT_REPORTING_ENABLED,
            "pure_teleop_psm_gravity_enabled": PURE_TELEOP_PSM_GRAVITY_ENABLED,
            "pure_teleop_trigger_jaw_control_enabled": PURE_TELEOP_TRIGGER_JAW_CONTROL_ENABLED,
            "pure_teleop_controller_translation_scale": PURE_TELEOP_TRANSLATION_SCALE,
            "pure_teleop_absolute_hinged_retargeting_enabled": (
                PURE_TELEOP_ABSOLUTE_HINGED_RETARGETING_ENABLED
            ),
            "pure_teleop_controller_translation_enabled": (
                PURE_TELEOP_CONTROLLER_TRANSLATION_ENABLED
            ),
            "pure_teleop_arm_clutch_enabled": PURE_TELEOP_ARM_CLUTCH_ENABLED,
            "pure_teleop_arm_clutch_threshold": PURE_TELEOP_ARM_CLUTCH_THRESHOLD,
            "pure_teleop_axial_translation_scale": PURE_TELEOP_AXIAL_TRANSLATION_SCALE,
            "pure_teleop_jaw_clutch_enabled": PURE_TELEOP_JAW_CLUTCH_ENABLED,
            "pure_teleop_absolute_trigger_jaw_enabled": (
                PURE_TELEOP_ABSOLUTE_TRIGGER_JAW_ENABLED
            ),
            "pure_teleop_psm_insertion_joint_lower_m": (
                PURE_TELEOP_PSM_INSERTION_JOINT_LOWER_M
            ),
            "pure_teleop_psm_insertion_joint_upper_m": (
                PURE_TELEOP_PSM_INSERTION_JOINT_UPPER_M
            ),
            "pure_teleop_psm_tool_radius_offset_m": PURE_TELEOP_PSM_TOOL_RADIUS_OFFSET_M,
            "pure_teleop_sabre_shaft_length_m": PURE_TELEOP_SABRE_SHAFT_LENGTH_M,
            "pure_teleop_sabre_min_shaft_length_m": PURE_TELEOP_SABRE_MIN_SHAFT_LENGTH_M,
            "pure_teleop_sabre_max_shaft_length_m": PURE_TELEOP_SABRE_MAX_SHAFT_LENGTH_M,
            "pure_teleop_sabre_yaw_limit_rad": PURE_TELEOP_SABRE_YAW_LIMIT_RAD,
            "pure_teleop_sabre_pitch_limit_rad": PURE_TELEOP_SABRE_PITCH_LIMIT_RAD,
            "pure_teleop_sabre_pole_horizontal_norm_threshold": (
                PURE_TELEOP_SABRE_POLE_HORIZONTAL_NORM_THRESHOLD
            ),
            "pure_teleop_sabre_reacquisition_orientation_step_limit_rad": (
                PURE_TELEOP_SABRE_REACQUISITION_ORIENTATION_STEP_LIMIT_RAD
            ),
            "pure_teleop_retargeting_mode": PURE_TELEOP_RETARGETING_MODE,
            "pure_teleop_bricks_enabled": PURE_TELEOP_BRICKS_ENABLED,
            "pure_teleop_brick_layout_revision": PURE_TELEOP_BRICK_LAYOUT_REVISION,
            "pure_teleop_brick_ids": list(PURE_TELEOP_BRICK_IDS),
            "pure_teleop_brick_lanes": dict(PURE_TELEOP_BRICK_LANES),
            "pure_teleop_brick_prim_names": dict(PURE_TELEOP_BRICK_PRIM_NAMES),
            "pure_teleop_brick_sizes_m": {
                side: list(size) for side, size in PURE_TELEOP_BRICK_SIZES_M.items()
            },
            "pure_teleop_brick_mass_kg": PURE_TELEOP_BRICK_MASS_KG,
            "pure_teleop_brick_start_positions_w": {
                side: list(position)
                for side, position in PURE_TELEOP_BRICK_START_POSITIONS_W.items()
            },
            "pure_teleop_brick_colours": {
                side: list(colour) for side, colour in PURE_TELEOP_BRICK_COLOURS.items()
            },
            "pure_teleop_brick_psm_contact_filters": {
                side: list(filters)
                for side, filters in PURE_TELEOP_BRICK_PSM_CONTACT_FILTERS.items()
            },
            "pure_teleop_brick_approach_speeds_m_s": dict(
                PURE_TELEOP_BRICK_APPROACH_SPEEDS_M_S
            ),
            "pure_teleop_brick_contact_force_threshold_n": (
                PURE_TELEOP_BRICK_CONTACT_FORCE_THRESHOLD_N
            ),
            "pure_teleop_brick_miss_y_m": PURE_TELEOP_BRICK_MISS_Y_M,
            "pure_teleop_brick_fall_z_m": PURE_TELEOP_BRICK_FALL_Z_M,
            "pure_teleop_brick_fall_timeout_s": PURE_TELEOP_BRICK_FALL_TIMEOUT_S,
            "pure_teleop_brick_approach_gravity_enabled": False,
            "pure_teleop_brick_first_hit_enables_gravity": True,
            "pure_teleop_brick_miss_recycle_enables_gravity": False,
            "pure_teleop_brick_haptic_intensity": PURE_TELEOP_BRICK_HAPTIC_INTENSITY,
            "pure_teleop_brick_haptic_duration_s": PURE_TELEOP_BRICK_HAPTIC_DURATION_S,
            "pure_teleop_brick_haptic_frequency_hz": (
                PURE_TELEOP_BRICK_HAPTIC_FREQUENCY_HZ
            ),
            "pure_teleop_brick_hit_speed_m_s": PURE_TELEOP_BRICK_HIT_SPEED_M_S,
            "pure_teleop_brick_randomisation_algorithm": (
                BRICK_PASS_RANDOMISATION_ALGORITHM
            ),
            "pure_teleop_brick_random_speeds_m_s": list(
                PURE_TELEOP_BRICK_RANDOM_SPEEDS_M_S
            ),
            "pure_teleop_brick_random_heights_m": list(
                PURE_TELEOP_BRICK_RANDOM_HEIGHTS_M
            ),
            "pure_teleop_brick_random_colours": [
                list(colour) for colour in PURE_TELEOP_BRICK_RANDOM_COLOURS
            ],
            "pure_teleop_score_enabled": PURE_TELEOP_BRICKS_ENABLED,
            "pure_teleop_score_success_transition": (
                "approaching_to_falling_instrument_hit"
            ),
            "pure_teleop_score_failure_transition": (
                "approaching_to_recycle_ready_missed"
            ),
            "live_scene_dressing": True,
            "xr_anchor_pos": list(xr_anchor_pos),
            "xr_near_plane_m": near_plane_m,
        },
    )
    instrumentation = IsaacLabEvidenceInstrumentation(
        recorder,
        xr_enabled=bool(runner.args_cli.xr),
        xr_anchor_pos=xr_anchor_pos if runner.args_cli.xr else None,
        xr_near_plane_m=near_plane_m if runner.args_cli.xr else None,
        pure_teleop=True,
        live_scene_dressing=True,
    )
    instrumentation.install(runner)

    shutdown_reason = "runner_returned"

    def handle_shutdown(signum: int, _frame: object) -> None:
        nonlocal shutdown_reason
        shutdown_reason = signal.Signals(signum).name.lower()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    terminal_status = "clean"
    try:
        runner.main()
        instrumentation.raise_if_runner_failed()
    except KeyboardInterrupt:
        shutdown_reason = "keyboard_interrupt"
    except SystemExit as error:
        exit_code = error.code if isinstance(error.code, int) else 0
        if exit_code != 0:
            terminal_status = "error"
            shutdown_reason = f"system_exit_{exit_code}"
            raise
    except BaseException as error:
        terminal_status = "error"
        shutdown_reason = type(error).__name__
        raise
    finally:
        recorder.record_trace_terminal(
            source="isaac",
            status=terminal_status,
            reason=shutdown_reason,
        )
        instrumentation.close()
        runner.simulation_app.close()


if __name__ == "__main__":
    main()
