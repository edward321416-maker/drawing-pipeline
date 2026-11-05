"""C-T14 층 도면 독립 QA — 렌더러가 스스로 적은 check.json을 믿지 않고 산출 파일(SVG·PDF·PNG·DXF)과 모델 slice JSON을 직접 대조한다.

    python -I tools/t14_floor_qa.py --run <후보 폴더> --floor 3F --glb <전층.glb> [--sheet-dir 3F_PILOT] [--suffix _cleanline]

검사 (실패는 숨기지 않고 FAIL로 남긴다):
  PROV   입력 GLB·slice·산출물 SHA256
  SIZE   PDF 쪽 크기 420×297 mm, PNG 300 dpi 이상, SVG width/height/viewBox가 축척과 일치
  VECTOR PDF에 래스터 이미지 0, 글자 추출 가능, Level S 표기 존재
  COLS   모델 기둥 전부가 시트에 (실선 또는 점선으로) 위치 일치, 1:200과 1:100 4타일이 같은 월드 위치
  TILE   2×2 타일이 건물 범위를 덮고 겹침이 있다
  LINE   선 굵기 분포, 흰색 덮개선, 중복 선분, 계단형 폴리라인
  DXF    레이어·객체 수, 건물 범위
  LEVELS Level S 가정: 벽·문 미검증 표시, 가구 PROPOSED_ONLY
"""
import argparse
import collections
import hashlib
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
import pipeline_common as pc  # noqa: E402

A3 = (420.0, 297.0)
NUM = re.compile(r"-?\d+(?:\.\d+)?(?:e-?\d+)?")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read(p):
    return open(p, encoding="utf-8").read()


def layer_blocks(svg):
    out = {}
    for m in re.finditer(r'<g id="(\w+)"([^>]*)>(.*?)</g>', svg, re.S):
        out[m.group(1)] = m.group(3)
    return out


def path_points(d):
    """SVG path d → 끝점 목록 (M/L/A/Z만 쓰는 렌더러 출력 전용)."""
    pts = []
    for cmd, args in re.findall(r"([MLAHVZmlahvz])([^MLAHVZmlahvz]*)", d):
        nums = [float(x) for x in NUM.findall(args)]
        if cmd in "ML" and len(nums) >= 2:
            for i in range(0, len(nums) - 1, 2):
                pts.append((nums[i], nums[i + 1]))
        elif cmd == "A" and len(nums) >= 7:
            for i in range(0, len(nums) - 6, 7):
                pts.append((nums[i + 5], nums[i + 6]))
    return pts


def circle_center(pts):
    """호 끝점들에 원을 맞춰 중심을 구한다(Kåsa 최소제곱). 끝점 간격이 고르지 않아도 정확하다. 2점이면 지름 양끝 → 중점."""
    if len(pts) == 2:
        return ((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2)
    import numpy as np
    P = np.array(pts, dtype=float)
    A = np.c_[2 * P[:, 0], 2 * P[:, 1], np.ones(len(P))]
    b = (P ** 2).sum(axis=1)
    sol = np.linalg.lstsq(A, b, rcond=None)[0]
    return (float(sol[0]), float(sol[1]))


def col_centers(block):
    """cols 레이어의 기둥 → [(cx, cy, dashed)] 시트 좌표."""
    out = []
    for m in re.finditer(r"<path ([^>]*?)/?>", block):
        a = m.group(1)
        d = re.search(r'(?:^|\s)d="([^"]+)"', a)
        if not d:
            continue
        pts = path_points(d.group(1))
        if len(pts) < 2:
            continue
        if pts[0] == pts[-1]:
            pts = pts[:-1]
        uniq = list(dict.fromkeys(pts))
        out.append(circle_center(uniq) + ("stroke-dasharray" in a,))
    return out


def segments_of(block, layer):
    """폴리라인·선·직선 path의 선분들 (시트 단위)."""
    segs = []
    for m in re.finditer(r'<polyline[^>]*points="([^"]+)"', block):
        n = [float(x) for x in NUM.findall(m.group(1))]
        pts = list(zip(n[0::2], n[1::2]))
        segs.append(pts)
    for m in re.finditer(r"<line ([^>]*)/?>", block):
        g = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        try:
            segs.append([(float(g["x1"]), float(g["y1"])), (float(g["x2"]), float(g["y2"]))])
        except KeyError:
            pass
    return segs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--floor", default="3F")
    ap.add_argument("--glb", required=True)
    ap.add_argument("--sheet-dir", default="3F_PILOT")
    ap.add_argument("--suffix", default="_cleanline")
    ap.add_argument("--report", default=None)
    ap.add_argument("--no-tiles", action="store_true", help="1:200 단일 시트만 검사(1:100 타일 검사 생략). 도면집 기준층 평면용")
    ap.add_argument("--ref-dir", default=None, help="1층 기준 폴더(reference_1F): camera_bounds.json, floor_1F_slice.json, 사용자 제공 1층 PDF")
    a = ap.parse_args()
    run = os.path.abspath(a.run)
    sd = os.path.join(run, a.sheet_dir)
    fl = a.floor
    res = []

    def chk(code, ok, msg, **kw):
        res.append({"code": code, "status": "PASS" if ok else "FAIL", "msg": msg, **kw})

    # ── 입력과 산출물 ──
    names = {"1to200": "plan_%s_A3_1to200%s" % (fl, a.suffix)}
    for i in range(1, 1 if a.no_tiles else 5):
        names["1to100_t%d" % i] = "plan_%s_A3_1to100_t%d%s" % (fl, i, a.suffix)
    sheets = {k: os.path.join(sd, v) for k, v in names.items()}
    slice_p = os.path.join(run, "raw_slices", "floor_%s_slice.json" % fl)
    layout_p = os.path.join(run, "vector", "floor_%s_layout.json" % fl)
    prov = {"glb": {"path": os.path.abspath(a.glb), "sha256": sha256(a.glb)},
            "slice": {"path": slice_p, "sha256": sha256(slice_p)},
            "layout": {"path": layout_p, "sha256": sha256(layout_p)}, "sheets": {}}
    for k, base in sheets.items():
        prov["sheets"][k] = {e: {"path": base + "." + e, "sha256": sha256(base + "." + e)} for e in ("svg", "pdf", "png")}
    chk("PROV", True, "입력·산출물 해시 기록", files=1 + 1 + 1 + 3 * len(sheets))

    sl = pc.load_json(slice_p)
    lay = pc.load_json(layout_p)
    bx0, by0, bx1, by1 = lay["building"]
    model_cols = [g.centroid for _, g in pc.cut_geometries(sl).get("column", [])]

    svgs = {k: read(b + ".svg") for k, b in sheets.items()}
    # ── SIZE ──
    import fitz
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    scale_of = {k: (200 if k == "1to200" else 100) for k in sheets}
    for k, b in sheets.items():
        doc = fitz.open(b + ".pdf")
        pg = doc[0]
        wmm, hmm = pg.rect.width * 25.4 / 72, pg.rect.height * 25.4 / 72
        chk("SIZE.pdf.%s" % k, abs(wmm - A3[0]) < 0.3 and abs(hmm - A3[1]) < 0.3 and len(doc) == 1, "PDF 1쪽 %.2f×%.2f mm" % (wmm, hmm))
        imgs = pg.get_images(full=True)
        chk("VECTOR.noraster.%s" % k, len(imgs) == 0, "PDF 내장 래스터 이미지 %d개" % len(imgs))
        txt = pg.get_text()
        chk("VECTOR.text.%s" % k, "SCHEMATIC" in txt and "1:%d" % scale_of[k] in txt, "PDF 글자 추출: Level S 표기·축척 표기 포함")
        chk("VECTOR.drawings.%s" % k, len(pg.get_drawings()) > 100, "PDF 벡터 도형 %d개" % len(pg.get_drawings()))
        im = Image.open(b + ".png")
        dpi = im.size[0] / (A3[0] / 25.4)
        chk("SIZE.png.%s" % k, dpi >= 299 and abs(im.size[0] / im.size[1] - A3[0] / A3[1]) < 0.002, "PNG %dx%d = %.0f dpi" % (im.size[0], im.size[1], dpi))
        s = svgs[k]
        m = re.search(r'width="([\d.]+)mm" height="([\d.]+)mm" viewBox="0 0 ([\d.]+) ([\d.]+)"', s)
        ok = bool(m) and abs(float(m.group(1)) - A3[0]) < 1e-6 and abs(float(m.group(2)) - A3[1]) < 1e-6 and abs(float(m.group(3)) - A3[0] * scale_of[k] / 1000) < 1e-3
        chk("SIZE.svg.%s" % k, ok, "SVG 420×297 mm, viewBox 폭 = 420 × 축척/1000 (1 단위 = 1 m)")
        # 축척 막대 상자가 건물(월드 범위를 시트 좌표로 옮긴 것)을 가리지 않는다
        wnd = pc.load_json(b + "_check.json")["window_world"]
        bld = (bx0 - wnd[0], wnd[3] - by1, bx1 - wnd[0], wnd[3] - by0)                      # 시트 좌표(단위 m): x0, y0(위), x1, y1(아래)
        allw = [tuple(float(v) for v in m) for m in re.findall(r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)" fill="#ffffff"', s)]
        boxes = [bx for bx in allw if abs(bx[3] - 12.5 * scale_of[k] / 1000) < 1e-3]          # 막대 상자 높이 = 12.5 mm 종이
        hit = [bx for bx in boxes if not (bx[0] + bx[2] <= bld[0] or bx[0] >= bld[2] or bx[1] + bx[3] <= bld[1] or bx[1] >= bld[3])]
        chk("SIZE.bar_clear.%s" % k, bool(boxes) and not hit, "축척 막대 상자 %d개, 건물과 겹침 %d개" % (len(boxes), len(hit)), hits=hit)
        sb = re.findall(r'<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)" height="([\d.]+)" fill="#111"', s)
        chk("SIZE.bar.%s" % k, len(sb) == 2, "축척 막대 검은 칸 %d개 (기대 2)" % len(sb))
        if len(sb) == 2:
            bar = {200: [0, 2, 5, 10], 100: [0, 1, 2, 5, 10]}[scale_of[k]]
            w1, w2 = float(sb[0][1]), float(sb[1][1])
            # SVG 1 단위 = 월드 1 m 이므로 막대 칸 폭(단위)이 곧 그 칸이 뜻하는 실제 길이(m)다
            chk("SIZE.barlen.%s" % k, abs(w1 - (bar[1] - bar[0])) < 1e-3 and abs(w2 - (bar[3] - bar[2])) < 1e-3,
                "검은 칸 폭 %.2f·%.2f m (기대 %d·%d m) → 막대가 실제 축척과 일치" % (w1, w2, bar[1] - bar[0], bar[3] - bar[2]))

    # ── COLS: 모델 기둥 34개 대조 ──
    k0 = scale_of["1to200"]
    cxy = ((bx0 + bx1) / 2, (by0 + by1) / 2)
    b200 = (cxy[0] - A3[0] * k0 / 2000, cxy[1] + A3[1] * k0 / 2000)                     # b0, b3
    cols200 = col_centers(layer_blocks(svgs["1to200"]).get("cols", ""))
    world200 = [(b200[0] + x, b200[1] - y, d) for x, y, d in cols200]
    miss, solid, dashed = [], 0, 0
    for c in model_cols:
        hit = min(world200, key=lambda w: math.hypot(w[0] - c.x, w[1] - c.y), default=None)
        if hit is None or math.hypot(hit[0] - c.x, hit[1] - c.y) > 0.05:
            miss.append((round(c.x, 2), round(c.y, 2)))
        elif hit[2]:
            dashed += 1
        else:
            solid += 1
    chk("COLS.model_vs_sheet", not miss and len(world200) == len(model_cols), "모델 기둥 %d개 → 1:200 시트 %d개 (실선 %d + 점선 %d), 누락 %d" % (len(model_cols), len(world200), solid, dashed, len(miss)), missing=miss)

    # ── TILE: 2×2 타일 위치 ──
    if not a.no_tiles:
        hw, hh = A3[0] * 100 / 2000, A3[1] * 100 / 2000
        wins, centers = {}, {}
        for t in range(1, 5):                                                        # 타일 창은 렌더러가 check.json에 적은 월드 창을 쓰되, 아래에서 SVG 기둥 위치로 다시 검증한다
            w = pc.load_json(sheets["1to100_t%d" % t] + "_check.json")["window_world"]
            wins["1to100_t%d" % t] = tuple(w)
            centers["1to100_t%d" % t] = ((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
        cover_x = min(w[0] for w in wins.values()) <= bx0 and max(w[2] for w in wins.values()) >= bx1
        cover_y = min(w[1] for w in wins.values()) <= by0 and max(w[3] for w in wins.values()) >= by1
        ov_x = wins["1to100_t1"][2] - wins["1to100_t2"][0]
        ov_y = wins["1to100_t3"][3] - wins["1to100_t1"][1]                            # 월드 y는 위로 증가: 아래 타일(t3)의 윗변 − 위 타일(t1)의 아랫변 > 0 이면 겹침
        chk("TILE.cover", cover_x and cover_y, "4타일이 건물 %.1f×%.1f m를 덮음" % (bx1 - bx0, by1 - by0))
        chk("TILE.overlap", ov_x > 0 and ov_y > 0, "타일 겹침 가로 %.1f m, 세로 %.1f m (누락 없음)" % (ov_x, ov_y))
        seen = {}
        bad_tile = []
        for k, c in centers.items():
            b0, b3 = c[0] - hw, c[1] + hh
            for x, y, d in col_centers(layer_blocks(svgs[k]).get("cols", "")):
                wx, wy = b0 + x, b3 - y
                if not (wins[k][0] <= wx <= wins[k][2] and wins[k][1] <= wy <= wins[k][3]):
                    continue
                ref = min(world200, key=lambda w: math.hypot(w[0] - wx, w[1] - wy))
                if math.hypot(ref[0] - wx, ref[1] - wy) > 0.05 or ref[2] != d:
                    bad_tile.append((k, round(wx, 2), round(wy, 2)))
                seen[(round(ref[0], 1), round(ref[1], 1))] = True
        chk("COLS.tiles_vs_overview", not bad_tile, "1:100 타일의 기둥이 1:200과 같은 월드 위치·같은 선 종류", mismatches=bad_tile[:10])
        chk("COLS.tiles_union", len(seen) >= 30, "4타일 기둥 합집합 %d개(경계 걸침 포함)" % len(seen))

    # ── LINE ──
    for k, s in svgs.items():
        k_ = scale_of[k] / 1000.0
        mmper = A3[0] / float(re.search(r'viewBox="0 0 ([\d.]+)', s).group(1))
        lw = collections.Counter()
        for m in re.finditer(r'stroke-width="([\d.]+)"', s):
            lw[round(float(m.group(1)) * mmper, 2)] += 1
        thin = {w: n for w, n in lw.items() if w < 0.04}
        chk("LINE.weights.%s" % k, not thin and max(lw) <= 0.6, "선 굵기(mm) 분포 %s" % dict(sorted(lw.items())), too_thin=thin)
        white = [m for m in re.finditer(r'<(?:path|polyline|line)[^>]*stroke="#(?:fff|ffffff|FFFFFF)"[^>]*>', s)]
        white = [m for m in white if 'fill="none"' in m.group(0) or "<polyline" in m.group(0) or "<line" in m.group(0)]
        blocks = layer_blocks(s)
        white_nonlegend = sum(1 for lyr, b in blocks.items() if lyr not in ("legend", "bgdots") for _ in re.finditer(r'<(?:polyline|line)[^>]*stroke="#(?:fff|ffffff)"', b))
        chk("LINE.whiteout.%s" % k, white_nonlegend == 0, "흰색 덮개선 %d개 (도면 레이어)" % white_nonlegend)
        # 중복 선분
        dup = 0
        stair = 0
        tiny_total = 0
        per_layer = collections.Counter()
        seen_seg = collections.Counter()
        for lyr, b in blocks.items():
            for pts in segments_of(b, lyr):
                tiny = 0
                axis = []
                for p, q in zip(pts, pts[1:]):
                    dx, dy = (q[0] - p[0]) * mmper, (q[1] - p[1]) * mmper
                    ln = math.hypot(dx, dy)
                    key = (lyr, tuple(sorted([(round(p[0], 3), round(p[1], 3)), (round(q[0], 3), round(q[1], 3))])))
                    if ln > 0.02:
                        seen_seg[key] += 1
                    if ln < 0.4:
                        tiny += 1
                        axis.append("H" if abs(dy) < 1e-6 else ("V" if abs(dx) < 1e-6 else "D"))
                    else:
                        axis.append("-")
                streak = 0
                best = 0
                prev = None
                for t in axis:
                    if t in ("H", "V") and prev in ("H", "V") and t != prev:
                        streak += 1
                        best = max(best, streak)
                    else:
                        streak = 0
                    prev = t
                if best >= 6:
                    stair += 1
                    per_layer[lyr] += 1
                tiny_total += tiny
        for key, n in seen_seg.items():
            if n > 1:
                dup += 1
                per_layer[key[0] + ":dup"] += 1
        chk("LINE.ghost_dup.%s" % k, dup == 0, "중복 선분(같은 레이어·같은 끝점) %d개" % dup, by_layer=dict(per_layer))
        chk("LINE.stairstep.%s" % k, stair == 0, "계단형 직교 폴리라인(0.4 mm 미만 H/V 6회 이상 교대) %d개" % stair, tiny_segments=tiny_total)

    # ── DXF ──
    import ezdxf
    dxf_p = os.path.join(run, "cad", "floor_%s.dxf" % fl)
    doc = ezdxf.readfile(dxf_p)
    cnt = collections.Counter(e.dxf.layer for e in doc.modelspace())
    chk("DXF.layers", len(cnt) >= 3, "DXF 레이어 %d개, 객체 %d개" % (len(cnt), sum(cnt.values())), layers=dict(cnt))
    chk("DXF.scope", True, "DXF는 층 모델공간 단일 파일(시트 축척·타일 분할 아님). 시트별 DXF 익스포터는 미구현 → 후속", note="NOT_SHEET_SCALED")
    prov["dxf"] = {"path": dxf_p, "sha256": sha256(dxf_p)}

    # ── ORIENT: 1층과 같은 방향체계인가 (페이지 회전·SVG 변환·진북 화살표·같은 요소의 위치·타일 사분면) ──
    if a.ref_dir:
        ref = os.path.abspath(a.ref_dir)
        rb = pc.load_json(os.path.join(ref, "camera_bounds.json"))
        r1 = pc.load_json(os.path.join(ref, "floor_1F_slice.json"))
        ref_north = rb["frame"]["north_deg"]
        own = pc.load_json(os.path.join(run, "raw_slices", "camera_bounds.json"))
        chk("ORIENT.north_frame", abs(own["frame"]["north_deg"] - ref_north) < 0.05,
            "3F 도면틀 north_deg %.3f ↔ 1층 마스터 %.3f (허용 0.05°)" % (own["frame"]["north_deg"], ref_north))
        for pdf in sorted(f for f in os.listdir(ref) if f.lower().endswith(".pdf")):
            chk("ORIENT.ref_pdf_rotate", fitz.open(os.path.join(ref, pdf))[0].rotation == 0, "1층 기준 PDF /Rotate = 0 (%s)" % pdf)
        for k, b in sheets.items():
            rot = fitz.open(b + ".pdf")[0].rotation
            chk("ORIENT.pdf_rotate.%s" % k, rot == 0, "PDF /Rotate = %d" % rot)
            s = svgs[k]
            chk("ORIENT.svg_transform.%s" % k, not re.search(r"\btransform\s*=", s), "SVG에 transform 속성 없음(회전·축 교환이 시트 단계에서 들어가지 않음)")
            ln = re.findall(r'<line x1="([\d.\-]+)" y1="([\d.\-]+)" x2="([\d.\-]+)" y2="([\d.\-]+)"', s)
            if len(ln) == 1:
                x1, y1, x2, y2 = (float(v) for v in ln[0])
                ang = math.degrees(math.atan2(x2 - x1, -(y2 - y1)))                      # 위쪽에서 시계 방향
                chk("ORIENT.arrow.%s" % k, abs(((ang - ref_north + 180) % 360) - 180) < 0.1, "시트에 그려진 진북 화살표 %.2f° ↔ 1층 기준 %.2f°" % (ang, ref_north))
            else:
                chk("ORIENT.arrow.%s" % k, False, "진북 화살표 선 %d개(기대 1)" % len(ln))

        def toks(sl_, bb):
            out = {}
            for kind, items in pc.cut_geometries(sl_).items():
                if kind not in ("tube_wall", "core_wall", "shaft"):
                    continue
                for it, g in items:
                    nm = it.get("name_ko") or ""
                    m = re.search(r"코어 ([A-D])", nm)
                    key = ("core " + m.group(1)) if m else None
                    if key is None:
                        m = re.search(r"\b(T[1-4]|M[12]|PL|FR|EV[12])\b", nm)
                        key = m.group(1) if m else (("capsule E" if re.search(r"캡슐\s*동|동측", nm) else "capsule W") if "캡슐" in nm else None)   # 동·서 캡슐은 다른 요소(1층 마스터엔 서측만 있다)
                    if key and key not in out:
                        out[key] = (g.centroid.x - bb["xmin"], g.centroid.y - bb["ymin"])
            return out
        t3, t1 = toks(sl, own["building"]), toks(r1, rb["building"])
        shared = sorted(set(t3) & set(t1))
        worst = max((math.hypot(t3[k_][0] - t1[k_][0], t3[k_][1] - t1[k_][1]) for k_ in shared), default=None)
        bad = {k_: (tuple(round(v, 1) for v in t3[k_]), tuple(round(v, 1) for v in t1[k_])) for k_ in shared if math.hypot(t3[k_][0] - t1[k_][0], t3[k_][1] - t1[k_][1]) > 1.0}
        chk("ORIENT.same_elements_same_place", len(shared) >= 12 and not bad,
            "1층 마스터와 이름이 같은 요소 %d개의 건물 모서리 기준 위치 차 최대 %s m (허용 1.0 m)" % (len(shared), "%.2f" % worst if worst is not None else "?"), mismatched_3F_vs_1F=bad, shared=shared)
        # 타일 사분면: t1 좌상, t2 우상, t3 좌하, t4 우하 (도면 y는 위로 증가)
        bcx, bcy = (bx0 + bx1) / 2, (by0 + by1) / 2
        want = {1: (-1, 1), 2: (1, 1), 3: (-1, -1), 4: (1, -1)}
        corner = {1: (bx0, by1), 2: (bx1, by1), 3: (bx0, by0), 4: (bx1, by0)}
        for t in (() if a.no_tiles else range(1, 5)):
            kk = "1to100_t%d" % t
            cj = pc.load_json(sheets[kk] + "_check.json")
            w = cj["window_world"]
            cx_, cy_ = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
            sx, sy = (1 if cx_ > bcx else -1), (1 if cy_ > bcy else -1)
            chk("ORIENT.tile_quadrant.t%d" % t, (sx, sy) == want[t] and cj.get("tag") == "_t%d" % t,
                "t%d 창 중심이 건물 중심의 %s%s (기대 %s%s), tag=%s" % (t, "우" if sx > 0 else "좌", "상" if sy > 0 else "하", "우" if want[t][0] > 0 else "좌", "상" if want[t][1] > 0 else "하", cj.get("tag")))
            cc = min(model_cols, key=lambda c: math.hypot(c.x - corner[t][0], c.y - corner[t][1]))
            b0_, b3_ = w[0], w[3]
            cols_t = [(b0_ + x, b3_ - y) for x, y, d in col_centers(layer_blocks(svgs[kk]).get("cols", ""))]
            present = any(math.hypot(wx - cc.x, wy - cc.y) < 0.05 for wx, wy in cols_t)
            txt = fitz.open(sheets[kk] + ".pdf")[0].get_text()
            chk("ORIENT.tile_corner_column.t%d" % t, present and ("[%d/4]" % t) in txt,
                "t%d 시트에 %s 모서리에 가장 가까운 모델 기둥(%.1f, %.1f)이 있고 제목이 [%d/4]" % (t, ["", "좌상", "우상", "좌하", "우하"][t], cc.x, cc.y, t))

    # ── LEVELS ──
    for k, b in sheets.items():
        cj = pc.load_json(b + "_check.json")
        s = svgs[k]
        ok = cj.get("level") == "S_SCHEMATIC" and cj.get("walls_doors_verified") is False and cj.get("furniture_status") == "PROPOSED_ONLY" \
            and "walls_doors=UNVERIFIED" in s and 'data-status="PROPOSED_ONLY"' in s
        chk("LEVELS.%s" % k, ok, "Level S 표기: 벽·문 미검증, 가구 PROPOSED_ONLY (check.json·SVG 메타 일치)")
        chk("LEVELS.nodoor.%s" % k, cj.get("door_gaps_punched") == 0 and cj.get("curtain_doors") == 0 and cj.get("entrance_boxes_drawn") == 0,
            "문 개구·커튼월 문·출입구 상자 0 (모델에 없는 문을 확정하지 않음)")
        chk("LEVELS.counts.%s" % k, cj.get("columns_in_model") == len(model_cols), "check.json 기둥 수 = slice 기둥 수 (%s = %d)" % (cj.get("columns_in_model"), len(model_cols)))
        # 카운터가 아니라 SVG 내용을 직접 본다: 문·커튼월 레이어에 도형이 없어야 하고, 캡슐 입구를 렌더러가 만들지 않아야 한다
        bl = layer_blocks(s)
        empty = {lyr: len(re.findall(r"<(?:path|polyline|line|circle|rect)\b", bl.get(lyr, ""))) for lyr in ("doors", "envelope")}
        chk("LEVELS.nodoor_svg.%s" % k, sum(empty.values()) == 0 and cj.get("capsule_entrance_generated") is False,
            "SVG의 문·외피(커튼월) 레이어 도형 %s, 캡슐 입구 생성 %s" % (empty, cj.get("capsule_entrance_generated")))
        # 모델의 절단 요소 중 전용 기호가 없는 종류는 윤곽으로라도 그려져야 한다(조용한 누락 금지)
        want = collections.Counter(it.get("kind") for it in sl["elements"] if it.get("kind") in ("stair", "facade"))
        got = cj.get("model_only_outlines_drawn", {})
        chk("ELEMENTS.furn_clear.%s" % k, cj.get("furniture_overlapping_model_outlines") == 0, "가구와 모델 에스컬레이터·입면 부재 윤곽의 겹침 %s개" % cj.get("furniture_overlapping_model_outlines"))
        chk("ELEMENTS.model_only.%s" % k, dict(want) == got, "모델 에스컬레이터·입면 부재 %s → 그려진 윤곽 %s" % (dict(want), got))

    fails = [r for r in res if r["status"] == "FAIL"]
    report = {"floor": fl, "run": run, "pass": len(res) - len(fails), "fail": len(fails), "total": len(res), "checks": res, "provenance": prov}
    rp = a.report or os.path.join(sd, "floor_%s_geometry_qa.json" % fl)
    json.dump(report, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in res:
        print("%-4s %-28s %s" % (r["status"], r["code"], r["msg"]))
    print("QA %s: %d/%d PASS, %d FAIL → %s" % (fl, report["pass"], report["total"], report["fail"], os.path.abspath(rp)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
