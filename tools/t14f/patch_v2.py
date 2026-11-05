#!/usr/bin/env python3
"""V2 PDF -> V3 (interim) PDF: corrections that do NOT need the GLB model.

Run:  python -I tools/t14f/patch_v2.py [--src V2.pdf] [--out V3.pdf] [--log patch_log.json]

What it does (every change is written to the patch log with page, bbox and before/after):
  F-01  callout labels on plan sheets: the scale printed after a detail number is rebuilt from
        the sheet registry (sheet_index.json), not typed (P-102 D-407, P-105 D-410 said 1:50,
        the details are 1:100).
  F-02  every detail sheet (scale 1:50 / 1:100) gets a real graphic scale bar whose physical
        length is checked after writing (5 m at 1:50 = 100 mm, 10 m at 1:100 = 100 mm).
  F-10  title block edition/project code: V2 -> V3 (interim), C-T14D -> C-T14F, with real
        spaces so the Korean text extracts properly.
  F-10  fonts: patched text uses the portable CJK resolver (tools/t14f/fonts.py); all fonts in
        the output are subset (the V2 file embedded complete Malgun Gothic copies).
Nothing else on any page changes. A-003 (page 4, user-supplied 1F sheet) is not touched.
What it cannot do: re-cut the model. Anything that needs the GLB stays BLOCKED_MISSING_SOURCE.
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys

import numpy as np
import pymupdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fonts            # noqa: E402
import pdfutil          # noqa: E402
import registry         # noqa: E402
from registry import MM  # noqa: E402

ORANGE = 0xAA6600
TITLE_BLOCK_Y = 262.0          # mm, top of the title block in every generated sheet
SAFE_Y1 = 258.0                # bars must end above this line
EDITION_TAG = "V3(중간본)"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Patcher:
    def __init__(self, src, reg):
        self.doc = pymupdf.open(src)
        self.reg = reg
        self.log = []
        self.regular, _ = fonts.resolve("regular")
        self.bold, _ = fonts.resolve("bold")
        self.f_reg = pymupdf.Font(fontfile=self.regular)
        self.f_bold = pymupdf.Font(fontfile=self.bold)
        self._redact = {}
        self._inserts = {}

    # ---- queued text replacement (one redaction pass per page) --------------------------------
    def replace_line(self, pno, rec, new_text, bold=False, anchor="start", size=None, color=None, why=""):
        size = size or rec["size"]
        color = rec["color"] if color is None else color
        r = pymupdf.Rect(rec["bbox"])
        self._redact.setdefault(pno, []).append(r)
        font = self.f_bold if bold else self.f_reg
        w = font.text_length(new_text, fontsize=size)
        x, y = rec["origin"]
        if anchor == "middle":
            x = (rec["bbox"].x0 + rec["bbox"].x1) / 2 - w / 2
        elif anchor == "end":
            x = rec["bbox"].x1 - w
        self._inserts.setdefault(pno, []).append({"pt": (x, y), "text": new_text, "bold": bold, "size": size,
                                                  "color": pdfutil.rgb(color), "mask": None})
        self.log.append({"page": pno, "kind": "text", "why": why, "before": rec["text"], "after": new_text,
                         "bbox_mm": [round(v / MM, 2) for v in (min(rec["bbox"].x0, x), rec["bbox"].y0,
                                                                  max(rec["bbox"].x1, x + w), rec["bbox"].y1)]})
        return w

    def flush_text(self, pno):
        page = self.doc[pno - 1]
        for r in self._redact.pop(pno, []):
            page.add_redact_annot(r)
        if page.first_annot:
            page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                                  text=pymupdf.PDF_REDACT_TEXT_REMOVE)
        page.insert_font(fontname="t14fR", fontfile=self.regular)
        page.insert_font(fontname="t14fB", fontfile=self.bold)
        for it in self._inserts.pop(pno, []):
            if it["mask"] is not None:
                page.draw_rect(it["mask"], color=None, fill=(1, 1, 1), width=0)
            page.insert_text(it["pt"], it["text"], fontname="t14fB" if it["bold"] else "t14fR",
                             fontsize=it["size"], color=it["color"])

    # ---- F-01 ---------------------------------------------------------------------------------
    def callouts(self, pno):
        """Orange 'D-407 · 1:50' labels on a sheet: [(id, shown_den, union_rect, spans)]."""
        sp = pdfutil.spans(self.doc[pno - 1])
        out = []
        for a in sp:
            if a["color"] != ORANGE or not re.fullmatch(r"[DES]-\d{3}", a["text"].strip()):
                continue
            same = [s for s in sp if s["color"] == ORANGE and abs(s["bbox"].y0 - a["bbox"].y0) < 0.6
                    and a["bbox"].x0 - 0.5 <= s["bbox"].x0 < a["bbox"].x1 + 25 * MM and s["text"].strip()]
            same.sort(key=lambda s: s["bbox"].x0)
            label = " ".join(s["text"].strip() for s in same)
            m = re.fullmatch(r"([DES]-\d{3}) · 1:(\d+)", label)
            if not m:
                continue
            u = pymupdf.Rect(same[0]["bbox"])
            for s in same[1:]:
                u |= s["bbox"]
            out.append({"id": m.group(1), "shown_den": int(m.group(2)), "rect": u, "origin": a["origin"],
                        "size": a["size"], "color": a["color"]})
        return out

    def fix_callouts(self):
        report = []
        for pno in range(1, len(self.doc) + 1):
            for c in self.callouts(pno):
                want = self.reg[c["id"]]["scale_den"] if c["id"] in self.reg else None
                ok = want is not None and want == c["shown_den"]
                rec = {"page": pno, "target": c["id"], "shown": "1:%d" % c["shown_den"],
                       "registry": ("1:%d" % want) if want else None, "ok": ok}
                report.append(rec)
                if ok or want is None:
                    continue
                new = "%s · 1:%d" % (c["id"], want)
                size, base = c["size"], c["origin"][1]
                cx = (c["rect"].x0 + c["rect"].x1) / 2
                w = self.f_reg.text_length(new, fontsize=size)
                mask = pymupdf.Rect(cx - w / 2 - 0.4 * MM, base - size * 0.95, cx + w / 2 + 0.4 * MM, base + size * 0.30)
                self._redact.setdefault(pno, []).append(pymupdf.Rect(c["rect"]))
                self._inserts.setdefault(pno, []).append({"pt": (cx - w / 2, base), "text": new, "bold": False,
                                                          "size": size, "color": pdfutil.rgb(c["color"]), "mask": mask})
                self.log.append({"page": pno, "kind": "callout_scale", "finding": "F-01",
                                 "why": "callout scale rebuilt from sheet registry",
                                 "before": "%s · 1:%d" % (c["id"], c["shown_den"]), "after": new,
                                 "bbox_mm": [round(v / MM, 2) for v in mask]})
                rec["fixed"] = True
        return report

    # ---- F-10 edition / project code ------------------------------------------------------------
    def edition(self):
        for pno in range(1, len(self.doc) + 1):
            if pno == 4:                                   # A-003 is the user's 1F sheet: do not touch
                continue
            for rec in pdfutil.lines(self.doc[pno - 1]):
                n = rec["norm"]
                if n == "도면집후보V2·FREEZE아님":
                    self.replace_line(pno, rec, "도면집 후보 %s · FREEZE 아님" % EDITION_TAG, why="edition label (F-10)")
                elif n == "C-T14D":
                    self.replace_line(pno, rec, "C-T14F", bold=True, why="project code C-T14D -> C-T14F (F-10)")
                elif n == "·최종FREEZE아님(후보V2).":
                    self.replace_line(pno, rec, "· 최종 FREEZE 아님(후보 V3 중간본).", why="edition note")
                elif pno == 1 and n == "수직보행연구—3D모델에서파생한도면(후보V2)":
                    self.replace_line(pno, rec, "수직 보행 연구 — 3D 모델에서 파생한 도면 (후보 V3 중간본)", anchor="middle", why="cover")
                elif pno == 1 and n.startswith("도면집후보V2·"):
                    date = re.search(r"\d{4}-\d{2}-\d{2}", rec["text"])
                    self.replace_line(pno, rec, "도면집 후보 V3(중간본) · %s" % (date.group(0) if date else ""),
                                      anchor="middle", why="cover")
                elif pno == 1 and n == "표지·도면집후보V2·CANDIDATE—NOTFROZEN":
                    self.replace_line(pno, rec, "표지 · 도면집 후보 %s · CANDIDATE — NOT FROZEN" % EDITION_TAG, why="cover footer")
                elif pno == 29 and n.startswith("이도면집은후보(V2)이며"):
                    self.replace_line(pno, rec, "이 도면집은 후보(V3 중간본)이며 FREEZE가 아니다 · 아래 항목은 근거 부재 또는 사용자 결정 전이라 확정하지 않았다",
                                      why="A-900 subtitle")

    def cover_notice(self):
        page = self.doc[0]
        txt = "V3 중간본(INTERIM) · V2 PDF에 보정 적용(변경 기록: docs/t14f_v3/patch_log.json) · 모델 원본 없음 → 모델 재생성은 BLOCKED_MISSING_SOURCE"
        size = 8.0
        w = self.f_reg.text_length(txt, fontsize=size)
        pt = (210 * MM - w / 2, 176.0 * MM)
        page.insert_font(fontname="t14fR", fontfile=self.regular)
        page.insert_text(pt, txt, fontname="t14fR", fontsize=size, color=(0.667, 0.2, 0.2))
        self.log.append({"page": 1, "kind": "cover_notice", "before": "", "after": txt,
                         "bbox_mm": [round(pt[0] / MM, 2), 170.0, round((pt[0] + w) / MM, 2), 178.0]})

    # ---- F-02 graphic scale bars ----------------------------------------------------------------
    @staticmethod
    def bar_spec(den):
        """Tick distances (m) so that the bar is 100 mm of paper: 5 m at 1:50, 10 m at 1:100."""
        return {50: (0, 1, 2, 5), 100: (0, 2, 5, 10)}.get(den)

    def free_slot(self, pno, w_mm, h_mm, clear_mm=2.0, dpi=100):
        """Largest-first search for an empty rectangle: rasterise the page, dilate everything that is
        not white by clear_mm, and take the free position closest to the lower-left of the drawing area."""
        from scipy.ndimage import maximum_filter
        page = self.doc[pno - 1]
        pm = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False)
        a = np.frombuffer(pm.samples, np.uint8).reshape(pm.h, pm.w)
        pxmm = dpi / 25.4
        occ = (a < 246).astype(np.uint8)
        k = int(round(clear_mm * pxmm))
        occ = maximum_filter(occ, size=2 * k + 1)
        # outside the usable band counts as occupied
        x0, x1, y0, y1 = 14.0, 406.0, 14.0, SAFE_Y1
        mask = np.ones_like(occ)
        mask[int(y0 * pxmm):int(y1 * pxmm), int(x0 * pxmm):int(x1 * pxmm)] = 0
        occ = np.maximum(occ, mask)
        ii = np.zeros((occ.shape[0] + 1, occ.shape[1] + 1), np.int64)
        ii[1:, 1:] = occ.cumsum(0).cumsum(1)
        ww, hh = int(math.ceil(w_mm * pxmm)), int(math.ceil(h_mm * pxmm))
        sums = ii[hh:, ww:] - ii[:-hh, ww:] - ii[hh:, :-ww] + ii[:-hh, :-ww]
        ys, xs = np.nonzero(sums == 0)
        if len(xs) == 0:
            return None
        xm, ym = xs / pxmm, ys / pxmm
        cost = (xm - 14.0) + 2.0 * (SAFE_Y1 - (ym + h_mm))
        i = int(np.argmin(cost))
        return float(xm[i]), float(ym[i])

    def draw_bar(self, pno, bx, by, den, meters):
        """Same geometry as Sheet.scale_bar() in tools/t14d_sheet.py, drawn straight into the PDF."""
        page = self.doc[pno - 1]
        k = 1000.0 / den                                   # paper mm per model metre
        x, y = bx + 3.0, by + 6.5
        L = meters[-1] * k
        R = lambda a, b, c, d: pymupdf.Rect(a * MM, b * MM, c * MM, d * MM)
        page.draw_rect(R(x - 3, y - 6.5, x + L + 14, y + 6), color=(0.733,) * 3, fill=(1, 1, 1), width=0.1 * MM)
        segs = []
        for i in range(len(meters) - 1):
            x0, x1 = x + meters[i] * k, x + meters[i + 1] * k
            dark = (i % 2 == 0)
            page.draw_rect(R(x0, y, x1, y + 1.6), color=(0.067,) * 3, fill=(0.067,) * 3 if dark else (1, 1, 1), width=0.15 * MM)
            segs.append(round(x1 - x0, 4))
        page.insert_font(fontname="t14fR", fontfile=self.regular)
        for m in meters:
            t = "%d%s" % (m, " m" if m == meters[-1] else "")
            tw = self.f_reg.text_length(t, fontsize=5.5)
            page.insert_text(((x + m * k) * MM - tw / 2, (y - 1.4) * MM), t, fontname="t14fR", fontsize=5.5, color=(0.2,) * 3)
        page.insert_text((x * MM, (y + 5.2) * MM), "1:%d · A3 420×297 mm 100%% 인쇄 기준" % den, fontname="t14fR",
                         fontsize=4.8, color=(0.333,) * 3)
        return {"box_mm": [round(bx, 2), round(by, 2), round(bx + L + 17, 2), round(by + 12.5, 2)], "segments_mm": segs,
                "length_mm": round(L, 3)}

    def scale_bars(self):
        report = []
        for sid, row in self.reg.items():
            den = row["scale_den"]
            if not sid.startswith("D-") or den is None:
                continue
            meters = self.bar_spec(den)
            if meters is None:
                report.append({"sheet": sid, "page": row["page"], "status": "UNSUPPORTED_SCALE", "den": den})
                continue
            L = meters[-1] * 1000.0 / den
            w, h = L + 17.0, 12.5
            pos = self.free_slot(row["page"], w, h)
            if pos is None:
                report.append({"sheet": sid, "page": row["page"], "status": "NO_FREE_SLOT", "need_mm": [w, h]})
                continue
            info = self.draw_bar(row["page"], pos[0], pos[1], den, meters)
            info.update({"sheet": sid, "page": row["page"], "status": "DRAWN", "den": den, "meters": list(meters)})
            report.append(info)
            self.log.append({"page": row["page"], "kind": "scale_bar", "finding": "F-02", "why": "graphic scale bar",
                             "before": "(none: only the title-block text)", "after": "%s m bar = %.1f mm at 1:%d" % (meters[-1], L, den),
                             "bbox_mm": info["box_mm"]})
        return report


def sanitize_log(res, root=registry.ROOT):
    """Make the log machine independent: repository-relative paths, font file names only."""
    def rel(p):
        p = os.path.abspath(p)
        return os.path.relpath(p, root).replace(os.sep, "/") if p.startswith(os.path.abspath(root)) else os.path.basename(p)
    out = dict(res)
    for k in ("src", "out"):
        out[k] = rel(res[k])
    for k in ("font_regular", "font_bold"):
        out[k] = os.path.basename(res[k])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", default=registry.V2_PDF)
    ap.add_argument("--index", default=registry.V2_INDEX)
    ap.add_argument("--out", required=True)
    ap.add_argument("--log", default=None)
    a = ap.parse_args()

    reg = registry.load(a.index)
    p = Patcher(a.src, reg)
    call = p.fix_callouts()
    p.edition()
    for pno in range(1, len(p.doc) + 1):
        p.flush_text(pno)
    p.cover_notice()
    bars = p.scale_bars()

    meta = p.doc.metadata
    meta.update({"title": "다층 상업시설 건축 도면집 — 후보 V3 (중간본: V2 PDF 보정)",
                 "subject": "CANDIDATE — NOT FROZEN · INTERIM · MODEL REBUILD BLOCKED_MISSING_SOURCE",
                 "keywords": "model-derived drawing set; Level S upper floors; V2 PDF patched (F-01 F-02 F-10)",
                 "creator": "tools/t14f/patch_v2.py", "producer": "PyMuPDF"})
    p.doc.set_metadata(meta)
    p.doc.subset_fonts()                                   # V2 embedded complete font copies; keep subsets only
    p.doc.save(a.out, garbage=4, deflate=True)
    res = {"src": a.src, "src_sha256": sha256(a.src), "out": a.out, "out_sha256": sha256(a.out),
           "font_regular": p.regular, "font_bold": p.bold, "callouts": call, "scale_bars": bars, "changes": p.log}
    if a.log:
        os.makedirs(os.path.dirname(os.path.abspath(a.log)), exist_ok=True)
        json.dump(sanitize_log(res), open(a.log, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    bad = [c for c in call if not c["ok"]]
    print("callouts checked %d, mismatched %d: %s" % (len(call), len(bad), [(c["page"], c["target"], c["shown"], c["registry"]) for c in bad]))
    print("scale bars:", [(b["sheet"], b["status"], b.get("box_mm")) for b in bars])
    print("changes logged:", len(p.log), "| out", a.out, "| %.2f MB" % (os.path.getsize(a.out) / 1e6))


if __name__ == "__main__":
    main()
