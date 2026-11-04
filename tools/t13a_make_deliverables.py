"""C-T13A 산출물 도구: before/after 크롭·비교판, 래스터↔벡터 비교, 선 위생 보고, QA 보고, manifest.

    python tools/t13a_make_deliverables.py --out outputs/T13A --before-svg <V2-B svg> --before-check <V2-B check json> \
        --after-base outputs/T13A/1F_Program_CleanLine_V2A --blend <.blend> --slice <slice json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
import line_hygiene as LH  # noqa: E402
import t13a_crops as C  # noqa: E402
import t13a_geometry_check as G  # noqa: E402
import t13a_hygiene as H  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
TITLES = {"01_north_market": "북측 시장", "02_central_hall": "중앙 홀", "03_west_capsule": "서측 캡슐", "04_piloti_landscape": "필로티·조경", "05_legend_text": "범례·텍스트"}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def font(sz):
    for f in ("C:/Windows/Fonts/malgun.ttf", "malgun.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(f, sz)
        except OSError:
            continue
    return ImageFont.load_default()


def raster_svg(svg, width):
    import cairosvg
    import io
    png = cairosvg.svg2png(url=svg, output_width=width, background_color="white")
    return Image.open(io.BytesIO(png)).convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--before-svg", required=True)
    ap.add_argument("--before-check", required=True)
    ap.add_argument("--after-base", required=True)
    ap.add_argument("--blend", default=None)
    ap.add_argument("--slice", default=None)
    ap.add_argument("--tests", default="")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    base = os.path.abspath(a.after_base)
    cdir = os.path.join(out, "crops")
    os.makedirs(cdir, exist_ok=True)

    # ── PNG 300 dpi 메타데이터 ──
    png_path = base + ".png"
    im = Image.open(png_path)
    px = im.size
    im.save(png_path, dpi=(300, 300))
    dpi_x = px[0] / (420 / 25.4)

    # ── 크롭 (같은 상자, 같은 12000 px 래스터) ──
    big_b = raster_svg(a.before_svg, 12000)
    big_a = raster_svg(base + ".svg", 12000)
    cb = C.crops_from_image(big_b, cdir, "before")
    ca = C.crops_from_image(big_a, cdir, "after")
    names = {}
    for k in C.RECTS:
        for tag, src in (("before", cb[k]), ("after", ca[k])):
            dst = os.path.join(cdir, "crop_%s_%s.png" % (k, tag))
            if os.path.exists(dst):
                os.remove(dst)
            os.rename(src, dst)
            names["%s_%s" % (k, tag)] = dst
    # ── 비교판 ──
    cell_w, pad, head = 900, 14, 54
    rows = []
    for k in C.RECTS:
        b, c = Image.open(names[k + "_before"]), Image.open(names[k + "_after"])
        h = int(b.size[1] * cell_w / b.size[0])
        rows.append((k, b.resize((cell_w, h), Image.LANCZOS), c.resize((cell_w, h), Image.LANCZOS)))
    H_ = head + sum(r[1].size[1] + pad + 30 for r in rows) + pad
    board = Image.new("RGB", (2 * cell_w + 3 * pad, H_), "white")
    d = ImageDraw.Draw(board)
    f1, f2 = font(26), font(20)
    d.text((pad + 6, 12), "BEFORE  1F_Program_Concept_V2_B (기존)", fill="#111", font=f1)
    d.text((2 * pad + cell_w + 6, 12), "AFTER  1F_Program_CleanLine_V2A (선 정리)", fill="#111", font=f1)
    y = head
    for k, b, c in rows:
        d.text((pad + 6, y), TITLES[k], fill="#444", font=f2)
        y += 30
        board.paste(b, (pad, y))
        board.paste(c, (2 * pad + cell_w, y))
        d.rectangle((pad, y, pad + cell_w, y + b.size[1]), outline="#aaa")
        d.rectangle((2 * pad + cell_w, y, 2 * pad + 2 * cell_w, y + b.size[1]), outline="#aaa")
        y += b.size[1] + pad
    board_path = os.path.join(out, "1F_CleanLine_Before_After.png")
    board.save(board_path)

    # ── 래스터 ↔ 벡터 비교: 같은 구역을 SVG 래스터·PDF 래스터·PNG(300 dpi)에서 ──
    rect = C.RECTS["03_west_capsule"]
    sub = (rect[0] + 8, rect[1] + 22, rect[0] + 26, rect[1] + 36)                      # 캡슐 호 부근 18×14 mm
    import fitz
    zoom = 12000 / 420.0 * 25.4 / 72.0
    pg = fitz.open(base + ".pdf")[0]
    mat = fitz.Matrix(zoom, zoom)
    pm = pg.get_pixmap(matrix=mat, clip=fitz.Rect(sub[0] / 25.4 * 72, sub[1] / 25.4 * 72, sub[2] / 25.4 * 72, sub[3] / 25.4 * 72))
    pdf_crop = Image.frombytes("RGB", (pm.width, pm.height), pm.samples)
    sx, sy = big_a.size[0] / 420.0, big_a.size[1] / 297.0
    svg_crop = big_a.crop((int(sub[0] * sx), int(sub[1] * sy), int(sub[2] * sx), int(sub[3] * sy)))
    png_full = Image.open(png_path).convert("RGB")
    px_, py_ = png_full.size[0] / 420.0, png_full.size[1] / 297.0
    png_crop = png_full.crop((int(sub[0] * px_), int(sub[1] * py_), int(sub[2] * px_), int(sub[3] * py_))).resize(svg_crop.size, Image.BICUBIC)
    pdf_crop = pdf_crop.resize(svg_crop.size, Image.LANCZOS)
    g = lambda im_: np.asarray(im_.convert("L"), dtype=float)  # noqa: E731
    mae_pdf = float(np.mean(np.abs(g(svg_crop) - g(pdf_crop))))
    mae_png = float(np.mean(np.abs(g(svg_crop) - g(png_crop))))
    trip = Image.new("RGB", (svg_crop.size[0] * 3 + 4 * 10, svg_crop.size[1] + 60), "white")
    dd = ImageDraw.Draw(trip)
    for i, (lab, im_) in enumerate((("SVG 래스터(725 dpi)", svg_crop), ("PDF 래스터(725 dpi)", pdf_crop), ("PNG 300 dpi → 확대", png_crop))):
        trip.paste(im_, (10 + i * (svg_crop.size[0] + 10), 50))
        dd.text((10 + i * (svg_crop.size[0] + 10), 12), lab, fill="#111", font=f2)
    trip_path = os.path.join(out, "1F_CleanLine_Raster_vs_Vector_Check.png")
    trip.save(trip_path)

    # ── 선 위생 지표 / 형상 편차 / 곡선 로그 ──
    b_svg = open(a.before_svg, encoding="utf-8").read()
    a_svg = open(base + ".svg", encoding="utf-8").read()
    m_b, m_a = H.analyze(b_svg), H.analyze(a_svg)
    gm = G.compare(b_svg, a_svg)
    gm["furn_bodies"] = G.compare(b_svg, a_svg, ("furn",), {"furn": lambda at: 'fill="#FFFFFF"' in at})["furn"]
    clog = json.load(open(base + "_curvelog.json", encoding="utf-8"))
    by = {}
    for e in clog:
        key = "%s/%s" % (e["layer"] or "(none)", e["kind"])
        r = by.setdefault(key, {"count": 0, "vertices_before": 0, "cmds_after": 0, "max_dev_m": 0.0})
        r["count"] += 1
        r["vertices_before"] += e["n_before"]
        r["cmds_after"] += e["n_after"]
        r["max_dev_m"] = max(r["max_dev_m"], e["max_dev_m"])
    chk_b = json.load(open(a.before_check, encoding="utf-8"))
    chk_a = json.load(open(base + "_check.json", encoding="utf-8"))
    pb, pa = chk_b["program"], chk_a["program"]
    same_areas = all(abs(pb["zones"][k]["area_m2"] - pa["zones"][k]["area_m2"]) < 1e-6 for k in pb["zones"])
    report = {
        "task": "C-T13A Clean Line Pass", "base": "1F_Program_Concept_V2_B (claude/t13-1f-concept-v2 891e5bd)",
        "diagnosis": [
            {"id": 1, "kind": "기하(geometry)", "found": True,
             "where": "program_planner.partition (래스터 L∞ 분할) → renderer.draw_program_overlay",
             "evidence": "구획 경계 선 조각 1081개 중 917개가 2 m 미만. 계단 모양 래스터 경계가 사선 대시 파편으로 보임",
             "fix": "공유 경계 노드 병합(linemerge)+단순화 0.8 m, 7 m 미만 조각 제외, 바닥 채움 열림·닫힘 평활"},
            {"id": 2, "kind": "렌더링(raster)", "found": False,
             "where": "cairosvg svg2png / svg2pdf",
             "evidence": "SVG 래스터·PDF 래스터·PNG(300 dpi) 같은 구역 평균 밝기 차이 PDF %.2f, PNG %.2f (0~255). 계단 현상은 래스터화가 아니라 경로 자체의 문제" % (mae_pdf, mae_png),
             "fix": "PNG 를 4096→4961 px(300 dpi)로 출력. SVG→PDF 직접 생성은 유지"},
            {"id": 3, "kind": "레이어 중복", "found": True,
             "where": "draw_program_overlay(구획별 경계를 각각 그려 공유 경계 2회), design 맥락 대지경계(buffer(0.0005) 폴리곤 양면 2회+후퇴선 겹침)",
             "evidence": "점선 중복 비율 %.1f%% → %.1f%%" % (100 * m_b["dashed_overlap"]["overlap_ratio"], 100 * m_a["dashed_overlap"]["overlap_ratio"]),
             "fix": "경계 병합·평행 중복 제거(0.2 m)·구조 격자와 겹침 제외, 대지 경계 한 겹 선 + 후퇴선 근접 구간 제외. 가구 body 고스트는 before/after 모두 0"},
            {"id": 4, "kind": "표현(의도적 불규칙)", "found": True,
             "where": "monograph.wobble_ring / tree_shapes / branch_lines / plant_bed / stipple_points → renderer.draw_trees, design_site",
             "evidence": "참 원이 아닌 식재 윤곽 %d개(before) → %d개(after), 점묘 점 %d → %d" % (m_b["layers"]["plants"]["non_circle_closed_plants"], m_a["layers"]["plants"]["non_circle_closed_plants"], m_b["totals"]["dots"], m_a["totals"]["dots"]),
             "fix": "수관=참 원+줄기 점, 관목·화단=참 원, 가지·로제트·고사리선 제거, 점묘 1/3로 솎음(난수열 소비는 그대로라 수목·보행로 위치 불변)"},
            {"id": 5, "kind": "선 위계", "found": True,
             "where": "RESTYLE(context·landscape 가 가구 토큰 T5 와 같은 굵기·명도), draw_program_overlay 흐름·경계",
             "evidence": "before: 조경 외곽선·이웃 건물 윤곽·구획 경계 모두 0.08~0.12 mm #666~#444 로 가구와 동급",
             "fix": "restyle_clean: 조경 0.06 #A8A8A8, 이웃 윤곽 0.08 #8E8E8E, 프로그램 표시(흐름 0.08 #777·경계 0.055 #8A8A8A)로 가구(0.08 #666) 아래 순위. 구조 T1~T5 는 불변"},
        ],
        "line_hierarchy_after": {"1_cut_structure": "0.45 #000", "2_envelope_doors": "0.09 #4A4A4A glass / 0.18 #222 door leaf", "3_furniture": "0.08 #666 (white fill)",
                                 "4_program_marks": "flows 0.08 #777, zone boundary 0.055 #8A8A8A dashed, chips outline 0.06 #8A8A8A", "5_landscape_paving_hatch": "landscape 0.06 #A8A8A8, context 0.08 #8E8E8E, stipple #C0C0C0"},
        "metrics_before": m_b, "metrics_after": m_a,
        "curve_conversions": by,
        "curve_conversion_policy": {"arc_tol_m": LH.ARC_TOL, "edge_sagitta_tol_m": LH.EDGE_SAGITTA_TOL, "smooth_tol_m": LH.SMOOTH_TOL, "smooth_layers": ["landscape", "plants"],
                                    "note": "구조·가구·문·외피 층은 호 적합만(편차 ≤ 7 mm), 평활(베지어)은 조경 층만. 일괄 simplify() 없음"},
        "independent_geometry_check": gm,
        "raster_vs_vector": {"mae_svg_vs_pdf_0_255": round(mae_pdf, 3), "mae_svg_vs_png300_0_255": round(mae_png, 3), "image": os.path.abspath(trip_path)},
    }
    json.dump(report, open(os.path.join(out, "line_hygiene_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)

    # ── QA ──
    from pypdf import PdfReader
    rd = PdfReader(base + ".pdf")
    mb = rd.pages[0].mediabox
    pdf_mm = (round(float(mb.width) * 25.4 / 72, 2), round(float(mb.height) * 25.4 / 72, 2))
    meta = rd.metadata or {}
    struct_bad = {k: v["over_tol"] for k, v in gm.items() if v["over_tol"] or not v["count_match"]}
    qa = {
        "gates": {
            "A3_pdf_420x297_1page": abs(pdf_mm[0] - 420) < 0.3 and abs(pdf_mm[1] - 297) < 0.3 and len(rd.pages) == 1,
            "scale_1to500_scale_bar_10m_is_20mm": chk_a["scale"] == "1:500" and abs(chk_a["scale_bar_10m_mm"] - 20.0) < 1e-9 and chk_a["canvas_matches_A3"],
            "png_at_least_300dpi": dpi_x >= 299.9,
            "svg_has_no_raster_image_underlay": "<image" not in a_svg and "data:image" not in a_svg,
            "pdf_is_vector_cairo_no_embedded_raster_images": "cairo" in str(meta.get("/Producer", "")).lower() and len(fitz.open(base + ".pdf")[0].get_images()) == 0,
            "programs_18_present_and_areas_identical_to_V2B": len(pa["zones"]) == 18 and same_areas,
            "furniture_inventory_identical_to_V2B": pa["furniture_instances_by_zone_type"] == pb["furniture_instances_by_zone_type"],
            "columns_34_source_23_drawn_same_as_V2B": chk_a["columns_in_model"] == 34 and chk_a["columns_drawn"] == chk_b["columns_drawn"] == 23,
            "structure_geometry_unchanged_within_12mm": not struct_bad,
            "furniture_ghost_duplicates_zero": m_a["furniture_bodies"]["identical_paths"] == 0 and m_a["furniture_bodies"]["partial_overlaps"] == 0,
            "dashed_line_overlap_reduced": m_a["dashed_overlap"]["overlap_ratio"] < m_b["dashed_overlap"]["overlap_ratio"],
            "zigzag_kinks_zero": m_a["totals"]["zigzag_kinks"] == 0,
            "proposed_entries_not_promoted": all("PROPOSED_ONLY" in e["status"] for e in pa["proposed_entries"]),
            "door_swing_hits_zero": chk_a["door_swing_hits_wall"] == 0 and chk_a["door_swing_hits_other_door"] == 0,
            "furniture_touching_structure_zero": chk_a["furniture_touching_column"] == 0 and chk_a["furniture_touching_tube"] == 0 and pa["qa"]["furniture_hits_structure"] == 0,
        },
        "details": {"pdf_mm": pdf_mm, "pdf_producer": str(meta.get("/Producer", "")), "png_px": list(px), "png_dpi": round(dpi_x, 2),
                    "structure_geometry_over_tol": struct_bad, "tests": a.tests,
                    "not_verified_still_open": ["시장·캡슐 출입문 위치·폭·형식 (점선 후보)", "피난·장애인 접근 법규", "화장실 B/C 슬라이딩 문 직렬화(C-T11B)", "보행 최소 실폭"]},
        "inputs_sha256": {"source_blend": sha256(a.blend) if a.blend and os.path.exists(a.blend) else None, "slice_1F": sha256(a.slice) if a.slice and os.path.exists(a.slice) else None},
    }
    try:
        qa["git_head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        qa["git_head"] = None
    qa["technical_gate"] = "PASS" if all(qa["gates"].values()) else "FAIL"
    json.dump(qa, open(os.path.join(out, "qa_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    man = {}
    for root, _, files in os.walk(out):
        for f in sorted(files):
            fp = os.path.join(root, f)
            if f != "manifest.json":
                man[os.path.relpath(fp, out).replace("\\", "/")] = {"sha256": sha256(fp), "bytes": os.path.getsize(fp)}
    json.dump({"git_head": qa["git_head"], "inputs": qa["inputs_sha256"], "files": man}, open(os.path.join(out, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("technical gate:", qa["technical_gate"])
    for k, v in qa["gates"].items():
        print(("PASS " if v else "FAIL ") + k)
    print("raster check MAE svg-pdf %.2f svg-png %.2f | dpi %.1f" % (mae_pdf, mae_png, dpi_x))
    print("before/after:", m_b["totals"], "->", m_a["totals"])
    sys.exit(0 if qa["technical_gate"] == "PASS" else 1)


if __name__ == "__main__":
    main()
