"""Visual-only USD dressing for the SurgiSabre arena."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .layout import SHAFT_INTERSECTION_Z_M, SUTURE_PAD_ROOT_POS

PAD_PATH = "/World/envs/env_0/SuturePad"
TABLE_PATH = "/World/EditableTable"
MATERIALS_SCOPE_PATH = "/World/SurgiSabreMaterials"
PAD_MATERIAL_PATH = f"{MATERIALS_SCOPE_PATH}/SuturePad"
TABLE_MATERIAL_PATH = f"{MATERIALS_SCOPE_PATH}/Table"

TABLE_TOP_Z_M = SUTURE_PAD_ROOT_POS[2]
SHAFT_INTERSECTION_M = (0.0, 0.004618802, SHAFT_INTERSECTION_Z_M)
TABLE_COLOUR = (0.94, 0.94, 0.94)
PAD_COLOUR = (0.20, 0.31, 0.39)

DOME_LIGHT_PATH = "/World/Light"
SIDE_KEY_LIGHT_PATH = "/World/DramaticSideKey"
SIDE_RIM_LIGHT_PATH = "/World/DramaticCoolRim"
DARK_DOME_COLOUR = (0.008, 0.006, 0.025)
DARK_DOME_INTENSITY = 35.0
DEFAULT_SIDE_KEY_COLOUR = (1.0, 0.66, 0.42)
DEFAULT_SIDE_RIM_COLOUR = (0.28, 0.46, 1.0)
DEFAULT_SIDE_KEY_INTENSITY = 3800.0
DEFAULT_SIDE_RIM_INTENSITY = 2600.0
HIT_DOMINANT_LIGHT_INTENSITY = 5200.0
HIT_FILL_LIGHT_INTENSITY = 1900.0
HIT_LIGHT_COLOUR_CYCLE = (
    (0.059, 0.373, 0.863),
    (0.10, 0.76, 1.0),
    (0.38, 0.10, 1.0),
    (0.67, 0.08, 0.96),
    (0.96, 0.20, 0.66),
    (0.92, 0.31, 0.54),
)

SCENE_DRESSING_PATHS = (
    TABLE_PATH,
    PAD_PATH,
    DOME_LIGHT_PATH,
    "/World/KeyLight",
    SIDE_KEY_LIGHT_PATH,
    SIDE_RIM_LIGHT_PATH,
)

@dataclass(frozen=True)
class HitLightingState:
    """One side-light state selected by an accepted hit."""

    hit_index: int
    hand: str | None
    side_key_colour: tuple[float, float, float]
    side_rim_colour: tuple[float, float, float]
    side_key_intensity: float
    side_rim_intensity: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "hit_index": self.hit_index,
            "hand": self.hand,
            "side_key_colour": list(self.side_key_colour),
            "side_rim_colour": list(self.side_rim_colour),
            "side_key_intensity": self.side_key_intensity,
            "side_rim_intensity": self.side_rim_intensity,
        }


class _HitLightingBackend(Protocol):
    def apply(self, state: HitLightingState) -> None: ...


def _initial_hit_lighting_state() -> HitLightingState:
    return HitLightingState(
        hit_index=0,
        hand=None,
        side_key_colour=DEFAULT_SIDE_KEY_COLOUR,
        side_rim_colour=DEFAULT_SIDE_RIM_COLOUR,
        side_key_intensity=DEFAULT_SIDE_KEY_INTENSITY,
        side_rim_intensity=DEFAULT_SIDE_RIM_INTENSITY,
    )


def hit_lighting_state(hit_index: int, hand: str) -> HitLightingState:
    """Select a deterministic dramatic lighting state for one accepted hit."""

    if isinstance(hit_index, bool) or not isinstance(hit_index, int) or hit_index < 1:
        raise ValueError("hit index must be a positive integer")
    if hand not in {"left", "right"}:
        raise ValueError("hit hand must be left or right")
    colour_index = (hit_index - 1) % len(HIT_LIGHT_COLOUR_CYCLE)
    opposite_index = (colour_index + len(HIT_LIGHT_COLOUR_CYCLE) // 2) % len(
        HIT_LIGHT_COLOUR_CYCLE
    )
    return HitLightingState(
        hit_index=hit_index,
        hand=hand,
        side_key_colour=HIT_LIGHT_COLOUR_CYCLE[colour_index],
        side_rim_colour=HIT_LIGHT_COLOUR_CYCLE[opposite_index],
        side_key_intensity=(
            HIT_DOMINANT_LIGHT_INTENSITY
            if hand == "left"
            else HIT_FILL_LIGHT_INTENSITY
        ),
        side_rim_intensity=(
            HIT_FILL_LIGHT_INTENSITY
            if hand == "left"
            else HIT_DOMINANT_LIGHT_INTENSITY
        ),
    )


def _resolve_stage(stage: Any | None) -> Any:
    if stage is not None:
        return stage
    import omni.usd

    resolved = omni.usd.get_context().get_stage()
    if resolved is None:
        raise RuntimeError("hit-reactive lighting requires an open USD stage")
    return resolved


class _UsdHitLightingBackend:
    def __init__(self, stage: Any) -> None:
        from pxr import UsdLux

        key_prim = stage.GetPrimAtPath(SIDE_KEY_LIGHT_PATH)
        rim_prim = stage.GetPrimAtPath(SIDE_RIM_LIGHT_PATH)
        if not key_prim or not rim_prim:
            raise RuntimeError("hit-reactive lighting requires both side lights")
        self._key = UsdLux.RectLight(key_prim)
        self._rim = UsdLux.RectLight(rim_prim)
        if not self._key or not self._rim:
            raise RuntimeError("hit-reactive lighting requires two RectLight prims")

    def apply(self, state: HitLightingState) -> None:
        from pxr import Gf

        self._key.GetColorAttr().Set(Gf.Vec3f(*state.side_key_colour))
        self._key.GetIntensityAttr().Set(state.side_key_intensity)
        self._rim.GetColorAttr().Set(Gf.Vec3f(*state.side_rim_colour))
        self._rim.GetIntensityAttr().Set(state.side_rim_intensity)


class IsaacSabreHitLighting:
    """Apply event-only side-light changes for accepted target hits."""

    def __init__(
        self,
        stage: Any | None = None,
        *,
        backend: _HitLightingBackend | None = None,
    ) -> None:
        self._backend = backend or _UsdHitLightingBackend(_resolve_stage(stage))
        self._state = _initial_hit_lighting_state()
        self._backend.apply(self._state)

    @property
    def state(self) -> HitLightingState:
        return self._state

    def register_hit(self, hand: str) -> HitLightingState:
        state = hit_lighting_state(self._state.hit_index + 1, hand)
        self._backend.apply(state)
        self._state = state
        return state

    def reset(self) -> HitLightingState:
        state = _initial_hit_lighting_state()
        self._backend.apply(state)
        self._state = state
        return state

    def report(self) -> dict[str, Any]:
        return {
            "update_policy": "accepted_instrument_hits_only",
            "side_key_path": SIDE_KEY_LIGHT_PATH,
            "side_rim_path": SIDE_RIM_LIGHT_PATH,
            "dominant_intensity": HIT_DOMINANT_LIGHT_INTENSITY,
            "fill_intensity": HIT_FILL_LIGHT_INTENSITY,
            "colour_cycle": [list(colour) for colour in HIT_LIGHT_COLOUR_CYCLE],
            "state": self._state.to_dict(),
        }


def _look_at_matrix(
    eye_values: tuple[float, float, float],
    target_values: tuple[float, float, float],
) -> Any:
    from pxr import Gf

    eye = Gf.Vec3d(*eye_values)
    target = Gf.Vec3d(*target_values)
    up = Gf.Vec3d(0.0, 0.0, 1.0)
    forward = (target - eye).GetNormalized()
    if abs(forward * up) > 0.99:
        up = Gf.Vec3d(0.0, 1.0, 0.0)
    right = Gf.Cross(forward, up).GetNormalized()
    light_up = Gf.Cross(right, forward).GetNormalized()
    return Gf.Matrix4d(
        right[0], right[1], right[2], 0.0,
        light_up[0], light_up[1], light_up[2], 0.0,
        -forward[0], -forward[1], -forward[2], 0.0,
        eye[0], eye[1], eye[2], 1.0,
    )


def _define_material(
    stage: Any,
    path: str,
    colour: tuple[float, float, float],
    *,
    metallic: float,
    roughness: float,
) -> Any:
    from pxr import Gf, Sdf, UsdShade

    material = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/PreviewSurface")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
        Gf.Vec3f(*colour)
    )
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(metallic)
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
    output = material.CreateSurfaceOutput()
    output.ClearSources()
    output.ConnectToSource(shader.ConnectableAPI(), "surface")
    return material


def _ensure_lighting(stage: Any) -> None:
    from pxr import Gf, Sdf, UsdGeom, UsdLux

    dome = UsdLux.DomeLight.Define(stage, DOME_LIGHT_PATH)
    dome.CreateIntensityAttr(DARK_DOME_INTENSITY)
    dome.CreateColorAttr(Gf.Vec3f(*DARK_DOME_COLOUR))
    dome.CreateTextureFileAttr().Set(Sdf.AssetPath(""))

    key = UsdLux.DistantLight.Define(stage, "/World/KeyLight")
    key.CreateIntensityAttr(180.0)
    key.CreateColorAttr(Gf.Vec3f(1.0, 0.96, 0.90))
    key.CreateAngleAttr(3.0)
    key_xform = UsdGeom.Xformable(key.GetPrim())
    key_xform.ClearXformOpOrder()
    key_xform.AddRotateXYZOp().Set(Gf.Vec3f(-45.0, 25.0, 20.0))

    side_key = UsdLux.RectLight.Define(stage, SIDE_KEY_LIGHT_PATH)
    side_key.CreateIntensityAttr(DEFAULT_SIDE_KEY_INTENSITY)
    side_key.CreateColorAttr(Gf.Vec3f(*DEFAULT_SIDE_KEY_COLOUR))
    side_key.CreateWidthAttr(0.30)
    side_key.CreateHeightAttr(0.42)
    side_key_xform = UsdGeom.Xformable(side_key.GetPrim())
    side_key_xform.ClearXformOpOrder()
    side_key_xform.MakeMatrixXform().Set(
        _look_at_matrix((-0.38, -0.03, 0.30), SHAFT_INTERSECTION_M)
    )

    rim = UsdLux.RectLight.Define(stage, SIDE_RIM_LIGHT_PATH)
    rim.CreateIntensityAttr(DEFAULT_SIDE_RIM_INTENSITY)
    rim.CreateColorAttr(Gf.Vec3f(*DEFAULT_SIDE_RIM_COLOUR))
    rim.CreateWidthAttr(0.20)
    rim.CreateHeightAttr(0.36)
    rim_xform = UsdGeom.Xformable(rim.GetPrim())
    rim_xform.ClearXformOpOrder()
    rim_xform.MakeMatrixXform().Set(
        _look_at_matrix((0.34, 0.12, 0.24), SHAFT_INTERSECTION_M)
    )


def _add_editable_table(stage: Any, table_material: Any) -> None:
    from pxr import Gf, UsdGeom, UsdShade

    table = UsdGeom.Cube.Define(stage, TABLE_PATH)
    table.CreateSizeAttr(1.0)
    xform = UsdGeom.Xformable(table.GetPrim())
    xform.ClearXformOpOrder()
    xform.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.075, TABLE_TOP_Z_M - 0.018))
    xform.AddScaleOp().Set(Gf.Vec3f(0.90, 0.62, 0.036))
    UsdShade.MaterialBindingAPI.Apply(table.GetPrim()).Bind(table_material)


def apply_scene_dressing(
    stage: Any | None = None,
    *,
    include_suture_pad: bool = False,
    pad_path: str = PAD_PATH,
) -> dict[str, Any]:
    """Apply the dark arena, plain table and event-reactive lights."""

    if stage is None:
        import omni.usd

        stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("live scene dressing requires an open USD stage")

    from pxr import UsdGeom, UsdShade

    pad_prim = stage.GetPrimAtPath(pad_path) if include_suture_pad else None
    if include_suture_pad and not pad_prim:
        raise RuntimeError(f"live scene dressing could not find the suture pad: {pad_path}")

    UsdGeom.Scope.Define(stage, MATERIALS_SCOPE_PATH)
    table_material = _define_material(
        stage, TABLE_MATERIAL_PATH, TABLE_COLOUR, metallic=0.02, roughness=0.76
    )
    pad_material = None
    if include_suture_pad:
        pad_material = _define_material(
            stage, PAD_MATERIAL_PATH, PAD_COLOUR, metallic=0.08, roughness=0.58
        )

    _ensure_lighting(stage)
    _add_editable_table(stage, table_material)
    if include_suture_pad:
        UsdShade.MaterialBindingAPI.Apply(pad_prim).Bind(
            pad_material, UsdShade.Tokens.strongerThanDescendants
        )
    dressing_paths = [
        pad_path if path == PAD_PATH else path
        for path in SCENE_DRESSING_PATHS
        if include_suture_pad or path != PAD_PATH
    ]
    return {
        "paths": dressing_paths,
        "suture_pad_included": include_suture_pad,
        "environment": {
            "type": "DomeLight",
            "path": DOME_LIGHT_PATH,
            "colour": list(DARK_DOME_COLOUR),
            "intensity": DARK_DOME_INTENSITY,
            "texture": None,
            "immersive_mode": "vr",
        },
        "hit_lighting": {
            "update_policy": "accepted_instrument_hits_only",
            "side_key_path": SIDE_KEY_LIGHT_PATH,
            "side_rim_path": SIDE_RIM_LIGHT_PATH,
            "dominant_intensity": HIT_DOMINANT_LIGHT_INTENSITY,
            "fill_intensity": HIT_FILL_LIGHT_INTENSITY,
            "colour_cycle": [list(colour) for colour in HIT_LIGHT_COLOUR_CYCLE],
            "state": _initial_hit_lighting_state().to_dict(),
        },
        "pad_material_binding_strength": (
            "strongerThanDescendants" if include_suture_pad else None
        ),
    }


__all__ = [
    "DARK_DOME_COLOUR",
    "DARK_DOME_INTENSITY",
    "DOME_LIGHT_PATH",
    "HIT_DOMINANT_LIGHT_INTENSITY",
    "HIT_FILL_LIGHT_INTENSITY",
    "HIT_LIGHT_COLOUR_CYCLE",
    "PAD_COLOUR",
    "PAD_PATH",
    "SCENE_DRESSING_PATHS",
    "SHAFT_INTERSECTION_M",
    "SIDE_KEY_LIGHT_PATH",
    "SIDE_RIM_LIGHT_PATH",
    "TABLE_COLOUR",
    "TABLE_PATH",
    "TABLE_TOP_Z_M",
    "HitLightingState",
    "IsaacSabreHitLighting",
    "apply_scene_dressing",
    "hit_lighting_state",
]
