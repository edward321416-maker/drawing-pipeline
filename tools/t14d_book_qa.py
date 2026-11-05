"""C-T14D 도면집 품질 게이트(COVERAGE / ORIENTATION / TRACEABILITY / SECTION↔PLAN / ELEVATION↔PLAN / PRINT / LINE).

    python -I tools/t14d_book_qa.py --run <도면집 후보 폴더> [--selftest]

레지스트리가 적은 값을 믿지 않고 산출 파일(PDF·SVG)과 모델·slice를 직접 다시 읽어 대조한다. 실패는 숨기지 않고 FAIL로 남긴다.
--selftest: 입면 방향 벡터를 90° 돌린 가짜 데이터로 같은 검사를 돌려 FAIL이 나오는지(검사가 결함을 잡는지) 확인한다.
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
import fitz  # noqa: E402
import pipeline_common as pc  # noqa: E402

A3 = (420.0, 297.0)
NUM = re.compile(r"-?\d+(?:\.\d+)?")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def jl(p):
    return json.load(open(p, encoding="utf-8"))


def bvec(b):
    return (math.sin(math.radians(b)), math.cos(math.radians(b)))


def angdiff(a, b):
    return abs(((a - b + 180) % 360) - 180)


def elev_orientation_ok(elevs, north):
    """입면 4장: 보는 방향 벡터 = 건물 면 법선(도면틀 방위), 실제 방위 = 법선 방위 − north, 네 방위가 모두 다르고 90° 간격."""
    names = []
    for e in elevs:
        v = e["view_direction_in_drawing_frame"]
        beta = math.degrees(math.atan2(v[0], v[1])) % 360
        cb = (beta - north) % 360
        if angdiff(cb, e["compass_of_face_normal_deg"]) > 0.05:
            return False, "%s 방위 불일치 (%.2f vs %.2f)" % (e["sheet"], cb, e["compass_of_face_normal_deg"])
        names.append(round(((cb + 45) % 360) // 90))
    if sorted(names) != [0, 1, 2, 3]:
        return False, "네 방위가 서로 다르지 않음 %s" % names
    bs = sorted(round(math.degrees(math.atan2(e["view_direction_in_drawing_frame"][0], e["view_direction_in_drawing_frame"][1])) % 360) for e in elevs)
    if any(abs((bs[(i + 1) % 4] - bs[i]) % 360 - 90) > 0.5 for i in range(4)):
        return False, "면 법선이 90° 간격이 아님 %s" % bs
    return True, "4면 법선 방위 %s, 서로 90° 간격, 방위 이름 N/E/S/W 각 1회" % [round(e["compass_of_face_normal_deg"], 1) for e in elevs]


def svg_arrow_angles(svg):
    """북 화살표: 굵기 0.35의 두 점 열린 경로(원 중심 → 끝)의 위쪽 기준 시계 방향 각."""
    out = []
    for m in re.finditer(r'<path d="M([\d.\-]+),([\d.\-]+) L([\d.\-]+),([\d.\-]+)" fill="none" stroke="#222" stroke-width="0.350"', svg):
        x1, y1, x2, y2 = (float(v) for v in m.groups())
        out.append(math.degrees(math.atan2(x2 - x1, -(y2 - y1))))
    return out


def norm(t):
    """cairosvg PDF는 공백 글리프가 없어 추출 글자에서 공백이 사라진다 → 공백을 모두 지우고 비교한다."""
    return re.sub(r"\s+", "", t)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    run = os.path.abspath(a.run)
    res = []

    def chk(code, ok, msg, **kw):
        res.append({"code": code, "status": "PASS" if ok else "FAIL", "msg": msg, **kw})

    reg = jl(os.path.join(run, "05_book", "book_registry.json"))
    elevr = jl(os.path.join(run, "02_elevations", "elevation_registry.json"))
    secr = jl(os.path.join(run, "03_sections", "section_line_registry.json"))
    detr = jl(os.path.join(run, "04_details", "detail_registry.json"))
    planr = jl(os.path.join(run, "01_plans", "plan_registry.json"))
    mo = jl(os.path.join(run, "model_cache", "model_objects.json"))
    ref = jl(os.path.join(run, "reference_1F", "camera_bounds.json"))
    own = jl(os.path.join(run, "raw_slices", "camera_bounds.json"))
    floors = mo["floors"]
    ffl0 = floors["1F"]
    roof_z = max(o["zmax"] for o in mo["objects"] if o["kind"] == "roof")
    obj_names = {o["name"] for o in mo["objects"]}
    order = ["B2", "B1"] + ["%dF" % i for i in range(1, 16)]
    north = ref["frame"]["north_deg"]

    # ── PRINT ────────────────────────────────────────────────────────────────────────────────
    doc = fitz.open(reg["pdf"])
    chk("PRINT.pages", len(doc) == len(reg["sheets"]) == len(doc.get_toc()), "PDF %d쪽 = 시트 %d = 책갈피 %d" % (len(doc), len(reg["sheets"]), len(doc.get_toc())))
    bad_size, bad_rot, raster, notext, nofont = [], [], [], [], []
    for i, pg in enumerate(doc):
        w, h = pg.rect.width * 25.4 / 72, pg.rect.height * 25.4 / 72
        if abs(w - A3[0]) > 0.3 or abs(h - A3[1]) > 0.3:
            bad_size.append(i + 1)
        if pg.rotation != 0:
            bad_rot.append(i + 1)
        if pg.get_images(full=True):
            raster.append(i + 1)
        if len(pg.get_text().strip()) < 10:
            notext.append(i + 1)
        if any(f[1] == "n/a" for f in pg.get_fonts()):
            nofont.append(i + 1)
    chk("PRINT.size", not bad_size, "모든 쪽 A3 420×297 mm (불일치 쪽: %s)" % (bad_size or "없음"))
    chk("PRINT.rotate", not bad_rot, "모든 쪽 /Rotate = 0 (불일치: %s)" % (bad_rot or "없음"))
    chk("PRINT.noraster", not raster, "PDF 내장 래스터 이미지 쪽 %s (래핑된 이미지 도면 없음)" % (raster or "0개"))
    chk("PRINT.text", not notext, "모든 쪽 글자 추출 가능(검색성), 불가: %s" % (notext or "없음"))
    chk("PRINT.fonts", not nofont, "글꼴 임베딩(미임베딩 쪽: %s)" % (nofont or "없음"))
    chk("PRINT.sha", sha(reg["pdf"]) == reg["pdf_sha256"], "도면집 PDF 해시 일치")

    # ── COVERAGE / CLAIMS ───────────────────────────────────────────────────────────────────
    cover = set(reg["published_floor_plans"]) | set(reg["unpublished_floors"])
    chk("COVERAGE.floors", cover == set(order), "17개 층 모두 '발행' 또는 '평면 미발행'으로 추적: 발행 %d, 미발행 %d" % (len(reg["published_floor_plans"]), len(reg["unpublished_floors"])))
    p3 = next(p["page"] for p in reg["sheets"] if p["sheet"] == "A-002")
    txt3 = norm(doc[p3 - 1].get_text())
    chk("COVERAGE.a002", all(f in txt3 for f in order) and txt3.count("평면미발행") >= len(reg["unpublished_floors"]), "A-002에 17개 층 전부와 '평면 미발행' %d회 표기(미발행 층 %d개)" % (txt3.count("평면미발행"), len(reg["unpublished_floors"])))
    bad_claim, n_eq = [], 0
    for i, pg in enumerate(doc):
        t = norm(pg.get_text())
        for m in re.finditer(r"EQUIVALENCEVERIFIED", t):
            n_eq += 1
            tail = t[m.end(): m.end() + 10]
            if "아님" not in tail:
                bad_claim.append(i + 1)
        if "ARCHITECTURAL_FINAL" in t or "FROZEN: true" in t:
            bad_claim.append(i + 1)
    chk("CLAIM.no_false_equivalence", (not bad_claim) and n_eq > 0, "'EQUIVALENCE VERIFIED' 등장 %d회(검사가 헛통과가 아님), 모두 부정(아님) 문맥, 최종본·FREEZE 표기 없음 (문제 쪽: %s)" % (n_eq, bad_claim or "없음"))
    chk("CLAIM.status", reg["status"] == "CANDIDATE — NOT FROZEN", "도면집 상태 = %s" % reg["status"])

    # ── ORIENTATION ─────────────────────────────────────────────────────────────────────────
    chk("ORIENT.north_frame", angdiff(own["frame"]["north_deg"], north) < 0.05, "도면틀 north_deg %.3f ↔ 1층 마스터 %.3f" % (own["frame"]["north_deg"], north))
    ok, msg = elev_orientation_ok(elevr["elevations"], north)
    chk("ORIENT.elevations", ok, msg)
    k_svg = open(secr["section_locator"]["files"]["svg"]["path"], encoding="utf-8").read()
    ang = svg_arrow_angles(k_svg)
    chk("ORIENT.keyplan_arrow", len(ang) == 1 and angdiff(ang[0], north) < 0.1, "키플랜에 그려진 진북 화살표 %s° ↔ 1층 기준 %.2f°" % ([round(x, 2) for x in ang], north))
    bad = []
    for p in planr["plans"]:
        svg = open(p["files"]["svg"]["path"], encoding="utf-8").read()
        m = re.findall(r'<line x1="([\d.\-]+)" y1="([\d.\-]+)" x2="([\d.\-]+)" y2="([\d.\-]+)"', svg)
        if len(m) != 1:
            bad.append((p["sheet"], "화살표 %d개" % len(m)))
            continue
        x1, y1, x2, y2 = (float(v) for v in m[0])
        ang_ = math.degrees(math.atan2(x2 - x1, -(y2 - y1)))
        if angdiff(ang_, north) > 0.1:
            bad.append((p["sheet"], round(ang_, 2)))
    chk("ORIENT.plans_arrow", not bad, "기준층 평면 3장의 진북 화살표 = 1층 기준 %.2f° (불일치: %s)" % (north, bad or "없음"))
    c_, s_ = math.cos(own["frame"]["theta_rad"]), math.sin(own["frame"]["theta_rad"])
    badw = []
    for s in secr["sections"]:
        for (wx, wy), (dx, dy) in zip(s["line_world"], s["line_drawing_frame"]):
            ex, ey = wx * c_ + wy * s_, -wx * s_ + wy * c_                         # 월드 → 도면틀
            if math.hypot(ex - dx, ey - dy) > 0.01:
                badw.append(s["name"])
    chk("ORIENT.section_world_roundtrip", not badw, "단면선 월드↔도면틀 좌표 왕복 일치(회전 방향 규약 확인)")

    # ── ELEVATION ↔ PLAN ────────────────────────────────────────────────────────────────────
    sl3 = pc.load_slice(os.path.join(run, "raw_slices"), "3F")
    slab = pc.polygons_from_segments([s for p in sl3["projection"] for s in p["segments"]])
    pts = []
    for g in (slab.geoms if hasattr(slab, "geoms") else [slab]):
        pts += list(g.exterior.coords)
    bad = []
    for e in elevr["elevations"]:
        v = e["view_direction_in_drawing_frame"]
        beta = math.degrees(math.atan2(v[0], v[1]))
        r = bvec(beta - 90.0)
        us = [x * r[0] + y * r[1] for x, y in pts]
        wp = max(us) - min(us)
        x0, y0, x1, y1 = e["extent_m"]
        if abs((x1 - x0) - wp) > 1.0 or abs(y1 - roof_z) > 0.01:
            bad.append((e["sheet"], round(x1 - x0, 2), round(wp, 2), round(y1, 3)))
    chk("ELEVxPLAN.extent", not bad, "입면 가로폭 = 3F 슬래브를 그 방향 오른쪽 축에 투영한 폭(±1.0 m, 외피 돌출 허용), 높이 상단 = 지붕 %.3f (불일치: %s)" % (roof_z, bad or "없음"))

    # ── 레벨 ────────────────────────────────────────────────────────────────────────────────
    def levels_in(svg, names):
        got = {}
        for m in re.finditer(r">(B2|B1|\d+F|ROOF)\s+([+-]\d+\.\d{3})<", svg):
            got.setdefault(m.group(1), float(m.group(2)))
        miss = [n for n in names if n not in got]
        bad_ = [n for n in names if n in got and abs(got[n] - ((roof_z if n == "ROOF" else floors[n]) - ffl0)) > 0.0006]
        return miss, bad_
    badl = []
    for e in elevr["elevations"]:
        miss, bad_ = levels_in(open(e["files"]["svg"]["path"], encoding="utf-8").read(), ["%dF" % i for i in range(2, 16)] + ["ROOF"])
        if miss or bad_:
            badl.append((e["sheet"], miss, bad_))
    for s in secr["sections"]:
        miss, bad_ = levels_in(open(s["files"]["svg"]["path"], encoding="utf-8").read(), order + ["ROOF"])
        if miss or bad_:
            badl.append((s["sheet"], miss, bad_))
    chk("LEVELS.labels", not badl, "입면 4장은 2F~15F+ROOF, 단면 4장은 B2~15F+ROOF 레벨 라벨이 모두 있고 값이 모델 층판 윗면과 ±0.6 mm 일치 (문제: %s)" % (badl or "없음"))

    # ── SECTION ↔ PLAN ──────────────────────────────────────────────────────────────────────
    from shapely.geometry import Polygon as _P  # noqa
    def tok(nm):
        m = re.search(r"\b(T[1-4]|M[12]|PL|FR|EV[12])\b", nm)
        if m:
            return m.group(1)
        if "캡슐" in nm:
            return "capE" if re.search(r"캡슐\s*동", nm) else "capW"
        return None
    cuts3 = pc.cut_geometries(sl3)
    tubes = {}
    for it, g in cuts3.get("tube_wall", []):
        t = tok(it["name_ko"])
        if t:
            tubes[t] = g.bounds
    badsec = []
    for s in secr["sections"]:
        ax = 0 if s["plane"]["axis"] == "x" else 1
        val = s["plane"]["value_drawing_frame"]
        expect = {t for t, b in tubes.items() if b[ax] <= val <= b[ax + 2]}
        actual = set()
        for c in s["cut_elements"]:
            m = re.search(r"A-CORE-TUBE_(\w+)", c["name"])
            if m:
                actual.add(m.group(1))
        if not expect <= actual:
            badsec.append((s["name"], sorted(expect - actual)))
    chk("SECxPLAN.tubes", not badsec, "각 단면의 절단 평면이 3F 평면에서 지나는 튜브가 모두 단면에서 실제로 절단됨 (누락: %s)" % (badsec or "없음"))
    names_ok = all(len(s["cut_elements"]) > 0 and s["geometry_sha256"] for s in secr["sections"])
    chk("SECxPLAN.cuts", names_ok, "단면 4장 모두 절단 요소와 geometry 해시 기록")

    # ── TRACEABILITY ────────────────────────────────────────────────────────────────────────
    badf, badn = [], []
    for grp, items in (("elev", elevr["elevations"]), ("sec", secr["sections"]), ("det", detr["details"]), ("plan", planr["plans"])):
        for it in items:
            for e, f in it["files"].items():
                if not os.path.exists(f["path"]) or sha(f["path"]) != f["sha256"]:
                    badf.append((it["sheet"], e))
    for e in elevr["elevations"]:
        badn += [n for n in e["source_objects"] if n not in obj_names]
        if not e["source_objects"] or not e["geometry_sha256"]:
            badn.append(e["sheet"])
    for s in secr["sections"]:
        badn += [n for n in s["visible_source_objects"] if n not in obj_names]
    for d in detr["details"]:
        names = list(d["section_visible_objects"]) + (list(d["plan"]["source_objects"]) if d["plan"]["source"] == "glb" else [])     # 1층 마스터 기반 평면의 이름은 GLB 객체가 아니므로 제외
        badn += [n for n in names if n not in obj_names]
    chk("TRACE.files", not badf, "시트 SVG·PDF·PNG 존재와 해시 재계산 일치 (불일치: %s)" % (badf or "없음"))
    chk("TRACE.sources", not badn, "입면·단면·상세의 source 객체가 모두 모델 객체 목록에 존재 (없는 객체: %s)" % (badn[:5] or "없음"))
    chk("TRACE.grades", all(d["grade"].split(" ")[0] in ("MODEL_GEOMETRY", "MODEL_GEOMETRY(1F", "SCHEMATIC") for d in detr["details"]), "상세 10장 모두 사실성 등급 명시: %s" % collections.Counter(d["grade"].split(" ")[0] for d in detr["details"]))
    chk("TRACE.blocked", any("BLOCKED_MISSING_SOURCE" in " ".join(d["notes"]) for d in detr["details"]), "근거 부재 항목(상층 코어 내부)은 BLOCKED_MISSING_SOURCE로 명시하고 그리지 않음")

    # ── LINE ────────────────────────────────────────────────────────────────────────────────
    allv = [e["files"]["svg"]["path"] for e in elevr["elevations"]] + [s["files"]["svg"]["path"] for s in secr["sections"]] + [d["files"]["svg"]["path"] for d in detr["details"]]
    dups, stairs, thin = {}, {}, []
    for f in allv:
        s = open(f, encoding="utf-8").read()
        seg = collections.Counter()
        st = 0
        for m in re.finditer(r'<path d="([^"]+)"([^>]*)/>', s):
            d, attrs = m.group(1), m.group(2)
            w = re.search(r'stroke-width="([\d.]+)"', attrs)
            if w and float(w.group(1)) < 0.04:
                thin.append(os.path.basename(f))
            if 'fill="none"' not in attrs or "stroke-dasharray" in attrs:
                continue
            for sub in d.split("M")[1:]:
                n = [float(x) for x in NUM.findall(sub)]
                pp = list(zip(n[0::2], n[1::2]))
                streak, prev = 0, None
                for p, q in zip(pp, pp[1:]):
                    ln = math.hypot(q[0] - p[0], q[1] - p[1])
                    if ln < 1e-6:
                        continue
                    seg[tuple(sorted([(round(p[0], 2), round(p[1], 2)), (round(q[0], 2), round(q[1], 2))]))] += 1
                    t = "H" if abs(q[1] - p[1]) < 1e-6 else ("V" if abs(q[0] - p[0]) < 1e-6 else "D")
                    if ln < 0.4 and t in "HV" and prev in ("H", "V") and t != prev:
                        streak += 1
                        if streak >= 6:
                            st += 1
                            streak = 0
                    else:
                        streak = 0
                    prev = t if ln < 0.4 else None
        dups[os.path.basename(f)] = sum(1 for v in seg.values() if v > 1)
        stairs[os.path.basename(f)] = st
    chk("LINE.duplicates", sum(dups.values()) == 0, "입면·단면·상세의 실선 중복 선분 합계 %d (파일별 %s)" % (sum(dups.values()), {k: v for k, v in dups.items() if v}))
    chk("LINE.stairstep", sum(stairs.values()) == 0, "계단형 직교 폴리라인 합계 %d" % sum(stairs.values()))
    chk("LINE.minweight", not thin, "0.04 mm 미만 선 %d개" % len(thin))

    # ── SELFTEST: 방향 검사가 결함을 잡는가 ───────────────────────────────────────────────────
    selftest = None
    if a.selftest:
        bad_e = json.loads(json.dumps(elevr["elevations"]))
        v = bad_e[0]["view_direction_in_drawing_frame"]
        bad_e[0]["view_direction_in_drawing_frame"] = [v[1], -v[0]]                  # 90° 회전한 가짜 데이터
        ok2, msg2 = elev_orientation_ok(bad_e, north)
        ok3, msg3 = elev_orientation_ok(elevr["elevations"], north + 90.0)             # 진북을 90° 틀리게 준 경우
        selftest = {"rotated_elevation_detected": not ok2, "wrong_north_detected": not ok3, "msgs": [msg2, msg3]}
        chk("SELFTEST.orientation_check_has_teeth", (not ok2) and (not ok3), "가짜 90° 회전 입면·틀린 진북에서 방향 검사가 FAIL을 냄: %s" % selftest["msgs"])

    fails = [r for r in res if r["status"] == "FAIL"]
    out = {"run": run, "pass": len(res) - len(fails), "fail": len(fails), "total": len(res), "checks": res, "selftest": selftest}
    p = os.path.join(run, "06_QA", "book_qa.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in res:
        print("%-4s %-34s %s" % (r["status"], r["code"], r["msg"]))
    print("BOOK QA: %d/%d PASS, %d FAIL → %s" % (out["pass"], out["total"], out["fail"], p))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
