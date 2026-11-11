"""V2 기준층 평면 시트 조립기.

렌더러가 만든 bare 평면(SVG)을 A3 시트에 얹고, 축선 기호·치수 체인(전체/구조 그리드/주요 요소 setout/주요 폭)·단면·입면·상세 호출 기호·큰 범례 패널·제목란을 더한다.
치수·위치는 모두 모델 slice와 객체에서 계산한다(숫자 좌표를 직접 쓰지 않는다).

    python -I tools/t14e_plan_sheet.py --run <V2 루트> --glb <glb> --plans 3F:P-101:3F,8F:P-102:8F+9F,...
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)
import pipeline_common as pc  # noqa: E402
import book_views as bv  # noqa: E402
from t14d_sheet import Sheet  # noqa: E402
import t14e_dims as dm  # noqa: E402
import t14d_sheet as _ts  # noqa: E402
from t14g import config as cfg  # noqa: E402
cfg.apply(_ts)

SCALE = 250
K = 1000.0 / SCALE          # 모델 1 m → 시트 4 mm
CX, CY = 158.0, 135.0       # 건물 중심의 시트 좌표(mm)
PANEL_X0, PANEL_X1 = 305.0, 411.0

STRATEGY = {
    "판매_A": "판매: 외벽 진열 띠 + 가로 섬 부스(엇갈림) + 튜브 둘레 휴게 벤치",
    "판매_B": "판매: 외벽 진열 띠 + 세로 쌍 섬(팝업) — 3F와 다른 배치",
    "F&B": "F&B: 외벽 뱅킷 · 4인 군집 · 공용 긴 테이블 · 바 카운터(스툴) · 서비스 카운터",
    "문화": "문화·엔터: 중앙 이벤트 무대(앞 계단·미디어 월) · 라운지 포드 · 전시 플린스 · 집합 계단",
    "garden": "정원·테라스: 식재 띠 · 수목 · 테라스 테이블 세트 · 벤치",
}


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def jl(p):
    return json.load(open(p, encoding="utf-8"))


def wrap(t, w=40):
    return textwrap.wrap(t, width=w, break_long_words=True) or [""]


def uniq(vals, tol=0.05):
    out = []
    for v in sorted(vals):
        if not out or abs(v - out[-1]) > tol:
            out.append(v)
    return out


def obj_center_r(model, name):
    o = next(o for o in model.objects if o["name"] == name)
    T = model.tris(o).reshape(-1, 3)
    cx, cy = (T[:, 0].min() + T[:, 0].max()) / 2, (T[:, 1].min() + T[:, 1].max()) / 2
    r = max(T[:, 0].max() - T[:, 0].min(), T[:, 1].max() - T[:, 1].min()) / 2
    return cx, cy, r


def compose(run, glb, floor, sid, applies, model, regs, evidence):
    raw_svg = os.path.join(run, "plans", "_raw", "raw_plan_%s.svg" % floor)
    chk = jl(os.path.join(run, "plans", "_raw", "raw_plan_%s_check.json" % floor))
    lay = jl(os.path.join(run, "vector", "floor_%s_layout.json" % floor))
    sl = pc.load_slice(os.path.join(run, "raw_slices"), floor)
    bx0, by0, bx1, by1 = lay["building"]
    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
    X = lambda x: CX + (x - cx) * K
    Y = lambda y: CY - (y - cy) * K
    cuts = pc.cut_geometries(sl)
    meta = {"overall_chains": 0, "grid_chains": 0, "setout_chains": 0, "major_dims": 0, "axis_bubbles": 0, "section_tags": 0, "elevation_tags": 0, "detail_callouts": 0, "level_dims": 0}

    progs = [(z["name_ko"]) for z in sl["zones"]]
    main = progs[0] if progs else ""
    title = "%s 기준 평면도" % ("%d층" % int(floor[:-1]))
    sh = Sheet(sid, "%s (적용: %s)" % (title, "·".join(applies)), SCALE,
               "LEVEL S · PROPOSED_ONLY · NOT FINAL",
               subtitle="치수 단위 mm · 축선은 모델 기둥 중심선 · 상층 구획벽·문은 모델에 없어 미확정",
               extra_lines=["프로그램: " + ", ".join(dict.fromkeys(progs)) if progs else "프로그램: -", "도면 방향: 1층 마스터와 동일(north_deg %.1f°, frame-ref)" % model.north_deg])

    # ── 렌더러 평면 얹기 ─────────────────────────────────────────────────────────────────────
    svg = open(raw_svg, encoding="utf-8").read()
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    W, H = float(m.group(1)), float(m.group(2))
    inner = svg[svg.index(">", svg.index("<svg")) + 1: svg.rindex("</svg>")]
    inner = re.sub(r'<rect width="[\d.]+" height="[\d.]+" fill="#ffffff"/>', "", inner, count=1)
    inner = re.sub(r"<metadata>.*?</metadata>", "", inner, flags=re.S)
    tx, ty = CX - (W / 2) * K, CY - (H / 2) * K
    sh.parts.append('<defs><clipPath id="drawclip"><rect x="14" y="6" width="288" height="252"/></clipPath></defs>')
    sh.parts.append('<g clip-path="url(#drawclip)"><g transform="translate(%.3f %.3f) scale(%.4f)">%s</g></g>' % (tx, ty, K, inner))

    # ── 축선 / 치수 ─────────────────────────────────────────────────────────────────────────
    cols = [g.centroid for _, g in cuts.get("column", [])]
    xs = uniq([c.x for c in cols])
    ys = uniq([c.y for c in cols])
    xl, yl = dm.axis_labels(xs, ys)
    Xl, Xr, Yt, Yb = X(bx0), X(bx1), Y(by1), Y(by0)
    for x in xs:                                                                       # 위쪽 알파벳 기호
        sh.line(X(x), Yt - 1.0, X(x), Yt - 14.5, 0.1, "#888", "6,1.4,1,1.4")
        dm.bubble(sh, X(x), Yt - 18.0, xl[round(x, 2)] if round(x, 2) in xl else chr(65 + xs.index(x)), r=3.0)
        meta["axis_bubbles"] += 1
    for y in ys:                                                                       # 왼쪽 숫자 기호
        sh.line(Xl - 1.0, Y(y), Xl - 14.5, Y(y), 0.1, "#888", "6,1.4,1,1.4")
        dm.bubble(sh, Xl - 18.0, Y(y), yl[round(y, 2)] if round(y, 2) in yl else str(len(ys) - ys.index(y)), r=3.0)
        meta["axis_bubbles"] += 1
    # 구조 그리드 체인(건물 가장자리 → 축선)
    gx = [bx0] + [x for x in xs if bx0 + 0.2 < x < bx1 - 0.2] + [bx1]
    dm.chain_h(sh, [X(v) for v in gx], Yt - 5.0, [dm.fmt_mm(b - a) for a, b in zip(gx, gx[1:])], from_y=Yt)
    meta["grid_chains"] += 1
    gy = [by1] + [y for y in sorted(ys, reverse=True) if by0 + 0.2 < y < by1 - 0.2] + [by0]
    dm.chain_v(sh, [Y(v) for v in gy], Xl - 5.0, [dm.fmt_mm(a - b) for a, b in zip(gy, gy[1:])], from_x=Xl)
    meta["grid_chains"] += 1
    dm.dim_h(sh, Xl, Xr, Yt - 10.5, dm.fmt_mm(bx1 - bx0), from_y=Yt)                    # 전체 폭
    dm.dim_v(sh, Yt, Yb, Xl - 10.5, dm.fmt_mm(by1 - by0), from_x=Xl)                    # 전체 깊이
    meta["overall_chains"] += 2
    # 주요 요소 setout(튜브·캡슐 중심선)
    cen = []
    for it, g in cuts.get("tube_wall", []):
        nm = it["name_ko"]
        b = g.bounds
        r = max(b[2] - b[0], b[3] - b[1]) / 2
        if r > 1.6 and ("T" in nm or "캡슐" in nm or "튜브" in nm):
            cen.append((nm, (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, r, b))
    sx = [bx0] + uniq([c[1] for c in cen]) + [bx1]
    sx = sorted(set(round(v, 2) for v in sx))
    dm.chain_h(sh, [X(v) for v in sx], Yb + 6.0, [dm.fmt_mm(b - a) for a, b in zip(sx, sx[1:])], from_y=Yb)
    sy = [by1] + sorted(uniq([c[2] for c in cen]), reverse=True) + [by0]
    sy = sorted(set(round(v, 2) for v in sy), reverse=True)
    dm.chain_v(sh, [Y(v) for v in sy], Xr + 6.0, [dm.fmt_mm(a - b) for a, b in zip(sy, sy[1:])], from_x=Xr, left=False)
    meta["setout_chains"] += 2
    sh.text(Xl + 1, Yb + 12.2, "← 튜브·캡슐 중심선 setout (치수는 중심선 사이)", 5.2, "normal", "#666")
    # 주요 폭: 캡슐 폭, 가장 큰 튜브 지름
    caps = [c for c in cen if "캡슐" in c[0]]
    big = sorted([c for c in cen if "캡슐" not in c[0]], key=lambda c: -c[3])[:2]
    for c in caps:
        b = c[4]
        wy = (b[1] + b[3]) / 2
        dm.dim_h(sh, X(b[0]), X(b[2]), Y(wy) - 0.0, dm.fmt_mm(b[2] - b[0]), pt=5.6, color="#06a")
        meta["major_dims"] += 1
    for c in big:
        b = c[4]
        dm.dim_h(sh, X(b[0]), X(b[2]), Y(b[1]) + 3.0, "Ø" + dm.fmt_mm(b[2] - b[0]), pt=5.6, color="#06a")
        meta["major_dims"] += 1

    # ── 단면·입면·상세 기호 ───────────────────────────────────────────────────────────────────
    for s in regs["sections"]["sections"]:
        (ax0, ay0), (ax1, ay1) = s["line_drawing_frame"]
        horizontal = abs(ay1 - ay0) < 1e-6
        e0 = (ax0, ay0)
        e1 = (ax1, ay1)
        # 건물 안으로 들여 그린 절단선(양 끝은 건물 경계에서 3 m 안쪽)
        if horizontal:
            p0, p1 = (bx0 + 2.5, ay0), (bx1 - 2.5, ay1)
        else:
            p0, p1 = (ax0, by0 + 2.5), (ax1, by1 - 2.5)
        sh.line(X(p0[0]), Y(p0[1]), X(p1[0]), Y(p1[1]), 0.2, "#c00", "7,1.6,1.2,1.6")
        lk = s["view_direction_drawing_frame"]
        arrow = (lk[0], -lk[1])
        ref = s["sheet"]
        dm.section_tag(sh, X(p0[0]), Y(p0[1]), s["name"][0], ref, arrow=arrow)
        dm.section_tag(sh, X(p1[0]), Y(p1[1]), s["name"][0], ref, arrow=arrow)
        meta["section_tags"] += 2
    names = {"N": "E-201", "E": "E-202", "S": "E-203", "W": "E-204"}
    vlines = [sec["plane"]["value_drawing_frame"] for sec in regs["sections"]["sections"] if sec["plane"]["axis"] == "x"]
    hlines = [sec["plane"]["value_drawing_frame"] for sec in regs["sections"]["sections"] if sec["plane"]["axis"] == "y"]

    def pick(lo, hi, lines):
        for f_ in (0.30, 0.70, 0.22, 0.78, 0.38, 0.62):
            v = lo + (hi - lo) * f_
            if all(abs(v - l_) >= 5.0 for l_ in lines):
                return v
        return (lo + hi) / 2
    tags = [("N", (bx1 - 5.0, pick(by0, by1, hlines)), (1, 0)), ("S", (bx0 + 5.0, pick(by0, by1, hlines)), (-1, 0)),
            ("E", (pick(bx0, bx1, vlines), by0 + 5.0), (0, 1)), ("W", (pick(bx0, bx1, vlines), by1 - 5.0), (0, -1))]
    for nm, (px, py), d in tags:
        ref = next(e["sheet"] for e in regs["elev"]["elevations"] if e["name"] == nm)
        dm.elevation_tag(sh, X(px), Y(py), ref, d)
        meta["elevation_tags"] += 1
    # 호출 대상 상세 번호와 위치 객체만 적는다. 축척은 detail_tag가 레지스트리(tools/t14g/registry.py)에서 읽는다.
    callouts = {"3F": [("D-401", "A-CORE-TUBE_T1"), ("D-402", "A-CORE-TUBE_T2"), ("D-403", "A-CORE-TUBE_T3"), ("D-405", "A-CORE-TUBE_capW")],
                "8F": [("D-407", None)], "15F": [("D-410", "A-ROOF_rescue_pad")]}
    used_callouts = []
    for sid_d, oname in callouts.get(floor, []):
        if oname is None:
            es = [o for o in model.objects if o["name"].startswith("A-VERT-ESCL_8F-9F")]
            pts = []
            for o in es:
                T = model.tris(o).reshape(-1, 3)
                pts += [(T[:, 0].min(), T[:, 1].min()), (T[:, 0].max(), T[:, 1].max())]
            ex, ey = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2, (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
            er = max(max(p[0] for p in pts) - min(p[0] for p in pts), max(p[1] for p in pts) - min(p[1] for p in pts)) / 2
        else:
            ex, ey, er = obj_center_r(model, oname)
        dm.detail_tag(sh, X(ex), Y(ey), sid_d, dashed_r=max(er, 2.0) * K * 0.55)
        used_callouts.append(sid_d)
        meta["detail_callouts"] += 1

    # ── 범례 패널(큰 글자, 여백, 잘림 없음) ──────────────────────────────────────────────────
    px0, py0 = PANEL_X0, 8.0
    sh.path([[(px0, py0), (PANEL_X1, py0), (PANEL_X1, 258.0), (px0, 258.0)]], fill="#fff", stroke="#555", w=0.3)
    x = px0 + 4
    y = py0 + 8
    sh.text(x, y, "범례  LEGEND", 9, "bold", "#111")
    y += 7
    legend = chk.get("legend", {})
    areas = {}
    for z in sl["zones"]:
        g = pc.polygons_from_segments(z["segments"])
        areas[z["name_ko"]] = areas.get(z["name_ko"], 0.0) + g.area
    for no in sorted(legend, key=lambda k: int(k)):
        nm = legend[no]
        sh.path([[(x + 2.6 + 2.4 * math.cos(t / 20 * 2 * math.pi), y - 0.8 + 2.4 * math.sin(t / 20 * 2 * math.pi)) for t in range(21)]], fill="#fff", stroke="#666", w=0.2)
        sh.text(x + 2.6, y + 0.1, str(no), 6, "bold", "#222", "middle")
        a = ""
        for zn, ar in areas.items():
            if (nm == "시장 홀" and ("판매" in zn or "시장" in zn)) or (nm == "F&B 구역" and "F&B" in zn) or (nm == "문화·엔터 구역" and ("문화" in zn or "엔터" in zn)) or (nm == "정원·테라스" and "garden" in zn.lower()):
                a = "  %s ㎡" % format(int(round(ar)), ",")
        sh.text(x + 7.5, y + 0.4, nm + a, 6.8, "normal", "#222")
        y += 5.4
    y += 2
    sh.line(x, y, PANEL_X1 - 4, y, 0.2, "#999")
    y += 6
    sh.text(x, y, "기호", 8, "bold", "#111")
    y += 6
    sym = [("●", "구조 기둥(모델 기둥, 실선)", None), ("◌", "점선 원 = 코어 인접 모델 기둥(1층 규칙상 생략 대상)", None), ("▭", "회색 사각 = 가구(PROPOSED_ONLY, 설계 데이터 아님)", None),
           ("⊙", "이중 원 = 튜브 / 이중 원 안 사각 = 승강로", None), ("A", "구조 축선(알파벳=가로, 숫자=세로), 치수 mm", None)]
    for g_, t, _ in sym:
        sh.text(x, y, g_, 7, "bold", "#333")
        for i, ln in enumerate(wrap(t, 36)):
            sh.text(x + 6, y + i * 3.6, ln, 6.0, "normal", "#333")
        y += 3.6 * len(wrap(t, 36)) + 1.8
    # 호출 기호 설명
    y += 1
    sh.text(x, y, "참조 기호", 8, "bold", "#111")
    y += 6
    dm.bubble(sh, x + 3, y - 0.6, "A", r=2.6, pt=6.0, color="#c00")
    sh.text(x + 8, y, "단면 절단선 — 단면 시트 S-302 ~ 305, 키플랜 S-301", 6.0, "normal", "#c00")
    y += 6.2
    dm.bubble(sh, x + 3, y - 0.6, "1", r=2.6, pt=6.0, color="#06a")
    sh.text(x + 8, y, "입면 방향 — E-201 북 · 202 동 · 203 남 · 204 서", 6.0, "normal", "#06a")
    y += 6.2
    dm.bubble(sh, x + 3, y - 0.6, "D", r=2.6, pt=6.0, color="#a60")
    sh.text(x + 8, y, "상세 호출 — 점선 원 위치, 상세 시트 D-4xx", 6.0, "normal", "#a60")
    y += 8
    sh.line(x, y - 3, PANEL_X1 - 4, y - 3, 0.2, "#999")
    sh.text(x, y + 2, "가구·프로그램 전략", 8, "bold", "#111")
    y += 8
    strat = []
    for pn in dict.fromkeys(progs):
        if "판매" in pn or "시장" in pn:
            strat.append(STRATEGY["판매_A"] if floor in ("2F", "3F", "4F", "5F") else STRATEGY["판매_B"])
        elif "F&B" in pn:
            strat.append(STRATEGY["F&B"])
        elif "문화" in pn or "엔터" in pn:
            strat.append(STRATEGY["문화"])
        elif "garden" in pn.lower():
            strat.append(STRATEGY["garden"])
    for t in strat:
        for i, ln in enumerate(wrap(t, 40)):
            sh.text(x, y, ln, 6.2, "normal", "#333")
            y += 3.7
        y += 1.2
    sh.line(x, y, PANEL_X1 - 4, y, 0.2, "#999")
    y += 6
    sh.text(x, y, "관련 시트", 8, "bold", "#111")
    y += 5.2
    rel = [("단면", "S-301 키플랜 · S-302 A–A · S-303 B–B · S-304 C–C · S-305 D–D"), ("입면", "E-201 북 · E-202 동 · E-203 남 · E-204 서"),
           ("상세", " · ".join(used_callouts) if used_callouts else "이 층에 호출된 상세 없음"), ("배치", "A-003 배치도·1층 / A-901 층별 층고·평면 발행표 / A-002 범례·기호")]
    for k_, t in rel:
        lines_ = wrap("%s  %s" % (k_, t), 42)
        for i, ln in enumerate(lines_):
            sh.text(x + (0 if i == 0 else 6), y, ln, 5.8, "normal", "#333")
            y += 3.6
        y += 0.8
    y += 2
    sh.line(x, y, PANEL_X1 - 4, y, 0.2, "#999")
    y += 6
    sh.text(x, y, "상태·한계", 8, "bold", "#111")
    y += 6
    notes = ["LEVEL S: 구조·프로그램 볼륨만 모델에 있음. 상층 구획벽·문·화장실·피난 경로는 모델에 없어 미확정.",
             "가구·식재는 설명용 PROPOSED_ONLY. 설계 확정 아님.", "최종 FREEZE 아님(후보 %s)." % cfg.EDITION]
    if len(applies) > 1:
        pr = next((p for h in evidence["hypothesis_groups"] for p in h["pairs"] if set(p["pair"].split("~")) == set(applies[:2])), None)
        notes.append("적용 층 %s: 수직동선 개구만 다름(검증됨), EQUIVALENCE VERIFIED 아님." % "·".join(applies))
        if pr:
            for kind, label in (("stair", "에스컬레이터"), ("shaft", "승강기 샤프트")):
                for ff in applies[:2]:
                    other = [a for a in applies[:2] if a != ff][0]
                    pts = pr["vertical_elements"][kind][ff]
                    op = pr["vertical_elements"][kind][other]
                    only = [p for p in pts if all(abs(p[0] - q[0]) > 0.5 or abs(p[1] - q[1]) > 0.5 for q in op)]
                    if only:
                        notes.append("%s %s 고유: %s (건물 모서리 기준 m)" % (ff, label, " ".join("(%.1f,%.1f)" % (p[0] - bx0, p[1] - by0) for p in only)))
    for t in notes:
        for i, ln in enumerate(wrap(t, 40)):
            sh.text(x + (0 if i == 0 else 2), y, ("· " if i == 0 else "") + ln, 6.0, "normal", "#444")
            y += 3.7
        y += 0.8
    # 방위·축척 막대
    sh.north_arrow(PANEL_X1 - 14, 226.0, model.north_deg, r=6.5)
    sh.text(PANEL_X1 - 14, 240.0, "진북 %.1f°" % model.north_deg, 5.6, "normal", "#444", "middle")
    k = K
    bx, by = px0 + 6, 236.0
    for i, (a, b_) in enumerate(((0, 5), (5, 10), (10, 20))):
        sh.path([[(bx + a * k, by), (bx + b_ * k, by), (bx + b_ * k, by + 1.8), (bx + a * k, by + 1.8)]], fill="#111" if i % 2 == 0 else "#fff", stroke="#111", w=0.15)
    for mv in (0, 5, 10, 20):
        sh.text(bx + mv * k, by - 1.4, "%d%s" % (mv, " m" if mv == 20 else ""), 5.6, "normal", "#333", "middle")
    sh.text(bx, by + 6.2, "1:250  A3 420×297 mm", 5.6, "normal", "#555")
    sh.text(bx, by + 10.4, "※ A3에서 1:200은 치수열·축선 기호·제목란이 들어갈 자리가 없어 1:250 사용", 4.6, "normal", "#777")
    sh.title_block()
    base = os.path.join(run, "plans", "%s_plan_%s" % (sid, floor))
    sh.save(base)
    return {"sheet": sid, "floor": floor, "applies_to": applies, "scale": "1:250", "meta": meta, "furniture_count": chk.get("furniture_items"), "legend": legend,
            "callouts": used_callouts, "axes": {"x": len(xs), "y": len(ys)}, "files": {e: {"path": base + "." + e, "sha256": sha_file(base + "." + e)} for e in ("svg", "pdf", "png")},
            "sections_marked": [s["sheet"] for s in regs["sections"]["sections"]], "elevations_marked": [e["sheet"] for e in regs["elev"]["elevations"]]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--glb", default=None, help="원본 GLB(없어도 됨)")
    ap.add_argument("--plans", required=True, help="층:시트번호:적용층(+로 연결) 쉼표 구분")
    a = ap.parse_args()
    run = os.path.abspath(a.run)
    model = bv.Model(os.path.join(run, "model_cache"), os.path.join(run, "raw_slices", "camera_bounds.json"))
    regs = {"sections": jl(os.path.join(run, "qa", "ref_registries", "section_line_registry.json")), "elev": jl(os.path.join(run, "qa", "ref_registries", "elevation_registry.json"))}
    evidence = jl(os.path.join(run, "00_index", "floor_equivalence_evidence.json"))
    out = []
    for spec in a.plans.split(","):
        floor, sid, ap_ = spec.split(":")
        r = compose(run, a.glb, floor, sid, ap_.split("+"), model, regs, evidence)
        out.append(r)
        print("PLAN SHEET", sid, floor, r["meta"])
    json.dump(out, open(os.path.join(run, "plans", "plan_sheets.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
