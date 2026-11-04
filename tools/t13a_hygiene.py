"""C-T13A 선 위생(line hygiene) 지표: SVG 한 장을 층별로 측정한다. before/after 에 같은 도구를 쓴다.

    python tools/t13a_hygiene.py --svg X.svg --out metrics.json [--scale 500]

지표: 요소 수, 꼭짓점·명령 수, 호(A)·베지어(C) 수, 미세 선분(<0.1 mm 종이), 짧은 선분 지그재그(꺾임>25°, 선분<1 m),
점선 중복(같은 선이 여러 번 그려진 비율)과 2 m 미만 점선 조각 수, 점묘 점 수, 식재 윤곽 중 참 원이 아닌 것,
가구 body 겹침(고스트), 층별 선 굵기·색 토큰(종이 mm).
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import re
import sys

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import line_hygiene as LH  # noqa: E402
import t13a_geometry_check as G  # noqa: E402

LAYERS = ("bgdots", "context", "ground", "landscape", "plants", "furn", "envelope", "walls", "cols", "grid", "symbols", "doors", "num", "legend")
ATTR = re.compile(r'(\w[\w-]*)="([^"]*)"')


def attrs_of(s):
    return dict(ATTR.findall(s))


def analyze(svg, scale=500):
    k = scale / 1000.0
    micro_m = 0.1 * k                                 # 종이 0.1 mm = 월드 m
    out = {"scale": scale, "layers": {}}
    all_dashed = []
    ghost_polys = []
    for layer in LAYERS:
        grp = G.group(svg, layer)
        els = re.findall(r"<(polyline|path)\b([^>]*)/>", grp)
        row = {"elements": len(els), "polylines": 0, "paths": 0, "vertices_or_cmds": 0, "arcs_A": 0, "cubics_C": 0, "micro_segments": 0,
               "zigzag_kinks": 0, "dashed_elements": 0, "dashed_len_m": 0.0, "dashed_pieces_lt2m": 0, "dots": 0, "non_circle_closed_plants": 0,
               "width_color_tokens_mm": collections.Counter()}
        for kind, a in els:
            at = attrs_of(a)
            sw = float(at.get("stroke-width", "0") or 0)
            if at.get("stroke") and at.get("stroke") != "none":
                row["width_color_tokens_mm"]["%.3f %s" % (sw / k, at["stroke"].upper())] += 1
            if kind == "polyline":
                row["polylines"] += 1
                P = [tuple(float(v) for v in q.split(",")) for q in at["points"].split()]
                subs = [P]
                row["vertices_or_cmds"] += len(P)
            else:
                row["paths"] += 1
                d = at.get("d", "")
                if "h0.001" in d:
                    row["dots"] += d.count("h0.001")
                    continue
                row["arcs_A"] += len(re.findall(r"\bA", d))
                row["cubics_C"] += len(re.findall(r"\bC", d))
                row["vertices_or_cmds"] += len(re.findall(r"[MLCA]", d))
                subs = LH.sample_path(d, 8, 6) if re.search(r"[CA]", d) else LH.sample_path(d)
                if layer == "plants" and at.get("fill") not in (None, "none") and not re.search(r"\bA", d):
                    row["non_circle_closed_plants"] += 1
            raw_pts = subs
            for P in raw_pts:
                segs = [math.hypot(P[i + 1][0] - P[i][0], P[i + 1][1] - P[i][1]) for i in range(len(P) - 1)]
                row["micro_segments"] += sum(1 for s in segs if 0 < s < micro_m)
                for i in range(1, len(P) - 1):
                    if segs[i - 1] < 1.0 and segs[i] < 1.0 and segs[i - 1] > 0 and segs[i] > 0:
                        v1 = (P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1])
                        v2 = (P[i + 1][0] - P[i][0], P[i + 1][1] - P[i][1])
                        c = max(-1, min(1, (v1[0] * v2[0] + v1[1] * v2[1]) / (segs[i - 1] * segs[i])))
                        if math.degrees(math.acos(c)) > 25 and kind == "polyline" and layer in ("furn", "landscape", "ground", "context", "plants", "symbols"):
                            row["zigzag_kinks"] += 1
            if at.get("stroke-dasharray"):
                row["dashed_elements"] += 1
                for P in subs:
                    if len(P) >= 2:
                        ls = LineString(P)
                        row["dashed_len_m"] += ls.length
                        if ls.length < 2.0:
                            row["dashed_pieces_lt2m"] += 1
                        all_dashed.append(ls)
            if layer == "furn" and kind == "path" and at.get("fill", "").upper() == "#FFFFFF":
                for P in subs:
                    if len(P) >= 4:
                        pg = Polygon(P)
                        if pg.is_valid and pg.area > 1e-4:
                            ghost_polys.append(pg)
        row["dashed_len_m"] = round(row["dashed_len_m"], 1)
        row["width_color_tokens_mm"] = dict(row["width_color_tokens_mm"].most_common(8))
        out["layers"][layer] = row
    uni = unary_union([l.buffer(0.02) for l in all_dashed]) if all_dashed else None
    tot = sum(l.length for l in all_dashed)
    # 선 길이 기준 중복 비율: 합계 길이 / (버퍼 합집합 면적 / 0.04)
    out["dashed_overlap"] = {"total_len_m": round(tot, 1), "union_len_m_est": round(uni.area / 0.04, 1) if uni is not None else 0,
                             "overlap_ratio": round(1 - (uni.area / 0.04) / tot, 3) if tot > 0 and uni is not None else 0.0}
    n_over, worst = 0, 0.0
    for i, a in enumerate(ghost_polys):
        for b in ghost_polys[i + 1:]:
            if a.bounds[2] < b.bounds[0] or b.bounds[2] < a.bounds[0] or a.bounds[3] < b.bounds[1] or b.bounds[3] < a.bounds[1]:
                continue
            ov = a.intersection(b).area
            if ov > 1e-3 and ov < 0.98 * min(a.area, b.area):                    # 한 몸체가 다른 몸체 안에 완전히 든 것(스툴 등 의도된 중첩)은 제외
                n_over += 1
                worst = max(worst, ov)
    out["furniture_bodies"] = {"count": len(ghost_polys), "partial_overlaps": n_over, "worst_overlap_m2": round(worst, 4),
                               "identical_paths": 0}
    ds = re.findall(r'<path d="([^"]+)"[^>]*fill="#FFFFFF"', G.group(svg, "furn"))
    out["furniture_bodies"]["identical_paths"] = len(ds) - len(set(ds))
    tot_v = sum(r["vertices_or_cmds"] for r in out["layers"].values())
    out["totals"] = {"elements": sum(r["elements"] for r in out["layers"].values()), "vertices_or_cmds": tot_v,
                     "arcs_A": sum(r["arcs_A"] for r in out["layers"].values()), "cubics_C": sum(r["cubics_C"] for r in out["layers"].values()),
                     "micro_segments": sum(r["micro_segments"] for r in out["layers"].values()), "zigzag_kinks": sum(r["zigzag_kinks"] for r in out["layers"].values()),
                     "dots": sum(r["dots"] for r in out["layers"].values()), "svg_bytes": len(svg.encode("utf-8"))}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--svg", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", type=int, default=500)
    a = ap.parse_args()
    m = analyze(open(a.svg, encoding="utf-8").read(), a.scale)
    json.dump(m, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(m["totals"], ensure_ascii=False), m["dashed_overlap"], m["furniture_bodies"])


if __name__ == "__main__":
    main()
