"""Focused tests for the runtime Quest telemetry writer."""

from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scripts.merge_telemetry import merge_traces  # noqa: E402
from surgisabre import QuestEvidenceRecorder  # noqa: E402


def brick_pass_spec(
    *,
    brick_id: str = "left_1",
    pass_index: int = 3,
    lane: str = "left",
) -> dict:
    return {
        "brick_id": brick_id,
        "pass_index": pass_index,
        "lane": lane,
        "spawn_position_m": [-0.064, 0.24, -0.018],
        "approach_velocity_m_s": [0.0, -0.208, 0.0],
        "approach_end_y_m": -0.16,
        "size_m": [0.048, 0.038, 0.038],
        "display_colour_rgb": [0.92, 0.12, 0.56],
        "speed_palette_index": 3,
        "height_palette_index": 1,
        "colour_palette_index": 0,
        "randomisation_token": "0123456789abcdef",
    }


class QuestEvidenceRecorderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.trace = Path(self.temporary.name) / "trace.jsonl"
        self.recorder = QuestEvidenceRecorder(self.trace, "quest-test-0001")

    def tearDown(self) -> None:
        self.recorder.close()
        self.temporary.cleanup()

    def events(self) -> list[dict]:
        self.recorder.close()
        return [json.loads(line) for line in self.trace.read_text(encoding="utf-8").splitlines()]

    def test_controller_and_action_share_the_acquisition_frame(self) -> None:
        self.recorder.record_controller_sample(
            hand="left",
            frame_index=8,
            pose_valid=True,
            position_m=[0.1, 0.2, 0.3],
            orientation_xyzw=[0.0, 0.0, 0.0, 1.0],
            trigger=0.4,
            squeeze=0.8,
        )
        self.recorder.record_control_action(
            [
                0.4,
                0.5,
                0.6,
                0.0,
                0.0,
                0.0,
                1.0,
                -0.1,
                0.1,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                1.0,
                -0.2,
                0.2,
            ],
            application_active=True,
            episode_id=2,
            environment_step=17,
        )
        events = self.events()
        self.assertEqual([event["sequence"] for event in events], [0, 1])
        self.assertEqual(events[1]["controller_frame_index"], 8)
        self.assertEqual(events[1]["jaw_command_rad"], [-0.1, 0.1])
        self.assertTrue(events[1]["application_active"])
        self.assertEqual(events[1]["environment_step"], 17)

    def test_fault_prevents_a_stale_control_pair(self) -> None:
        self.recorder.record_controller_sample(
            hand="right",
            frame_index=1,
            pose_valid=True,
            position_m=[0.0, 0.0, 0.0],
            orientation_xyzw=[0.0, 0.0, 0.0, 1.0],
            trigger=0.0,
            squeeze=0.0,
        )
        self.recorder.record_controller_fault(hand="right", frame_index=2, fault="tracking invalid")
        self.recorder.record_control_action(
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, -0.1, 0.1] * 2,
            application_active=False,
            episode_id=0,
            environment_step=0,
        )
        events = self.events()
        self.assertNotIn("control_sample", [event["type"] for event in events])

    def test_non_finite_data_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "trigger must be finite"):
            self.recorder.record_controller_sample(
                hand="left",
                frame_index=0,
                pose_valid=True,
                position_m=[0.0, 0.0, 0.0],
                orientation_xyzw=[0.0, 0.0, 0.0, 1.0],
                trigger=math.nan,
                squeeze=0.0,
            )

    def test_action_application_records_command_and_measured_jaws(self) -> None:
        action = [float(index) / 100.0 for index in range(18)]
        self.recorder.record_action_application(
            applied_action=action,
            jaw_position_rad={
                "left": [-0.30, 0.29],
                "right": [-0.12, 0.11],
            },
            controller_frame_index=41,
            episode_id=0,
            environment_step_before=9,
            environment_step_after=10,
            environment_count=1,
        )

        event = self.events()[0]
        self.assertEqual(event["jaw_command_rad"]["left"], action[7:9])
        self.assertEqual(event["jaw_command_rad"]["right"], action[16:18])
        self.assertEqual(event["jaw_position_rad"]["left"], [-0.30, 0.29])
        self.assertEqual(event["jaw_position_rad"]["right"], [-0.12, 0.11])

    def test_action_application_rejects_incomplete_or_invalid_measured_jaws(self) -> None:
        base = {
            "applied_action": [0.0] * 18,
            "controller_frame_index": 0,
            "episode_id": 0,
            "environment_step_before": 0,
            "environment_step_after": 1,
            "environment_count": 1,
        }
        with self.assertRaisesRegex(ValueError, "exactly left and right"):
            self.recorder.record_action_application(
                **base,
                jaw_position_rad={"left": [0.0, 0.0]},
            )
        with self.assertRaisesRegex(ValueError, "right jaw_position_rad must be finite"):
            self.recorder.record_action_application(
                **base,
                jaw_position_rad={
                    "left": [0.0, 0.0],
                    "right": [math.nan, 0.0],
                },
            )

    def test_runtime_validation_records_only_observed_isaac_configuration(self) -> None:
        validation = {
            "needle_prim_present": False,
            "trigger_jaw_control_enabled": True,
        }

        self.recorder.record_runtime_validation(
            source="isaac",
            validation=validation,
        )

        event = self.events()[0]
        self.assertEqual(event["type"], "runtime_validation")
        self.assertEqual(event["source"], "isaac")
        self.assertEqual(event["validation"], validation)

    def test_runtime_validation_rejects_non_isaac_or_empty_reports(self) -> None:
        with self.assertRaisesRegex(ValueError, "source must be isaac"):
            self.recorder.record_runtime_validation(
                source="browser",
                validation={"needle_prim_present": False},
            )
        with self.assertRaisesRegex(ValueError, "non-empty object"):
            self.recorder.record_runtime_validation(source="isaac", validation={})

    def test_brick_hit_and_haptic_pulse_are_structured_for_physical_evidence(self) -> None:
        self.recorder.record_brick_state(
            brick_id="left_1",
            pass_index=3,
            lane="left",
            previous_state="approaching",
            state="falling",
            reason="instrument_hit",
            hitter="right",
            position_m=[-0.05, 0.02, -0.03],
            pass_spec=brick_pass_spec(),
            environment_step=71,
        )
        capability = {
            "hand": "right",
            "available": True,
            "reason": "available",
        }
        self.recorder.record_haptic_pulse(
            hand="right",
            brick_id="left_1",
            pass_index=3,
            intensity=0.72,
            duration_s=0.055,
            frequency_hz=0.0,
            kit_accepted=True,
            capability=capability,
            environment_step=71,
        )
        self.recorder.record_brick_impact(
            hand="right",
            brick_id="left_1",
            pass_index=3,
            actor_path_expr="{ENV_REGEX_NS}/RightPSM/psm_tool_yaw_link",
            sensed_force_w=[0.03, 0.04, 0.0],
            sensed_force_n=0.05,
            applied_linear_velocity_m_s=[1.2, 1.6, 0.0],
            equivalent_impulse_n_s=[0.066, 0.088, 0.0],
            equivalent_force_n=13.2,
            physics_dt_s=1.0 / 120.0,
            environment_step=71,
        )

        brick, pulse, impact = self.events()
        self.assertEqual(brick["type"], "brick_state")
        self.assertEqual(brick["reason"], "instrument_hit")
        self.assertEqual(brick["hitter"], "right")
        self.assertEqual(brick["pass_spec"], brick_pass_spec())
        self.assertEqual(pulse["type"], "haptic_pulse")
        self.assertEqual(pulse["hand"], "right")
        self.assertTrue(pulse["kit_accepted"])
        self.assertEqual(pulse["capability"], capability)
        self.assertEqual(impact["type"], "brick_impact")
        self.assertEqual(impact["applied_linear_velocity_m_s"], [1.2, 1.6, 0.0])
        self.assertEqual(impact["equivalent_impulse_n_s"], [0.066, 0.088, 0.0])

    def test_brick_and_haptic_events_reject_invalid_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "brick lane"):
            self.recorder.record_brick_state(
                brick_id="left_1",
                pass_index=0,
                lane="centre",
                previous_state="approaching",
                state="falling",
                reason="instrument_hit",
                hitter="left",
                position_m=[0.0, 0.0, 0.0],
                pass_spec=brick_pass_spec(),
                environment_step=1,
            )
        invalid_pass = brick_pass_spec()
        invalid_pass["randomisation_token"] = ""
        with self.assertRaisesRegex(ValueError, "randomisation_token"):
            self.recorder.record_brick_state(
                brick_id="left_1",
                pass_index=3,
                lane="left",
                previous_state="approaching",
                state="falling",
                reason="instrument_hit",
                hitter="left",
                position_m=[0.0, 0.0, 0.0],
                pass_spec=invalid_pass,
                environment_step=1,
            )
        with self.assertRaisesRegex(ValueError, "forces and time step"):
            self.recorder.record_brick_impact(
                hand="left",
                brick_id="left_1",
                pass_index=3,
                actor_path_expr="{ENV_REGEX_NS}/LeftPSM/psm_tool_yaw_link",
                sensed_force_w=[0.0, 0.0, 0.0],
                sensed_force_n=0.0,
                applied_linear_velocity_m_s=[0.0, 0.0, 0.0],
                equivalent_impulse_n_s=[0.0, 0.0, 0.0],
                equivalent_force_n=0.0,
                physics_dt_s=1.0 / 120.0,
                environment_step=1,
            )
        with self.assertRaisesRegex(ValueError, "intensity"):
            self.recorder.record_haptic_pulse(
                hand="left",
                brick_id="left",
                pass_index=0,
                intensity=1.1,
                duration_s=0.05,
                frequency_hz=0.0,
                kit_accepted=False,
                capability={"available": False},
                environment_step=1,
            )

    def test_sabre_score_records_aggregate_outcome_and_reset(self) -> None:
        self.recorder.record_sabre_score(
            successful_instances=4,
            failed_instances=2,
            reason="instrument_hit",
            brick_id="left_1",
            pass_index=3,
            environment_step=71,
        )
        self.recorder.record_sabre_score(
            successful_instances=0,
            failed_instances=0,
            reason="environment_reset",
            brick_id=None,
            pass_index=None,
            environment_step=72,
        )

        scored, reset = self.events()
        self.assertEqual(scored["type"], "sabre_score")
        self.assertEqual(scored["successful_instances"], 4)
        self.assertEqual(scored["failed_instances"], 2)
        self.assertEqual(scored["total_instances"], 6)
        self.assertEqual(scored["brick_id"], "left_1")
        self.assertIsNone(reset["brick_id"])
        self.assertEqual(reset["reason"], "environment_reset")

    def test_sabre_score_rejects_negative_or_partial_identity(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-negative"):
            self.recorder.record_sabre_score(
                successful_instances=-1,
                failed_instances=0,
                reason="instrument_hit",
                brick_id="left_1",
                pass_index=0,
                environment_step=1,
            )
        with self.assertRaisesRegex(ValueError, "both be present or absent"):
            self.recorder.record_sabre_score(
                successful_instances=0,
                failed_instances=0,
                reason="environment_reset",
                brick_id="left_1",
                pass_index=None,
                environment_step=1,
            )
    def test_handoff_event_uses_task_phase_names(self) -> None:
        self.recorder.record_handoff_sample(
            episode_id=3,
            step=42,
            phase=4,
            normal_forces_n=[0.0, 0.0, 0.02, 0.02],
            opposed_normal_dot=[0.0, -1.0],
            engage_force_n=0.01487981432835477,
            disengage_force_n=0.007439907164177385,
            opposed_normal_tolerance_rad=math.radians(25.0),
            needle_lift_delta_m=0.02,
            required_lift_delta_m=0.015,
        )
        event = self.events()[0]
        self.assertEqual(event["phase"], "RETAINED_LIFT")
        self.assertEqual(event["episode_id"], 3)

    def test_trace_merge_reassigns_one_global_sequence(self) -> None:
        self.recorder.record_stereo_frame(
            client_id="quest-client-01",
            device_label="Mozilla/5.0 OculusBrowser/36.0 Quest 3",
            streaming=True,
            frame_id=1,
            source_timestamp_ms=10.0,
            sdk_metrics_timestamp_ms=1000.0,
            streaming_fps=72.0,
            pose_to_render_ms=20.0,
            gpu_index=0,
            gpu_name="NVIDIA RTX PRO 6000 Blackwell Workstation Edition",
            gpu_utilization_percent=45.0,
            encoder_utilization_percent=18.0,
            nvenc_session_count=1,
            nvenc_average_fps=72.0,
            nvenc_average_latency_us=3100.0,
            view_count=2,
            left_view_index=0,
            right_view_index=1,
            left_eye_code=1,
            right_eye_code=2,
            left_width_px=1024,
            right_width_px=1024,
            height_px=1024,
        )
        self.recorder.close()
        second_path = Path(self.temporary.name) / "second.jsonl"
        second = QuestEvidenceRecorder(second_path, "quest-test-0001")
        second.record_lifecycle(
            command="START",
            before_active=False,
            after_active=True,
            episode_before=0,
            episode_after=0,
            handoff_phase_after=0,
            reset_counter_before=0,
            reset_counter_after=0,
        )
        second.close()
        output = Path(self.temporary.name) / "merged.jsonl"
        self.assertEqual(merge_traces([self.trace, second_path], output), 2)
        merged = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([event["sequence"] for event in merged], [0, 1])
        self.assertEqual({event["session_id"] for event in merged}, {"quest-test-0001"})


if __name__ == "__main__":
    unittest.main()
