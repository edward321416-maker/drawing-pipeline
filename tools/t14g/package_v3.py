"""Assemble docs/t14g_v3 from a finished run: PDF, per-sheet PDF/SVG/PNG, contact sheet, QA reports, cross-reference graph,
source manifest, audit CSVs, before/after panels, unified diff.

    python -I tools/t14g/package_v3.py --run <run> --out docs/t14g_v3 --base origin/claude/t14f-candidate-v3-audit
"""
import argparse
import csv
import glob
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import pymupdf  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from t14g import qa_pdf, modelsrc  # noqa: E402
from t14f import fonts  # noqa: E402

MM = 72.0 / 25.4
V2_PDF = os.path.join(ROOT, "docs", "t14e_v2", "drawing_set_candidate_v2.pdf")
V3I_PDF = os.path.join(ROOT, "docs", "t14f_v3", "Candidate_V3_interim.pdf")


def sha(p):
    return modelsrc.sha256_file(p)


def sh(*a, cwd=ROOT):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def font(sz, bold=False):
    return ImageFont.truetype(fonts.resolve("bold" if bold else "regular")[0], sz)


def page_png(pdf, pno, dpi, box_mm=None):
    pg = pymupdf.open(pdf)[pno - 1]
    clip = pymupdf.Rect(*[v * MM for v in box_mm]) if box_mm else None
    pm = pg.get_pixmap(dpi=dpi, clip=clip)
    return Image.frombytes("RGB", (pm.width, pm.height), pm.samples)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--junit", default=None)
    a = ap.parse_args()
    run, out = os.path.abspath(a.run), os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    book = os.path.join(run, "book", "drawing_set_candidate_v3.pdf")
    pdf = os.path.join(out, "Candidate_V3_drawing_set.pdf")
    shutil.copy(book, pdf)
    rows = json.load(open(os.path.join(run, "00_index", "sheet_index.json"), encoding="utf-8"))["sheets"]
    shutil.copy(os.path.join(run, "00_index", "sheet_index.json"), os.path.join(out, "sheet_index.json"))
    shutil.copy(os.path.join(run, "00_index", "sheet_index.csv"), os.path.join(out, "sheet_index.csv"))
    reg = json.load(open(os.path.join(run, "book", "book_registry.json"), encoding="utf-8"))

    # ── per-sheet PDF / SVG / PNG ─────────────────────────────────────────────────────────────
    skipped_svg = []
    for p in reg["sheets"]:
        d = os.path.join(out, "sheets", p["folder"])
        os.makedirs(d, exist_ok=True)
        src = p["source_pdf"]
        shutil.copy(src, os.path.join(d, p["sheet"] + ".pdf"))
        svg = os.path.splitext(src)[0] + ".svg"
        if os.path.exists(svg):
            if os.path.getsize(svg) <= 6 * 1024 * 1024:
                shutil.copy(svg, os.path.join(d, p["sheet"] + ".svg"))
            else:
                skipped_svg.append((p["sheet"], os.path.getsize(svg)))
        page_png(pdf, p["page"], 150).save(os.path.join(d, p["sheet"] + ".png"), optimize=True)

    # ── contact sheet (numbered) ──────────────────────────────────────────────────────────────
    thumbs = [(p, page_png(pdf, p["page"], 55)) for p in rows]
    tw, th = thumbs[0][1].size
    cols = 6
    W, H = cols * (tw + 14) + 14, ((len(thumbs) + cols - 1) // cols) * (th + 40) + 14
    cs = Image.new("RGB", (W, H), "#d8d8d8")
    dr = ImageDraw.Draw(cs)
    for i, (p, im) in enumerate(thumbs):
        x, y = 14 + (i % cols) * (tw + 14), 14 + (i // cols) * (th + 40)
        cs.paste(im, (x, y + 26))
        dr.text((x, y + 2), "%02d  %s  %s" % (p["page"], p["sheet"], p["title"][:26]), font=font(15, True), fill="#111")
    cs.save(os.path.join(out, "Candidate_V3_contact_sheet.png"), optimize=True)

    # ── QA reports ────────────────────────────────────────────────────────────────────────────
    for f in ("dimension_truth_report.json", "furniture_qa.json", "qa_mutation_report.json", "tests_report_historical_63.json"):
        s = os.path.join(run, f)
        if os.path.exists(s):
            shutil.copy(s, os.path.join(out, f))
    shutil.copy(os.path.join(run, "appendix", "typical_floor_coverage.json"), os.path.join(out, "typical_floor_coverage.json"))
    hist = json.load(open(os.path.join(run, "tests_report.json"), encoding="utf-8"))
    shutil.copy(os.path.join(run, "tests_report.json"), os.path.join(out, "tests_report_historical_63.json"))
    bars = qa_pdf.scale_bar_report(pymupdf.open(pdf), rows)
    json.dump(bars, open(os.path.join(out, "scale_bar_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    checks = qa_pdf.run_all(pdf, rows)
    junit = {}
    if a.junit and os.path.exists(a.junit):
        r = ET.parse(a.junit).getroot()
        ts = r if r.tag == "testsuite" else r.find("testsuite")
        junit = {"tests": int(ts.get("tests")), "failures": int(ts.get("failures")), "errors": int(ts.get("errors")), "skipped": int(ts.get("skipped")), "time_s": float(ts.get("time"))}
    furn = json.load(open(os.path.join(run, "furniture_qa.json"), encoding="utf-8"))
    mut = json.load(open(os.path.join(run, "qa_mutation_report.json"), encoding="utf-8"))
    truth = json.load(open(os.path.join(run, "dimension_truth_report.json"), encoding="utf-8"))
    json.dump({"pytest_t14g_and_repo": junit, "historical_book_qa": {"passed": hist["passed"], "total": hist["total"], "failed": hist["failed"]},
               "independent_pdf_checks": {k: len(v) for k, v in checks.items()}, "scale_bars": {"checked": len(bars), "ok": sum(1 for b in bars if b["status"] == "OK")},
               "dimension_truth": {"checked": truth["checked"], "passed": truth["passed"]},
               "furniture_geometry": {x["floor"]: x["passes"] for x in furn["floors"]} | {"distinct_programs": furn["distinct"]["passes"]},
               "mutations": {"detected": mut["detected"], "total": mut["total"]}}, open(os.path.join(out, "tests_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ── cross reference graph ─────────────────────────────────────────────────────────────────
    scale = {r["sheet"]: r["scale"] for r in rows}
    doc = pymupdf.open(pdf)
    edges = []
    for r in rows:
        if r["sheet"] == "A-003":
            continue
        for ln in qa_pdf._lines(doc[r["page"] - 1]):
            for sid, den in qa_pdf.CALL_RE.findall(ln["text"]):
                edges.append({"from": r["sheet"], "to": sid, "kind": "detail_callout", "printed_scale": "1:" + den, "target_scale": scale.get(sid), "ok": scale.get(sid) == "1:" + den})
            for sid in set(re.findall(r"[ES]-\d{3}", ln["text"])):
                if sid != r["sheet"] and not qa_pdf.CALL_RE.search(ln["text"]):
                    edges.append({"from": r["sheet"], "to": sid, "kind": "section_or_elevation_mark", "ok": sid in scale})
    uniq = {(e["from"], e["to"], e["kind"]): e for e in edges}
    edges = list(uniq.values())
    orphans = sorted(s for s in scale if s.startswith("D-") and not any(e["to"] == s for e in edges))
    json.dump({"nodes": [{"sheet": r["sheet"], "page": r["page"], "scale": r["scale"]} for r in rows], "edges": edges, "all_edges_ok": all(e["ok"] for e in edges),
               "detail_sheets_never_called_out": orphans, "note": "orphan detail sheets are listed, not hidden"}, open(os.path.join(out, "cross_reference_graph.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ── source manifest ───────────────────────────────────────────────────────────────────────
    ident = modelsrc.identity(run)
    srcs = {}
    for g in ("tools/t14g/*.py", "tools/t14e_*.py", "tools/t14d_sheet.py", "src/layouts_v3.py", "src/architectural_plan_renderer.py", "tests/test_t14g_qa.py"):
        for f in sorted(glob.glob(os.path.join(ROOT, g))):
            srcs[os.path.relpath(f, ROOT).replace(os.sep, "/")] = sha(f)
    import cairosvg
    json.dump({"git_head": sh("git", "rev-parse", "HEAD"), "git_branch": sh("git", "branch", "--show-current"), "base": a.base, "base_sha": sh("git", "rev-parse", a.base),
               "model": ident, "inputs": {"V2_pdf_sha256": sha(V2_PDF), "V3_interim_pdf_sha256": sha(V3I_PDF)},
               "outputs": {"Candidate_V3_drawing_set.pdf": {"sha256": sha(pdf), "bytes": os.path.getsize(pdf), "pages": len(doc)}},
               "tools": {"python": platform.python_version(), "pymupdf": pymupdf.__doc__.split()[1] if pymupdf.__doc__ else pymupdf.VersionBind, "cairosvg": cairosvg.__version__},
               "fonts": {k: os.path.basename(fonts.resolve(k)[0]) for k in ("regular", "bold")}, "source_sha256": srcs,
               "cloud": "Modal/Claude cloud NOT used: no verified balance or spend limit; everything ran locally", "svg_over_6MB_not_committed": skipped_svg},
              open(os.path.join(out, "source_manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ── audit CSVs (baseline: independent agents' V2 / V3-interim findings) ───────────────────
    find = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "output", "audit", "findings", "pages_*.json"))):
        for p in json.load(open(f, encoding="utf-8"))["pages"]:
            find[p["page"]] = p
    with open(os.path.join(out, "qa_30page_visual_audit_V2_V3i.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["page", "sheet", "V2_verdict", "V3interim_verdict", "defects_high", "defects_medium", "defects_low", "items_ISSUE_V3i", "top_defects"])
        for pno in sorted(find):
            p = find[pno]
            ds = p["defects"]
            top = " | ".join("%s[%s] %s" % (d["id"], d["severity"], d["description"][:110].replace("\n", " ")) for d in ds if d["severity"] == "high")[:600]
            w.writerow([pno, p["sheet"], p["V2"]["verdict"], p["V3i"]["verdict"], sum(d["severity"] == "high" for d in ds), sum(d["severity"] == "medium" for d in ds),
                        sum(d["severity"] == "low" for d in ds), sum(1 for v in p["V3i"]["items"].values() if v["status"] == "ISSUE"), top])
    with open(os.path.join(out, "qa_defect_ledger_baseline.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "page", "sheet", "severity", "in_editions", "category", "fix_needs_model", "description", "evidence_crop"])
        for pno in sorted(find):
            for d in find[pno]["defects"]:
                w.writerow([d["id"], pno, find[pno]["sheet"], d["severity"], "/".join(d["in"]), d["category"], d.get("fix_needs_model"), d["description"].replace("\n", " "), d.get("evidence_crop")])

    # ── unified diff of the source changes against the base (PR #15 head) ─────────────────────
    diff = sh("git", "diff", a.base, "--", "tools", "src", "tests")
    open(os.path.join(out, "source_changes.diff"), "w", encoding="utf-8").write(diff)
    print("packaged", out, "| sheets", len(rows), "| svg skipped", skipped_svg, "| diff lines", diff.count("\n"))


if __name__ == "__main__":
    main()
