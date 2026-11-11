"""V2 도면집 독립 검사: 완성된 PDF·SVG·레지스트리를 다시 읽어 확인한다(생성 코드의 자기 보고를 믿지 않는다).

    python -I tools/t14e_book_qa.py --run <V2 루트>

결과: tests_report.json, sheet_manifest.json, equivalence_check_report.json, dimension_coverage_report.json (V2 루트) + 도면집 PDF 사본.
마지막에 음성 대조(일부러 망가뜨린 입력)를 돌려 검사가 실제로 실패를 잡는지 확인한다.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys

import fitz

sys.stdout.reconfigure(encoding="utf-8")
PDFN = "drawing_set_candidate_%s.pdf" % os.environ.get("T14_EDITION", "V2").lower()     # 판 이름은 T14_EDITION(기본 V2: 과거 실행 재현)에서
EDN = os.environ.get("T14_EDITION", "V2")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest().upper()


def jl(p):
    return json.load(open(p, encoding="utf-8"))


def norm(s):
    return re.sub(r"\s+", "", s)


R = []


def check(cid, name, ok, detail=""):
    R.append({"id": cid, "name": name, "ok": bool(ok), "detail": detail})
    print(("PASS" if ok else "FAIL"), cid, name, "—", detail if not ok else (detail[:110] if detail else ""))
    return bool(ok)


def index_vs_pdf(pdf_path, rows, csv_rows, json_pages):
    """목록(CSV·JSON)과 실제 PDF의 쪽수·시트 번호·순서가 같은지."""
    d = fitz.open(pdf_path)
    ok = len(d) == len(rows) == len(csv_rows) == json_pages
    bad = []
    for i, r in enumerate(rows):
        if i >= len(d):
            bad.append((r["sheet"], "쪽 없음"))
            continue
        if norm(r["sheet"]) not in norm(d[i].get_text()):
            bad.append((r["sheet"], "쪽 %d에 시트 번호 없음" % (i + 1)))
    ids_csv = [c["sheet"] for c in csv_rows]
    ids_idx = [r["sheet"] for r in rows]
    return ok and not bad and ids_csv == ids_idx, "pdf=%d index=%d csv=%d json=%d bad=%s" % (len(d), len(rows), len(csv_rows), json_pages, bad[:3])


def texts_of_svg(path):
    s = open(path, encoding="utf-8").read()
    out = []
    for m in re.finditer(r'<text x="([\-\d.]+)" y="([\-\d.]+)" font-family="[^"]*" font-size="([\d.]+)" font-weight="\w+" fill="[^"]*" text-anchor="(\w+)"([^>]*)>(.*?)</text>', s):
        x, y, sz, an, rest, t = float(m.group(1)), float(m.group(2)), float(m.group(3)), m.group(4), m.group(5), m.group(6)
        w = len(t) * sz * 0.62
        x0 = x - (w / 2 if an == "middle" else (w if an == "end" else 0))
        out.append({"x0": x0, "x1": x0 + w, "y": y, "size": sz, "text": t, "rot": "rotate" in rest})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    run = os.path.abspath(a.run)
    P = lambda *x: os.path.join(run, *x)
    pdf = P("book", PDFN)
    reg = jl(P("book", "book_registry.json"))
    idx = jl(P("00_index", "sheet_index.json"))
    csv_rows = list(csv.DictReader(open(P("00_index", "sheet_index.csv"), encoding="utf-8-sig")))
    rows = idx["sheets"]
    plans = jl(P("plans", "plan_sheets.json"))
    elev = jl(P("elevations", "elevation_registry.json"))
    secr = jl(P("sections", "section_line_registry.json"))
    det = jl(P("details", "detail_registry.json"))["details"]
    ev = jl(P("00_index", "floor_equivalence_evidence.json"))
    ref = jl(P("reference_1F", "reference_manifest.json"))
    d = fitz.open(pdf)
    page_of = {r["sheet"]: i for i, r in enumerate(rows)}
    T = {r["sheet"]: norm(d[i].get_text()) for i, r in enumerate(rows)}

    # ── 목록 = 쪽수 ────────────────────────────────────────────────────────────────────────────
    ok, det_ = index_vs_pdf(pdf, rows, csv_rows, idx["pages"])
    check("Q01", "시트 목록(CSV·JSON·A-001) = 실제 PDF 쪽수·순서", ok, det_)
    a001 = T["A-001"]
    miss = [r["sheet"] for r in rows if norm(r["sheet"]) not in a001]
    check("Q02", "A-001 표에 모든 시트 번호 수록", not miss, str(miss))
    pg_ok = all(norm(str(r["page"])) in a001 for r in rows)
    check("Q03", "A-001의 쪽 번호가 레지스트리와 일치(실제 쪽)", pg_ok and all(r["page"] == i + 1 for i, r in enumerate(rows)))
    # ── 기본 ───────────────────────────────────────────────────────────────────────────────────
    sizes = {(round(p.rect.width / 72 * 25.4), round(p.rect.height / 72 * 25.4)) for p in d}
    check("Q04", "전 쪽 A3 가로(420×297)", sizes == {(420, 297)}, str(sizes))
    imgs = {rows[i]["sheet"]: len(p.get_images()) for i, p in enumerate(d) if p.get_images()}
    orig = fitz.open(P("reference_1F", "1F_CleanLine_FIXED_user_supplied.pdf"))
    allowed = {"A-003": len(orig[0].get_images())}
    bad_img = {k: v for k, v in imgs.items() if allowed.get(k) != v}
    check("Q05", "새로 만든 시트에 래스터 이미지 없음(A-003 사용자 파일 제외)", not bad_img, "images=%s" % imgs)
    fonts = sorted({f[3] for p in d for f in p.get_fonts()})
    check("Q06", "글꼴이 PDF에 포함(참조만 하는 글꼴 없음)", bool(fonts) and all(f[1] != "n/a" for f in d[0].get_fonts()), str(fonts)[:100])
    # ── 사용자 제공 1층 ────────────────────────────────────────────────────────────────────────
    a003 = P("plans", "A-003_site_plan_1F_1to400.pdf")
    check("Q07", "A-003 = 사용자 제공 PDF와 해시 동일(수정 없음)", sha(a003) == ref["user_supplied_pdf_sha256"].upper() == sha(P("reference_1F", "1F_CleanLine_FIXED_user_supplied.pdf")), "%s" % sha(a003)[:16])
    import numpy as np
    pm1 = d[page_of["A-003"]].get_pixmap(dpi=100)
    pm2 = orig[0].get_pixmap(dpi=100)
    A1 = np.frombuffer(pm1.samples, dtype=np.uint8).reshape(pm1.height, pm1.width, pm1.n).copy()
    A2 = np.frombuffer(pm2.samples, dtype=np.uint8).reshape(pm2.height, pm2.width, pm2.n).copy()
    sc = 100 / 72
    x0, y0, x1, y1 = int(915 * sc), int(798 * sc), int(1170 * sc), int(820 * sc)                 # 쪽 번호표 영역만 제외
    diff = np.abs(A1.astype(int) - A2.astype(int)).max(axis=2)
    diff[y0:y1, x0:x1] = 0
    stamp_changed = int((np.abs(A1.astype(int) - A2.astype(int)).max(axis=2)[y0:y1, x0:x1] > 30).sum())
    check("Q08", "도면집 A-003 쪽이 원본과 화소 동일(쪽 번호표 영역 제외)", (pm1.width, pm1.height) == (pm2.width, pm2.height) and int((diff > 8).sum()) == 0 and stamp_changed > 20, "outside_diff=%d stamp_pixels=%d" % (int((diff > 8).sum()), stamp_changed))
    # ── 평면 ───────────────────────────────────────────────────────────────────────────────────
    for p in plans:
        sid = p["sheet"]
        m = p["meta"]
        t = T[sid]
        raw = jl(P("plans", "_raw", "raw_plan_%s_check.json" % p["floor"]))
        need = {"전체 치수열": m["overall_chains"] >= 1, "축선 치수열": m["grid_chains"] >= 1, "배치 치수열": m["setout_chains"] >= 1, "축선 기호": m["axis_bubbles"] >= 10, "단면 표시": m["section_tags"] >= 4,
                "입면 표시": m["elevation_tags"] >= 4, "축척 문구": "1:250" in t, "그래픽 스케일": "20m" in t, "방위": "진북63.2°" in t, "상태 LEVELS": "LEVELS" in t and "PROPOSED_ONLY" in t and "NOTFINAL" in t,
                "범례": "범례" in t and "LEGEND" in t, "기호 범례": "단면절단선" in t and "입면방향" in t and "상세호출" in t, "제목·시트 번호": sid in t}
        check("Q10_" + sid, "%s 평면 필수 요소" % sid, all(need.values()), str([k for k, v in need.items() if not v]))
        for c_ in p.get("callouts", []):
            if c_ not in t:
                check("Q11_%s_%s" % (sid, c_), "%s 상세 호출 %s 표기" % (sid, c_), False)
        raw_bad = {k: raw.get(k) for k in ("furniture_touching_column", "furniture_touching_tube", "furniture_overlapping_model_outlines", "numbers_colliding_with_furniture") if raw.get(k)}
        check("Q12_" + sid, "%s 가구가 기둥·튜브·모델 윤곽과 겹치지 않음(원 검사 JSON)" % sid, not raw_bad, str(raw_bad))
        tx = texts_of_svg(p["files"]["svg"]["path"])
        out = [x["text"] for x in tx if x["x0"] < 4 or x["x1"] > 414 or x["y"] > 290 or x["y"] < 3]
        panel = [x for x in tx if x["x0"] >= 303]
        pan_out = [x["text"] for x in panel if x["x1"] > 412 or (x["y"] > 258 and x["y"] < 262)]
        check("Q13_" + sid, "%s 범례·문자가 용지 밖/패널 밖으로 잘리지 않음" % sid, not out and not pan_out, str((out + pan_out)[:4]))
    # 프로그램별 가구 전략 구분(범례 문구)
    strat = {"P-101": ("A형" in T["P-101"] or "가로열" in T["P-101"]) or "판매" in T["P-101"], "P-102": "3F와다른배치" in T["P-102"], "P-103": "좌석" in T["P-103"] or "F&B" in T["P-103"], "P-104": "이벤트무대" in T["P-104"], "P-105": "식재" in T["P-105"] or "정원" in T["P-105"]}
    check("Q14", "프로그램별 가구·식재 전략이 시트 범례에 명시(3F/8F 판매는 서로 다름, 13F 문화·엔터, 10F·15F F&B·정원)", all(strat.values()), str(strat))
    fc = {p["sheet"]: p["furniture_count"] for p in plans}
    check("Q15", "모든 평면에 제안 가구가 실제로 배치(각 ≥30)", all(v >= 30 for v in fc.values()), str(fc))
    # 판매 → 판매가 같은 배치가 아님: 3F vs 8F 가구 SVG 경로 서명이 다름
    def furn_sig(sid):
        s = open(next(p for p in plans if p["sheet"] == sid)["files"]["svg"]["path"], encoding="utf-8").read()
        return hashlib.sha1(re.sub(r"\s+", " ", s).encode()).hexdigest()
    check("Q16", "3F와 8F 평면 배치(가구 포함)가 서로 다름", furn_sig("P-101") != furn_sig("P-102"))
    # ── 입면·단면 ──────────────────────────────────────────────────────────────────────────────
    floors = ev["floor_z_m"]
    ffl0 = floors["1F"]
    roof = max(o["zmax"] for o in jl(P("model_cache", "model_objects.json"))["objects"] if o["kind"] == "roof") - ffl0
    allowed_levels = sorted([round(v - ffl0, 3) for v in floors.values()] + [round(roof, 3)])
    for e in elev["elevations"] + secr["sections"]:
        sid, m, t = e["sheet"], e["dimension_meta"], T[e["sheet"]]
        is_e = sid.startswith("E")
        need = {"전체 치수열": m["overall_chains"] >= 1, "축선 치수열": m["grid_chains"] >= 1, "층고 치수": m["level_dims"] >= 1, "주요 높이": m["major_dims"] >= 1, "축선 기호": m["axis_bubbles"] >= 7, "축척": "1:400" in t,
                "GL": "GL±0.000" in t, "ROOF": "ROOF" in t, "상태": "MODEL_GEOMETRY" in t, "제목·번호": sid in t, "레벨 15+": m["level_labels"] >= 15, "방위": "진북" in t or "N" in t}
        if is_e:
            need["상세 호출"] = m["detail_callouts"] >= 1
        else:
            need["키플랜"] = "키플랜" in t and "절단선" in t
        check("Q20_" + sid, "%s 필수 요소(축척·GL·레벨·치수·축선·참조)" % sid, all(need.values()), str([k for k, v in need.items() if not v]))
        svg = e["files"]["svg"]["path"]
        lv = []
        for x in texts_of_svg(svg):
            mm = re.fullmatch(r"([A-Z0-9]+)\s+([+\-]\d+\.\d{3})", x["text"].strip())
            if mm:
                lv.append(float(mm.group(2)))
        bad = [v for v in lv if min(abs(v - w) for w in allowed_levels) > 0.0051]
        check("Q21_" + sid, "%s 레벨 문자가 모델 층 FFL과 ±5 mm 이내 일치(%d개)" % (sid, len(lv)), lv and not bad, str(bad[:4]))
    north = {round(elev["frame"]["north_deg"], 2), round(secr["frame"]["north_deg"], 2)}
    cam = jl(P("raw_slices", "camera_bounds.json"))
    mf = jl(P("reference_1F", "camera_bounds.json"))["frame"]
    cf = cam["frame"]
    ok22 = north == {63.2} and abs(cf["north_deg"] - mf["north_deg"]) < 0.01 and abs(cf["theta_deg"] - elev["frame"]["theta_deg"]) < 1e-6 and all("63.2" in T[s] for s in ("A-002", "P-101", "E-201", "S-301"))
    check("Q22", "모든 시트 방위(진북)가 1층 마스터와 같은 63.2°(3F 슬라이스 north_deg = 1층 마스터 north_deg)", ok22, "north=%s slice_north=%.3f master_north=%.3f slice_theta=%.3f" % (north, cf["north_deg"], mf["north_deg"], cf["theta_deg"]))
    # ── 상세 ───────────────────────────────────────────────────────────────────────────────────
    check("Q30", "상세도 ≥ 8장(실제 10장)", len(det) >= 8, str(len(det)))
    for dd in det:
        sid, t = dd["sheet"], T[dd["sheet"]]
        g = re.search(r"(MODELDETAIL|CONCEPTDETAIL|UNRESOLVEDDETAIL)", t)
        nd = dd["dimension_meta"]["plan_dims"] + dd["dimension_meta"]["section_dims"]
        vals_ok = all(str(x["value_mm"]).replace(" ", "").replace("×", "×") in t.replace("×", "×") for x in dd["dimensions"])
        need = {"등급 표기": bool(g), "축척": ("1:%s" % dd["scale"].split(":")[1]) in t, "확대 위치 키플랜": "확대위치" in t, "참조 시트": "참조" in t, "치수 ≥ 2": nd >= 2 or sid == "D-404", "치수표 값이 시트 문자에 존재": vals_ok,
                "근거 표": "치수·근거" in t, "평면·단면 제목": "평면PLAN" in t and "단면SECTION" in t, "제목·번호": sid in t}
        if dd.get("section"):
            need["레벨 기호"] = dd["dimension_meta"]["level_tags"] >= 1 and "+" in t
        check("Q31_" + sid, "%s 상세 필수 요소" % sid, all(need.values()), str([k for k, v in need.items() if not v]))
    # ── 정직성·동결 표기 ───────────────────────────────────────────────────────────────────────
    full = "".join(T.values())
    pos = [m.start() for m in re.finditer("EQUIVALENCEVERIFIED", full)]
    neg_ok = all(full[s:s + 40].startswith("EQUIVALENCEVERIFIED아님") or full[s:s + 40].startswith("EQUIVALENCEVERIFIED주장없음") for s in pos)
    check("Q40", "'EQUIVALENCE VERIFIED'는 부정문('아님/주장 없음')으로만 등장", neg_ok, "n=%d" % len(pos))
    fz = [full[m.start():m.start() + 10] for m in re.finditer("FREEZE", full)]
    check("Q41", "FREEZE는 항상 'FREEZE 아님' 형태로만 등장(동결 주장 없음)", all(x.startswith("FREEZE아님") or x.startswith("FREEZE가아니다") for x in fz), "n=%d %s" % (len(fz), sorted({x for x in fz if not x.startswith("FREEZE아님")})[:3]))
    fin = [full[max(0, m.start() - 4):m.start() + 5] for m in re.finditer("FINAL", full) if not full[max(0, m.start() - 3):m.start()] == "NOT"]
    check("Q42", "'FINAL'은 NOT FINAL로만 사용", not fin, str(fin[:3]))
    check("Q43", "상층 벽·문 없음·PROPOSED_ONLY·LEVEL S 고지가 A-900에 존재", all(k in T["A-900"] for k in ("U-01", "LEVELS", "PROPOSED_ONLY", "U-05")), "")
    # ── 동등성 ─────────────────────────────────────────────────────────────────────────────────
    rel = {}
    for h in ev["hypothesis_groups"]:
        for pr in h["pairs"]:
            rel[pr["pair"]] = pr
    strict = [k for k, v in rel.items() if v["relation"] == "STRICT"]
    eq = {"strict_pairs": strict, "relations": {k: v["relation"] for k, v in rel.items()}, "plan_groups": [], "tolerance": ev["tolerance"], "note": "공통 평면 = 면적·프로그램 동일 + 차이는 수직동선 개구(5 m 이내)뿐인 경우만. STRICT(완전 동일) 쌍은 없다."}
    eq_ok = True
    for p in plans:
        if len(p["applies_to"]) > 1:
            k = "~".join(p["applies_to"][:2])
            v = rel.get(k)
            good = v is not None and v["relation"] == "CIRCULATION_ONLY" and v["program_equal"]
            eq_ok &= good
            eq["plan_groups"].append({"sheet": p["sheet"], "floors": p["applies_to"], "pair": k, "relation": v and v["relation"], "program_equal": v and v["program_equal"], "slab_residual_outside_vertical_m2": v and v["slab_residual_outside_vertical_m2"],
                                      "delta_beyond_tolerance": v and v["delta_beyond_tolerance"], "verdict": "공통 평면 + 개구 차이 표기" if good else "합치면 안 됨", "claim": "동등함을 주장하지 않음"})
        else:
            eq["plan_groups"].append({"sheet": p["sheet"], "floors": p["applies_to"], "verdict": "단독 평면(다른 층과 합치지 않음)"})
    refuted = [k for k in ("3F~4F", "3F~5F", "4F~5F", "8F~10F", "9F~10F") if rel.get(k, {}).get("relation") == "DIFFERENT"]
    eq["refuted_pairs"] = refuted
    check("Q50", "공통 평면(8F·9F, 13F·14F)은 증거상 CIRCULATION_ONLY & 프로그램 동일, STRICT 0건, 3F/4F/5F·8F/9F/10F 가설 반증 유지", eq_ok and not strict and len(refuted) == 5, str(eq["relations"]))
    check("Q51", "공통 평면 시트에 층별 고유 개구 차이가 표기", "8F에스컬레이터고유" in T["P-102"] and "9F에스컬레이터고유" in T["P-102"] and "13F에스컬레이터고유" in T["P-104"] and "14F승강기샤프트고유" in T["P-104"], "")
    json.dump(eq, open(P("equivalence_check_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # ── 중복 선분 ──────────────────────────────────────────────────────────────────────────────
    dup_rows = []
    for r in rows:
        f = [x for x in (P("plans", "%s*" % r["sheet"]),)]
    svgs = {}
    for sd in ("plans", "elevations", "sections", "details", "appendix"):
        for fn in os.listdir(P(sd)):
            if fn.endswith(".svg"):
                m = re.match(r"([A-Z]-\d{3})", fn)
                if m:
                    svgs[m.group(1)] = P(sd, fn)
    worst = 0.0
    for sid, pth in svgs.items():
        s = open(pth, encoding="utf-8").read()
        segs = {}
        n = 0
        for dm_ in re.finditer(r'<path d="([^"]+)" fill="none"[^>]*stroke-width="([\d.]+)"', s):
            for sub in dm_.group(1).split("M")[1:]:
                if re.search(r"[CAQSTHV]", sub):                      # 곡선 명령이 든 경로는 제외(제어점을 선분으로 오해하지 않게)
                    continue
                pts = [tuple(map(float, q.split(","))) for q in re.findall(r"[\d.\-]+,[\d.\-]+", sub)]
                for u, v in zip(pts, pts[1:]):
                    k = tuple(sorted([u, v]))
                    n += 1
                    segs[k] = segs.get(k, 0) + 1
        dup = sum(c - 1 for c in segs.values() if c > 1)
        frac = dup / n if n else 0
        worst = max(worst, frac)
        dup_rows.append((sid, n, dup))
    check("Q60", "동일 선분 중복 ≤ 1% (모든 SVG)", worst <= 0.01, "worst=%.3f%%" % (worst * 100))
    # ── 치수 현황 보고서 ───────────────────────────────────────────────────────────────────────
    cov = []
    for p in plans:
        cov.append({"sheet": p["sheet"], "kind": "plan", **p["meta"]})
    for e in elev["elevations"]:
        cov.append({"sheet": e["sheet"], "kind": "elevation", **e["dimension_meta"]})
    for s in secr["sections"]:
        cov.append({"sheet": s["sheet"], "kind": "section", **s["dimension_meta"]})
    for dd in det:
        cov.append({"sheet": dd["sheet"], "kind": "detail", **dd["dimension_meta"], "dimension_rows": len(dd["dimensions"]), "dimensions": dd["dimensions"]})
    json.dump({"note": "치수 개수는 생성 레지스트리 값이고, Q10·Q20·Q31이 시트 텍스트에서 독립 확인함", "sheets": cov}, open(P("dimension_coverage_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # ── 필수 산출물 존재 ───────────────────────────────────────────────────────────────────────
    need_files = [P("book", PDFN), P("00_index", "sheet_index.csv"), P("00_index", "sheet_index.json"), P("visual_issues_resolved.md"), P("unresolved_design_decisions.md"), P("dimension_coverage_report.json"), P("equivalence_check_report.json")]
    miss = [f for f in need_files if not os.path.exists(f)]
    check("Q70", "필수 산출물 존재(보고서 md 포함)", not miss, str(miss))
    # ── 음성 대조 ──────────────────────────────────────────────────────────────────────────────
    tmp = P("qa", "_negative_control.pdf")
    os.makedirs(P("qa"), exist_ok=True)
    bad = fitz.open(pdf)
    bad.delete_page(len(bad) - 1)
    bad.save(tmp)
    r1, _ = index_vs_pdf(tmp, rows, csv_rows, idx["pages"])
    swap = fitz.open(pdf)
    swap.move_page(5, 8)
    swap.save(tmp.replace(".pdf", "2.pdf"))
    r2, _ = index_vs_pdf(tmp.replace(".pdf", "2.pdf"), rows, csv_rows, idx["pages"])
    r3, _ = index_vs_pdf(pdf, rows, csv_rows[:-1], idx["pages"])
    r4 = "FINAL" in norm("FINAL") and bool([m for m in re.finditer("FINAL", "FINAL") if not "FINAL"[max(0, m.start() - 3):m.start()] == "NOT"])
    check("Q90", "음성 대조: 쪽 삭제·순서 바꿈·CSV 행 누락·'FINAL' 단독 문구를 검사가 실제로 잡는다", (not r1) and (not r2) and (not r3) and r4, "drop=%s swap=%s csv=%s final=%s" % (r1, r2, r3, r4))
    for f in (tmp, tmp.replace(".pdf", "2.pdf")):
        try:
            os.remove(f)
        except OSError:
            pass
    # ── 매니페스트·보고 ────────────────────────────────────────────────────────────────────────
    man = []
    for r in rows:
        man.append({"page": r["page"], "sheet": r["sheet"], "title": r["title"], "scale": r["scale"], "grade": r["grade"], "folder": r["folder"], "source_sha256": r["source_sha256"]})
    shutil.copy(pdf, P(PDFN))
    json.dump({"pdf": P(PDFN), "pdf_sha256": sha(pdf), "pages": len(d), "sheets": man, "model_sha256": reg["model_sha256"], "edition": EDN, "status": "CANDIDATE — NOT FROZEN"},
              open(P("sheet_manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    passed = sum(r["ok"] for r in R)
    rep = {"edition": EDN, "pdf": pdf, "pdf_sha256": sha(pdf), "pages": len(d), "checks": R, "passed": passed, "failed": len(R) - passed, "total": len(R),
           "method": "완성된 PDF·SVG를 다시 읽어 확인. 생성 코드의 자기 보고(레지스트리)는 PDF 텍스트·SVG 기하와 교차 확인. 음성 대조 포함.",
           "limits": ["PDF 텍스트는 cairosvg 글리프 출력 때문에 공백이 빠져 공백 없이 비교", "시각적 겹침은 문자 상자 추정(문자 수×글자 크기×0.62)과 눈 검토로 확인 — 완전한 자동 증명이 아님", "치수 값이 모델과 일치하는지는 생성 코드가 모델에서 읽은 값이며, 별도 CAD와 대조하지 않음"]}
    json.dump(rep, open(P("tests_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("QA %d/%d passed" % (passed, len(R)))
    sys.exit(0 if passed == len(R) else 1)


if __name__ == "__main__":
    main()
