"""C-T13A 독립 검증: before/after SVG 의 같은 요소를 같은 순서로 짝지어 형상 편차(월드 m)를 잰다.

구조·가구·문·외피 층은 형상이 바뀌면 안 된다 (허용 편차 STRUCT_TOL). 호/베지어 변환은 꼭짓점 열이 아니라
**실제 변환 결과 경로를 표본화**해 원래 꺾은선과 양방향으로 비교하므로 변환 코드의 자기 보고와 무관하다.

    python tools/t13a_geometry_check.py --before X.svg --after Y.svg --out report.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import line_hygiene as LH  # noqa: E402

STRUCT_LAYERS = ("cols", "walls", "doors", "envelope")
STRUCT_TOL = 0.012          # m (1:500 종이 0.024 mm)
ELEM = re.compile(r"<(polyline|path)\b([^>]*)/>")


def group(svg, gid):
    m = re.search(r'<g id="%s">(.*?)</g>' % gid, svg, re.S)
    return m.group(1) if m else ""


def elements(svg_group, only=None):
    out = []
    for kind, attrs in ELEM.findall(svg_group):
        if only is not None and not only(attrs):
            continue
        if kind == "polyline":
            pts = re.search(r'points="([^"]+)"', attrs)
            if not pts:
                continue
            P = [tuple(float(v) for v in q.split(",")) for q in pts.group(1).split()]
            out.append(([P], attrs))
        else:
            d = re.search(r' d="([^"]+)"', " " + attrs)
            if not d or "h0.001" in d.group(1):
                continue
            out.append((LH.sample_path(d.group(1), n_arc=48, n_bez=24), attrs))
    return out


def pair_dev(a_subs, b_subs):
    if len(a_subs) != len(b_subs):
        return None
    worst = 0.0
    for a, b in zip(a_subs, b_subs):
        if len(a) < 2 or len(b) < 2:
            continue
        worst = max(worst, LH.poly_distance(b, a), LH.poly_distance(a, b))
    return worst


def compare(before_svg, after_svg, layers=STRUCT_LAYERS, extra_filters=None):
    rep = {}
    for layer in layers:
        flt = (extra_filters or {}).get(layer)
        A, B = elements(group(before_svg, layer), flt), elements(group(after_svg, layer), flt)
        row = {"before_elements": len(A), "after_elements": len(B), "paired": 0, "max_dev_m": 0.0, "over_tol": 0, "worst": []}
        if len(A) == len(B):
            for (sa, aa), (sb, ab) in zip(A, B):
                dv = pair_dev(sa, sb)
                if dv is None:
                    row["over_tol"] += 1
                    row["worst"].append({"dev_m": None, "note": "subpath count differs", "attrs": aa[:80]})
                    continue
                row["paired"] += 1
                row["max_dev_m"] = max(row["max_dev_m"], dv)
                if dv > STRUCT_TOL:
                    row["over_tol"] += 1
                    row["worst"].append({"dev_m": round(dv, 4), "attrs": aa[:80]})
        else:
            row["over_tol"] = abs(len(A) - len(B))
        row["max_dev_m"] = round(row["max_dev_m"], 5)
        row["worst"] = sorted(row["worst"], key=lambda w: -(w["dev_m"] or 9))[:5]
        row["count_match"] = len(A) == len(B)
        rep[layer] = row
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    b_svg, a_svg = open(a.before, encoding="utf-8").read(), open(a.after, encoding="utf-8").read()
    fw = lambda attrs: 'fill="#FFFFFF"' in attrs or 'fill="#ffffff"' in attrs  # noqa: E731
    furn = compare(b_svg, a_svg, ("furn",), {"furn": fw})
    rep = compare(b_svg, a_svg)
    rep.update({"furn_bodies": furn["furn"]})
    json.dump(rep, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    bad = {k: v["over_tol"] for k, v in rep.items() if v["over_tol"] or not v["count_match"]}
    for k, v in rep.items():
        print("%-12s before %4d after %4d paired %4d max_dev %.5f m over_tol %d" % (k, v["before_elements"], v["after_elements"], v["paired"], v["max_dev_m"], v["over_tol"]))
    print("GEOMETRY CHECK:", "PASS" if not bad else "FAIL %s" % bad)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
