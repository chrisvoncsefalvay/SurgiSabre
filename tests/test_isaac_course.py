import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from surgisabre.course import (  # noqa: E402
    BrickGameConfig,
    BrickPassRandomisation,
    BrickSpec,
    BrickState,
    RecycleRequest,
    ReleaseToPhysicsRequest,
    ScriptedPoseRequest,
)
from surgisabre.isaac_course import (  # noqa: E402
    InstrumentActorFilter,
    IsaacSabreBrickAdapter,
    IsaacSabreBrickBinding,
    IsaacSabreBrickConfig,
    canonicalise_environment_prim_path,
)


class _FakeRigidObject:
    def __init__(self, position: tuple[float, float, float]) -> None:
        self.device = "fake-device"
        self.data = SimpleNamespace(root_pos_w=[list(position)])
        self.pose_writes: list[list[list[float]]] = []
        self.velocity_writes: list[list[list[float]]] = []

    def write_root_pose_to_sim(self, root_pose: list[list[float]]) -> None:
        values = [list(row) for row in root_pose]
        self.pose_writes.append(values)
        self.data.root_pos_w[0] = values[0][:3]

    def write_root_velocity_to_sim(
        self,
        root_velocity: list[list[float]],
    ) -> None:
        self.velocity_writes.append([list(row) for row in root_velocity])

    def clear_writes(self) -> None:
        self.pose_writes.clear()
        self.velocity_writes.clear()


class _FakeContactSensor:
    def __init__(self, filters: tuple[str, ...]) -> None:
        self.cfg = SimpleNamespace(filter_prim_paths_expr=list(filters))
        self.data = SimpleNamespace(force_matrix_w=None)
        self.set_forces([0.0] * len(filters))

    def set_forces(self, magnitudes: list[float]) -> None:
        self.data.force_matrix_w = [
            [[[magnitude, 0.0, 0.0] for magnitude in magnitudes]]
        ]

    def set_force_vectors(
        self,
        vectors: list[tuple[float, float, float]],
    ) -> None:
        self.data.force_matrix_w = [[[[*vector] for vector in vectors]]]


class _GravityRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[object, str, bool]] = []
        self.filter_calls: list[tuple[object, str, tuple[str, ...]]] = []

    def __call__(self, stage: object, prim_path: str, enabled: bool) -> None:
        self.calls.append((stage, prim_path, enabled))

    def clear(self) -> None:
        self.calls.clear()

    def filter_pairs(
        self,
        stage: object,
        prim_path: str,
        filtered_paths: tuple[str, ...],
    ) -> None:
        self.filter_calls.append((stage, prim_path, filtered_paths))


def _specs(*, left_spawn_y: float = 0.20) -> tuple[BrickSpec, ...]:
    return (
        BrickSpec(
            brick_id="left",
            lane="left",
            spawn_position_m=(-0.05, left_spawn_y, -0.03),
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


def _filters() -> tuple[InstrumentActorFilter, ...]:
    return (
        InstrumentActorFilter(
            "left",
            "{ENV_REGEX_NS}/LeftPSM/psm_tool_wrist_link",
        ),
        InstrumentActorFilter(
            "left",
            "{ENV_REGEX_NS}/LeftPSM/psm_tool_tip_link",
        ),
        InstrumentActorFilter(
            "right",
            "{ENV_REGEX_NS}/RightPSM/psm_tool_wrist_link",
        ),
        InstrumentActorFilter(
            "right",
            "{ENV_REGEX_NS}/RightPSM/psm_tool_tip_link",
        ),
    )


def _bindings() -> tuple[IsaacSabreBrickBinding, ...]:
    return (
        IsaacSabreBrickBinding(
            brick_id="left",
            rigid_object_name="sabre_brick_left",
            contact_sensor_name="sabre_brick_left_contact",
            rigid_body_prim_path="/World/envs/env_0/SabreBrickLeft",
        ),
        IsaacSabreBrickBinding(
            brick_id="right",
            rigid_object_name="sabre_brick_right",
            contact_sensor_name="sabre_brick_right_contact",
            rigid_body_prim_path="/World/envs/env_0/SabreBrickRight",
        ),
    )


def test_canonicalise_environment_prim_path_accepts_isaac_lab_resolution() -> None:
    assert canonicalise_environment_prim_path(
        "/World/envs/env_.*/LeftPSM/psm_tool_tip_link"
    ) == "{ENV_REGEX_NS}/LeftPSM/psm_tool_tip_link"
    assert canonicalise_environment_prim_path(
        "{ENV_REGEX_NS}/LeftPSM/psm_tool_tip_link"
    ) == "{ENV_REGEX_NS}/LeftPSM/psm_tool_tip_link"
    assert canonicalise_environment_prim_path(
        "/World/envs/env_0/LeftPSM/psm_tool_tip_link"
    ) == "/World/envs/env_0/LeftPSM/psm_tool_tip_link"


def test_adapter_accepts_isaac_lab_resolved_sensor_filters() -> None:
    actor_filters = _filters()
    resolved_filter_paths = tuple(
        item.prim_path_expr.replace("{ENV_REGEX_NS}", "/World/envs/env_.*")
        for item in actor_filters
    )
    specs = _specs()
    objects = {
        "sabre_brick_left": _FakeRigidObject(specs[0].spawn_position_m),
        "sabre_brick_right": _FakeRigidObject(specs[1].spawn_position_m),
    }
    sensors = {
        "sabre_brick_left_contact": _FakeContactSensor(resolved_filter_paths),
        "sabre_brick_right_contact": _FakeContactSensor(resolved_filter_paths),
    }
    env = SimpleNamespace(
        num_envs=1,
        scene=SimpleNamespace(rigid_objects=objects, sensors=sensors),
    )
    gravity = _GravityRecorder()

    IsaacSabreBrickAdapter(
        env,
        IsaacSabreBrickConfig(
            specs=specs,
            game_config=BrickGameConfig(),
            bindings=_bindings(),
            instrument_actor_filters=actor_filters,
            contact_force_threshold_n=0.01,
            fall_through_prim_paths=("/World/envs/env_0/SuturePad",),
        ),
        stage="fake-stage",
        tensor_factory=lambda values, _device: values,
        gravity_writer=gravity,
        collision_filter_writer=gravity.filter_pairs,
    )


def test_pad_free_adapter_skips_collision_pair_authoring() -> None:
    actor_filters = _filters()
    specs = _specs()
    filter_paths = tuple(item.prim_path_expr for item in actor_filters)
    objects = {
        "sabre_brick_left": _FakeRigidObject(specs[0].spawn_position_m),
        "sabre_brick_right": _FakeRigidObject(specs[1].spawn_position_m),
    }
    sensors = {
        "sabre_brick_left_contact": _FakeContactSensor(filter_paths),
        "sabre_brick_right_contact": _FakeContactSensor(filter_paths),
    }
    env = SimpleNamespace(
        num_envs=1,
        scene=SimpleNamespace(rigid_objects=objects, sensors=sensors),
    )
    gravity = _GravityRecorder()

    adapter = IsaacSabreBrickAdapter(
        env,
        IsaacSabreBrickConfig(
            specs=specs,
            game_config=BrickGameConfig(),
            bindings=_bindings(),
            instrument_actor_filters=actor_filters,
            contact_force_threshold_n=0.01,
            fall_through_prim_paths=(),
        ),
        stage="fake-stage",
        tensor_factory=lambda values, _device: values,
        gravity_writer=gravity,
        collision_filter_writer=gravity.filter_pairs,
    )

    assert gravity.filter_calls == []
    assert adapter.runtime_report()["fall_through_prim_paths"] == []


def _make_adapter(
    *,
    specs: tuple[BrickSpec, ...] | None = None,
    game_config: BrickGameConfig | None = None,
    haptic_sink=None,
    impact_event_sink=None,
    brick_mass_kg: float = 0.055,
    hit_speed_m_s: float = 0.0,
    pass_randomisation: BrickPassRandomisation | None = None,
    appearance_writer=None,
) -> tuple[
    IsaacSabreBrickAdapter,
    dict[str, _FakeRigidObject],
    dict[str, _FakeContactSensor],
    _GravityRecorder,
]:
    specs = specs or _specs()
    actor_filters = _filters()
    filter_paths = tuple(item.prim_path_expr for item in actor_filters)
    objects = {
        "sabre_brick_left": _FakeRigidObject(specs[0].spawn_position_m),
        "sabre_brick_right": _FakeRigidObject(specs[1].spawn_position_m),
    }
    sensors = {
        "sabre_brick_left_contact": _FakeContactSensor(filter_paths),
        "sabre_brick_right_contact": _FakeContactSensor(filter_paths),
    }
    env = SimpleNamespace(
        num_envs=1,
        scene=SimpleNamespace(rigid_objects=objects, sensors=sensors),
    )
    gravity = _GravityRecorder()
    adapter = IsaacSabreBrickAdapter(
        env,
        IsaacSabreBrickConfig(
            specs=specs,
            game_config=game_config or BrickGameConfig(),
            bindings=_bindings(),
            instrument_actor_filters=actor_filters,
            contact_force_threshold_n=0.01,
            fall_through_prim_paths=("/World/envs/env_0/SuturePad",),
            brick_mass_kg=brick_mass_kg,
            hit_speed_m_s=hit_speed_m_s,
            pass_randomisation=pass_randomisation,
        ),
        stage="fake-stage",
        tensor_factory=lambda values, _device: values,
        gravity_writer=gravity,
        collision_filter_writer=gravity.filter_pairs,
        haptic_sink=haptic_sink,
        impact_event_sink=impact_event_sink,
        appearance_writer=appearance_writer,
    )
    return adapter, objects, sensors, gravity


def _clear_runtime_writes(
    objects: dict[str, _FakeRigidObject],
    gravity: _GravityRecorder,
) -> None:
    for rigid_object in objects.values():
        rigid_object.clear_writes()
    gravity.clear()


def test_reset_restores_spawn_with_gravity_disabled_on_bricks_only() -> None:
    adapter, objects, _sensors, gravity = _make_adapter()

    assert objects["sabre_brick_left"].pose_writes[-1][0] == pytest.approx(
        [-0.05, 0.20, -0.03, 1.0, 0.0, 0.0, 0.0]
    )
    assert objects["sabre_brick_right"].velocity_writes[-1][0] == [0.0] * 6
    assert {(path, enabled) for _stage, path, enabled in gravity.calls} == {
        ("/World/envs/env_0/SabreBrickLeft", False),
        ("/World/envs/env_0/SabreBrickRight", False),
    }
    assert all("PSM" not in path for _stage, path, _enabled in gravity.calls)
    assert gravity.filter_calls == [
        (
            "fake-stage",
            "/World/envs/env_0/SabreBrickLeft",
            ("/World/envs/env_0/SuturePad",),
        ),
        (
            "fake-stage",
            "/World/envs/env_0/SabreBrickRight",
            ("/World/envs/env_0/SuturePad",),
        ),
    ]
    assert all(
        "PSM" not in target
        for _stage, _brick, targets in gravity.filter_calls
        for target in targets
    )
    assert adapter.runtime_report()["contact_reporting_scope"] == "brick_assets_only"


def test_randomised_reset_and_recycle_write_selected_pose_and_colour() -> None:
    randomisation = BrickPassRandomisation(
        seed="test-session",
        speed_choices_m_s=(0.20, 0.30),
        height_choices_m=(-0.01, 0.02),
        colour_choices_rgb=((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        brick_ids=("left", "right"),
    )
    appearance_calls = []
    specs = _specs(left_spawn_y=-0.09)

    adapter, objects, _sensors, _gravity = _make_adapter(
        specs=specs,
        pass_randomisation=randomisation,
        appearance_writer=lambda stage, path, colour: appearance_calls.append(
            (stage, path, colour)
        ),
    )

    left_pass_zero = randomisation.select(specs[0], 0)
    assert objects["sabre_brick_left"].pose_writes[-1][0][:3] == pytest.approx(
        left_pass_zero.spawn_position_m
    )
    assert appearance_calls[:2] == [
        (
            "fake-stage",
            "/World/envs/env_0/SabreBrickLeft",
            randomisation.select(specs[0], 0).display_colour_rgb,
        ),
        (
            "fake-stage",
            "/World/envs/env_0/SabreBrickRight",
            randomisation.select(specs[1], 0).display_colour_rgb,
        ),
    ]

    result = adapter.after_physics_step(0.5)

    recycle = next(
        command
        for command in result.applied_commands
        if isinstance(command, RecycleRequest) and command.brick_id == "left"
    )
    left_pass_one = randomisation.select(specs[0], 1)
    assert recycle.next_pass_spec == left_pass_one
    assert appearance_calls[-1] == (
        "fake-stage",
        "/World/envs/env_0/SabreBrickLeft",
        left_pass_one.display_colour_rgb,
    )
    assert adapter.game.snapshot("left").pass_spec == left_pass_one


def test_approach_is_scripted_with_zero_velocity_and_no_gravity() -> None:
    adapter, objects, _sensors, gravity = _make_adapter()
    _clear_runtime_writes(objects, gravity)

    result = adapter.after_physics_step(0.5)

    left_command = next(
        command
        for command in result.applied_commands
        if command.brick_id == "left"
    )
    assert isinstance(left_command, ScriptedPoseRequest)
    assert objects["sabre_brick_left"].pose_writes[-1][0][:3] == pytest.approx(
        [-0.05, 0.175, -0.03]
    )
    assert objects["sabre_brick_left"].velocity_writes[-1][0] == [0.0] * 6
    assert ("fake-stage", "/World/envs/env_0/SabreBrickLeft", False) in gravity.calls
    assert not any(enabled for _stage, _path, enabled in gravity.calls)


def test_strongest_distal_contact_releases_once_and_pulses_matching_hand() -> None:
    haptics = []
    adapter, objects, sensors, gravity = _make_adapter(
        game_config=BrickGameConfig(
            haptic_amplitude=0.72,
            haptic_duration_s=0.055,
            haptic_frequency_hz=0.0,
        ),
        haptic_sink=lambda event: haptics.append(event) is None,
    )
    _clear_runtime_writes(objects, gravity)
    sensors["sabre_brick_left_contact"].set_forces([0.02, 0.03, 0.04, 0.20])

    first = adapter.after_physics_step(0.01)
    duplicate = adapter.after_physics_step(0.01)

    release = next(
        command
        for command in first.applied_commands
        if isinstance(command, ReleaseToPhysicsRequest)
    )
    assert release.brick_id == "left"
    assert first.contacts[0].contact.hitter == "right"
    assert first.contacts[0].actor_path_expr.endswith(
        "/RightPSM/psm_tool_tip_link"
    )
    assert first.contacts[0].force_n == pytest.approx(0.20)
    assert len(first.haptic_events) == 1
    assert first.haptic_events[0].hand == "right"
    assert first.haptic_events[0].amplitude == 0.72
    assert first.haptic_dispatches[0].accepted is True
    assert haptics == list(first.haptic_events)
    assert objects["sabre_brick_left"].velocity_writes[0][0] == [0.0] * 6
    assert ("fake-stage", "/World/envs/env_0/SabreBrickLeft", True) in gravity.calls
    assert not duplicate.haptic_events


def test_first_hit_applies_one_bounded_contact_directed_velocity_kick() -> None:
    impact_events = []
    adapter, objects, sensors, gravity = _make_adapter(
        brick_mass_kg=0.055,
        hit_speed_m_s=2.0,
        impact_event_sink=impact_events.append,
    )
    _clear_runtime_writes(objects, gravity)
    sensors["sabre_brick_left_contact"].set_force_vectors(
        [
            (0.02, 0.0, 0.0),
            (0.0, -3.0, 4.0),
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
        ]
    )

    first = adapter.after_physics_step(0.01)
    duplicate = adapter.after_physics_step(0.01)

    assert objects["sabre_brick_left"].velocity_writes == [
        [[0.0, -1.2, 1.6, 0.0, 0.0, 0.0]]
    ]
    assert len(first.impact_events) == 1
    impact = first.impact_events[0]
    assert impact.hand == "left"
    assert impact.sensed_force_w == pytest.approx((0.0, -3.0, 4.0))
    assert impact.sensed_force_n == pytest.approx(5.0)
    assert impact.applied_linear_velocity_m_s == pytest.approx((0.0, -1.2, 1.6))
    assert impact.equivalent_impulse_n_s == pytest.approx((0.0, -0.066, 0.088))
    assert impact.equivalent_force_n == pytest.approx(11.0)
    assert impact.physics_dt_s == pytest.approx(0.01)
    assert impact_events == list(first.impact_events)
    assert duplicate.impact_events == ()


def test_falling_is_physics_owned_then_recycled_below_threshold() -> None:
    adapter, objects, sensors, gravity = _make_adapter(
        game_config=BrickGameConfig(
            fall_z_threshold_m=-0.25,
            fall_timeout_s=2.0,
        )
    )
    sensors["sabre_brick_left_contact"].set_forces([0.0, 0.05, 0.0, 0.0])
    adapter.after_physics_step(0.01)
    sensors["sabre_brick_left_contact"].set_forces([0.0] * 4)
    _clear_runtime_writes(objects, gravity)

    objects["sabre_brick_left"].data.root_pos_w[0] = [-0.05, 0.10, -0.20]
    above = adapter.after_physics_step(0.10)

    assert not any(
        command.brick_id == "left" for command in above.applied_commands
    )
    assert not objects["sabre_brick_left"].pose_writes
    assert not objects["sabre_brick_left"].velocity_writes
    assert not any(path.endswith("SabreBrickLeft") for _stage, path, _enabled in gravity.calls)

    objects["sabre_brick_left"].data.root_pos_w[0] = [-0.05, 0.10, -0.26]
    below = adapter.after_physics_step(0.10)

    recycle = next(
        command
        for command in below.applied_commands
        if isinstance(command, RecycleRequest) and command.brick_id == "left"
    )
    assert recycle.next_pass_index == 1
    assert objects["sabre_brick_left"].pose_writes[-1][0][:3] == pytest.approx(
        [-0.05, 0.20, -0.03]
    )
    assert ("fake-stage", "/World/envs/env_0/SabreBrickLeft", False) in gravity.calls
    assert adapter.game.snapshot("left").state is BrickState.APPROACHING
    assert adapter.game.snapshot("left").pass_index == 1
    assert [event.reason for event in below.state_events] == [
        "fall_threshold",
        "fall_threshold_recycled_from_pass_0",
    ]


def test_lane_miss_recycles_without_ever_enabling_gravity() -> None:
    adapter, objects, _sensors, gravity = _make_adapter(
        specs=_specs(left_spawn_y=-0.09)
    )
    _clear_runtime_writes(objects, gravity)

    result = adapter.after_physics_step(0.5)

    left_recycle = next(
        command
        for command in result.applied_commands
        if isinstance(command, RecycleRequest) and command.brick_id == "left"
    )
    assert left_recycle.next_pass_index == 1
    left_gravity = [
        enabled
        for _stage, path, enabled in gravity.calls
        if path.endswith("SabreBrickLeft")
    ]
    assert left_gravity == [False]
    assert not result.haptic_events
    assert [event.reason for event in result.state_events[:2]] == [
        "missed",
        "missed_recycled_from_pass_0",
    ]


def test_fall_timeout_recycles_and_haptic_sink_failure_is_contained() -> None:
    def failing_haptic_sink(_event):
        raise RuntimeError("controller disappeared")

    adapter, _objects, sensors, gravity = _make_adapter(
        game_config=BrickGameConfig(
            fall_z_threshold_m=-0.50,
            fall_timeout_s=0.20,
        ),
        haptic_sink=failing_haptic_sink,
    )
    sensors["sabre_brick_right_contact"].set_forces([0.04, 0.0, 0.0, 0.0])

    first = adapter.after_physics_step(0.10)
    second = adapter.after_physics_step(0.10)

    assert first.haptic_dispatches[0].accepted is False
    assert first.haptic_dispatches[0].error_type == "RuntimeError"
    assert any(
        isinstance(command, RecycleRequest) and command.brick_id == "right"
        for command in second.applied_commands
    )
    right_gravity = [
        enabled
        for _stage, path, enabled in gravity.calls
        if path.endswith("SabreBrickRight")
    ]
    assert True in right_gravity
    assert right_gravity[-1] is False


def test_sensor_filter_order_and_distal_scope_fail_closed() -> None:
    with pytest.raises(ValueError, match="whole-PSM"):
        InstrumentActorFilter(
            "left",
            "{ENV_REGEX_NS}/LeftPSM/.*",
        )

    specs = _specs()
    objects = {
        "sabre_brick_left": _FakeRigidObject(specs[0].spawn_position_m),
        "sabre_brick_right": _FakeRigidObject(specs[1].spawn_position_m),
    }
    sensors = {
        "sabre_brick_left_contact": _FakeContactSensor(
            tuple(reversed([item.prim_path_expr for item in _filters()]))
        ),
        "sabre_brick_right_contact": _FakeContactSensor(
            tuple(item.prim_path_expr for item in _filters())
        ),
    }
    env = SimpleNamespace(
        num_envs=1,
        scene=SimpleNamespace(rigid_objects=objects, sensors=sensors),
    )
    config = IsaacSabreBrickConfig(
        specs=specs,
        game_config=BrickGameConfig(),
        bindings=_bindings(),
        instrument_actor_filters=_filters(),
        contact_force_threshold_n=0.01,
        fall_through_prim_paths=("/World/envs/env_0/SuturePad",),
    )

    with pytest.raises(ValueError, match="filters"):
        IsaacSabreBrickAdapter(
            env,
            config,
            stage="fake-stage",
            tensor_factory=lambda values, _device: values,
            gravity_writer=_GravityRecorder(),
            collision_filter_writer=_GravityRecorder().filter_pairs,
        )


@pytest.mark.parametrize(
    "body_name",
    [
        "psm_main_insertion_link_2",
        "psm_main_insertion_link_3",
        "psm_tool_roll_link",
        "psm_tool_pitch_link",
        "psm_tool_yaw_link",
    ],
)
def test_distal_insertion_and_tool_actor_filters_are_accepted(
    body_name: str,
) -> None:
    actor_filter = InstrumentActorFilter(
        "left",
        f"{{ENV_REGEX_NS}}/LeftPSM/{body_name}",
    )

    assert actor_filter.prim_path_expr.endswith(f"/LeftPSM/{body_name}")


def test_force_matrix_filter_count_must_match_ordered_actor_filters() -> None:
    adapter, _objects, sensors, _gravity = _make_adapter()
    sensors["sabre_brick_left_contact"].set_forces([0.1, 0.0])

    with pytest.raises(RuntimeError, match="resolved 2 filters, expected 4"):
        adapter.after_physics_step(0.01)
