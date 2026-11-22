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
from . import sheets as SH
from . import source as SRC
from .model import MODEL_VERIFIED, PROPOSED, SYMBOL_REUSE

OUT = ROOT / "outputs" / "T14S"
SCHEMA = "C-T14S-FLOOR-1.0"
PNG_DPI = 200
REVIEW_STATE = "READY_FOR_CHATGPT_INDEPENDENT_REVIEW"


def sha(p) -> str:
    return SRC.sha256(p)


def floor_titles(f: str) -> str:
    if f.startswith("B"):
        return "지하 %s층 평면도" % f[1:]
    return "%s층 평면도" % f[:-1]


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
    pl = LY.Planner(g, 7)
    d = pl.run()
    area_by = {}
    for r in d.rooms:
        area_by[r["program"]] = area_by.get(r["program"], 0.0) + r["poly"].area
    gross = g.outline.area
    info = {"floor": f, "title_ko": floor_titles(f) + " (제안 후보)", "level": "%+.3f" % round(g.z, 3), "sheet_id": "T14S-P-%s" % f,
            "subtitle": "모델 검증 구조 위에 제안한 구획·문·실·가구·동선 · 프로그램: " + programs.get(f, ""),
            "north_deg": g.north_deg, "slab_gross_m2": gross, "slab_net_m2": g.slab.area, "opening_m2": gross - g.slab.area,
            "room_area_by_program": area_by, "levels": levels}
    odir = out_root / f
    odir.mkdir(parents=True, exist_ok=True)
    stem = "T14S_%s_plan" % f
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
              "provenance": r["prov"], "use": r.get("use", "")} for r in sorted(d.rooms, key=lambda r: r["id"])]
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
                              "program_zones": [{"name_ko": z["name_ko"], "program_floor": z["program_floor"], "area_m2": round(z["poly"].area, 1)} for z in g.zones]},
        "design_proposed": {"rooms": rooms, "unit_count": sum(1 for r in rooms if r["kind"] == "unit"), "doors": d.meta.get("doors", []) and len(d.meta["doors"]),
                            "room_area_by_program_m2": {k: round(v, 1) for k, v in area_by.items()},
                            "vertical_elements": d.meta.get("vertical", []), "notes": d.notes,
                            "method": "shapely booleans on the verified slab; units on the 9 m column grid; engine stair-core/restroom/tube symbols reused; furniture from upper_layouts + fitout"},
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
