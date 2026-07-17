"""Focused tests for the project-local Kit XRCore haptic adapter."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from surgisabre.haptics import (  # noqa: E402
    CONTROLLER_DEVICE_PATHS,
    XRControllerHaptics,
)


class _FakeDevice:
    def __init__(
        self,
        *,
        outputs: set[str] | None = None,
        query_error: Exception | None = None,
        pulse_error: Exception | None = None,
    ) -> None:
        self.outputs = (
            outputs
            if outputs is not None
            else {
                "haptic",
                "haptic:duration",
                "haptic:frequency",
            }
        )
        self.query_error = query_error
        self.pulse_error = pulse_error
        self.queries: list[str] = []
        self.pulses: list[dict[str, Any]] = []

    def has_output(self, output_name: str) -> bool:
        self.queries.append(output_name)
        if self.query_error is not None:
            raise self.query_error
        return output_name in self.outputs

    def trigger_haptic_pulse(self, **values: Any) -> None:
        if self.pulse_error is not None:
            raise self.pulse_error
        self.pulses.append(values)


class _FakeCore:
    def __init__(
        self,
        devices: dict[str, _FakeDevice | None],
        *,
        lookup_error: Exception | None = None,
    ) -> None:
        self.devices = devices
        self.lookup_error = lookup_error
        self.lookups: list[str] = []

    def get_input_device(self, handle: str) -> _FakeDevice | None:
        self.lookups.append(handle)
        if self.lookup_error is not None:
            raise self.lookup_error
        return self.devices.get(handle)


class _BrokenLogger:
    def warning(self, *_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("logging failed")


class XRControllerHapticsTests(unittest.TestCase):
    def test_pulse_uses_existing_device_and_exact_kit_signature(self) -> None:
        device = _FakeDevice()
        core = _FakeCore({CONTROLLER_DEVICE_PATHS["left"]: device})
        haptics = XRControllerHaptics(core)

        accepted = haptics.pulse(
            "left",
            intensity=0.75,
            duration_s=0.08,
            frequency_hz=120.0,
        )

        self.assertTrue(accepted)
        self.assertEqual(core.lookups, ["/user/hand/left"])
        self.assertEqual(
            device.queries,
            ["haptic", "haptic:duration", "haptic:frequency"],
        )
        self.assertEqual(
            device.pulses,
            [
                {
                    "intensity": 0.75,
                    "duration": 0.08,
                    "frequency": 120.0,
                    "output_name": "haptic",
                }
            ],
        )

    def test_left_and_right_use_the_openxr_user_paths(self) -> None:
        left = _FakeDevice()
        right = _FakeDevice()
        core = _FakeCore(
            {
                CONTROLLER_DEVICE_PATHS["left"]: left,
                CONTROLLER_DEVICE_PATHS["right"]: right,
            }
        )
        haptics = XRControllerHaptics(core)

        self.assertTrue(haptics.pulse("left"))
        self.assertTrue(haptics.pulse("right"))

        self.assertEqual(core.lookups, ["/user/hand/left", "/user/hand/right"])
        self.assertEqual(len(left.pulses), 1)
        self.assertEqual(len(right.pulses), 1)

    def test_capability_report_is_json_safe_and_checks_all_required_outputs(self) -> None:
        left = _FakeDevice()
        right = _FakeDevice(outputs={"haptic", "haptic:duration"})
        core = _FakeCore(
            {
                CONTROLLER_DEVICE_PATHS["left"]: left,
                CONTROLLER_DEVICE_PATHS["right"]: right,
            }
        )

        report = XRControllerHaptics(core).capability_report()

        self.assertEqual(report["backend"], "omni.kit.xr.core")
        self.assertEqual(report["scope"], "kit_xr_output_exposure")
        self.assertTrue(report["physical_delivery_requires_cloudxr_evidence"])
        self.assertTrue(report["hands"]["left"]["available"])
        self.assertFalse(report["hands"]["right"]["available"])
        self.assertTrue(report["hands"]["right"]["haptic_output_present"])
        self.assertTrue(report["hands"]["right"]["duration_output_present"])
        self.assertFalse(report["hands"]["right"]["frequency_output_present"])
        self.assertEqual(
            report["hands"]["right"]["reason"],
            "missing_required_outputs",
        )

    def test_missing_haptic_output_fails_closed_without_pulsing(self) -> None:
        device = _FakeDevice(
            outputs={"haptic:duration", "haptic:frequency"}
        )
        haptics = XRControllerHaptics(
            _FakeCore({CONTROLLER_DEVICE_PATHS["right"]: device})
        )

        self.assertFalse(haptics.pulse("right"))
        self.assertEqual(device.pulses, [])

    def test_missing_core_device_and_unknown_hand_are_safe_no_ops(self) -> None:
        cases = (
            ("missing core", XRControllerHaptics(xr_core_provider=lambda: None), "left"),
            ("missing device", XRControllerHaptics(_FakeCore({})), "right"),
            ("unknown hand", XRControllerHaptics(_FakeCore({})), "centre"),
        )
        for label, haptics, hand in cases:
            with self.subTest(label=label):
                self.assertFalse(haptics.pulse(hand))

    def test_provider_lookup_output_pulse_and_logging_errors_do_not_escape(self) -> None:
        cases = (
            (
                "provider",
                XRControllerHaptics(
                    xr_core_provider=lambda: (_ for _ in ()).throw(
                        RuntimeError("provider failed")
                    )
                ),
            ),
            (
                "lookup",
                XRControllerHaptics(
                    _FakeCore({}, lookup_error=RuntimeError("lookup failed"))
                ),
            ),
            (
                "query",
                XRControllerHaptics(
                    _FakeCore(
                        {
                            CONTROLLER_DEVICE_PATHS["left"]: _FakeDevice(
                                query_error=RuntimeError("query failed")
                            )
                        }
                    )
                ),
            ),
            (
                "pulse",
                XRControllerHaptics(
                    _FakeCore(
                        {
                            CONTROLLER_DEVICE_PATHS["left"]: _FakeDevice(
                                pulse_error=RuntimeError("pulse failed")
                            )
                        }
                    )
                ),
            ),
            (
                "logging",
                XRControllerHaptics(
                    xr_core_provider=lambda: None,
                    logger=_BrokenLogger(),
                ),
            ),
        )
        for label, haptics in cases:
            with self.subTest(label=label):
                self.assertFalse(haptics.pulse("left"))

    def test_invalid_parameters_fail_closed_before_device_lookup(self) -> None:
        cases = (
            {"intensity": math.nan},
            {"duration_s": math.inf},
            {"frequency_hz": -1.0},
            {"duration_s": -0.01},
            {"intensity": object()},
        )
        for values in cases:
            with self.subTest(values=values):
                core = _FakeCore({CONTROLLER_DEVICE_PATHS["left"]: _FakeDevice()})
                self.assertFalse(XRControllerHaptics(core).pulse("left", **values))
                self.assertEqual(core.lookups, [])

    def test_finite_intensity_is_clamped_to_openxr_range(self) -> None:
        cases = ((-2.0, 0.0), (2.0, 1.0))
        for requested, expected in cases:
            with self.subTest(requested=requested):
                device = _FakeDevice()
                haptics = XRControllerHaptics(
                    _FakeCore({CONTROLLER_DEVICE_PATHS["left"]: device})
                )

                self.assertTrue(haptics.pulse("left", intensity=requested))
                self.assertEqual(device.pulses[0]["intensity"], expected)

    def test_stop_and_stop_all_use_best_effort_zero_amplitude_pulses(self) -> None:
        left = _FakeDevice()
        right = _FakeDevice()
        haptics = XRControllerHaptics(
            _FakeCore(
                {
                    CONTROLLER_DEVICE_PATHS["left"]: left,
                    CONTROLLER_DEVICE_PATHS["right"]: right,
                }
            )
        )

        self.assertTrue(haptics.stop("left"))
        self.assertTrue(haptics.stop_all())

        zero_pulse = {
            "intensity": 0.0,
            "duration": 0.0,
            "frequency": 0.0,
            "output_name": "haptic",
        }
        self.assertEqual(left.pulses, [zero_pulse, zero_pulse])
        self.assertEqual(right.pulses, [zero_pulse])

    def test_provider_is_resolved_per_call_for_dynamic_xr_lifecycle(self) -> None:
        device = _FakeDevice()
        responses = iter(
            (
                None,
                _FakeCore({CONTROLLER_DEVICE_PATHS["left"]: device}),
            )
        )
        haptics = XRControllerHaptics(xr_core_provider=lambda: next(responses))

        self.assertFalse(haptics.pulse("left"))
        self.assertTrue(haptics.pulse("left"))
        self.assertEqual(len(device.pulses), 1)

    def test_default_constructor_defers_kit_import_until_a_runtime_call(self) -> None:
        haptics = XRControllerHaptics()

        self.assertEqual(type(haptics).__name__, "XRControllerHaptics")


if __name__ == "__main__":
    unittest.main()
