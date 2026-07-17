import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from surgisabre.isaac_score import (  # noqa: E402
    FAILED_COLOUR,
    PANEL_COLOUR,
    SCORE_PANEL_OPACITY,
    SCORE_PANEL_SIZE_M,
    SCORE_POSITION_W,
    SCORE_PRESENTATION,
    SCORE_ROOT_PATH,
    SCORE_SURFACE_OFFSET_M,
    SCORE_TEXT_OFFSET_M,
    SCORE_TEXT_OPACITY,
    SCORE_TILT_DEG,
    SCORE_UPDATE_POLICY,
    SUCCESS_COLOUR,
    IsaacSabreScoreIndicator,
    ScoreIndicatorSnapshot,
    _panel_mesh_data,
    _score_line,
    _text_mesh_data,
)
from surgisabre.scene import TABLE_TOP_Z_M  # noqa: E402


class _RecordingBackend:
    def __init__(self) -> None:
        self.updates = []

    def update(self, successful: int, failed: int) -> None:
        self.updates.append((successful, failed))


def test_module_imports_when_pxr_is_unavailable() -> None:
    code = """
import builtins
original_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name == 'pxr' or name.startswith('pxr.'):
        raise AssertionError('pxr was imported at module load time')
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
import surgisabre.isaac_score
"""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(REPO_ROOT / "src")

    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr


def test_indicator_updates_and_resets_exact_aggregate_counts() -> None:
    backend = _RecordingBackend()
    indicator = IsaacSabreScoreIndicator(backend=backend)

    assert backend.updates == [(0, 0)]
    assert indicator.update(12, 7) == ScoreIndicatorSnapshot(successful=12, failed=7)
    assert indicator.successful == 12
    assert indicator.failed == 7
    assert indicator.reset() == ScoreIndicatorSnapshot(successful=0, failed=0)
    assert backend.updates == [(0, 0), (12, 7), (0, 0)]


@pytest.mark.parametrize(
    ("successful", "failed", "error"),
    (
        (-1, 0, ValueError),
        (0, -1, ValueError),
        (1.5, 0, TypeError),
        (0, True, TypeError),
    ),
)
def test_indicator_rejects_invalid_counts(successful, failed, error) -> None:
    indicator = IsaacSabreScoreIndicator(backend=_RecordingBackend())

    with pytest.raises(error):
        indicator.update(successful, failed)


def test_score_lines_keep_at_least_three_digits_without_truncation() -> None:
    assert _score_line("SUCCESS", 2) == "SUCCESS 002"
    assert _score_line("FAILED", 1234) == "FAILED 1234"


def test_embedded_bitmap_font_authors_quad_only_meshes() -> None:
    mesh = _text_mesh_data("SUCCESS 0123456789", centre_y=0.0)

    assert mesh.points
    assert len(mesh.points) % 4 == 0
    assert mesh.face_vertex_counts == (4,) * (len(mesh.points) // 4)
    assert mesh.face_vertex_indices == tuple(range(len(mesh.points)))
    assert all(point[2] == SCORE_TEXT_OFFSET_M for point in mesh.points)


def test_panel_and_palette_match_the_table_decal_visual_contract() -> None:
    panel = _panel_mesh_data()
    indicator = IsaacSabreScoreIndicator(backend=_RecordingBackend())

    assert SCORE_ROOT_PATH == "/World/SurgSabreScore"
    assert SCORE_PRESENTATION == "table_decal"
    assert SCORE_UPDATE_POLICY == "score_events_only"
    assert SCORE_POSITION_W == (0.300, -0.105, TABLE_TOP_Z_M + 0.0008)
    assert SCORE_POSITION_W[2] == pytest.approx(TABLE_TOP_Z_M + SCORE_SURFACE_OFFSET_M)
    assert SCORE_TILT_DEG == 0.0
    assert SCORE_PANEL_SIZE_M == (0.255, 0.070)
    assert 0.0 < SCORE_PANEL_OPACITY < SCORE_TEXT_OPACITY < 1.0
    assert PANEL_COLOUR == (0.025, 0.035, 0.16)
    assert SUCCESS_COLOUR == (0.10, 0.76, 1.0)
    assert FAILED_COLOUR == (0.96, 0.20, 0.66)
    assert panel.face_vertex_counts == (4,)
    assert all(point[2] == 0.0 for point in panel.points)
    panel_world_x = [SCORE_POSITION_W[0] + point[0] for point in panel.points]
    panel_world_y = [SCORE_POSITION_W[1] + point[1] for point in panel.points]
    assert min(panel_world_x) > 0.15
    assert max(panel_world_x) <= 0.45
    assert min(panel_world_y) >= -0.235
    assert max(panel_world_y) <= 0.385
    assert indicator.report() == {
        "root_path": SCORE_ROOT_PATH,
        "presentation": SCORE_PRESENTATION,
        "update_policy": SCORE_UPDATE_POLICY,
        "position_w": list(SCORE_POSITION_W),
        "tilt_deg": SCORE_TILT_DEG,
        "panel_opacity": SCORE_PANEL_OPACITY,
        "text_opacity": SCORE_TEXT_OPACITY,
        "successful": 0,
        "failed": 0,
    }
