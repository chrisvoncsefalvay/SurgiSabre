import math
import sys
from dataclasses import dataclass, replace
from itertools import pairwise
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import surgisabre.layout as layout  # noqa: E402
from surgisabre.layout import (  # noqa: E402
    LEFT_PSM_ROOT_POS,
    LEFT_PSM_ROOT_ROT_WXYZ,
    LEFT_TOOL_HOME_POS_W,
    LEFT_TOOL_HOME_ROT_XYZW,
    NEEDLE_RESET_POS,
    NEEDLE_RESET_ROT_WXYZ,
    PINNED_NEEDLE_TASK_PHYSICS_DT_S,
    PSM_LAYOUT_VERTICAL_SHIFT_M,
    PURE_TELEOP_DECIMATION,
    PURE_TELEOP_GROUND_VISIBLE,
    PURE_TELEOP_JAW_CLOSE_TIME_S,
    PURE_TELEOP_JAW_COLLISION_PHYSICS_ENABLED,
    PURE_TELEOP_JAW_VELOCITY_LIMIT_RAD_S,
    PURE_TELEOP_NEEDLE_TASK_ENABLED,
    PURE_TELEOP_PHYSICS_DT_S,
    PURE_TELEOP_PSM_CONTACT_REPORTING_ENABLED,
    PURE_TELEOP_PSM_GRAVITY_ENABLED,
    PURE_TELEOP_RENDER_INTERVAL,
    PURE_TELEOP_TRANSLATION_SCALE,
    PURE_TELEOP_TRIGGER_JAW_CONTROL_ENABLED,
    PURE_TELEOP_WORKSPACE_LOWER_W,
    PURE_TELEOP_WORKSPACE_UPPER_W,
    RIGHT_PSM_ROOT_POS,
    RIGHT_PSM_ROOT_ROT_WXYZ,
    RIGHT_TOOL_HOME_POS_W,
    RIGHT_TOOL_HOME_ROT_XYZW,
    SHAFT_INTERSECTION_CLEARANCE_M,
    SHAFT_INTERSECTION_Z_M,
    SUTURE_PAD_ROOT_POS,
    SUTURE_PAD_TOP_LOCAL_Z_M,
    apply_pure_teleop_layout,
)

_REAL_ADD_SABRE_BRICKS = layout._add_sabre_bricks


@pytest.fixture(autouse=True)
def _stub_sabre_bricks(monkeypatch):
    """Keep general layout tests independent of the Isaac Lab installation."""

    def add_bricks(scene):
        for brick_id in layout.PURE_TELEOP_BRICK_IDS:
            setattr(scene, f"sabre_brick_{brick_id}", object())
            setattr(scene, f"sabre_brick_{brick_id}_contact", object())

    monkeypatch.setattr(layout, "_add_sabre_bricks", add_bricks)


@dataclass
class NormalJawAction:
    asset_name: str
    joint_names: list[str]
    scale: float = 1.0
    offset: float = 0.0
    use_default_offset: bool = False
    preserve_order: bool = True

    def replace(self, **changes):
        return replace(self, **changes)


@dataclass
class GuardedJawAction(NormalJawAction):
    phase_cfg: object | None = None
    release_aperture_threshold_rad: float = 0.0
    hold_jaw_pos: tuple[float, float] = (0.0, 0.0)


@dataclass
class JawActuator:
    velocity_limit_sim: float
    stiffness: float = 0.00747
    damping: float = 0.0000996
    effort_limit_sim: float = 0.16

    def replace(self, **changes):
        return replace(self, **changes)


@dataclass
class RigidBodyProperties:
    disable_gravity: bool = False
    linear_damping: float = 0.0

    def replace(self, **changes):
        return replace(self, **changes)


@dataclass
class ArticulationProperties:
    fix_root_link: bool = True
    solver_velocity_iteration_count: int = 4


@dataclass
class SpawnConfig:
    func: object | None = None
    activate_contact_sensors: bool = True
    collision_props: object | None = None
    rigid_props: object | None = None
    articulation_props: object | None = None

    def replace(self, **changes):
        return replace(self, **changes)


@dataclass
class EventTerm:
    func: object
    params: dict[str, object]

    def replace(self, **changes):
        return replace(self, **changes)


@dataclass(frozen=True)
class SideRetargeterConfig:
    home_position: tuple[float, float, float]
    home_orientation: tuple[float, float, float, float]
    workspace_lower: tuple[float, float, float] | None = None
    workspace_upper: tuple[float, float, float] | None = None
    translation_scale: float = 1.0
    orientation_offset: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    jaw_open: tuple[float, float] = (-math.pi / 6.0, math.pi / 6.0)
    jaw_closed: tuple[float, float] = (0.0, 0.0)
    initial_closedness: float = 0.0


def _environment_config() -> SimpleNamespace:
    jaw_joint_names = [
        "psm_tool_gripper1_joint",
        "psm_tool_gripper2_joint",
    ]
    left_joint_home = {
        "left_arm_joint": 0.25,
        "psm_tool_gripper1_joint": -0.02,
        "psm_tool_gripper2_joint": 0.02,
    }
    right_joint_home = {
        "right_arm_joint": -0.25,
        "psm_tool_gripper1_joint": -math.pi / 6.0,
        "psm_tool_gripper2_joint": math.pi / 6.0,
    }
    left_retargeter = SideRetargeterConfig(
        home_position=(-0.025, 0.0, 0.060),
        home_orientation=(0.0, 0.0, 0.0, 1.0),
        workspace_lower=(-0.18, -0.16, 0.015),
        workspace_upper=(0.18, 0.16, 0.20),
        initial_closedness=1.0,
    )
    right_retargeter = SideRetargeterConfig(
        home_position=(0.025, 0.0, 0.060),
        home_orientation=(0.0, 0.0, 0.0, 1.0),
        workspace_lower=(-0.18, -0.16, 0.015),
        workspace_upper=(0.18, 0.16, 0.20),
    )
    dvrk_retargeter = SimpleNamespace(
        left=left_retargeter,
        right=right_retargeter,
    )
    normal_right_jaw = NormalJawAction(
        asset_name="right_psm",
        joint_names=jaw_joint_names,
    )
    guarded_left_jaw = GuardedJawAction(
        asset_name="left_psm",
        joint_names=jaw_joint_names,
        phase_cfg=object(),
        hold_jaw_pos=(-0.1, 0.1),
    )
    left_jaw_actuator = JawActuator(velocity_limit_sim=2.1)
    right_jaw_actuator = JawActuator(velocity_limit_sim=2.1)
    return SimpleNamespace(
        decimation=1,
        sim=SimpleNamespace(dt=1.0 / 240.0, render_interval=1),
        scene=SimpleNamespace(
            left_psm=SimpleNamespace(
                spawn=SpawnConfig(
                    collision_props=object(),
                    rigid_props=RigidBodyProperties(),
                    articulation_props=ArticulationProperties(),
                ),
                init_state=SimpleNamespace(
                    pos=(-1.0, -1.0, -1.0),
                    rot=(1.0, 0.0, 0.0, 0.0),
                    joint_pos=left_joint_home,
                ),
                actuators={"arms": object(), "jaws": left_jaw_actuator},
            ),
            right_psm=SimpleNamespace(
                spawn=SpawnConfig(
                    collision_props=object(),
                    rigid_props=RigidBodyProperties(),
                    articulation_props=ArticulationProperties(),
                ),
                init_state=SimpleNamespace(
                    pos=(1.0, -1.0, -1.0),
                    rot=(1.0, 0.0, 0.0, 0.0),
                    joint_pos=right_joint_home,
                ),
                actuators={"arms": object(), "jaws": right_jaw_actuator},
            ),
            needle=SimpleNamespace(
                init_state=SimpleNamespace(
                    pos=(0.0, 0.0, 0.1),
                    rot=(1.0, 0.0, 0.0, 0.0),
                )
            ),
            left_jaw_1_needle_contact=object(),
            left_jaw_2_needle_contact=object(),
            right_jaw_1_needle_contact=object(),
            right_jaw_2_needle_contact=object(),
            suture_pad=SimpleNamespace(init_state=SimpleNamespace(pos=(0.45, 0.45, -0.20))),
            ground=SimpleNamespace(spawn=SimpleNamespace(visible=True)),
        ),
        teleop_devices=SimpleNamespace(devices={"motion_controllers": SimpleNamespace(retargeters=[dvrk_retargeter])}),
        actions=SimpleNamespace(
            left_jaw_action=guarded_left_jaw,
            right_jaw_action=normal_right_jaw,
        ),
        observations=SimpleNamespace(
            policy=SimpleNamespace(
                needle_pose_w=object(),
                needle_velocity_w=object(),
                jaw_needle_contact_force=object(),
                handoff_phase=object(),
                left_joint_pos=object(),
            ),
            subtask_terms=object(),
        ),
        events=SimpleNamespace(reset_all=EventTerm(func=object(), params={"phase_cfg": object()})),
        rewards=SimpleNamespace(
            phase_progress=object(),
            retained_lift=object(),
        ),
    )


def test_pure_teleop_adds_gravity_free_contact_reporting_bricks(monkeypatch) -> None:
    class Config:
        def __init__(self, **fields):
            vars(self).update(fields)

    class RigidObjectConfig(Config):
        InitialStateCfg = Config

    sim_module = ModuleType("isaaclab.sim")
    for name in (
        "CollisionPropertiesCfg",
        "CuboidCfg",
        "MassPropertiesCfg",
        "RigidBodyPropertiesCfg",
    ):
        setattr(sim_module, name, Config)
    assets_module = ModuleType("isaaclab.assets")
    assets_module.RigidObjectCfg = RigidObjectConfig
    sensors_module = ModuleType("isaaclab.sensors")
    sensors_module.ContactSensorCfg = Config
    isaaclab_module = ModuleType("isaaclab")
    isaaclab_module.sim = sim_module
    for name, module in {
        "isaaclab": isaaclab_module,
        "isaaclab.sim": sim_module,
        "isaaclab.assets": assets_module,
        "isaaclab.sensors": sensors_module,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    scene = SimpleNamespace()

    _REAL_ADD_SABRE_BRICKS(scene)

    for brick_id, expected_colour in layout.PURE_TELEOP_BRICK_COLOURS.items():
        brick = getattr(scene, f"sabre_brick_{brick_id}")
        sensor = getattr(scene, f"sabre_brick_{brick_id}_contact")
        assert brick.prim_path == (
            f"{{ENV_REGEX_NS}}/{layout.PURE_TELEOP_BRICK_PRIM_NAMES[brick_id]}"
        )
        assert brick.spawn.size == layout.PURE_TELEOP_BRICK_SIZES_M[brick_id]
        assert brick.spawn.rigid_props.disable_gravity is True
        assert brick.spawn.rigid_props.kinematic_enabled is False
        assert brick.spawn.collision_props.collision_enabled is True
        assert brick.spawn.activate_contact_sensors is True
        assert brick.spawn.mass_props.mass == layout.PURE_TELEOP_BRICK_MASS_KG
        assert brick.spawn.func is layout._spawn_coloured_sabre_brick
        assert not hasattr(brick.spawn, "visual_material")
        assert expected_colour == layout.PURE_TELEOP_BRICK_COLOURS[brick_id]
        assert brick.init_state.pos == layout.PURE_TELEOP_BRICK_START_POSITIONS_W[brick_id]
        assert brick.init_state.lin_vel == (
            0.0,
            -layout.PURE_TELEOP_BRICK_APPROACH_SPEEDS_M_S[brick_id],
            0.0,
        )
        assert sensor.prim_path == brick.prim_path
        assert sensor.force_threshold == layout.PURE_TELEOP_BRICK_CONTACT_FORCE_THRESHOLD_N
        assert sensor.filter_prim_paths_expr == [
            path
            for side in ("left", "right")
            for path in layout.PURE_TELEOP_BRICK_PSM_CONTACT_FILTERS[side]
        ]

    assert layout.PURE_TELEOP_BRICK_LAYOUT_REVISION == 4
    assert len(layout.PURE_TELEOP_BRICK_IDS) == 6
    assert set(layout.PURE_TELEOP_BRICK_SIZES_M) == set(layout.PURE_TELEOP_BRICK_IDS)
    assert set(layout.PURE_TELEOP_BRICK_START_POSITIONS_W) == set(
        layout.PURE_TELEOP_BRICK_IDS
    )
    assert set(layout.PURE_TELEOP_BRICK_APPROACH_SPEEDS_M_S) == set(
        layout.PURE_TELEOP_BRICK_IDS
    )
    assert set(layout.PURE_TELEOP_BRICK_COLOURS) == set(layout.PURE_TELEOP_BRICK_IDS)
    assert list(layout.PURE_TELEOP_BRICK_LANES.values()).count("left") == 3
    assert list(layout.PURE_TELEOP_BRICK_LANES.values()).count("right") == 3
    assert len(set(layout.PURE_TELEOP_BRICK_COLOURS.values())) == 6
    assert len({size[0] for size in layout.PURE_TELEOP_BRICK_SIZES_M.values()}) == 4
    assert len(
        {position[2] for position in layout.PURE_TELEOP_BRICK_START_POSITIONS_W.values()}
    ) == 4
    assert tuple(layout.PURE_TELEOP_BRICK_APPROACH_SPEEDS_M_S.values()) == (
        0.160,
        0.176,
        0.192,
        0.208,
        0.224,
        0.240,
    )
    assert layout.PURE_TELEOP_BRICK_RANDOM_SPEEDS_M_S == (
        0.160,
        0.176,
        0.192,
        0.208,
        0.224,
        0.240,
    )
    assert set(layout.PURE_TELEOP_BRICK_RANDOM_HEIGHTS_M) == {
        position[2]
        for position in layout.PURE_TELEOP_BRICK_START_POSITIONS_W.values()
    }
    assert set(layout.PURE_TELEOP_BRICK_RANDOM_COLOURS) == set(
        layout.PURE_TELEOP_BRICK_COLOURS.values()
    )
    assert layout.PURE_TELEOP_BRICK_HIT_SPEED_M_S == 2.0
    for lane in ("left", "right"):
        lane_starts = sorted(
            layout.PURE_TELEOP_BRICK_START_POSITIONS_W[brick_id][1]
            for brick_id in layout.PURE_TELEOP_BRICK_IDS
            if layout.PURE_TELEOP_BRICK_LANES[brick_id] == lane
        )
        assert all(
            trailing - leading >= 0.038
            for leading, trailing in pairwise(lane_starts)
        )
    assert all(
        abs(layout.PURE_TELEOP_BRICK_START_POSITIONS_W[brick_id][0])
        - layout.PURE_TELEOP_BRICK_SIZES_M[brick_id][0] / 2.0
        >= 0.015
        for brick_id in layout.PURE_TELEOP_BRICK_IDS
    )


@pytest.mark.parametrize("brick_id", layout.PURE_TELEOP_BRICK_IDS)
def test_sabre_brick_spawn_authors_display_colour_without_a_kit_material(
    monkeypatch,
    brick_id: str,
) -> None:
    class Attribute:
        def __init__(self):
            self.value = None

        def Set(self, value):
            self.value = value
            return True

    class Gprim:
        def __init__(self, _prim):
            self.colour = Attribute()

        def __bool__(self):
            return True

        def CreateDisplayColorAttr(self):
            return self.colour

    mesh_prim = object()
    stage = SimpleNamespace(GetPrimAtPath=lambda _path: mesh_prim)
    root_path = f"/World/envs/env_0/{layout.PURE_TELEOP_BRICK_PRIM_NAMES[brick_id]}"
    spawned = object()
    calls = []
    gprims = []

    def make_gprim(prim):
        result = Gprim(prim)
        gprims.append(result)
        return result

    pxr_module = ModuleType("pxr")
    pxr_module.Gf = SimpleNamespace(Vec3f=lambda *values: tuple(values))
    pxr_module.UsdGeom = SimpleNamespace(Gprim=make_gprim)
    shapes_module = ModuleType("isaaclab.sim.spawners.shapes")

    def spawn_cuboid(*args, **kwargs):
        calls.append((args, kwargs))
        return spawned

    shapes_module.spawn_cuboid = spawn_cuboid
    utils_module = ModuleType("isaaclab.sim.utils")
    utils_module.find_matching_prim_paths = lambda _path: [root_path]
    utils_module.get_current_stage = lambda: stage
    for name, module in {
        "pxr": pxr_module,
        "isaaclab": ModuleType("isaaclab"),
        "isaaclab.sim": ModuleType("isaaclab.sim"),
        "isaaclab.sim.spawners": ModuleType("isaaclab.sim.spawners"),
        "isaaclab.sim.spawners.shapes": shapes_module,
        "isaaclab.sim.utils": utils_module,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

    result = layout._spawn_coloured_sabre_brick(
        root_path,
        SimpleNamespace(),
        translation=(0.0, 0.0, 0.0),
    )

    assert result is spawned
    assert len(calls) == 1
    assert gprims[0].colour.value == [layout.PURE_TELEOP_BRICK_COLOURS[brick_id]]


def test_pure_teleop_layout_applies_authored_geometry_and_preserves_arm_homes() -> None:
    env_cfg = _environment_config()
    left_joint_home = env_cfg.scene.left_psm.init_state.joint_pos
    right_joint_home = env_cfg.scene.right_psm.init_state.joint_pos

    result = apply_pure_teleop_layout(env_cfg)

    assert result is env_cfg
    assert env_cfg.scene.left_psm.init_state.pos == LEFT_PSM_ROOT_POS
    assert env_cfg.scene.left_psm.init_state.rot == LEFT_PSM_ROOT_ROT_WXYZ
    assert env_cfg.scene.right_psm.init_state.pos == RIGHT_PSM_ROOT_POS
    assert env_cfg.scene.right_psm.init_state.rot == RIGHT_PSM_ROOT_ROT_WXYZ
    assert env_cfg.scene.left_psm.init_state.joint_pos is left_joint_home
    assert env_cfg.scene.right_psm.init_state.joint_pos is right_joint_home
    assert env_cfg.scene.needle is None
    assert env_cfg.scene.suture_pad is None
    assert env_cfg.scene.ground.spawn.visible is PURE_TELEOP_GROUND_VISIBLE is False


def test_pure_teleop_layout_updates_bilateral_retargeter_homes() -> None:
    env_cfg = _environment_config()
    retargeter = env_cfg.teleop_devices.devices["motion_controllers"].retargeters[0]

    apply_pure_teleop_layout(env_cfg)

    assert retargeter.left.home_position == LEFT_TOOL_HOME_POS_W
    assert retargeter.left.home_orientation == LEFT_TOOL_HOME_ROT_XYZW
    assert retargeter.right.home_position == RIGHT_TOOL_HOME_POS_W
    assert retargeter.right.home_orientation == RIGHT_TOOL_HOME_ROT_XYZW
    assert retargeter.left.translation_scale == PURE_TELEOP_TRANSLATION_SCALE == 1.0
    assert retargeter.right.translation_scale == PURE_TELEOP_TRANSLATION_SCALE
    assert retargeter.left.initial_closedness == 0.0
    assert retargeter.right.initial_closedness == 0.0
    assert retargeter.left.orientation_offset == (0.0, 0.0, 0.0, 1.0)
    assert retargeter.right.orientation_offset == (0.0, 0.0, 0.0, 1.0)
    assert retargeter.left.workspace_lower == PURE_TELEOP_WORKSPACE_LOWER_W
    assert retargeter.left.workspace_upper == PURE_TELEOP_WORKSPACE_UPPER_W
    assert retargeter.right.workspace_lower == PURE_TELEOP_WORKSPACE_LOWER_W
    assert retargeter.right.workspace_upper == PURE_TELEOP_WORKSPACE_UPPER_W
    assert retargeter.left.workspace_lower[2] <= retargeter.left.home_position[2]
    assert retargeter.left.home_position[2] <= retargeter.left.workspace_upper[2]
    assert retargeter.right.workspace_lower[2] <= retargeter.right.home_position[2]
    assert retargeter.right.home_position[2] <= retargeter.right.workspace_upper[2]


def test_pure_teleop_layout_replaces_guarded_left_jaw_with_normal_copy() -> None:
    env_cfg = _environment_config()
    right_jaw = env_cfg.actions.right_jaw_action

    apply_pure_teleop_layout(env_cfg)

    left_jaw = env_cfg.actions.left_jaw_action
    assert type(left_jaw) is NormalJawAction
    assert left_jaw is not right_jaw
    assert left_jaw.asset_name == "left_psm"
    assert left_jaw.joint_names == right_jaw.joint_names
    assert left_jaw.scale == right_jaw.scale
    assert left_jaw.offset == right_jaw.offset
    assert left_jaw.use_default_offset == right_jaw.use_default_offset
    assert left_jaw.preserve_order == right_jaw.preserve_order
    assert PURE_TELEOP_TRIGGER_JAW_CONTROL_ENABLED is True


def test_pure_teleop_layout_removes_only_needle_dependent_task_layer() -> None:
    env_cfg = _environment_config()
    left_joint_observation = env_cfg.observations.policy.left_joint_pos

    apply_pure_teleop_layout(env_cfg)

    assert PURE_TELEOP_NEEDLE_TASK_ENABLED is False
    assert env_cfg.scene.needle is None
    assert env_cfg.scene.left_jaw_1_needle_contact is None
    assert env_cfg.scene.left_jaw_2_needle_contact is None
    assert env_cfg.scene.right_jaw_1_needle_contact is None
    assert env_cfg.scene.right_jaw_2_needle_contact is None
    assert env_cfg.observations.policy.needle_pose_w is None
    assert env_cfg.observations.policy.needle_velocity_w is None
    assert env_cfg.observations.policy.jaw_needle_contact_force is None
    assert env_cfg.observations.policy.handoff_phase is None
    assert env_cfg.observations.policy.left_joint_pos is left_joint_observation
    assert env_cfg.observations.subtask_terms is None
    assert env_cfg.events.reset_all is not None
    assert env_cfg.events.reset_all.func is layout._reset_psms_to_default
    assert env_cfg.events.reset_all.params == {}
    assert env_cfg.rewards.phase_progress is None
    assert env_cfg.rewards.retained_lift is None
    assert env_cfg.actions.left_jaw_action is not None
    assert env_cfg.actions.right_jaw_action is not None
    assert PURE_TELEOP_PSM_CONTACT_REPORTING_ENABLED is False
    assert PURE_TELEOP_JAW_COLLISION_PHYSICS_ENABLED is False
    assert env_cfg.scene.left_psm.spawn.func is layout._spawn_psm_without_jaw_collisions
    assert env_cfg.scene.right_psm.spawn.func is layout._spawn_psm_without_jaw_collisions
    assert env_cfg.scene.left_psm.spawn.activate_contact_sensors is False
    assert env_cfg.scene.right_psm.spawn.activate_contact_sensors is False
    assert env_cfg.scene.left_psm.spawn.collision_props is not None
    assert env_cfg.scene.right_psm.spawn.collision_props is not None
    assert PURE_TELEOP_PSM_GRAVITY_ENABLED is False
    assert env_cfg.scene.left_psm.spawn.rigid_props.disable_gravity is True
    assert env_cfg.scene.right_psm.spawn.rigid_props.disable_gravity is True
    assert env_cfg.scene.left_psm.spawn.rigid_props.linear_damping == 0.0
    assert env_cfg.scene.right_psm.spawn.rigid_props.linear_damping == 0.0
    assert env_cfg.scene.left_psm.spawn.articulation_props.fix_root_link is True
    assert env_cfg.scene.right_psm.spawn.articulation_props.fix_root_link is True


def test_pure_teleop_layout_starts_both_jaws_open_without_removing_control() -> None:
    env_cfg = _environment_config()
    left_joint_pos = env_cfg.scene.left_psm.init_state.joint_pos
    right_joint_pos = env_cfg.scene.right_psm.init_state.joint_pos

    apply_pure_teleop_layout(env_cfg)

    expected = (-math.pi / 6.0, math.pi / 6.0)
    jaw_names = ("psm_tool_gripper1_joint", "psm_tool_gripper2_joint")
    assert tuple(left_joint_pos[name] for name in jaw_names) == expected
    assert tuple(right_joint_pos[name] for name in jaw_names) == expected
    assert env_cfg.actions.left_jaw_action.joint_names == list(jaw_names)
    assert env_cfg.actions.right_jaw_action.joint_names == list(jaw_names)


def test_pure_teleop_layout_builds_gravity_override_when_asset_has_none(
    monkeypatch,
) -> None:
    env_cfg = _environment_config()
    env_cfg.scene.left_psm.spawn.rigid_props = None
    env_cfg.scene.right_psm.spawn.rigid_props = None
    created = []

    def make_rigid_props():
        props = RigidBodyProperties(disable_gravity=True)
        created.append(props)
        return props

    monkeypatch.setattr(layout, "_make_gravity_disabled_rigid_props", make_rigid_props)

    apply_pure_teleop_layout(env_cfg)

    assert env_cfg.scene.left_psm.spawn.rigid_props is created[0]
    assert env_cfg.scene.right_psm.spawn.rigid_props is created[1]
    assert all(props.disable_gravity for props in created)


def test_pure_teleop_layout_refuses_an_unfixed_psm_root() -> None:
    env_cfg = _environment_config()
    env_cfg.scene.left_psm.spawn.articulation_props.fix_root_link = False

    with pytest.raises(ValueError, match="fixed left PSM root link"):
        apply_pure_teleop_layout(env_cfg)


def test_psm_spawn_wrapper_disables_every_jaw_collision_shape(monkeypatch) -> None:
    class FakeAttribute:
        def __init__(self):
            self.value = True

        def Set(self, value):
            self.value = value
            return True

    class FakePrim:
        def __init__(self, path, *, collision=False, children=()):
            self.path = path
            self.collision = collision
            self.children = list(children)
            self.collision_enabled = FakeAttribute()

        def __bool__(self):
            return True

        def HasAPI(self, _api):
            return self.collision

    class FakeCollisionAPI:
        def __init__(self, prim):
            self.prim = prim

        def CreateCollisionEnabledAttr(self, _default):
            return self.prim.collision_enabled

    root_path = "/World/envs/env_0/LeftPSM"
    collision_prims = {}
    body_prims = {}
    for body_name in ("psm_tool_gripper1_link", "psm_tool_gripper2_link"):
        collision = FakePrim(f"{root_path}/{body_name}/collisions", collision=True)
        collision_prims[body_name] = collision
        body_prims[f"{root_path}/{body_name}"] = FakePrim(
            f"{root_path}/{body_name}",
            children=[collision],
        )
    stage = SimpleNamespace(GetPrimAtPath=lambda path: body_prims[path])
    spawn_calls = []

    pxr_module = ModuleType("pxr")
    pxr_module.Usd = SimpleNamespace(PrimRange=lambda prim: prim.children)
    pxr_module.UsdPhysics = SimpleNamespace(CollisionAPI=FakeCollisionAPI)
    from_files_module = ModuleType("isaaclab.sim.spawners.from_files")

    def fake_spawn(*args, **kwargs):
        spawn_calls.append((args, kwargs))
        return "spawned"

    from_files_module.spawn_from_usd = fake_spawn
    utils_module = ModuleType("isaaclab.sim.utils")
    utils_module.find_matching_prim_paths = lambda _path: [root_path]
    utils_module.get_current_stage = lambda: stage
    modules = {
        "pxr": pxr_module,
        "isaaclab": ModuleType("isaaclab"),
        "isaaclab.sim": ModuleType("isaaclab.sim"),
        "isaaclab.sim.spawners": ModuleType("isaaclab.sim.spawners"),
        "isaaclab.sim.spawners.from_files": from_files_module,
        "isaaclab.sim.utils": utils_module,
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    result = layout._spawn_psm_without_jaw_collisions(
        root_path,
        SimpleNamespace(),
        translation=(1.0, 2.0, 3.0),
    )

    assert result == "spawned"
    assert len(spawn_calls) == 1
    assert all(prim.collision_enabled.value is False for prim in collision_prims.values())


def test_psm_only_reset_writes_both_articulations_without_a_needle(monkeypatch) -> None:
    class FakeTensor:
        def __init__(self, values):
            self.values = values

        def __getitem__(self, indices):
            return FakeTensor([self.values[index] for index in indices.values])

        def clone(self):
            return FakeTensor([value[:] if isinstance(value, list) else value for value in self.values])

        def to(self, **_kwargs):
            return self

        def tolist(self):
            return self.values

    fake_torch = SimpleNamespace(
        long=object(),
        zeros_like=lambda tensor: FakeTensor(
            [[0.0 for _ in row] if isinstance(row, list) else 0.0 for row in tensor.values]
        ),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    class FakePsm:
        def __init__(self, default_joint_pos):
            self.data = SimpleNamespace(default_joint_pos=default_joint_pos)
            self.calls = []

        def write_joint_state_to_sim(self, joint_pos, joint_vel, *, env_ids):
            self.calls.append(("state", joint_pos.clone(), joint_vel.clone(), env_ids.clone()))

        def set_joint_position_target(self, joint_pos, *, env_ids):
            self.calls.append(("position", joint_pos.clone(), env_ids.clone()))

        def set_joint_velocity_target(self, joint_vel, *, env_ids):
            self.calls.append(("velocity", joint_vel.clone(), env_ids.clone()))

    left = FakePsm(FakeTensor([[1.0, 2.0], [3.0, 4.0]]))
    right = FakePsm(FakeTensor([[5.0, 6.0], [7.0, 8.0]]))
    env = SimpleNamespace(
        num_envs=2,
        device="cpu",
        scene={"left_psm": left, "right_psm": right},
    )

    layout._reset_psms_to_default(env, FakeTensor([1]))

    for psm, expected in ((left, [3.0, 4.0]), (right, [7.0, 8.0])):
        assert [call[0] for call in psm.calls] == ["state", "position", "velocity"]
        assert psm.calls[0][1].tolist() == [expected]
        assert psm.calls[0][2].tolist() == [[0.0, 0.0]]
        assert psm.calls[1][1].tolist() == [expected]
        assert psm.calls[2][1].tolist() == [[0.0, 0.0]]


def test_needle_dependent_layer_can_be_restored_with_one_project_flag(monkeypatch) -> None:
    env_cfg = _environment_config()
    original_sensor = env_cfg.scene.left_jaw_1_needle_contact
    original_left_spawn_func = env_cfg.scene.left_psm.spawn.func
    original_right_spawn_func = env_cfg.scene.right_psm.spawn.func
    monkeypatch.setattr(layout, "PURE_TELEOP_NEEDLE_TASK_ENABLED", True)

    apply_pure_teleop_layout(env_cfg)

    assert env_cfg.scene.needle.init_state.pos == NEEDLE_RESET_POS
    assert env_cfg.scene.needle.init_state.rot == NEEDLE_RESET_ROT_WXYZ
    assert env_cfg.scene.left_jaw_1_needle_contact is original_sensor
    assert env_cfg.observations.policy.needle_pose_w is not None
    assert env_cfg.observations.subtask_terms is not None
    assert env_cfg.events.reset_all is not None
    assert env_cfg.rewards.phase_progress is not None
    assert env_cfg.scene.left_psm.spawn.activate_contact_sensors is True
    assert env_cfg.scene.right_psm.spawn.activate_contact_sensors is True
    assert env_cfg.scene.left_psm.spawn.func is original_left_spawn_func
    assert env_cfg.scene.right_psm.spawn.func is original_right_spawn_func
    assert env_cfg.scene.left_psm.spawn.rigid_props.disable_gravity is False
    assert env_cfg.scene.right_psm.spawn.rigid_props.disable_gravity is False


def test_pure_teleop_layout_reduces_physics_and_preserves_xr_refresh_cadence() -> None:
    env_cfg = _environment_config()
    original_left = env_cfg.scene.left_psm.actuators["jaws"]
    original_right = env_cfg.scene.right_psm.actuators["jaws"]
    original_left_arm = env_cfg.scene.left_psm.actuators["arms"]
    original_right_arm = env_cfg.scene.right_psm.actuators["arms"]
    physics_dt = env_cfg.sim.dt

    apply_pure_teleop_layout(env_cfg)

    assert physics_dt == PINNED_NEEDLE_TASK_PHYSICS_DT_S
    assert env_cfg.sim.dt == PURE_TELEOP_PHYSICS_DT_S == pytest.approx(1.0 / 120.0)
    assert env_cfg.decimation == PURE_TELEOP_DECIMATION
    assert env_cfg.sim.render_interval == PURE_TELEOP_RENDER_INTERVAL
    assert env_cfg.sim.render_interval == 2 * env_cfg.decimation
    assert env_cfg.sim.dt * env_cfg.sim.render_interval == pytest.approx(1.0 / 60.0)

    for psm, original, arm in (
        (env_cfg.scene.left_psm, original_left, original_left_arm),
        (env_cfg.scene.right_psm, original_right, original_right_arm),
    ):
        jaw = psm.actuators["jaws"]
        assert jaw is not original
        assert original.velocity_limit_sim == 2.1
        assert jaw.velocity_limit_sim == PURE_TELEOP_JAW_VELOCITY_LIMIT_RAD_S
        assert math.pi / 6.0 / jaw.velocity_limit_sim == pytest.approx(PURE_TELEOP_JAW_CLOSE_TIME_S)
        assert pytest.approx(0.10) == PURE_TELEOP_JAW_CLOSE_TIME_S
        assert 2.0 * jaw.velocity_limit_sim * env_cfg.sim.dt == pytest.approx(math.radians(5.0))
        assert jaw.stiffness == original.stiffness
        assert jaw.damping == original.damping
        assert jaw.effort_limit_sim == original.effort_limit_sim
        assert psm.actuators["arms"] is arm


def test_pure_teleop_layout_rejects_changed_contact_timestep() -> None:
    env_cfg = _environment_config()
    env_cfg.sim.dt = 1.0 / 120.0

    with pytest.raises(ValueError, match="contact-qualified"):
        apply_pure_teleop_layout(env_cfg)


def test_shaft_intersection_is_three_millimetres_above_pad() -> None:
    pad_top_z = SUTURE_PAD_ROOT_POS[2] + SUTURE_PAD_TOP_LOCAL_Z_M

    assert pytest.approx(0.003) == SHAFT_INTERSECTION_CLEARANCE_M
    assert SHAFT_INTERSECTION_Z_M - pad_top_z == pytest.approx(SHAFT_INTERSECTION_CLEARANCE_M)


def test_bilateral_psm_geometry_moves_down_as_one_rigid_layout() -> None:
    assert pytest.approx(-0.1113) == PSM_LAYOUT_VERTICAL_SHIFT_M
    assert LEFT_PSM_ROOT_POS[2] == pytest.approx(0.1614 + PSM_LAYOUT_VERTICAL_SHIFT_M)
    assert RIGHT_PSM_ROOT_POS[2] == pytest.approx(0.1614 + PSM_LAYOUT_VERTICAL_SHIFT_M)
    assert LEFT_TOOL_HOME_POS_W[2] == pytest.approx(0.060 + PSM_LAYOUT_VERTICAL_SHIFT_M)
    assert RIGHT_TOOL_HOME_POS_W[2] == pytest.approx(0.060 + PSM_LAYOUT_VERTICAL_SHIFT_M)
    assert NEEDLE_RESET_POS[2] == pytest.approx(0.058368816972 + PSM_LAYOUT_VERTICAL_SHIFT_M)


def test_bilateral_psm_layout_locks_authored_shaft_geometry() -> None:
    left_direction = tuple(tip - root for tip, root in zip(LEFT_TOOL_HOME_POS_W, LEFT_PSM_ROOT_POS, strict=True))
    right_direction = tuple(tip - root for tip, root in zip(RIGHT_TOOL_HOME_POS_W, RIGHT_PSM_ROOT_POS, strict=True))

    def norm(vector):
        return math.sqrt(sum(value * value for value in vector))

    def angle_degrees(first, second):
        cosine = sum(a * b for a, b in zip(first, second, strict=True)) / (norm(first) * norm(second))
        return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))

    left_elevation = math.degrees(math.atan2(abs(left_direction[2]), norm(left_direction[:2])))
    right_elevation = math.degrees(math.atan2(abs(right_direction[2]), norm(right_direction[:2])))
    tip_gap = norm(tuple(left - right for left, right in zip(LEFT_TOOL_HOME_POS_W, RIGHT_TOOL_HOME_POS_W, strict=True)))
    denominator = left_direction[0] * right_direction[1] - left_direction[1] * right_direction[0]
    root_delta = tuple(right - left for left, right in zip(LEFT_PSM_ROOT_POS, RIGHT_PSM_ROOT_POS, strict=True))
    left_parameter = (root_delta[0] * right_direction[1] - root_delta[1] * right_direction[0]) / denominator
    intersection = tuple(
        root + left_parameter * direction for root, direction in zip(LEFT_PSM_ROOT_POS, left_direction, strict=True)
    )

    assert left_elevation == pytest.approx(30.0, abs=0.001)
    assert right_elevation == pytest.approx(30.0, abs=0.001)
    assert tip_gap == pytest.approx(0.016, abs=1.0e-9)
    assert angle_degrees(left_direction, right_direction) == pytest.approx(97.1807, abs=0.001)
    assert angle_degrees(left_direction[:2], right_direction[:2]) == pytest.approx(120.0, abs=0.001)
    assert intersection == pytest.approx((0.0, SUTURE_PAD_ROOT_POS[1], SHAFT_INTERSECTION_Z_M), abs=1.0e-8)


def test_pure_teleop_layout_requires_motion_controller_device() -> None:
    env_cfg = _environment_config()
    env_cfg.teleop_devices.devices = {}

    with pytest.raises(ValueError, match="motion_controllers"):
        apply_pure_teleop_layout(env_cfg)
