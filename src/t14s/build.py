"""Build driver: 16 floor plans -> SVG, DXF, A1 PDF, A3 split PDF, hi-res PNG, metadata JSON, SHA256 manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import fitz
from shapely.ops import unary_union

from . import ROOT
from . import annotate as AN
from . import export_dxf as XD
from . import export_svg as XS
from . import layout as LY
from . import planner as PL
from . import sheets as SH
from . import source as SRC
from .model import MODEL_VERIFIED, PROPOSED, SYMBOL_REUSE

OUT = ROOT / "outputs" / "T14T"
SCHEMA = "C-T14T-FLOOR-1.0"
PNG_DPI = 200
REVIEW_STATE = "C_T14T_READY_FOR_CHATGPT_INDEPENDENT_REVIEW"


def sha(p) -> str:
    return SRC.sha256(p)


def floor_titles(f: str) -> str:
    if f.startswith("B"):
        return "지하 %s층 평면도" % f[1:]
    return "%s층 평면도" % f[:-1]


CORRECTIONS: dict = {}
BASELINE = ROOT / "outputs" / "T14S"                       # PR #29 deliverables, kept unchanged in this branch


def corrections_for(f: str, d, g) -> list:
    """정정 전(PR #29 메타데이터)과 정정 후의 사실 기록. 점수·평가 없음."""
    out = []
    old_p = BASELINE / f / ("T14S_%s_plan_metadata.json" % f)
    old = json.loads(old_p.read_text(encoding="utf-8")) if old_p.exists() else {"design_proposed": {"notes": [], "rooms": [], "doors": 0}}
    old_notes = [n for n in old["design_proposed"]["notes"] if n.startswith(("CIRC_", "CORE_", "RESTROOM_"))]
    G = d.meta.get("graph", {})
    S = G.get("summary", {})
    dec = d.meta.get("decisions", {})
    out.append({"area": "P0", "issue": "방문객 동선 연결 (PR #29 메모: %s)" % ("; ".join(n.split(":")[0].split(" ")[0] for n in old_notes) or "없음"),
                "change": "기하 보행 그래프로 재계산: 접근 노드 %s개 중 %s개 바닥판 위 연결, 개구 가장자리 임시 접점 %s개, 미결 %s건; 점포 문 앞 %s/%s 연결"
                % (S.get("visitor_nodes"), S.get("connected"), S.get("provisional_at_opening_edge"), S.get("unresolved"), S.get("unit_doors_reachable"), S.get("unit_doors")),
                "open_items": [u["id"] for u in G.get("unresolved", [])], "decisions": sorted(dec)})
    if "D-03" in dec:
        out.append({"area": "P0", "issue": "승강기 로비 출입구가 캡슐 개구와 접해 설 자리 없음",
                    "change": "출입구를 홀 쪽으로 회전(제안): " + ", ".join("%s %+d°" % (x["tube"], x["turn_deg"]) for x in dec["D-03"] if "turn_deg" in x), "decisions": ["D-03"]})
    if "D-02" in dec:
        out.append({"area": "P0/P1", "issue": "이 층에 바닥판이 없는 코어", "change": "통과 전용 닫힌 샤프트로 그리고 '출입 불가' 표시(제안): 코어 " + ", ".join(x["core"] for x in dec["D-02"]), "decisions": ["D-02"]})
    if d.meta.get("cars"):
        out.append({"area": "P1", "issue": "도면에 내부 식별자 노출 (%s)" % ", ".join(c["source_id"] for c in d.meta["cars"]),
                    "change": "도면 글자·실 일람에서 제거, 원본 식별자는 메타데이터(model_objects_not_drawn)에 보존"})
    kinds = {}
    for o in d.meta.get("openings", []):
        kinds.setdefault(o["kind"], []).append(o)
    if "no_slab_region" in kinds:
        out.append({"area": "P1", "issue": "바닥판 없는 영역이 보행 바닥과 구분되지 않음", "change": "하부 개방 해칭과 라벨 추가; 관통하는 기둥·튜브·코어는 그대로 표시(기둥에 점선 링)"})
    if "free_opening" in kinds:
        out.append({"area": "P1", "issue": "자유 개구부 가장자리 표기 없음", "change": "자유 개구 %d곳에 해칭·라벨, 제안 난간(붉은 점선, 미검증) 표기" % len(kinds["free_opening"])})
    if "capsule_opening" in kinds:
        out.append({"area": "P1", "issue": "캡슐 개구가 바닥처럼 읽힘", "change": "하부 개방 해칭, 모델의 에스컬레이터 축을 투영(보라색)하고 승·하차 표기"})
    n_sup = sum(1 for r in d.rooms if r["kind"] == "support")
    n_svc = len(G.get("service_edges", []))
    if n_sup:
        out.append({"area": "P2", "issue": "점포가 분리되지 않은 단일 실", "change": "판매·객석·문화 주 공간과 지원(BOH) 실 %d개 분리, FR 반입 접점까지 서비스 경로 %d개" % (n_sup, n_svc)})
    if g.floor in ("11F", "12F", "13F", "14F"):
        from . import program as PGM
        out.append({"area": "P2", "issue": "문화 용도가 자리표시자 이름", "change": "운영 개념 제안: %s" % PGM.CULTURE_CONCEPT[g.floor][0]})
    gardens = [r for r in d.rooms if r["kind"] == "garden"]
    if gardens:
        out.append({"area": "P2", "issue": "정원 홀에 흩어진 기호만 있음", "change": "산책로·식재 베드·벤치·그늘 시설 추가: " + "; ".join(
            "산책로 %s m, 베드 %s, 수목 %s, 벤치 %s" % (r["garden"]["path_m"], r["garden"]["beds"], r["garden"]["trees"], r["garden"]["benches"]) for r in gardens if r.get("garden"))})
    return out


def program_table():
    out, levels = {}, {}
    names = {"retail": "판매", "fnb": "F&B", "culture": "문화", "garden": "정원", "service": "서비스"}
    for f in SRC.FLOORS:
        g = SRC.load_floor(f)
        levels[f] = round(g.z, 3)
        seen = []
        for z in g.zones:
            k = names.get(LY.PROG.get(z["name_ko"], "retail"))
            if k not in seen:
                seen.append(k)
        out[f] = "/".join(seen)
    return out, levels


def build_floor(f: str, programs, levels, out_root: Path = OUT) -> dict:
    t0 = time.time()
    g = SRC.load_floor(f)
    pl = PL.Planner2(g, 7)
    d = pl.run()
    area_by, by_role = {}, {}
    for r in d.rooms:
        area_by[r["program"]] = area_by.get(r["program"], 0.0) + r["poly"].area
        k = "main" if r["kind"] == "unit" else r["kind"]
        by_role[k] = by_role.get(k, 0.0) + r["poly"].area
    gross = g.outline.area
    info = {"floor": f, "title_ko": floor_titles(f) + " (정정 후보)", "level": "%+.3f" % round(g.z, 3), "sheet_id": "T14T-P-%s" % f,
            "subtitle": "모델 검증 구조 위에 제안한 구획·문·실·가구·동선 · 프로그램: " + programs.get(f, ""),
            "north_deg": g.north_deg, "slab_gross_m2": gross, "slab_net_m2": g.slab.area, "opening_m2": gross - g.slab.area,
            "room_area_by_program": area_by, "room_area_by_role": by_role, "levels": levels}
    odir = out_root / f
    odir.mkdir(parents=True, exist_ok=True)
    stem = "T14T_%s_plan" % f
    files = {}
    # A1 sheet: SVG (editable), PDF (vector), PNG (hi-res)
    a1 = SH.compose_a1(d, info, programs, SRC.FLOORS)
    svg_text = XS.save_svg(a1, odir / (stem + "_A1_1to200.svg"))
    XS.svg_to_pdf(svg_text, odir / (stem + "_A1_1to200.pdf"))
    wpx = int(round(SH.A1[0] / 25.4 * PNG_DPI))
    XS.svg_to_png(svg_text, odir / (stem + "_A1_1to200.png"), wpx)
    # A3 split sheets -> one two-page PDF
    pages = []
    for half in ("N", "S"):
        s3 = SH.compose_a3(d, info, half)
        txt = s3.string()
        tmp = odir / ("_tmp_a3_%s.pdf" % half)
        XS.svg_to_pdf(txt, tmp)
        pages.append(tmp)
    merged = fitz.open()
    for p in pages:
        with fitz.open(p) as src:
            merged.insert_pdf(src)
    a3 = odir / (stem + "_A3_split_1to200.pdf")
    merged.save(a3)
    merged.close()
    for p in pages:
        p.unlink()
    ent = XD.write_dxf(d, odir / (stem + ".dxf"))
    # metadata
    rooms = [{"id": r["id"], "name": r["name"], "program": r["program"], "kind": r["kind"], "area_m2": r["area_m2"],
              "provenance": r["prov"], "use": r.get("use", ""), "role": r.get("role"), "parent_id": r.get("parent_id"),
              "garden": r.get("garden")} for r in sorted(d.rooms, key=lambda r: r["id"])]
    meta = {
        "schema": SCHEMA, "floor": f, "level_ffl_m": round(g.z, 3), "review_state": REVIEW_STATE,
        "approval": "NOT_APPROVED", "frozen": False, "scale": "1:200",
        "sheets": {"A1": "841x594 mm landscape", "A3": "420x297 mm landscape, 2-page north/south split with match line y=+9.000"},
        "source": {"slice_file": "floor_%s_slice.json" % f, "slice_sha256": g.slice_sha256, "elements": g.elements_count,
                   "source_manifest": "data/t14s/source_slices/manifest.json",
                   "model_cache_sha256": {"model_world.npz": "992e2ec51ec17dc494ed2f99ddb11298671449dd6661d92df3b3536a0049537b",
                                          "model_objects.json": "722dd7359e2f13534ff4ae91088ba8649e8a8f96b27c60f000ddb09c01106488"},
                   "glb": "BLOCKED_MISSING_SOURCE (cache only, as in V4 U-20)"},
        "geometry_verified": {"slab_gross_m2": round(gross, 1), "slab_net_m2": round(g.slab.area, 1),
                              "opening_m2": round(gross - g.slab.area, 1), "openings": len(g.holes), "columns": len(g.columns),
                              "cores": sorted(g.cores), "tubes": sorted(g.tubes), "shafts": sorted(g.shafts),
                              "escalator_cuts": [e["name"] for e in g.escalators], "ramp_present": bool(g.ramps),
                              "escalator_axes": [{"source_id": e["source_id"], "from": e["from"], "to": e["to"], "role_here": e["role"], "low_xy": [round(v, 2) for v in e["low"]],
                                                  "high_xy": [round(v, 2) for v in e["high"]], "z_low": round(e["z_low"], 2), "z_high": round(e["z_high"], 2)} for e in g.esc_ends],
                              "model_objects_not_drawn": d.meta.get("cars", []), "openings_classified": d.meta.get("openings", []),
                              "program_zones": [{"name_ko": z["name_ko"], "program_floor": z["program_floor"], "area_m2": round(z["poly"].area, 1)} for z in g.zones]},
        "design_proposed": {"rooms": rooms, "unit_count": sum(1 for r in rooms if r["kind"] == "unit"), "doors": d.meta.get("doors", []) and len(d.meta["doors"]),
                            "room_area_by_program_m2": {k: round(v, 1) for k, v in area_by.items()},
                            "room_area_by_role_m2": {k: round(v, 1) for k, v in by_role.items()},
                            "circulation_graph": d.meta.get("graph", {}), "decision_refs": d.meta.get("decisions", {}),
                            "vertical_elements": d.meta.get("vertical", []), "notes": d.notes,
                            "method": "C-T14T targeted corrections on the C-T14S planner: raster walking graph, sales/BOH sub-division, culture concepts, garden design, open-to-below notation; verified geometry unchanged"},
        "corrections_vs_pr29": corrections_for(f, d, g),
        "provenance_counts": d.counts_by_prov(),
        "provenance_legend": {MODEL_VERIFIED: "taken from the model slice", SYMBOL_REUSE: "verified 1F symbol geometry placed in a proposed position/content",
                              PROPOSED: "architectural proposal, not in the model"},
        "dxf_entities": ent, "png_dpi": PNG_DPI, "build_seconds": round(time.time() - t0, 1),
    }
    (odir / (stem + "_metadata.json")).write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    for p in sorted(odir.iterdir()):
        files[p.name] = {"sha256": sha(p), "bytes": p.stat().st_size}
    return {"floor": f, "dir": odir, "files": files, "rooms": len(rooms), "notes": d.notes, "seconds": meta["build_seconds"]}


def write_manifest(out: Path):
    """SHA256 manifest of every floor directory on disk (a subset build never drops other floors)."""
    floors = {}
    for f in SRC.TARGET_FLOORS:
        fd = out / f
        if fd.is_dir():
            floors[f] = {p.name: {"sha256": sha(p), "bytes": p.stat().st_size} for p in sorted(fd.iterdir()) if p.is_file()}
    manifest = {"schema": SCHEMA + "-MANIFEST", "review_state": REVIEW_STATE, "floors": floors}
    (out / "SHA256_MANIFEST.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--floors", nargs="*", default=SRC.TARGET_FLOORS)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    programs, levels = program_table()
    out = Path(a.out)
    results = []
    for f in a.floors:
        r = build_floor(f, programs, levels, out)
        results.append(r)
        print("%-4s built in %.1fs: rooms=%d files=%d dir=%s" % (f, r["seconds"], r["rooms"], len(r["files"]), r["dir"].resolve()))
    write_manifest(out)
    print("manifest:", (out / "SHA256_MANIFEST.json").resolve())


if __name__ == "__main__":
    main()
