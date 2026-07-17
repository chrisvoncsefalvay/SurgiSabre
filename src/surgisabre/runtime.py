"""Opt-in instrumentation for the pinned Isaac Lab teleoperation runner."""

from __future__ import annotations

import math
from types import MethodType
from typing import Any

from .course import (
    BrickGameConfig,
    BrickPassRandomisation,
    BrickSpec,
    BrickStateEvent,
    HapticHitEvent,
)
from .haptics import XRControllerHaptics
from .isaac_course import (
    BrickImpactEvent,
    InstrumentActorFilter,
    IsaacSabreBrickAdapter,
    IsaacSabreBrickBinding,
    IsaacSabreBrickConfig,
    canonicalise_environment_prim_path,
)
from .isaac_score import IsaacSabreScoreIndicator
from .layout import (
    LEFT_PSM_REMOTE_CENTER_POS_W,
    LEFT_PSM_ROOT_ROT_WXYZ,
    LEFT_TOOL_HOME_POS_W,
    LEFT_TOOL_HOME_ROT_XYZW,
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
    PURE_TELEOP_JAW_CLUTCH_ENABLED,
    PURE_TELEOP_JAW_VELOCITY_LIMIT_RAD_S,
    PURE_TELEOP_PHYSICS_DT_S,
    PURE_TELEOP_PSM_GRAVITY_ENABLED,
    PURE_TELEOP_RENDER_INTERVAL,
    PURE_TELEOP_RETARGETING_MODE,
    PURE_TELEOP_SABRE_MAX_SHAFT_LENGTH_M,
    PURE_TELEOP_SABRE_MIN_SHAFT_LENGTH_M,
    PURE_TELEOP_SABRE_PITCH_LIMIT_RAD,
    PURE_TELEOP_SABRE_POLE_HORIZONTAL_NORM_THRESHOLD,
    PURE_TELEOP_SABRE_REACQUISITION_ORIENTATION_STEP_LIMIT_RAD,
    PURE_TELEOP_SABRE_SHAFT_LENGTH_M,
    PURE_TELEOP_SABRE_TOOL_TIP_AXIS,
    PURE_TELEOP_SABRE_YAW_LIMIT_RAD,
    PURE_TELEOP_SUTURE_PAD_ENABLED,
    PURE_TELEOP_TRANSLATION_SCALE,
    PURE_TELEOP_WORKSPACE_LOWER_W,
    PURE_TELEOP_WORKSPACE_UPPER_W,
    RIGHT_PSM_REMOTE_CENTER_POS_W,
    RIGHT_PSM_ROOT_ROT_WXYZ,
    RIGHT_TOOL_HOME_POS_W,
    RIGHT_TOOL_HOME_ROT_XYZW,
    apply_pure_teleop_layout,
)
from .retargeting import (
    AbsoluteHingedPoseConfig,
    AbsoluteHingedPoseStateMachine,
    DirectTriggerJawConfig,
    DirectTriggerJawStateMachine,
)
from .scene import PAD_PATH, IsaacSabreHitLighting, apply_scene_dressing
from .score import SabreScoreCounter
from .telemetry import QuestEvidenceRecorder

_DVRK_JAW_JOINT_NAMES = (
    "psm_tool_gripper1_joint",
    "psm_tool_gripper2_joint",
)


def _make_isaac_sabre_brick_config(
    randomisation_seed: str = "test-session",
) -> IsaacSabreBrickConfig:
    """Bind the six authored targets to the instantiated Isaac Lab scene."""
    specs = tuple(
        BrickSpec(
            brick_id=brick_id,
            lane=PURE_TELEOP_BRICK_LANES[brick_id],
            spawn_position_m=PURE_TELEOP_BRICK_START_POSITIONS_W[brick_id],
            approach_velocity_m_s=(
                0.0,
                -PURE_TELEOP_BRICK_APPROACH_SPEEDS_M_S[brick_id],
                0.0,
            ),
            approach_end_y_m=PURE_TELEOP_BRICK_MISS_Y_M,
            size_m=PURE_TELEOP_BRICK_SIZES_M[brick_id],
            display_colour_rgb=PURE_TELEOP_BRICK_COLOURS[brick_id],
        )
        for brick_id in PURE_TELEOP_BRICK_IDS
    )
    actor_filters = tuple(
        InstrumentActorFilter(hand=side, prim_path_expr=path)
        for side in ("left", "right")
        for path in PURE_TELEOP_BRICK_PSM_CONTACT_FILTERS[side]
    )
    bindings = tuple(
        IsaacSabreBrickBinding(
            brick_id=brick_id,
            rigid_object_name=f"sabre_brick_{brick_id}",
            contact_sensor_name=f"sabre_brick_{brick_id}_contact",
            rigid_body_prim_path=(
                f"/World/envs/env_0/{PURE_TELEOP_BRICK_PRIM_NAMES[brick_id]}"
            ),
        )
        for brick_id in PURE_TELEOP_BRICK_IDS
    )
    return IsaacSabreBrickConfig(
        specs=specs,
        game_config=BrickGameConfig(
            fall_z_threshold_m=PURE_TELEOP_BRICK_FALL_Z_M,
            fall_timeout_s=PURE_TELEOP_BRICK_FALL_TIMEOUT_S,
            haptic_amplitude=PURE_TELEOP_BRICK_HAPTIC_INTENSITY,
            haptic_duration_s=PURE_TELEOP_BRICK_HAPTIC_DURATION_S,
            haptic_frequency_hz=PURE_TELEOP_BRICK_HAPTIC_FREQUENCY_HZ,
        ),
        bindings=bindings,
        instrument_actor_filters=actor_filters,
        contact_force_threshold_n=PURE_TELEOP_BRICK_CONTACT_FORCE_THRESHOLD_N,
        fall_through_prim_paths=(),
        brick_mass_kg=PURE_TELEOP_BRICK_MASS_KG,
        hit_speed_m_s=PURE_TELEOP_BRICK_HIT_SPEED_M_S,
        pass_randomisation=BrickPassRandomisation(
            seed=randomisation_seed,
            brick_ids=PURE_TELEOP_BRICK_IDS,
            speed_choices_m_s=PURE_TELEOP_BRICK_RANDOM_SPEEDS_M_S,
            height_choices_m=PURE_TELEOP_BRICK_RANDOM_HEIGHTS_M,
            colour_choices_rgb=PURE_TELEOP_BRICK_RANDOM_COLOURS,
        ),
    )


def _scalar_bool(value: Any) -> bool:
    if hasattr(value, "detach"):
        value = value.detach().cpu()
    if hasattr(value, "reshape"):
        value = value.reshape(-1)
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        return bool(value[0]) if value else False
    return bool(value)


def _vector(value: Any) -> list[float]:
    if hasattr(value, "detach"):
        value = value.detach().cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    return [float(item) for item in value]


def _applied_action_vector(value: Any) -> list[float]:
    if hasattr(value, "detach"):
        value = value.detach().cpu()
    if hasattr(value, "reshape"):
        value = value.reshape(-1)
    elif isinstance(value, (list, tuple)) and len(value) == 1 and isinstance(value[0], (list, tuple)):
        value = value[0]
    return _vector(value)


def _normal_dot(first: list[float], second: list[float]) -> float:
    first_norm = math.sqrt(sum(value * value for value in first))
    second_norm = math.sqrt(sum(value * value for value in second))
    if first_norm <= 1.0e-12 or second_norm <= 1.0e-12:
        return 1.0
    return sum(a * b for a, b in zip(first, second, strict=True)) / (first_norm * second_norm)


def _apply_xr_anchor_position(
    env_cfg: Any,
    anchor_pos: tuple[float, float, float],
    near_plane_m: float | None = None,
) -> Any:
    """Apply one XR anchor and close-view plane to every configured XR device."""
    xr_cfg = getattr(env_cfg, "xr", None)
    if xr_cfg is None:
        raise ValueError("XR anchor override requires an environment XR configuration")
    xr_cfg.anchor_pos = anchor_pos
    if near_plane_m is not None:
        xr_cfg.near_plane = near_plane_m

    teleop_devices = getattr(env_cfg, "teleop_devices", None)
    devices = getattr(teleop_devices, "devices", {})
    for device_cfg in devices.values():
        device_xr_cfg = getattr(device_cfg, "xr_cfg", None)
        if device_xr_cfg is not None:
            device_xr_cfg.anchor_pos = anchor_pos
            if near_plane_m is not None:
                device_xr_cfg.near_plane = near_plane_m
    return env_cfg


def _disable_automatic_terminations(env_cfg: Any) -> Any:
    """Disable every RL termination term for an uninterrupted teleop session."""
    terminations = getattr(env_cfg, "terminations", None)
    if terminations is None:
        raise ValueError("pure teleop requires an environment termination configuration")
    term_names = [name for name in vars(terminations) if not name.startswith("_")]
    if not term_names:
        raise ValueError("pure teleop found no configurable termination terms")
    for name in term_names:
        setattr(terminations, name, None)
    return env_cfg


def _inspect_jaw_collision_runtime(stage: Any) -> dict[str, Any]:
    """Report whether any PSM jaw collision shape remains enabled."""
    from pxr import Usd, UsdPhysics

    shape_count: dict[str, int] = {}
    enabled_paths: list[str] = []
    missing_body_paths: list[str] = []
    for side, psm_name in (("left", "LeftPSM"), ("right", "RightPSM")):
        count = 0
        for body_name in (
            "psm_tool_gripper1_link",
            "psm_tool_gripper2_link",
        ):
            body_path = f"/World/envs/env_0/{psm_name}/{body_name}"
            body_prim = stage.GetPrimAtPath(body_path)
            if not body_prim:
                missing_body_paths.append(body_path)
                continue
            for prim in Usd.PrimRange(body_prim):
                if not prim.HasAPI(UsdPhysics.CollisionAPI):
                    continue
                count += 1
                enabled = UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get()
                if enabled is not False:
                    enabled_paths.append(str(prim.GetPath()))
        shape_count[side] = count
    return {
        "jaw_collision_shape_count": shape_count,
        "enabled_jaw_collision_paths": enabled_paths,
        "missing_jaw_body_paths": missing_body_paths,
    }


def _inspect_psm_stability_runtime(stage: Any) -> dict[str, Any]:
    """Inspect the fixed root and per-body gravity state of both PSMs."""
    from isaaclab.sim.utils import find_global_fixed_joint_prim
    from pxr import Usd, UsdPhysics

    fixed_root_joint_paths: dict[str, str] = {}
    rigid_body_count: dict[str, int] = {}
    gravity_enabled_paths: list[str] = []
    missing_root_paths: list[str] = []
    for side, psm_name in (("left", "LeftPSM"), ("right", "RightPSM")):
        root_path = f"/World/envs/env_0/{psm_name}"
        root_prim = stage.GetPrimAtPath(root_path)
        if not root_prim:
            missing_root_paths.append(root_path)
            fixed_root_joint_paths[side] = ""
            rigid_body_count[side] = 0
            continue
        fixed_joint = find_global_fixed_joint_prim(
            root_path,
            check_enabled_only=True,
            stage=stage,
        )
        fixed_root_joint_paths[side] = (
            str(fixed_joint.GetPath()) if fixed_joint is not None else ""
        )
        count = 0
        for prim in Usd.PrimRange(root_prim):
            if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
                continue
            count += 1
            disable_gravity = prim.GetAttribute(
                "physxRigidBody:disableGravity"
            ).Get()
            if disable_gravity is not True:
                gravity_enabled_paths.append(str(prim.GetPath()))
        rigid_body_count[side] = count
    return {
        "psm_fixed_root_joint_paths": fixed_root_joint_paths,
        "psm_rigid_body_count": rigid_body_count,
        "gravity_enabled_psm_body_paths": gravity_enabled_paths,
        "missing_psm_root_paths": missing_root_paths,
    }


def _inspect_brick_display_colours(stage: Any) -> dict[str, list[float]]:
    """Read the display colours authored on all live sabre brick meshes."""
    colours: dict[str, list[float]] = {}
    for brick_id in PURE_TELEOP_BRICK_IDS:
        mesh_path = (
            f"/World/envs/env_0/{PURE_TELEOP_BRICK_PRIM_NAMES[brick_id]}"
            "/geometry/mesh"
        )
        mesh_prim = stage.GetPrimAtPath(mesh_path)
        if not mesh_prim:
            raise RuntimeError(f"sabre brick display mesh is missing: {mesh_path}")
        values = mesh_prim.GetAttribute("primvars:displayColor").Get()
        if values is None or len(values) != 1 or len(values[0]) != 3:
            raise RuntimeError(f"sabre brick display colour is invalid: {mesh_path}")
        colours[brick_id] = [float(component) for component in values[0]]
    return colours


def _validate_pure_teleop_runtime(
    env: Any,
    stage: Any | None = None,
    jaw_collision_report: dict[str, Any] | None = None,
    psm_stability_report: dict[str, Any] | None = None,
    brick_display_colours: dict[str, list[float]] | None = None,
) -> dict[str, Any]:
    """Fail closed unless the instantiated scene is genuinely needle-free."""
    if stage is None:
        import omni.usd

        stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("pure teleop runtime validation requires an open USD stage")

    scene = env.scene
    environment_count = int(env.num_envs)
    rigid_object_names = sorted(scene.rigid_objects)
    sensor_names = sorted(scene.sensors)
    needle_contact_sensors = [name for name in sensor_names if "needle_contact" in name]
    needle_prim_present = bool(stage.GetPrimAtPath("/World/envs/env_0/Needle"))
    suture_pad_prim_present = bool(stage.GetPrimAtPath(PAD_PATH))
    suture_pad_configured = getattr(env.cfg.scene, "suture_pad", None) is not None

    devices = env.cfg.teleop_devices.devices
    controller_cfg = devices["motion_controllers"]
    retargeter_cfg = next(
        cfg
        for cfg in controller_cfg.retargeters
        if hasattr(cfg, "left") and hasattr(cfg, "right")
    )
    translation_scale = {
        "left": float(retargeter_cfg.left.translation_scale),
        "right": float(retargeter_cfg.right.translation_scale),
    }
    controller_workspace = {
        side: {
            "lower": _vector(getattr(retargeter_cfg, side).workspace_lower),
            "upper": _vector(getattr(retargeter_cfg, side).workspace_upper),
        }
        for side in ("left", "right")
    }
    jaw_retargeter = {
        side: {
            "jaw_open": _vector(getattr(retargeter_cfg, side).jaw_open),
            "jaw_closed": _vector(getattr(retargeter_cfg, side).jaw_closed),
            "initial_closedness": float(
                getattr(retargeter_cfg, side).initial_closedness
            ),
        }
        for side in ("left", "right")
    }
    psm_contact_reporting = {
        "left": bool(env.cfg.scene.left_psm.spawn.activate_contact_sensors),
        "right": bool(env.cfg.scene.right_psm.spawn.activate_contact_sensors),
    }
    expected_brick_names = sorted(
        f"sabre_brick_{brick_id}" for brick_id in PURE_TELEOP_BRICK_IDS
    )
    expected_brick_sensor_names = sorted(
        f"sabre_brick_{brick_id}_contact" for brick_id in PURE_TELEOP_BRICK_IDS
    )
    expected_brick_filters = [
        path
        for side in ("left", "right")
        for path in PURE_TELEOP_BRICK_PSM_CONTACT_FILTERS[side]
    ]
    if brick_display_colours is None:
        brick_display_colours = _inspect_brick_display_colours(stage)
    brick_configuration = {}
    for brick_id in PURE_TELEOP_BRICK_IDS:
        brick_cfg = getattr(env.cfg.scene, f"sabre_brick_{brick_id}")
        sensor_cfg = getattr(env.cfg.scene, f"sabre_brick_{brick_id}_contact")
        brick_configuration[brick_id] = {
            "lane": PURE_TELEOP_BRICK_LANES[brick_id],
            "prim_path": canonicalise_environment_prim_path(brick_cfg.prim_path),
            "gravity_disabled": bool(brick_cfg.spawn.rigid_props.disable_gravity),
            "kinematic_enabled": bool(brick_cfg.spawn.rigid_props.kinematic_enabled),
            "contact_reporting_enabled": bool(brick_cfg.spawn.activate_contact_sensors),
            "size_m": _vector(brick_cfg.spawn.size),
            "mass_kg": float(brick_cfg.spawn.mass_props.mass),
            "spawn_position_w": _vector(brick_cfg.init_state.pos),
            "approach_velocity_m_s": _vector(brick_cfg.init_state.lin_vel),
            "display_colour_rgb": _vector(brick_display_colours[brick_id]),
            "sensor_prim_path": canonicalise_environment_prim_path(
                sensor_cfg.prim_path
            ),
            "sensor_filters": [
                canonicalise_environment_prim_path(path)
                for path in sensor_cfg.filter_prim_paths_expr
            ],
            "sensor_force_threshold_n": float(sensor_cfg.force_threshold),
        }
    psm_fix_root_link_configured = {
        side: bool(
            getattr(env.cfg.scene, f"{side}_psm")
            .spawn.articulation_props.fix_root_link
        )
        for side in ("left", "right")
    }
    psm_disable_gravity_configured = {
        side: bool(
            getattr(env.cfg.scene, f"{side}_psm").spawn.rigid_props.disable_gravity
        )
        for side in ("left", "right")
    }
    psm_is_fixed_base: dict[str, bool] = {}
    for side in ("left", "right"):
        asset_name = f"{side}_psm"
        try:
            articulation = scene[asset_name]
        except (KeyError, TypeError):
            articulation = getattr(scene, asset_name)
        psm_is_fixed_base[side] = bool(articulation.is_fixed_base)
    action_terms = list(env.action_manager.active_terms)
    action_dim = int(env.action_manager.total_action_dim)
    jaw_actions = {
        side: getattr(env.cfg.actions, f"{side}_jaw_action")
        for side in ("left", "right")
    }
    jaw_action_types = {
        side: type(action).__name__ for side, action in jaw_actions.items()
    }
    jaw_action_joint_names = {
        side: list(action.joint_names) for side, action in jaw_actions.items()
    }
    jaw_actuator_velocity_limit = {
        side: float(
            getattr(env.cfg.scene, f"{side}_psm")
            .actuators["jaws"]
            .velocity_limit_sim
        )
        for side in ("left", "right")
    }
    physics_dt_s = float(env.cfg.sim.dt)
    decimation = int(env.cfg.decimation)
    render_interval = int(env.cfg.sim.render_interval)
    expected_action_terms = [
        "left_arm_action",
        "left_jaw_action",
        "right_arm_action",
        "right_jaw_action",
    ]
    expected_jaw_joint_names = list(_DVRK_JAW_JOINT_NAMES)
    trigger_jaw_control_enabled = (
        action_terms == expected_action_terms
        and all(
            names == expected_jaw_joint_names
            for names in jaw_action_joint_names.values()
        )
        and len(set(jaw_action_types.values())) == 1
        and not any("guard" in name.lower() for name in jaw_action_types.values())
        and all(
            values["jaw_open"] != values["jaw_closed"]
            and values["initial_closedness"] == 0.0
            for values in jaw_retargeter.values()
        )
    )
    if jaw_collision_report is None:
        jaw_collision_report = _inspect_jaw_collision_runtime(stage)
    if psm_stability_report is None:
        psm_stability_report = _inspect_psm_stability_runtime(stage)
    report = {
        "needle_prim_present": needle_prim_present,
        "suture_pad_prim_present": suture_pad_prim_present,
        "suture_pad_configured": suture_pad_configured,
        "environment_count": environment_count,
        "rigid_objects": rigid_object_names,
        "sensors": sensor_names,
        "needle_contact_sensors": needle_contact_sensors,
        "bricks_enabled": PURE_TELEOP_BRICKS_ENABLED,
        "brick_configuration": brick_configuration,
        "action_terms": action_terms,
        "action_dim": action_dim,
        "controller_translation_scale": translation_scale,
        "controller_workspace": controller_workspace,
        "psm_contact_reporting_enabled": psm_contact_reporting,
        "psm_fix_root_link_configured": psm_fix_root_link_configured,
        "psm_disable_gravity_configured": psm_disable_gravity_configured,
        "psm_is_fixed_base": psm_is_fixed_base,
        "physics_dt_s": physics_dt_s,
        "decimation": decimation,
        "render_interval": render_interval,
        "jaw_action_types": jaw_action_types,
        "jaw_action_joint_names": jaw_action_joint_names,
        "jaw_retargeter": jaw_retargeter,
        "jaw_actuator_velocity_limit_rad_s": jaw_actuator_velocity_limit,
        "trigger_jaw_control_enabled": trigger_jaw_control_enabled,
        **jaw_collision_report,
        **psm_stability_report,
    }

    errors: list[str] = []
    if needle_prim_present or "needle" in rigid_object_names:
        errors.append("needle is present")
    if suture_pad_prim_present or suture_pad_configured:
        errors.append(
            "suture pad is present: "
            f"prim={suture_pad_prim_present}, configured={suture_pad_configured}"
        )
    if environment_count != 1:
        errors.append(
            "absolute hinged pure teleop requires exactly one environment, "
            f"got {environment_count}"
        )
    if needle_contact_sensors:
        errors.append(f"needle contact sensors are active: {needle_contact_sensors}")
    if rigid_object_names != expected_brick_names:
        errors.append(
            "gravity-free brick rigid objects are not exact: "
            f"{rigid_object_names}, expected {expected_brick_names}"
        )
    if sensor_names != expected_brick_sensor_names:
        errors.append(
            "brick contact sensors are not exact: "
            f"{sensor_names}, expected {expected_brick_sensor_names}"
        )
    for brick_id, config in brick_configuration.items():
        if not config["gravity_disabled"] or config["kinematic_enabled"]:
            errors.append(
                f"{brick_id} brick is not dynamic and gravity-free on approach: {config}"
            )
        if not config["contact_reporting_enabled"]:
            errors.append(f"{brick_id} brick contact reporting is disabled")
        if config["sensor_prim_path"] != config["prim_path"]:
            errors.append(
                f"{brick_id} brick sensor path differs from its rigid object path"
            )
        if config["size_m"] != list(PURE_TELEOP_BRICK_SIZES_M[brick_id]):
            errors.append(f"{brick_id} brick size is wrong: {config['size_m']}")
        if not math.isclose(
            config["mass_kg"],
            PURE_TELEOP_BRICK_MASS_KG,
            abs_tol=1.0e-12,
        ):
            errors.append(f"{brick_id} brick mass is wrong: {config['mass_kg']}")
        if config["spawn_position_w"] != list(
            PURE_TELEOP_BRICK_START_POSITIONS_W[brick_id]
        ):
            errors.append(
                f"{brick_id} brick spawn position is wrong: {config['spawn_position_w']}"
            )
        expected_velocity = [
            0.0,
            -PURE_TELEOP_BRICK_APPROACH_SPEEDS_M_S[brick_id],
            0.0,
        ]
        if config["approach_velocity_m_s"] != expected_velocity:
            errors.append(
                f"{brick_id} brick approach velocity is wrong: "
                f"{config['approach_velocity_m_s']}"
            )
        if any(
            not math.isclose(actual, expected, abs_tol=1.0e-6)
            for actual, expected in zip(
                config["display_colour_rgb"],
                PURE_TELEOP_BRICK_COLOURS[brick_id],
                strict=True,
            )
        ):
            errors.append(
                f"{brick_id} brick display colour is wrong: "
                f"{config['display_colour_rgb']}"
            )
        actual_filters = [
            canonicalise_environment_prim_path(path)
            for path in config["sensor_filters"]
        ]
        if actual_filters != expected_brick_filters:
            errors.append(
                f"{brick_id} brick distal PSM filters are wrong: "
                f"{config['sensor_filters']}"
            )
        if not math.isclose(
            config["sensor_force_threshold_n"],
            PURE_TELEOP_BRICK_CONTACT_FORCE_THRESHOLD_N,
            abs_tol=1.0e-12,
        ):
            errors.append(
                f"{brick_id} brick contact force threshold is wrong: "
                f"{config['sensor_force_threshold_n']}"
            )
    if action_dim != 18:
        errors.append(f"action dimension is {action_dim}, expected 18")
    if action_terms != expected_action_terms:
        errors.append(f"bilateral arm and trigger jaw actions are not intact: {action_terms}")
    if any(value != PURE_TELEOP_TRANSLATION_SCALE for value in translation_scale.values()):
        errors.append(f"controller translation scale is wrong: {translation_scale}")
    expected_workspace = {
        "lower": list(PURE_TELEOP_WORKSPACE_LOWER_W),
        "upper": list(PURE_TELEOP_WORKSPACE_UPPER_W),
    }
    if any(workspace != expected_workspace for workspace in controller_workspace.values()):
        errors.append(f"controller workspace is wrong: {controller_workspace}")
    if any(psm_contact_reporting.values()):
        errors.append(f"PSM contact reporting is still enabled: {psm_contact_reporting}")
    if not all(psm_fix_root_link_configured.values()):
        errors.append(f"PSM fixed roots are not configured: {psm_fix_root_link_configured}")
    if PURE_TELEOP_PSM_GRAVITY_ENABLED:
        errors.append("pure teleop PSM gravity constant must remain false")
    if not all(psm_disable_gravity_configured.values()):
        errors.append(
            "PSM gravity disabling is not configured: "
            f"{psm_disable_gravity_configured}"
        )
    if not all(psm_is_fixed_base.values()):
        errors.append(f"PSM runtime roots are not fixed: {psm_is_fixed_base}")
    if not math.isclose(physics_dt_s, PURE_TELEOP_PHYSICS_DT_S, abs_tol=1.0e-12):
        errors.append(f"physics timestep is wrong: {physics_dt_s}")
    if decimation != PURE_TELEOP_DECIMATION:
        errors.append(f"decimation is wrong: {decimation}")
    if render_interval != PURE_TELEOP_RENDER_INTERVAL:
        errors.append(f"render interval is wrong: {render_interval}")
    if any(
        not math.isclose(
            value,
            PURE_TELEOP_JAW_VELOCITY_LIMIT_RAD_S,
            abs_tol=1.0e-12,
        )
        for value in jaw_actuator_velocity_limit.values()
    ):
        errors.append(
            "jaw actuator velocity limits are wrong: "
            f"{jaw_actuator_velocity_limit}"
        )
    if not trigger_jaw_control_enabled:
        errors.append(
            "trigger-driven bilateral jaw control is not intact: "
            f"types={jaw_action_types}, joints={jaw_action_joint_names}, "
            f"retargeter={jaw_retargeter}"
        )
    if jaw_collision_report["missing_jaw_body_paths"]:
        errors.append(
            "jaw collision validation is missing bodies: "
            f"{jaw_collision_report['missing_jaw_body_paths']}"
        )
    if any(
        count <= 0
        for count in jaw_collision_report["jaw_collision_shape_count"].values()
    ):
        errors.append(
            "jaw collision validation found no shapes: "
            f"{jaw_collision_report['jaw_collision_shape_count']}"
        )
    if jaw_collision_report["enabled_jaw_collision_paths"]:
        errors.append(
            "jaw collision physics is still enabled: "
            f"{jaw_collision_report['enabled_jaw_collision_paths']}"
        )
    if psm_stability_report["missing_psm_root_paths"]:
        errors.append(
            "PSM stability validation is missing roots: "
            f"{psm_stability_report['missing_psm_root_paths']}"
        )
    if any(
        not path
        for path in psm_stability_report["psm_fixed_root_joint_paths"].values()
    ):
        errors.append(
            "PSM stability validation found no enabled world root joint: "
            f"{psm_stability_report['psm_fixed_root_joint_paths']}"
        )
    if any(
        count <= 0 for count in psm_stability_report["psm_rigid_body_count"].values()
    ):
        errors.append(
            "PSM stability validation found no rigid bodies: "
            f"{psm_stability_report['psm_rigid_body_count']}"
        )
    if psm_stability_report["gravity_enabled_psm_body_paths"]:
        errors.append(
            "PSM gravity is still enabled on bodies: "
            f"{psm_stability_report['gravity_enabled_psm_body_paths']}"
        )
    if errors:
        raise RuntimeError("pure teleop runtime validation failed: " + "; ".join(errors))
    return report


def _install_absolute_hinged_retargeting(device: Any) -> dict[str, Any]:
    """Replace only the pure-mode arm pose kernels with hinged absolute ones."""
    retargeter = getattr(device, "_dvrk_retargeter", None)
    if retargeter is None:
        raise RuntimeError("absolute hinged retargeting requires the dVRK retargeter")
    side_geometry = {
        "left": (
            LEFT_PSM_REMOTE_CENTER_POS_W,
            LEFT_PSM_ROOT_ROT_WXYZ,
            LEFT_TOOL_HOME_POS_W,
            LEFT_TOOL_HOME_ROT_XYZW,
        ),
        "right": (
            RIGHT_PSM_REMOTE_CENTER_POS_W,
            RIGHT_PSM_ROOT_ROT_WXYZ,
            RIGHT_TOOL_HOME_POS_W,
            RIGHT_TOOL_HOME_ROT_XYZW,
        ),
    }
    replaced_jaw_kernel_types: dict[str, str] = {}
    for side, (
        pivot,
        root_orientation_wxyz,
        home_position,
        home_orientation,
    ) in side_geometry.items():
        kernels = getattr(retargeter, f"_{side}", None)
        if kernels is None or not hasattr(kernels, "pose") or not hasattr(kernels, "jaw"):
            raise RuntimeError(
                f"absolute hinged retargeting requires complete {side} dVRK kernels"
            )
        replaced_jaw_kernel_types[side] = type(kernels.jaw).__name__
        jaw_open = getattr(kernels.jaw, "_jaw_open", None)
        jaw_closed = getattr(kernels.jaw, "_jaw_closed", None)
        if jaw_open is None or jaw_closed is None:
            raise RuntimeError(
                f"absolute trigger retargeting requires {side} jaw endpoints"
            )
        kernels.pose = AbsoluteHingedPoseStateMachine(
            AbsoluteHingedPoseConfig(
                pivot_position_w=pivot,
                home_position_w=home_position,
                home_orientation_xyzw=home_orientation,
                shaft_length_m=PURE_TELEOP_SABRE_SHAFT_LENGTH_M,
                shaft_length_min_m=PURE_TELEOP_SABRE_MIN_SHAFT_LENGTH_M,
                shaft_length_max_m=PURE_TELEOP_SABRE_MAX_SHAFT_LENGTH_M,
                axial_translation_scale=PURE_TELEOP_AXIAL_TRANSLATION_SCALE,
                clutch_threshold=PURE_TELEOP_ARM_CLUTCH_THRESHOLD,
                base_orientation_xyzw=(
                    root_orientation_wxyz[1],
                    root_orientation_wxyz[2],
                    root_orientation_wxyz[3],
                    root_orientation_wxyz[0],
                ),
                tool_tip_axis=PURE_TELEOP_SABRE_TOOL_TIP_AXIS,
                yaw_limit_rad=PURE_TELEOP_SABRE_YAW_LIMIT_RAD,
                pitch_limit_rad=PURE_TELEOP_SABRE_PITCH_LIMIT_RAD,
                pole_horizontal_norm_threshold=(
                    PURE_TELEOP_SABRE_POLE_HORIZONTAL_NORM_THRESHOLD
                ),
                reacquisition_orientation_step_limit_rad=(
                    PURE_TELEOP_SABRE_REACQUISITION_ORIENTATION_STEP_LIMIT_RAD
                ),
            )
        )
        kernels.jaw = DirectTriggerJawStateMachine(
            DirectTriggerJawConfig(
                jaw_open=tuple(_vector(jaw_open)),
                jaw_closed=tuple(_vector(jaw_closed)),
                initial_closedness=0.0,
            )
        )
    reset = getattr(retargeter, "reset", None)
    if not callable(reset):
        raise RuntimeError("absolute hinged retargeting requires a resettable retargeter")
    reset()

    pose_kernel_types = {
        side: type(getattr(retargeter, f"_{side}").pose).__name__
        for side in ("left", "right")
    }
    expected_kernel_type = AbsoluteHingedPoseStateMachine.__name__
    if any(value != expected_kernel_type for value in pose_kernel_types.values()):
        raise RuntimeError(
            "absolute hinged retargeting did not install both pose kernels: "
            f"{pose_kernel_types}"
        )
    jaw_kernel_types = {
        side: type(getattr(retargeter, f"_{side}").jaw).__name__
        for side in ("left", "right")
    }
    expected_jaw_kernel_type = DirectTriggerJawStateMachine.__name__
    if any(value != expected_jaw_kernel_type for value in jaw_kernel_types.values()):
        raise RuntimeError(
            "absolute trigger retargeting did not install both jaw kernels: "
            f"{jaw_kernel_types}"
        )
    return {
        "retargeting_mode": PURE_TELEOP_RETARGETING_MODE,
        "controller_orientation_mode": "session_registered_absolute_openxr_grip",
        "controller_translation_input_used": PURE_TELEOP_CONTROLLER_TRANSLATION_ENABLED,
        "squeeze_controls_arm_pose": PURE_TELEOP_ARM_CLUTCH_ENABLED,
        "trigger_jaw_mode": "absolute_analog",
        "squeeze_controls_jaw_pose": PURE_TELEOP_JAW_CLUTCH_ENABLED,
        "absolute_trigger_jaw_enabled": PURE_TELEOP_ABSOLUTE_TRIGGER_JAW_ENABLED,
        "controller_registration_mode": "first_engaged_sample_to_held_tool_pose",
        "controller_registration_preserved_across_tracking_loss": False,
        "controller_registration_preserved_across_clutch_release": False,
        "controller_reengagement_is_jump_free": True,
        "controller_registration_cleared_by_device_reset": True,
        "arm_clutch_threshold": PURE_TELEOP_ARM_CLUTCH_THRESHOLD,
        "axial_translation_scale": PURE_TELEOP_AXIAL_TRANSLATION_SCALE,
        "tool_tip_axis_in_tool_frame": list(PURE_TELEOP_SABRE_TOOL_TIP_AXIS),
        "proximal_angle_limits_rad": {
            "yaw": PURE_TELEOP_SABRE_YAW_LIMIT_RAD,
            "pitch": PURE_TELEOP_SABRE_PITCH_LIMIT_RAD,
        },
        "pole_horizontal_norm_threshold": (
            PURE_TELEOP_SABRE_POLE_HORIZONTAL_NORM_THRESHOLD
        ),
        "reacquisition_orientation_step_limit_rad": (
            PURE_TELEOP_SABRE_REACQUISITION_ORIENTATION_STEP_LIMIT_RAD
        ),
        "psm_hinge_pivot_w": {
            "left": list(LEFT_PSM_REMOTE_CENTER_POS_W),
            "right": list(RIGHT_PSM_REMOTE_CENTER_POS_W),
        },
        "psm_shaft_length_m": {
            "left": PURE_TELEOP_SABRE_SHAFT_LENGTH_M,
            "right": PURE_TELEOP_SABRE_SHAFT_LENGTH_M,
        },
        "psm_shaft_length_bounds_m": {
            "minimum": PURE_TELEOP_SABRE_MIN_SHAFT_LENGTH_M,
            "maximum": PURE_TELEOP_SABRE_MAX_SHAFT_LENGTH_M,
        },
        "pose_kernel_types": pose_kernel_types,
        "jaw_kernel_types": jaw_kernel_types,
        "replaced_jaw_kernel_types": replaced_jaw_kernel_types,
    }


class _ControllerPairActivityGate:
    """Start on bilateral tracking and stop when either controller becomes invalid."""

    def __init__(self) -> None:
        self._valid_hands: set[str] = set()
        self._active = False
        self._frame_token: int | None = None
        self._frame_validity: dict[str, bool] = {}

    def observe(
        self,
        hand: str,
        pose_valid: bool,
        frame_token: int | None = None,
    ) -> str | None:
        if frame_token is None:
            if pose_valid:
                self._valid_hands.add(hand)
            else:
                self._valid_hands.discard(hand)
            both_valid = self._valid_hands == {"left", "right"}
        else:
            if frame_token != self._frame_token:
                self._frame_token = frame_token
                self._frame_validity = {}
            self._frame_validity[hand] = pose_valid
            if self._frame_validity.keys() != {"left", "right"}:
                return None
            both_valid = all(self._frame_validity.values())
        if not self._active and both_valid:
            self._active = True
            return "START"
        if self._active and not both_valid:
            self._active = False
            return "STOP"
        return None


class IsaacLabEvidenceInstrumentation:
    """Instrument one execution without modifying the authoritative checkout."""

    def __init__(
        self,
        recorder: QuestEvidenceRecorder,
        *,
        xr_enabled: bool,
        xr_anchor_pos: tuple[float, float, float] | None = None,
        xr_near_plane_m: float | None = None,
        pure_teleop: bool = False,
        live_scene_dressing: bool = False,
    ):
        self.telemetry = recorder
        self.application_active = not xr_enabled
        self._auto_start_xr = xr_enabled
        self.xr_anchor_pos = xr_anchor_pos
        self.xr_near_plane_m = xr_near_plane_m
        self.pure_teleop = pure_teleop
        self.live_scene_dressing = live_scene_dressing
        self.scene_report: dict[str, Any] | None = None
        self.pure_teleop_runtime_report: dict[str, Any] | None = None
        self._pure_teleop_runtime_validation_recorded = False
        self.episode_id = 0
        self.reset_counter = 0
        self.frame_index = -1
        self._pending_reset = False
        self._initial_reset_complete = False
        self._env = None
        self._device = None
        self._haptics: XRControllerHaptics | None = None
        self._brick_game: IsaacSabreBrickAdapter | None = None
        self._score_counter: SabreScoreCounter | None = None
        self._score_indicator: IsaacSabreScoreIndicator | None = None
        self._hit_lighting: IsaacSabreHitLighting | None = None
        self._phase_machine = None
        self._phase_advance_original = None
        self._jaw_state_sources: dict[str, tuple[Any, list[int]]] = {}
        self.runner_error: str | None = None

    def install(self, runner_module: Any) -> None:
        """Install factory hooks before invoking the pinned runner's main function."""

        if self.xr_anchor_pos is not None or self.pure_teleop:
            original_parse_env_cfg = runner_module.parse_env_cfg

            def instrumented_parse_env_cfg(*args: Any, **kwargs: Any):
                env_cfg = original_parse_env_cfg(*args, **kwargs)
                if self.xr_anchor_pos is not None:
                    env_cfg = _apply_xr_anchor_position(
                        env_cfg,
                        self.xr_anchor_pos,
                        self.xr_near_plane_m,
                    )
                if self.pure_teleop:
                    env_cfg = apply_pure_teleop_layout(env_cfg)
                    env_cfg = _disable_automatic_terminations(env_cfg)
                return env_cfg

            runner_module.parse_env_cfg = instrumented_parse_env_cfg

        original_make = runner_module.gym.make
        original_device_factory = runner_module.create_teleop_device
        original_logger_error = runner_module.logger.error

        def instrumented_logger_error(message: Any, *args: Any, **kwargs: Any):
            if self.runner_error is None:
                try:
                    self.runner_error = str(message) % args if args else str(message)
                except (TypeError, ValueError):
                    self.runner_error = str(message)
            return original_logger_error(message, *args, **kwargs)

        def instrumented_make(*args: Any, **kwargs: Any):
            made = original_make(*args, **kwargs)
            self._env = made.unwrapped
            if self.pure_teleop:
                self.pure_teleop_runtime_report = _validate_pure_teleop_runtime(
                    self._env
                )
                self._haptics = XRControllerHaptics()
                if PURE_TELEOP_BRICKS_ENABLED:
                    self._score_counter = SabreScoreCounter()
                    self._score_indicator = IsaacSabreScoreIndicator()
                    self._brick_game = IsaacSabreBrickAdapter(
                        self._env,
                        _make_isaac_sabre_brick_config(self.telemetry.session_id),
                        haptic_sink=self._handle_brick_haptic,
                        state_event_sink=self._record_brick_state_event,
                        impact_event_sink=self._record_brick_impact,
                    )
                    self.pure_teleop_runtime_report = {
                        **self.pure_teleop_runtime_report,
                        "brick_runtime": self._brick_game.runtime_report(),
                        "score_indicator": self._score_indicator.report(),
                        "score_semantics": {
                            "successful": "approaching_to_falling_instrument_hit",
                            "failed": "approaching_to_recycle_ready_missed",
                            "scope": "aggregate_session_instances",
                        },
                    }
                if not PURE_TELEOP_ABSOLUTE_HINGED_RETARGETING_ENABLED:
                    self._record_pure_teleop_runtime_validation()
            self._instrument_environment(self._env)
            if self.live_scene_dressing:
                self.scene_report = apply_scene_dressing(
                    include_suture_pad=(
                        not self.pure_teleop or PURE_TELEOP_SUTURE_PAD_ENABLED
                    )
                )
                if self._brick_game is not None:
                    self._hit_lighting = IsaacSabreHitLighting()
                    self.scene_report = {
                        **self.scene_report,
                        "hit_lighting": self._hit_lighting.report(),
                    }
                if self.pure_teleop_runtime_report is not None:
                    self.pure_teleop_runtime_report = {
                        **self.pure_teleop_runtime_report,
                        "scene_dressing": self.scene_report,
                    }
                print(
                    f"[INFO] Live scene dressing applied: {self.scene_report}",
                    flush=True,
                )
            return made

        def instrumented_device_factory(name: str, configs: Any, callbacks: dict[str, Any]):
            wrapped_callbacks = dict(callbacks)
            for command in ("START", "STOP", "RESET"):
                callback = callbacks.get(command)
                if callback is not None:
                    wrapped_callbacks[command] = self._wrap_lifecycle(command, callback)
            device = original_device_factory(name, configs, wrapped_callbacks)
            self._device = device
            if self.pure_teleop and PURE_TELEOP_ABSOLUTE_HINGED_RETARGETING_ENABLED:
                if self.pure_teleop_runtime_report is None:
                    raise RuntimeError(
                        "absolute hinged retargeting requires the validated environment"
                    )
                retargeter_report = _install_absolute_hinged_retargeting(device)
                if self._haptics is None:
                    raise RuntimeError(
                        "pure teleop XR haptics must be initialised with the environment"
                    )
                self.pure_teleop_runtime_report = {
                    **self.pure_teleop_runtime_report,
                    **retargeter_report,
                    "xr_haptics": self._haptics.capability_report(),
                }
                self._record_pure_teleop_runtime_validation()
            auto_start = wrapped_callbacks.get("START") if self._auto_start_xr else None
            auto_stop = wrapped_callbacks.get("STOP") if self._auto_start_xr else None
            self._instrument_device(device, auto_start=auto_start, auto_stop=auto_stop)
            return device

        runner_module.gym.make = instrumented_make
        runner_module.create_teleop_device = instrumented_device_factory
        runner_module.logger.error = instrumented_logger_error

    def _record_pure_teleop_runtime_validation(self) -> None:
        if self.pure_teleop_runtime_report is None:
            raise RuntimeError("pure teleop runtime validation report is unavailable")
        if self._pure_teleop_runtime_validation_recorded:
            raise RuntimeError("pure teleop runtime validation was already recorded")
        self.telemetry.record_runtime_validation(
            source="isaac",
            validation=self.pure_teleop_runtime_report,
        )
        self._pure_teleop_runtime_validation_recorded = True
        print(
            "[INFO] Pure teleop runtime validated: "
            f"{self.pure_teleop_runtime_report}",
            flush=True,
        )

    def raise_if_runner_failed(self) -> None:
        if self.runner_error is not None:
            raise RuntimeError(f"pinned teleoperation runner reported an error: {self.runner_error}")

    def _instrument_environment(self, env: Any) -> None:
        self._cache_jaw_state_sources(env)
        original_reset = env.reset
        original_step = env.step

        def instrumented_reset(_env_self: Any, *args: Any, **kwargs: Any):
            episode_before = self.episode_id
            reset_before = self.reset_counter
            result = original_reset(*args, **kwargs)
            if self._brick_game is not None:
                self._brick_game.reset()
                self._reset_sabre_score(reason="environment_reset")
            if not self.pure_teleop:
                self._attach_phase_machine(env)
            if not self._initial_reset_complete:
                self._initial_reset_complete = True
            elif self._pending_reset:
                self.episode_id += 1
                self.reset_counter += 1
                self._pending_reset = False
                self.telemetry.record_lifecycle(
                    command="RESET",
                    before_active=self.application_active,
                    after_active=self.application_active,
                    episode_before=episode_before,
                    episode_after=self.episode_id,
                    handoff_phase_after=self._current_phase(),
                    reset_counter_before=reset_before,
                    reset_counter_after=self.reset_counter,
                )
            return result

        def instrumented_step(_env_self: Any, *args: Any, **kwargs: Any):
            episode_before = self.episode_id
            step_before = int(env.common_step_counter)
            action_frame_index = self.frame_index
            action_argument = args[0] if args else kwargs.get("action")
            if action_argument is None:
                raise RuntimeError("instrumented environment step requires an explicit action")
            applied_action = _applied_action_vector(action_argument)
            result = original_step(*args, **kwargs)
            step_after = int(env.common_step_counter)
            if self._brick_game is not None:
                self._brick_game.after_physics_step(
                    float(env.cfg.sim.dt) * int(env.cfg.decimation)
                )
            self.telemetry.record_action_application(
                applied_action=applied_action,
                jaw_position_rad=self._measured_jaw_positions(),
                controller_frame_index=action_frame_index,
                episode_id=episode_before,
                environment_step_before=step_before,
                environment_step_after=step_after,
                environment_count=int(env.num_envs),
            )
            if not self.pure_teleop:
                success = env.termination_manager.get_term("success")
                failure = env.termination_manager.get_term("needle_dropped_or_out_of_bounds")
                if _scalar_bool(success) or _scalar_bool(failure):
                    self.telemetry.record_termination(
                        episode_id=self.episode_id,
                        step=int(env.common_step_counter),
                        success=success,
                        failure=failure,
                    )
                    self.episode_id += 1
            return result

        env.reset = MethodType(instrumented_reset, env)
        env.step = MethodType(instrumented_step, env)

    def _handle_brick_haptic(self, event: HapticHitEvent) -> bool:
        if self._haptics is None:
            raise RuntimeError("brick haptics are unavailable before XR initialisation")
        capability = self._haptics.capability(event.hand)
        accepted = self._haptics.pulse(
            event.hand,
            intensity=event.amplitude,
            duration_s=event.duration_s,
            frequency_hz=event.frequency_hz,
        )
        environment_step = (
            int(self._env.common_step_counter) if self._env is not None else 0
        )
        self.telemetry.record_haptic_pulse(
            hand=event.hand,
            brick_id=event.brick_id,
            pass_index=event.pass_index,
            intensity=event.amplitude,
            duration_s=event.duration_s,
            frequency_hz=event.frequency_hz,
            kit_accepted=accepted,
            capability=capability.to_dict(),
            environment_step=environment_step,
        )
        return accepted

    def _record_brick_state_event(self, event: BrickStateEvent) -> None:
        if self._brick_game is None:
            raise RuntimeError("brick state telemetry requires the Isaac adapter")
        if event.pass_spec is None:
            raise RuntimeError("brick state telemetry requires the per-pass contract")
        environment_step = (
            int(self._env.common_step_counter) if self._env is not None else 0
        )
        self.telemetry.record_brick_state(
            brick_id=event.brick_id,
            pass_index=event.pass_index,
            lane=event.lane,
            previous_state=event.previous_state.value,
            state=event.state.value,
            reason=event.reason,
            hitter=event.hitter,
            position_m=event.position_m,
            pass_spec=event.pass_spec.to_dict(),
            environment_step=environment_step,
        )
        if self._score_counter is None or self._score_indicator is None:
            raise RuntimeError("brick score telemetry requires the score indicator")
        if not self._score_counter.record_event(event):
            return
        snapshot = self._score_counter.snapshot()
        self._score_indicator.update(
            snapshot.successful_instances,
            snapshot.failed_instances,
        )
        if event.reason == "instrument_hit" and self._hit_lighting is not None:
            if event.hitter is None:
                raise RuntimeError("accepted sabre hit is missing its controller hand")
            self._hit_lighting.register_hit(event.hitter)
            if self.scene_report is not None:
                self.scene_report = {
                    **self.scene_report,
                    "hit_lighting": self._hit_lighting.report(),
                }
        self.telemetry.record_sabre_score(
            successful_instances=snapshot.successful_instances,
            failed_instances=snapshot.failed_instances,
            reason=event.reason,
            brick_id=event.brick_id,
            pass_index=event.pass_index,
            environment_step=environment_step,
        )

    def _record_brick_impact(self, event: BrickImpactEvent) -> None:
        environment_step = (
            int(self._env.common_step_counter) if self._env is not None else 0
        )
        self.telemetry.record_brick_impact(
            hand=event.hand,
            brick_id=event.brick_id,
            pass_index=event.pass_index,
            actor_path_expr=event.actor_path_expr,
            sensed_force_w=event.sensed_force_w,
            sensed_force_n=event.sensed_force_n,
            applied_linear_velocity_m_s=event.applied_linear_velocity_m_s,
            equivalent_impulse_n_s=event.equivalent_impulse_n_s,
            equivalent_force_n=event.equivalent_force_n,
            physics_dt_s=event.physics_dt_s,
            environment_step=environment_step,
        )

    def _reset_sabre_score(self, *, reason: str) -> None:
        if self._score_counter is None and self._score_indicator is None:
            return
        if self._score_counter is None or self._score_indicator is None:
            raise RuntimeError("Surg Sabre score state is only partly initialised")
        self._score_counter.reset()
        self._score_indicator.reset()
        if self._hit_lighting is not None:
            self._hit_lighting.reset()
            if self.scene_report is not None:
                self.scene_report = {
                    **self.scene_report,
                    "hit_lighting": self._hit_lighting.report(),
                }
        environment_step = (
            int(self._env.common_step_counter) if self._env is not None else 0
        )
        self.telemetry.record_sabre_score(
            successful_instances=0,
            failed_instances=0,
            reason=reason,
            brick_id=None,
            pass_index=None,
            environment_step=environment_step,
        )

    def _cache_jaw_state_sources(self, env: Any) -> None:
        actions_cfg = getattr(env.cfg, "actions", None)
        if actions_cfg is None:
            raise RuntimeError("dVRK jaw telemetry requires the action configuration")
        sources: dict[str, tuple[Any, list[int]]] = {}
        for hand in ("left", "right"):
            action_cfg = getattr(actions_cfg, f"{hand}_jaw_action", None)
            if action_cfg is None:
                raise RuntimeError(f"dVRK jaw telemetry requires {hand}_jaw_action")
            joint_names = tuple(action_cfg.joint_names)
            if joint_names != _DVRK_JAW_JOINT_NAMES:
                raise RuntimeError(
                    f"{hand} jaw telemetry requires ordered joints {_DVRK_JAW_JOINT_NAMES}, got {joint_names}"
                )
            articulation = env.scene[action_cfg.asset_name]
            joint_ids, resolved_names = articulation.find_joints(
                list(joint_names),
                preserve_order=True,
            )
            if tuple(resolved_names) != joint_names or len(joint_ids) != 2:
                raise RuntimeError(
                    f"{hand} jaw telemetry resolved {resolved_names}, expected {joint_names}"
                )
            sources[hand] = (articulation, joint_ids)
        self._jaw_state_sources = sources

    def _measured_jaw_positions(self) -> dict[str, list[float]]:
        if set(self._jaw_state_sources) != {"left", "right"}:
            raise RuntimeError("dVRK jaw telemetry sources are incomplete")
        return {
            hand: _vector(articulation.data.joint_pos[0, joint_ids])
            for hand, (articulation, joint_ids) in self._jaw_state_sources.items()
        }

    def _attach_phase_machine(self, env: Any) -> None:
        from isaaclab_tasks.manager_based.manipulation.needle_pass.mdp.terminations import (
            get_handoff_phase_machine,
        )

        phase_cfg = env.cfg.terminations.success.params["phase_cfg"]
        machine = get_handoff_phase_machine(env, phase_cfg)
        if machine is self._phase_machine:
            return
        self._phase_machine = machine
        original_advance = machine.advance
        self._phase_advance_original = original_advance

        def instrumented_advance(measurements: Any, step_token: int):
            result = original_advance(measurements, step_token)
            normals = [_vector(measurements.reaction_normals_w[0, index]) for index in range(4)]
            opposed_dots = (
                _normal_dot(normals[0], normals[1]),
                _normal_dot(normals[2], normals[3]),
            )
            needle_lift = float(measurements.needle_pose_w[0, 2] - machine.reset_needle_z_w[0])
            self.telemetry.record_handoff_sample(
                episode_id=self.episode_id,
                step=int(step_token),
                phase=int(machine.phase[0]),
                normal_forces_n=measurements.normal_forces_n[0],
                opposed_normal_dot=opposed_dots,
                engage_force_n=machine.cfg.engage_force_n,
                disengage_force_n=machine.cfg.disengage_force_n,
                opposed_normal_tolerance_rad=machine.cfg.opposed_normal_tolerance_rad,
                needle_lift_delta_m=needle_lift,
                required_lift_delta_m=machine.cfg.required_lift_delta_z_m,
            )
            return result

        machine.advance = instrumented_advance

    def _instrument_device(
        self,
        device: Any,
        *,
        auto_start: Any | None = None,
        auto_stop: Any | None = None,
    ) -> None:
        original_get_controller_sample = device._get_controller_sample
        original_advance = device.advance
        activity_gate = _ControllerPairActivityGate()

        def apply_tracking_transition(hand: str, pose_valid: bool) -> None:
            transition = activity_gate.observe(
                hand,
                pose_valid,
                frame_token=self.frame_index,
            )
            if transition == "START" and auto_start is not None:
                retargeter = getattr(device, "_dvrk_retargeter", None)
                if retargeter is None:
                    raise RuntimeError("XR controller auto-start requires the dVRK retargeter")
                retargeter.start()
                auto_start()
            elif transition == "STOP" and auto_stop is not None:
                retargeter = getattr(device, "_dvrk_retargeter", None)
                if retargeter is None:
                    raise RuntimeError("XR controller auto-stop requires the dVRK retargeter")
                retargeter.stop()
                auto_stop()

        def instrumented_get_controller_sample(input_path: str, target: Any):
            sample = original_get_controller_sample(input_path, target)
            hand = "left" if input_path.endswith("/left") else "right"
            if sample is None:
                fault = device.controller_faults.get(target) or "controller sample unavailable"
                self.telemetry.record_controller_fault(
                    hand=hand,
                    frame_index=self.frame_index,
                    fault=fault,
                )
                apply_tracking_transition(hand, False)
                return sample
            pose = sample[0]
            inputs = sample[1]
            pose_valid = inputs[6] == 1.0
            self.telemetry.record_controller_sample(
                hand=hand,
                frame_index=self.frame_index,
                pose_valid=pose_valid,
                position_m=pose[0:3],
                orientation_xyzw=(pose[4], pose[5], pose[6], pose[3]),
                trigger=inputs[2],
                squeeze=inputs[3],
            )
            apply_tracking_transition(hand, pose_valid)
            return sample

        def instrumented_advance():
            self.frame_index += 1
            action = original_advance()
            retargeter = getattr(device, "_dvrk_retargeter", None)
            if retargeter is None:
                evidence_action = action
            else:
                evidence_action = (
                    *_vector(retargeter._left_pose),
                    *_vector(retargeter._left_jaws),
                    *_vector(retargeter._right_pose),
                    *_vector(retargeter._right_jaws),
                )
            environment_step = int(self._env.common_step_counter) if self._env is not None else 0
            self.telemetry.record_control_action(
                evidence_action,
                application_active=self.application_active,
                episode_id=self.episode_id,
                environment_step=environment_step,
            )
            return action

        device._get_controller_sample = instrumented_get_controller_sample
        device.advance = instrumented_advance

    def _wrap_lifecycle(self, command: str, callback: Any):
        def wrapped_callback() -> None:
            before_active = self.application_active
            episode_before = self.episode_id
            reset_before = self.reset_counter
            callback()
            if command == "START":
                self.application_active = True
            elif command == "STOP":
                self.application_active = False
            else:
                self._pending_reset = True
                return
            self.telemetry.record_lifecycle(
                command=command,
                before_active=before_active,
                after_active=self.application_active,
                episode_before=episode_before,
                episode_after=self.episode_id,
                handoff_phase_after=self._current_phase(),
                reset_counter_before=reset_before,
                reset_counter_after=self.reset_counter,
            )

        return wrapped_callback

    def _current_phase(self) -> int:
        if self._phase_machine is None:
            return 0
        return int(self._phase_machine.phase[0])

    def close(self) -> None:
        if self._haptics is not None:
            self._haptics.stop_all()
        self.telemetry.close()
