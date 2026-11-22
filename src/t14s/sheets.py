"""Sheet composition (paper mm, 1:200): A1 landscape full plan and two A3 landscape split sheets (north / south halves)."""
from __future__ import annotations

import math

from .export_svg import Svg, Xf, draw_plan, f3
from .model import MM_PER_M, PROPOSED, MODEL_VERIFIED, Drawing
from .layout import PROG_KO, TINT

A1 = (841.0, 594.0)
A3 = (420.0, 297.0)
INK, GREY = "#111111", "#555555"
PROJECT = "C-T14T"
ISSUE_DATE = "2026-11-23"
STATUS_LINE = "PROPOSED_DESIGN · NOT APPROVED · NOT FROZEN"
PROG_ORDER = ["retail", "fnb", "culture", "garden", "restroom"]


def window_full(env=(-9.0, -18.0, 45.0, 36.0)):
    return (env[0] - 9.0, env[1] - 11.0, env[2] + 9.0, env[3] + 9.0)


def frame(svg, W, H, m):
    svg.rect(m, m, W - 2 * m, H - 2 * m, stroke=INK, sw=0.6)


def title_block(svg, x0, y0, x1, y1, info, sheet_text, paper_text):
    svg.rect(x0, y0, x1 - x0, y1 - y0, stroke=INK, sw=0.5)
    w = x1 - x0
    cuts = [x0 + w * 0.10, x0 + w * 0.46, x0 + w * 0.72, x0 + w * 0.86]
    for c in cuts:
        svg.line(c, y0, c, y1, stroke=INK, sw=0.35)
    h = y1 - y0
    svg.text(x0 + 3, y0 + h * 0.55, info["sheet_id"], 12, "bold", INK, "start")
    svg.text(x0 + 3, y0 + h * 0.80, sheet_text, 6.25, "normal", GREY, "start")
    svg.text(cuts[0] + 4, y0 + h * 0.42, info["title_ko"], 13, "bold", INK, "start")
    svg.text(cuts[0] + 4, y0 + h * 0.64, "Floor plan %s · FFL %s m · 다층 상업시설 수직 보행" % (info["floor"], info["level"]), 7.5, "normal", GREY, "start")
    svg.text(cuts[0] + 4, y0 + h * 0.84, info["subtitle"], 6.25, "normal", GREY, "start")
    svg.text(cuts[1] + 4, y0 + h * 0.36, "축척 1:200 (%s)" % paper_text, 8, "bold", INK, "start")
    svg.text(cuts[1] + 4, y0 + h * 0.58, STATUS_LINE, 6.25, "bold", "#9b1c1c", "start")
    svg.text(cuts[1] + 4, y0 + h * 0.78, "검수: C_T14T_READY_FOR_CHATGPT_INDEPENDENT_REVIEW", 6.25, "normal", GREY, "start")
    svg.text(cuts[2] + 4, y0 + h * 0.36, PROJECT, 11, "bold", INK, "start")
    svg.text(cuts[2] + 4, y0 + h * 0.58, "개정 R1 (정정 후보)", 6.25, "normal", GREY, "start")
    svg.text(cuts[2] + 4, y0 + h * 0.78, "출력 " + ISSUE_DATE, 6.25, "normal", GREY, "start")
    svg.text(cuts[3] + 4, y0 + h * 0.36, "진북 %.1f°" % info["north_deg"], 6.25, "normal", GREY, "start")
    svg.text(cuts[3] + 4, y0 + h * 0.58, "PR #29 기준 정정", 6.25, "normal", GREY, "start")
    svg.text(cuts[3] + 4, y0 + h * 0.78, "1F 원본 보존", 6.25, "normal", GREY, "start")


def scale_bar(svg, x, y):
    k = MM_PER_M
    for i, (a, b) in enumerate(((0, 5), (5, 10), (10, 20))):
        svg.rect(x + a * k, y, (b - a) * k, 2.2, stroke=INK, sw=0.25, fill=INK if i % 2 == 0 else "#ffffff")
    for v in (0, 5, 10, 20):
        svg.text(x + v * k, y - 1.2, "%d%s" % (v, " m" if v == 20 else ""), 6.25, "normal", INK, "middle")
    svg.text(x, y + 6.2, "1:200 · 1 m = 5 mm · SCALE BAR 20 m = 100 mm", 5.25, "normal", GREY, "start")


def north_arrow(svg, cx, cy, deg, r=9.0):
    svg.circle(cx, cy, r, stroke=INK, sw=0.3)
    a = math.radians(deg)
    dx, dy = math.sin(a), -math.cos(a)
    tip = (cx + dx * r * 0.95, cy + dy * r * 0.95)
    tail = (cx - dx * r * 0.7, cy - dy * r * 0.7)
    left = (cx - dy * r * 0.28 - dx * r * 0.05, cy + dx * r * 0.28 - dy * r * 0.05)
    svg.line(tail[0], tail[1], tip[0], tip[1], stroke=INK, sw=0.4)
    svg.path("M%s %s L%s %s L%s %s Z" % (f3(tip[0]), f3(tip[1]), f3(cx + dy * r * 0.2), f3(cy - dx * r * 0.2),
                                         f3(cx - dy * r * 0.2), f3(cy + dx * r * 0.2)), stroke=INK, sw=0.2, fill=INK)
    svg.text(tip[0] + dx * 3.2, tip[1] + dy * 3.2 + 1.0, "N", 7.5, "bold", INK, "middle")


def key_plan(svg, x, y, size, env, highlight=None):
    k = size / (env[2] - env[0])
    bx, by = x, y
    svg.rect(bx, by, size, size, stroke=INK, sw=0.3, fill="#ffffff")
    if highlight:
        y0, y1 = highlight
        svg.rect(bx, by + (env[3] - y1) * k, size, (y1 - y0) * k, stroke="none", sw=0, fill="#cfd8e3")
    svg.rect(bx, by, size, size, stroke=INK, sw=0.3)
    svg.text(bx + size / 2, by + size + 4.5, "KEY PLAN", 5.25, "bold", GREY, "middle")


def table(svg, x, y, widths, rows, row_h=3.9, head=None, pt=6.25, aligns=None):
    cx = [x]
    for w in widths:
        cx.append(cx[-1] + w)
    yy = y
    if head:
        svg.rect(x, yy, sum(widths), row_h + 0.4, stroke="none", sw=0, fill="#eeeeee")
        for i, h in enumerate(head):
            svg.text(cx[i] + 1.2, yy + row_h - 0.9, h, 5.25, "bold", INK, "start")
        yy += row_h + 0.4
    for r in rows:
        for i, c in enumerate(r):
            al = (aligns[i] if aligns else "start")
            tx = cx[i] + (1.2 if al == "start" else widths[i] - 1.2)
            svg.text(tx, yy + row_h - 1.0, c, pt, "normal", "#222", al)
        svg.line(x, yy + row_h, x + sum(widths), yy + row_h, stroke="#dddddd", sw=0.08)
        yy += row_h
    return yy


def heading(svg, x, y, s, sub=""):
    svg.text(x, y, s, 8, "bold", INK, "start")
    if sub:
        svg.text(x + 40, y, sub, 5.25, "normal", GREY, "start")
    svg.line(x, y + 1.4, x + 200, y + 1.4, stroke=INK, sw=0.3)
    return y + 5.2


def legend(svg, x, y):
    y = heading(svg, x, y, "범례 LEGEND")
    items = [
        ("col", "구조 기둥 Ø0.9 (MODEL_VERIFIED)"), ("open", "슬래브 개구·튜브 외곽 (MODEL_VERIFIED)"),
        ("core", "코어 벽 (1F 검증 심볼 재사용·제안)"), ("wall", "구획벽 150 mm (PROPOSED)"),
        ("door", "문 + 개폐 반경 (PROPOSED)"), ("furn", "가구·집기 (PROPOSED)"),
        ("circ", "방문객 주 동선 (PROPOSED)"), ("tag", "실 번호 · 이름 · 면적(폴리곤 계산)"),
        ("svc", "서비스·반입 동선 → FR 반입 접점 (PROPOSED)"), ("prov", "미결 접점: 랜딩이 모델에 없음 (결정 D-01)"),
        ("proj", "에스컬레이터 축 투영 (MODEL_VERIFIED 축)"), ("hatch", "바닥판 없음 · 개구부 = 하부 개방 (해칭)"),
        ("rail", "가장자리 난간 제안 (미검증)"), ("thru", "개방부를 관통하는 기둥 (검증 위치)"),
        ("supp", "지원·BOH 실 (창고·주방·세척 등, PROPOSED)"),
    ]
    for key, label in items:
        cy = y - 1.3
        if key == "col":
            svg.circle(x + 5, cy, 1.5, stroke=INK, sw=0.3, fill=INK)
        elif key == "open":
            svg.circle(x + 5, cy, 2.0, stroke="#222", sw=0.3)
            svg.circle(x + 5, cy, 1.6, stroke="#222", sw=0.15)
        elif key == "core":
            svg.rect(x + 2, cy - 1.8, 6, 3.6, stroke=INK, sw=0.5, fill="#1a1a1a")
        elif key == "wall":
            svg.rect(x + 2, cy - 0.5, 6, 1.0, stroke="#222", sw=0.3, fill="#666")
        elif key == "door":
            svg.line(x + 2, cy + 1.5, x + 2, cy - 1.5, stroke="#444", sw=0.16)
            svg.path("M%s %s A3 3 0 0 1 %s %s" % (f3(x + 2), f3(cy - 1.5), f3(x + 5), f3(cy + 1.5)), stroke="#aaa", sw=0.09)
        elif key == "furn":
            svg.rect(x + 2.5, cy - 1.2, 5, 2.4, stroke="#444", sw=0.16, fill="#fff")
        elif key == "circ":
            svg.line(x + 1.5, cy, x + 8.5, cy, stroke="#2f5d8a", sw=0.18, dash=(2.2, 0.9, 0.5, 0.9))
        elif key == "tag":
            svg.circle(x + 5, cy, 1.7, stroke="#444", sw=0.16, fill="#fff")
            svg.text(x + 5, cy + 0.7, "07", 5.25, "bold", "#333", "middle")
        elif key == "svc":
            svg.line(x + 1.5, cy, x + 8.5, cy, stroke="#9a5b1e", sw=0.18, dash=(1.6, 0.8))
        elif key == "prov":
            svg.line(x + 1.5, cy, x + 7.0, cy, stroke="#2f5d8a", sw=0.16, dash=(0.8, 1.2))
            svg.circle(x + 8.2, cy, 0.9, stroke="#2f5d8a", sw=0.16, fill="#fff")
        elif key == "proj":
            svg.line(x + 1.5, cy, x + 8.5, cy, stroke="#7a3b8c", sw=0.14, dash=(3.0, 0.8, 0.6, 0.8))
        elif key == "hatch":
            svg.rect(x + 2, cy - 1.6, 6, 3.2, stroke="#8c8c8c", sw=0.1, fill="#ffffff")
            for k in range(0, 5):
                svg.line(x + 2 + k * 1.2, cy + 1.6, x + 2 + k * 1.2 + 1.2, cy - 1.6 + 2.0, stroke="#8c8c8c", sw=0.05)
        elif key == "rail":
            svg.line(x + 1.5, cy, x + 8.5, cy, stroke="#b3261e", sw=0.16, dash=(1.0, 0.5))
        elif key == "thru":
            svg.circle(x + 5, cy, 0.9, stroke="#000", sw=0.2, fill="#000")
            svg.circle(x + 5, cy, 1.9, stroke="#333", sw=0.12)
        elif key == "supp":
            svg.rect(x + 2, cy - 1.4, 6, 2.8, stroke="#444", sw=0.2, fill="#ebe7df")
        svg.text(x + 11, y, label, 6.25, "normal", "#222", "start")
        y += 4.6
    svg.text(x + 1, y + 1, "프로그램 색조", 6.25, "bold", INK, "start")
    xx = x + 24
    for p in ("retail", "fnb", "culture", "garden"):
        svg.rect(xx, y - 2.2, 5, 3.2, stroke="#888", sw=0.12, fill=TINT[p])
        svg.text(xx + 6.5, y + 0.4, PROG_KO[p], 5.25, "normal", "#222", "start")
        xx += 28
    return y + 5.0


def schedule_rows(d: Drawing):
    rows = []
    for r in sorted(d.rooms, key=lambda r: r["id"]):
        rows.append((r["id"], r["name"], PROG_KO.get(r["program"], r["program"]) + ("·지원" if r["kind"] == "support" else ""), format(r["area_m2"], ",.1f"),
                     "제안" if r["prov"] == PROPOSED else "심볼"))
    return rows


def areas_summary(d: Drawing, g_info):
    by = {}
    for r in d.rooms:
        by[r["program"]] = by.get(r["program"], 0.0) + r["poly"].area
    return by


def side_panel(svg, d: Drawing, info, x0, y0, width):
    colw = (width - 10) / 2
    xl, xr = x0, x0 + colw + 10
    y = legend(svg, xl, y0)
    # vertical elements (right column)
    yr = heading(svg, xr, y0, "수직 요소 VERTICAL ELEMENTS")
    seen = {}
    for v in d.meta.get("vertical", []):
        seen.setdefault(v["id"], v)
    rows = [(v["id"], v["name"][:26], "검증 개구" if "MODEL_VERIFIED" in v["status"] else "제안") for v in seen.values()]
    yr = table(svg, xr, yr, (22, colw - 22 - 24, 24), rows[:24], row_h=3.5, head=("ID", "명칭", "근거"), pt=5.6)
    # room schedule
    ys = max(y, yr) + 5
    ys = heading(svg, x0, ys, "실 일람 ROOM SCHEDULE", "면적 = 폴리곤 계산값(기둥 면적 포함) · 층 면적 근거는 하단 요약")
    rows = schedule_rows(d)
    half = (len(rows) + 1) // 2
    head = ("No", "실명", "구분", "면적 ㎡", "근거")
    wid = (8, colw - 8 - 26 - 17 - 12, 26, 17, 12)
    al = ("start", "start", "start", "end", "start")
    table(svg, xl, ys, wid, rows[:half], head=head, aligns=al, pt=5.8)
    table(svg, xr, ys, wid, rows[half:], head=head, aligns=al, pt=5.8)
    return ys + 4.3 * (half + 1)


def summary_and_status(svg, d: Drawing, info, x0, y0, width):
    colw = (width - 10) / 2
    xl, xr = x0, x0 + colw + 10
    y = heading(svg, xl, y0, "면적 요약 AREA SUMMARY", "㎡")
    rows = [("층판 외곽 (MODEL_VERIFIED)", format(info["slab_gross_m2"], ",.1f")),
            ("층판 개구 (MODEL_VERIFIED)", format(info["opening_m2"], ",.1f")),
            ("층판 순면적 (MODEL_VERIFIED)", format(info["slab_net_m2"], ",.1f"))]
    for k, lab in (("main", "공용 판매·객석·문화 주 공간"), ("support", "지원·BOH (창고·주방·세척)"), ("hall", "공용 홀·통로"),
                   ("garden", "정원 (산책로·식재·휴게)"), ("restroom", "화장실")):
        v = info.get("room_area_by_role", {}).get(k)
        if v:
            rows.append(("제안 · " + lab, format(v, ",.1f")))
    rows.append(("제안 실 합계 (폴리곤)", format(sum(info["room_area_by_program"].values()), ",.1f")))
    y = table(svg, xl, y, (colw - 26, 26), rows, row_h=3.7, aligns=("start", "end"), pt=6.0)
    svg.text(xl + 1, y + 3.4, "※ 제안 실 합계 + 코어·튜브·복도·기둥 = 층판 순면적 아님(복도·미분류 틈 제외)", 5.25, "normal", GREY, "start")
    yy = heading(svg, xr, y0, "상태·한계 STATUS & LIMITS")
    lines = [
        "MODEL_VERIFIED: 층판 외곽·개구, 기둥, 코어 외곽, 튜브 개구, 에스컬레이터 절단부·축, 파사드 부재.",
        "PROPOSED_DESIGN: 구획벽, 문, 실, 가구, 동선, 난간, 코어·화장실·튜브 내부(1F 검증 심볼 재사용 포함).",
        "법규(피난·방화·장애인) 적합성, 구조 규격, 설비는 검증하지 않았다. 승인 아님.",
        "화장실 위치는 1F 승인 위치(사용자 승인 이동 반영)를 수직으로 쌓았다. 모델 사실 아님.",
    ] + ["미결 · " + u["id"] + (" → " + u["decision"] if u.get("decision") else "") for u in d.meta.get("graph", {}).get("unresolved", [])[:6]] \
      + ["NOTE · " + n[:92] for n in d.notes if not n.startswith(("ESC_LANDING", "CORE_", "TUBE_"))][:3]
    for ln in lines:
        svg.text(xr + 1, yy, ln, 5.6, "normal", "#333", "start")
        yy += 3.9


def level_stack(svg, x, y, w, info, program_by_floor, floors):
    cw = w / len(floors)
    svg.text(x, y - 3, "LEVEL STACK · 층 적층 (모델 FFL · 주 프로그램)", 6.25, "bold", INK, "start")
    for i, f in enumerate(floors):
        cx = x + i * cw
        cur = f == info["floor"]
        svg.rect(cx, y, cw, 26, stroke=INK if cur else "#999", sw=0.5 if cur else 0.15, fill="#e3ebf5" if cur else "#ffffff")
        svg.text(cx + cw / 2, y + 5.5, f, 7.5 if cur else 6.25, "bold" if cur else "normal", INK, "middle")
        svg.text(cx + cw / 2, y + 11.0, "%+.1f" % info["levels"][f], 5.0, "normal", GREY, "middle")
        prog = program_by_floor.get(f, "")
        for j, part in enumerate(prog.split("/")[:3]):
            svg.text(cx + cw / 2, y + 15.5 + j * 3.5, part, 4.6, "normal", "#333", "middle")


def compose_a1(d: Drawing, info, program_by_floor, floors) -> Svg:
    W, H = A1
    svg = Svg(W, H, "%s %s plan A1 1:200" % (PROJECT, info["floor"]))
    frame(svg, W, H, 10)
    win = window_full()
    ox, oy = 22.0, 18.0
    xf = Xf(win, (ox, oy))
    draw_plan(svg, d, xf)
    pw, ph = xf.rect[2], xf.rect[3]
    scale_bar(svg, ox + 6, oy + ph + 14)
    north_arrow(svg, ox + pw - 18, oy + ph + 12, info["north_deg"])
    level_stack(svg, ox, oy + ph + 40, 400, info, program_by_floor, floors)
    px = ox + pw + 14
    yend = side_panel(svg, d, info, px, 24, W - 10 - px - 4)
    summary_and_status(svg, d, info, px, max(yend + 6, 380), W - 10 - px - 4)
    title_block(svg, 10, 524, W - 10, 584, info, "SHEET 1/1 · A1 841×594", "A1 841×594 mm")
    return svg


def compose_a3(d: Drawing, info, half: str) -> Svg:
    W, H = A3
    n = 1 if half == "N" else 2
    svg = Svg(W, H, "%s %s plan A3 %d/2 1:200" % (PROJECT, info["floor"], n))
    frame(svg, W, H, 7)
    env = window_full()
    split = 9.0                                              # grid line 4 (y = 9)
    win = (env[0], split - 4.0, env[2], env[3]) if half == "N" else (env[0], env[1], env[2], split + 4.0)
    ox, oy = 30.0, 14.0
    xf = Xf(win, (ox, oy))
    draw_plan(svg, d, xf, clip_id="planclip_%s" % half)
    pw, ph = xf.rect[2], xf.rect[3]
    mx0, my = xf.pt(win[0], split)[0], xf.pt(win[0], split)[1]
    svg.line(ox, my, ox + pw, my, stroke="#9b1c1c", sw=0.2, dash=(6, 1.5, 1, 1.5))
    other = "2/2 남측" if half == "N" else "1/2 북측"
    svg.text(ox + pw - 2, my - 1.5, "MATCH LINE y=+9.000 (그리드 4) → 시트 %s" % other, 5.6, "bold", "#9b1c1c", "end")
    scale_bar(svg, ox + 4, oy + ph + 12)
    north_arrow(svg, ox + 160, oy + ph + 12, info["north_deg"], r=7.0)
    key_plan(svg, ox + 200, oy + ph + 3, 22, (-9.0, -18.0, 45.0, 36.0), (split, 36.0) if half == "N" else (-18.0, split))
    svg.text(ox + 235, oy + ph + 8, STATUS_LINE, 6.0, "bold", "#9b1c1c", "start")
    svg.text(ox + 235, oy + ph + 13, "범례·실 일람·면적: A1 시트 참조 (%s)" % info["sheet_id"], 5.6, "normal", GREY, "start")
    title_block(svg, 7, 250, W - 7, 283, info, "SHEET %d/2 · A3 420×297 · %s" % (n, "북측 절반" if half == "N" else "남측 절반"), "A3 420×297 mm, 분할 %d/2" % n)
    return svg
