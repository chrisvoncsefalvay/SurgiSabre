"""Fail-closed JSONL telemetry writer for one physical Quest session."""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Any


def _finite_float(value: Any, field: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def _finite_vector(value: Any, length: int, field: str) -> list[float]:
    if hasattr(value, "detach"):
        value = value.detach().cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    result = [_finite_float(item, field) for item in value]
    if len(result) != length:
        raise ValueError(f"{field} must contain {length} values")
    return result


def _brick_pass_spec(
    value: Any,
    *,
    brick_id: str,
    pass_index: int,
    lane: str,
) -> dict[str, Any]:
    """Validate and normalise one deterministic per-pass target contract."""
    if not isinstance(value, dict):
        raise ValueError("pass_spec must be an object")
    fields = {
        "brick_id",
        "pass_index",
        "lane",
        "spawn_position_m",
        "approach_velocity_m_s",
        "approach_end_y_m",
        "size_m",
        "display_colour_rgb",
        "speed_palette_index",
        "height_palette_index",
        "colour_palette_index",
        "randomisation_token",
    }
    if set(value) != fields:
        raise ValueError("pass_spec must contain the complete per-pass contract")
    if value["brick_id"] != brick_id:
        raise ValueError("pass_spec brick_id must match the state event")
    if value["pass_index"] != pass_index:
        raise ValueError("pass_spec pass_index must match the state event")
    if value["lane"] != lane:
        raise ValueError("pass_spec lane must match the state event")

    palette_indices: dict[str, int | None] = {}
    for field in (
        "speed_palette_index",
        "height_palette_index",
        "colour_palette_index",
    ):
        item = value[field]
        if item is not None and (
            not isinstance(item, int) or isinstance(item, bool) or item < 0
        ):
            raise ValueError(f"pass_spec {field} must be a non-negative integer or null")
        palette_indices[field] = item

    token = value["randomisation_token"]
    if not isinstance(token, str) or not token:
        raise ValueError("pass_spec randomisation_token must be a non-empty string")
    size_m = _finite_vector(value["size_m"], 3, "pass_spec size_m")
    if any(component <= 0.0 for component in size_m):
        raise ValueError("pass_spec size_m values must be positive")
    colour = _finite_vector(
        value["display_colour_rgb"],
        3,
        "pass_spec display_colour_rgb",
    )
    if any(not 0.0 <= component <= 1.0 for component in colour):
        raise ValueError("pass_spec display_colour_rgb values must be normalised")

    return {
        "brick_id": brick_id,
        "pass_index": pass_index,
        "lane": lane,
        "spawn_position_m": _finite_vector(
            value["spawn_position_m"],
            3,
            "pass_spec spawn_position_m",
        ),
        "approach_velocity_m_s": _finite_vector(
            value["approach_velocity_m_s"],
            3,
            "pass_spec approach_velocity_m_s",
        ),
        "approach_end_y_m": _finite_float(
            value["approach_end_y_m"],
            "pass_spec approach_end_y_m",
        ),
        "size_m": size_m,
        "display_colour_rgb": colour,
        **palette_indices,
        "randomisation_token": token,
    }


class QuestEvidenceRecorder:
    """Append validated events to a session-scoped JSONL trace."""

    PHASE_NAMES = (
        "INITIAL",
        "DONOR_HOLD",
        "CO_HOLD",
        "RECEIVER_ONLY_HOLD",
        "RETAINED_LIFT",
    )

    def __init__(self, trace_path: str | Path, session_id: str):
        if not session_id or any(character.isspace() for character in session_id):
            raise ValueError("session_id must be non-empty and contain no whitespace")
        self.session_id = session_id
        self.trace_path = Path(trace_path).resolve()
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = self.trace_path.open("x", encoding="utf-8", buffering=1)
        self._sequence = 0
        self._last_controller: dict[str, dict[str, Any]] = {}
        self._last_controller_fault: dict[str, str] = {}
        self._closed = False

    @classmethod
    def from_environment(cls) -> QuestEvidenceRecorder:
        trace_path = os.environ.get("SURGISABRE_TELEMETRY_PATH")
        session_id = os.environ.get("SURGISABRE_SESSION_ID")
        if not trace_path or not session_id:
            raise RuntimeError(
                "SURGISABRE_TELEMETRY_PATH and SURGISABRE_SESSION_ID are required"
            )
        return cls(trace_path, session_id)

    def _emit(self, event_type: str, **fields: Any) -> None:
        if self._closed:
            raise RuntimeError("cannot emit to a closed evidence trace")
        event = {
            "type": event_type,
            "session_id": self.session_id,
            "sequence": self._sequence,
            "monotonic_ns": time.monotonic_ns(),
            **fields,
        }
        self._stream.write(json.dumps(event, allow_nan=False, separators=(",", ":")) + "\n")
        self._sequence += 1

    def record_controller_sample(
        self,
        *,
        hand: str,
        frame_index: int,
        pose_valid: bool,
        position_m: Any,
        orientation_xyzw: Any,
        trigger: Any,
        squeeze: Any,
    ) -> None:
        if hand not in {"left", "right"}:
            raise ValueError("hand must be left or right")
        sample = {
            "hand": hand,
            "frame_index": int(frame_index),
            "pose_valid": bool(pose_valid),
            "position_m": _finite_vector(position_m, 3, "position_m"),
            "orientation_xyzw": _finite_vector(orientation_xyzw, 4, "orientation_xyzw"),
            "trigger": _finite_float(trigger, "trigger"),
            "squeeze": _finite_float(squeeze, "squeeze"),
        }
        self._last_controller[hand] = sample
        self._last_controller_fault.pop(hand, None)
        self._emit("controller_sample", **sample)

    def record_stereo_frame(
        self,
        *,
        client_id: str,
        device_label: str,
        streaming: bool,
        frame_id: int,
        source_timestamp_ms: Any,
        sdk_metrics_timestamp_ms: Any,
        streaming_fps: Any,
        pose_to_render_ms: Any,
        gpu_index: int,
        gpu_name: str,
        gpu_utilization_percent: Any,
        encoder_utilization_percent: Any,
        nvenc_session_count: int,
        nvenc_average_fps: Any,
        nvenc_average_latency_us: Any,
        view_count: int,
        left_view_index: int,
        right_view_index: int,
        left_eye_code: int,
        right_eye_code: int,
        left_width_px: int,
        right_width_px: int,
        height_px: int,
    ) -> None:
        self._emit(
            "stereo_frame",
            client_id=str(client_id),
            device_label=str(device_label),
            streaming=bool(streaming),
            frame_id=int(frame_id),
            source_timestamp_ms=_finite_float(source_timestamp_ms, "source_timestamp_ms"),
            sdk_metrics_timestamp_ms=_finite_float(
                sdk_metrics_timestamp_ms, "sdk_metrics_timestamp_ms"
            ),
            streaming_fps=_finite_float(streaming_fps, "streaming_fps"),
            pose_to_render_ms=_finite_float(pose_to_render_ms, "pose_to_render_ms"),
            gpu_index=int(gpu_index),
            gpu_name=str(gpu_name),
            gpu_utilization_percent=_finite_float(
                gpu_utilization_percent, "gpu_utilization_percent"
            ),
            encoder_utilization_percent=_finite_float(
                encoder_utilization_percent, "encoder_utilization_percent"
            ),
            nvenc_session_count=int(nvenc_session_count),
            nvenc_average_fps=_finite_float(nvenc_average_fps, "nvenc_average_fps"),
            nvenc_average_latency_us=_finite_float(
                nvenc_average_latency_us, "nvenc_average_latency_us"
            ),
            view_count=int(view_count),
            left_view_index=int(left_view_index),
            right_view_index=int(right_view_index),
            left_eye_code=int(left_eye_code),
            right_eye_code=int(right_eye_code),
            left_width_px=int(left_width_px),
            right_width_px=int(right_width_px),
            height_px=int(height_px),
        )

    def record_controller_fault(self, *, hand: str, frame_index: int, fault: str) -> None:
        if hand not in {"left", "right"}:
            raise ValueError("hand must be left or right")
        self._last_controller.pop(hand, None)
        fault = str(fault)
        if self._last_controller_fault.get(hand) == fault:
            return
        self._last_controller_fault[hand] = fault
        self._emit(
            "controller_fault",
            hand=hand,
            frame_index=int(frame_index),
            fault=fault,
        )

    def record_control_action(
        self,
        action: Any,
        *,
        application_active: bool,
        episode_id: int,
        environment_step: int,
    ) -> None:
        values = _finite_vector(action, 18, "action")
        slices = {
            "left": (values[0:3], values[3:7], values[7:9]),
            "right": (values[9:12], values[12:16], values[16:18]),
        }
        for hand, (position, orientation, jaws) in slices.items():
            controller = self._last_controller.get(hand)
            if controller is None:
                continue
            self._emit(
                "control_sample",
                hand=hand,
                controller_frame_index=controller["frame_index"],
                application_active=bool(application_active),
                episode_id=int(episode_id),
                environment_step=int(environment_step),
                tool_position_m=position,
                tool_orientation_xyzw=orientation,
                jaw_command_rad=jaws,
            )

    def record_action_application(
        self,
        *,
        applied_action: Any,
        jaw_position_rad: dict[str, Any],
        controller_frame_index: int,
        episode_id: int,
        environment_step_before: int,
        environment_step_after: int,
        environment_count: int,
    ) -> None:
        values = _finite_vector(applied_action, 18, "applied_action")
        if set(jaw_position_rad) != {"left", "right"}:
            raise ValueError("jaw_position_rad must contain exactly left and right")
        self._emit(
            "action_application",
            applied_action=values,
            jaw_command_rad={
                "left": values[7:9],
                "right": values[16:18],
            },
            jaw_position_rad={
                hand: _finite_vector(jaw_position_rad[hand], 2, f"{hand} jaw_position_rad")
                for hand in ("left", "right")
            },
            controller_frame_index=int(controller_frame_index),
            episode_id=int(episode_id),
            environment_step_before=int(environment_step_before),
            environment_step_after=int(environment_step_after),
            environment_count=int(environment_count),
        )

    def record_runtime_identity(self, *, source: str, identity: dict[str, Any]) -> None:
        if source not in {"browser", "isaac"}:
            raise ValueError("runtime identity source must be browser or isaac")
        if not isinstance(identity, dict) or not identity:
            raise ValueError("runtime identity must be a non-empty object")
        self._emit("runtime_identity", source=source, identity=identity)

    def record_runtime_validation(
        self,
        *,
        source: str,
        validation: dict[str, Any],
    ) -> None:
        """Record configuration observed after the runtime scene is instantiated."""
        if source != "isaac":
            raise ValueError("runtime validation source must be isaac")
        if not isinstance(validation, dict) or not validation:
            raise ValueError("runtime validation must be a non-empty object")
        self._emit("runtime_validation", source=source, validation=validation)

    def record_brick_state(
        self,
        *,
        brick_id: str,
        pass_index: int,
        lane: str,
        previous_state: str,
        state: str,
        reason: str,
        hitter: str | None,
        position_m: Any,
        pass_spec: Any,
        environment_step: int,
    ) -> None:
        """Record one deterministic target lifecycle transition."""
        if lane not in {"left", "right"}:
            raise ValueError("brick lane must be left or right")
        if hitter not in {None, "left", "right"}:
            raise ValueError("brick hitter must be left, right or absent")
        allowed_states = {"approaching", "falling", "recycle_ready"}
        if previous_state not in allowed_states or state not in allowed_states:
            raise ValueError("brick states must be recognised lifecycle values")
        self._emit(
            "brick_state",
            brick_id=str(brick_id),
            pass_index=int(pass_index),
            lane=lane,
            previous_state=previous_state,
            state=state,
            reason=str(reason),
            hitter=hitter,
            position_m=_finite_vector(position_m, 3, "position_m"),
            pass_spec=_brick_pass_spec(
                pass_spec,
                brick_id=str(brick_id),
                pass_index=int(pass_index),
                lane=lane,
            ),
            environment_step=int(environment_step),
        )

    def record_brick_impact(
        self,
        *,
        hand: str,
        brick_id: str,
        pass_index: int,
        actor_path_expr: str,
        sensed_force_w: Any,
        sensed_force_n: Any,
        applied_linear_velocity_m_s: Any,
        equivalent_impulse_n_s: Any,
        equivalent_force_n: Any,
        physics_dt_s: Any,
        environment_step: int,
    ) -> None:
        """Record one bounded contact-directed target impulse."""
        if hand not in {"left", "right"}:
            raise ValueError("brick impact hand must be left or right")
        force_n = _finite_float(sensed_force_n, "sensed_force_n")
        equivalent_force = _finite_float(
            equivalent_force_n,
            "equivalent_force_n",
        )
        dt_s = _finite_float(physics_dt_s, "physics_dt_s")
        if force_n <= 0.0 or equivalent_force <= 0.0 or dt_s <= 0.0:
            raise ValueError("brick impact forces and time step must be positive")
        self._emit(
            "brick_impact",
            hand=hand,
            brick_id=str(brick_id),
            pass_index=int(pass_index),
            actor_path_expr=str(actor_path_expr),
            sensed_force_w=_finite_vector(sensed_force_w, 3, "sensed_force_w"),
            sensed_force_n=force_n,
            applied_linear_velocity_m_s=_finite_vector(
                applied_linear_velocity_m_s,
                3,
                "applied_linear_velocity_m_s",
            ),
            equivalent_impulse_n_s=_finite_vector(
                equivalent_impulse_n_s,
                3,
                "equivalent_impulse_n_s",
            ),
            equivalent_force_n=equivalent_force,
            physics_dt_s=dt_s,
            environment_step=int(environment_step),
        )

    def record_sabre_score(
        self,
        *,
        successful_instances: int,
        failed_instances: int,
        reason: str,
        brick_id: str | None,
        pass_index: int | None,
        environment_step: int,
    ) -> None:
        """Record one aggregate Surg Sabre score update or reset."""
        successful = int(successful_instances)
        failed = int(failed_instances)
        if successful < 0 or failed < 0:
            raise ValueError("Surg Sabre score counts must be non-negative")
        if not reason:
            raise ValueError("Surg Sabre score reason must be non-empty")
        if (brick_id is None) != (pass_index is None):
            raise ValueError(
                "Surg Sabre score brick identifier and pass index must both be present or absent"
            )
        self._emit(
            "sabre_score",
            successful_instances=successful,
            failed_instances=failed,
            total_instances=successful + failed,
            reason=str(reason),
            brick_id=None if brick_id is None else str(brick_id),
            pass_index=None if pass_index is None else int(pass_index),
            environment_step=int(environment_step),
        )

    def record_haptic_pulse(
        self,
        *,
        hand: str,
        brick_id: str,
        pass_index: int,
        intensity: Any,
        duration_s: Any,
        frequency_hz: Any,
        kit_accepted: bool,
        capability: dict[str, Any],
        environment_step: int,
    ) -> None:
        """Record one collision pulse request and Kit's immediate acceptance."""
        if hand not in {"left", "right"}:
            raise ValueError("haptic hand must be left or right")
        if not isinstance(capability, dict) or not capability:
            raise ValueError("haptic capability must be a non-empty object")
        intensity_value = _finite_float(intensity, "intensity")
        duration_value = _finite_float(duration_s, "duration_s")
        frequency_value = _finite_float(frequency_hz, "frequency_hz")
        if not 0.0 <= intensity_value <= 1.0:
            raise ValueError("intensity must be in [0, 1]")
        if duration_value < 0.0 or frequency_value < 0.0:
            raise ValueError("haptic duration and frequency must be non-negative")
        self._emit(
            "haptic_pulse",
            hand=hand,
            brick_id=str(brick_id),
            pass_index=int(pass_index),
            intensity=intensity_value,
            duration_s=duration_value,
            frequency_hz=frequency_value,
            kit_accepted=bool(kit_accepted),
            capability=capability,
            environment_step=int(environment_step),
        )

    def record_trace_terminal(self, *, source: str, status: str, reason: str) -> None:
        if source not in {"browser", "isaac"}:
            raise ValueError("trace terminal source must be browser or isaac")
        if status not in {"clean", "error"}:
            raise ValueError("trace terminal status must be clean or error")
        self._emit("trace_terminal", source=source, status=status, reason=str(reason))

    def record_lifecycle(
        self,
        *,
        command: str,
        before_active: bool,
        after_active: bool,
        episode_before: int,
        episode_after: int,
        handoff_phase_after: int | str,
        reset_counter_before: int,
        reset_counter_after: int,
    ) -> None:
        command = command.upper()
        if command not in {"START", "STOP", "RESET"}:
            raise ValueError("unsupported lifecycle command")
        if isinstance(handoff_phase_after, int):
            handoff_phase_after = self.PHASE_NAMES[handoff_phase_after]
        self._emit(
            "lifecycle",
            command=command,
            before_active=bool(before_active),
            after_active=bool(after_active),
            episode_before=int(episode_before),
            episode_after=int(episode_after),
            handoff_phase_after=str(handoff_phase_after),
            reset_counter_before=int(reset_counter_before),
            reset_counter_after=int(reset_counter_after),
        )

    def record_handoff_sample(
        self,
        *,
        episode_id: int,
        step: int,
        phase: int,
        normal_forces_n: Any,
        opposed_normal_dot: Any,
        engage_force_n: Any,
        disengage_force_n: Any,
        opposed_normal_tolerance_rad: Any,
        needle_lift_delta_m: Any,
        required_lift_delta_m: Any,
    ) -> None:
        try:
            phase_name = self.PHASE_NAMES[int(phase)]
        except (IndexError, ValueError) as error:
            raise ValueError(f"invalid hand-off phase: {phase}") from error
        self._emit(
            "handoff_sample",
            episode_id=int(episode_id),
            step=int(step),
            phase=phase_name,
            normal_forces_n=_finite_vector(normal_forces_n, 4, "normal_forces_n"),
            opposed_normal_dot=_finite_vector(opposed_normal_dot, 2, "opposed_normal_dot"),
            engage_force_n=_finite_float(engage_force_n, "engage_force_n"),
            disengage_force_n=_finite_float(disengage_force_n, "disengage_force_n"),
            opposed_normal_tolerance_rad=_finite_float(
                opposed_normal_tolerance_rad, "opposed_normal_tolerance_rad"
            ),
            needle_lift_delta_m=_finite_float(needle_lift_delta_m, "needle_lift_delta_m"),
            required_lift_delta_m=_finite_float(required_lift_delta_m, "required_lift_delta_m"),
        )

    def record_termination(self, *, episode_id: int, step: int, success: Any, failure: Any) -> None:
        def first_bool(value: Any) -> bool:
            if hasattr(value, "detach"):
                value = value.detach().cpu()
            if hasattr(value, "reshape"):
                value = value.reshape(-1)
            if hasattr(value, "tolist"):
                value = value.tolist()
            if isinstance(value, (list, tuple)):
                if not value:
                    return False
                value = value[0]
            return bool(value)

        self._emit(
            "termination",
            episode_id=int(episode_id),
            step=int(step),
            success=first_bool(success),
            needle_dropped_or_out_of_bounds=first_bool(failure),
        )

    def close(self) -> None:
        if self._closed:
            return
        self._stream.flush()
        os.fsync(self._stream.fileno())
        self._stream.close()
        self._closed = True

    def __enter__(self) -> QuestEvidenceRecorder:
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.close()


SessionTelemetryRecorder = QuestEvidenceRecorder

__all__ = ["QuestEvidenceRecorder", "SessionTelemetryRecorder"]
