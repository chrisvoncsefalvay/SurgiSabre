import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import surgisabre.runtime as instrumentation_module  # noqa: E402
from surgisabre.runtime import (  # noqa: E402
    IsaacLabEvidenceInstrumentation,
)
from surgisabre.scene import (  # noqa: E402
    DARK_DOME_COLOUR,
    DARK_DOME_INTENSITY,
    DOME_LIGHT_PATH,
    HIT_DOMINANT_LIGHT_INTENSITY,
    HIT_FILL_LIGHT_INTENSITY,
    HIT_LIGHT_COLOUR_CYCLE,
    PAD_COLOUR,
    SCENE_DRESSING_PATHS,
    SIDE_KEY_LIGHT_PATH,
    SIDE_RIM_LIGHT_PATH,
    TABLE_COLOUR,
    IsaacSabreHitLighting,
    _ensure_lighting,
    hit_lighting_state,
)


def test_scene_dressing_contract_contains_no_camera_or_xr_paths() -> None:
    assert TABLE_COLOUR == (0.94, 0.94, 0.94)
    assert PAD_COLOUR == (0.20, 0.31, 0.39)
    assert not any("Camera" in path or "XR" in path for path in SCENE_DRESSING_PATHS)


def test_dark_dome_and_hit_palette_are_explicit_scene_contracts() -> None:
    assert DOME_LIGHT_PATH in SCENE_DRESSING_PATHS
    assert SIDE_KEY_LIGHT_PATH in SCENE_DRESSING_PATHS
    assert SIDE_RIM_LIGHT_PATH in SCENE_DRESSING_PATHS
    assert DARK_DOME_COLOUR == (0.008, 0.006, 0.025)
    assert DARK_DOME_INTENSITY == 35.0
    assert len(HIT_LIGHT_COLOUR_CYCLE) == 6
    assert len(set(HIT_LIGHT_COLOUR_CYCLE)) == 6
    assert all(
        0.0 <= component <= 1.0
        for colour in HIT_LIGHT_COLOUR_CYCLE
        for component in colour
    )


def test_accepted_hits_deterministically_cycle_and_swap_dominant_side() -> None:
    class Backend:
        def __init__(self):
            self.states = []

        def apply(self, state):
            self.states.append(state)

    backend = Backend()
    lighting = IsaacSabreHitLighting(backend=backend)

    left_hit = lighting.register_hit("left")
    right_hit = lighting.register_hit("right")

    assert len(backend.states) == 3
    assert left_hit == hit_lighting_state(1, "left")
    assert right_hit == hit_lighting_state(2, "right")
    assert left_hit.side_key_intensity == HIT_DOMINANT_LIGHT_INTENSITY
    assert left_hit.side_rim_intensity == HIT_FILL_LIGHT_INTENSITY
    assert right_hit.side_key_intensity == HIT_FILL_LIGHT_INTENSITY
    assert right_hit.side_rim_intensity == HIT_DOMINANT_LIGHT_INTENSITY
    assert hit_lighting_state(7, "left").side_key_colour == (
        left_hit.side_key_colour
    )
    assert lighting.report()["update_policy"] == "accepted_instrument_hits_only"

    reset_state = lighting.reset()

    assert reset_state.hit_index == 0
    assert reset_state.hand is None
    assert len(backend.states) == 4


def test_dark_dome_and_hit_updates_author_on_an_in_memory_usd_stage() -> None:
    pytest.importorskip("pxr")
    from pxr import Usd, UsdGeom

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")

    _ensure_lighting(stage)
    dome = stage.GetPrimAtPath(DOME_LIGHT_PATH)
    lighting = IsaacSabreHitLighting(stage)
    left_hit = lighting.register_hit("left")

    assert dome.GetTypeName() == "DomeLight"
    assert tuple(dome.GetAttribute("inputs:color").Get()) == pytest.approx(
        DARK_DOME_COLOUR
    )
    assert dome.GetAttribute("inputs:intensity").Get() == DARK_DOME_INTENSITY
    assert dome.GetAttribute("inputs:texture:file").Get().path == ""
    assert (
        stage.GetPrimAtPath(SIDE_KEY_LIGHT_PATH)
        .GetAttribute("inputs:intensity")
        .Get()
        == HIT_DOMINANT_LIGHT_INTENSITY
    )
    assert (
        stage.GetPrimAtPath(SIDE_RIM_LIGHT_PATH)
        .GetAttribute("inputs:intensity")
        .Get()
        == left_hit.side_rim_intensity
    )


def test_live_scene_dressing_runs_after_environment_creation(monkeypatch) -> None:
    events = []
    environment = SimpleNamespace()
    made_environment = SimpleNamespace(unwrapped=environment)

    def make_environment():
        events.append("make")
        return made_environment

    report = {"paths": list(SCENE_DRESSING_PATHS)}
    monkeypatch.setattr(
        instrumentation_module,
        "apply_scene_dressing",
        lambda **kwargs: events.append(("dress", kwargs)) or report,
    )
    runner_module = SimpleNamespace(
        parse_env_cfg=lambda: SimpleNamespace(),
        gym=SimpleNamespace(make=make_environment),
        create_teleop_device=lambda *_args, **_kwargs: None,
        logger=SimpleNamespace(error=lambda *_args, **_kwargs: None),
    )
    instrumentation = IsaacLabEvidenceInstrumentation(
        SimpleNamespace(),
        xr_enabled=True,
        pure_teleop=False,
        live_scene_dressing=True,
    )
    instrumentation._instrument_environment = lambda env: events.append(
        "instrument" if env is environment else "wrong_environment"
    )

    instrumentation.install(runner_module)
    result = runner_module.gym.make()

    assert result is made_environment
    assert events == [
        "make",
        "instrument",
        ("dress", {"include_suture_pad": True}),
    ]
    assert instrumentation.scene_report == report


def test_pure_teleop_runtime_evidence_includes_the_dark_scene_contract(
    monkeypatch,
) -> None:
    environment = SimpleNamespace()
    made_environment = SimpleNamespace(unwrapped=environment)
    scene_report = {
        "environment": {"type": "DomeLight", "immersive_mode": "vr"},
        "hit_lighting": {"update_policy": "accepted_instrument_hits_only"},
    }

    class BrickGame:
        def __init__(self, *_args, **_kwargs):
            pass

        def runtime_report(self):
            return {"targets": 6}

    class ScoreIndicator:
        def __init__(self, *_args, **_kwargs):
            pass

        def report(self):
            return {"presentation": "table_decal"}

    class HitLighting:
        def __init__(self, *_args, **_kwargs):
            pass

        def report(self):
            return scene_report["hit_lighting"]

    monkeypatch.setattr(
        instrumentation_module,
        "_validate_pure_teleop_runtime",
        lambda _env: {"layout": "validated"},
    )
    monkeypatch.setattr(instrumentation_module, "XRControllerHaptics", lambda: object())
    monkeypatch.setattr(instrumentation_module, "IsaacSabreBrickAdapter", BrickGame)
    monkeypatch.setattr(instrumentation_module, "IsaacSabreScoreIndicator", ScoreIndicator)
    monkeypatch.setattr(instrumentation_module, "IsaacSabreHitLighting", HitLighting)
    monkeypatch.setattr(
        instrumentation_module,
        "apply_scene_dressing",
        lambda **_kwargs: scene_report,
    )
    runner_module = SimpleNamespace(
        parse_env_cfg=lambda: SimpleNamespace(),
        gym=SimpleNamespace(make=lambda: made_environment),
        create_teleop_device=lambda *_args, **_kwargs: None,
        logger=SimpleNamespace(error=lambda *_args, **_kwargs: None),
    )
    instrumentation = IsaacLabEvidenceInstrumentation(
        SimpleNamespace(session_id="dark-arena-test"),
        xr_enabled=True,
        pure_teleop=True,
        live_scene_dressing=True,
    )
    instrumentation._instrument_environment = lambda _env: None

    instrumentation.install(runner_module)
    runner_module.gym.make()

    assert instrumentation.pure_teleop_runtime_report is not None
    assert instrumentation.pure_teleop_runtime_report["scene_dressing"] == scene_report
