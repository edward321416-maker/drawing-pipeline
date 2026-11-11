"""도면집 A3 시트 구성(밀리미터 단위 SVG → PDF/PNG). 입면·단면·상세·표지가 같은 제목란·선 위계·글꼴을 쓴다.

선 두께(종이 mm)와 글자 크기(pt)는 AGENTS §3.1 위계를 따른다:
  절단 포셰 0.45~0.5 / 보이는 구조 윤곽 0.25 / 보이는 부재 0.15 / 보조·치수·레벨선 0.1 / 격자 0.05
  제목 11~13 pt, 이름 7.5~8.5 pt, 보조 6~6.5 pt, 미세 5~5.5 pt.
"""
import os
import sys

A3 = (420.0, 297.0)
PT = 0.3528                                         # 1 pt = 0.3528 mm
EDITION = "V1"                                      # 도면집 스크립트가 tools/t14g/config.py 값으로 바꾼다(제목란 표기)
PROJECT_CODE = "C-T14D"                             # 같은 방식. 기본값은 V1 그대로
REVISION = ""
ISSUE_DATE = "2026-11-05"


def _detect_font():
    """cairosvg에 줄 CJK 글꼴 이름: tools/t14f/fonts.py가 찾은 글꼴 파일의 family (Windows 경로를 박지 않는다). 못 찾으면 V2와 같은 이름."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from t14f import fonts
        from fontTools.ttLib import TTFont
        path, _ = fonts.resolve("regular")
        fam = TTFont(path, fontNumber=0, lazy=True)["name"].getDebugName(1)
        if fam:
            return "%s, Arial, sans-serif" % fam
    except (ImportError, OSError, FileNotFoundError):
        pass
    return "Malgun Gothic, Arial, sans-serif"


FONT = _detect_font()


class LayoutConflict(Exception):
    """Two claimed layout regions overlap, or a region leaves the sheet."""


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Sheet:
    def __init__(self, sid, title, scale, status, subtitle="", extra_lines=(), paper=A3):
        self.sid, self.title, self.scale, self.status, self.subtitle = sid, title, scale, status, subtitle
        self.paper = paper
        self.extra = list(extra_lines)
        self.claims = []                                # (name, x0, y0, x1, y1): 겹치면 저장 시 LayoutConflict
        self.bars = []                                  # 그린 스케일바의 기대 실측 길이(QA가 PDF에서 다시 잰다)
        self.parts = []
        self._seg = {}                                  # 열린 선분 중복 제거: 선분 키 → 가장 굵은 굵기
        self.dedup_removed = 0
        self.k = 1000.0 / scale if scale else 1.0     # 모델 1 m → 종이 mm (표·문서 시트는 scale=None)

    # 기본 요소 ---------------------------------------------------------------------------------
    def _dedupe_open(self, rings, w, stroke):
        """같은 두 점을 잇는 선분이 이미 같거나 더 굵게 그려졌으면 다시 그리지 않는다. 남은 선분은 연속 구간으로 이어 붙인다."""
        out = []
        for r in rings:
            r = list(r)
            cur = [r[0]] if r else []
            for p, q in zip(r, r[1:]):
                key = tuple(sorted([(round(p[0], 2), round(p[1], 2)), (round(q[0], 2), round(q[1], 2))]))
                if key[0] == key[1]:
                    continue
                prev = self._seg.get(key)
                if prev is not None and prev >= w - 1e-9:
                    self.dedup_removed += 1
                    if len(cur) > 1:
                        out.append(cur)
                    cur = [q]
                    continue
                self._seg[key] = w
                if not cur:
                    cur = [p]
                cur.append(q)
            if len(cur) > 1:
                out.append(cur)
        return out

    def path(self, rings, fill="none", stroke="#000", w=0.15, dash=None, closed=True, evenodd=True, opacity=None):
        rings = [[(round(x, 2), round(y, 2)) for x, y in r] for r in rings]                  # 경로 좌표는 0.01 mm 해상도(인쇄상 차이 없음). 중복 제거 키와 QA 키를 같은 값으로 맞춘다
        if not closed and fill == "none" and dash is None:
            rings = self._dedupe_open(rings, w, stroke)
        d = []
        for r in rings:
            r = list(r)
            if len(r) < 2:
                continue
            d.append("M" + " L".join("%.2f,%.2f" % (x, y) for x, y in r) + (" Z" if closed else ""))
        if not d:
            return
        a = 'd="%s" fill="%s" stroke="%s" stroke-width="%.3f" stroke-linejoin="round" stroke-linecap="round"' % (" ".join(d), fill, stroke if stroke else "none", w)
        if evenodd:
            a += ' fill-rule="evenodd"'
        if dash:
            a += ' stroke-dasharray="%s"' % dash
        if opacity is not None:
            a += ' fill-opacity="%.2f"' % opacity
        self.parts.append("<path %s/>" % a)

    def line(self, x1, y1, x2, y2, w=0.1, color="#888", dash=None):
        self.path([[(x1, y1), (x2, y2)]], stroke=color, w=w, dash=dash, closed=False)

    def text(self, x, y, s, pt=6.5, weight="normal", color="#333", anchor="start", rotate=None, bg=False):
        size = pt * PT
        a = 'x="%.3f" y="%.3f" font-family="%s" font-size="%.3f" font-weight="%s" fill="%s" text-anchor="%s"' % (x, y, FONT, size, weight, color, anchor)
        if rotate is not None:
            a += ' transform="rotate(%.1f %.3f %.3f)"' % (rotate, x, y)
        if bg:                                         # 선 위에 놓일 때만 흰 배경 박스(규칙 §3.3)
            w = len(s) * size * 0.62
            x0 = x - (w / 2 if anchor == "middle" else (w if anchor == "end" else 0))
            self.parts.append('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="#fff"/>' % (x0 - 0.4, y - size * 0.95, w + 0.8, size * 1.25))
        self.parts.append("<text %s>%s</text>" % (a, esc(s)))

    # 공통 요소 ---------------------------------------------------------------------------------
    def claim(self, name, x0, y0, x1, y1):
        """Reserve a rectangle (sheet mm). Overlaps and out-of-sheet regions fail at save() (§3.3 zero collision)."""
        self.claims.append((name, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))

    def check_claims(self, allow=()):
        W, H = self.paper
        errs = []
        for n, x0, y0, x1, y1 in self.claims:
            if x0 < 0 or y0 < 0 or x1 > W or y1 > H:
                errs.append("%s leaves the sheet: (%.1f,%.1f,%.1f,%.1f)" % (n, x0, y0, x1, y1))
        for i, a in enumerate(self.claims):
            for b in self.claims[i + 1:]:
                if (a[0], b[0]) in allow or (b[0], a[0]) in allow:
                    continue
                if a[1] < b[3] and b[1] < a[3] and a[2] < b[4] and b[2] < a[4]:
                    errs.append("%s overlaps %s" % (a[0], b[0]))
        if errs:
            raise LayoutConflict("%s: %s" % (self.sid, "; ".join(errs)))

    def scale_bar(self, x, y, meters=None):
        """Graphic scale bar. Physical length = meters[-1] * 1000/scale paper mm (5 m at 1:50, 10 m at 1:100, 20 m at 1:250)."""
        if meters is None:
            from t14g import registry
            meters = registry.bar_meters(self.scale)
        k = self.k
        L = meters[-1] * k
        self.path([[(x - 3, y - 6.5), (x + L + 14, y - 6.5), (x + L + 14, y + 6), (x - 3, y + 6)]], fill="#fff", stroke="#bbb", w=0.1)
        for i in range(len(meters) - 1):
            x0, x1 = x + meters[i] * k, x + meters[i + 1] * k
            self.path([[(x0, y), (x1, y), (x1, y + 1.6), (x0, y + 1.6)]], fill="#111" if i % 2 == 0 else "#fff", stroke="#111", w=0.15)
        for m in meters:
            self.text(x + m * k, y - 1.4, "%d%s" % (m, " m" if m == meters[-1] else ""), 5.5, "normal", "#333", "middle")
        self.text(x, y + 5.2, "1:%d  %s %g×%g mm 100%% 인쇄 기준" % (self.scale, "A3" if self.paper == A3 else "A1", self.paper[0], self.paper[1]), 5.0, "normal", "#555")
        self.claim("scale_bar", x - 3, y - 6.5, x + L + 14, y + 6)
        self.bars.append({"x_mm": round(x, 3), "y_mm": round(y, 3), "length_mm": round(L, 4), "scale": self.scale, "meters": list(meters)})

    def title_block(self):
        W, H = self.paper
        x0, y0, x1, y1 = 10.0, H - 35.0, W - 10.0, H - 10.0     # A3: 10,262 → 410,287 (V2와 같은 좌표)
        c1, c2 = W - 120.0, W - 62.0                              # A3: 300, 358
        self.claim("title_block", x0, y0, x1, y1)
        self.path([[(x0, y0), (x1, y0), (x1, y1), (x0, y1)]], fill="#fff", stroke="#222", w=0.35)
        self.line(c1, y0, c1, y1, 0.2, "#222")
        self.line(c2, y0, c2, y1, 0.2, "#222")
        self.text(x0 + 4, y0 + 7.5, self.sid, 12, "bold", "#111")
        self.text(x0 + 30, y0 + 7.5, self.title, 12, "bold", "#111")
        if self.subtitle:
            self.text(x0 + 30, y0 + 13.5, self.subtitle, 7, "normal", "#444")
        yy = y0 + 19
        for ln in self.extra[:2]:
            self.text(x0 + 30, yy, ln, 6, "normal", "#555")
            yy += 4.2
        pn = "A3" if self.paper == A3 else ("A1" if self.paper == (841.0, 594.0) else "%gx%g" % self.paper)
        self.text(c1 + 5, y0 + 7, ("축척 1:%d (%s)" % (self.scale, pn)) if self.scale else "축척 — (표·문서, %s)" % pn, 8, "bold", "#222")
        parts = [t.strip() for t in self.status.split(" · ")]
        lines = [parts[0], " · ".join(parts[1:])] if len(parts) > 1 else [parts[0]]            # 상태 문구는 '·' 단위로 두 줄까지(제목란 옆 칸을 침범하지 않게)
        yy2 = y0 + 12.5
        for i, ln_ in enumerate(lines[:2]):
            self.text(c1 + 5, yy2, ln_, 5.5, "bold" if i == 0 else "normal", "#a33")
            yy2 += 4.0
        self.text(c1 + 5, y0 + 21.5, "도면집 후보 %s · FREEZE 아님" % EDITION, 5.5, "normal", "#555")
        self.text(c2 + 5, y0 + 7, PROJECT_CODE, 8, "bold", "#222")
        self.text(c2 + 5, y0 + 13, ("개정 %s (%s)" % (REVISION, EDITION)) if REVISION else ISSUE_DATE, 6, "normal", "#555")
        if REVISION:
            self.text(c2 + 5, y0 + 18.5, "출력 %s" % ISSUE_DATE, 6, "normal", "#555")

    def north_arrow(self, x, y, north_deg_from_up, r=7.0, label="N"):
        import math
        self.path([[(x + r * math.cos(t / 20 * 2 * math.pi), y + r * math.sin(t / 20 * 2 * math.pi)) for t in range(21)]], stroke="#555", w=0.2, closed=True)
        a = math.radians(north_deg_from_up)
        tip = (x + math.sin(a) * (r + 3.5), y - math.cos(a) * (r + 3.5))
        self.path([[(x, y), tip]], stroke="#222", w=0.35, closed=False)
        self.text(tip[0], tip[1] - 1.0, label, 7, "bold", "#111", "middle")

    # 저장 --------------------------------------------------------------------------------------
    def save(self, base, png_width=None, allow=()):
        import cairosvg
        W, H = self.paper
        self.check_claims(allow)
        png_width = png_width or int(round(W / 25.4 * 300))                                   # 300 dpi (A3 = 4961 px)
        svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" viewBox="0 0 %g %g">' % (W, H, W, H),
               '<metadata>%s</metadata>' % esc(self.status), '<rect width="%g" height="%g" fill="#fff"/>' % (W, H)] + self.parts + ["</svg>"]
        os.makedirs(os.path.dirname(base), exist_ok=True)
        open(base + ".svg", "w", encoding="utf-8").write("\n".join(svg))
        cairosvg.svg2pdf(url=base + ".svg", write_to=base + ".pdf")
        cairosvg.svg2png(url=base + ".svg", write_to=base + ".png", output_width=png_width, background_color="white")
        return base


def geom_rings(g):
    """shapely Polygon/MultiPolygon → 외곽·구멍 링 목록."""
    rings = []
    if g.is_empty:
        return rings
    polys = list(g.geoms) if hasattr(g, "geoms") else [g]
    for p in polys:
        if p.geom_type != "Polygon":
            continue
        rings.append(list(p.exterior.coords))
        rings += [list(r.coords) for r in p.interiors]
    return rings


def geom_lines(g):
    """LineString/MultiLineString/GeometryCollection → 선 목록."""
    out = []
    if g.is_empty:
        return out
    if g.geom_type == "LineString":
        return [list(g.coords)]
    if hasattr(g, "geoms"):
        for h in g.geoms:
            out += geom_lines(h)
    return out
