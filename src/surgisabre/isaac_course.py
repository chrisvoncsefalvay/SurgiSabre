"""Isaac Lab adapter for the project-local sabre brick state machine.

The pure state machine owns pass timing and lifecycle transitions.  This
adapter is deliberately small: it translates its commands into one-environment
``RigidObject`` writes, reads brick-owned ``ContactSensor`` force matrices and
toggles the brick rigid bodies' PhysX gravity attributes.  It never enables
contact reporting on either PSM.

Isaac Sim, PhysX and torch are resolved only by the default runtime helpers at
call time.  Tests and offline evidence tooling can therefore import this module
with dependency-injected fakes on machines that do not have Isaac installed.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from .course import (
    BrickCommand,
    BrickGameConfig,
    BrickPassRandomisation,
    BrickSpec,
    BrickState,
    BrickStateEvent,
    Hand,
    HapticHitEvent,
    InstrumentContact,
    RecycleRequest,
    ReleaseToPhysicsRequest,
    ScriptedPoseRequest,
    TwoLaneBrickStateMachine,
)

Vector3 = tuple[float, float, float]
QuaternionWXYZ = tuple[float, float, float, float]


class _RigidObject(Protocol):
    device: Any
    data: Any

    def write_root_pose_to_sim(self, root_pose: Any) -> None: ...

    def write_root_velocity_to_sim(self, root_velocity: Any) -> None: ...


class _ContactSensor(Protocol):
    cfg: Any
    data: Any


TensorFactory = Callable[[list[list[float]], Any], Any]
GravityWriter = Callable[[Any, str, bool], None]
CollisionFilterWriter = Callable[[Any, str, tuple[str, ...]], None]
AppearanceWriter = Callable[[Any, str, Vector3], None]
StageProvider = Callable[[], Any]
HapticSink = Callable[[HapticHitEvent], bool | None]
StateEventSink = Callable[[BrickStateEvent], None]
ImpactEventSink = Callable[["BrickImpactEvent"], None]

_ENV_REGEX_NS_TOKEN = "{ENV_REGEX_NS}"
_RESOLVED_ENV_REGEX_NS = "/World/envs/env_.*"


def canonicalise_environment_prim_path(path: str) -> str:
    """Restore Isaac Lab's resolved environment regex to its authored token."""
    path = str(path)
    if path == _RESOLVED_ENV_REGEX_NS:
        return _ENV_REGEX_NS_TOKEN
    resolved_prefix = f"{_RESOLVED_ENV_REGEX_NS}/"
    if path.startswith(resolved_prefix):
        return f"{_ENV_REGEX_NS_TOKEN}/{path[len(resolved_prefix):]}"
    return path


def _finite_float(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{field} must be a finite number") from error
    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number")
    return number


def _finite_quaternion(value: QuaternionWXYZ) -> QuaternionWXYZ:
    result = tuple(_finite_float(item, "spawn_orientation_wxyz") for item in value)
    if len(result) != 4:
        raise ValueError("spawn_orientation_wxyz must contain four values")
    norm = math.sqrt(sum(item * item for item in result))
    if norm <= 1.0e-12:
        raise ValueError("spawn_orientation_wxyz must have non-zero norm")
    return tuple(item / norm for item in result)


def _default_tensor_factory(values: list[list[float]], device: Any) -> Any:
    import torch

    return torch.tensor(values, dtype=torch.float32, device=device)


def _default_stage_provider() -> Any:
    import omni.usd

    return omni.usd.get_context().get_stage()


def _default_gravity_writer(stage: Any, prim_path: str, enabled: bool) -> None:
    from pxr import PhysxSchema

    if stage is None:
        raise RuntimeError("sabre brick gravity write requires an open USD stage")
    prim = stage.GetPrimAtPath(prim_path)
    if not prim or (hasattr(prim, "IsValid") and not prim.IsValid()):
        raise RuntimeError(f"sabre brick rigid body prim is missing: {prim_path}")
    rigid_body = PhysxSchema.PhysxRigidBodyAPI(prim)
    if not rigid_body:
        raise RuntimeError(
            f"sabre brick prim has no PhysxRigidBodyAPI: {prim_path}"
        )
    attribute = rigid_body.GetDisableGravityAttr()
    if not attribute:
        attribute = rigid_body.CreateDisableGravityAttr()
    result = attribute.Set(not enabled)
    if result is False:
        raise RuntimeError(f"failed to set sabre brick gravity: {prim_path}")


def _default_collision_filter_writer(
    stage: Any,
    prim_path: str,
    filtered_prim_paths: tuple[str, ...],
) -> None:
    from pxr import Sdf, UsdPhysics

    if stage is None:
        raise RuntimeError("sabre brick collision filtering requires an open USD stage")
    prim = stage.GetPrimAtPath(prim_path)
    if not prim or (hasattr(prim, "IsValid") and not prim.IsValid()):
        raise RuntimeError(f"sabre brick rigid body prim is missing: {prim_path}")
    for filtered_path in filtered_prim_paths:
        filtered_prim = stage.GetPrimAtPath(filtered_path)
        if not filtered_prim or (
            hasattr(filtered_prim, "IsValid") and not filtered_prim.IsValid()
        ):
            raise RuntimeError(
                f"sabre brick filtered-pair target is missing: {filtered_path}"
            )
    filtered_pairs = UsdPhysics.FilteredPairsAPI.Apply(prim)
    if not filtered_pairs:
        raise RuntimeError(f"failed to apply FilteredPairsAPI to {prim_path}")
    relationship = filtered_pairs.CreateFilteredPairsRel()
    for filtered_path in filtered_prim_paths:
        if relationship.AddTarget(Sdf.Path(filtered_path)) is False:
            raise RuntimeError(
                f"failed to filter collision pair: {prim_path}, {filtered_path}"
            )


def _default_appearance_writer(
    stage: Any,
    prim_path: str,
    colour_rgb: Vector3,
) -> None:
    from pxr import Gf, UsdGeom

    if stage is None:
        raise RuntimeError("sabre brick appearance write requires an open USD stage")
    mesh_path = f"{prim_path}/geometry/mesh"
    prim = stage.GetPrimAtPath(mesh_path)
    if not prim or (hasattr(prim, "IsValid") and not prim.IsValid()):
        raise RuntimeError(f"sabre brick display mesh is missing: {mesh_path}")
    gprim = UsdGeom.Gprim(prim)
    if not gprim:
        raise RuntimeError(f"sabre brick display mesh is not a Gprim: {mesh_path}")
    if gprim.CreateDisplayColorAttr().Set([Gf.Vec3f(*colour_rgb)]) is False:
        raise RuntimeError(f"failed to set sabre brick display colour: {mesh_path}")


def _to_python(value: Any) -> Any:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    return value


@dataclass(frozen=True)
class InstrumentActorFilter:
    """One exact distal PSM actor filter and its controller hand."""

    hand: Hand
    prim_path_expr: str

    def __post_init__(self) -> None:
        if self.hand not in {"left", "right"}:
            raise ValueError("instrument actor hand must be left or right")
        if not self.prim_path_expr.startswith("{") and not self.prim_path_expr.startswith(
            "/"
        ):
            raise ValueError("instrument actor path must be an absolute or environment path")
        psm_name = "LeftPSM" if self.hand == "left" else "RightPSM"
        if f"/{psm_name}/" not in self.prim_path_expr:
            raise ValueError(
                f"{self.hand} instrument actor path must be beneath {psm_name}"
            )
        if self.prim_path_expr.endswith("/.*"):
            raise ValueError("whole-PSM contact filters are not distal actor filters")
        body_name = self.prim_path_expr.rsplit("/", 1)[-1]
        insertion_bodies = {
            "psm_main_insertion_link_2",
            "psm_main_insertion_link_3",
        }
        if body_name not in insertion_bodies and not body_name.startswith("psm_tool_"):
            raise ValueError(
                "instrument actor filters must identify distal insertion or psm_tool actors"
            )


@dataclass(frozen=True)
class IsaacSabreBrickBinding:
    """Bind one pure brick identifier to one Isaac object and sensor."""

    brick_id: str
    rigid_object_name: str
    contact_sensor_name: str
    rigid_body_prim_path: str
    spawn_orientation_wxyz: QuaternionWXYZ = (1.0, 0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        for field, value in (
            ("brick_id", self.brick_id),
            ("rigid_object_name", self.rigid_object_name),
            ("contact_sensor_name", self.contact_sensor_name),
            ("rigid_body_prim_path", self.rigid_body_prim_path),
        ):
            if not value or any(character.isspace() for character in value):
                raise ValueError(f"{field} must be non-empty and contain no whitespace")
        if not self.rigid_body_prim_path.startswith("/"):
            raise ValueError("rigid_body_prim_path must be an absolute USD path")
        object.__setattr__(
            self,
            "spawn_orientation_wxyz",
            _finite_quaternion(self.spawn_orientation_wxyz),
        )


@dataclass(frozen=True)
class IsaacSabreBrickConfig:
    """Complete, explicit binding of the pure game to an Isaac scene."""

    specs: tuple[BrickSpec, ...]
    game_config: BrickGameConfig
    bindings: tuple[IsaacSabreBrickBinding, ...]
    instrument_actor_filters: tuple[InstrumentActorFilter, ...]
    contact_force_threshold_n: float
    fall_through_prim_paths: tuple[str, ...]
    brick_mass_kg: float = 0.055
    hit_speed_m_s: float = 0.0
    pass_randomisation: BrickPassRandomisation | None = None

    def __post_init__(self) -> None:
        if not self.specs:
            raise ValueError("Isaac sabre brick config requires brick specs")
        spec_ids = [spec.brick_id for spec in self.specs]
        binding_ids = [binding.brick_id for binding in self.bindings]
        if len(binding_ids) != len(set(binding_ids)):
            raise ValueError("Isaac sabre brick binding identifiers must be unique")
        if set(spec_ids) != set(binding_ids):
            raise ValueError("Isaac sabre brick bindings must exactly match brick specs")
        object_names = [binding.rigid_object_name for binding in self.bindings]
        sensor_names = [binding.contact_sensor_name for binding in self.bindings]
        prim_paths = [binding.rigid_body_prim_path for binding in self.bindings]
        for field, values in (
            ("rigid object names", object_names),
            ("contact sensor names", sensor_names),
            ("rigid body prim paths", prim_paths),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"Isaac sabre brick {field} must be unique")
        hands = {actor_filter.hand for actor_filter in self.instrument_actor_filters}
        if hands != {"left", "right"}:
            raise ValueError("instrument actor filters must include left and right hands")
        threshold = _finite_float(
            self.contact_force_threshold_n,
            "contact_force_threshold_n",
        )
        if threshold <= 0.0:
            raise ValueError("contact_force_threshold_n must be positive")
        mass = _finite_float(self.brick_mass_kg, "brick_mass_kg")
        hit_speed = _finite_float(self.hit_speed_m_s, "hit_speed_m_s")
        if mass <= 0.0:
            raise ValueError("brick_mass_kg must be positive")
        if hit_speed < 0.0:
            raise ValueError("hit_speed_m_s must be non-negative")
        if len(self.fall_through_prim_paths) != len(
            set(self.fall_through_prim_paths)
        ):
            raise ValueError("fall_through_prim_paths must be unique")
        if any(not path.startswith("/") for path in self.fall_through_prim_paths):
            raise ValueError("fall_through_prim_paths must be absolute USD paths")
        object.__setattr__(self, "contact_force_threshold_n", threshold)
        object.__setattr__(self, "brick_mass_kg", mass)
        object.__setattr__(self, "hit_speed_m_s", hit_speed)


@dataclass(frozen=True)
class ClassifiedBrickContact:
    """Strongest qualifying distal-instrument contact for one brick."""

    contact: InstrumentContact
    force_n: float
    force_w: Vector3
    actor_path_expr: str


@dataclass(frozen=True)
class BrickImpactEvent:
    """One bounded contact-directed velocity kick applied on first hit."""

    brick_id: str
    pass_index: int
    hand: Hand
    actor_path_expr: str
    sensed_force_w: Vector3
    sensed_force_n: float
    applied_linear_velocity_m_s: Vector3
    equivalent_impulse_n_s: Vector3
    equivalent_force_n: float
    physics_dt_s: float


@dataclass(frozen=True)
class HapticDispatchResult:
    """Whether an optional runtime haptic sink accepted one hit event."""

    event: HapticHitEvent
    accepted: bool | None
    error_type: str | None = None


@dataclass(frozen=True)
class IsaacSabreBrickStepResult:
    """Commands, contacts and one-shot events handled during one adapter step."""

    applied_commands: tuple[BrickCommand, ...] = ()
    contacts: tuple[ClassifiedBrickContact, ...] = ()
    haptic_events: tuple[HapticHitEvent, ...] = ()
    haptic_dispatches: tuple[HapticDispatchResult, ...] = ()
    impact_events: tuple[BrickImpactEvent, ...] = ()
    state_events: tuple[BrickStateEvent, ...] = ()


class IsaacSabreBrickAdapter:
    """Translate a two-lane brick game into one Isaac Lab environment.

    Call :meth:`after_physics_step` exactly once after each successful Isaac Lab
    environment step.  Approaching bricks are teleported to the next scripted
    pose with zero velocity and gravity disabled.  A first qualifying contact
    clears the scripted velocity, enables gravity and transfers ownership to
    PhysX until the pure state machine requests a recycle.
    """

    def __init__(
        self,
        env: Any,
        config: IsaacSabreBrickConfig,
        *,
        stage: Any | None = None,
        stage_provider: StageProvider | None = None,
        tensor_factory: TensorFactory | None = None,
        gravity_writer: GravityWriter | None = None,
        collision_filter_writer: CollisionFilterWriter | None = None,
        appearance_writer: AppearanceWriter | None = None,
        haptic_sink: HapticSink | None = None,
        state_event_sink: StateEventSink | None = None,
        impact_event_sink: ImpactEventSink | None = None,
        auto_reset: bool = True,
    ) -> None:
        if stage is not None and stage_provider is not None:
            raise ValueError("pass stage or stage_provider, not both")
        environment_count = int(getattr(env, "num_envs", 0))
        if environment_count != 1:
            raise ValueError(
                "Isaac sabre bricks require exactly one teleoperation environment"
            )
        self._env = env
        self.config = config
        self._stage = stage
        self._stage_provider = stage_provider or _default_stage_provider
        self._tensor_factory = tensor_factory or _default_tensor_factory
        self._gravity_writer = gravity_writer or _default_gravity_writer
        self._collision_filter_writer = (
            collision_filter_writer or _default_collision_filter_writer
        )
        self._appearance_writer = appearance_writer or _default_appearance_writer
        self._haptic_sink = haptic_sink
        self._state_event_sink = state_event_sink
        self._impact_event_sink = impact_event_sink
        self._bindings = {binding.brick_id: binding for binding in config.bindings}
        self._specs = {spec.brick_id: spec for spec in config.specs}
        self._objects: dict[str, _RigidObject] = {}
        self._sensors: dict[str, _ContactSensor] = {}
        self._game = self._new_game()
        self._resolve_scene_assets()
        self._validate_sensor_filters()
        self._configure_fall_through_pairs()
        if auto_reset:
            self.reset()

    @property
    def game(self) -> TwoLaneBrickStateMachine:
        """Return the pure state machine for inspection and evidence capture."""
        return self._game

    def reset(self) -> IsaacSabreBrickStepResult:
        """Restore pass zero at each configured spawn with gravity disabled."""
        self._game = self._new_game()
        for spec in self.config.specs:
            binding = self._bindings[spec.brick_id]
            pass_spec = self._game.snapshot(spec.brick_id).pass_spec
            self._set_gravity(binding, enabled=False)
            self._write_zero_velocity(binding)
            self._write_pose(
                binding,
                pass_spec.spawn_position_m,
                binding.spawn_orientation_wxyz,
            )
            self._write_display_colour(binding, pass_spec.display_colour_rgb)
        return IsaacSabreBrickStepResult()

    def after_physics_step(self, dt_s: float) -> IsaacSabreBrickStepResult:
        """Decode new contacts, advance the pure game and apply its commands."""
        dt_s = _finite_float(dt_s, "dt_s")
        if dt_s <= 0.0:
            raise ValueError("dt_s must be positive")

        contacts: list[ClassifiedBrickContact] = []
        updates = []
        snapshots = {snapshot.brick_id: snapshot for snapshot in self._game.snapshots()}
        observed_positions = {
            brick_id: self._read_position(self._bindings[brick_id])
            for brick_id, snapshot in snapshots.items()
            if snapshot.state is BrickState.FALLING
        }

        for binding in self.config.bindings:
            snapshot = snapshots[binding.brick_id]
            if snapshot.state is not BrickState.APPROACHING:
                continue
            classified = self._classify_contact(binding, snapshot.pass_index)
            if classified is None:
                continue
            contacts.append(classified)
            updates.append(self._game.record_instrument_contact(classified.contact))

        updates.append(self._game.step(dt_s, observed_positions))

        applied_commands: list[BrickCommand] = []
        haptic_events: list[HapticHitEvent] = []
        haptic_dispatches: list[HapticDispatchResult] = []
        impact_events: list[BrickImpactEvent] = []
        state_events: list[BrickStateEvent] = []
        classified_by_pass = {
            (classified.contact.brick_id, classified.contact.pass_index): classified
            for classified in contacts
        }
        for update in updates:
            state_events.extend(update.state_events)
            for command in update.commands:
                impact = self._apply_command(
                    command,
                    physics_dt_s=dt_s,
                    classified_contact=classified_by_pass.get(
                        (command.brick_id, command.pass_index)
                    )
                    if isinstance(command, ReleaseToPhysicsRequest)
                    else None,
                )
                if impact is not None:
                    impact_events.append(impact)
                applied_commands.append(command)
                if isinstance(command, RecycleRequest):
                    acknowledgement = self._game.acknowledge_recycle(
                        command.brick_id,
                        command.next_pass_index,
                    )
                    state_events.extend(acknowledgement.state_events)
            for event in update.haptic_events:
                haptic_events.append(event)
                haptic_dispatches.append(self._dispatch_haptic(event))

        for event in state_events:
            if self._state_event_sink is not None:
                self._state_event_sink(event)
        for event in impact_events:
            if self._impact_event_sink is not None:
                self._impact_event_sink(event)

        return IsaacSabreBrickStepResult(
            applied_commands=tuple(applied_commands),
            contacts=tuple(contacts),
            haptic_events=tuple(haptic_events),
            haptic_dispatches=tuple(haptic_dispatches),
            impact_events=tuple(impact_events),
            state_events=tuple(state_events),
        )

    def runtime_report(self) -> dict[str, Any]:
        """Return the explicit scene binding and current state for evidence."""
        bricks = []
        for binding in self.config.bindings:
            snapshot = self._game.snapshot(binding.brick_id)
            pass_spec = snapshot.pass_spec
            bricks.append(
                {
                    "brick_id": binding.brick_id,
                    "rigid_object_name": binding.rigid_object_name,
                    "contact_sensor_name": binding.contact_sensor_name,
                    "rigid_body_prim_path": binding.rigid_body_prim_path,
                    "spawn_position_m": list(pass_spec.spawn_position_m),
                    "size_m": list(pass_spec.size_m),
                    "approach_velocity_m_s": list(pass_spec.approach_velocity_m_s),
                    "display_colour_rgb": list(pass_spec.display_colour_rgb),
                    "pass_spec": pass_spec.to_dict(),
                    "state": snapshot.state.value,
                    "pass_index": snapshot.pass_index,
                }
            )
        return {
            "environment_count": 1,
            "contact_reporting_scope": "brick_assets_only",
            "psm_contact_reporting_modified": False,
            "contact_force_threshold_n": self.config.contact_force_threshold_n,
            "brick_mass_kg": self.config.brick_mass_kg,
            "hit_speed_m_s": self.config.hit_speed_m_s,
            "hit_impulse_n_s": self.config.brick_mass_kg * self.config.hit_speed_m_s,
            "pass_randomisation": (
                None
                if self.config.pass_randomisation is None
                else self.config.pass_randomisation.report()
            ),
            "fall_through_prim_paths": list(self.config.fall_through_prim_paths),
            "instrument_actor_filters": [
                {
                    "hand": actor_filter.hand,
                    "prim_path_expr": actor_filter.prim_path_expr,
                }
                for actor_filter in self.config.instrument_actor_filters
            ],
            "bricks": bricks,
        }

    def _new_game(self) -> TwoLaneBrickStateMachine:
        return TwoLaneBrickStateMachine(
            self.config.specs,
            self.config.game_config,
            pass_randomisation=self.config.pass_randomisation,
        )

    def _resolve_scene_assets(self) -> None:
        scene = getattr(self._env, "scene", None)
        if scene is None:
            raise ValueError("Isaac sabre brick adapter requires env.scene")
        rigid_objects = getattr(scene, "rigid_objects", {})
        sensors = getattr(scene, "sensors", {})
        for binding in self.config.bindings:
            try:
                self._objects[binding.brick_id] = rigid_objects[
                    binding.rigid_object_name
                ]
            except (KeyError, TypeError) as error:
                raise ValueError(
                    "missing configured sabre brick rigid object: "
                    f"{binding.rigid_object_name}"
                ) from error
            try:
                self._sensors[binding.brick_id] = sensors[
                    binding.contact_sensor_name
                ]
            except (KeyError, TypeError) as error:
                raise ValueError(
                    "missing configured sabre brick contact sensor: "
                    f"{binding.contact_sensor_name}"
                ) from error

    def _validate_sensor_filters(self) -> None:
        expected = tuple(
            canonicalise_environment_prim_path(actor_filter.prim_path_expr)
            for actor_filter in self.config.instrument_actor_filters
        )
        for binding in self.config.bindings:
            sensor = self._sensors[binding.brick_id]
            actual = tuple(
                canonicalise_environment_prim_path(path)
                for path in getattr(sensor.cfg, "filter_prim_paths_expr", ())
            )
            if actual != expected:
                raise ValueError(
                    f"contact sensor {binding.contact_sensor_name!r} filters "
                    f"{actual!r}, expected {expected!r}"
                )

    def _configure_fall_through_pairs(self) -> None:
        if not self.config.fall_through_prim_paths:
            return
        if self._stage is None:
            self._stage = self._stage_provider()
        for binding in self.config.bindings:
            self._collision_filter_writer(
                self._stage,
                binding.rigid_body_prim_path,
                self.config.fall_through_prim_paths,
            )

    def _classify_contact(
        self,
        binding: IsaacSabreBrickBinding,
        pass_index: int,
    ) -> ClassifiedBrickContact | None:
        sensor = self._sensors[binding.brick_id]
        matrix = _to_python(getattr(sensor.data, "force_matrix_w", None))
        if matrix is None:
            raise RuntimeError(
                f"contact sensor {binding.contact_sensor_name!r} has no force matrix"
            )
        try:
            environment_matrix = matrix[0]
        except (IndexError, TypeError) as error:
            raise RuntimeError(
                f"contact sensor {binding.contact_sensor_name!r} has invalid force matrix"
            ) from error
        if not environment_matrix:
            raise RuntimeError(
                f"contact sensor {binding.contact_sensor_name!r} resolved no brick body"
            )

        filter_count = len(self.config.instrument_actor_filters)
        strongest: tuple[float, int, Vector3] | None = None
        for body_forces in environment_matrix:
            if len(body_forces) != filter_count:
                raise RuntimeError(
                    f"contact sensor {binding.contact_sensor_name!r} resolved "
                    f"{len(body_forces)} filters, expected {filter_count}"
                )
            for filter_index, vector in enumerate(body_forces):
                if len(vector) != 3:
                    raise RuntimeError(
                        f"contact sensor {binding.contact_sensor_name!r} force vector "
                        "must contain three values"
                    )
                components = tuple(
                    _finite_float(
                        component,
                        f"{binding.contact_sensor_name}.force_matrix_w",
                    )
                    for component in vector
                )
                force_n = math.sqrt(sum(component * component for component in components))
                if force_n < self.config.contact_force_threshold_n:
                    continue
                if strongest is None or force_n > strongest[0]:
                    strongest = (force_n, filter_index, components)
        if strongest is None:
            return None

        force_n, filter_index, force_w = strongest
        actor_filter = self.config.instrument_actor_filters[filter_index]
        contact = InstrumentContact(
            brick_id=binding.brick_id,
            pass_index=pass_index,
            hitter=actor_filter.hand,
            position_m=self._read_position(binding),
        )
        return ClassifiedBrickContact(
            contact=contact,
            force_n=force_n,
            force_w=force_w,
            actor_path_expr=actor_filter.prim_path_expr,
        )

    def _apply_command(
        self,
        command: BrickCommand,
        *,
        physics_dt_s: float,
        classified_contact: ClassifiedBrickContact | None,
    ) -> BrickImpactEvent | None:
        binding = self._bindings[command.brick_id]
        if isinstance(command, ScriptedPoseRequest):
            if command.gravity_enabled or not command.scripted_motion_enabled:
                raise RuntimeError("invalid scripted sabre brick pose request")
            self._set_gravity(binding, enabled=False)
            self._write_zero_velocity(binding)
            self._write_pose(
                binding,
                command.position_m,
                binding.spawn_orientation_wxyz,
            )
            return None
        if isinstance(command, ReleaseToPhysicsRequest):
            if not command.gravity_enabled or command.scripted_motion_enabled:
                raise RuntimeError("invalid sabre brick physics release request")
            self._set_gravity(binding, enabled=True)
            if self.config.hit_speed_m_s > 0.0:
                if classified_contact is None:
                    raise RuntimeError(
                        "sabre brick hit-speed release requires a classified contact"
                    )
                return self._write_contact_impact(
                    binding,
                    classified_contact,
                    physics_dt_s=physics_dt_s,
                )
            if command.clear_velocity:
                self._write_zero_velocity(binding)
            return None
        if isinstance(command, RecycleRequest):
            if command.gravity_enabled or not command.scripted_motion_enabled:
                raise RuntimeError("invalid sabre brick recycle request")
            self._set_gravity(binding, enabled=False)
            if command.clear_velocity:
                self._write_zero_velocity(binding)
            self._write_pose(
                binding,
                command.position_m,
                binding.spawn_orientation_wxyz,
            )
            self._write_display_colour(
                binding,
                command.next_pass_spec.display_colour_rgb,
            )
            return None
        raise TypeError(f"unsupported sabre brick command: {type(command).__name__}")

    def _write_contact_impact(
        self,
        binding: IsaacSabreBrickBinding,
        classified: ClassifiedBrickContact,
        *,
        physics_dt_s: float,
    ) -> BrickImpactEvent:
        force_n = classified.force_n
        if force_n <= 0.0:
            raise RuntimeError("classified sabre brick contact force must be positive")
        direction = tuple(component / force_n for component in classified.force_w)
        velocity = tuple(
            component * self.config.hit_speed_m_s for component in direction
        )
        impulse = tuple(
            component * self.config.brick_mass_kg for component in velocity
        )
        self._write_velocity(binding, velocity)
        return BrickImpactEvent(
            brick_id=classified.contact.brick_id,
            pass_index=classified.contact.pass_index,
            hand=classified.contact.hitter,
            actor_path_expr=classified.actor_path_expr,
            sensed_force_w=classified.force_w,
            sensed_force_n=force_n,
            applied_linear_velocity_m_s=velocity,
            equivalent_impulse_n_s=impulse,
            equivalent_force_n=(
                self.config.brick_mass_kg
                * self.config.hit_speed_m_s
                / physics_dt_s
            ),
            physics_dt_s=physics_dt_s,
        )

    def _dispatch_haptic(self, event: HapticHitEvent) -> HapticDispatchResult:
        if self._haptic_sink is None:
            return HapticDispatchResult(event=event, accepted=None)
        try:
            result = self._haptic_sink(event)
        except Exception as error:
            return HapticDispatchResult(
                event=event,
                accepted=False,
                error_type=type(error).__name__,
            )
        accepted = None if result is None else bool(result)
        return HapticDispatchResult(event=event, accepted=accepted)

    def _read_position(self, binding: IsaacSabreBrickBinding) -> Vector3:
        asset = self._objects[binding.brick_id]
        positions = _to_python(getattr(asset.data, "root_pos_w", None))
        try:
            position = positions[0]
        except (IndexError, TypeError) as error:
            raise RuntimeError(
                f"rigid object {binding.rigid_object_name!r} has no root position"
            ) from error
        if len(position) != 3:
            raise RuntimeError(
                f"rigid object {binding.rigid_object_name!r} root position is invalid"
            )
        return tuple(
            _finite_float(component, f"{binding.rigid_object_name}.root_pos_w")
            for component in position
        )

    def _write_pose(
        self,
        binding: IsaacSabreBrickBinding,
        position_m: Vector3,
        orientation_wxyz: QuaternionWXYZ,
    ) -> None:
        values = [[*position_m, *orientation_wxyz]]
        asset = self._objects[binding.brick_id]
        asset.write_root_pose_to_sim(
            self._tensor_factory(values, getattr(asset, "device", None))
        )

    def _write_zero_velocity(self, binding: IsaacSabreBrickBinding) -> None:
        self._write_velocity(binding, (0.0, 0.0, 0.0))

    def _write_velocity(
        self,
        binding: IsaacSabreBrickBinding,
        linear_velocity_m_s: Vector3,
    ) -> None:
        values = [[*linear_velocity_m_s, 0.0, 0.0, 0.0]]
        asset = self._objects[binding.brick_id]
        asset.write_root_velocity_to_sim(
            self._tensor_factory(values, getattr(asset, "device", None))
        )

    def _write_display_colour(
        self,
        binding: IsaacSabreBrickBinding,
        colour_rgb: Vector3,
    ) -> None:
        if self.config.pass_randomisation is None:
            return
        if self._stage is None:
            self._stage = self._stage_provider()
        self._appearance_writer(
            self._stage,
            binding.rigid_body_prim_path,
            colour_rgb,
        )

    def _set_gravity(
        self,
        binding: IsaacSabreBrickBinding,
        *,
        enabled: bool,
    ) -> None:
        if self._stage is None:
            self._stage = self._stage_provider()
        self._gravity_writer(
            self._stage,
            binding.rigid_body_prim_path,
            enabled,
        )


__all__ = [
    "BrickImpactEvent",
    "ClassifiedBrickContact",
    "HapticDispatchResult",
    "InstrumentActorFilter",
    "IsaacSabreBrickAdapter",
    "IsaacSabreBrickBinding",
    "IsaacSabreBrickConfig",
    "IsaacSabreBrickStepResult",
]
