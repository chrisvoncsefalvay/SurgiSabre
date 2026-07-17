import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import surgisabre.runtime as instrumentation_module  # noqa: E402
from surgisabre.course import (  # noqa: E402
    BrickPassSpec,
    BrickState,
    BrickStateEvent,
)
from surgisabre.runtime import (  # noqa: E402
    IsaacLabEvidenceInstrumentation,
    _apply_xr_anchor_position,
    _ControllerPairActivityGate,
    _disable_automatic_terminations,
    _inspect_brick_display_colours,
    _make_isaac_sabre_brick_config,
    _validate_pure_teleop_runtime,
)
from surgisabre.score import SabreScoreCounter  # noqa: E402


def test_live_brick_display_colour_reader_uses_authored_mesh_values() -> None:
    class Attribute:
        def __init__(self, value):
            self.value = value

        def Get(self):
            return self.value

    class Prim:
        def __init__(self, colour):
            self.colour = colour

        def __bool__(self):
            return True

        def GetAttribute(self, name):
            assert name == "primvars:displayColor"
            return Attribute([self.colour])

    prims = {
        (
            "/World/envs/env_0/"
            f"{instrumentation_module.PURE_TELEOP_BRICK_PRIM_NAMES[brick_id]}"
            "/geometry/mesh"
        ): Prim(instrumentation_module.PURE_TELEOP_BRICK_COLOURS[brick_id])
        for brick_id in instrumentation_module.PURE_TELEOP_BRICK_IDS
    }
    stage = SimpleNamespace(GetPrimAtPath=lambda path: prims.get(path))

    assert _inspect_brick_display_colours(stage) == {
        brick_id: list(instrumentation_module.PURE_TELEOP_BRICK_COLOURS[brick_id])
        for brick_id in instrumentation_module.PURE_TELEOP_BRICK_IDS
    }


def test_live_brick_display_colour_reader_rejects_a_missing_mesh() -> None:
    stage = SimpleNamespace(GetPrimAtPath=lambda _path: None)

    with pytest.raises(RuntimeError, match="display mesh is missing"):
        _inspect_brick_display_colours(stage)


def test_xr_anchor_position_updates_environment_and_device_configs() -> None:
    environment_xr = SimpleNamespace(anchor_pos=(0.0, 0.0, 0.0), near_plane=0.15)
    device_xr = SimpleNamespace(anchor_pos=(0.0, 0.0, 0.0), near_plane=0.15)
    env_cfg = SimpleNamespace(
        xr=environment_xr,
        teleop_devices=SimpleNamespace(
            devices={"motion_controllers": SimpleNamespace(xr_cfg=device_xr)},
        ),
    )

    result = _apply_xr_anchor_position(env_cfg, (0.0, -0.45, -0.90), 0.05)

    assert result is env_cfg
    assert environment_xr.anchor_pos == (0.0, -0.45, -0.90)
    assert device_xr.anchor_pos == (0.0, -0.45, -0.90)
    assert environment_xr.near_plane == 0.05
    assert device_xr.near_plane == 0.05


def test_xr_anchor_position_requires_environment_xr_config() -> None:
    with pytest.raises(ValueError, match="environment XR configuration"):
        _apply_xr_anchor_position(SimpleNamespace(), (0.0, -0.45, -0.90))


def test_pure_teleop_disables_every_automatic_termination() -> None:
    terminations = SimpleNamespace(
        time_out=object(),
        success=object(),
        needle_dropped_or_out_of_bounds=object(),
    )
    env_cfg = SimpleNamespace(terminations=terminations)

    result = _disable_automatic_terminations(env_cfg)

    assert result is env_cfg
    assert vars(terminations) == {
        "time_out": None,
        "success": None,
        "needle_dropped_or_out_of_bounds": None,
    }


def test_pure_teleop_requires_configurable_terminations() -> None:
    with pytest.raises(ValueError, match="termination configuration"):
        _disable_automatic_terminations(SimpleNamespace())

    with pytest.raises(ValueError, match="no configurable termination terms"):
        _disable_automatic_terminations(SimpleNamespace(terminations=SimpleNamespace()))


def test_isaac_sabre_brick_config_matches_the_authored_six_target_contract() -> None:
    config = _make_isaac_sabre_brick_config()

    assert [spec.brick_id for spec in config.specs] == list(
        instrumentation_module.PURE_TELEOP_BRICK_IDS
    )
    assert [spec.spawn_position_m for spec in config.specs] == [
        instrumentation_module.PURE_TELEOP_BRICK_START_POSITIONS_W[brick_id]
        for brick_id in instrumentation_module.PURE_TELEOP_BRICK_IDS
    ]
    assert [spec.approach_velocity_m_s for spec in config.specs] == [
        (
            0.0,
            -instrumentation_module.PURE_TELEOP_BRICK_APPROACH_SPEEDS_M_S[side],
            0.0,
        )
        for side in instrumentation_module.PURE_TELEOP_BRICK_IDS
    ]
    assert [spec.size_m for spec in config.specs] == [
        instrumentation_module.PURE_TELEOP_BRICK_SIZES_M[side]
        for side in instrumentation_module.PURE_TELEOP_BRICK_IDS
    ]
    assert config.game_config.fall_z_threshold_m == (
        instrumentation_module.PURE_TELEOP_BRICK_FALL_Z_M
    )
    assert config.game_config.haptic_amplitude == (
        instrumentation_module.PURE_TELEOP_BRICK_HAPTIC_INTENSITY
    )
    assert config.fall_through_prim_paths == ()
    assert [item.hand for item in config.instrument_actor_filters] == [
        *(["left"] * 5),
        *(["right"] * 5),
    ]


def test_pure_teleop_runtime_validation_requires_needle_free_18d_scene() -> None:
    retargeter = SimpleNamespace(
        left=SimpleNamespace(
            translation_scale=instrumentation_module.PURE_TELEOP_TRANSLATION_SCALE,
            workspace_lower=instrumentation_module.PURE_TELEOP_WORKSPACE_LOWER_W,
            workspace_upper=instrumentation_module.PURE_TELEOP_WORKSPACE_UPPER_W,
            jaw_open=(-0.5, 0.5),
            jaw_closed=(0.0, 0.0),
            initial_closedness=0.0,
        ),
        right=SimpleNamespace(
            translation_scale=instrumentation_module.PURE_TELEOP_TRANSLATION_SCALE,
            workspace_lower=instrumentation_module.PURE_TELEOP_WORKSPACE_LOWER_W,
            workspace_upper=instrumentation_module.PURE_TELEOP_WORKSPACE_UPPER_W,
            jaw_open=(-0.5, 0.5),
            jaw_closed=(0.0, 0.0),
            initial_closedness=0.0,
        ),
    )
    jaw_joint_names = list(instrumentation_module._DVRK_JAW_JOINT_NAMES)
    jaw_action = SimpleNamespace(joint_names=jaw_joint_names)
    jaw_actuator = SimpleNamespace(
        velocity_limit_sim=instrumentation_module.PURE_TELEOP_JAW_VELOCITY_LIMIT_RAD_S
    )
    brick_filters = [
        path.replace("{ENV_REGEX_NS}", "/World/envs/env_.*")
        for side in ("left", "right")
        for path in instrumentation_module.PURE_TELEOP_BRICK_PSM_CONTACT_FILTERS[side]
    ]

    def brick_config(brick_id: str):
        prim_path = (
            "/World/envs/env_.*/"
            f"{instrumentation_module.PURE_TELEOP_BRICK_PRIM_NAMES[brick_id]}"
        )
        return (
            SimpleNamespace(
                prim_path=prim_path,
                spawn=SimpleNamespace(
                    size=instrumentation_module.PURE_TELEOP_BRICK_SIZES_M[brick_id],
                    rigid_props=SimpleNamespace(
                        disable_gravity=True,
                        kinematic_enabled=False,
                    ),
                    mass_props=SimpleNamespace(
                        mass=instrumentation_module.PURE_TELEOP_BRICK_MASS_KG
                    ),
                    activate_contact_sensors=True,
                ),
                init_state=SimpleNamespace(
                    pos=instrumentation_module.PURE_TELEOP_BRICK_START_POSITIONS_W[
                        brick_id
                    ],
                    lin_vel=(
                        0.0,
                        -instrumentation_module.PURE_TELEOP_BRICK_APPROACH_SPEEDS_M_S[
                            brick_id
                        ],
                        0.0,
                    ),
                ),
            ),
            SimpleNamespace(
                prim_path=prim_path,
                filter_prim_paths_expr=brick_filters,
                force_threshold=(
                    instrumentation_module.PURE_TELEOP_BRICK_CONTACT_FORCE_THRESHOLD_N
                ),
            ),
        )

    brick_configs = {
        brick_id: brick_config(brick_id)
        for brick_id in instrumentation_module.PURE_TELEOP_BRICK_IDS
    }
    brick_scene_configs = {
        field_name: value
        for brick_id, (brick, sensor) in brick_configs.items()
        for field_name, value in (
            (f"sabre_brick_{brick_id}", brick),
            (f"sabre_brick_{brick_id}_contact", sensor),
        )
    }
    env = SimpleNamespace(
        num_envs=1,
        scene=SimpleNamespace(
            rigid_objects={
                f"sabre_brick_{brick_id}": object()
                for brick_id in instrumentation_module.PURE_TELEOP_BRICK_IDS
            },
            sensors={
                f"sabre_brick_{brick_id}_contact": object()
                for brick_id in instrumentation_module.PURE_TELEOP_BRICK_IDS
            },
            left_psm=SimpleNamespace(is_fixed_base=True),
            right_psm=SimpleNamespace(is_fixed_base=True),
        ),
        action_manager=SimpleNamespace(
            active_terms=[
                "left_arm_action",
                "left_jaw_action",
                "right_arm_action",
                "right_jaw_action",
            ],
            total_action_dim=18,
        ),
        cfg=SimpleNamespace(
            decimation=instrumentation_module.PURE_TELEOP_DECIMATION,
            sim=SimpleNamespace(
                dt=instrumentation_module.PURE_TELEOP_PHYSICS_DT_S,
                render_interval=instrumentation_module.PURE_TELEOP_RENDER_INTERVAL,
            ),
            actions=SimpleNamespace(
                left_jaw_action=jaw_action,
                right_jaw_action=SimpleNamespace(joint_names=jaw_joint_names),
            ),
            teleop_devices=SimpleNamespace(
                devices={
                    "motion_controllers": SimpleNamespace(
                        retargeters=[retargeter]
                    )
                }
            ),
            scene=SimpleNamespace(
                left_psm=SimpleNamespace(
                    spawn=SimpleNamespace(
                        activate_contact_sensors=False,
                        articulation_props=SimpleNamespace(fix_root_link=True),
                        rigid_props=SimpleNamespace(disable_gravity=True),
                    ),
                    actuators={"jaws": jaw_actuator},
                ),
                right_psm=SimpleNamespace(
                    spawn=SimpleNamespace(
                        activate_contact_sensors=False,
                        articulation_props=SimpleNamespace(fix_root_link=True),
                        rigid_props=SimpleNamespace(disable_gravity=True),
                    ),
                    actuators={"jaws": jaw_actuator},
                ),
                suture_pad=None,
                **brick_scene_configs,
            ),
        ),
    )
    stage = SimpleNamespace(GetPrimAtPath=lambda _path: False)

    report = _validate_pure_teleop_runtime(
        env,
        stage,
        jaw_collision_report={
            "jaw_collision_shape_count": {"left": 2, "right": 2},
            "enabled_jaw_collision_paths": [],
            "missing_jaw_body_paths": [],
        },
        psm_stability_report={
            "psm_fixed_root_joint_paths": {
                "left": "/World/envs/env_0/LeftPSM/root_joint",
                "right": "/World/envs/env_0/RightPSM/root_joint",
            },
            "psm_rigid_body_count": {"left": 13, "right": 13},
            "gravity_enabled_psm_body_paths": [],
            "missing_psm_root_paths": [],
        },
        brick_display_colours={
            brick_id: list(
                instrumentation_module.PURE_TELEOP_BRICK_COLOURS[brick_id]
            )
            for brick_id in instrumentation_module.PURE_TELEOP_BRICK_IDS
        },
    )

    assert report["needle_prim_present"] is False
    assert report["suture_pad_prim_present"] is False
    assert report["suture_pad_configured"] is False
    assert report["environment_count"] == 1
    assert report["action_dim"] == 18
    assert report["controller_translation_scale"] == {"left": 1.0, "right": 1.0}
    assert report["controller_workspace"] == {
        "left": {
            "lower": list(instrumentation_module.PURE_TELEOP_WORKSPACE_LOWER_W),
            "upper": list(instrumentation_module.PURE_TELEOP_WORKSPACE_UPPER_W),
        },
        "right": {
            "lower": list(instrumentation_module.PURE_TELEOP_WORKSPACE_LOWER_W),
            "upper": list(instrumentation_module.PURE_TELEOP_WORKSPACE_UPPER_W),
        },
    }
    assert report["psm_contact_reporting_enabled"] == {
        "left": False,
        "right": False,
    }
    assert report["psm_fix_root_link_configured"] == {
        "left": True,
        "right": True,
    }
    assert report["psm_disable_gravity_configured"] == {
        "left": True,
        "right": True,
    }
    assert report["psm_is_fixed_base"] == {"left": True, "right": True}
    assert report["psm_fixed_root_joint_paths"] == {
        "left": "/World/envs/env_0/LeftPSM/root_joint",
        "right": "/World/envs/env_0/RightPSM/root_joint",
    }
    assert report["gravity_enabled_psm_body_paths"] == []
    assert report["jaw_collision_shape_count"] == {"left": 2, "right": 2}
    assert report["enabled_jaw_collision_paths"] == []
    assert report["physics_dt_s"] == pytest.approx(1.0 / 120.0)
    assert report["decimation"] == 1
    assert report["render_interval"] == 2
    assert report["jaw_action_joint_names"] == {
        "left": jaw_joint_names,
        "right": jaw_joint_names,
    }
    assert report["jaw_retargeter"]["left"]["initial_closedness"] == 0.0
    assert report["trigger_jaw_control_enabled"] is True
    assert report["rigid_objects"] == sorted(
        f"sabre_brick_{brick_id}"
        for brick_id in instrumentation_module.PURE_TELEOP_BRICK_IDS
    )
    assert report["sensors"] == sorted(
        f"sabre_brick_{brick_id}_contact"
        for brick_id in instrumentation_module.PURE_TELEOP_BRICK_IDS
    )
    assert all(
        config["gravity_disabled"] and not config["kinematic_enabled"]
        for config in report["brick_configuration"].values()
    )
    expected_brick_filters = [
        path
        for side in ("left", "right")
        for path in instrumentation_module.PURE_TELEOP_BRICK_PSM_CONTACT_FILTERS[side]
    ]
    for brick_id, config in report["brick_configuration"].items():
        expected_prim_path = (
            "{ENV_REGEX_NS}/"
            f"{instrumentation_module.PURE_TELEOP_BRICK_PRIM_NAMES[brick_id]}"
        )
        assert config["prim_path"] == expected_prim_path
        assert config["sensor_prim_path"] == expected_prim_path
        assert config["lane"] == instrumentation_module.PURE_TELEOP_BRICK_LANES[brick_id]
        assert config["sensor_filters"] == expected_brick_filters
        assert config["size_m"] == list(
            instrumentation_module.PURE_TELEOP_BRICK_SIZES_M[brick_id]
        )
        assert config["spawn_position_w"] == list(
            instrumentation_module.PURE_TELEOP_BRICK_START_POSITIONS_W[brick_id]
        )
        assert config["approach_velocity_m_s"] == [
            0.0,
            -instrumentation_module.PURE_TELEOP_BRICK_APPROACH_SPEEDS_M_S[brick_id],
            0.0,
        ]
        assert config["display_colour_rgb"] == list(
            instrumentation_module.PURE_TELEOP_BRICK_COLOURS[brick_id]
        )


def test_pure_teleop_applies_layout_before_disabling_terminations(monkeypatch) -> None:
    calls = []
    env_cfg = SimpleNamespace()

    def record_layout(config):
        calls.append("layout")
        return config

    def record_termination_disable(config):
        calls.append("terminations")
        return config

    monkeypatch.setattr(
        instrumentation_module,
        "apply_pure_teleop_layout",
        record_layout,
    )
    monkeypatch.setattr(
        instrumentation_module,
        "_disable_automatic_terminations",
        record_termination_disable,
    )
    runner_module = SimpleNamespace(
        parse_env_cfg=lambda: env_cfg,
        gym=SimpleNamespace(make=lambda: None),
        create_teleop_device=lambda *_args, **_kwargs: None,
        logger=SimpleNamespace(error=lambda *_args, **_kwargs: None),
    )
    instrumentation = IsaacLabEvidenceInstrumentation(
        SimpleNamespace(),
        xr_enabled=True,
        pure_teleop=True,
    )

    instrumentation.install(runner_module)
    result = runner_module.parse_env_cfg()

    assert result is env_cfg
    assert calls == ["layout", "terminations"]


def test_pure_teleop_records_runtime_validation_after_hinged_kernel_install(
    monkeypatch,
) -> None:
    env = SimpleNamespace()
    made = SimpleNamespace(unwrapped=env)
    report = {
        "needle_prim_present": False,
        "trigger_jaw_control_enabled": True,
    }
    recorded = []
    recorder = SimpleNamespace(
        session_id="test-session",
        record_runtime_validation=lambda **fields: recorded.append(fields)
    )
    left_jaw_kernel = SimpleNamespace(
        _jaw_open=(-0.5, 0.5),
        _jaw_closed=(0.0, 0.0),
    )
    right_jaw_kernel = SimpleNamespace(
        _jaw_open=(-0.5, 0.5),
        _jaw_closed=(0.0, 0.0),
    )

    class Retargeter:
        def __init__(self) -> None:
            self._left = SimpleNamespace(pose=object(), jaw=left_jaw_kernel)
            self._right = SimpleNamespace(pose=object(), jaw=right_jaw_kernel)
            self._left_pose = None
            self._right_pose = None

        def reset(self) -> None:
            self._left_pose = self._left.pose.reset()
            self._right_pose = self._right.pose.reset()

    device = SimpleNamespace(_dvrk_retargeter=Retargeter())
    runner_module = SimpleNamespace(
        parse_env_cfg=lambda: SimpleNamespace(),
        gym=SimpleNamespace(make=lambda: made),
        create_teleop_device=lambda *_args, **_kwargs: device,
        logger=SimpleNamespace(error=lambda *_args, **_kwargs: None),
    )
    instrumentation = IsaacLabEvidenceInstrumentation(
        recorder,
        xr_enabled=True,
        pure_teleop=True,
    )
    instrumentation._instrument_environment = lambda observed: None
    instrumentation._instrument_device = lambda *_args, **_kwargs: None
    class FakeBrickAdapter:
        def __init__(self, *_args, **_kwargs):
            pass

        def runtime_report(self):
            return {"contact_reporting_scope": "brick_assets_only"}

    class FakeScoreIndicator:
        def __init__(self):
            self.successful = 0
            self.failed = 0

        def update(self, successful, failed):
            self.successful = successful
            self.failed = failed

        def reset(self):
            self.update(0, 0)

        def report(self):
            return {
                "root_path": "/World/SurgSabreScore",
                "successful": self.successful,
                "failed": self.failed,
            }

    monkeypatch.setattr(
        instrumentation_module,
        "IsaacSabreBrickAdapter",
        FakeBrickAdapter,
    )
    monkeypatch.setattr(
        instrumentation_module,
        "IsaacSabreScoreIndicator",
        FakeScoreIndicator,
    )
    monkeypatch.setattr(
        instrumentation_module,
        "_validate_pure_teleop_runtime",
        lambda observed: report,
    )

    instrumentation.install(runner_module)

    assert runner_module.gym.make() is made
    assert instrumentation.pure_teleop_runtime_report == {
        **report,
        "brick_runtime": {"contact_reporting_scope": "brick_assets_only"},
        "score_indicator": {
            "root_path": "/World/SurgSabreScore",
            "successful": 0,
            "failed": 0,
        },
        "score_semantics": {
            "successful": "approaching_to_falling_instrument_hit",
            "failed": "approaching_to_recycle_ready_missed",
            "scope": "aggregate_session_instances",
        },
    }
    assert recorded == []

    assert runner_module.create_teleop_device("motion_controllers", {}, {}) is device
    installed_report = instrumentation.pure_teleop_runtime_report
    assert installed_report is not report
    assert installed_report["retargeting_mode"] == (
        "clutched_absolute_hinged_sabre_with_axial_insertion"
    )
    assert installed_report["controller_orientation_mode"] == (
        "session_registered_absolute_openxr_grip"
    )
    assert installed_report["controller_translation_input_used"] is True
    assert installed_report["squeeze_controls_arm_pose"] is True
    assert installed_report["arm_clutch_threshold"] == 0.5
    assert installed_report["axial_translation_scale"] == 1.0
    assert installed_report["controller_registration_mode"] == (
        "first_engaged_sample_to_held_tool_pose"
    )
    assert installed_report["controller_reengagement_is_jump_free"] is True
    assert installed_report["psm_shaft_length_bounds_m"] == {
        "minimum": pytest.approx(0.0593),
        "maximum": pytest.approx(0.2428),
    }
    assert installed_report["trigger_jaw_mode"] == "absolute_analog"
    assert installed_report["squeeze_controls_jaw_pose"] is False
    assert installed_report["pose_kernel_types"] == {
        "left": "AbsoluteHingedPoseStateMachine",
        "right": "AbsoluteHingedPoseStateMachine",
    }
    assert installed_report["jaw_kernel_types"] == {
        "left": "DirectTriggerJawStateMachine",
        "right": "DirectTriggerJawStateMachine",
    }
    assert installed_report["replaced_jaw_kernel_types"] == {
        "left": "SimpleNamespace",
        "right": "SimpleNamespace",
    }
    assert installed_report["brick_runtime"] == {
        "contact_reporting_scope": "brick_assets_only"
    }
    assert installed_report["score_indicator"] == {
        "root_path": "/World/SurgSabreScore",
        "successful": 0,
        "failed": 0,
    }
    assert installed_report["xr_haptics"]["backend"] == "omni.kit.xr.core"
    assert device._dvrk_retargeter._left.jaw is not left_jaw_kernel
    assert device._dvrk_retargeter._right.jaw is not right_jaw_kernel
    assert recorded == [{"source": "isaac", "validation": installed_report}]


def test_controller_pair_auto_starts_once_when_both_poses_are_valid() -> None:
    gate = _ControllerPairActivityGate()

    assert gate.observe("left", True) is None
    assert gate.observe("right", False) is None
    assert gate.observe("right", True) == "START"
    assert gate.observe("left", True) is None
    assert gate.observe("right", True) is None


def test_controller_pair_requires_simultaneously_valid_tracking() -> None:
    gate = _ControllerPairActivityGate()

    assert gate.observe("left", True) is None
    assert gate.observe("left", False) is None
    assert gate.observe("right", True) is None
    assert gate.observe("left", True) == "START"


def test_controller_pair_pauses_on_loss_and_restarts_after_recovery() -> None:
    gate = _ControllerPairActivityGate()

    assert gate.observe("left", True) is None
    assert gate.observe("right", True) == "START"
    assert gate.observe("left", False) == "STOP"
    assert gate.observe("right", False) is None
    assert gate.observe("right", True) is None
    assert gate.observe("left", True) == "START"


def test_controller_pair_uses_only_bilateral_samples_from_the_same_frame() -> None:
    gate = _ControllerPairActivityGate()

    assert gate.observe("left", True, frame_token=1) is None
    assert gate.observe("right", False, frame_token=1) is None
    assert gate.observe("left", True, frame_token=2) is None
    assert gate.observe("right", True, frame_token=2) == "START"
    assert gate.observe("left", True, frame_token=3) is None
    assert gate.observe("right", False, frame_token=3) == "STOP"


def test_device_tracking_gate_stops_retargeter_before_application_and_restarts_cleanly() -> None:
    events = []
    samples = {}

    class Retargeter:
        _left_pose = [0.0] * 7
        _left_jaws = [0.0] * 2
        _right_pose = [0.0] * 7
        _right_jaws = [0.0] * 2

        def start(self) -> None:
            events.append("retargeter_start")

        def stop(self) -> None:
            events.append("retargeter_stop")

    class Device:
        def __init__(self) -> None:
            self._dvrk_retargeter = Retargeter()
            self.controller_faults = {}

        def _get_controller_sample(self, _path, target):
            return samples[target]

        def advance(self):
            self._get_controller_sample("/user/hand/left", "left")
            self._get_controller_sample("/user/hand/right", "right")
            return [0.0] * 18

    device = Device()
    recorder = SimpleNamespace(
        record_controller_sample=lambda **_kwargs: None,
        record_controller_fault=lambda **_kwargs: None,
        record_control_action=lambda *_args, **_kwargs: None,
    )
    instrumentation = IsaacLabEvidenceInstrumentation(
        recorder,
        xr_enabled=True,
        pure_teleop=True,
    )
    instrumentation._instrument_device(
        device,
        auto_start=lambda: events.append("application_start"),
        auto_stop=lambda: events.append("application_stop"),
    )
    valid_pose = ([0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0], [0.0] * 6 + [1.0])
    invalid_pose = ([0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0], [0.0] * 7)

    samples["left"] = valid_pose
    samples["right"] = valid_pose
    device.advance()
    samples["left"] = invalid_pose
    device.advance()
    samples["left"] = valid_pose
    device.advance()

    assert events == [
        "retargeter_start",
        "application_start",
        "retargeter_stop",
        "application_stop",
        "retargeter_start",
        "application_start",
    ]


def test_pure_teleop_initial_reset_skips_outcome_phase_hooks() -> None:
    instrumentation = IsaacLabEvidenceInstrumentation(
        SimpleNamespace(),
        xr_enabled=True,
        pure_teleop=True,
    )
    instrumentation._attach_phase_machine = lambda _env: pytest.fail("phase hook installed")
    instrumentation._cache_jaw_state_sources = lambda _env: None
    env = SimpleNamespace(
        reset=lambda: None,
        step=lambda _action: None,
        common_step_counter=0,
        num_envs=1,
    )

    instrumentation._instrument_environment(env)
    env.reset()


def test_environment_reset_and_step_drive_brick_adapter_after_physics() -> None:
    class BrickAdapter:
        def __init__(self):
            self.reset_count = 0
            self.step_durations = []

        def reset(self):
            self.reset_count += 1

        def after_physics_step(self, dt_s):
            self.step_durations.append(dt_s)

    recorder = SimpleNamespace(record_action_application=lambda **_fields: None)
    instrumentation = IsaacLabEvidenceInstrumentation(
        recorder,
        xr_enabled=True,
        pure_teleop=True,
    )
    instrumentation._cache_jaw_state_sources = lambda _env: None
    instrumentation._measured_jaw_positions = lambda: {
        "left": [0.0, 0.0],
        "right": [0.0, 0.0],
    }
    brick_adapter = BrickAdapter()
    instrumentation._brick_game = brick_adapter
    env = SimpleNamespace(
        reset=lambda: "reset",
        step=lambda _action: "step",
        common_step_counter=0,
        num_envs=1,
        cfg=SimpleNamespace(
            sim=SimpleNamespace(dt=1.0 / 120.0),
            decimation=2,
        ),
    )

    instrumentation._instrument_environment(env)

    assert env.reset() == "reset"
    assert env.step([[0.0] * 18]) == "step"
    assert brick_adapter.reset_count == 1
    assert brick_adapter.step_durations == [pytest.approx(1.0 / 60.0)]


def test_brick_haptic_uses_matching_xr_output_and_records_capability() -> None:
    class Capability:
        def to_dict(self):
            return {"hand": "right", "available": True, "reason": "available"}

    class Haptics:
        def __init__(self):
            self.pulses = []

        def capability(self, hand):
            assert hand == "right"
            return Capability()

        def pulse(self, hand, **parameters):
            self.pulses.append((hand, parameters))
            return True

    recorded = []
    recorder = SimpleNamespace(
        record_haptic_pulse=lambda **fields: recorded.append(fields)
    )
    instrumentation = IsaacLabEvidenceInstrumentation(
        recorder,
        xr_enabled=True,
        pure_teleop=True,
    )
    haptics = Haptics()
    instrumentation._haptics = haptics
    instrumentation._env = SimpleNamespace(common_step_counter=19)
    event = instrumentation_module.HapticHitEvent(
        brick_id="left",
        pass_index=4,
        hand="right",
        amplitude=0.72,
        duration_s=0.055,
        frequency_hz=0.0,
        contact_position_m=(-0.05, 0.02, -0.03),
    )

    assert instrumentation._handle_brick_haptic(event) is True
    assert haptics.pulses == [
        (
            "right",
            {"intensity": 0.72, "duration_s": 0.055, "frequency_hz": 0.0},
        )
    ]
    assert recorded[0]["hand"] == "right"
    assert recorded[0]["brick_id"] == "left"
    assert recorded[0]["kit_accepted"] is True
    assert recorded[0]["capability"]["available"] is True
    assert recorded[0]["environment_step"] == 19


def test_brick_state_updates_visible_aggregate_score_once_per_pass() -> None:
    class Indicator:
        def __init__(self):
            self.updates = []

        def update(self, successful, failed):
            self.updates.append((successful, failed))

        def reset(self):
            self.update(0, 0)

    brick_events = []
    score_events = []
    recorder = SimpleNamespace(
        record_brick_state=lambda **fields: brick_events.append(fields),
        record_sabre_score=lambda **fields: score_events.append(fields),
    )
    instrumentation = IsaacLabEvidenceInstrumentation(
        recorder,
        xr_enabled=True,
        pure_teleop=True,
    )
    instrumentation._env = SimpleNamespace(common_step_counter=37)
    instrumentation._brick_game = object()
    instrumentation._score_counter = SabreScoreCounter()
    indicator = Indicator()
    instrumentation._score_indicator = indicator
    event = BrickStateEvent(
        brick_id="left_1",
        pass_index=2,
        lane="left",
        previous_state=BrickState.APPROACHING,
        state=BrickState.FALLING,
        reason="instrument_hit",
        position_m=(-0.064, 0.01, -0.04),
        hitter="right",
        pass_spec=BrickPassSpec(
            brick_id="left_1",
            pass_index=2,
            lane="left",
            spawn_position_m=(-0.064, 0.240, -0.040),
            approach_velocity_m_s=(0.0, -0.160, 0.0),
            approach_end_y_m=-0.160,
            size_m=(0.048, 0.038, 0.038),
            display_colour_rgb=(0.92, 0.12, 0.56),
            speed_palette_index=0,
            height_palette_index=0,
            colour_palette_index=0,
            randomisation_token="0123456789abcdef",
        ),
    )

    instrumentation._record_brick_state_event(event)
    instrumentation._record_brick_state_event(event)

    assert len(brick_events) == 2
    assert brick_events[0]["pass_spec"]["randomisation_token"] == (
        "0123456789abcdef"
    )
    assert indicator.updates == [(1, 0)]
    assert score_events == [
        {
            "successful_instances": 1,
            "failed_instances": 0,
            "reason": "instrument_hit",
            "brick_id": "left_1",
            "pass_index": 2,
            "environment_step": 37,
        }
    ]

    instrumentation._reset_sabre_score(reason="environment_reset")

    assert indicator.updates[-1] == (0, 0)
    assert score_events[-1]["reason"] == "environment_reset"
    assert score_events[-1]["brick_id"] is None


@pytest.mark.parametrize(
    "pure_teleop",
    [True, False],
    ids=["pure_teleop", "contact_handoff"],
)
def test_environment_step_records_post_physics_jaw_positions_in_both_modes(
    pure_teleop: bool,
) -> None:
    class JointPositions:
        def __init__(self, values):
            self.values = values

        def __getitem__(self, key):
            environment, joint_ids = key
            assert environment == 0
            return [self.values[index] for index in joint_ids]

    class Articulation:
        def __init__(self, values):
            self.data = SimpleNamespace(joint_pos=JointPositions(values))

        def find_joints(self, joint_names, *, preserve_order=False):
            assert preserve_order is True
            assert joint_names == list(instrumentation_module._DVRK_JAW_JOINT_NAMES)
            return [1, 2], list(instrumentation_module._DVRK_JAW_JOINT_NAMES)

    left = Articulation([9.0, -0.40, 0.39])
    right = Articulation([9.0, -0.20, 0.19])
    recorded = []
    recorder = SimpleNamespace(
        record_action_application=lambda **fields: recorded.append(fields),
    )
    instrumentation = IsaacLabEvidenceInstrumentation(
        recorder,
        xr_enabled=True,
        pure_teleop=pure_teleop,
    )
    actions = SimpleNamespace(
        left_jaw_action=SimpleNamespace(
            asset_name="left_psm",
            joint_names=list(instrumentation_module._DVRK_JAW_JOINT_NAMES),
        ),
        right_jaw_action=SimpleNamespace(
            asset_name="right_psm",
            joint_names=list(instrumentation_module._DVRK_JAW_JOINT_NAMES),
        ),
    )
    env = SimpleNamespace(
        cfg=SimpleNamespace(actions=actions),
        scene={"left_psm": left, "right_psm": right},
        reset=lambda: None,
        common_step_counter=0,
        num_envs=1,
        termination_manager=SimpleNamespace(get_term=lambda _name: False),
    )

    def step(_action):
        env.common_step_counter = 1
        left.data.joint_pos.values = [9.0, -0.10, 0.09]
        right.data.joint_pos.values = [9.0, -0.02, 0.01]
        return "post-physics"

    env.step = step
    instrumentation._instrument_environment(env)

    assert env.step([[0.0] * 18]) == "post-physics"
    assert recorded[0]["jaw_position_rad"] == {
        "left": [-0.10, 0.09],
        "right": [-0.02, 0.01],
    }
    assert recorded[0]["environment_step_before"] == 0
    assert recorded[0]["environment_step_after"] == 1
