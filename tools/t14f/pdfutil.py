"""Small PyMuPDF helpers shared by the V3 patcher and the QA scripts."""
import re

import pymupdf

from registry import MM


def rgb(c):
    return ((c >> 16) & 255) / 255.0, ((c >> 8) & 255) / 255.0, (c & 255) / 255.0


def norm(s):
    """Text with all whitespace removed (V2 PDFs lose word spaces on extraction)."""
    return re.sub(r"\s+", "", s)


def lines(page):
    """Every text line of a page with geometry, so callers can match on text and rewrite it."""
    out = []
    for b in page.get_text("rawdict")["blocks"]:
        for l in b.get("lines", []):
            spans = l["spans"]
            if not spans:
                continue
            text = "".join("".join(c["c"] for c in s["chars"]) for s in spans)
            s0 = spans[0]
            out.append({"text": text, "norm": norm(text), "bbox": pymupdf.Rect(l["bbox"]),
                        "origin": tuple(s0["origin"]), "size": s0["size"], "color": s0["color"],
                        "font": s0["font"], "spans": spans})
    return out


def spans(page):
    out = []
    for ln in lines(page):
        for s in ln["spans"]:
            t = "".join(c["c"] for c in s["chars"])
            out.append({"text": t, "bbox": pymupdf.Rect(s["bbox"]), "origin": tuple(s["origin"]),
                        "size": s["size"], "color": s["color"], "font": s["font"]})
    return out


def mm(v):
    return v / MM
