"""자율 QA: 도면 파이프라인 산출물을 자동 검증한다. 하나라도 실패하면 종료 코드 1.

    python tests/verify_pipeline.py --out output/drawing_pipeline [--floors 1F,2F] [--tol-px 1.5]

a) 절단 폐곡선: 모든 절단 폴리곤이 shapely에서 is_valid이고 면적 > 0, 절단 선분의 98 % 이상이 폐곡선 경계에 포함된다.
b) Y축 뒤집힘·정렬: 기준 기둥 꼭짓점이 (1) SVG 파일 좌표, (2) SVG를 래스터화한 이미지, (3) Blender 정렬 마스크에서 같은 정규화 픽셀(u,v)에 놓인다.
   기둥 전체의 SVG↔마스크 무게중심 차이도 잰다.
c) DXF: ezdxf.readfile()이 열리고 A-WALL-CUT·A-ANNO-DIMS·A-ANNO-TEXT에 객체가 있다.
d) 합성: 글자 상자끼리·절단 요소와 겹치지 않고, 합성 PNG의 기둥 위치가 어둡다(벡터 층이 정렬돼 얹혔다).
e) A3 도면(architectural_plan_renderer): 종이 420×297·축척(1층 1:500, 상층 1:100), 가구 흰 채움·가는 선, 커튼월 가는 선,
   충돌 지표 0, 확대 점검 그림 800×800.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

import ezdxf
import numpy as np
from PIL import Image
from shapely.geometry import LineString, box
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import pipeline_common as pc  # noqa: E402


class Report:
    def __init__(self):
        self.rows = []

    def add(self, floor, name, ok, detail=""):
        self.rows.append({"floor": floor, "check": name, "ok": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + "%-4s %-34s %s" % (floor, name, detail))

    @property
    def failed(self):
        return [r for r in self.rows if not r["ok"]]


def blob_centroid(img, cx, cy, half):
    h, w = img.shape
    x0, x1 = max(0, int(cx - half)), min(w, int(cx + half) + 1)
    y0, y1 = max(0, int(cy - half)), min(h, int(cy + half) + 1)
    win = img[y0:y1, x0:x1] < 128
    ys, xs = np.nonzero(win)
    if len(xs) < 4:
        return None
    return xs.mean() + x0, ys.mean() + y0


def check_closed(rep, floor, sl):
    bad, tot, uncovered, total_len = [], 0, 0.0, 0.0
    for it in sl["elements"]:
        segs = [LineString([(s[0], s[1]), (s[2], s[3])]) for s in it["segments"] if (s[0], s[1]) != (s[2], s[3])]
        if not segs:
            continue
        g = pc.polygons_from_segments(it["segments"])
        tot += 1
        polys = list(pc.iter_polygons(g))
        if g.is_empty or not g.is_valid or g.area <= 0:
            bad.append(it["name"])
            continue
        bnd = unary_union([p.boundary for p in polys]).buffer(2e-4)
        line_u = unary_union(segs)
        total_len += line_u.length
        uncovered += line_u.difference(bnd).length
    frac = 1 - (uncovered / total_len if total_len else 0)
    rep.add(floor, "a) 절단 폴리곤 폐곡선", not bad and frac >= 0.98,
            "요소 %d개, 무효/빈 %d개 %s, 선분 폐곡선 포함 %.1f%%" % (tot, len(bad), bad[:3], frac * 100))


def check_alignment(rep, floor, out, raw, tol_px):
    import cairosvg
    bounds = pc.load_bounds(raw)
    mask_p = os.path.join(raw, "floor_%s_cutmask.png" % floor)
    svg_p = os.path.join(out, "vector", "floor_%s_vector.svg" % floor)
    if not (os.path.exists(mask_p) and os.path.exists(svg_p)):
        rep.add(floor, "b) 정렬", False, "마스크/SVG 없음")
        return
    mask = np.asarray(Image.open(mask_p).convert("L"))
    size = mask.shape[0]
    png = cairosvg.svg2png(url=svg_p, output_width=size, output_height=size, background_color="white")
    svg_img = np.asarray(Image.open(io.BytesIO(png)).convert("L"))
    sl = pc.load_slice(raw, floor)
    cuts = pc.cut_geometries(sl)
    cols = [g for _, g in cuts.get("column", [])]
    if not cols:
        rep.add(floor, "b) 정렬", False, "기둥 없음(기준 물체 없음)")
        return
    # (1) SVG 파일 안의 좌표 ↔ 기대 정규화 좌표 (Y 뒤집힘 검사)
    txt = open(svg_p, encoding="utf-8").read()
    m = re.search(r'<g[^>]*id="A-COLS-CUT"[^>]*>\s*<path d="M([-\d.]+),([-\d.]+)', txt)
    ref = None
    if m:
        sx, sy = float(m.group(1)), float(m.group(2))
        side = bounds["xmax"] - bounds["xmin"]
        # 이 점이 어떤 기둥의 꼭짓점인지 월드 좌표로 되돌려 찾는다
        wx, wy = sx + bounds["xmin"], bounds["ymax"] - sy
        best = min(((abs(wx - x) + abs(wy - y), x, y) for g in cols for x, y in g.exterior.coords))
        u_svg, v_svg = sx / side, sy / side
        u_exp, v_exp = [c / size for c in pc.world_to_px(best[1], best[2], bounds, size)]
        ref = (best[1], best[2])
        rep.add(floor, "b1) SVG 좌표 = 기대 정규화(u,v)", best[0] < 1e-3 and abs(u_svg - u_exp) < 1e-5 and abs(v_svg - v_exp) < 1e-5,
                "SVG (%.5f,%.5f) 기대 (%.5f,%.5f)" % (u_svg, v_svg, u_exp, v_exp))
    # (2) 기둥 무게중심: SVG 래스터 ↔ Blender 마스크
    offs = []
    for g in cols:
        u, v = pc.world_to_px(g.centroid.x, g.centroid.y, bounds, size)
        cs, cm = blob_centroid(svg_img, u, v, 0.9 * size / 2048 * 14), blob_centroid(mask, u, v, 0.9 * size / 2048 * 14)
        if cs and cm:
            offs.append(((cs[0] - cm[0]) ** 2 + (cs[1] - cm[1]) ** 2) ** 0.5)
    ok = len(offs) >= 0.8 * len(cols) and (np.median(offs) <= tol_px and max(offs) <= 2.5 * tol_px)
    rep.add(floor, "b2) 기둥 위치 SVG↔마스크(px)", ok,
            "측정 %d/%d, 중앙값 %.2f px, 최대 %.2f px (허용 %.1f / %.1f, %d px 이미지)" % (
                len(offs), len(cols), np.median(offs) if offs else -1, max(offs) if offs else -1, tol_px, 2.5 * tol_px, size))
    # (3) 기준 꼭짓점 바로 안쪽 픽셀이 SVG·마스크 모두 어둡다
    if ref:
        g = min(cols, key=lambda c: abs(c.centroid.x - ref[0]) + abs(c.centroid.y - ref[1]))
        u, v = pc.world_to_px(g.centroid.x, g.centroid.y, bounds, size)
        rep.add(floor, "b3) 기준 기둥 중심 픽셀(SVG·마스크)", svg_img[int(v), int(u)] < 80 and mask[int(v), int(u)] < 80,
                "SVG=%d 마스크=%d at (%d,%d)" % (svg_img[int(v), int(u)], mask[int(v), int(u)], int(u), int(v)))
    # (4) 전체 IoU (기둥+튜브, 참고)
    sel = [g for k in ("column", "tube_wall") for _, g in cuts.get(k, [])]
    vec = np.asarray(pc.rasterize(sel, bounds, size)) < 128
    msk = mask < 128
    from scipy.ndimage import binary_dilation
    region = binary_dilation(vec, iterations=int(size / 2048 * 10))
    m2 = msk & region
    union = (m2 | vec).sum()
    iou = (m2 & vec).sum() / union if union else 0
    rep.add(floor, "b4) 기둥+튜브 IoU(참고, ≥0.75)", iou >= 0.75, "IoU %.3f" % iou)


def check_dxf(rep, floor, out):
    p = os.path.join(out, "cad", "floor_%s.dxf" % floor)
    try:
        doc = ezdxf.readfile(p)
    except Exception as e:                                   # noqa: BLE001
        rep.add(floor, "c) DXF 열기", False, str(e))
        return
    msp = doc.modelspace()
    counts = {l: sum(1 for e in msp if e.dxf.layer == l) for l in ("A-WALL-CUT", "A-ANNO-DIMS", "A-ANNO-TEXT", "A-COLS-CUT")}
    rep.add(floor, "c) DXF 열림·레이어 비어있지 않음", all(counts[l] > 0 for l in ("A-WALL-CUT", "A-ANNO-DIMS", "A-ANNO-TEXT")),
            " ".join("%s=%d" % kv for kv in counts.items()))


def check_composite(rep, floor, out, raw):
    lay = pc.load_json(os.path.join(out, "vector", "floor_%s_layout.json" % floor))
    sl = pc.load_slice(raw, floor)
    cuts = pc.cut_geometries(sl)
    # 글자 상자: 서로 겹치지 않는다
    boxes = [(lb["text"], box(lb["x"] - lb["w"] / 2, lb["y"], lb["x"] + lb["w"] / 2, lb["y"] + lb["h"])) for lb in lay["labels"]]
    clash = [(a[0], b[0]) for i, a in enumerate(boxes) for b in boxes[i + 1:] if a[1].intersects(b[1])]
    rep.add(floor, "d1) 글자 상자끼리 겹침 없음", not clash, "라벨 %d개 %s" % (len(boxes), clash[:3]))
    # 글자가 절단 요소(벽·기둥·튜브)와 겹치지 않는다. 코어 이름은 코어 안에 놓는 것이 정상이다
    hit = []
    knock = {lb["text"] for lb in lay["labels"] if lb.get("knockout")}              # 순백색 배경 상자를 깐 글자는 선 위에 놓아도 된다 (AGENTS.md §3.1)
    for text, bx in boxes:
        if text in knock:
            continue
        for kind, items in cuts.items():
            for it, g in items:
                if g.intersects(bx):
                    inside_own = kind == "core_wall" and g.buffer(0.01).contains(bx)
                    if not inside_own:
                        hit.append((text, it["name"]))
    rep.add(floor, "d2) 글자가 절단 요소와 겹침 없음", not hit, "%s (흰 배경 상자 %d개)" % (hit[:3], len(knock)))
    rep.add(floor, "d3) 배치 실패 라벨 없음", not lay["unplaced"], "%s" % lay["unplaced"])
    # 합성 PNG에 벡터가 정렬되어 얹혔다: 기둥 중심 픽셀이 어둡다
    sj, sp = os.path.join(out, "final_sheets", "floor_%s_sheet.json" % floor), os.path.join(out, "final_sheets", "floor_%s_sheet.png" % floor)
    if not (os.path.exists(sj) and os.path.exists(sp)):
        rep.add(floor, "d4) 합성 PNG", False, "시트 없음")
        return
    info = pc.load_json(sj)
    img = np.asarray(Image.open(sp).convert("L"))
    bounds = pc.load_bounds(raw)
    px_per_mm = info["dpi"] / 25.4
    k = 1000.0 / info["scale"]
    dark, n = 0, 0
    for _, g in cuts.get("column", []):
        mx = info["plan_x_mm"] + (g.centroid.x - bounds["xmin"]) * k
        my = info["plan_y_mm"] + (bounds["ymax"] - g.centroid.y) * k
        u, v = int(round(mx * px_per_mm)), int(round(my * px_per_mm))
        if 0 <= v < img.shape[0] and 0 <= u < img.shape[1]:
            n += 1
            dark += int(img[v, u] < 90)
    rep.add(floor, "d4) 합성 PNG: 기둥 위치에 벡터가 얹힘", n > 0 and dark >= 0.95 * n, "%d/%d 어두움, 시트 %s px" % (dark, n, img.shape[::-1]))


ZERO_KEYS = ("numbers_on_elevators_or_shafts", "entrance_boxes_drawn", "furniture_touching_column", "furniture_touching_tube",
             "numbers_colliding_with_furniture", "door_swing_hits_wall", "door_swing_hits_other_door", "curtain_door_swing_hits_wall",
             "fixtures_remaining_in_swing", "door_opening_residual_wall_area_m2", "door_jamb_clearance_violations")


def _group(svg, gid):
    m = re.search(r'<g id="%s">(.*?)</g>' % gid, svg, re.S)
    return m.group(1) if m else ""


def check_architectural(rep, floor, out):
    """e) A3 도면: 축척·종이 크기, 선 위계(커튼월·가구 가는 선), 가구 흰 채움, 충돌 지표 0, 확대 점검 그림 800×800."""
    fs = os.path.join(out, "final_sheets")
    svgs = sorted(f for f in os.listdir(fs) if re.match(r"plan_%s_A3_1to\d+(_t\d)?\.svg$" % floor, f)) if os.path.isdir(fs) else []
    if not svgs:
        return
    for name in svgs:
        base = name[:-4]
        svg = open(os.path.join(fs, name), encoding="utf-8").read()
        chk = pc.load_json(os.path.join(fs, base + "_check.json"))
        scale = int(re.search(r"1to(\d+)", base).group(1))
        k = scale / 1000.0
        rep.add(floor, "e1) %s A3·축척" % base[-9:], 'width="420mm" height="297mm"' in svg and chk["canvas_matches_A3"] and scale == (500 if floor == "1F" else 100),
                "1:%d" % scale)
        furn = _group(svg, "furn")
        fills = set(re.findall(r'fill="(#[0-9a-fA-F]{3,6}|none)"', furn))
        bad_fill = {f for f in fills if f.lower() not in ("#ffffff", "#fff", "none", "#000", "#000000") and not re.fullmatch(r"#[A-Fa-f0-9]{6}", f)}
        body_white = any(f.lower() in ("#ffffff", "#fff") for f in fills) or not furn.strip()
        rep.add(floor, "e2) %s 가구 불투명 흰 채움" % base[-9:], body_white and not bad_fill, "채움 %s" % sorted(fills)[:4])
        fw = [float(x) for x in re.findall(r'stroke-width="([0-9.]+)"', re.sub(r'<path d="M[^"]*h0\.001"[^>]*/>', "", furn))]      # 볼라드 점(둥근 끝 점)은 선이 아니다
        rep.add(floor, "e3) %s 가구 선 ≤0.12 mm" % base[-9:], all(w <= 0.12 * k + 1e-6 for w in fw), "최대 %.3f mm" % (max(fw, default=0) / k))
        ew = [float(x) for x in re.findall(r'stroke-width="([0-9.]+)"', _group(svg, "envelope"))]
        rep.add(floor, "e4) %s 커튼월 선 ≤0.18 mm" % base[-9:], all(w <= 0.18 * k + 1e-6 for w in ew), "최대 %.3f mm" % (max(ew, default=0) / k))
        nz = {key: chk.get(key) for key in ZERO_KEYS if chk.get(key)}
        rep.add(floor, "e5) %s 충돌 지표 0" % base[-9:], not nz, "%s" % (nz or "모두 0"))
        rep.add(floor, "e6) %s 번호 전부 숫자" % base[-9:], chk.get("plan_text_all_numeric", True), "")
    if floor == "1F":
        for nm in ("crop_core_restroom.png", "crop_curtainwall_furniture.png", "crop_tube_capsule.png"):
            p = os.path.join(fs, nm)
            ok = os.path.exists(p) and Image.open(p).size == (800, 800)
            rep.add(floor, "e7) 확대 점검 %s" % nm, ok, "800×800" if ok else "없거나 크기 다름")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--floors", default="")
    ap.add_argument("--tol-px", type=float, default=1.5)
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    raw = os.path.join(out, "raw_slices")
    floors = [f for f in a.floors.split(",") if f] or pc.list_floors(raw)
    rep = Report()
    for f in floors:
        if not os.path.exists(os.path.join(raw, "floor_%s_cutmask.png" % f)):
            rep.add(f, "산출물 존재", False, "렌더 결과 없음")
            continue
        sl = pc.load_slice(raw, f)
        check_closed(rep, f, sl)
        mask_w = Image.open(os.path.join(raw, "floor_%s_cutmask.png" % f)).size[0]
        check_alignment(rep, f, out, raw, a.tol_px * max(1.0, mask_w / 2048))        # 허용 오차는 물리 길이 기준이라 해상도에 비례한다
        check_dxf(rep, f, out)
        check_composite(rep, f, out, raw)
        check_architectural(rep, f, out)
    path = os.path.join(out, "qa_report.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"failed": len(rep.failed), "total": len(rep.rows), "rows": rep.rows}, fh, ensure_ascii=False, indent=1)
    print("QA %d/%d 통과, 보고서: %s" % (len(rep.rows) - len(rep.failed), len(rep.rows), path))
    sys.exit(1 if rep.failed else 0)


if __name__ == "__main__":
    main()
