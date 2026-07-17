"""Project-local dVRK layout overrides for unrestricted Quest teleoperation."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

PSM_LAYOUT_VERTICAL_SHIFT_M = -0.1113

LEFT_PSM_ROOT_POS = (-0.160099840833, -0.087814884049, 0.0501)
RIGHT_PSM_ROOT_POS = (0.160099840833, -0.087814884049, 0.0501)
LEFT_PSM_ROOT_ROT_WXYZ = (0.991444861374, 0.0, 0.0, -0.130526192220)
RIGHT_PSM_ROOT_ROT_WXYZ = (0.991444861374, 0.0, 0.0, 0.130526192220)

LEFT_TOOL_HOME_POS_W = (-0.008, 0.0, -0.0513)
RIGHT_TOOL_HOME_POS_W = (0.008, 0.0, -0.0513)
LEFT_TOOL_HOME_ROT_XYZW = (
    0.236909824887,
    -0.440310948546,
    0.025955728065,
    0.865636351336,
)
RIGHT_TOOL_HOME_ROT_XYZW = (
    0.236909824887,
    0.440310948546,
    -0.025955728065,
    0.865636351336,
)

# Pure mode uses the fixed PSM root and remote-centre origin as one hinge.
# The pinned asset's tool shaft points along local -Z, and both authored homes
# place the tip on a 202.8 mm ray from that hinge.
LEFT_PSM_REMOTE_CENTER_POS_W = LEFT_PSM_ROOT_POS
RIGHT_PSM_REMOTE_CENTER_POS_W = RIGHT_PSM_ROOT_POS
PURE_TELEOP_SABRE_TOOL_TIP_AXIS = (0.0, 0.0, -1.0)
PURE_TELEOP_SABRE_SHAFT_LENGTH_M = math.dist(
    LEFT_PSM_REMOTE_CENTER_POS_W,
    LEFT_TOOL_HOME_POS_W,
)
if not math.isclose(
    PURE_TELEOP_SABRE_SHAFT_LENGTH_M,
    math.dist(RIGHT_PSM_REMOTE_CENTER_POS_W, RIGHT_TOOL_HOME_POS_W),
    abs_tol=1.0e-12,
):
    raise RuntimeError("pure teleop PSM homes require equal shaft lengths")

PURE_TELEOP_ABSOLUTE_HINGED_RETARGETING_ENABLED = True
PURE_TELEOP_CONTROLLER_TRANSLATION_ENABLED = True
PURE_TELEOP_ARM_CLUTCH_ENABLED = True
PURE_TELEOP_JAW_CLUTCH_ENABLED = False
PURE_TELEOP_ABSOLUTE_TRIGGER_JAW_ENABLED = True
PURE_TELEOP_ARM_CLUTCH_THRESHOLD = 0.5
PURE_TELEOP_PSM_INSERTION_JOINT_LOWER_M = 0.0565
PURE_TELEOP_PSM_INSERTION_JOINT_UPPER_M = 0.24
PURE_TELEOP_PSM_TOOL_RADIUS_OFFSET_M = 0.0028
PURE_TELEOP_SABRE_MIN_SHAFT_LENGTH_M = (
    PURE_TELEOP_PSM_INSERTION_JOINT_LOWER_M
    + PURE_TELEOP_PSM_TOOL_RADIUS_OFFSET_M
)
PURE_TELEOP_SABRE_MAX_SHAFT_LENGTH_M = (
    PURE_TELEOP_PSM_INSERTION_JOINT_UPPER_M
    + PURE_TELEOP_PSM_TOOL_RADIUS_OFFSET_M
)
PURE_TELEOP_AXIAL_TRANSLATION_SCALE = 1.0
PURE_TELEOP_SABRE_YAW_LIMIT_RAD = math.radians(85.0)
PURE_TELEOP_SABRE_PITCH_LIMIT_RAD = math.radians(48.0)
PURE_TELEOP_SABRE_POLE_HORIZONTAL_NORM_THRESHOLD = 0.02
PURE_TELEOP_SABRE_REACQUISITION_ORIENTATION_STEP_LIMIT_RAD = math.radians(45.0)
PURE_TELEOP_RETARGETING_MODE = "clutched_absolute_hinged_sabre_with_axial_insertion"

NEEDLE_RESET_POS = (-0.008751878984, -0.003081114514, -0.052931183028)
NEEDLE_RESET_ROT_WXYZ = (
    0.757438615755,
    0.111339563922,
    0.626494521034,
    0.146269686888,
)

SUTURE_PAD_ROOT_POS = (0.0, 0.004618802, -0.093063338)
SUTURE_PAD_TOP_LOCAL_Z_M = 0.033429999
SHAFT_INTERSECTION_CLEARANCE_M = 0.003
SHAFT_INTERSECTION_Z_M = SUTURE_PAD_ROOT_POS[2] + SUTURE_PAD_TOP_LOCAL_Z_M + SHAFT_INTERSECTION_CLEARANCE_M

# These bounds keep the upstream Cartesian kernel constructible until the
# application-local hinged kernels replace it. They are not used by the active
# absolute-orientation mapping.
PURE_TELEOP_WORKSPACE_LOWER_W = (-0.075, -0.052, -0.072)
PURE_TELEOP_WORKSPACE_UPPER_W = (0.075, 0.061, 0.001)

# The task ground is retained but hidden so it does not create an artificial
# infinite horizon behind the close tabletop composition.
PURE_TELEOP_GROUND_VISIBLE = False

# Free teleoperation does not instantiate the needle or its four filtered jaw
# contact sensors. Setting this one flag to True restores the pinned needle,
# reset, observation, phase and reward layer without changing upstream sources.
# The committed checkpoint remains the exact restoration point for every tuning
# value, including cadence, translation gain and the guarded left jaw action.
PURE_TELEOP_NEEDLE_TASK_ENABLED = False
PURE_TELEOP_SUTURE_PAD_ENABLED = PURE_TELEOP_NEEDLE_TASK_ENABLED
PURE_TELEOP_JAW_COLLISION_PHYSICS_ENABLED = PURE_TELEOP_NEEDLE_TASK_ENABLED
PURE_TELEOP_PSM_CONTACT_REPORTING_ENABLED = PURE_TELEOP_NEEDLE_TASK_ENABLED
PURE_TELEOP_TRIGGER_JAW_CONTROL_ENABLED = True
PURE_TELEOP_PSM_GRAVITY_ENABLED = False

# Six application-local targets approach the tools without gravity. Their first
# PSM contact transfers motion to PhysX, enables gravity and emits one haptic
# event for the striking hand. A missed or fallen target is recycled to its
# authored lane. These targets are intentionally absent from the pinned needle
# task and from every upstream asset or environment configuration.
PURE_TELEOP_BRICKS_ENABLED = not PURE_TELEOP_NEEDLE_TASK_ENABLED
PURE_TELEOP_BRICK_LAYOUT_REVISION = 4
PURE_TELEOP_BRICK_IDS = (
    "left_1",
    "right_1",
    "left_2",
    "right_2",
    "left_3",
    "right_3",
)
PURE_TELEOP_BRICK_LANES = {
    brick_id: brick_id.split("_", maxsplit=1)[0]
    for brick_id in PURE_TELEOP_BRICK_IDS
}
PURE_TELEOP_BRICK_PRIM_NAMES = {
    brick_id: f"SabreBrick{lane.title()}{brick_id.rsplit('_', maxsplit=1)[1]}"
    for brick_id, lane in PURE_TELEOP_BRICK_LANES.items()
}
PURE_TELEOP_BRICK_SIZES_M = {
    "left_1": (0.048, 0.038, 0.038),
    "right_1": (0.064, 0.038, 0.038),
    "left_2": (0.080, 0.038, 0.038),
    "right_2": (0.096, 0.038, 0.038),
    "left_3": (0.064, 0.038, 0.038),
    "right_3": (0.080, 0.038, 0.038),
}
PURE_TELEOP_BRICK_MASS_KG = 0.055
PURE_TELEOP_BRICK_APPROACH_SPEEDS_M_S = {
    "left_1": 0.160,
    "right_1": 0.176,
    "left_2": 0.192,
    "right_2": 0.208,
    "left_3": 0.224,
    "right_3": 0.240,
}
PURE_TELEOP_BRICK_RANDOM_SPEEDS_M_S = (
    0.160,
    0.176,
    0.192,
    0.208,
    0.224,
    0.240,
)
PURE_TELEOP_BRICK_RANDOM_HEIGHTS_M = (-0.040, -0.018, 0.004, 0.026)
PURE_TELEOP_BRICK_CONTACT_FORCE_THRESHOLD_N = 0.01
PURE_TELEOP_BRICK_MISS_Y_M = -0.16
PURE_TELEOP_BRICK_FALL_Z_M = -0.42
PURE_TELEOP_BRICK_FALL_TIMEOUT_S = 4.0
PURE_TELEOP_BRICK_HAPTIC_INTENSITY = 0.72
PURE_TELEOP_BRICK_HAPTIC_DURATION_S = 0.055
PURE_TELEOP_BRICK_HAPTIC_FREQUENCY_HZ = 0.0
PURE_TELEOP_BRICK_HIT_SPEED_M_S = 2.0
PURE_TELEOP_BRICK_PSM_CONTACT_FILTERS = {
    side: tuple(
        f"{{ENV_REGEX_NS}}/{psm_name}/{body_name}"
        for body_name in (
            "psm_main_insertion_link_2",
            "psm_main_insertion_link_3",
            "psm_tool_roll_link",
            "psm_tool_pitch_link",
            "psm_tool_yaw_link",
        )
    )
    for side, psm_name in (("left", "LeftPSM"), ("right", "RightPSM"))
}
PURE_TELEOP_BRICK_START_POSITIONS_W = {
    "left_1": (-0.064, 0.240, -0.040),
    "right_1": (0.064, 0.285, -0.018),
    "left_2": (-0.064, 0.330, 0.004),
    "right_2": (0.064, 0.375, 0.026),
    "left_3": (-0.064, 0.375, -0.018),
    "right_3": (0.064, 0.435, 0.004),
}
PURE_TELEOP_BRICK_COLOURS = {
    "left_1": (0.92, 0.12, 0.56),
    "right_1": (0.08, 0.28, 1.00),
    "left_2": (0.55, 0.12, 0.92),
    "right_2": (1.00, 0.35, 0.65),
    "left_3": (0.04, 0.78, 0.94),
    "right_3": (0.18, 0.05, 0.56),
}
PURE_TELEOP_BRICK_RANDOM_COLOURS = tuple(
    PURE_TELEOP_BRICK_COLOURS[brick_id]
    for brick_id in PURE_TELEOP_BRICK_IDS
)

# The upstream Cartesian kernel is constructed before the project-local hinged
# kernel replaces it. Keep that temporary kernel's positive scale neutral. The
# active kernel applies its own collinear insertion scale after clutching.
PURE_TELEOP_TRANSLATION_SCALE = 1.0

# The pinned contact task starts at 240 Hz. With no free needle or filtered
# contacts, free teleoperation can run physics at 120 Hz. Rendering every second
# step requests a nominal 60 Hz OpenXR refresh. Physical Spark traces predict
# about 11 fresh poses and frames per wall-clock second, twice the old rate,
# without the saturation risk of rendering every step.
PINNED_NEEDLE_TASK_PHYSICS_DT_S = 1.0 / 240.0
PURE_TELEOP_DECIMATION = 1
PURE_TELEOP_RENDER_INTERVAL = 2
PURE_TELEOP_PHYSICS_DT_S = 1.0 / 120.0

# The qualified task limits the jaws to 2.1 rad/s.  On the Spark XR path the
# renderer time-dilates that nominal 0.249 s full travel into several wall-clock
# seconds.  A physical Quest trial showed that a 50 ms free-motion stroke hit
# the velocity cap and could dislodge the needle.  This 100 ms stroke halves the
# peak per-step motion while preserving the jaw joint drive, stiffness, damping
# and effort limit. Jaw contact is restored only with the needle-task layer.
PURE_TELEOP_JAW_CLOSE_TIME_S = 0.10
PURE_TELEOP_JAW_VELOCITY_LIMIT_RAD_S = math.pi / 6.0 / PURE_TELEOP_JAW_CLOSE_TIME_S


def _required_attr(value: Any, name: str, context: str) -> Any:
    result = getattr(value, name, None)
    if result is None:
        raise ValueError(f"pure teleop layout requires {context}.{name}")
    return result


def _dvrk_retargeter(env_cfg: Any) -> Any:
    teleop_devices = _required_attr(env_cfg, "teleop_devices", "environment")
    devices = _required_attr(teleop_devices, "devices", "teleop devices")
    try:
        controller = devices["motion_controllers"]
    except (KeyError, TypeError) as exc:
        raise ValueError("pure teleop layout requires the motion_controllers device") from exc
    retargeters = _required_attr(controller, "retargeters", "motion controller")
    for retargeter in retargeters:
        if hasattr(retargeter, "left") and hasattr(retargeter, "right"):
            return retargeter
    raise ValueError("pure teleop layout requires a bilateral dVRK retargeter")


def _apply_fast_jaw_actuator(psm_cfg: Any, label: str) -> None:
    actuators = _required_attr(psm_cfg, "actuators", label)
    try:
        jaw_actuator = actuators["jaws"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"pure teleop layout requires {label}.actuators['jaws']") from exc
    replace_actuator = getattr(jaw_actuator, "replace", None)
    if not callable(replace_actuator):
        raise ValueError(f"pure teleop layout requires a replaceable {label} jaw actuator")
    psm_cfg.actuators = {
        **actuators,
        "jaws": replace_actuator(
            velocity_limit_sim=PURE_TELEOP_JAW_VELOCITY_LIMIT_RAD_S,
        ),
    }


_DVRK_JAW_BODY_NAMES = (
    "psm_tool_gripper1_link",
    "psm_tool_gripper2_link",
)


def _spawn_psm_without_jaw_collisions(
    prim_path: str,
    cfg: Any,
    translation: tuple[float, float, float] | None = None,
    orientation: tuple[float, float, float, float] | None = None,
    **kwargs: Any,
) -> Any:
    """Spawn one PSM and disable only its jaw collision descendants."""
    from isaaclab.sim.spawners.from_files import spawn_from_usd
    from isaaclab.sim.utils import find_matching_prim_paths, get_current_stage
    from pxr import Usd, UsdPhysics

    spawned = spawn_from_usd(
        prim_path,
        cfg,
        translation=translation,
        orientation=orientation,
        **kwargs,
    )
    stage = get_current_stage()
    root_paths = find_matching_prim_paths(prim_path)
    if not root_paths:
        raise RuntimeError(f"jaw collision override resolved no PSM roots for {prim_path!r}")
    for root_path in root_paths:
        for body_name in _DVRK_JAW_BODY_NAMES:
            body_path = f"{root_path}/{body_name}"
            body_prim = stage.GetPrimAtPath(body_path)
            if not body_prim:
                raise RuntimeError(f"jaw collision override could not find {body_path}")
            collision_prims = [
                prim
                for prim in Usd.PrimRange(body_prim)
                if prim.HasAPI(UsdPhysics.CollisionAPI)
            ]
            if not collision_prims:
                raise RuntimeError(f"jaw collision override found no collision shapes under {body_path}")
            for collision_prim in collision_prims:
                UsdPhysics.CollisionAPI(collision_prim).CreateCollisionEnabledAttr(
                    False
                ).Set(False)
    return spawned


def _disable_jaw_contact_physics(psm_cfg: Any, label: str) -> None:
    """Disable jaw collision solving and unused PhysX contact reports."""
    spawn = _required_attr(psm_cfg, "spawn", label)
    replace_spawn = getattr(spawn, "replace", None)
    if not callable(replace_spawn):
        raise ValueError(f"pure teleop layout requires a replaceable {label} spawn config")
    psm_cfg.spawn = replace_spawn(
        func=_spawn_psm_without_jaw_collisions,
        activate_contact_sensors=False,
    )


def _make_gravity_disabled_rigid_props() -> Any:
    import isaaclab.sim as sim_utils

    return sim_utils.RigidBodyPropertiesCfg(disable_gravity=True)


def _disable_psm_gravity(psm_cfg: Any, label: str) -> None:
    """Remove joint sag while preserving the fixed root and all live drives."""
    spawn = _required_attr(psm_cfg, "spawn", label)
    replace_spawn = getattr(spawn, "replace", None)
    if not callable(replace_spawn):
        raise ValueError(f"pure teleop layout requires a replaceable {label} spawn config")
    articulation_props = _required_attr(spawn, "articulation_props", f"{label} spawn")
    if getattr(articulation_props, "fix_root_link", None) is not True:
        raise ValueError(f"pure teleop layout requires a fixed {label} root link")
    rigid_props = getattr(spawn, "rigid_props", None)
    if rigid_props is None:
        rigid_props = _make_gravity_disabled_rigid_props()
    else:
        replace_rigid_props = getattr(rigid_props, "replace", None)
        if not callable(replace_rigid_props):
            raise ValueError(
                f"pure teleop layout requires replaceable {label} rigid body properties"
            )
        rigid_props = replace_rigid_props(disable_gravity=True)
    psm_cfg.spawn = replace_spawn(rigid_props=rigid_props)


_NEEDLE_CONTACT_SENSOR_NAMES = (
    "left_jaw_1_needle_contact",
    "left_jaw_2_needle_contact",
    "right_jaw_1_needle_contact",
    "right_jaw_2_needle_contact",
)
_NEEDLE_POLICY_TERM_NAMES = (
    "needle_pose_w",
    "needle_velocity_w",
    "jaw_needle_contact_force",
    "handoff_phase",
)
_NEEDLE_REWARD_TERM_NAMES = (
    "phase_progress",
    "retained_lift",
)


def _disable_needle_task(env_cfg: Any, scene: Any) -> None:
    """Remove the free needle and every manager term that depends on it."""
    _required_attr(scene, "needle", "scene")
    for name in _NEEDLE_CONTACT_SENSOR_NAMES:
        _required_attr(scene, name, "scene")

    observations = _required_attr(env_cfg, "observations", "environment")
    policy = _required_attr(observations, "policy", "observations")
    for name in _NEEDLE_POLICY_TERM_NAMES:
        _required_attr(policy, name, "policy observations")
    _required_attr(observations, "subtask_terms", "observations")

    events = _required_attr(env_cfg, "events", "environment")
    reset_all = _required_attr(events, "reset_all", "events")
    replace_reset = getattr(reset_all, "replace", None)
    if not callable(replace_reset):
        raise ValueError("pure teleop layout requires a replaceable reset event")
    rewards = _required_attr(env_cfg, "rewards", "environment")
    for name in _NEEDLE_REWARD_TERM_NAMES:
        _required_attr(rewards, name, "rewards")

    scene.needle = None
    for name in _NEEDLE_CONTACT_SENSOR_NAMES:
        setattr(scene, name, None)
    for name in _NEEDLE_POLICY_TERM_NAMES:
        setattr(policy, name, None)
    observations.subtask_terms = None
    events.reset_all = replace_reset(func=_reset_psms_to_default, params={})
    for name in _NEEDLE_REWARD_TERM_NAMES:
        setattr(rewards, name, None)


def _spawn_coloured_sabre_brick(
    prim_path: str,
    cfg: Any,
    translation: tuple[float, float, float] | None = None,
    orientation: tuple[float, float, float, float] | None = None,
    **kwargs: Any,
) -> Any:
    """Spawn one cuboid and author colour without the incompatible Kit material helper."""
    from isaaclab.sim.spawners.shapes import spawn_cuboid
    from isaaclab.sim.utils import find_matching_prim_paths, get_current_stage
    from pxr import Gf, UsdGeom

    spawned = spawn_cuboid(
        prim_path,
        cfg,
        translation=translation,
        orientation=orientation,
        **kwargs,
    )
    stage = get_current_stage()
    root_paths = find_matching_prim_paths(prim_path)
    if not root_paths:
        raise RuntimeError(f"sabre brick colour resolved no prims for {prim_path!r}")
    prim_name_to_id = {
        prim_name: brick_id
        for brick_id, prim_name in PURE_TELEOP_BRICK_PRIM_NAMES.items()
    }
    for root_path in root_paths:
        prim_name = root_path.rsplit("/", maxsplit=1)[-1]
        brick_id = prim_name_to_id.get(prim_name)
        if brick_id is None:
            raise RuntimeError(f"unrecognised sabre brick path: {root_path}")
        mesh_path = f"{root_path}/geometry/mesh"
        mesh_prim = stage.GetPrimAtPath(mesh_path)
        if not mesh_prim:
            raise RuntimeError(f"sabre brick mesh is missing: {mesh_path}")
        gprim = UsdGeom.Gprim(mesh_prim)
        if not gprim:
            raise RuntimeError(f"sabre brick mesh is not a Gprim: {mesh_path}")
        colour = Gf.Vec3f(*PURE_TELEOP_BRICK_COLOURS[brick_id])
        if gprim.CreateDisplayColorAttr().Set([colour]) is False:
            raise RuntimeError(f"failed to author sabre brick colour: {mesh_path}")
    return spawned


def _add_sabre_bricks(scene: Any) -> None:
    """Add six gravity-free, contact-reporting targets to pure teleoperation."""
    import isaaclab.sim as sim_utils
    from isaaclab.assets import RigidObjectCfg
    from isaaclab.sensors import ContactSensorCfg

    psm_filters = [
        path
        for side in ("left", "right")
        for path in PURE_TELEOP_BRICK_PSM_CONTACT_FILTERS[side]
    ]
    for brick_id in PURE_TELEOP_BRICK_IDS:
        object_name = f"sabre_brick_{brick_id}"
        sensor_name = f"{object_name}_contact"
        prim_name = PURE_TELEOP_BRICK_PRIM_NAMES[brick_id]
        setattr(
            scene,
            object_name,
            RigidObjectCfg(
                prim_path=f"{{ENV_REGEX_NS}}/{prim_name}",
                spawn=sim_utils.CuboidCfg(
                    func=_spawn_coloured_sabre_brick,
                    size=PURE_TELEOP_BRICK_SIZES_M[brick_id],
                    rigid_props=sim_utils.RigidBodyPropertiesCfg(
                        rigid_body_enabled=True,
                        kinematic_enabled=False,
                        disable_gravity=True,
                        linear_damping=0.01,
                        angular_damping=0.04,
                        max_depenetration_velocity=1.0,
                        solver_position_iteration_count=8,
                        solver_velocity_iteration_count=2,
                    ),
                    collision_props=sim_utils.CollisionPropertiesCfg(
                        collision_enabled=True,
                    ),
                    mass_props=sim_utils.MassPropertiesCfg(
                        mass=PURE_TELEOP_BRICK_MASS_KG,
                    ),
                    activate_contact_sensors=True,
                ),
                init_state=RigidObjectCfg.InitialStateCfg(
                    pos=PURE_TELEOP_BRICK_START_POSITIONS_W[brick_id],
                    rot=(1.0, 0.0, 0.0, 0.0),
                    lin_vel=(
                        0.0,
                        -PURE_TELEOP_BRICK_APPROACH_SPEEDS_M_S[brick_id],
                        0.0,
                    ),
                    ang_vel=(0.0, 0.0, 0.0),
                ),
            ),
        )
        setattr(
            scene,
            sensor_name,
            ContactSensorCfg(
                prim_path=f"{{ENV_REGEX_NS}}/{prim_name}",
                filter_prim_paths_expr=psm_filters,
                track_pose=True,
                update_period=0.0,
                history_length=1,
                force_threshold=PURE_TELEOP_BRICK_CONTACT_FORCE_THRESHOLD_N,
                debug_vis=False,
            ),
        )


def _reset_psms_to_default(env: Any, env_ids: Any) -> None:
    """Restore both PSM joint states and targets without a needle state write."""
    import torch

    if env_ids is None:
        env_ids = torch.arange(env.num_envs, dtype=torch.long, device=env.device)
    else:
        env_ids = env_ids.to(device=env.device, dtype=torch.long)

    for asset_name in ("left_psm", "right_psm"):
        psm = env.scene[asset_name]
        joint_pos = psm.data.default_joint_pos[env_ids].clone()
        joint_vel = torch.zeros_like(joint_pos)
        psm.write_joint_state_to_sim(joint_pos, joint_vel, env_ids=env_ids)
        psm.set_joint_position_target(joint_pos, env_ids=env_ids)
        psm.set_joint_velocity_target(joint_vel, env_ids=env_ids)


def _set_jaw_reset_open(psm_cfg: Any, side_cfg: Any, label: str) -> None:
    """Start one PSM open while preserving its arm home and live jaw action."""
    init_state = _required_attr(psm_cfg, "init_state", label)
    joint_pos = _required_attr(init_state, "joint_pos", f"{label} initial state")
    jaw_open = _required_attr(side_cfg, "jaw_open", f"{label} retargeter")
    if len(jaw_open) != 2:
        raise ValueError(f"pure teleop layout requires two {label} open jaw positions")
    jaw_names = ("psm_tool_gripper1_joint", "psm_tool_gripper2_joint")
    for name in jaw_names:
        if name not in joint_pos:
            raise ValueError(f"pure teleop layout requires {label} initial joint {name}")
    joint_pos.update(dict(zip(jaw_names, jaw_open, strict=True)))


def apply_pure_teleop_layout(env_cfg: Any) -> Any:
    """Apply the operator-authored dVRK free-teleoperation configuration.

    Root transforms, retargeter homes, workspace heights, ground visibility and
    the left jaw action are changed. The default mode removes the needle and
    suture-pad task layer but preserves bilateral trigger jaw control and the
    stable 18D action ABI. It uses 120 Hz physics and renders every second step
    for a nominal 60 Hz OpenXR refresh.
    """

    scene = _required_attr(env_cfg, "scene", "environment")
    left_psm = _required_attr(scene, "left_psm", "scene")
    right_psm = _required_attr(scene, "right_psm", "scene")
    needle = _required_attr(scene, "needle", "scene")
    suture_pad = _required_attr(scene, "suture_pad", "scene")
    ground = _required_attr(scene, "ground", "scene")
    sim = _required_attr(env_cfg, "sim", "environment")
    if sim.dt != PINNED_NEEDLE_TASK_PHYSICS_DT_S:
        raise ValueError("pure teleop layout requires the contact-qualified 1/240 s physics timestep")

    left_init_state = _required_attr(left_psm, "init_state", "left PSM")
    right_init_state = _required_attr(right_psm, "init_state", "right PSM")
    ground_spawn = _required_attr(ground, "spawn", "ground")

    left_init_state.pos = LEFT_PSM_ROOT_POS
    left_init_state.rot = LEFT_PSM_ROOT_ROT_WXYZ
    right_init_state.pos = RIGHT_PSM_ROOT_POS
    right_init_state.rot = RIGHT_PSM_ROOT_ROT_WXYZ
    if PURE_TELEOP_NEEDLE_TASK_ENABLED:
        needle_init_state = _required_attr(needle, "init_state", "needle")
        pad_init_state = _required_attr(suture_pad, "init_state", "suture pad")
        needle_init_state.pos = NEEDLE_RESET_POS
        needle_init_state.rot = NEEDLE_RESET_ROT_WXYZ
        pad_init_state.pos = SUTURE_PAD_ROOT_POS
    else:
        _disable_needle_task(env_cfg, scene)
        scene.suture_pad = None
        if PURE_TELEOP_BRICKS_ENABLED:
            _add_sabre_bricks(scene)
    ground_spawn.visible = PURE_TELEOP_GROUND_VISIBLE

    retargeter = _dvrk_retargeter(env_cfg)
    side_overrides: dict[str, Any] = {
        "translation_scale": PURE_TELEOP_TRANSLATION_SCALE,
    }
    if not PURE_TELEOP_NEEDLE_TASK_ENABLED:
        side_overrides["initial_closedness"] = 0.0
    try:
        retargeter.left = replace(
            retargeter.left,
            home_position=LEFT_TOOL_HOME_POS_W,
            home_orientation=LEFT_TOOL_HOME_ROT_XYZW,
            workspace_lower=PURE_TELEOP_WORKSPACE_LOWER_W,
            workspace_upper=PURE_TELEOP_WORKSPACE_UPPER_W,
            **side_overrides,
        )
        retargeter.right = replace(
            retargeter.right,
            home_position=RIGHT_TOOL_HOME_POS_W,
            home_orientation=RIGHT_TOOL_HOME_ROT_XYZW,
            workspace_lower=PURE_TELEOP_WORKSPACE_LOWER_W,
            workspace_upper=PURE_TELEOP_WORKSPACE_UPPER_W,
            **side_overrides,
        )
    except TypeError as exc:
        raise ValueError("pure teleop layout requires dataclass side retargeter configurations") from exc

    actions = _required_attr(env_cfg, "actions", "environment")
    right_jaw_action = _required_attr(actions, "right_jaw_action", "actions")
    replace_action = getattr(right_jaw_action, "replace", None)
    if not callable(replace_action):
        raise ValueError("pure teleop layout requires a replaceable right jaw action")
    unrestricted_left_jaw = replace_action(asset_name="left_psm")
    if unrestricted_left_jaw is right_jaw_action:
        raise ValueError("right jaw action replacement must return an independent config")
    actions.left_jaw_action = unrestricted_left_jaw

    if not PURE_TELEOP_NEEDLE_TASK_ENABLED:
        _set_jaw_reset_open(left_psm, retargeter.left, "left PSM")
        _set_jaw_reset_open(right_psm, retargeter.right, "right PSM")
        _disable_jaw_contact_physics(left_psm, "left PSM")
        _disable_jaw_contact_physics(right_psm, "right PSM")
        _disable_psm_gravity(left_psm, "left PSM")
        _disable_psm_gravity(right_psm, "right PSM")

    _apply_fast_jaw_actuator(left_psm, "left PSM")
    _apply_fast_jaw_actuator(right_psm, "right PSM")
    env_cfg.decimation = PURE_TELEOP_DECIMATION
    sim.dt = PURE_TELEOP_PHYSICS_DT_S
    sim.render_interval = PURE_TELEOP_RENDER_INTERVAL

    return env_cfg


__all__ = [
    "LEFT_PSM_REMOTE_CENTER_POS_W",
    "LEFT_PSM_ROOT_POS",
    "LEFT_PSM_ROOT_ROT_WXYZ",
    "LEFT_TOOL_HOME_POS_W",
    "LEFT_TOOL_HOME_ROT_XYZW",
    "NEEDLE_RESET_POS",
    "NEEDLE_RESET_ROT_WXYZ",
    "PINNED_NEEDLE_TASK_PHYSICS_DT_S",
    "PSM_LAYOUT_VERTICAL_SHIFT_M",
    "PURE_TELEOP_ABSOLUTE_HINGED_RETARGETING_ENABLED",
    "PURE_TELEOP_ABSOLUTE_TRIGGER_JAW_ENABLED",
    "PURE_TELEOP_ARM_CLUTCH_ENABLED",
    "PURE_TELEOP_ARM_CLUTCH_THRESHOLD",
    "PURE_TELEOP_AXIAL_TRANSLATION_SCALE",
    "PURE_TELEOP_BRICKS_ENABLED",
    "PURE_TELEOP_BRICK_APPROACH_SPEEDS_M_S",
    "PURE_TELEOP_BRICK_COLOURS",
    "PURE_TELEOP_BRICK_CONTACT_FORCE_THRESHOLD_N",
    "PURE_TELEOP_BRICK_FALL_TIMEOUT_S",
    "PURE_TELEOP_BRICK_FALL_Z_M",
    "PURE_TELEOP_BRICK_HAPTIC_DURATION_S",
    "PURE_TELEOP_BRICK_HAPTIC_FREQUENCY_HZ",
    "PURE_TELEOP_BRICK_HAPTIC_INTENSITY",
    "PURE_TELEOP_BRICK_HIT_SPEED_M_S",
    "PURE_TELEOP_BRICK_IDS",
    "PURE_TELEOP_BRICK_LANES",
    "PURE_TELEOP_BRICK_LAYOUT_REVISION",
    "PURE_TELEOP_BRICK_MASS_KG",
    "PURE_TELEOP_BRICK_MISS_Y_M",
    "PURE_TELEOP_BRICK_PRIM_NAMES",
    "PURE_TELEOP_BRICK_PSM_CONTACT_FILTERS",
    "PURE_TELEOP_BRICK_RANDOM_COLOURS",
    "PURE_TELEOP_BRICK_RANDOM_HEIGHTS_M",
    "PURE_TELEOP_BRICK_RANDOM_SPEEDS_M_S",
    "PURE_TELEOP_BRICK_SIZES_M",
    "PURE_TELEOP_BRICK_START_POSITIONS_W",
    "PURE_TELEOP_CONTROLLER_TRANSLATION_ENABLED",
    "PURE_TELEOP_DECIMATION",
    "PURE_TELEOP_GROUND_VISIBLE",
    "PURE_TELEOP_JAW_CLOSE_TIME_S",
    "PURE_TELEOP_JAW_CLUTCH_ENABLED",
    "PURE_TELEOP_JAW_COLLISION_PHYSICS_ENABLED",
    "PURE_TELEOP_JAW_VELOCITY_LIMIT_RAD_S",
    "PURE_TELEOP_NEEDLE_TASK_ENABLED",
    "PURE_TELEOP_PHYSICS_DT_S",
    "PURE_TELEOP_PSM_CONTACT_REPORTING_ENABLED",
    "PURE_TELEOP_PSM_GRAVITY_ENABLED",
    "PURE_TELEOP_PSM_INSERTION_JOINT_LOWER_M",
    "PURE_TELEOP_PSM_INSERTION_JOINT_UPPER_M",
    "PURE_TELEOP_PSM_TOOL_RADIUS_OFFSET_M",
    "PURE_TELEOP_RENDER_INTERVAL",
    "PURE_TELEOP_RETARGETING_MODE",
    "PURE_TELEOP_SABRE_MAX_SHAFT_LENGTH_M",
    "PURE_TELEOP_SABRE_MIN_SHAFT_LENGTH_M",
    "PURE_TELEOP_SABRE_PITCH_LIMIT_RAD",
    "PURE_TELEOP_SABRE_POLE_HORIZONTAL_NORM_THRESHOLD",
    "PURE_TELEOP_SABRE_REACQUISITION_ORIENTATION_STEP_LIMIT_RAD",
    "PURE_TELEOP_SABRE_SHAFT_LENGTH_M",
    "PURE_TELEOP_SABRE_TOOL_TIP_AXIS",
    "PURE_TELEOP_SABRE_YAW_LIMIT_RAD",
    "PURE_TELEOP_SUTURE_PAD_ENABLED",
    "PURE_TELEOP_TRANSLATION_SCALE",
    "PURE_TELEOP_TRIGGER_JAW_CONTROL_ENABLED",
    "PURE_TELEOP_WORKSPACE_LOWER_W",
    "PURE_TELEOP_WORKSPACE_UPPER_W",
    "RIGHT_PSM_REMOTE_CENTER_POS_W",
    "RIGHT_PSM_ROOT_POS",
    "RIGHT_PSM_ROOT_ROT_WXYZ",
    "RIGHT_TOOL_HOME_POS_W",
    "RIGHT_TOOL_HOME_ROT_XYZW",
    "SHAFT_INTERSECTION_CLEARANCE_M",
    "SHAFT_INTERSECTION_Z_M",
    "SUTURE_PAD_ROOT_POS",
    "SUTURE_PAD_TOP_LOCAL_Z_M",
    "apply_pure_teleop_layout",
]
