"""Independent drawing-set QA on the FINISHED PDF (no generator code is imported).

Inputs: the PDF, the sheet registry rows ([{page, sheet, scale, ...}]) and the expected north angle.
Every check returns a list of finding strings; an empty list means the check passed. `run_all` returns {check: [findings]}.

  page_size       every page is the registry paper size (A3 420x297 mm unless a sheet says otherwise)
  index           page count and the sheet id printed in each title block equal the registry
  callouts        every 'D-4xx . 1:N' span: target exists in the registry and N equals that sheet's scale
  scale_bars      a graphic bar exists on each scaled sheet and its physical length equals meters*1000/scale (vector measurement)
  text_bounds     no text outside the sheet margin, none from the drawing area running into the title block
  text_overlap    two text lines whose boxes overlap by more than 35 % of the smaller box
  fonts           every font object on every page is embedded
  duplicates      identical vector items stacked on each other
  north           every printed 'north X deg' equals the model's north angle
  stale_refs      known wrong cross references (A-002 for floor heights: the floor table is A-901)
"""
import re
from collections import Counter

import pymupdf

MM = 72.0 / 25.4
TITLE_TOP_MM = 262.0
SKIP_PAGE_SHEETS = {"A-003"}                      # user supplied sheet: judged, never modified
CALL_RE = re.compile(r"([DES]-\d{3})·1:(\d+)")
STALE_REFS = [("A-002", "층고")]


def _spans(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            for sp in ln["spans"]:
                t = sp["text"].strip()
                if t:
                    out.append({"text": t, "bbox": sp["bbox"], "size": sp["size"], "font": sp["font"], "line": ln["bbox"]})
    return out


def _lines(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            txt = "".join(sp["text"] for sp in ln["spans"])
            if txt.strip():
                out.append({"text": re.sub(r"\s+", "", txt), "bbox": ln["bbox"], "size": max(sp["size"] for sp in ln["spans"])})
    return out


def _mm(b):
    return [round(v / MM, 2) for v in b]


def check_page_size(doc, rows):
    out = []
    for i, pg in enumerate(doc):
        w, h = round(pg.rect.width / MM, 1), round(pg.rect.height / MM, 1)
        if abs(w - 420.0) > 0.6 or abs(h - 297.0) > 0.6:
            out.append("page %d is %.1f x %.1f mm, expected A3 420 x 297" % (i + 1, w, h))
    return out


def check_index(doc, rows):
    out = []
    if len(doc) != len(rows):
        out.append("PDF has %d pages but the registry lists %d sheets" % (len(doc), len(rows)))
    for r in rows:
        if r["page"] > len(doc):
            out.append("registry page %d (%s) is beyond the PDF" % (r["page"], r["sheet"]))
            continue
        pg = doc[r["page"] - 1]
        if r["sheet"] in SKIP_PAGE_SHEETS:
            txt = re.sub(r"\s+", "", pg.get_text())
            if r["sheet"] not in txt:
                out.append("page %d: sheet id %s not printed anywhere" % (r["page"], r["sheet"]))
            continue
        low = [re.sub(r"\s+", "", s["text"]) for s in _spans(pg) if s["bbox"][1] / MM > TITLE_TOP_MM or s["bbox"][1] / MM < 30 and s["size"] > 10]
        if r["sheet"] not in low and not any(r["sheet"] == t[:len(r["sheet"])] for t in low):
            out.append("page %d: title block does not print sheet id %s" % (r["page"], r["sheet"]))
    return out


def check_callouts(doc, rows):
    scale = {r["sheet"]: r["scale"] for r in rows}
    out = []
    for i, pg in enumerate(doc):
        for ln in _lines(pg):
            for sid, den in CALL_RE.findall(ln["text"]):
                if sid not in scale:
                    out.append("page %d: callout to %s, which is not a sheet in the set" % (i + 1, sid))
                elif scale[sid] != "1:" + den:
                    out.append("page %d: callout %s printed 1:%s, sheet is %s" % (i + 1, sid, den, scale[sid]))
    return out


def _bars(page):
    """Contiguous filled/outlined bar rectangles of 1.5-1.9 mm height: list of (x0_mm, x1_mm, y_mm, [segments])."""
    segs = []
    for d in page.get_drawings():
        r = d["rect"]
        h = r.height / MM
        if 1.5 <= h <= 1.9 and r.width / MM > 2.0 and d.get("fill") is not None or (1.5 <= h <= 1.9 and r.width / MM > 2.0 and d.get("color") is not None):
            segs.append((round(r.x0 / MM, 3), round(r.x1 / MM, 3), round(r.y0 / MM, 1)))
    segs = sorted(set(segs), key=lambda s: (s[2], s[0]))
    chains = []
    for s in segs:
        if chains and abs(chains[-1][2] - s[2]) < 0.05 and abs(chains[-1][1] - s[0]) < 0.06:
            chains[-1] = (chains[-1][0], s[1], s[2], chains[-1][3] + [s])
        else:
            chains.append((s[0], s[1], s[2], [s]))
    return chains


def scale_bar_report(doc, rows):
    """Per scaled sheet: measured bar length, expected length from the printed end label, verdict."""
    rep = []
    for r in rows:
        m = re.fullmatch(r"1:(\d+)", r["scale"] or "")
        if not m or r["sheet"] in SKIP_PAGE_SHEETS or r["page"] > len(doc):
            continue
        den = int(m.group(1))
        pg = doc[r["page"] - 1]
        chains = [c for c in _bars(pg) if (c[1] - c[0]) > 15.0]
        if not chains:
            rep.append({"sheet": r["sheet"], "page": r["page"], "scale": r["scale"], "status": "MISSING"})
            continue
        best = max(chains, key=lambda c: c[1] - c[0])
        L = best[1] - best[0]
        labels = []
        for s in _spans(pg):
            b = [v / MM for v in s["bbox"]]
            if best[2] - 6.5 < b[3] <= best[2] + 0.5 and best[0] - 2 < b[0] < best[1] + 12:
                mm_ = re.fullmatch(r"(\d+)(?:m)?", re.sub(r"\s+", "", s["text"]))
                if mm_:
                    labels.append(int(mm_.group(1)))
        meters = max(labels) if labels else None
        exp = meters * 1000.0 / den if meters else None
        status = "OK" if exp is not None and abs(L - exp) <= 0.3 else ("NO_END_LABEL" if exp is None else "LENGTH_MISMATCH")
        rep.append({"sheet": r["sheet"], "page": r["page"], "scale": r["scale"], "measured_mm": round(L, 3), "end_label_m": meters,
                    "expected_mm": round(exp, 3) if exp else None, "segments_mm": [round(s[1] - s[0], 3) for s in best[3]], "status": status})
    return rep


def check_scale_bars(doc, rows):
    return ["%s (page %d): scale bar %s (measured %s mm, expected %s mm)" % (x["sheet"], x["page"], x["status"], x.get("measured_mm"), x.get("expected_mm"))
            for x in scale_bar_report(doc, rows) if x["status"] != "OK"]


def check_text_bounds(doc, rows):
    skip = {r["page"] for r in rows if r["sheet"] in SKIP_PAGE_SHEETS}
    out = []
    for i, pg in enumerate(doc):
        if i + 1 in skip:
            continue
        W, H = pg.rect.width / MM, pg.rect.height / MM
        for s in _spans(pg):
            x0, y0, x1, y1 = [v / MM for v in s["bbox"]]
            if x0 < 4.0 or y0 < 3.0 or x1 > W - 4.0 or y1 > H - 3.0:
                out.append("page %d: text outside the sheet margin %s %r" % (i + 1, _mm(s["bbox"]), s["text"][:30]))
            elif y0 < TITLE_TOP_MM - 0.2 and y1 > TITLE_TOP_MM + 0.4:
                out.append("page %d: text runs into the title block %s %r" % (i + 1, _mm(s["bbox"]), s["text"][:30]))
    return out


def check_text_overlap(doc, rows, frac=0.35):
    skip = {r["page"] for r in rows if r["sheet"] in SKIP_PAGE_SHEETS}
    out = []
    for i, pg in enumerate(doc):
        if i + 1 in skip:
            continue
        ls = _lines(pg)
        for a in range(len(ls)):
            ba = ls[a]["bbox"]
            for b in range(a + 1, len(ls)):
                bb = ls[b]["bbox"]
                ix, iy = min(ba[2], bb[2]) - max(ba[0], bb[0]), min(ba[3], bb[3]) - max(ba[1], bb[1])
                if ix <= 0.3 or iy <= 0.3:
                    continue
                small = min((ba[2] - ba[0]) * (ba[3] - ba[1]), (bb[2] - bb[0]) * (bb[3] - bb[1]))
                if small > 0 and ix * iy / small > frac:
                    out.append("page %d: text overlap %r / %r at %s" % (i + 1, ls[a]["text"][:24], ls[b]["text"][:24], _mm(ba)))
    return out


def check_fonts(doc, rows=None):
    out = []
    for i, pg in enumerate(doc):
        for f in pg.get_fonts():
            if f[1] == "n/a":
                out.append("page %d: font %s is not embedded" % (i + 1, f[3]))
    return out


def check_duplicates(doc, rows=None, limit=10):
    out = []
    for i, pg in enumerate(doc):
        keys = Counter()
        for d in pg.get_drawings():
            its = tuple((it[0],) + tuple(round(float(v), 2) for p in it[1:] for v in (p if hasattr(p, "__len__") and not isinstance(p, str) else [p]) if isinstance(v, (int, float))) for it in d["items"])
            keys[(its, str(d.get("color")), str(d.get("fill")), round(d.get("width") or 0, 2))] += 1
        dup = sum(c - 1 for c in keys.values() if c > 1)
        if dup > limit:
            out.append("page %d: %d stacked duplicate vector items" % (i + 1, dup))
    return out


def check_north(doc, rows, north_deg=63.2):
    out = []
    for i, pg in enumerate(doc):
        for ln in _lines(pg):
            m = re.fullmatch(r"진북(\d+(?:\.\d+)?)°", ln["text"])
            if m and abs(float(m.group(1)) - north_deg) > 0.06:
                out.append("page %d: north printed %s deg, model north is %.1f deg" % (i + 1, m.group(1), north_deg))
    return out


def check_stale_refs(doc, rows=None):
    out = []
    for i, pg in enumerate(doc):
        for ln in _lines(pg):
            for ref, word in STALE_REFS:
                if ref in ln["text"] and word in ln["text"]:
                    out.append("page %d: stale reference %s with %s: %r" % (i + 1, ref, word, ln["text"][:50]))
    return out


CHECKS = {"page_size": check_page_size, "index": check_index, "callouts": check_callouts, "scale_bars": check_scale_bars, "text_bounds": check_text_bounds,
          "text_overlap": check_text_overlap, "fonts": check_fonts, "duplicates": check_duplicates, "north": check_north, "stale_refs": check_stale_refs}


def run_all(pdf, rows, north_deg=63.2, only=None):
    doc = pymupdf.open(pdf) if isinstance(pdf, str) else pdf
    res = {}
    for name, fn in CHECKS.items():
        if only and name not in only:
            continue
        res[name] = fn(doc, rows, north_deg) if name == "north" else fn(doc, rows)
    return res
