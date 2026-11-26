"""R10-B drawing build driver.

Reuses the R10-A composer (draft.py + build.py data loaders: PR30 planner, R8 research meshes) from its local folder and
adds: GLB mesh-plane sections (A-301, A-302) and the developed 2F plan (A-201).

    python -I -X utf8 tools/r10b/build_r10b.py --out <dir> [--sheets A-301,A-302,A-201]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
R10A_DIR = r"D:\Users\admin\Desktop\2학기 논문\도면\01_과정\01_기획_구획_베이스\WP0_R10_A_대표도면"
sys.path[:0] = [HERE, R10A_DIR]
sys.dont_write_bytecode = True

import fitz  # noqa: E402

import glb_section as gs  # noqa: E402


def load_r10a():
    spec = importlib.util.spec_from_file_location("r10a_build", os.path.join(R10A_DIR, "build.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def legend_panel(p, x, y, items, notes, width, D):
    """Compact legend + unverified-items list.  items: [(kind, label)], notes: [str]."""
    D.text(p, x, y, "표기 구분", 8.6, True)
    D.rule(p, x, y + 2.2, x + width, y + 2.2, .22)
    yy = y + 9
    for kind, label in items:
        sx0, sx1 = x, x + 11
        if kind == "cut":
            D.frame(p, (sx0, yy - 2.2, sx1, yy - .4), .2, (.16, .17, .17))
        elif kind == "env":
            D.line(p, [(sx0, yy - 3.2), (sx1, yy - 3.2), (sx1, yy + .4), (sx0, yy + .4), (sx0, yy - 3.2)], .17, D.GRAY, D.DASH)
        elif kind == "prog":
            D.frame(p, (sx0, yy - 3.2, sx1, yy + .4), .06, (.955, .962, .958), D.FAINT)
        elif kind == "beyond":
            D.rule(p, sx0, yy - 1.4, sx1, yy - 1.4, .12, (.55, .57, .57))
        elif kind == "research":
            D.frame(p, (sx0, yy - 3.2, sx1, yy + .4), .3, D.CAND, D.INK)
        D.text(p, x + 15, yy - .3, label, 6.9)
        yy += 6.6
    yy += 3
    D.text(p, x, yy, "미확인 · 제외 사항", 8.6, True)
    D.rule(p, x, yy + 2.2, x + width, yy + 2.2, .22)
    yy += 9
    for n in notes:
        D.text(p, x, yy, n, 6.8, col=D.GRAY)
        yy += 5.9
    return yy


INDEX = {
    "A-301": [("코어 A · D", "A-VERT-STRS_A, _D  표현 외곽 · 절단"), ("M1 튜브", "A-CORE-TUBE_M1  절단"),
              ("T1 램프", "A-VERT-SPRL_B1-6F_T1_spiral  투영"), ("에스컬레이터", "A-VERT-ESCL_*_W_*  투영(서측)"),
              ("선큰 코트", "A-SITE_sunken_0118·0133, wall_0120  절단"), ("정원", "L-PLNT_garden_0115·0116  절단"),
              ("프로그램", "A-PROG_*  절단 · 볼륨"), ("브리지", "R8 연구 형상  절단 [제안]")],
    "A-302": [("M1 튜브", "A-CORE-TUBE_M1  절단"), ("캡슐", "A-CORE-TUBE_capW · capE  절단"),
              ("에스컬레이터", "A-VERT-ESCL_*  절단 · 투영"), ("커튼월", "A-FACD_glass·band·spandrel·rail  절단"),
              ("정원", "L-PLNT_garden_*  절단"), ("옥상 패드", "A-ROOF_rescue_pad · mark  절단"),
              ("프로그램", "A-PROG_*  절단 · 볼륨")],
}


def key_plan(p, B, D, x, y, cuts, current):
    """2F key plan 1:1000 locating both section planes (geometry = the 2F slab and cores already used by A-201)."""
    from shapely.geometry import box
    G = B.G
    v = D.View(p, "KEY", 1000, (-10, -19, 46, 37), (x, y + 11))
    D.text(p, x, y, "KEY PLAN · 2F  1:1000", 7.0, True)
    v.geo(G.slab, .14, D.BLACK, D.PALE)
    for k in "ABCD":
        v.geo(box(*G.cores[k]), .12, D.GRAY, None)
    for c in cuts:
        w = .45 if c["id"] == current else .18
        if c["axis"] == "x":
            a, b = v.xy(c["value"], -19), v.xy(c["value"], 37)
            D.rule(p, *a, *b, w, D.BLACK, D.GRID)
            D.symbol(p, a[0], a[1] + 4.2, c["mark"], None, 2.6)
            D.symbol(p, b[0], b[1] - 4.2, c["mark"], None, 2.6)
        else:
            a, b = v.xy(-10, c["value"]), v.xy(46, c["value"])
            D.rule(p, *a, *b, w, D.BLACK, D.GRID)
            D.symbol(p, a[0] - 4.2, a[1], c["mark"], None, 2.6)
            D.symbol(p, b[0] + 4.2, b[1], c["mark"], None, 2.6)
    D.text(p, x, v.r[3] + 9, "도면 위쪽 = +Y (A-201과 동일)", 6.4, col=D.GRAY)
    return v.r[3] + 9


def text_collisions(page_no, D, min_area=0.25):
    """Pairs of placed texts on a page whose boxes overlap by more than min_area mm^2 (halo boxes are not texts)."""
    boxes = [b for b in D.BBOX if b[0] == page_no]
    out = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            w = min(a[3], b[3]) - max(a[1], b[1])
            h = min(a[4], b[4]) - max(a[2], b[2])
            if w > 0 and h > 0 and w * h > min_area:
                out.append(dict(a=a[5], b=b[5], area_mm2=round(w * h, 2), at_mm=[round(max(a[1], b[1]), 1), round(max(a[2], b[2]), 1)]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--sheets", default="A-301,A-302")
    a = ap.parse_args()
    import draft as D
    os.makedirs(a.out, exist_ok=True)
    print("R10-A composer :", os.path.abspath(os.path.join(R10A_DIR, "build.py")))
    B = load_r10a()
    scene = gs.load_scene(verify_hash=True)
    theta = gs.frame_theta()
    import sheet_sections as S

    want = [s.strip() for s in a.sheets.split(",") if s.strip()]
    cfgs = {
        "A-301": dict(id="A-301", name=["전체 건축", "종단면도 A–A"], scale=250, axis="x", value=-4.2, depth=18.0,
                      hrange=(-38.5, 38.5), zrange=(-12.2, 77.0), paper=(60, 38), grid="Y", strip_x=40,
                      building_h=(-36.0, 18.0),
                      refs=["A-201  A–A 절단 위치", "A-302  B–B 횡단면", "A-501  코어 D 실상세"],
                      desc=["절단 X = -4.200 m", "+X 방향, 우측은 남측", "투영 깊이 18 m", "코어 상자는 표현 외곽"],
                      bridge_leader_x=378, caption=("01", "A–A 전체 종단면"), panel_x=386,
                      callouts=[dict(h=-32.5, z=58, t="코어 A", bold=True), dict(h=15.0, z=58, t="코어 D", bold=True),
                                dict(h=-9.0, z=44, t="M1", size=6.2),
                                dict(h=6.0, z=21.2, t="T1 나선 램프(투영)"), dict(h=-5.5, z=14.5, th=-27.0, tz=15.0, t="서측 에스컬레이터(투영)", align="center"),
                                dict(h=26.0, z=-3.9, t="선큰 코트 B1 -5.500", bold=True),
                                dict(h=36.2, z=0.9, th=31.0, tz=3.4, t="선큰 벽 +0.900", align="right"),
                                dict(h=-3.0, z=71.0, th=-3.0, tz=74.9, t="15F 옥상 정원"),
                                dict(h=8.0, z=27.7, t="6F 정원")]),
        "A-302": dict(id="A-302", name=["전체 건축", "횡단면도 B–B"], scale=250, axis="y", value=10.0, depth=18.0,
                      hrange=(-11.0, 47.0), zrange=(-12.2, 77.0), paper=(60, 38), grid="X", strip_x=40,
                      building_h=(-9.0, 45.0),
                      refs=["A-201  B–B 절단 위치", "A-301  A–A 종단면", "SECTION_B_REFINEMENT"],
                      desc=["절단 Y = +10.000 m", "+Y 방향, 우측은 동측", "투영 깊이 18 m", "코어 상자는 표현 외곽"],
                      bridge_leader_x=0, caption=("02", "B–B 전체 횡단면"), panel_x=312,
                      callouts=[dict(h=-4.0, z=48.0, t="M1", size=6.2),
                                dict(h=3.0, z=29.4, t="서측 캡슐(capW)", bold=True),
                                dict(h=31.0, z=74.2, t="동측 캡슐(capE)", bold=True),
                                dict(h=45.1, z=19.5, th=40.0, tz=19.8, t="유리 커튼월·스팬드럴 절단", align="right"),
                                dict(h=17.0, z=71.1, th=17.0, tz=74.5, t="옥상 rescue pad", size=6.6)]),
    }
    results = {}
    doc = fitz.open()
    fit_items, fit_report, fit_dropped, fit_info = [], None, [], {}
    if "A-201" in want:
        try:
            import fitout_r10b as F
            fit_items = F.develop_fitout(B.PR, B.G)
            fit_dropped, fit_info = list(getattr(fit_items, "dropped", [])), getattr(fit_items, "info", {})
            import fitout_checks_r10b as FC
            fit_report = FC.check_fitout(B.PR, B.G, fit_items)
            print("fit-out items:", len(fit_items), " violations:", {k: len(v_) for k, v_ in fit_report.get("violations", {}).items()}, flush=True)
        except ModuleNotFoundError as e:
            print("fit-out module not available yet:", e, flush=True)
    for sid in want:
        if sid == "A-201":
            import sheet_plan as SP
            print("Build A-201", flush=True)
            p, v, rec = SP.build_a201(doc, B, fit_items)
            rec["fitout_report"] = fit_report
            rec["fitout_dropped"] = fit_dropped
            rec["fitout_info"] = fit_info
            rec["text_collisions"] = text_collisions(p.number, D)
            print("A-201 text collisions:", len(rec["text_collisions"]), flush=True)
            results[sid] = rec
            continue
        if sid not in cfgs:
            continue
        cfg = cfgs[sid]
        print("Build", sid, flush=True)
        r = S.build_section_sheet(doc, B, cfg, scene, theta)
        p, v, rec = r["page"], r["view"], r["rec"]
        px = cfg["panel_x"]
        items = [("cut", "슬래브·튜브벽 절단 [모형]"), ("env", "코어 표현 외곽(내부 미모델링)"),
                 ("prog", "프로그램 볼륨(CH 아님)"), ("beyond", "절단면 뒤 투영 18 m")]
        if sid == "A-301":
            items.append(("research", "R8 브리지·랜딩 [연구 후보]"))
        notes = ["지하 외벽·흙막이·기초는 모형에 없어 미작도.",
                 "맥락 매스 일부가 건물 외곽과 겹쳐 단면에서 제외.",
                 "코어 내부 계단·승강로는 A-501(연구 형상).",
                 "층고는 모형 레벨. 마감 천장고(CH) 미확인.",
                 "부재 크기는 모형 외형. 구조 검토 없음.",
                 "대지 지반 ±0.000은 맥락 모형 바닥 기준."]
        if sid == "A-301":
            notes.append("A–A는 코어 단부에서 끝나 파사드를 자르지 않음. 외피는 A-302.")
        yend = legend_panel(p, px, 40, items, notes, 520 - px, D)
        yk = key_plan(p, B, D, px, yend + 8,
                      [dict(id="A-301", axis="x", value=-4.2, mark="A"), dict(id="A-302", axis="y", value=10.0, mark="B")], sid)
        D.text(p, px, yk + 9, "요소 색인 (모형 명칭)", 8.6, True)
        D.rule(p, px, yk + 11.2, 520, yk + 11.2, .22)
        yy = yk + 18
        for lab, src in INDEX[sid]:
            D.text(p, px, yy, lab, 6.9, True)
            D.text(p, px + 25, yy, src, 6.6, col=D.GRAY)
            yy += 5.8
        D.view_caption(p, 330 if sid == "A-301" else 300, 401, cfg["caption"][0], cfg["caption"][1], cfg["scale"], 520)
        v.bar(10, 62, 401)
        rec["text_collisions"] = text_collisions(p.number, D)
        print(sid, "text collisions:", len(rec["text_collisions"]), flush=True)
        results[sid] = rec
    ids = [s for s in want if s in cfgs or s == "A-201"]
    titles = {"A-201": "2층 전체 건축 평면도", "A-301": "전체 건축 종단면도 A–A", "A-302": "전체 건축 횡단면도 B–B"}
    doc.set_toc([[1, f"{i} {titles[i]}", n + 1] for n, i in enumerate(ids)])
    doc.set_metadata(dict(title="WP0 R10-B · 대표 도면", subject="독립 검수용", author="WP0 연구"))
    doc.subset_fonts()
    pdf = os.path.join(a.out, "WP0_R10B_Representative_A2.pdf")
    doc.save(pdf, garbage=4, deflate=True)
    for s_, expected in zip(doc, ids):
        assert expected in s_.get_text() and len(s_.get_image_info()) == 0, expected
        assert "R10-A" not in s_.get_text(), "stale R10-A text in " + expected
    print("saved PDF :", os.path.abspath(pdf))
    for i, pg in enumerate(doc):
        png = os.path.join(a.out, f"{ids[i]}_dev.png")
        pg.get_pixmap(dpi=90, alpha=False).save(png)
        print("saved PNG :", os.path.abspath(png))
    src = {
        "original_glb": gs.GLB_PATH,
        "approved_1f_master": "D:/Users/admin/Desktop/2학기 논문/도면/00_엔진/model/1F_master.blend",
        "r9_book_pdf": "D:/Users/admin/Desktop/2학기 논문/도면/01_과정/01_기획_구획_베이스/WP0_R9_기술도면집/WP0_R9_A2_기술도면집.pdf",
        "pr30_floor_2F_slice": os.path.join(ROOT, "data", "t14s", "source_slices", "floor_2F_slice.json"),
    }
    record = dict(page_order=ids, sheets=results, calculated_dimensions=D.SCALE_CHECKS, graphical_scales=D.GEOM,
                  normalized_geometry_at_draft_clip=D.NORMALIZED, label_count=len(D.BBOX),
                  protected_sources=[dict(role=k, path=os.path.abspath(v_), sha256=gs.sha256_file(v_)) for k, v_ in src.items()],
                  pdf_sha256=gs.sha256_file(pdf))
    rj = os.path.join(a.out, "R10B_GEOMETRY.json")
    with open(rj, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=1, default=str)
    print("saved JSON:", os.path.abspath(rj))


if __name__ == "__main__":
    main()
