# FILE: tests/test_build.py
import json

from build import build
from extract.schema import ModelObject
from model_fixtures import box_mesh, cylinder_mesh, mk, sample_model, write_model_json


def _report(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_clean_model_is_exported_to_out_dir_only(tmp_path):
    model_json = write_model_json(sample_model(), tmp_path / "model.json")
    out, rej = tmp_path / "out", tmp_path / "rej"
    r = build(model_json, out, rej, "plan")
    assert r.ok and r.violations == []
    assert (out / "plan.png").exists() and (out / "plan.report.json").exists()
    assert not rej.exists() or not any(rej.iterdir())
    data = _report(out / "plan.report.json")
    assert data["ok"] is True
    assert {"TAG", "G1", "G2", "G4", "G5", "T1", "T2", "T3", "T4"} <= set(data["checks_run"])


def test_model_with_violation_goes_to_rejected_with_report(tmp_path):
    m = sample_model()
    m.objects.append(mk("Col_bad", "column", "기둥 오류", cylinder_mesh(14.5, 9.0, 0.45, 0, 4.5)))
    model_json = write_model_json(m, tmp_path / "model.json")
    out, rej = tmp_path / "out", tmp_path / "rej"
    r = build(model_json, out, rej, "plan")
    assert not r.ok
    assert not (out / "plan.png").exists()
    assert (rej / "plan.png").exists() and (rej / "plan.report.json").exists()
    data = _report(rej / "plan.report.json")
    assert data["ok"] is False
    assert any(v["check"] == "G1" for v in data["violations"])


def test_untagged_object_is_rejected_without_rendering(tmp_path):
    m = sample_model()
    verts, tris = box_mesh(0, 0, 1, 1, 0, 1)
    m.objects.append(ModelObject("Untagged", {}, verts, tris))
    model_json = write_model_json(m, tmp_path / "model.json")
    out, rej = tmp_path / "out", tmp_path / "rej"
    r = build(model_json, out, rej, "plan")
    assert not r.ok and r.png_path is None
    assert not (rej / "plan.png").exists()
    data = _report(rej / "plan.report.json")
    assert data["checks_run"] == ["TAG"]
    assert {v["check"] for v in data["violations"]} == {"TAG"}


def test_unplaceable_label_becomes_layout_violation(tmp_path):
    m = sample_model()
    m.objects.append(
        mk("Void_tiny", "void", "아주 긴 이름의 보이드 라벨은 어디에도 들어가지 않는다" * 3,
           box_mesh(0.3, 0.3, 0.5, 0.5, 0, 4.5)))
    model_json = write_model_json(m, tmp_path / "model.json")
    r = build(model_json, tmp_path / "out", tmp_path / "rej", "plan")
    assert not r.ok
    assert any(v.check in {"LAYOUT", "T1", "T2", "T3"} for v in r.violations)
