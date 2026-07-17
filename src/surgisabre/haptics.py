"""Fail-closed haptics for the XR controllers owned by the Kit session.

The adapter deliberately uses the existing ``omni.kit.xr.core`` input devices.
It does not create an IsaacTeleop controller tracker, OpenXR action set or
session.  Kit is imported only by the default provider at call time so this
module remains importable and testable outside Isaac Sim.

An available capability means that Kit exposes the required output components.
It does not prove that CloudXR mapped the output to a physical controller.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Protocol

HAPTIC_OUTPUT_NAME = "haptic"
HAPTIC_DURATION_OUTPUT_NAME = "haptic:duration"
HAPTIC_FREQUENCY_OUTPUT_NAME = "haptic:frequency"

CONTROLLER_DEVICE_PATHS = {
    "left": "/user/hand/left",
    "right": "/user/hand/right",
}


class _XRInputDevice(Protocol):
    def has_output(self, output_name: str) -> bool: ...

    def trigger_haptic_pulse(
        self,
        intensity: float = 0.5,
        duration: float = 0.0,
        frequency: float = 0.0,
        output_name: str = HAPTIC_OUTPUT_NAME,
    ) -> None: ...


class _XRCore(Protocol):
    def get_input_device(self, handle: str) -> _XRInputDevice | None: ...


XRCoreProvider = Callable[[], _XRCore | None]


@dataclass(frozen=True)
class XRHapticCapability:
    """One hand's currently observed Kit XRCore haptic capability."""

    hand: str
    device_path: str | None
    device_present: bool
    haptic_output_present: bool
    duration_output_present: bool
    frequency_output_present: bool
    available: bool
    reason: str
    error_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation for runtime evidence."""
        return asdict(self)


def _default_xr_core_provider() -> _XRCore | None:
    """Resolve Kit XRCore lazily without making it a package dependency."""
    from omni.kit.xr.core import XRCore

    return XRCore.get_singleton()


class XRControllerHaptics:
    """Safely pulse the existing left and right Kit XR input devices.

    Calls must be made on the Kit application thread.  Every runtime lookup,
    capability query and output call is guarded so loss of the XR session or a
    controller cannot interrupt teleoperation.
    """

    def __init__(
        self,
        xr_core: _XRCore | None = None,
        *,
        xr_core_provider: XRCoreProvider | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if xr_core is not None and xr_core_provider is not None:
            raise ValueError("pass xr_core or xr_core_provider, not both")
        if xr_core_provider is not None:
            self._xr_core_provider = xr_core_provider
        elif xr_core is not None:
            self._xr_core_provider = lambda: xr_core
        else:
            self._xr_core_provider = _default_xr_core_provider
        self._logger = logger or logging.getLogger(__name__)
        self._reported_failures: set[tuple[str, str, str | None]] = set()

    def capability(self, hand: str) -> XRHapticCapability:
        """Return the current output capability for ``left`` or ``right``."""
        capability, _ = self._resolve_device(hand)
        return capability

    def capability_report(self) -> dict[str, Any]:
        """Return a JSON-safe snapshot for diagnostics and session evidence."""
        return {
            "backend": "omni.kit.xr.core",
            "output_name": HAPTIC_OUTPUT_NAME,
            "scope": "kit_xr_output_exposure",
            "physical_delivery_requires_cloudxr_evidence": True,
            "hands": {
                hand: self.capability(hand).to_dict()
                for hand in CONTROLLER_DEVICE_PATHS
            },
        }

    def pulse(
        self,
        hand: str,
        *,
        intensity: float = 0.5,
        duration_s: float = 0.1,
        frequency_hz: float = 0.0,
    ) -> bool:
        """Request one finite pulse, returning whether Kit accepted the call.

        Intensity is clamped to OpenXR's ``[0, 1]`` range.  Non-finite values,
        negative durations and negative frequencies are rejected without an
        output call.
        """
        parameters = self._normalise_pulse_parameters(
            intensity=intensity,
            duration_s=duration_s,
            frequency_hz=frequency_hz,
        )
        if parameters is None:
            self._report_failure(
                hand,
                "invalid_pulse_parameters",
                None,
                "Ignoring invalid XR haptic pulse parameters",
            )
            return False

        capability, device = self._resolve_device(hand)
        if not capability.available or device is None:
            self._report_capability_failure(capability)
            return False

        safe_intensity, safe_duration_s, safe_frequency_hz = parameters
        try:
            device.trigger_haptic_pulse(
                intensity=safe_intensity,
                duration=safe_duration_s,
                frequency=safe_frequency_hz,
                output_name=HAPTIC_OUTPUT_NAME,
            )
        except Exception as error:
            self._report_failure(
                hand,
                "pulse_failed",
                type(error).__name__,
                f"XR haptic pulse failed for {hand} controller",
            )
            return False
        return True

    def stop(self, hand: str) -> bool:
        """Supersede a pulse with zero amplitude through the same Kit output.

        Kit XRCore 109 has no public explicit stop method.  Collision feedback
        should therefore use short finite pulses.  This zero-amplitude pulse is
        a best-effort shutdown safeguard, not an ``xrStopHapticFeedback``
        acknowledgement.
        """
        return self.pulse(
            hand,
            intensity=0.0,
            duration_s=0.0,
            frequency_hz=0.0,
        )

    def stop_all(self) -> bool:
        """Best-effort zero both controller outputs without short-circuiting."""
        results = [self.stop(hand) for hand in CONTROLLER_DEVICE_PATHS]
        return all(results)

    @staticmethod
    def _normalise_pulse_parameters(
        *,
        intensity: Any,
        duration_s: Any,
        frequency_hz: Any,
    ) -> tuple[float, float, float] | None:
        try:
            values = (
                float(intensity),
                float(duration_s),
                float(frequency_hz),
            )
        except (TypeError, ValueError, OverflowError):
            return None
        if not all(math.isfinite(value) for value in values):
            return None
        safe_intensity = min(1.0, max(0.0, values[0]))
        if values[1] < 0.0 or values[2] < 0.0:
            return None
        return safe_intensity, values[1], values[2]

    def _resolve_device(
        self,
        hand: str,
    ) -> tuple[XRHapticCapability, _XRInputDevice | None]:
        device_path = CONTROLLER_DEVICE_PATHS.get(hand)
        if device_path is None:
            return self._unavailable(hand, None, "unsupported_hand"), None

        try:
            xr_core = self._xr_core_provider()
        except Exception as error:
            return (
                self._unavailable(
                    hand,
                    device_path,
                    "xr_core_provider_failed",
                    error_type=type(error).__name__,
                ),
                None,
            )
        if xr_core is None:
            return self._unavailable(hand, device_path, "xr_core_unavailable"), None

        try:
            device = xr_core.get_input_device(device_path)
        except Exception as error:
            return (
                self._unavailable(
                    hand,
                    device_path,
                    "input_device_lookup_failed",
                    error_type=type(error).__name__,
                ),
                None,
            )
        if device is None:
            return self._unavailable(hand, device_path, "input_device_unavailable"), None

        try:
            outputs = {
                HAPTIC_OUTPUT_NAME: bool(device.has_output(HAPTIC_OUTPUT_NAME)),
                HAPTIC_DURATION_OUTPUT_NAME: bool(
                    device.has_output(HAPTIC_DURATION_OUTPUT_NAME)
                ),
                HAPTIC_FREQUENCY_OUTPUT_NAME: bool(
                    device.has_output(HAPTIC_FREQUENCY_OUTPUT_NAME)
                ),
            }
        except Exception as error:
            return (
                self._unavailable(
                    hand,
                    device_path,
                    "output_query_failed",
                    device_present=True,
                    error_type=type(error).__name__,
                ),
                None,
            )

        missing_outputs = [name for name, present in outputs.items() if not present]
        reason = "available" if not missing_outputs else "missing_required_outputs"
        capability = XRHapticCapability(
            hand=hand,
            device_path=device_path,
            device_present=True,
            haptic_output_present=outputs[HAPTIC_OUTPUT_NAME],
            duration_output_present=outputs[HAPTIC_DURATION_OUTPUT_NAME],
            frequency_output_present=outputs[HAPTIC_FREQUENCY_OUTPUT_NAME],
            available=not missing_outputs,
            reason=reason,
        )
        return capability, device

    @staticmethod
    def _unavailable(
        hand: str,
        device_path: str | None,
        reason: str,
        *,
        device_present: bool = False,
        error_type: str | None = None,
    ) -> XRHapticCapability:
        return XRHapticCapability(
            hand=hand,
            device_path=device_path,
            device_present=device_present,
            haptic_output_present=False,
            duration_output_present=False,
            frequency_output_present=False,
            available=False,
            reason=reason,
            error_type=error_type,
        )

    def _report_capability_failure(self, capability: XRHapticCapability) -> None:
        self._report_failure(
            capability.hand,
            capability.reason,
            capability.error_type,
            f"XR haptics unavailable for {capability.hand} controller",
        )

    def _report_failure(
        self,
        hand: str,
        reason: str,
        error_type: str | None,
        message: str,
    ) -> None:
        failure = (hand, reason, error_type)
        if failure in self._reported_failures:
            return
        self._reported_failures.add(failure)
        try:
            self._logger.warning(
                "%s: reason=%s error_type=%s",
                message,
                reason,
                error_type or "none",
            )
        except Exception:
            # Diagnostics must never be able to interrupt the teleop loop.
            return


__all__ = [
    "CONTROLLER_DEVICE_PATHS",
    "HAPTIC_DURATION_OUTPUT_NAME",
    "HAPTIC_FREQUENCY_OUTPUT_NAME",
    "HAPTIC_OUTPUT_NAME",
    "XRControllerHaptics",
    "XRHapticCapability",
]
