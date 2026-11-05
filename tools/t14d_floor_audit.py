"""C-T14D 1단계: 층별 실제 동등성 감사(읽기 전용).

17개 층(B2~15F)을 1층과 같은 도면 좌표틀로 슬라이스한 slice JSON에서 기하·용도 지문을 계산하고,
모든 층 쌍의 차이를 수치로 비교해 '기준층'을 증거로만 판정한다. 추측으로 합치지 않는다.

    python -I tools/t14d_floor_audit.py --run <도면집 후보 폴더> --glb <전층.glb>

산출 (<run>\\00_index): floor_typology_matrix.csv, floor_equivalence_evidence.json, floor_coverage_audit.json,
                        floor_pairwise_delta.csv, 그리고 <run>\\06_QA\\floor_contact_sheet.png (층별 썸네일, 검토용)
"""
import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
import pipeline_common as pc  # noqa: E402
from shapely.geometry import MultiPolygon, Polygon  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

AREA_TOL = 0.05          # m² : 같은 종류 요소 합집합의 대칭차 허용(테셀레이션 잡음 수준)
HAUS_TOL = 0.05          # m  : 하우스도르프 거리 허용. 합집합 비교는 조각(sliver) 하나에 민감해 면적 허용과 함께 쓴다(8F~9F 외피: 면적차 0.0002 m², 거리 0.042 m)
VERT_BUFFER = 5.0        # m  : 수직동선(에스컬레이터·램프·승강기 샤프트) 둘레. slice에는 1.5 m 높이에서 잘린 일부만 있고 개구는 에스컬레이터 길이(약 8.6 m)만큼 길다(8F~9F 실측: 개구 띠가 에스컬레이터 중심에서 2.1~2.2 m)
CUT_KINDS = ("column", "core_wall", "tube_wall", "shaft", "stair", "ramp", "facade")
FLOOR_ORDER = ["B2", "B1"] + ["%dF" % i for i in range(1, 16)]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def U(geoms):
    geoms = [g for g in geoms if g is not None and not g.is_empty]
    return unary_union(geoms) if geoms else Polygon()


def polys(g):
    if g.is_empty:
        return []
    return list(g.geoms) if hasattr(g, "geoms") else [g]


def fingerprint(sl):
    cuts = pc.cut_geometries(sl)
    comp = {k: U([g for _, g in cuts.get(k, [])]) for k in CUT_KINDS}
    comp["slab"] = U([pc.polygons_from_segments(p["segments"]) for p in sl["projection"]])
    zones = [(z["name_ko"], pc.polygons_from_segments(z["segments"])) for z in sl["zones"]]
    comp["zone"] = U([g for _, g in zones])
    # 슬래브의 구멍(보이드)
    voids = []
    for p in polys(comp["slab"]):
        voids += [Polygon(r) for r in p.interiors]
    items = []
    for k in CUT_KINDS:
        for it, g in cuts.get(k, []):
            c = g.centroid
            items.append((k, it.get("name_ko") or "", round(c.x, 2), round(c.y, 2), round(g.area, 2)))
    return {"comp": comp, "zones": zones, "voids": voids, "items": sorted(items),
            "counts": {k: len(cuts.get(k, [])) for k in CUT_KINDS}, "n_elements": len(sl["elements"])}


def delta(a, b):
    out = {}
    for k in list(CUT_KINDS) + ["slab", "zone"]:
        ga, gb = a["comp"][k], b["comp"][k]
        sd = ga.symmetric_difference(gb).area
        hd = 0.0
        if not ga.is_empty and not gb.is_empty:
            hd = ga.hausdorff_distance(gb)
        elif ga.is_empty != gb.is_empty:
            hd = float("inf")
        out[k] = {"sym_diff_m2": round(sd, 4), "hausdorff_m": round(hd, 4) if hd != float("inf") else None}
    return out


def same(d):
    return all(v["sym_diff_m2"] <= AREA_TOL and (v["hausdorff_m"] is not None and v["hausdorff_m"] <= HAUS_TOL) for v in d.values())


VERT_KINDS = ("stair", "ramp", "shaft")


def same_geom(d):
    return same({k: v for k, v in d.items() if k != "zone"})


def program_key(fp):
    """프로그램: 구역 이름별 면적 합(이름이 다르면 다른 프로그램)."""
    acc = {}
    for n, g in fp["zones"]:
        acc[n] = acc.get(n, 0.0) + g.area
    return {n: round(a_, 1) for n, a_ in acc.items()}


def program_equal(fa, fb):
    ka, kb = program_key(fa), program_key(fb)
    return set(ka) == set(kb) and all(abs(ka[n] - kb[n]) <= AREA_TOL for n in ka)


def circulation_only(fa, fb, d):
    """두 층의 차이가 수직동선(에스컬레이터·램프·샤프트)과 그 개구(슬래브)에만 있는가.
    기둥·코어·튜브·외피·프로그램은 같고, 슬래브 차이는 수직동선 둘레(VERT_BUFFER) 안에 있어야 한다."""
    for k in ("column", "core_wall", "tube_wall", "facade"):
        v = d[k]
        if v["sym_diff_m2"] > AREA_TOL or v["hausdorff_m"] is None or v["hausdorff_m"] > HAUS_TOL:
            return False
    if not program_equal(fa, fb):
        return False
    return slab_residual(fa, fb) <= AREA_TOL


def slab_residual(fa, fb):
    """슬래브 차이 중 수직동선 둘레(VERT_BUFFER) 밖에 남는 면적."""
    zone = U([fa["comp"][k] for k in VERT_KINDS] + [fb["comp"][k] for k in VERT_KINDS]).buffer(VERT_BUFFER)
    return fa["comp"]["slab"].symmetric_difference(fb["comp"]["slab"]).difference(zone).area


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--glb", required=True)
    a = ap.parse_args()
    run = os.path.abspath(a.run)
    raw = os.path.join(run, "raw_slices")
    floors = pc.load_json(os.path.join(raw, "floors.json"))["floors"]
    found = [f for f in FLOOR_ORDER if os.path.exists(os.path.join(raw, "floor_%s_slice.json" % f))]
    missing = [f for f in FLOOR_ORDER if f not in found]
    extra = [f for f in floors if f not in FLOOR_ORDER]
    fps, slices = {}, {}
    for f in found:
        slices[f] = pc.load_json(os.path.join(raw, "floor_%s_slice.json" % f))
        fps[f] = fingerprint(slices[f])
    zs = sorted(floors.items(), key=lambda kv: kv[1])
    height = {zs[i][0]: round(zs[i + 1][1] - zs[i][1], 3) for i in range(len(zs) - 1)}
    height["15F"] = None   # 15F 위는 지붕(층판 목록에 없음) → 입면 단계에서 A-ROOF로 확정

    # 쌍별 차이
    pair = {}
    rows = []
    for i, f1 in enumerate(found):
        for f2 in found[i + 1:]:
            d = delta(fps[f1], fps[f2])
            pair[(f1, f2)] = d
            pe = program_equal(fps[f1], fps[f2])
            rows.append({"a": f1, "b": f2, "geometry_equal": same_geom(d), "program_equal": pe, "strict_equal": same_geom(d) and pe,
                         "circulation_only_delta": circulation_only(fps[f1], fps[f2], d), "slab_residual_outside_vertical_m2": round(slab_residual(fps[f1], fps[f2]), 4),
                         "max_sym_diff_m2": max(v["sym_diff_m2"] for v in d.values()),
                         **{"%s_symdiff" % k: v["sym_diff_m2"] for k, v in d.items()}})
    with open(os.path.join(run, "00_index", "floor_pairwise_delta.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    rel = {}
    for r in rows:
        rel[(r["a"], r["b"])] = "STRICT" if r["strict_equal"] else ("CIRCULATION_ONLY" if r["circulation_only_delta"] else None)

    def related(f1, f2):
        return rel.get((f1, f2)) or rel.get((f2, f1))

    # 그룹: 모든 쌍이 STRICT 또는 CIRCULATION_ONLY인 층끼리만 묶는다(전이 추론 금지, 모든 쌍 직접 검증)
    groups = []
    for f in found:
        for g in groups:
            if all(related(m, f) for m in g):
                g.append(f)
                break
        else:
            groups.append([f])

    def kind_of(g):
        if len(g) == 1:
            return "INDEPENDENT"
        if all(related(x, y) == "STRICT" for i, x in enumerate(g) for y in g[i + 1:]):
            return "TYPICAL_STRICT"
        return "TYPICAL_WITH_CIRCULATION_VARIATION"

    matrix = []
    for f in found:
        fp = fps[f]
        gi = next(i for i, g in enumerate(groups) if f in g)
        matrix.append({"floor": f, "floor_z_m": floors[f], "floor_to_floor_m": height.get(f), "cut_z_m": slices[f]["cut_z"], "group": "G%02d" % (gi + 1),
                       "group_members": "+".join(groups[gi]), "group_kind": kind_of(groups[gi]), "elements": fp["n_elements"], **{"n_" + k: v for k, v in fp["counts"].items()},
                       "slab_area_m2": round(fp["comp"]["slab"].area, 1), "voids": len(fp["voids"]), "void_area_m2": round(sum(v.area for v in fp["voids"]), 1),
                       "program": "; ".join("%s %.1f" % (n, a_) for n, a_ in sorted(program_key(fp).items())) or "-"})
    with open(os.path.join(run, "00_index", "floor_typology_matrix.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(matrix[0].keys()))
        w.writeheader()
        w.writerows(matrix)

    # 사용자 가설 그룹을 쌍별로 검증
    hyp = [["3F", "4F", "5F"], ["8F", "9F", "10F"], ["13F", "14F"]]
    hyp_res = []
    for g in hyp:
        pairs = []
        for i, f1 in enumerate(g):
            for f2 in g[i + 1:]:
                d = pair[(f1, f2)]
                pairs.append({"pair": "%s~%s" % (f1, f2), "relation": related(f1, f2) or "DIFFERENT", "program_equal": program_equal(fps[f1], fps[f2]),
                              "program": {f1: program_key(fps[f1]), f2: program_key(fps[f2])}, "slab_residual_outside_vertical_m2": round(slab_residual(fps[f1], fps[f2]), 4),
                              "vertical_elements": {k: {f1: [(round(q.centroid.x, 1), round(q.centroid.y, 1)) for q in polys(fps[f1]["comp"][k])], f2: [(round(q.centroid.x, 1), round(q.centroid.y, 1)) for q in polys(fps[f2]["comp"][k])]} for k in VERT_KINDS},
                              "delta_beyond_tolerance": {k: v for k, v in d.items() if v["sym_diff_m2"] > AREA_TOL or (v["hausdorff_m"] or 0) > HAUS_TOL}})
        rels = {p["relation"] for p in pairs}
        hyp_res.append({"group": g, "floor_to_floor_m": {f: height.get(f) for f in g}, "pairs": pairs,
                        "verdict": "STRICT" if rels == {"STRICT"} else ("CIRCULATION_ONLY_OR_STRICT" if rels <= {"STRICT", "CIRCULATION_ONLY"} else "NOT_EQUIVALENT")})

    ev = {"purpose": "층별 실제 동등성 검증(추측 금지)", "frame": pc.load_json(os.path.join(raw, "camera_bounds.json"))["frame"],
          "tolerance": {"sym_diff_m2": AREA_TOL, "hausdorff_m": HAUS_TOL, "vertical_circulation_buffer_m": VERT_BUFFER,
                        "note": "요소 종류별(기둥·코어·튜브·샤프트·에스컬레이터·램프·입면 부재·슬래브·프로그램 구역) 합집합 비교. 프로그램은 구역 이름별 면적까지 같아야 같다."},
          "relations": {"STRICT": "기둥·코어·튜브·샤프트·에스컬레이터·램프·외피·슬래브·프로그램이 모두 허용오차 내 동일",
                        "CIRCULATION_ONLY": "기둥·코어·튜브·외피·프로그램은 동일하고, 차이는 에스컬레이터·램프·샤프트와 그 슬래브 개구(둘레 %.1f m)에만 있다" % VERT_BUFFER},
          "model": {"path": os.path.abspath(a.glb), "sha256": sha256(a.glb)},
          "floors_found": found, "floors_missing": missing, "floors_extra_in_model": extra,
          "floor_z_m": {f: floors[f] for f in found}, "floor_to_floor_m": height,
          "groups": [{"id": "G%02d" % (i + 1), "floors": g, "kind": kind_of(g)} for i, g in enumerate(groups)],
          "hypothesis_groups": hyp_res,
          "slices": {f: {"path": os.path.join(raw, "floor_%s_slice.json" % f), "sha256": sha256(os.path.join(raw, "floor_%s_slice.json" % f))} for f in found},
          "roof": "ROOF는 층판 목록에 없다. A-ROOF 원천은 2단계(지붕 평면·입면)에서 별도 확인"}
    json.dump(ev, open(os.path.join(run, "00_index", "floor_equivalence_evidence.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    cov, sheets = {}, []
    for i, g in enumerate(groups):
        hs = {m: height.get(m) for m in g}
        s_ = {"group": "G%02d" % (i + 1), "representative": g[0], "members": g, "kind": kind_of(g), "floor_to_floor_m": hs,
              "floor_to_floor_all_equal": len({v for v in hs.values() if v is not None}) <= 1}
        sheets.append(s_)
        for m in g:
            cov[m] = {"group": s_["group"], "representative": g[0], "kind": s_["kind"], "mapped": True}
    audit = {"required": FLOOR_ORDER, "covered": sorted(cov, key=FLOOR_ORDER.index), "covered_count": len(cov), "required_count": len(FLOOR_ORDER),
             "coverage": "%d/%d" % (len(cov), len(FLOOR_ORDER)), "missing_floors": [f for f in FLOOR_ORDER if f not in cov],
             "plan_sheet_groups": sheets, "by_floor": cov,
             "label_rule": {"TYPICAL_STRICT": "EQUIVALENCE VERIFIED 표기 허용(층고가 다르면 함께 고지)",
                            "TYPICAL_WITH_CIRCULATION_VARIATION": "'EQUIVALENCE VERIFIED' 금지. 'TYPICAL — DIFFERS ONLY IN VERTICAL-CIRCULATION OPENINGS (VERIFIED)' + 차이 시트 필수",
                            "INDEPENDENT": "독립 평면 1장"},
             "note": "지붕(ROOF)은 별도 시트."}
    json.dump(audit, open(os.path.join(run, "00_index", "floor_coverage_audit.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    classes = groups

    # 검토용 썸네일 시트
    import cairosvg
    from PIL import Image, ImageDraw, ImageFont
    cell, cols_n = 520, 6
    rows_n = math.ceil(len(found) / cols_n)
    sheet = Image.new("RGB", (cols_n * cell, rows_n * (cell + 60) + 90), "white")
    d = ImageDraw.Draw(sheet)
    ft = ImageFont.truetype(r"C:\Windows\Fonts\malgunbd.ttf", 34)
    fs = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 24)
    d.text((20, 14), "층별 절단 평면 썸네일 (1층과 같은 좌표틀, 1.5 m 절단) — 색 테두리 = 묶인 그룹(전 쌍 직접 검증), 회색 = 독립 층", font=ft, fill="#111")
    palette = ["#c0392b", "#2980b9", "#27ae60", "#8e44ad", "#d35400", "#16a085", "#7f8c8d", "#2c3e50", "#b7950b", "#c2185b", "#00796b", "#5d4037"]
    bb = pc.load_json(os.path.join(raw, "camera_bounds.json"))["building"]
    x0, y0, x1, y1 = bb["xmin"] - 2, bb["ymin"] - 2, bb["xmax"] + 2, bb["ymax"] + 2
    s_ = (cell - 20) / max(x1 - x0, y1 - y0)
    for i, f in enumerate(found):
        grp = next(c for c in classes if f in c)
        multi = [c for c in classes if len(c) > 1]
        col = palette[multi.index(grp) % len(palette)] if len(grp) > 1 else "#bbbbbb"      # 묶인 그룹만 색. 독립 층은 회색(색 반복으로 다른 그룹이 같아 보이는 일 방지)
        parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"><rect width="100%%" height="100%%" fill="white"/>' % (cell, cell)]

        def pt(x, y):
            return (10 + (x - x0) * s_, cell - 10 - (y - y0) * s_)

        def draw(g, fill, stroke, w):
            for p in polys(g):
                for ring, f_ in [(p.exterior, fill)] + [(r, "#ffffff") for r in p.interiors]:
                    parts.append('<polygon points="%s" fill="%s" stroke="%s" stroke-width="%.2f"/>' % (" ".join("%.1f,%.1f" % pt(*c) for c in ring.coords), f_, stroke, w))
        c_ = fps[f]["comp"]
        draw(c_["slab"], "#f3f3f3", "#999", 1)
        for k, fill in (("zone", "none"),):
            pass
        for k, fill in (("core_wall", "#222"), ("tube_wall", "#777"), ("shaft", "#555"), ("stair", "#d77"), ("ramp", "#77d"), ("facade", "#bbb"), ("column", "#000")):
            draw(c_[k], fill, "#000", 0.4)
        parts.append("</svg>")
        png = cairosvg.svg2png(bytestring="".join(parts).encode("utf-8"))
        tmp = os.path.join(run, "06_QA", "_tmp_cell.png")
        open(tmp, "wb").write(png)
        im = Image.open(tmp).convert("RGB")
        cx, cy = (i % cols_n) * cell, 90 + (i // cols_n) * (cell + 60)
        sheet.paste(im, (cx, cy + 50))
        d.rectangle([cx + 2, cy + 50, cx + cell - 2, cy + 50 + cell], outline=col, width=6)
        d.text((cx + 10, cy + 4), "%s  z=%.1f  h=%s" % (f, floors[f], height.get(f)), font=fs, fill="#111")
    os.remove(os.path.join(run, "06_QA", "_tmp_cell.png"))
    sp = os.path.join(run, "06_QA", "floor_contact_sheet.png")
    sheet.save(sp)

    print("FOUND", len(found), "MISSING", missing, "EXTRA", extra)
    for i, c in enumerate(classes):
        print("G%02d" % (i + 1), c)
    for g in groups:
        print("KIND", g, kind_of(g))
    for h in hyp_res:
        print("HYP", "+".join(h["group"]), h["verdict"], "ff=", h["floor_to_floor_m"], [(p["pair"], p["relation"]) for p in h["pairs"]])
    print("COVERAGE", audit["coverage"])
    print("CONTACT", os.path.abspath(sp))


if __name__ == "__main__":
    main()

