"""C-T14G tests: registry, Sheet claims/scale bars, 3D truth functions, independent PDF QA and defect injection.

PDF tests run on docs/t14g_v3/Candidate_V3_drawing_set.pdf (or $T14G_PDF) with the sheet registry next to it. Tests that need the
model run folder (output/C_T14G_V3_run or $T14G_RUN, not in git) skip when it is absent.
"""
import json
import math
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "src"))

PDF = os.environ.get("T14G_PDF", os.path.join(ROOT, "docs", "t14g_v3", "Candidate_V3_drawing_set.pdf"))
INDEX = os.environ.get("T14G_INDEX", os.path.join(ROOT, "docs", "t14g_v3", "sheet_index.json"))
RUN = os.environ.get("T14G_RUN", os.path.join(ROOT, "output", "C_T14G_V3_run"))
have_pdf = os.path.exists(PDF) and os.path.exists(INDEX)
need_pdf = pytest.mark.skipif(not have_pdf, reason="V3 PDF / sheet index not present")
need_run = pytest.mark.skipif(not os.path.isdir(RUN), reason="model run folder not present (gitignored)")


# ── registry ─────────────────────────────────────────────────────────────────────────────────────
def test_callout_scale_comes_from_registry():
    from t14g import registry as R
    assert R.callout_label("D-407") == "D-407 · 1:100"
    assert R.callout_label("D-410") == "D-410 · 1:100"
    assert R.callout_label("D-401") == "D-401 · 1:50"


def test_wrong_callout_scale_is_rejected():
    from t14g import registry as R
    with pytest.raises(R.ScaleMismatchError):
        R.callout_label("D-410", 50)          # the V2 error: P-105 / E-201..204 printed 1:50


def test_unknown_detail_is_rejected():
    from t14g import registry as R
    with pytest.raises(R.UnknownSheetError):
        R.detail_scale("D-499")


def test_generated_registry_mismatch_is_reported(tmp_path):
    from t14g import registry as R
    bad = {"details": [{"sheet": s, "scale": "1:%d" % d} for s, d in R.DETAIL_SCALE.items()]}
    bad["details"][6]["scale"] = "1:50"       # D-407 generated at the wrong scale
    p = tmp_path / "detail_registry.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    assert any("D-407" in x for x in R.verify_against_registry(str(p)))


# ── Sheet: scale bars and layout claims ──────────────────────────────────────────────────────────
def test_scale_bar_physical_length():
    import t14d_sheet as T
    for den, meters in ((50, 5), (100, 10), (250, 20), (400, 20)):
        sh = T.Sheet("T-000", "t", den, "DOCUMENT")
        sh.scale_bar(20.0, 100.0)
        assert abs(sh.bars[0]["length_mm"] - meters * 1000.0 / den) < 1e-3


def test_overlapping_claims_fail_the_build(tmp_path):
    import t14d_sheet as T
    sh = T.Sheet("T-001", "t", 100, "DOCUMENT")
    sh.claim("a", 10, 10, 60, 60)
    sh.claim("b", 50, 50, 90, 90)
    with pytest.raises(T.LayoutConflict):
        sh.save(str(tmp_path / "x"))


def test_scale_bar_leaving_the_sheet_fails(tmp_path):
    import t14d_sheet as T
    sh = T.Sheet("T-002", "t", 50, "DOCUMENT")
    sh.scale_bar(380.0, 100.0)                 # 100 mm bar + margin runs off the 420 mm sheet
    with pytest.raises(T.LayoutConflict):
        sh.save(str(tmp_path / "x"))


def test_title_block_uses_config_not_hardcoded_text():
    import t14d_sheet as T
    from t14g import config
    config.apply(T)
    sh = T.Sheet("T-003", "t", 100, "DOCUMENT")
    sh.title_block()
    joined = " ".join(sh.parts)
    assert config.PROJECT_CODE in joined and "C-T14D" not in joined


# ── 3D truth functions on synthetic meshes ───────────────────────────────────────────────────────
class _FakeModel:
    def __init__(self, tris):
        self._t = np.asarray(tris, float)

    def tris(self, o):
        return self._t


def _plate(angle_deg, run=8.0, width=3.0, thick=0.4):
    """Inclined plate (top + bottom faces) plus two flat landings, like an escalator flight."""
    rise = run * math.tan(math.radians(angle_deg))
    tris = []
    for z0 in (0.0, -thick):
        a, b, c, d = (0, 0, z0), (width, 0, z0), (width, run, z0 + rise), (0, run, z0 + rise)
        tris += [[a, b, c], [a, c, d]]
    for y0, y1 in ((-2.5, 0.0), (run, run + 2.5)):                                   # flat landings
        z = 0.0 if y0 < 0 else rise
        a, b, c, d = (0, y0, z), (width, y0, z), (width, y1, z), (0, y1, z)
        tris += [[a, b, c], [a, c, d]]
    return tris


def test_sloped_incline_ignores_landings():
    from t14g import truth
    inc = truth.sloped_incline(_FakeModel(_plate(30.0)), [{"name": "x"}])
    assert abs(inc["angle_deg"] - 30.0) < 0.3                  # a whole-object regression would give ~24 deg here


def test_circularity_distinguishes_circle_and_slot():
    from shapely.geometry import Point, box
    from t14g import truth
    assert truth.is_circle(Point(0, 0).buffer(2.8, 32))
    assert not truth.is_circle(box(0, 0, 8, 21))                # capsule/rectangle must not get a diameter symbol
    assert truth.diameter_label(box(0, 0, 8, 21), "8000").startswith("폭")


def test_congruence_detects_a_different_tube():
    from t14g import truth
    class Two:
        objects = [{"name": "A"}, {"name": "B"}]
        def __init__(self): self.i = 0
        def tris(self, o): return np.asarray(_plate(30.0) if o["name"] == "A" else _plate(30.0, run=9.0), float)
    r = truth.congruent(Two(), "A", "B")
    assert not r["congruent"]


# ── independent PDF QA on the real V3 PDF ────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def rows():
    return json.load(open(INDEX, encoding="utf-8"))["sheets"]


@need_pdf
@pytest.mark.parametrize("check", ["page_size", "index", "callouts", "scale_bars", "text_bounds", "text_overlap", "fonts", "duplicates", "north", "stale_refs"])
def test_pdf_check_is_clean(check, rows):
    from t14g import qa_pdf
    res = qa_pdf.run_all(PDF, rows, only={check})
    assert res[check] == [], res[check][:5]


@need_pdf
def test_every_scaled_sheet_has_a_correct_bar(rows):
    import pymupdf
    from t14g import qa_pdf
    rep = qa_pdf.scale_bar_report(pymupdf.open(PDF), rows)
    scaled = [r for r in rows if r["scale"] not in (None, "—", "") and r["sheet"] != "A-003"]
    assert len(rep) == len(scaled) >= 25
    assert all(x["status"] == "OK" for x in rep)


@need_pdf
def test_no_v2_leftovers_in_text(rows):
    import re
    import pymupdf
    d = pymupdf.open(PDF)
    for i, pg in enumerate(d, 1):
        t = re.sub(r"\s+", "", pg.get_text())
        if rows[i - 1]["sheet"] == "A-003":
            continue
        assert "C-T14D" not in t, "page %d still prints the V1 project code" % i


@need_pdf
def test_page_count_equals_sheet_list(rows):
    import pymupdf
    assert pymupdf.open(PDF).page_count == len(rows) >= 31


# ── defect injection: every mutation must be caught, the clean PDF must stay clean ───────────────
def _mutation_cases():
    from t14g import mutations
    return [(n, f, c) for n, f, c in mutations.MUTATIONS]


@need_pdf
@pytest.mark.parametrize("name,fn,check", _mutation_cases() if have_pdf else [], ids=lambda v: v if isinstance(v, str) else None)
def test_injected_defect_is_detected(name, fn, check, rows):
    import pymupdf
    from t14g import qa_pdf
    assert qa_pdf.run_all(PDF, rows, only={check})[check] == []
    doc = pymupdf.open(PDF)
    fn(doc, rows)
    assert qa_pdf.run_all(doc, rows, only={check})[check], "%s was not detected by %s" % (name, check)


@need_pdf
@need_run
def test_wrong_printed_overall_dimension_is_detected(rows, tmp_path):
    import pymupdf
    from t14g import mutations, truth_report
    doc = pymupdf.open(PDF)
    mutations.m_wrong_printed_dimension(doc, rows)
    p = tmp_path / "mut.pdf"
    doc.save(str(p))
    rep = truth_report.build(RUN, str(p), str(tmp_path / "t.json"))
    assert any(r["sheet"] == "P-101" and not r["passes"] for r in rep["rows"])


@need_pdf
@need_run
def test_dimension_truth_report_all_pass(tmp_path):
    from t14g import truth_report
    rep = truth_report.build(RUN, PDF, str(tmp_path / "t.json"))
    assert rep["failed"] == [] and rep["checked"] >= 25


# ── furniture design on real geometry (needs the run folder) ────────────────────────────────────
@need_run
@pytest.mark.parametrize("floor", ["3F", "8F", "10F", "13F", "15F"])
def test_furniture_floor_passes_geometry_checks(floor):
    from t14g import furniture_qa
    r = furniture_qa.check_floor(RUN, floor)
    assert r["overlapping_pairs"] == 0 and r["touching_structure"] == 0
    assert r["max_identical_share"] <= furniture_qa.MAX_SHARE and r["n_types"] >= furniture_qa.MIN_TYPES
    assert r["aisle_width_connecting_all_anchors_m"] is not None and r["aisle_width_connecting_all_anchors_m"] >= 1.2


@need_run
def test_programs_have_different_furniture_languages():
    from t14g import furniture_qa
    rs = [furniture_qa.check_floor(RUN, f) for f in ("3F", "8F", "10F", "13F", "15F")]
    assert furniture_qa.check_distinct(rs)["passes"]


@need_run
def test_coverage_covers_all_17_floors():
    p = os.path.join(RUN, "appendix", "typical_floor_coverage.json")
    d = json.load(open(p, encoding="utf-8"))
    fl = [f["floor"] for f in d["floors"]]
    assert fl == ["B2", "B1"] + ["%dF" % i for i in range(1, 16)]
