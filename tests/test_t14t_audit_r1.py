"""Tests for the C-T14T independent audit reconciliation pack (docs/t14t_audit_r1).

They check that the measurements are reproducible from the pinned slices, that the reconciliation data is well-formed and honest about what was not
available, that the Korean A3 PDF is what it claims to be, that the manifest matches the files, and that nothing protected was touched.
They do not review any architecture.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import fitz
import pytest

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "docs" / "t14t_audit_r1"
BASE_REF = "origin/claude/t14-skills-library-20261123"


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


meas_tool = load("tools/t14s/audit_measurements.py", "audit_meas")
guard = load(".claude/skills/drawing-source-guard/scripts/guard_check.py", "audit_guard")


def jl(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fresh(tmp_path_factory):
    out = tmp_path_factory.mktemp("meas")
    assert meas_tool.main(["--out", str(out)]) == 0
    return jl(out / "measurements.json")


def test_measurements_are_reproducible_from_the_pinned_slices_and_match_the_committed_pack(fresh):
    committed = jl(D / "measurements" / "measurements.json")
    assert fresh == committed
    assert fresh["source_geometry"]["ok"] is True


def test_measurements_cover_exactly_the_documented_decision_counts(fresh):
    assert (len(fresh["d01"]), len(fresh["d02"]), len(fresh["d03"])) == (25, 3, 15)
    where = {k: sum(1 for r in fresh["d01"] if r["end_lies_in"] == k) for k in ("core", "opening", "outside_slab_outline", "slab")}
    assert where == {"core": 1, "opening": 20, "outside_slab_outline": 4, "slab": 0}                     # no landing is on usable slab


def test_measurements_d01_alternative_figures_are_in_the_stated_ranges(fresh):
    cap = [r for r in fresh["d01"] if r["end_lies_in"] != "core"]
    assert min(r["altA_new_deck_m2"] for r in cap) == 9.6 and max(r["altA_new_deck_m2"] for r in cap) == 19.0
    assert all(r["altA_columns_within_deck_m"] == 0 for r in cap)
    shifts = [r["altC_shift_outward_to_slab_m"] for r in cap if r["altC_shift_outward_to_slab_m"] != ""]
    assert 12.0 <= min(shifts) and max(shifts) <= 15.0 and all(r["landing_rect_walkable_m2"] < 1.0 for r in cap)


def test_measurements_d02_cores_have_no_slab_within_17_m(fresh):
    assert [r["id"] for r in fresh["d02"]] == ["D02-2F-core-D", "D02-7F-core-C", "D02-7F-core-D"]
    for r in fresh["d02"]:
        assert r["core_on_slab_m2"] == 0.0 and r["nearest_slab_m"] == 17.0
        assert all(side["on_slab_pct"] == 0.0 for side in r["apron_by_side"].values())


def test_measurements_d03_every_unrotated_entry_is_blocked_and_every_proposal_is_clear(fresh):
    for r in fresh["d03"]:
        assert r["unrotated_blocked_by"] == (["tube:capW"] if r["tube"] == "T3" else ["tube:capE"]), r["id"]
        assert r["proposed_blocked_by"] == [] and r["proposed_apron_on_slab_pct"] == 100.0
    t4_12 = next(r for r in fresh["d03"] if r["id"] == "D03-12F-T4")
    assert t4_12["proposed_turn_deg"] == -75.0 and t4_12["sweep"]["-45"]["on_slab_pct"] < 100.0 and t4_12["sweep"]["-75"]["on_slab_pct"] == 100.0


def test_reconciliation_data_is_well_formed_and_states_what_was_unavailable():
    items = jl(D / "data" / "reconciliation_items.json")
    ids = [i["id"] for i in items["items"]]
    assert ids == ["R-%02d" % n for n in range(1, len(ids) + 1)] and len(ids) == 29
    assert all(i["status"] in items["status_values"] for i in items["items"])
    assert "AUDIT_REGISTER_47_NOT_AVAILABLE" in items["basis"] and "NOT a mapping of the 47" in items["basis"]
    assert all(i["note_ko"] and i["title_ko"] for i in items["items"])


def test_reconciliation_only_claims_verified_where_a_rerun_evidence_file_exists():
    items = jl(D / "data" / "reconciliation_items.json")["items"]
    for i in items:
        if i["status"] == "RESOLVED_VERIFIED":
            assert i["evidence"], i["id"]
            for e in i["evidence"]:
                rel = re.sub(r"\s*\(.*\)$", "", e)
                assert (D / rel).exists() or (ROOT / rel).exists(), (i["id"], e)
    assert {i["id"] for i in items if i["status"] == "NOT_APPLICABLE"} == {"R-29"}


def test_reconciliation_evidence_paths_exist():
    for i in jl(D / "data" / "reconciliation_items.json")["items"]:
        for e in i["evidence"]:
            rel = re.sub(r"(#.*|\s*\(.*\))$", "", e).strip()
            if rel.startswith(("evidence/", "measurements/")):
                assert (D / rel).exists(), (i["id"], e)
            elif rel.startswith(("docs/", "outputs/", "tools/", ".claude/")):
                assert (ROOT / rel).exists(), (i["id"], e)


def test_evidence_reruns_agree_with_the_documented_baselines():
    val = jl(D / "evidence" / "validator_rerun_report.json")["summary"]
    assert val["floors_technical_pass"] == 16 and val["source_geometry_unchanged"] is True and val["open_circulation_items"] == 25
    assert val["floors_circulation_complete"] == ["B2", "3F"]
    audit = jl(D / "evidence" / "circulation_audit.json")["floors"]
    assert not [f for f in audit if f["verdict"] == "COMPLETE"]                                     # the audit tool finds no complete floor
    pdf = jl(D / "evidence" / "pdf_consistency.json")
    assert pdf["cross_floor"]["P6_level_stack_identical_across_floors"]["pass"] and pdf["cross_floor"]["P7_title_strings_identical_across_floors"]["pass"]
    assert pdf["summary"]["F4_area_not_printed"] == 161 and pdf["summary"]["floors_all_pass"] == 4


def test_pdf_consistency_check_is_reproducible():
    pdf_tool = load("tools/t14s/audit_pdf_consistency.py", "audit_pdfc")
    committed = jl(D / "evidence" / "pdf_consistency.json")
    one = pdf_tool.check_floor(ROOT / "outputs" / "T14T", "3F")
    assert one["pass"] is True and committed["floors"][3]["floor"] == "3F" and committed["floors"][3]["pass"] is True
    two = pdf_tool.check_floor(ROOT / "outputs" / "T14T", "2F")
    assert two["checks"]["P4_main_room_areas_printed"]["pass"] is False                             # the measured finding: some main-room areas are not printed


def test_korean_a3_pdf_is_a3_landscape_vector_and_extractable():
    with fitz.open(str(D / "T14T_audit_reconciliation_A3_KO.pdf")) as doc:
        assert len(doc) == 7
        for pg in doc:
            assert abs(pg.rect.width - 1190.55) < 1 and abs(pg.rect.height - 841.89) < 1 and not pg.get_images()
        text = "\n".join(p.get_text() for p in doc)
    for needle in ("대조표", "AUDIT_REGISTER_47_UNAVAILABLE", "D-01", "WP0", "건축 승인 아님", "NOT_RUN"):
        assert needle in text, needle
    assert "APPROVED" not in re.sub(r"NOT APPROVED", "", text)


def test_page_previews_exist_for_every_pdf_page():
    assert sorted(p.name for p in (D / "preview").glob("page_*.png")) == ["page_%02d.png" % n for n in range(1, 8)]


def test_manifest_matches_every_file_in_the_pack():
    lines = (D / "SHA256_MANIFEST.txt").read_text(encoding="utf-8").splitlines()
    listed = {ln.split("  ", 1)[1]: ln.split("  ", 1)[0] for ln in lines}
    files = {p.relative_to(D).as_posix() for p in D.rglob("*") if p.is_file() and p.name != "SHA256_MANIFEST.txt"}
    assert set(listed) == files
    bad = [n for n, h in listed.items() if hashlib.sha256((D / n).read_bytes()).hexdigest() != h]
    assert not bad, bad


def test_pack_text_makes_no_approval_claim():
    files = [p for p in D.rglob("*") if p.suffix in (".md", ".json", ".csv") and p.parent.name != "measurements" and "evidence" not in p.parts and "source" not in p.parts]
    assert files
    for p in files:
        text = p.read_text(encoding="utf-8")
        assert not re.search(r"(?<![A-Za-z])(is|are|was|were) (now )?approved(?![A-Za-z])", text, re.I), p.name
        assert "APPROVED_DESIGN" not in text and not re.search(r"(?<![A-Za-z])frozen(?![A-Za-z])", text.replace("NOT FROZEN", ""), re.I), p.name


def test_captured_source_comments_hash_is_recorded():
    src = D / "source" / "pr30_review_comments_20261123.md"
    assert hashlib.sha256(src.read_bytes()).hexdigest() in (D / "00_STATE_AND_INTEGRITY.md").read_text(encoding="utf-8")


def test_protected_baselines_and_pinned_slices_were_not_touched():
    assert guard.check_sources(ROOT)["ok"]
    assert guard.check_manifests(ROOT, guard.load_config()["protected_manifests"])["ok"]
    try:
        res = guard.check_diff(ROOT, BASE_REF, [])
    except RuntimeError:
        pytest.skip("base ref %s not available" % BASE_REF)
    assert res["ok"], res["violations"]
