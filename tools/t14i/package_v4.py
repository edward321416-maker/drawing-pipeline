"""Package the C-T14I deliverables into docs/t14i_graduation from a finished run.

    python -X utf8 tools/t14i/package_v4.py --run <RUN> --out docs/t14i_graduation --base origin/claude/t14g-candidate-v3-full

Copies the two PDFs + indexes + contact sheets, writes per-sheet PDF/SVG/PNG, the cross-reference graph (both PDFs), the source manifest
(SHA256 of model cache, outputs, sources), before/after panels (V3 page crop | V4 page crop) and the unified diff. QA reports that other
tools wrote below RUN\\v4\\qa are copied as they are (this script never fabricates them).
"""
import argparse
import glob
import json
import os
import platform
import re
import shutil
import subprocess

import t14i  # noqa: F401
from t14i import config as cfg, common
import pymupdf  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from t14f import fonts  # noqa: E402
from t14g import qa_pdf, modelsrc  # noqa: E402

MM = 72.0 / 25.4
ROOT = t14i.ROOT
V3_PDF = os.path.join(ROOT, "docs", "t14g_v3", "Candidate_V3_drawing_set.pdf")
V3_INDEX = os.path.join(ROOT, "docs", "t14g_v3", "sheet_index.json")


def sh(*a, cwd=ROOT):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def font(sz, bold=False):
    return ImageFont.truetype(fonts.resolve("bold" if bold else "regular")[0], sz)


def page_of(index_json, sheet):
    for s in common.jl(index_json)["sheets"]:
        if s["sheet"] == sheet:
            return s["page"]
    return None


def crop(pdf, pno, dpi, box_mm=None):
    pg = pymupdf.open(pdf)[pno - 1]
    clip = pymupdf.Rect(*[v * MM for v in box_mm]) if box_mm else None
    pm = pg.get_pixmap(dpi=dpi, clip=clip)
    return Image.frombytes("RGB", (pm.width, pm.height), pm.samples)


def find_box(pdf, pno, text, rx, ry):
    hits = pymupdf.open(pdf)[pno - 1].search_for(text)
    if not hits:
        return None
    r = hits[0]
    cx, cy = (r.x0 + r.x1) / 2 / MM, (r.y0 + r.y1) / 2 / MM
    return (max(0, cx - rx), max(0, cy - ry), cx + rx, cy + ry)


def panel(before, after, caption, out, lb="BEFORE  Candidate V3", la="AFTER  Candidate V4 (C-T14I)"):
    W = before.width + after.width + 36
    H = max(before.height, after.height) + 76
    im = Image.new("RGB", (W, H), "#fff")
    d = ImageDraw.Draw(im)
    d.text((12, 8), caption, font=font(20, True), fill="#111")
    d.text((12, 42), lb, font=font(17), fill="#a33")
    d.text((before.width + 24, 42), la, font=font(17), fill="#063")
    im.paste(before, (12, 70))
    im.paste(after, (before.width + 24, 70))
    d.rectangle([12, 70, 12 + before.width, 70 + before.height], outline="#999")
    d.rectangle([before.width + 24, 70, before.width + 24 + after.width, 70 + after.height], outline="#999")
    im.save(out, optimize=True)


# (file name, V4 sheet, V3 sheet, box mm on V4 page or None, box mm on V3 page or None (same as V4 if None), dpi, caption). A box given as text finds the label on the page.
PANELS = [
    ("01_P-101_number_symbols", "P-101", "P-101", (118, 70, 262, 200), None, 130, "P-101: zone number symbols (V3: 0.49-0.57 mm high) and legend text"),
    ("02_P-104_number_symbols", "P-104", "P-104", (118, 70, 262, 200), None, 130, "P-104: zone number symbols and dimension text sizes"),
    ("03_D-401_spiral_ramp", "D-401", "D-401", None, None, 70, "D-401 spiral ramp: plan + development section + intent/relationship (V3: floating lumps, empty areas)"),
    ("04_D-402_light_tube", "D-402", "D-402", None, None, 70, "D-402 light tube"),
    ("05_D-403_panoramic_elevator", "D-403", "D-403", None, None, 70, "D-403 panoramic elevator"),
    ("06_D-404_core", "D-404", "D-404", None, None, 70, "D-404 core: V3 printed 'section: none'; V4 section (model levels) + concept section separated"),
    ("07_D-405_capsule", "D-405", "D-405", None, None, 70, "D-405 capsule"),
    ("08_D-406_envelope", "D-406", "D-406", None, None, 70, "D-406 envelope and slab edge (model vs concept separated)"),
    ("09_D-407_escalator", "D-407", "D-407", None, None, 70, "D-407 escalator (30.0 deg incline kept; landings, openings, relationship)"),
    ("10_D-408_sunken", "D-408", "D-408", None, None, 70, "D-408 sunken stair: section added; 458 mm shown as DERIVED, not approved"),
    ("11_D-409_cargo_lift", "D-409", "D-409", None, None, 70, "D-409 cargo lift: loading -> storage -> shaft route (concept) on model plan"),
    ("12_D-410_roof", "D-410", "D-410", None, None, 70, "D-410 roof and setback"),
    ("13_S-301_symbols", "S-301", "S-301", None, None, 70, "S-301: section symbols moved outside the axis-bubble ring"),
    ("14_E-201_levels_outline", "E-201", "E-201", (230, 20, 412, 160), None, 130, "E-201: tube-top level label and outline overshoot explained (54610 = 54000 + 600)"),
    ("15_A-902_floor_overview", "A-902", "A-902", None, None, 60, "A-902: area labels re-defined (program volume projection vs slab) - see A-903"),
    ("16_P-101_vs_P-201_print_size", "P-201", "P-101", None, None, 45, "3F plan: A3 1:250 overview (V3) | A1 1:200 full plan (V4)"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=common.RUN_DEFAULT)
    ap.add_argument("--out", required=True)
    ap.add_argument("--base", required=True)
    a = ap.parse_args()
    run, out = os.path.abspath(a.run), os.path.abspath(a.out)
    bk = os.path.join(run, "v4", "book")
    os.makedirs(out, exist_ok=True)
    pdf1, pdf2 = os.path.join(out, cfg.OUT_BOOK_I), os.path.join(out, cfg.OUT_BOOK_II)
    for src, dst in ((os.path.join(bk, cfg.OUT_BOOK_I), pdf1), (os.path.join(bk, cfg.OUT_BOOK_II), pdf2)):
        shutil.copy(src, dst)
    for f in glob.glob(os.path.join(bk, "*_index.*")) + glob.glob(os.path.join(bk, "*Contact_Sheet.png")) + [os.path.join(bk, "book_registry.json")]:
        shutil.copy(f, out)
    idx1 = os.path.join(out, os.path.splitext(cfg.OUT_BOOK_I)[0] + "_index.json")
    idx2 = os.path.join(out, os.path.splitext(cfg.OUT_BOOK_II)[0] + "_index.json")
    rows1, rows2 = common.jl(idx1)["sheets"], common.jl(idx2)["sheets"]

    # per-sheet PDF / SVG / PNG (source sheets as built; PNG re-rendered from the assembled page at 150 dpi)
    skipped_svg = []
    for pdf, rows, folder in ((pdf1, rows1, "partI"), (pdf2, rows2, "partII")):
        reg = common.jl(os.path.join(bk, "book_registry.json"))
        for p in rows:
            d = os.path.join(out, "sheets", folder, p["folder"] or "misc")
            os.makedirs(d, exist_ok=True)
            src = None
            for f in glob.glob(os.path.join(run, "v4", "**", p["sheet"] + "*.pdf"), recursive=True) + glob.glob(os.path.join(run, "**", p["sheet"] + "_*.pdf"), recursive=True):
                if common.sha_file(f) == p["source_sha256"]:
                    src = f
                    break
            if src is None:
                m = [f for f in glob.glob(os.path.join(run, "**", "*.pdf"), recursive=True) if os.path.basename(f).startswith(p["sheet"])]
                src = m[0] if m else None
            if src:
                shutil.copy(src, os.path.join(d, p["sheet"] + ".pdf"))
                svg = os.path.splitext(src)[0] + ".svg"
                if os.path.exists(svg):
                    if os.path.getsize(svg) <= 6 * 1024 * 1024:
                        shutil.copy(svg, os.path.join(d, p["sheet"] + ".svg"))
                    else:
                        skipped_svg.append((p["sheet"], os.path.getsize(svg)))
            crop(pdf, p["page"], 150).save(os.path.join(d, p["sheet"] + ".png"), optimize=True)
    # detail sheets also in one flat folder for the reviewer
    dd = os.path.join(out, "details")
    os.makedirs(dd, exist_ok=True)
    for p in rows2:
        if p["sheet"].startswith("D-4"):
            for e in ("pdf", "svg", "png"):
                s = os.path.join(out, "sheets", "partII", p["folder"] or "misc", p["sheet"] + "." + e)
                if os.path.exists(s):
                    shutil.copy(s, os.path.join(dd, p["sheet"] + "." + e))

    # 1:200 deliverables in one reviewer-facing folder.
    p200 = os.path.join(out, "plans_1to200")
    os.makedirs(p200, exist_ok=True)
    for p in rows2:
        if p["sheet"] in ("P-201", "P-202", "P-211", "P-212", "P-213", "P-214"):
            for e in ("pdf", "svg", "png"):
                s = os.path.join(out, "sheets", "partII", p["folder"] or "misc", p["sheet"] + "." + e)
                if os.path.exists(s):
                    shutil.copy(s, os.path.join(p200, p["sheet"] + "." + e))

    # Finished QA and audit records are copied, never regenerated here.
    qa_out = os.path.join(out, "qa")
    os.makedirs(qa_out, exist_ok=True)
    for f in glob.glob(os.path.join(run, "v4", "qa", "*")):
        if os.path.isfile(f):
            shutil.copy(f, qa_out)
    for f in glob.glob(os.path.join(run, "v4", "area", "area_reconciliation.*")):
        shutil.copy(f, out)
    unresolved = os.path.join(run, "v4", "appendix_v4", "unresolved_design_decisions.md")
    if os.path.exists(unresolved):
        shutil.copy(unresolved, out)

    # before / after panels
    ba = os.path.join(out, "before_after")
    os.makedirs(ba, exist_ok=True)
    made = []
    for name, s4, s3, box, box3, dpi, cap in PANELS:
        try:
            p4, p3 = page_of(idx2, s4) or page_of(idx1, s4), page_of(V3_INDEX, s3)
            pdf4 = pdf2 if page_of(idx2, s4) else pdf1
            if p4 is None or p3 is None:
                continue
            b = find_box(pdf4, p4, box, 30, 14) if isinstance(box, str) else box
            panel(crop(V3_PDF, p3, dpi, box3 or b), crop(pdf4, p4, dpi, b), cap, os.path.join(ba, name + ".png"))
            made.append(name)
        except Exception as e:  # a missing/changed layout must not hide the others; it is reported below
            print("before/after FAILED", name, e)
    print("before/after panels:", len(made))

    # cross-reference graph over BOTH PDFs
    docs = {"I": (pymupdf.open(pdf1), rows1), "II": (pymupdf.open(pdf2), rows2)}
    scale = {r["sheet"]: r["scale"] for _, rows in docs.values() for r in rows}
    edges = []
    for part, (doc, rows) in docs.items():
        for r in rows:
            if r["sheet"] == "A-003" or r["sheet"] in ("A-001", "G-002"):
                continue                                                          # index pages list every sheet by design
            for ln in qa_pdf._lines(doc[r["page"] - 1]):
                for sid, den in qa_pdf.CALL_RE.findall(ln["text"]):
                    edges.append({"from": r["sheet"], "to": sid, "kind": "callout", "printed_scale": "1:" + den, "target_scale": scale.get(sid), "ok": scale.get(sid) == "1:" + den})
                # Korean letters are Unicode word characters, so ``\bD-404``
                # misses strings such as ``상세D-404``.  Only exclude an ASCII
                # sheet-id prefix; Korean prose immediately before the id is valid.
                for sid in set(re.findall(r"(?<![A-Z0-9])[ESPD]-\d{3}(?!\d)", ln["text"])):
                    if sid != r["sheet"] and not qa_pdf.CALL_RE.search(ln["text"]):
                        edges.append({"from": r["sheet"], "to": sid, "kind": "reference", "ok": sid in scale})
    uniq = {(e["from"], e["to"], e["kind"]): e for e in edges}
    edges = list(uniq.values())
    orphans = sorted(s for s in scale if s.startswith("D-") and not any(e["to"] == s for e in edges))
    json.dump({"nodes": [{"sheet": r["sheet"], "part": p, "page": r["page"], "scale": r["scale"]} for p, (_, rows) in docs.items() for r in rows], "edges": edges,
               "all_edges_ok": all(e["ok"] for e in edges), "dangling_edges": [e for e in edges if not e["ok"]], "detail_sheets_never_called_out": orphans},
              open(os.path.join(out, "cross_reference_graph.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # source manifest / hashes
    ident = modelsrc.identity(run)
    srcs = {}
    for g in ("tools/t14i/*.py", "tools/t14g/*.py", "tools/t14e_*.py", "tools/t14d_sheet.py", "src/layouts_v3.py", "src/architectural_plan_renderer.py", "tests/test_t14i_qa.py", "tests/test_t14g_qa.py"):
        for f in sorted(glob.glob(os.path.join(ROOT, g))):
            srcs[os.path.relpath(f, ROOT).replace(os.sep, "/")] = common.sha_file(f)
    import cairosvg
    outs = {}
    for f in sorted(glob.glob(os.path.join(out, "*.pdf"))) + sorted(glob.glob(os.path.join(out, "plans_1to200", "*.pdf"))):
        outs[os.path.relpath(f, out).replace(os.sep, "/")] = {"sha256": common.sha_file(f), "bytes": os.path.getsize(f), "pages": len(pymupdf.open(f))}
    json.dump({"git_head": sh("git", "rev-parse", "HEAD"), "git_branch": sh("git", "branch", "--show-current"), "base": a.base, "base_sha": sh("git", "rev-parse", a.base),
               "model": ident, "model_cache_files": {f: common.sha_file(os.path.join(run, "model_cache", f)) for f in ("model_world.npz", "model_objects.json")},
               "inputs": {"V3_pdf_sha256": common.sha_file(V3_PDF)}, "outputs": outs,
               "tools": {"python": platform.python_version(), "pymupdf": pymupdf.VersionBind, "cairosvg": cairosvg.__version__}, "fonts": {k: os.path.basename(fonts.resolve(k)[0]) for k in ("regular", "bold")},
               "source_sha256": srcs, "cloud": "Modal/Claude cloud NOT used: no verified balance or spend limit; everything ran locally", "svg_over_6MB_not_committed": skipped_svg},
              open(os.path.join(out, "source_manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    diff = sh("git", "diff", a.base, "--", "tools", "src", "tests")
    untracked = sh("git", "ls-files", "--others", "--exclude-standard", "--", "tools", "src", "tests").splitlines()
    for f in untracked:                                                            # new files are part of the unified diff too
        d = subprocess.run(["git", "diff", "--no-index", "--", os.devnull, f], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
        diff += "\n" + d
    open(os.path.join(out, "source_changes.diff"), "w", encoding="utf-8").write(diff)
    print("packaged", out, "| part I", len(rows1), "| part II", len(rows2), "| orphans", orphans, "| diff lines", diff.count("\n"))


if __name__ == "__main__":
    main()
