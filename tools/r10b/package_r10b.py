"""Package R10-B: independent output QA + review artifacts.

    python -I -X utf8 tools/r10b/package_r10b.py --build <dir with PDF+R10B_GEOMETRY.json> [--out review/wp0_r10_b]

Everything printed/recorded uses absolute paths (project rule 0.3).  Reference-page renders are third-party drawings and are
written to a LOCAL folder only, never into the review package.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
from collections import Counter
from io import BytesIO

import fitz
from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
K = 72 / 25.4
DPI = 300
FONT = "C:/Windows/Fonts/malgun.ttf"
LOCAL_COMPARE = r"D:\Users\admin\Desktop\2학기 논문\도면\01_과정\01_기획_구획_베이스\WP0_R10_B_대표도면\비교검수"
REF = {"arch": ("재열지원_건축 도면집 제출자료.pdf", {"A-201": 6, "A-301": 19}),
       "over": ("설계 개요.pdf", {"A-201": 6})}

TITLES = {"A-201": ("2층 전체 건축 평면도", "1:200"), "A-301": ("전체 건축 종단면도 A–A", "1:250"),
          "A-302": ("전체 건축 횡단면도 B–B", "1:250")}
# detail windows: (name, centre in paper mm) ; size 128 x 108 mm
DETAILS = {
    "A-301": [("sunken_court", (310, 350)), ("bridge_zone", (242, 266)), ("roof_garden", (194, 62))],
    "A-302": [("west_capsule", (116, 290)), ("east_capsule_roof", (228, 90)), ("east_facade", (262, 226))],
}
ROOM_DETAILS = ["2-03", "2-16", "2-20", "2-10"]       # A-201 windows are centred on these rooms


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def save_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        f.write("\n")


def image_of(page, dpi=DPI, clip=None):
    pix = page.get_pixmap(dpi=dpi, alpha=False, annots=False, clip=clip)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def small_jpeg(im, path, target=(1880, 1330), limit=950_000):
    ip = ImageOps.contain(im, target, Image.Resampling.LANCZOS)
    for q in (92, 88, 83, 77, 70, 62, 55):
        b = BytesIO()
        ip.save(b, format="JPEG", quality=q, optimize=True, subsampling=0)
        if len(b.getvalue()) < limit:
            with open(path, "wb") as f:
                f.write(b.getvalue())
            return dict(width=ip.width, height=ip.height, bytes=len(b.getvalue()), quality=q)
    raise ValueError("JPEG over budget " + path)


def window(page, cx, cy, w=128, h=108):
    x0 = min(max(cx - w / 2, 15), 531 - w)
    y0 = min(max(cy - h / 2, 14), 406 - h)
    return fitz.Rect(x0 * K, y0 * K, (x0 + w) * K, (y0 + h) * K), (round(x0, 1), round(y0, 1), round(x0 + w, 1), round(y0 + h, 1))


def pen_stats(page):
    return Counter(round(q["width"] / K, 3) for q in page.get_drawings() if q.get("width") and q["width"] > 0)


def font_report(doc, page_no):
    out = []
    for f in doc[page_no].get_fonts(full=True):
        out.append(dict(name=f[3], type=f[2], embedded=bool(f[0])))
    return out


def scale_bar_checks(doc, rec, ids):
    res = []
    for row in rec["graphical_scales"]:
        sid = row["panel"][:5]
        page = doc[ids.index(sid)]
        x, y, hgt = row["bar"]
        lens = []
        for d in page.get_drawings():
            a, b, c, e = [v / K for v in d["rect"]]
            if abs(b - y) < .020 and abs(e - y - hgt) < .018 and (abs(a - x) < .018 or abs(a - x - row["paper_mm"] / 2) < .018):
                lens.append((a, c))
        if len(lens) != 2:
            res.append(dict(**row, status="FAIL", detail=f"bars found {len(lens)}"))
            continue
        measured = max(c for a, c in lens) - min(a for a, c in lens)
        ok = abs(measured - row["metres"] * 1000 / row["scale"]) < .025
        res.append(dict(**row, vector_measured_mm=round(measured, 5), status="PASS" if ok else "FAIL"))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True)
    ap.add_argument("--out", default=os.path.join(ROOT, "review", "wp0_r10_b"))
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    pdf_src = os.path.join(a.build, "WP0_R10B_Representative_A2.pdf")
    rec = json.load(open(os.path.join(a.build, "R10B_GEOMETRY.json"), encoding="utf-8"))
    ids = rec["page_order"]
    assert sha(pdf_src) == rec["pdf_sha256"], "PDF changed after geometry record"
    for sub in ("pdf", "svg", "previews", "high_resolution", "details", "tiles", "validation", "comparison"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)
    os.makedirs(LOCAL_COMPARE, exist_ok=True)
    shutil.copyfile(pdf_src, os.path.join(out, "pdf", "WP0_R10B_Representative_A2.pdf"))
    print("package dir :", out)

    doc = fitz.open(pdf_src)
    assert len(doc) == len(ids)
    bars = scale_bar_checks(doc, rec, ids)
    dims_ok = all(abs(d["paper_mm"] - 1000 * d["metres"] / d["scale"]) < 1e-6 for d in rec["calculated_dimensions"])
    pages, qa_pages = [], []
    r10a_dir = os.path.join(ROOT, "review", "wp0_r10_a")
    for n, sid in enumerate(ids):
        page = doc[n]
        text = page.get_text()
        qa = dict(sheet=sid,
                  page_mm=[round(page.rect.width / K, 3), round(page.rect.height / K, 3)],
                  page_size_ok=abs(page.rect.width / K - 594) < .003 and abs(page.rect.height / K - 420) < .003,
                  raster_images=len(page.get_image_info()), vector_paths=len(page.get_drawings()),
                  korean_glyphs=bool(re.search("[가-힣]", text)), replacement_char="\ufffd" in text,
                  sheet_id_in_text=sid in text, stale_r10a_text=("R10-A" in text), fonts=font_report(doc, n),
                  text_collisions=len(rec["sheets"][sid].get("text_collisions", [])))
        qa["status"] = "PASS" if (qa["page_size_ok"] and qa["raster_images"] == 0 and qa["korean_glyphs"] and not qa["replacement_char"]
                                  and qa["sheet_id_in_text"] and not qa["stale_r10a_text"] and qa["text_collisions"] == 0) else "FAIL"
        one = os.path.join(out, "pdf", f"{sid}.pdf")
        with fitz.open() as only:
            only.insert_pdf(doc, from_page=n, to_page=n, annots=False, links=False)
            only.save(one, garbage=4, deflate=True)
        with fitz.open(one) as only:
            assert only[0].get_text() == text
        svg = page.get_svg_image(text_as_path=True)
        assert "<image" not in svg
        with open(os.path.join(out, "svg", f"{sid}.svg"), "w", encoding="utf-8", newline="\n") as f:
            f.write(svg)
        im = image_of(page)
        im.save(os.path.join(out, "high_resolution", f"{sid}.png"), dpi=(DPI, DPI))
        prev = small_jpeg(im, os.path.join(out, "previews", f"{sid}.jpg"))
        # detail windows
        if sid == "A-201":
            centres = {r["id"]: r["centre_paper_mm"] for r in rec["sheets"]["A-201"]["rooms"]}
            wins = [(f"room_{rid}", tuple(centres[rid])) for rid in ROOM_DETAILS]
        else:
            wins = DETAILS[sid]
        details = []
        for name, (cx, cy) in wins:
            clip, mm = window(page, cx, cy)
            dim_ = image_of(page, DPI, clip)
            dp = os.path.join(out, "details", f"{sid}_{name}.png")
            dim_.save(dp, dpi=(DPI, DPI))
            jd = small_jpeg(dim_, os.path.join(out, "details", f"{sid}_{name}.jpg"), (1530, 1310))
            details.append(dict(name=name, window_mm=mm, png=f"details/{sid}_{name}.png", jpeg=f"details/{sid}_{name}.jpg", jpeg_data=jd))
        # tiles 4 x 3
        td = os.path.join(out, "tiles", sid)
        os.makedirs(td, exist_ok=True)
        tiles = []
        w, h = im.size
        for r in range(3):
            for c in range(4):
                b = (max(0, w * c // 4 - 40), max(0, h * r // 3 - 40), min(w, w * (c + 1) // 4 + 40), min(h, h * (r + 1) // 3 + 40))
                tname = f"r{r + 1:02d}-c{c + 1:02d}"
                im.crop(b).save(os.path.join(td, tname + ".png"), dpi=(DPI, DPI))
                sj = small_jpeg(im.crop(b), os.path.join(td, tname + ".jpg"), (1800, 1700))
                tiles.append(dict(png=f"tiles/{sid}/{tname}.png", jpeg=f"tiles/{sid}/{tname}.jpg", bounds_px=b, jpeg_data=sj))
        pages.append(dict(number=n + 1, sheet=sid, title=TITLES[sid][0], scale=TITLES[sid][1], pdf=f"pdf/{sid}.pdf", svg=f"svg/{sid}.svg",
                          preview=f"previews/{sid}.jpg", preview_data=prev, high_resolution=f"high_resolution/{sid}.png",
                          high_resolution_px=im.size, details=details, tiles=tiles, pen_distribution_mm=dict(pen_stats(page))))
        qa_pages.append(qa)
        print(sid, qa["status"], "paths", qa["vector_paths"], flush=True)

    # --- R10-A vs R10-B (our own sheets: stored in the package) ------------------------------------------------------------
    cmp_rows = []
    f = ImageFont.truetype(FONT, 20)
    for n, sid in enumerate(ids):
        old_pdf = os.path.join(r10a_dir, "pdf", f"{sid}.pdf")
        row = dict(sheet=sid, r10b_vector_paths=len(doc[n].get_drawings()), r10b_text_chars=len(doc[n].get_text()))
        if os.path.exists(old_pdf):
            with fitz.open(old_pdf) as od:
                row.update(r10a_vector_paths=len(od[0].get_drawings()), r10a_text_chars=len(od[0].get_text()))
                a_img = image_of(od[0], 80)
            b_img = image_of(doc[n], 80)
            canvas = Image.new("RGB", (a_img.width * 2 + 50, a_img.height + 56), "#e5e9e8")
            dr = ImageDraw.Draw(canvas)
            dr.text((14, 14), f"R10-A {sid} (벡터 경로 {row['r10a_vector_paths']:,})", font=f, fill="#202526")
            dr.text((a_img.width + 36, 14), f"R10-B {sid} (벡터 경로 {row['r10b_vector_paths']:,})", font=f, fill="#202526")
            canvas.paste(a_img, (12, 46))
            canvas.paste(b_img, (a_img.width + 36, 46))
            small_jpeg(canvas, os.path.join(out, "comparison", f"R10A_vs_R10B_{sid}.jpg"), (2400, 1000))
        else:
            row["note"] = "R10-A sheet not present (new sheet in R10-B)"
        cmp_rows.append(row)
    save_json(os.path.join(out, "validation", "R10A_VS_R10B.json"), cmp_rows)

    # --- reference pages: LOCAL ONLY ---------------------------------------------------------------------------------------------
    ref_rows = []
    for tag, (name, pm) in REF.items():
        src = os.path.join("D:/Temp", name)
        with fitz.open(src) as rd:
            for sid, pn in pm.items():
                if sid not in ids:
                    continue
                r = rd[pn - 1]
                widths = Counter(round(d["width"] / K, 3) for d in r.get_drawings() if d.get("width") and d["width"] > 0)
                target = doc[ids.index(sid)]
                aimg, bimg = image_of(r, 80), image_of(target, 80)
                canvas = Image.new("RGB", (aimg.width + bimg.width + 50, max(aimg.height, bimg.height) + 56), "#e5e9e8")
                dr = ImageDraw.Draw(canvas)
                dr.text((14, 14), f"참고 {name} p{pn}", font=f, fill="#202526")
                dr.text((aimg.width + 36, 14), f"R10-B {sid}", font=f, fill="#202526")
                canvas.paste(aimg, (12, 46))
                canvas.paste(bimg, (aimg.width + 36, 46))
                lp = os.path.join(LOCAL_COMPARE, f"{tag}_{pn:02}_vs_R10B_{sid}.jpg")
                canvas.save(lp, quality=93)
                ref_rows.append(dict(sheet=sid, reference_filename=name, reference_page=pn, reference_sha256=sha(src),
                                     reference_paper_mm=[round(r.rect.width / K, 3), round(r.rect.height / K, 3)],
                                     reference_vector_paths=len(r.get_drawings()), r10b_vector_paths=len(target.get_drawings()),
                                     reference_pen_mm_top=widths.most_common(8), local_comparison_image=lp))
    save_json(os.path.join(out, "validation", "REFERENCE_PAGES.json"), ref_rows)

    qa_all = dict(page_count=len(ids), raster_dpi=DPI, pages=pages, qa=qa_pages, scale_bars=bars,
                  scale_bars_all_pass=all(b["status"] == "PASS" for b in bars), dimension_samples=len(rec["calculated_dimensions"]),
                  dimension_paper_mm_consistent=dims_ok, previews_limit_bytes=1_000_000,
                  previews_all_under_limit=all(p["preview_data"]["bytes"] < 1_000_000 for p in pages),
                  reference_pages=ref_rows, r10a_vs_r10b=cmp_rows)
    save_json(os.path.join(out, "validation", "R10B_OUTPUT_QA.json"), qa_all)
    shutil.copyfile(os.path.join(a.build, "R10B_GEOMETRY.json"), os.path.join(out, "validation", "R10B_GEOMETRY.json"))

    # --- manifest ----------------------------------------------------------------------------------------------------------------------
    files = []
    for dp, _, fs in os.walk(out):
        for fn in sorted(fs):
            if fn == "manifest.json":
                continue
            full = os.path.join(dp, fn)
            files.append(dict(path=os.path.relpath(full, out).replace("\\", "/"), bytes=os.path.getsize(full), sha256=sha(full)))
    files.sort(key=lambda r: r["path"])
    pdfm = "pdf/WP0_R10B_Representative_A2.pdf"
    save_json(os.path.join(out, "manifest.json"), dict(base="review/wp0_r10_b", algorithm="SHA-256", artifact_count=len(files),
                                                       pdf=dict(path=pdfm, sha256=sha(os.path.join(out, pdfm))), files=files))
    print("manifest    :", os.path.join(out, "manifest.json"), "files:", len(files))
    print("OVERALL QA  :", "PASS" if all(q["status"] == "PASS" for q in qa_pages) and qa_all["scale_bars_all_pass"] and dims_ok
          and qa_all["previews_all_under_limit"] else "FAIL")


if __name__ == "__main__":
    main()
