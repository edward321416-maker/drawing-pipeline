"""C-T14I V4 regression, print-scale, truth-class and finished-PDF QA."""
import json
import os
import sys

import pymupdf
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "src"))
RUN = os.environ.get("T14I_RUN", os.path.join(ROOT, "output", "C_T14I_run"))
BOOK = os.path.join(RUN, "v4", "book")
PDF_I = os.path.join(BOOK, "Graduation_Drawing_Book_Candidate_V4.pdf")
PDF_II = os.path.join(BOOK, "Technical_Drawing_Appendix_Candidate_V4.pdf")
IDX_I = os.path.splitext(PDF_I)[0] + "_index.json"
IDX_II = os.path.splitext(PDF_II)[0] + "_index.json"
need = pytest.mark.skipif(not all(os.path.exists(p) for p in (PDF_I, PDF_II, IDX_I, IDX_II)), reason="V4 books not built")


def rows(path):
    return json.load(open(path, encoding="utf-8"))["sheets"]


@need
def test_exact_deliverable_names_and_page_counts():
    assert os.path.basename(PDF_I) == "Graduation_Drawing_Book_Candidate_V4.pdf"
    assert os.path.basename(PDF_II) == "Technical_Drawing_Appendix_Candidate_V4.pdf"
    assert pymupdf.open(PDF_I).page_count == len(rows(IDX_I)) == 15
    assert pymupdf.open(PDF_II).page_count == len(rows(IDX_II)) == 49


@need
@pytest.mark.parametrize("pdf,index", [(PDF_I, IDX_I), (PDF_II, IDX_II)])
def test_finished_pdf_independent_qa_is_clean(pdf, index):
    from t14g import qa_pdf
    res = qa_pdf.run_all(pdf, rows(index))
    assert all(not findings for findings in res.values()), {k: v[:3] for k, v in res.items() if v}


@need
@pytest.mark.parametrize("pdf", [PDF_I, PDF_II])
def test_searchable_text_is_at_least_six_points(pdf):
    d = pymupdf.open(pdf)
    vals = [s["size"] for p in d for b in p.get_text("dict")["blocks"] if "lines" in b
            for line in b["lines"] for s in line["spans"] if s.get("text", "").strip()]
    assert vals and min(vals) >= 5.99


def test_model_cache_identity():
    from t14i import common
    p = os.path.join(RUN, "model_cache", "model_world.npz")
    assert common.sha_file(p) == "992e2ec51ec17dc494ed2f99ddb11298671449dd6661d92df3b3536a0049537b"


def test_original_glb_is_not_fabricated():
    from t14g import modelsrc
    ident = modelsrc.identity(RUN)
    assert ident["glb_present"] is False
    assert "MISSING" in ident["status"].upper() or "CACHE" in ident["status"].upper()


def test_plan_registry_has_required_sheets():
    p = os.path.join(RUN, "v4", "plans", "plan_registry.json")
    reg = {r["sheet"]: r for r in json.load(open(p, encoding="utf-8"))}
    required = {"P-%03d" % i for i in range(106, 113)} | {"P-201", "P-202", "P-211", "P-212", "P-213", "P-214", "A-905"}
    assert required <= set(reg)
    assert all(reg[s]["scale"] == "1:200" for s in ("P-201", "P-202", "P-211", "P-212", "P-213", "P-214"))
    assert all("OVERVIEW" in reg["P-%03d" % i]["grade"] for i in range(106, 113))


def test_one_to_two_hundred_paper_is_physical_not_image_scaled():
    reg = {r["sheet"]: r for r in json.load(open(os.path.join(RUN, "v4", "plans", "plan_registry.json"), encoding="utf-8"))}
    assert reg["P-201"]["paper"] == [841.0, 594.0]
    assert reg["P-202"]["paper"] == [841.0, 594.0]
    for sid in ("P-211", "P-212", "P-213", "P-214"):
        assert reg[sid]["paper"] == [420.0, 297.0]
        w = reg[sid]["window_m"][2] - reg[sid]["window_m"][0]
        h = reg[sid]["window_m"][3] - reg[sid]["window_m"][1]
        assert abs(reg[sid]["plan_size_mm"][0] - w * 5.0) < 0.02
        assert abs(reg[sid]["plan_size_mm"][1] - h * 5.0) < 0.02


def test_tile_registration_marks_are_shared_model_coordinates():
    reg = {r["sheet"]: r for r in json.load(open(os.path.join(RUN, "v4", "plans", "plan_registry.json"), encoding="utf-8"))}
    for a, b in (("P-211", "P-212"), ("P-213", "P-214")):
        ma = {x["id"]: x["model_xy_m"] for x in reg[a]["registration_marks"]}
        mb = {x["id"]: x["model_xy_m"] for x in reg[b]["registration_marks"]}
        assert ma == mb and len(ma) == 3


def test_area_reconciliation_keeps_reported_values_and_definitions():
    d = json.load(open(os.path.join(RUN, "v4", "area", "area_reconciliation.json"), encoding="utf-8"))
    f = {x["floor"]: x for x in d["floors"]}
    q8 = {k: v["value"] for k, v in f["8F"]["quantities"].items()}
    q12 = {k: v["value"] for k, v in f["12F"]["quantities"].items()}
    assert q8["program_sum_legacy_m2"] == 2526.02 and q8["slab_net_m2"] == 2339.34
    assert q12["program_sum_legacy_m2"] == 2489.09 and q12["slab_net_m2"] == 2012.23
    assert q12["borrowed_union_m2"] == 323.74
    assert "사용" in d["usable_area_basis"] and "UNRESOLVED" in d["usable_area_basis"]


def test_area_accounting_identity_residuals_are_tiny():
    d = json.load(open(os.path.join(RUN, "v4", "area", "area_reconciliation.json"), encoding="utf-8"))
    assert max(abs(f["accounting_identity_residual_m2"]) for f in d["floors"]) <= 0.01


def test_detail_registry_is_complete_and_v4():
    p = os.path.join(RUN, "v4", "details", "detail_registry.json")
    reg = {r["sheet"]: r for r in json.load(open(p, encoding="utf-8"))}
    assert set(reg) == {"D-%03d" % n for n in range(401, 411)}
    assert reg["D-404"]["v4_change"] == "missing section added"
    assert reg["D-408"]["v4_change"] == "missing section added"
    assert all("MODEL VERIFIED" in r["status_class"] and "UNRESOLVED" in r["status_class"] for r in reg.values())


def test_d408_does_not_present_458_as_approved_dimension():
    p = os.path.join(RUN, "v4", "details", "D-408_detail_v4.pdf")
    text = pymupdf.open(p)[0].get_text()
    assert "458" in text and "승인된 보행계단 단높이 아님" in text
    assert "DERIVED" in text and "UNRESOLVED" in text


def test_d404_separates_model_levels_from_concept_core():
    p = os.path.join(RUN, "v4", "details", "D-404_detail_v4.pdf")
    text = pymupdf.open(p)[0].get_text()
    assert "MODEL VERIFIED" in text and "CONCEPT PROPOSED" in text
    assert "1F→2F" in text and "층고" in text


@need
def test_contact_sheets_exist():
    for name in ("Graduation_Drawing_Book_Contact_Sheet.png", "Technical_Appendix_Contact_Sheet.png"):
        p = os.path.join(BOOK, name)
        assert os.path.exists(p) and os.path.getsize(p) > 100_000


def test_part_i_covers_required_editorial_sequence():
    reg = json.load(open(os.path.join(RUN, "v4", "partI", "partI_front_registry.json"), encoding="utf-8"))
    titles = " ".join(r["title"] for r in reg)
    for key in ("프로젝트 개요", "대지·도시 맥락", "매스 형성", "수직 보행", "프로그램", "대표층 평면", "시나리오", "입면", "단면", "축투상", "상세", "설계 요약"):
        assert key in titles


@need
def test_page_size_mutation_is_detected():
    from t14g import qa_pdf
    doc = pymupdf.open(PDF_II)
    doc[0].set_mediabox(pymupdf.Rect(0, 0, 300, 200))
    assert qa_pdf.check_page_size(doc, rows(IDX_II))


@need
def test_index_mutation_is_detected():
    from t14g import qa_pdf
    bad = rows(IDX_I)[:-1]
    assert qa_pdf.check_index(pymupdf.open(PDF_I), bad)
