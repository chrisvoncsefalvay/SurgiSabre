"""Table-aligned USD score panel for the SurgiSabre teleoperation mode."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral
from typing import Any, Protocol

from .scene import TABLE_TOP_Z_M

SCORE_ROOT_PATH = "/World/SurgSabreScore"
SCORE_PRESENTATION = "table_decal"
SCORE_UPDATE_POLICY = "score_events_only"
SCORE_SURFACE_OFFSET_M = 0.0008
SCORE_TEXT_OFFSET_M = 0.0002
SCORE_POSITION_W = (0.300, -0.105, TABLE_TOP_Z_M + SCORE_SURFACE_OFFSET_M)
SCORE_TILT_DEG = 0.0
SCORE_PANEL_SIZE_M = (0.255, 0.070)
SCORE_CELL_SIZE_M = 0.0028
SCORE_PANEL_OPACITY = 0.34
SCORE_TEXT_OPACITY = 0.76

PANEL_COLOUR = (0.025, 0.035, 0.16)
SUCCESS_COLOUR = (0.10, 0.76, 1.0)
FAILED_COLOUR = (0.96, 0.20, 0.66)

_GLYPHS = {
    " ": (
        "00000",
        "00000",
        "00000",
        "00000",
        "00000",
        "00000",
        "00000",
    ),
    "0": (
        "01110",
        "10001",
        "10011",
        "10101",
        "11001",
        "10001",
        "01110",
    ),
    "1": (
        "00100",
        "01100",
        "00100",
        "00100",
        "00100",
        "00100",
        "01110",
    ),
    "2": (
        "01110",
        "10001",
        "00001",
        "00010",
        "00100",
        "01000",
        "11111",
    ),
    "3": (
        "11110",
        "00001",
        "00001",
        "01110",
        "00001",
        "00001",
        "11110",
    ),
    "4": (
        "00010",
        "00110",
        "01010",
        "10010",
        "11111",
        "00010",
        "00010",
    ),
    "5": (
        "11111",
        "10000",
        "10000",
        "11110",
        "00001",
        "00001",
        "11110",
    ),
    "6": (
        "01110",
        "10000",
        "10000",
        "11110",
        "10001",
        "10001",
        "01110",
    ),
    "7": (
        "11111",
        "00001",
        "00010",
        "00100",
        "01000",
        "01000",
        "01000",
    ),
    "8": (
        "01110",
        "10001",
        "10001",
        "01110",
        "10001",
        "10001",
        "01110",
    ),
    "9": (
        "01110",
        "10001",
        "10001",
        "01111",
        "00001",
        "00001",
        "01110",
    ),
    "A": (
        "01110",
        "10001",
        "10001",
        "11111",
        "10001",
        "10001",
        "10001",
    ),
    "C": (
        "01111",
        "10000",
        "10000",
        "10000",
        "10000",
        "10000",
        "01111",
    ),
    "D": (
        "11110",
        "10001",
        "10001",
        "10001",
        "10001",
        "10001",
        "11110",
    ),
    "E": (
        "11111",
        "10000",
        "10000",
        "11110",
        "10000",
        "10000",
        "11111",
    ),
    "F": (
        "11111",
        "10000",
        "10000",
        "11110",
        "10000",
        "10000",
        "10000",
    ),
    "I": (
        "11111",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
        "11111",
    ),
    "L": (
        "10000",
        "10000",
        "10000",
        "10000",
        "10000",
        "10000",
        "11111",
    ),
    "S": (
        "01111",
        "10000",
        "10000",
        "01110",
        "00001",
        "00001",
        "11110",
    ),
    "U": (
        "10001",
        "10001",
        "10001",
        "10001",
        "10001",
        "10001",
        "01110",
    ),
}


@dataclass(frozen=True)
class ScoreIndicatorSnapshot:
    """Current aggregate outcome counts displayed in the scene."""

    successful: int
    failed: int


@dataclass(frozen=True)
class _MeshData:
    points: tuple[tuple[float, float, float], ...]
    face_vertex_counts: tuple[int, ...]
    face_vertex_indices: tuple[int, ...]


class _ScoreBackend(Protocol):
    def update(self, successful: int, failed: int) -> None: ...


def _validated_count(value: int, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} count must be an integer")
    count = int(value)
    if count < 0:
        raise ValueError(f"{name} count must be non-negative")
    return count


def _score_line(label: str, count: int) -> str:
    return f"{label} {count:03d}"


def _text_mesh_data(
    text: str,
    *,
    centre_y: float,
    cell_size_m: float = SCORE_CELL_SIZE_M,
    z_m: float = SCORE_TEXT_OFFSET_M,
) -> _MeshData:
    """Convert an embedded 5x7 bitmap string into table-aligned quads."""
    normalised = text.upper()
    unsupported = sorted(set(normalised) - set(_GLYPHS))
    if unsupported:
        raise ValueError(f"unsupported score glyphs: {''.join(unsupported)}")
    if cell_size_m <= 0.0:
        raise ValueError("score glyph cell size must be positive")

    width_cells = max(0, len(normalised) * 6 - 1)
    left_m = -0.5 * width_cells * cell_size_m
    bottom_m = centre_y - 3.5 * cell_size_m
    points: list[tuple[float, float, float]] = []
    indices: list[int] = []
    for glyph_index, glyph in enumerate(normalised):
        for row_index, row in enumerate(_GLYPHS[glyph]):
            for column_index, enabled in enumerate(row):
                if enabled != "1":
                    continue
                x0 = left_m + (glyph_index * 6 + column_index) * cell_size_m
                x1 = x0 + cell_size_m * 0.82
                y1 = bottom_m + (7 - row_index) * cell_size_m
                y0 = y1 - cell_size_m * 0.82
                offset = len(points)
                points.extend(
                    (
                        (x0, y0, z_m),
                        (x1, y0, z_m),
                        (x1, y1, z_m),
                        (x0, y1, z_m),
                    )
                )
                indices.extend((offset, offset + 1, offset + 2, offset + 3))
    return _MeshData(
        points=tuple(points),
        face_vertex_counts=(4,) * (len(points) // 4),
        face_vertex_indices=tuple(indices),
    )


def _panel_mesh_data() -> _MeshData:
    half_width = SCORE_PANEL_SIZE_M[0] * 0.5
    half_height = SCORE_PANEL_SIZE_M[1] * 0.5
    return _MeshData(
        points=(
            (-half_width, -half_height, 0.0),
            (half_width, -half_height, 0.0),
            (half_width, half_height, 0.0),
            (-half_width, half_height, 0.0),
        ),
        face_vertex_counts=(4,),
        face_vertex_indices=(0, 1, 2, 3),
    )


def _resolve_stage(stage: Any | None) -> Any:
    if stage is not None:
        return stage
    import omni.usd

    resolved = omni.usd.get_context().get_stage()
    if resolved is None:
        raise RuntimeError("Surg Sabre score indicator requires an open USD stage")
    return resolved


class _UsdScoreBackend:
    def __init__(
        self,
        stage: Any,
        *,
        root_path: str,
        position_w: tuple[float, float, float],
    ) -> None:
        from pxr import Gf, Sdf, UsdGeom

        self._Gf = Gf
        self._Sdf = Sdf
        self._UsdGeom = UsdGeom
        self._root_path = root_path.rstrip("/")
        root = UsdGeom.Xform.Define(stage, self._root_path)
        xform = UsdGeom.Xformable(root.GetPrim())
        xform.ClearXformOpOrder()
        xform.AddTranslateOp().Set(Gf.Vec3d(*position_w))

        material_scope = f"{self._root_path}/Materials"
        UsdGeom.Scope.Define(stage, material_scope)
        panel_material = self._define_material(
            stage,
            f"{material_scope}/Panel",
            PANEL_COLOUR,
            SCORE_PANEL_OPACITY,
        )
        success_material = self._define_material(
            stage,
            f"{material_scope}/Successful",
            SUCCESS_COLOUR,
            SCORE_TEXT_OPACITY,
        )
        failed_material = self._define_material(
            stage,
            f"{material_scope}/Failed",
            FAILED_COLOUR,
            SCORE_TEXT_OPACITY,
        )
        self._panel_mesh = self._define_mesh(
            stage,
            f"{self._root_path}/Panel",
            _panel_mesh_data(),
            panel_material,
        )
        self._success_mesh = self._define_mesh(
            stage,
            f"{self._root_path}/Successful",
            _text_mesh_data(_score_line("SUCCESS", 0), centre_y=0.016),
            success_material,
        )
        self._failed_mesh = self._define_mesh(
            stage,
            f"{self._root_path}/Failed",
            _text_mesh_data(_score_line("FAILED", 0), centre_y=-0.016),
            failed_material,
        )
        root_prim = root.GetPrim()
        self._successful_attr = root_prim.CreateAttribute(
            "surgisabre:successful",
            Sdf.ValueTypeNames.Int,
            custom=True,
        )
        self._failed_attr = root_prim.CreateAttribute(
            "surgisabre:failed",
            Sdf.ValueTypeNames.Int,
            custom=True,
        )
        root_prim.CreateAttribute(
            "surgisabre:label",
            Sdf.ValueTypeNames.String,
            custom=True,
        ).Set("Surg Sabre score")

    @staticmethod
    def _define_material(
        stage: Any,
        path: str,
        colour: tuple[float, float, float],
        opacity: float,
    ) -> Any:
        from pxr import Gf, Sdf, UsdShade

        material = UsdShade.Material.Define(stage, path)
        shader = UsdShade.Shader.Define(stage, f"{path}/PreviewSurface")
        shader.CreateIdAttr("UsdPreviewSurface")
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
            Gf.Vec3f(*colour)
        )
        shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(opacity)
        shader.CreateInput("opacityThreshold", Sdf.ValueTypeNames.Float).Set(0.0)
        shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.48)
        shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
        output = material.CreateSurfaceOutput()
        output.ClearSources()
        output.ConnectToSource(shader.ConnectableAPI(), "surface")
        return material

    def _define_mesh(
        self,
        stage: Any,
        path: str,
        data: _MeshData,
        material: Any,
    ) -> Any:
        from pxr import UsdGeom, UsdShade

        mesh = UsdGeom.Mesh.Define(stage, path)
        mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
        mesh.CreateDoubleSidedAttr(True)
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)
        self._set_mesh_data(mesh, data)
        return mesh

    def _set_mesh_data(self, mesh: Any, data: _MeshData) -> None:
        points = [self._Gf.Vec3f(*point) for point in data.points]
        mesh.CreatePointsAttr().Set(points)
        mesh.CreateFaceVertexCountsAttr().Set(list(data.face_vertex_counts))
        mesh.CreateFaceVertexIndicesAttr().Set(list(data.face_vertex_indices))

    def update(self, successful: int, failed: int) -> None:
        self._set_mesh_data(
            self._success_mesh,
            _text_mesh_data(_score_line("SUCCESS", successful), centre_y=0.016),
        )
        self._set_mesh_data(
            self._failed_mesh,
            _text_mesh_data(_score_line("FAILED", failed), centre_y=-0.016),
        )
        self._successful_attr.Set(successful)
        self._failed_attr.Set(failed)


class IsaacSabreScoreIndicator:
    """Author and update a semitransparent side-mounted score panel."""

    def __init__(
        self,
        stage: Any | None = None,
        *,
        root_path: str = SCORE_ROOT_PATH,
        position_w: tuple[float, float, float] = SCORE_POSITION_W,
        successful: int = 0,
        failed: int = 0,
        backend: _ScoreBackend | None = None,
    ) -> None:
        if not root_path.startswith("/"):
            raise ValueError("score root path must be absolute")
        if len(position_w) != 3:
            raise ValueError("score position must contain exactly three coordinates")
        self.root_path = root_path.rstrip("/")
        self.position_w = tuple(float(value) for value in position_w)
        self._backend = backend or _UsdScoreBackend(
            _resolve_stage(stage),
            root_path=self.root_path,
            position_w=self.position_w,
        )
        self._snapshot = ScoreIndicatorSnapshot(successful=0, failed=0)
        self.update(successful, failed)

    @property
    def successful(self) -> int:
        return self._snapshot.successful

    @property
    def failed(self) -> int:
        return self._snapshot.failed

    def update(self, successful: int, failed: int) -> ScoreIndicatorSnapshot:
        """Display exact aggregate counts and return their immutable snapshot."""
        successful_count = _validated_count(successful, name="successful")
        failed_count = _validated_count(failed, name="failed")
        self._backend.update(successful_count, failed_count)
        self._snapshot = ScoreIndicatorSnapshot(
            successful=successful_count,
            failed=failed_count,
        )
        return self._snapshot

    def reset(self) -> ScoreIndicatorSnapshot:
        """Reset both displayed outcome counts to zero."""
        return self.update(0, 0)

    def report(self) -> dict[str, Any]:
        """Return the authored visual contract for runtime evidence."""
        return {
            "root_path": self.root_path,
            "presentation": SCORE_PRESENTATION,
            "update_policy": SCORE_UPDATE_POLICY,
            "position_w": list(self.position_w),
            "tilt_deg": SCORE_TILT_DEG,
            "panel_opacity": SCORE_PANEL_OPACITY,
            "text_opacity": SCORE_TEXT_OPACITY,
            "successful": self.successful,
            "failed": self.failed,
        }


__all__ = [
    "FAILED_COLOUR",
    "PANEL_COLOUR",
    "SCORE_CELL_SIZE_M",
    "SCORE_PANEL_OPACITY",
    "SCORE_PANEL_SIZE_M",
    "SCORE_POSITION_W",
    "SCORE_PRESENTATION",
    "SCORE_ROOT_PATH",
    "SCORE_SURFACE_OFFSET_M",
    "SCORE_TEXT_OFFSET_M",
    "SCORE_TEXT_OPACITY",
    "SCORE_TILT_DEG",
    "SCORE_UPDATE_POLICY",
    "SUCCESS_COLOUR",
    "IsaacSabreScoreIndicator",
    "ScoreIndicatorSnapshot",
]
