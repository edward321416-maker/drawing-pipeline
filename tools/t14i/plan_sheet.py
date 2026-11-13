"""C-T14I 평면 시트 조립기 (일반화판): 용지·축척·도면 창·패널 위치를 매개변수로 받는다.

    compose(run, floor, sid, applies, model, regs, evidence, out_dir, paper=(420, 297), scale=250, window=None, tile=None, role="overview"|"full"|"tile")

  overview  A3 1:250 개요도(OVERVIEW)  - 건물 전체, 오른쪽 패널                 (V3 P-101~105 대체)
  full      A1 1:200 전체 평면         - 건물 전체, 오른쪽 3단 패널                (P-201, P-202)
  tile      A3 1:200 분할 평면         - 건물 일부(창), MATCH LINE·겹침 구간·등록 표식·타일 키 (P-211~214)

V3 조립기(tools/t14e_plan_sheet.py)에서 바뀐 점
  * 축척 K=1000/scale, 용지·창·패널 좌표는 모두 계산한다(250·CX·CY·PANEL 상수 없음). 제목란은 Sheet(paper=...).
  * 글자: 모두 6 pt 이상, 치수·범례 이름·주기는 7 pt. 구역 번호 기호는 렌더러 매개변수(--num-pt 등)로 종이 크기 그대로.
  * 단면·입면·상세 기호는 흰 배경 상자를 쓰지 않는다. 가구·기둥·튜브·번호가 없는 빈자리를 찾아 놓고 상세는 지시선으로 잇는다.
  * 범례 패널은 글자 폭을 실측해 줄바꿈하고, 넘치면 LayoutConflict(잘림 없음).
  * 상태 문구: MODEL VERIFIED(구조·치수) / CONCEPT PROPOSED(가구·동선·프로그램) / UNRESOLVED(상층 벽·문·피난).
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys

import t14i  # noqa: F401  (edition env, sys.path, text policy)
from t14i import common as cm
from t14i import config as cfg

import pipeline_common as pc  # noqa: E402
from shapely import wkt as _wkt  # noqa: E402
from shapely.affinity import affine_transform  # noqa: E402
from shapely.geometry import LineString, Point, Polygon, box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402
from shapely.prepared import prep  # noqa: E402

import t14d_sheet as _ts  # noqa: E402
from t14d_sheet import Sheet, LayoutConflict  # noqa: E402
import t14e_dims as dm  # noqa: E402
import t14e_plan_sheet as legacy  # noqa: E402  (STRATEGY·uniq·obj_center_r 재사용; 이 모듈은 수정하지 않는다)
from t14g import registry  # noqa: E402

PT_MM = _ts.PT                      # 1 pt = 0.3528 mm
PT_DIM = 7.0                        # 치수 문자
PT_NOTE = 7.0                       # 범례 이름·주기
PT_SYM = 6.0                        # 기호 안 문자(번호·참조 시트)
MARGIN_L, MARGIN_T, MARGIN_R, MARGIN_B = 25.0, 21.0, 11.0, 10.0      # 평면 창 바깥 주석 폭(mm): 축선 기호·치수열
WIN_MARGIN_M = 0.3                  # 건물 바깥으로 보이는 창 여유(m)
SHEET_TOP, TITLE_H = 5.0, 35.0
RAW_NUM_STYLE = {250: dict(pt=7.5, r=2.4, r_small=1.9, small_factor=0.87, clear=0.70),
                 200: dict(pt=7.5, r=2.4, r_small=1.9, small_factor=0.87, clear=0.58)}
STATUS_MV, STATUS_CP, STATUS_UR = cfg.MODEL_VERIFIED, cfg.CONCEPT_PROPOSED, cfg.UNRESOLVED


# ─────────────────────────────────────────────────────────────────────────────────────────────────
# 글자 폭 실측 · 블록 흐름(범례 패널)
# ─────────────────────────────────────────────────────────────────────────────────────────────────
class Meter:
    """실제 글꼴(Malgun Gothic)의 자폭으로 글자 폭(mm)을 잰다. 줄바꿈·잘림 검사에 쓴다."""
    _inst = None

    def __init__(self):
        from fontTools.ttLib import TTFont
        from t14f import fonts
        self.f = {}
        for face in ("regular", "bold"):
            path, _ = fonts.resolve(face)
            t = TTFont(path, fontNumber=0, lazy=True)
            self.f[face] = (t.getBestCmap(), t["hmtx"].metrics, t["head"].unitsPerEm)

    @classmethod
    def get(cls):
        if cls._inst is None:
            cls._inst = Meter()
        return cls._inst

    def width(self, s, pt, bold=False):
        cmap, hm, upm = self.f["bold" if bold else "regular"]
        size = pt * PT_MM
        tot = 0.0
        for ch in s:
            g = cmap.get(ord(ch))
            tot += hm[g][0] if g in hm else upm * 0.6
        return tot / upm * size

    def wrap(self, s, pt, w, bold=False):
        out, cur = [], ""
        for tok in re.findall(r"\S+\s*", s) or [""]:
            if self.width((cur + tok).rstrip(), pt, bold) <= w:
                cur += tok
                continue
            if cur:
                out.append(cur.rstrip())
                cur = ""
            while self.width(tok.rstrip(), pt, bold) > w and len(tok) > 1:     # 한 낱말이 한 줄보다 길면 글자 단위로 자른다
                k = len(tok)
                while k > 1 and self.width(tok[:k], pt, bold) > w:
                    k -= 1
                out.append(tok[:k])
                tok = tok[k:]
            cur = tok
        if cur.strip() or not out:
            out.append(cur.rstrip())
        return out


class Block:
    """범례 패널의 한 덩어리(제목·문단·기호 줄·배지). measure로 높이를 먼저 재고, draw로 그린다."""

    def __init__(self):
        self.ops = []

    def head(self, t, pt=8.5):
        self.ops.append(("head", t, pt))
        return self

    def para(self, t, pt=PT_NOTE, color="#333", indent=0.0, bullet=None, bold=False):
        self.ops.append(("para", t, pt, color, indent, bullet, bold))
        return self

    def item(self, sym, t, pt=PT_NOTE, sw=8.0, color="#222"):
        self.ops.append(("item", sym, t, pt, sw, color))
        return self

    def badge(self, kind, t, pt=PT_NOTE):
        self.ops.append(("badge", kind, t, pt))
        return self

    def gap(self, mm):
        self.ops.append(("gap", mm))
        return self

    def rule(self):
        self.ops.append(("rule",))
        return self

    def run(self, sh, x, y, w, dry=False):
        """(sh, x, y, w) 위쪽 y에서 시작해 끝 y를 돌려준다. dry=True면 그리지 않고 높이만."""
        m = Meter.get()
        for op in self.ops:
            k = op[0]
            if k == "gap":
                y += op[1]
            elif k == "rule":
                if not dry:
                    sh.line(x, y + 0.8, x + w, y + 0.8, 0.15, "#999")
                y += 2.2
            elif k == "head":
                _, t, pt = op
                if not dry:
                    sh.text(x, y + pt * PT_MM * 0.85, t, pt, "bold", "#111")
                y += pt * PT_MM * 1.55
            elif k == "para":
                _, t, pt, col, ind, bullet, bold = op
                size = pt * PT_MM
                lines = m.wrap(t, pt, w - ind - (2.4 if bullet else 0.0), bold)
                for i, ln in enumerate(lines):
                    if not dry:
                        if bullet and i == 0:
                            sh.text(x + ind, y + size * 0.85, bullet, pt, "normal", col)
                        sh.text(x + ind + (2.4 if bullet else 0.0), y + size * 0.85, ln, pt, "bold" if bold else "normal", col)
                    y += size * 1.42
                y += 0.5
            elif k == "item":
                _, sym, t, pt, sw, col = op
                size = pt * PT_MM
                lines = m.wrap(t, pt, w - sw - 1.0)
                h0 = max(size * 1.42, 4.6 if callable(sym) else 0.0)
                if not dry:
                    if callable(sym):
                        sym(sh, x, y + h0 / 2)
                    elif sym:
                        sh.text(x + sw / 2, y + size * 0.85 + (h0 - size * 1.42) / 2, sym, pt, "bold", col, "middle")
                    for i, ln in enumerate(lines):
                        sh.text(x + sw + 1.0, y + size * 0.85 + (h0 - size * 1.42) / 2 + i * size * 1.42, ln, pt, "normal", col)
                y += max(h0, size * 1.42 * len(lines)) + 0.7
            elif k == "badge":
                _, kind, t, pt = op
                size = pt * PT_MM
                bw = m.width(kind, 6.0, True) + 3.0
                lines = m.wrap(t, pt, w - bw - 1.5)
                if not dry:
                    cm.badge(sh, x, y, kind, w=bw, h=4.4, pt=6.0)
                    for i, ln in enumerate(lines):
                        sh.text(x + bw + 1.5, y + size * 0.85 + 0.4 + i * size * 1.42, ln, pt, "normal", "#333")
                y += max(4.4, size * 1.42 * len(lines) + 0.4) + 1.0
        return y

    def height(self, w):
        return self.run(None, 0.0, 0.0, w, dry=True)


def place_blocks(sh, blocks, rect, ncols=1, gap=6.0, name="panel", pt_note=None):
    """블록들을 직사각형 rect=(x0,y0,x1,y1)의 ncols 단에 위에서 아래로 채운다. 넘치면 LayoutConflict. 채운 영역을 claim한다."""
    x0, y0, x1, y1 = rect
    cw = (x1 - x0 - gap * (ncols - 1)) / ncols
    col, y = 0, y0
    used = [y0] * ncols
    for b in blocks:
        h = b.height(cw)
        if y + h > y1 + 1e-6:
            col += 1
            y = y0
            if col >= ncols or h > y1 - y0:
                raise LayoutConflict("%s: 패널이 넘친다(블록 높이 %.1f mm, 남은 %.1f mm, 단 %d/%d)" % (name, h, y1 - y, col + 1, ncols))
        b.run(sh, x0 + col * (cw + gap), y, cw)
        y += h
        used[col] = y
    sh.claim(name, x0, y0, x1, y1)
    return {"cols": ncols, "col_width_mm": round(cw, 1), "bottom_mm": [round(u, 1) for u in used], "free_mm": round(y1 - max(used), 1)}


# ─────────────────────────────────────────────────────────────────────────────────────────────────
# 좌표 틀 · 점유 영역
# ─────────────────────────────────────────────────────────────────────────────────────────────────
class Frame:
    """도면 좌표(m, y 위) ↔ 시트 좌표(mm, y 아래). 창(win)의 왼쪽 위가 시트 (px0, py0)."""

    def __init__(self, K, win, px0, py0):
        self.K, self.win, self.px0, self.py0 = K, tuple(win), px0, py0

    def X(self, x):
        return self.px0 + (x - self.win[0]) * self.K

    def Y(self, y):
        return self.py0 + (self.win[3] - y) * self.K

    def inx(self, X):
        return self.win[0] + (X - self.px0) / self.K

    def iny(self, Y):
        return self.win[3] - (Y - self.py0) / self.K

    @property
    def rect(self):
        w = self.win
        return (self.px0, self.py0, self.px0 + (w[2] - w[0]) * self.K, self.py0 + (w[3] - w[1]) * self.K)

    @property
    def matrix(self):
        return [self.K, 0, 0, -self.K, self.px0 - self.win[0] * self.K, self.py0 + self.win[3] * self.K]

    def inside(self, x, y, pad=0.0):
        w = self.win
        return w[0] + pad <= x <= w[2] - pad and w[1] + pad <= y <= w[3] - pad


def _poly(g):
    return None if not g else _wkt.loads(g)


def load_occupancy(chk, cuts):
    """렌더러 점검 JSON의 점유 정보(WKT, 도면 좌표 m) + 모델 기둥·코어 박스 → 점유 도형 목록."""
    occ = chk.get("occupancy")
    if not occ:
        raise ValueError("raw 평면 점검 JSON에 occupancy가 없다: 렌더러를 --occupancy로 다시 실행해야 한다")
    parts = {"furniture": _poly(occ["furniture"]), "walls": _poly(occ["walls"]), "tubes": _poly(occ["tubes"]), "symbols": _poly(occ["symbols"]),
             "model_only": _poly(occ["model_only"]), "door_swings": _poly(occ["door_swings"])}
    parts["columns"] = unary_union([g for _, g in cuts.get("column", [])]) if cuts.get("column") else None
    parts["cores"] = unary_union([g.convex_hull for it, g in cuts.get("core_wall", [])]) if cuts.get("core_wall") else None
    parts["numbers"] = unary_union([Point(x, y).buffer(r) for _, x, y, r in occ["numbers"]]) if occ["numbers"] else None
    return {k: v for k, v in parts.items() if v is not None and not v.is_empty}


BUF = {"furniture": 0.25, "walls": 0.15, "tubes": 0.2, "symbols": 0.2, "model_only": 0.2, "door_swings": 0.1, "columns": 0.3, "cores": 0.2, "numbers": 0.3}


# ─────────────────────────────────────────────────────────────────────────────────────────────────
# 기호(참조 기호는 흰 배경 상자 없이)
# ─────────────────────────────────────────────────────────────────────────────────────────────────
def _circle(cx, cy, r, n=24):
    return [(cx + r * math.cos(t / n * 2 * math.pi), cy + r * math.sin(t / n * 2 * math.pi)) for t in range(n + 1)]


def tag_label(sh, x, base_y, s, color):
    sh.text(x, base_y, s, 6.0, "normal", color, "middle")


def section_tag_fp(meter, x, y, ay, ax, ref, r=3.2):
    """단면 기호(원 + 화살표 + 시트 번호 글자)가 차지하는 시트 mm 도형."""
    tip = (x + ax * (r + 4.0), y + ay * (r + 4.0))
    base = y + r + 3.4 if ay >= 0 else y - r - 1.4
    w = meter.width(ref, 6.0) + 1.0
    return unary_union([Point(x, y).buffer(r + 0.5), LineString([(x, y), tip]).buffer(1.3), box(x - w / 2, base - 2.2, x + w / 2, base + 0.6)])


def draw_section_tag(sh, x, y, letter, ref, arrow, r=3.2):
    dm.bubble(sh, x, y, letter, r=r, pt=7.5, color="#c00")
    ax, ay = arrow
    tip = (x + ax * (r + 4.0), y + ay * (r + 4.0))
    sh.path([[(x + ax * r, y + ay * r), tip]], stroke="#c00", w=0.35, closed=False)
    px, py = -ay, ax
    sh.path([[tip, (tip[0] - ax * 1.6 + px * 1.0, tip[1] - ay * 1.6 + py * 1.0), (tip[0] - ax * 1.6 - px * 1.0, tip[1] - ay * 1.6 - py * 1.0)]], fill="#c00", stroke="#c00", w=0.1, closed=True)
    tag_label(sh, x, y + r + 3.4 if ay >= 0 else y - r - 1.4, ref, "#c00")


def elev_tag_fp(meter, x, y, d, ref, r=3.4):
    dx, dy = d
    tip = (x + dx * (r + 4.0), y + dy * (r + 4.0))
    w = meter.width(ref, 6.0) + 1.0
    return unary_union([Point(x, y).buffer(r + 0.5), Point(tip).buffer(2.4), box(x - w / 2, y + r + 3.2 - 2.2, x + w / 2, y + r + 3.2 + 0.6)])


def draw_elev_tag(sh, x, y, ref, d, r=3.4):
    dm.bubble(sh, x, y, ref.split("-")[1], r=r, pt=6.5, color="#06a")
    dx, dy = d
    tip = (x + dx * (r + 4.0), y + dy * (r + 4.0))
    px, py = -dy, dx
    sh.path([[tip, (tip[0] - dx * 3.0 + px * 1.6, tip[1] - dy * 3.0 + py * 1.6), (tip[0] - dx * 3.0 - px * 1.6, tip[1] - dy * 3.0 - py * 1.6)]], fill="#06a", stroke="#06a", w=0.1, closed=True)
    tag_label(sh, x, y + r + 3.2, ref, "#06a")


class _NoBg:
    """dm.detail_tag가 글자 뒤에 흰 상자(bg=True)를 깔지 못하게 하는 얇은 덮개. 나머지는 Sheet 그대로."""

    def __init__(self, sh):
        self._sh = sh

    def __getattr__(self, k):
        return getattr(self._sh, k)

    def text(self, *a, **kw):
        kw["bg"] = False
        return self._sh.text(*a, **kw)


def detail_tag_fp(meter, bx, by, sid, r=3.4):
    lab = registry.callout_label(sid)
    w = meter.width(lab, 6.0) + 1.0
    return unary_union([Point(bx, by).buffer(r + 0.5), box(bx - w / 2, by + r + 3.0 - 2.2, bx + w / 2, by + r + 3.0 + 0.6)])


# ─────────────────────────────────────────────────────────────────────────────────────────────────
# 타일 분할
# ─────────────────────────────────────────────────────────────────────────────────────────────────
def make_tiles(bounds, rows, ids, pick=0.42, wm=WIN_MARGIN_M, edge=0.5):
    """건물을 도면 y축(시트 위아래)으로 두 창으로 나눈다. 쪼갬선은 두 축선 행 사이의 가운데이고,
    두 창은 그 두 행을 모두 품는다(겹침 구간 = 행 간격 + 2·edge). 같은 행·같은 모델 좌표가 두 장에 모두 나온다."""
    bx0, by0, bx1, by1 = bounds
    rd = sorted(rows, reverse=True)
    mids = [((a + b) / 2, a, b) for a, b in zip(rd, rd[1:])]
    target = by1 - pick * (by1 - by0)
    ym, ra, rb = min(mids, key=lambda m: abs(m[0] - target))        # ra > rb  (위 행, 아래 행)
    w1 = (bx0 - wm, rb - edge, bx1 + wm, by1 + wm)
    w2 = (bx0 - wm, by0 - wm, bx1 + wm, ra + edge)
    return [{"index": 1, "count": 2, "id": ids[0], "other": ids[1], "window": w1, "match_y": ym, "rows_pair": (ra, rb), "overlap": (rb - edge, ra + edge)},
            {"index": 2, "count": 2, "id": ids[1], "other": ids[0], "window": w2, "match_y": ym, "rows_pair": (ra, rb), "overlap": (rb - edge, ra + edge)}]


# ─────────────────────────────────────────────────────────────────────────────────────────────────
# 배치(용지·창·패널)
# ─────────────────────────────────────────────────────────────────────────────────────────────────
def plan_layout(role, paper, K, win, tile=None):
    W, H = paper
    ww, wh = (win[2] - win[0]) * K, (win[3] - win[1]) * K
    bot = H - TITLE_H - 4.0                              # 제목란 위 4 mm
    L, T, R, B = MARGIN_L, MARGIN_T, MARGIN_R, MARGIN_B
    lay = {"paper": paper, "bot": bot}
    if role == "overview":
        pnl = (W - 115.0, 8.0, W - 9.0, bot)
        ax0, ax1 = 12.0, pnl[0] - 4.0
        px0 = ax0 + L + ((ax1 - ax0) - (L + ww + R)) / 2
        py0 = SHEET_TOP + T + ((bot - SHEET_TOP) - (T + wh + B)) / 2
        lay.update(panel=pnl, ann=(px0 - L, py0 - T, px0 + ww + R, py0 + wh + B))
    elif role == "full":
        px0 = 12.0 + L + 8.0
        py0 = SHEET_TOP + T + ((bot - SHEET_TOP) - (T + wh + B)) / 2
        pnl = (px0 + ww + R + 18.0, py0 - T, W - 12.0, py0 + wh + B)
        lay.update(panel=pnl, ann=(px0 - L, py0 - T, px0 + ww + R, py0 + wh + B))
    elif role == "tile":
        px0 = 12.0 + L
        py0 = SHEET_TOP + T
        ann = (px0 - L, py0 - T, px0 + ww + R, py0 + wh + B)
        match_zone = (ann[2] + 1.0, py0, ann[2] + 27.0, py0 + wh)
        right = (match_zone[2] + 3.0, SHEET_TOP + 3.0, W - 12.0, bot)
        band = (12.0, ann[3] + 3.0, ann[2], bot)
        lay.update(ann=ann, match_zone=match_zone, right=right, band=band)
    else:
        raise ValueError("role: overview | full | tile")
    if px0 + ww + R > W - 8 or py0 + wh + B > bot + 0.01:
        raise LayoutConflict("%s: 도면 창 %.0f x %.0f mm + 주석 여백이 용지 %g x %g mm 안에 안 든다" % (role, ww, wh, W, H))
    lay["px0"], lay["py0"] = px0, py0
    return lay


# ─────────────────────────────────────────────────────────────────────────────────────────────────
# 조립
# ─────────────────────────────────────────────────────────────────────────────────────────────────
def raw_paths(raw_dir, floor, scale):
    base = os.path.join(raw_dir, "raw_plan_%s_s%d" % (floor, scale))
    return base + ".svg", base + "_check.json"


def render_raw(run, floor, scale, raw_dir, png_width=1600):
    """렌더러 CLI로 bare 평면(+점유 JSON)을 만든다. 이미 있으면 다시 만들지 않는다(삭제 후 재실행하면 다시 생성)."""
    svg, chk = raw_paths(raw_dir, floor, scale)
    if os.path.exists(svg) and os.path.exists(chk):
        return svg, chk
    ns = RAW_NUM_STYLE[scale]
    cmd = [sys.executable, "-X", "utf8", "-I", os.path.join(t14i.ROOT, "src", "architectural_plan_renderer.py"), "--out", run, "--floor", floor, "--scale", str(scale), "--v3layout", "--bare", "--cleanline",
           "--final-dir", raw_dir, "--name", "raw_plan_%s_s%d" % (floor, scale), "--png-width", str(png_width), "--num-pt", str(ns["pt"]), "--num-r", str(ns["r"]), "--num-r-small", str(ns["r_small"]),
           "--num-small-factor", str(ns["small_factor"]), "--num-clear", str(ns["clear"]), "--occupancy"]
    os.makedirs(raw_dir, exist_ok=True)
    subprocess.run(cmd, check=True)
    return svg, chk


def _status_line(floor, level_s=True):
    return "LEVEL S · 구조 MODEL VERIFIED · 가구 CONCEPT PROPOSED"


def compose(run, floor, sid, applies, model, regs, evidence, out_dir, paper=(420.0, 297.0), scale=250, window=None, tile=None, role="overview",
            raw_dir=None, sheet_title=None, file_tag=None, png_width=None, extra_notes=()):
    paper = (float(paper[0]), float(paper[1]))
    K = 1000.0 / scale
    raw_dir = raw_dir or cm.v4_dir(run, "plans_raw")
    raw_svg, raw_chk = raw_paths(raw_dir, floor, scale)
    if not (os.path.exists(raw_svg) and os.path.exists(raw_chk)):
        raise FileNotFoundError("raw 평면이 없다: %s (render_raw로 만든다)" % raw_svg)
    chk = cm.jl(raw_chk)
    sl = pc.load_slice(os.path.join(run, "raw_slices"), floor)
    bnd = pc.load_bounds(os.path.join(run, "raw_slices"))
    b = bnd["building"]
    lay_p = os.path.join(run, "vector", "floor_%s_layout.json" % floor)
    bx0, by0, bx1, by1 = (cm.jl(lay_p)["building"] if os.path.exists(lay_p) else [b["xmin"], b["ymin"], b["xmax"], b["ymax"]])
    cuts = pc.cut_geometries(sl)
    meter = Meter.get()
    meta = {"overall_chains": 0, "grid_chains": 0, "setout_chains": 0, "major_dims": 0, "axis_bubbles": 0, "section_tags": 0, "elevation_tags": 0, "detail_callouts": 0, "tags_on_occupied_spot": 0,
            "major_dims_on_occupied_spot": 0, "chain_segments_printed": 0}
    facts = []

    def fact(i, label, value, unit, klass, source, printed):
        facts.append({"id": "%s:%s" % (sid, i), "label": label, "value": value, "unit": unit, "class": klass, "source": source, "printed": printed})

    # ── 축·도면 창 ──────────────────────────────────────────────────────────────────────────────
    cols = [g.centroid for _, g in cuts.get("column", [])]
    xs = legacy.uniq([c.x for c in cols])
    ys = legacy.uniq([c.y for c in cols])
    xl, yl = dm.axis_labels(xs, ys)
    if window is None:
        # A3 분할도는 CLI가 계산한 실제 모델 좌표 창을 그대로 사용한다.
        # 전체 평면 창을 다시 적용하면 1:200 물리 크기가 A3를 초과한다.
        window = tile["window"] if tile else (
            bx0 - WIN_MARGIN_M,
            by0 - WIN_MARGIN_M,
            bx1 + WIN_MARGIN_M,
            by1 + WIN_MARGIN_M,
        )
    lay = plan_layout(role, paper, K, window, tile)
    fr = Frame(K, window, lay["px0"], lay["py0"])
    X, Y = fr.X, fr.Y
    win_rect = fr.rect
    whole = tile is None

    # ── 시트 ───────────────────────────────────────────────────────────────────────────────────
    progs = [z["name_ko"] for z in sl["zones"]]
    plan_name = "%d층" % int(floor[:-1]) if floor.endswith("F") and floor[:-1].isdigit() else floor.replace("B", "지하 ")
    pn = {"overview": "A3 1:%d OVERVIEW 개요도" % scale, "full": "A1 1:%d 전체 평면" % scale,
          "tile": "A3 1:%d 분할 평면 %d/%d" % (scale, tile["index"], tile["count"]) if tile else ""}[role]
    title = sheet_title or "%s 기준 평면도 · %s (적용: %s)" % (plan_name, pn, "·".join(applies))
    sub = {"overview": "OVERVIEW 개요도 — 1:200 평면이 아님(A1 1:200 P-20x · A3 1:200 분할 P-21x 참조) · 치수 mm · 축선=모델 기둥 중심선",
           "full": "치수 단위 mm · 축선은 모델 기둥 중심선 · 상층 구획벽·문은 모델에 없어 UNRESOLVED(그리지 않음)",
           "tile": "치수 단위 mm · 축선·좌표는 이웃 도면과 동일 · MATCH LINE %s 와 이어 붙임 · 겹침 구간 등록 표식 R1~R3" % (tile["other"] if tile else "")}[role]
    extra = ["프로그램: " + ", ".join(dict.fromkeys(progs)) if progs else "프로그램: -",
             "도면 방향: 1층 마스터와 동일(north_deg %.1f°, frame-ref) · 가구·동선·프로그램 배치 = CONCEPT PROPOSED(PROPOSED_ONLY)" % model.north_deg]
    sh = Sheet(sid, title, scale, _status_line(floor), subtitle=sub, extra_lines=extra, paper=paper)

    # ── raw 평면 얹기(창으로 자른다) ───────────────────────────────────────────────────────────────
    svg = open(raw_svg, encoding="utf-8").read()
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    W_raw, H_raw = float(m.group(1)), float(m.group(2))
    rwin = chk["window_world"]                                   # raw 캔버스가 덮는 도면 좌표 (xmin, ymin, xmax, ymax)
    if not (rwin[0] <= window[0] + 1e-6 and rwin[1] <= window[1] + 1e-6 and rwin[2] >= window[2] - 1e-6 and rwin[3] >= window[3] - 1e-6):
        raise LayoutConflict("%s: 도면 창 %s 가 raw 캔버스 %s 밖이다" % (sid, [round(v, 2) for v in window], [round(v, 2) for v in rwin]))
    inner = svg[svg.index(">", svg.index("<svg")) + 1: svg.rindex("</svg>")]
    inner = re.sub(r'<rect width="[\d.]+" height="[\d.]+" fill="#ffffff"/>', "", inner, count=1)
    inner = re.sub(r"<metadata>.*?</metadata>", "", inner, flags=re.S)
    tx, ty = X(rwin[0]), Y(rwin[3])                                # raw (0,0) = 도면 좌표 (xmin, ymax)
    sh.parts.append('<defs><clipPath id="drawclip"><rect x="%.3f" y="%.3f" width="%.3f" height="%.3f"/></clipPath></defs>' % (win_rect[0], win_rect[1], win_rect[2] - win_rect[0], win_rect[3] - win_rect[1]))
    sh.parts.append('<g clip-path="url(#drawclip)"><g transform="translate(%.3f %.3f) scale(%.5f)">%s</g></g>' % (tx, ty, K, inner))
    sh.claim("plan_annotation", *lay["ann"])

    # ── 점유 도형(시트 mm) ────────────────────────────────────────────────────────────────────────
    occ_parts = load_occupancy(chk, cuts)
    occ_model = unary_union([g.buffer(BUF[k]) for k, g in occ_parts.items()])
    occ = affine_transform(occ_model, fr.matrix)
    placed = []                                                   # 이미 놓은 기호·선(시트 mm)

    def free(fp, pad=0.0):
        r = win_rect
        if not box(r[0] + 1.0, r[1] + 1.0, r[2] - 1.0, r[3] - 1.0).contains(fp):
            return False
        if fp.intersects(occ):
            return False
        return not any(fp.intersects(p) for p in placed)

    # ── 축선 · 치수열 ───────────────────────────────────────────────────────────────────────────
    top_ref, bot_ref = Y(min(window[3], by1)), Y(max(window[1], by0))
    lft_ref, rgt_ref = X(max(window[0], bx0)), X(min(window[2], bx1))
    Xl, Xr, Yt, Yb = lft_ref, rgt_ref, top_ref, bot_ref
    in_y = lambda y: window[1] - 1e-6 <= y <= window[3] + 1e-6
    axis_facts = {"cols": [], "rows": []}
    for x in xs:                                                                       # 위쪽 알파벳 기호
        lab = xl[round(x, 2)] if round(x, 2) in xl else chr(65 + xs.index(x))
        sh.line(X(x), Yt - 1.0, X(x), Yt - 14.5, 0.1, "#888", "6,1.4,1,1.4")
        dm.bubble(sh, X(x), Yt - 18.0, lab, r=3.0, pt=7.0)
        meta["axis_bubbles"] += 1
        axis_facts["cols"].append((lab, round(x, 3)))
    for y in ys:                                                                       # 왼쪽 숫자 기호
        if not in_y(y):
            continue
        lab = yl[round(y, 2)] if round(y, 2) in yl else str(len(ys) - ys.index(y))
        sh.line(Xl - 1.0, Y(y), Xl - 14.5, Y(y), 0.1, "#888", "6,1.4,1,1.4")
        dm.bubble(sh, Xl - 18.0, Y(y), lab, r=3.0, pt=7.0)
        meta["axis_bubbles"] += 1
        axis_facts["rows"].append((lab, round(y, 3)))
    gx = [bx0] + [x for x in xs if bx0 + 0.2 < x < bx1 - 0.2] + [bx1]
    dm.chain_h(sh, [X(v) for v in gx], Yt - 5.0, [dm.fmt_mm(b_ - a_) for a_, b_ in zip(gx, gx[1:])], from_y=Yt, pt=PT_DIM)
    meta["grid_chains"] += 1
    meta["chain_segments_printed"] += len(gx) - 1
    for a_, b_ in zip(gx, gx[1:]):
        fact("grid_x_%.2f" % a_, "축선 간격(가로) %.2f~%.2f" % (a_, b_), int(dm.fmt_mm(b_ - a_)), "mm", cfg.MODEL_VERIFIED, "모델 기둥 중심 좌표 차(10 mm 반올림, 계산값)", dm.fmt_mm(b_ - a_))
    gy_all = [by1] + [y for y in sorted(ys, reverse=True) if by0 + 0.2 < y < by1 - 0.2] + [by0]
    gy = [v for v in gy_all if in_y(v)]
    seg_full_grid = list(zip(gy_all, gy_all[1:]))
    dm.chain_v(sh, [Y(v) for v in gy], Xl - 5.0, [dm.fmt_mm(a_ - b_) for a_, b_ in zip(gy, gy[1:])], from_x=Xl, pt=PT_DIM)
    meta["grid_chains"] += 1
    meta["chain_segments_printed"] += len(gy) - 1
    dm.dim_h(sh, X(bx0), X(bx1), Yt - 10.5, dm.fmt_mm(bx1 - bx0), from_y=Yt, pt=PT_DIM)               # 전체 폭
    fact("overall_w", "건물 전체 폭(가로)", int(dm.fmt_mm(bx1 - bx0)), "mm", cfg.MODEL_VERIFIED, "layout building 외곽 x1-x0", dm.fmt_mm(bx1 - bx0))
    if whole:
        dm.dim_v(sh, Yt, Yb, Xl - 10.5, dm.fmt_mm(by1 - by0), from_x=Xl, pt=PT_DIM)                    # 전체 깊이
        fact("overall_d", "건물 전체 깊이(세로)", int(dm.fmt_mm(by1 - by0)), "mm", cfg.MODEL_VERIFIED, "layout building 외곽 y1-y0", dm.fmt_mm(by1 - by0))
    else:
        yv0, yv1 = (by1, window[1]) if tile["index"] == 1 else (window[3], by0)
        ytop, ybot = max(yv0, yv1), min(yv0, yv1)
        ytop, ybot = min(ytop, by1), max(ybot, by0)
        half = by1 - tile["match_y"] if tile["index"] == 1 else tile["match_y"] - by0
        dm.dim_v(sh, Y(ytop), Y(ybot), Xl - 10.5, dm.fmt_mm(ytop - ybot) + " ▸", from_x=Xl, pt=PT_DIM)
        fact("overall_d_part", "이 장에 보이는 깊이 부분(전체 %s의 일부)" % dm.fmt_mm(by1 - by0), int(dm.fmt_mm(ytop - ybot)), "mm", cfg.DERIVED if hasattr(cfg, "DERIVED") else "DERIVED", "전체 깊이 중 창에 드는 부분(계산값)", dm.fmt_mm(ytop - ybot) + " ▸")
    meta["overall_chains"] += 2 if whole else 1
    # 튜브·캡슐 중심선 setout
    cen = []
    for it, g in cuts.get("tube_wall", []):
        nm = it["name_ko"]
        bb = g.bounds
        r = max(bb[2] - bb[0], bb[3] - bb[1]) / 2
        if r > 1.6 and ("T" in nm or "캡슐" in nm or "튜브" in nm):
            cen.append((nm, (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, r, bb))
    cen_w = [c for c in cen if fr.inside(c[1], c[2])]
    sx_all = sorted(set(round(v, 2) for v in [bx0] + legacy.uniq([c[1] for c in cen]) + [bx1]))
    sx = sorted(set(round(v, 2) for v in [bx0] + legacy.uniq([c[1] for c in cen_w]) + [bx1])) if cen_w else sx_all
    dm.chain_h(sh, [X(v) for v in sx], Yb + 6.0, [dm.fmt_mm(b_ - a_) for a_, b_ in zip(sx, sx[1:])], from_y=Yb, pt=PT_DIM)
    meta["setout_chains"] += 1
    meta["chain_segments_printed"] += len(sx) - 1
    sy_all = sorted(set(round(v, 2) for v in [by1] + legacy.uniq([c[2] for c in cen]) + [by0]), reverse=True)
    sy = [v for v in sorted(set(round(v, 2) for v in [by1] + legacy.uniq([c[2] for c in cen_w]) + [by0]), reverse=True) if in_y(v)]
    seg_full_set = list(zip(sy_all, sy_all[1:]))
    dm.chain_v(sh, [Y(v) for v in sy], Xr + 6.0, [dm.fmt_mm(a_ - b_) for a_, b_ in zip(sy, sy[1:])], from_x=Xr, left=False, pt=PT_DIM)
    meta["setout_chains"] += 1
    meta["chain_segments_printed"] += len(sy) - 1
    for a_, b_ in zip(sx, sx[1:]):
        fact("setout_x_%.2f" % a_, "튜브·캡슐 중심선 간격(가로)", int(dm.fmt_mm(b_ - a_)), "mm", cfg.MODEL_VERIFIED, "tube_wall 외곽 경계 중심 x 차", dm.fmt_mm(b_ - a_))
    for a_, b_ in zip(sy, sy[1:]):
        fact("setout_y_%.2f" % a_, "튜브·캡슐 중심선 간격(세로)", int(dm.fmt_mm(a_ - b_)), "mm", cfg.MODEL_VERIFIED, "tube_wall 외곽 경계 중심 y 차", dm.fmt_mm(a_ - b_))
    # 나눔 가로선: 쪼개진 구간이 두 장 중 한 곳에는 온전히 나오는지(타일 전용 검사에서 모음)
    chain_cover = {"grid_y": [(round(a_, 3), round(b_, 3)) for a_, b_ in zip(gy, gy[1:])], "grid_y_full": [(round(a_, 3), round(b_, 3)) for a_, b_ in seg_full_grid],
                   "setout_y": [(round(a_, 3), round(b_, 3)) for a_, b_ in zip(sy, sy[1:])], "setout_y_full": [(round(a_, 3), round(b_, 3)) for a_, b_ in seg_full_set]}

    # 주요 폭(파랑): 캡슐 폭, 가장 큰 튜브 지름 — 가구·튜브 선과 겹치지 않는 자리를 찾는다
    def band_free(x0_, x1_, y_, txt_w):
        fp = box(x0_ - 0.5, y_ - 1.2 - 2.9, x1_ + 0.5, y_ + 1.0)
        return fp, (not fp.intersects(occ_no_tube) and not any(fp.intersects(p) for p in placed))

    occ_no_tube = affine_transform(unary_union([g.buffer(BUF[k]) for k, g in occ_parts.items() if k not in ("tubes", "cores")]), fr.matrix)
    caps = [c for c in cen_w if "캡슐" in c[0]]
    big = sorted([c for c in cen_w if "캡슐" not in c[0]], key=lambda c: -c[3])[:2]
    for c in caps:
        bb = c[4]
        x0_, x1_ = X(bb[0]), X(bb[2])
        y_mid = Y((bb[1] + bb[3]) / 2)
        pick_y = None
        for off in [0] + [s * o for o in (1.5, 3.0, 4.5, 6.0, 7.5, 9.0, 11.0, 13.0, 15.0) for s in (1, -1)]:
            fp, ok = band_free(x0_, x1_, y_mid + off, 12)
            if ok:
                pick_y = y_mid + off
                break
        if pick_y is None:
            pick_y = y_mid
            meta["major_dims_on_occupied_spot"] += 1
        dm.dim_h(sh, x0_, x1_, pick_y, dm.fmt_mm(bb[2] - bb[0]), pt=PT_DIM, color="#06a")
        placed.append(box(x0_ - 0.5, pick_y - 4.0, x1_ + 0.5, pick_y + 1.0))
        meta["major_dims"] += 1
        fact("cap_w_%s" % c[0], "%s 폭" % c[0], int(dm.fmt_mm(bb[2] - bb[0])), "mm", cfg.MODEL_VERIFIED, "tube_wall %s 외곽 폭" % c[0], dm.fmt_mm(bb[2] - bb[0]))
    for c in big:
        bb = c[4]
        x0_, x1_ = X(bb[0]), X(bb[2])
        y_bot = Y(bb[1])
        pick_y = None
        for off in (3.0, 4.5, 6.0, 7.5, 9.0, -(Y(bb[3]) - Y(bb[1])) - 3.0, -(Y(bb[3]) - Y(bb[1])) - 5.0):
            yy = y_bot + off
            fp = box(x0_ - 0.5, yy - 4.0, x1_ + 0.5, yy + 1.0)
            if fp.intersects(occ_no_tube) or any(fp.intersects(p) for p in placed):
                continue
            if not box(win_rect[0], win_rect[1], win_rect[2], win_rect[3]).contains(fp):
                continue
            pick_y = yy
            break
        if pick_y is None:
            pick_y = y_bot + 3.0
            meta["major_dims_on_occupied_spot"] += 1
        dm.dim_h(sh, x0_, x1_, pick_y, "Ø" + dm.fmt_mm(bb[2] - bb[0]), pt=PT_DIM, color="#06a")
        placed.append(box(x0_ - 0.5, pick_y - 4.0, x1_ + 0.5, pick_y + 1.0))
        meta["major_dims"] += 1
        fact("tube_d_%s" % c[0], "%s 지름" % c[0], int(dm.fmt_mm(bb[2] - bb[0])), "mm", cfg.MODEL_VERIFIED, "tube_wall %s 외곽 지름" % c[0], "Ø" + dm.fmt_mm(bb[2] - bb[0]))

    # ── 단면 절단선·기호: 가구·기둥·튜브 위가 아닌 빈자리 ───────────────────────────────────────
    sec_geoms = []
    sec_list = regs["sections"]["sections"]
    for s in sec_list:
        (ax0, ay0), (ax1, ay1) = s["line_drawing_frame"]
        horizontal = abs(ay1 - ay0) < 1e-6
        if horizontal:
            p0, p1 = (bx0 + 2.5, ay0), (bx1 - 2.5, ay1)
        else:
            p0, p1 = (ax0, by0 + 2.5), (ax1, by1 - 2.5)
        lk = s["view_direction_drawing_frame"]
        arrow = (lk[0], -lk[1])
        ref = s["sheet"]
        line_sheet = LineString([(X(p0[0]), Y(p0[1])), (X(p1[0]), Y(p1[1]))])
        ends = []
        for end_i, (pa, pb) in enumerate(((p0, p1), (p1, p0))):
            ax_, ay_ = X(pa[0]), Y(pa[1])
            bx_, by_ = X(pb[0]), Y(pb[1])
            L_ = math.hypot(bx_ - ax_, by_ - ay_)
            ux, uy = ((bx_ - ax_) / L_, (by_ - ay_) / L_) if L_ else (0.0, 0.0)
            if not fr.inside(*pa):
                ends.append(None)                                            # 이 끝은 이 장(창) 밖: 기호는 이웃 장에
                continue
            pick = None
            for t in [i * 1.0 for i in range(0, 60)]:                        # 끝에서 안쪽으로 1 mm씩
                cx_, cy_ = ax_ + ux * t, ay_ + uy * t
                fp = section_tag_fp(meter, cx_, cy_, arrow[1], arrow[0], ref)
                if free(fp):
                    pick = (cx_, cy_, fp)
                    break
            if pick is None:
                cx_, cy_ = ax_, ay_
                pick = (cx_, cy_, section_tag_fp(meter, cx_, cy_, arrow[1], arrow[0], ref))
                meta["tags_on_occupied_spot"] += 1
            placed.append(pick[2])
            ends.append(pick)
        # 선: 이 창 안의 구간만, 두 기호 사이(창 밖으로 이어지면 창 가장자리까지)
        seg = line_sheet.intersection(box(*win_rect))
        pts = []
        for e in ends:
            if e:
                pts.append((e[0], e[1]))
        if seg.is_empty:
            continue
        sx0, sy0, sx1, sy1 = list(seg.coords)[0] + list(seg.coords)[-1]
        a_pt = ends[0][:2] if ends[0] else (sx0, sy0)
        b_pt = ends[1][:2] if ends[1] else (sx1, sy1)
        sh.line(a_pt[0], a_pt[1], b_pt[0], b_pt[1], 0.2, "#c00", "7,1.6,1.2,1.6")
        placed.append(LineString([a_pt, b_pt]).buffer(0.6))
        for e in ends:
            if e:
                draw_section_tag(sh, e[0], e[1], s["name"][0], ref, arrow)
                meta["section_tags"] += 1
        sec_geoms.append((s["name"], ref))

    # ── 입면 기호 ────────────────────────────────────────────────────────────────────────────────
    vlines = [sec["plane"]["value_drawing_frame"] for sec in sec_list if sec["plane"]["axis"] == "x"]
    hlines = [sec["plane"]["value_drawing_frame"] for sec in sec_list if sec["plane"]["axis"] == "y"]

    def edge_candidates(nm):
        fr_list = (0.30, 0.70, 0.22, 0.78, 0.38, 0.62, 0.15, 0.85, 0.5)
        ins_list = (5.0, 4.0, 6.0, 3.2, 7.0, 8.0)
        for ins in ins_list:
            for f_ in fr_list:
                if nm == "N":
                    yield (bx1 - ins, by0 + (by1 - by0) * f_), (1, 0)
                elif nm == "S":
                    yield (bx0 + ins, by0 + (by1 - by0) * f_), (-1, 0)
                elif nm == "E":
                    yield (bx0 + (bx1 - bx0) * f_, by0 + ins), (0, 1)
                else:
                    yield (bx0 + (bx1 - bx0) * f_, by1 - ins), (0, -1)

    for nm in ("N", "S", "E", "W"):
        ref = next(e["sheet"] for e in regs["elev"]["elevations"] if e["name"] == nm)
        chosen = None
        anchor_in_win = [(p, d) for p, d in edge_candidates(nm) if fr.inside(*p)]
        if not anchor_in_win:
            continue                                                         # 이 입면 기호의 변은 이 장 창 밖
        for (px_, py_), d in anchor_in_win:
            if any(abs(px_ - v) < 4.0 for v in vlines if nm in ("E", "W")) or any(abs(py_ - v) < 4.0 for v in hlines if nm in ("N", "S")):
                continue
            fp = elev_tag_fp(meter, X(px_), Y(py_), d, ref)
            if free(fp):
                chosen = ((px_, py_), d, fp)
                break
        if chosen is None:
            (px_, py_), d = anchor_in_win[0]
            chosen = ((px_, py_), d, elev_tag_fp(meter, X(px_), Y(py_), d, ref))
            meta["tags_on_occupied_spot"] += 1
        placed.append(chosen[2])
        draw_elev_tag(sh, X(chosen[0][0]), Y(chosen[0][1]), ref, chosen[1])
        meta["elevation_tags"] += 1

    # ── 상세 호출: 대상 둘레 점선 원 + 빈자리의 기호(+지시선). 축척 문자는 dm.detail_tag(registry) ────────────────
    callouts = {"3F": [("D-401", "A-CORE-TUBE_T1"), ("D-402", "A-CORE-TUBE_T2"), ("D-403", "A-CORE-TUBE_T3"), ("D-405", "A-CORE-TUBE_capW")],
                "8F": [("D-407", None)], "15F": [("D-410", "A-ROOF_rescue_pad")]}
    used_callouts = []
    detail_info = []
    for sid_d, oname in callouts.get(floor, []):
        if oname is None:
            es = [o for o in model.objects if o["name"].startswith("A-VERT-ESCL_8F-9F")]
            pts = []
            for o in es:
                T = model.tris(o).reshape(-1, 3)
                pts += [(T[:, 0].min(), T[:, 1].min()), (T[:, 0].max(), T[:, 1].max())]
            ex, ey = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2, (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
            er = max(max(p[0] for p in pts) - min(p[0] for p in pts), max(p[1] for p in pts) - min(p[1] for p in pts)) / 2
        else:
            ex, ey, er = legacy.obj_center_r(model, oname)
        if not fr.inside(ex, ey):
            continue                                                         # 이 장 창 밖의 대상: 이웃 장에서 호출
        cxs, cys = X(ex), Y(ey)
        dr = max(er, 2.0) * K * 0.55
        sh.path([_circle(cxs, cys, dr, 28)], stroke="#a60", w=0.25, dash="1.6,1.0", closed=True)
        found = None
        rin = er * K + 6.0
        for rho in [rin + 1.5 * i for i in range(0, 24)]:
            for ang in (45, 135, -45, -135, 90, 0, 180, -90, 20, 70, 110, 160, -20, -70, -110, -160):
                a_ = math.radians(ang)
                bxx, byy = cxs + rho * math.cos(a_), cys - rho * math.sin(a_)
                fp = detail_tag_fp(meter, bxx, byy, sid_d)
                if free(fp):
                    found = (bxx, byy, fp, a_)
                    break
            if found:
                break
        if found is None:
            a_ = math.radians(45)
            found = (cxs + (dr + 6) * math.cos(a_), cys - (dr + 6) * math.sin(a_), None, a_)
            found = (found[0], found[1], detail_tag_fp(meter, found[0], found[1], sid_d), a_)
            meta["tags_on_occupied_spot"] += 1
        bxx, byy, fp, a_ = found
        sh.line(cxs + dr * math.cos(a_), cys - dr * math.sin(a_), bxx - 3.4 * math.cos(a_), byy + 3.4 * math.sin(a_), 0.2, "#a60")
        dm.detail_tag(_NoBg(sh), bxx - 3.4, byy + 3.4, sid_d)              # 기호 중심 = (x+3.4, y-3.4): 축척 문자는 레지스트리
        placed.append(fp)
        placed.append(LineString([(cxs + dr * math.cos(a_), cys - dr * math.sin(a_)), (bxx, byy)]).buffer(0.5))
        used_callouts.append(sid_d)
        detail_info.append({"sheet": sid_d, "target": oname or "A-VERT-ESCL_8F-9F*", "center_m": [round(ex, 2), round(ey, 2)], "label": registry.callout_label(sid_d)})
        meta["detail_callouts"] += 1

    # ── 타일 전용: 겹침 구간, MATCH LINE, 등록 표식 ──────────────────────────────────────────────
    reg_marks = []
    if tile:
        ym = tile["match_y"]
        o0, o1 = tile["overlap"]
        yl_a, yl_b = Y(o1), Y(o0)
        # 겹침 구간: 아주 옅은 띠(이웃 장과 같은 내용이 나오는 곳)
        sh.parts.append('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="#dfe8f5" fill-opacity="0.22"/>' % (win_rect[0], yl_a, win_rect[2] - win_rect[0], yl_b - yl_a))
        sh.line(win_rect[0], yl_a, win_rect[2], yl_a, 0.15, "#6a8cc0", "3,1.5")
        sh.line(win_rect[0], yl_b, win_rect[2], yl_b, 0.15, "#6a8cc0", "3,1.5")
        sh.line(win_rect[0], Y(ym), win_rect[2] + 3.0, Y(ym), 0.45, "#000", "9,1.6,1.4,1.6")
        mz = lay["match_zone"]
        yml = Y(ym)
        arrow_dir = -1 if tile["index"] == 1 else 1             # 1번 장은 이웃이 아래, 2번 장은 위
        sh.text(mz[0] + 4.0, yml - 1.2, "MATCH LINE", 7.0, "bold", "#000")
        sh.text(mz[0] + 4.0, yml + 3.0, "격자 %s–%s 사이" % (yl[round(tile["rows_pair"][0], 2)] if round(tile["rows_pair"][0], 2) in yl else "?", yl[round(tile["rows_pair"][1], 2)] if round(tile["rows_pair"][1], 2) in yl else "?"), 6.0, "normal", "#333")
        sh.text(mz[0] + 4.0, yml + 6.6, ("▼ " if arrow_dir > 0 else "▲ ") + tile["other"], 7.0, "bold", "#000")
        sh.text(mz[0] + 4.0, yml + 10.2, "에 이어짐", 6.0, "normal", "#333")
        sh.claim("match_label", mz[0] + 2.0, yml - 4.5, mz[2], yml + 11.5)
        # 겹침 구간 표지(창 안쪽 가장자리에 붙여 글자를 놓는다: 이웃 장 번호)
        sh.text(win_rect[0] + 1.5, (yl_a if tile["index"] == 2 else yl_b) + (-1.2 if tile["index"] == 1 else 3.0) * (1 if tile["index"] == 2 else 1), "", 6.0)
        # 등록 표식 R1~R3: 가로 격자 A·D·G(맨 왼·가운데·맨 오른쪽 열)와 쪼갬선에 가장 가까운 행의 교점 → 두 장에서 같은 모델 좌표
        rows_pair = tile["rows_pair"]
        ry = rows_pair[0] if abs(rows_pair[0] - ym) <= abs(rows_pair[1] - ym) else rows_pair[1]
        # 외곽 축선은 도면 창 여백에 걸려 한쪽 타일에서 빠질 수 있다. 두 타일의
        # 공통 창 안에 실제로 들어오는 축선만 고른 뒤 좌·중·우 세 점을 쓴다.
        # 따라서 registry에도 R1~R3가 두 장 모두 같은 모델 좌표로 남는다.
        # 두 창은 공통 축선을 경계에서 0.5 m씩 더 품도록 정의되어 있으므로
        # 0.2 m 안전 여백을 쓴다(1.0 m이면 한쪽 창의 공통 행 자체가 탈락한다).
        cols_sorted = [cx_ for cx_ in sorted(xs) if fr.inside(cx_, ry, pad=0.2)]
        if len(cols_sorted) < 3:
            raise LayoutConflict("%s: 공통 겹침 구간 안에 정합 표식용 축선이 3개 미만" % sid)
        pick_cols = [cols_sorted[0], cols_sorted[len(cols_sorted) // 2], cols_sorted[-1]]
        for i_, cx_ in enumerate(pick_cols):
            px_, py_ = X(cx_), Y(ry)
            sh.path([_circle(px_, py_, 2.8, 24)], stroke="#b0007a", w=0.25, closed=True)
            sh.line(px_ - 4.2, py_, px_ + 4.2, py_, 0.2, "#b0007a")
            sh.line(px_, py_ - 4.2, px_, py_ + 4.2, 0.2, "#b0007a")
            sh.text(px_ + 3.4, py_ - 3.0, "R%d" % (i_ + 1), 6.0, "bold", "#b0007a")
            reg_marks.append({"id": "R%d" % (i_ + 1), "model_xy_m": [round(cx_, 3), round(ry, 3)], "grid": "%s/%s" % (xl.get(round(cx_, 2), "?"), yl.get(round(ry, 2), "?")), "sheet_xy_mm": [round(px_, 3), round(py_, 3)]})

    # ── 범례·주기 블록 ───────────────────────────────────────────────────────────────────────────
    legend = chk.get("legend", {})
    areas = {}
    for z in sl["zones"]:
        g = pc.polygons_from_segments(z["segments"])
        areas[z["name_ko"]] = areas.get(z["name_ko"], 0.0) + g.area

    def num_sym(no):
        def _d(sh_, x_, yc_):
            sh_.path([_circle(x_ + 3.0, yc_, 2.4, 24)], fill="#fff", stroke="#666", w=0.2, closed=True)
            sh_.text(x_ + 3.0, yc_ + 0.9, str(no), 7.0, "bold", "#222", "middle")
        return _d

    blk_legend = Block().head("범례  LEGEND")
    legend_rows = []
    for no in sorted(legend, key=lambda k_: int(k_)):
        nm = legend[no]
        a = ""
        for zn, ar in areas.items():
            if (nm == "시장 홀" and ("판매" in zn or "시장" in zn)) or (nm == "F&B 구역" and "F&B" in zn) or (nm == "문화·엔터 구역" and ("문화" in zn or "엔터" in zn)) or (nm == "정원·테라스" and "garden" in zn.lower()):
                a = "  %s ㎡" % format(int(round(ar)), ",")
                fact("area_%s" % no, "%s 구획 면적(폴리곤 계산값)" % nm, int(round(ar)), "㎡", cfg.MODEL_VERIFIED, "slice zone 폴리곤 shapely area (%s)" % zn, "%s ㎡" % format(int(round(ar)), ","))
        blk_legend.item(num_sym(no), nm + a, sw=7.5)
        legend_rows.append((no, nm + a))

    def s_col(sh_, x_, yc_):
        sh_.path([_circle(x_ + 3.0, yc_, 1.3, 20)], fill="#000", stroke="#000", w=0.2, closed=True)

    def s_col_dash(sh_, x_, yc_):
        sh_.path([_circle(x_ + 3.0, yc_, 1.3, 20)], stroke="#666", w=0.2, dash="0.9,0.7", closed=True)

    def s_furn(sh_, x_, yc_):
        sh_.path([[(x_ + 0.6, yc_ - 1.2), (x_ + 5.4, yc_ - 1.2), (x_ + 5.4, yc_ + 1.2), (x_ + 0.6, yc_ + 1.2)]], fill="#fff", stroke="#666", w=0.15)

    def s_counter(sh_, x_, yc_):
        sh_.path([[(x_ + 0.6, yc_ - 1.2), (x_ + 5.4, yc_ - 1.2), (x_ + 5.4, yc_ + 1.2), (x_ + 0.6, yc_ + 1.2)]], fill="#D9D9D9", stroke="#444", w=0.2)

    def s_zone(sh_, x_, yc_):
        sh_.path([[(x_ + 0.6, yc_ - 1.4), (x_ + 5.4, yc_ - 1.4), (x_ + 5.4, yc_ + 1.4), (x_ + 0.6, yc_ + 1.4)]], stroke="#666", w=0.15, dash="0.9,0.7")

    def s_route_v(sh_, x_, yc_):
        sh_.line(x_ + 0.3, yc_, x_ + 5.7, yc_, 0.2, "#666", "2.4,0.9")

    def s_route_o(sh_, x_, yc_):
        sh_.line(x_ + 0.3, yc_, x_ + 5.7, yc_, 0.15, "#999", "1.8,0.6,0.4,0.6")

    def s_tube(sh_, x_, yc_):
        sh_.path([_circle(x_ + 3.0, yc_, 2.5, 24)], stroke="#000", w=0.3, closed=True)
        sh_.path([_circle(x_ + 3.0, yc_, 1.9, 24)], stroke="#222", w=0.15, closed=True)
        sh_.path([[(x_ + 2.0, yc_ - 1.0), (x_ + 4.0, yc_ - 1.0), (x_ + 4.0, yc_ + 1.0), (x_ + 2.0, yc_ + 1.0)]], stroke="#444", w=0.15)
        sh_.line(x_ + 2.0, yc_ - 1.0, x_ + 4.0, yc_ + 1.0, 0.1, "#777")
        sh_.line(x_ + 4.0, yc_ - 1.0, x_ + 2.0, yc_ + 1.0, 0.1, "#777")

    def s_axis(sh_, x_, yc_):
        dm.bubble(sh_, x_ + 3.0, yc_, "A", r=2.4, pt=6.0)

    def s_sec(sh_, x_, yc_):
        dm.bubble(sh_, x_ + 3.0, yc_, "A", r=2.4, pt=6.0, color="#c00")

    def s_elev(sh_, x_, yc_):
        dm.bubble(sh_, x_ + 3.0, yc_, "1", r=2.4, pt=6.0, color="#06a")

    def s_det(sh_, x_, yc_):
        dm.bubble(sh_, x_ + 3.0, yc_, "D", r=2.4, pt=6.0, color="#a60")

    def s_reg(sh_, x_, yc_):
        sh_.path([_circle(x_ + 3.0, yc_, 2.0, 20)], stroke="#b0007a", w=0.2, closed=True)
        sh_.line(x_ + 0.6, yc_, x_ + 5.4, yc_, 0.15, "#b0007a")
        sh_.line(x_ + 3.0, yc_ - 2.4, x_ + 3.0, yc_ + 2.4, 0.15, "#b0007a")

    blk_sym = Block().head("기호").item(s_col, "구조 기둥(모델 기둥, 실선)").item(s_col_dash, "점선 원 = 코어 인접 모델 기둥(1층 규칙상 생략 대상)")
    blk_sym.item(s_furn, "흰 사각 = 가구 (CONCEPT PROPOSED)").item(s_counter, "회색 채움 = 계산대·카운터 (CONCEPT PROPOSED)").item(s_zone, "점선 사각 = 바닥 표시 구역 (CONCEPT PROPOSED)")
    blk_sym.item(s_route_v, "긴 점선 = 방문자 동선 (CONCEPT PROPOSED)").item(s_route_o, "일점쇄선 = 운영 동선 (CONCEPT PROPOSED)").item(s_tube, "이중 원 = 튜브 · 안의 사각 = 승강로")
    blk_sym.item(s_axis, "구조 축선(알파벳 가로 · 숫자 세로), 치수 mm")
    blk_ref = Block().head("참조 기호").item(s_sec, "단면 절단선 — 단면 시트 S-302 ~ 305, 키플랜 S-301", color="#c00").item(s_elev, "입면 방향 — E-201 북 · 202 동 · 203 남 · 204 서", color="#06a")
    blk_ref.item(s_det, "상세 호출 — 점선 원이 대상, 지시선 끝의 기호가 상세 시트 D-4xx (축척은 시트 번호 옆)", color="#a60")
    if tile:
        blk_ref.item(s_reg, "등록 표식 R1~R3 — 이웃 장과 같은 모델 좌표(격자 교점). 겹쳐 맞출 때 쓴다")

    strat = []
    for pnm in dict.fromkeys(progs):
        if "판매" in pnm or "시장" in pnm:
            strat.append(legacy.STRATEGY["판매_A"] if floor in ("2F", "3F", "4F", "5F", "B1", "B2") else legacy.STRATEGY["판매_B"])
        elif "F&B" in pnm:
            strat.append(legacy.STRATEGY["F&B"])
        elif "문화" in pnm or "엔터" in pnm:
            strat.append(legacy.STRATEGY["문화"])
        elif "garden" in pnm.lower():
            strat.append(legacy.STRATEGY["garden"])
    blk_strat = Block().head("가구·프로그램 배치").badge(STATUS_CP, "제안일 뿐 시공 사실이 아니다(PROPOSED_ONLY)")
    for t_ in strat:
        blk_strat.para(t_, pt=PT_NOTE - 0.5, color="#333")
    rel = [("단면", "S-301 키플랜 · S-302 A–A · S-303 B–B · S-304 C–C · S-305 D–D"), ("입면", "E-201 북 · E-202 동 · E-203 남 · E-204 서"),
           ("상세", " · ".join(used_callouts) if used_callouts else "이 장에 호출된 상세 없음"), ("배치", "A-003 배치도 · A-901 층별 표 · A-902 층별 일람")]
    if role == "overview":
        rel.append(("1:200 평면", "A1 1:200 전체 P-201(3F)·P-202(13F) · A3 1:200 분할 P-211~214"))
    if role == "tile":
        rel.append(("이웃 장", "%s — MATCH LINE에서 이어 붙임. 같은 층의 A1 전체 평면은 P-20x" % tile["other"]))
    blk_rel = Block().head("관련 시트")
    for k_, t_ in rel:
        blk_rel.para("%s  %s" % (k_, t_), pt=PT_NOTE - 0.5, color="#333")
    blk_stat = Block().head("상태·한계")
    blk_stat.badge(STATUS_MV, "기둥·튜브·코어·캡슐 윤곽, 축선·치수(모델 좌표에서 계산, 10 mm 반올림)")
    blk_stat.badge(STATUS_CP, "가구·식재·동선·구역 표시·프로그램 배치(PROPOSED_ONLY)")
    blk_stat.badge(STATUS_UR, "상층 구획벽·문·화장실·피난 경로: 모델에 없어 그리지 않음")
    blk_stat.para("LEVEL S: 구조·프로그램 볼륨만 모델에 있음. 최종 FREEZE 아님(후보 %s)." % cfg.EDITION, pt=PT_NOTE - 0.5, color="#444", bullet="·")
    if len(applies) > 1:
        pr = next((p for h in evidence["hypothesis_groups"] for p in h["pairs"] if set(p["pair"].split("~")) == set(applies[:2])), None)
        blk_stat.para("적용 층 %s: 수직동선 개구만 다름(검증됨), EQUIVALENCE VERIFIED 아님." % "·".join(applies), pt=PT_NOTE - 0.5, color="#444", bullet="·")
        deltas = []
        if pr:
            for kind, label in (("stair", "에스컬레이터"), ("shaft", "승강기 샤프트")):
                for ff in applies[:2]:
                    other = [a for a in applies[:2] if a != ff][0]
                    pts_ = pr["vertical_elements"][kind][ff]
                    op = pr["vertical_elements"][kind][other]
                    only = [p for p in pts_ if all(abs(p[0] - q[0]) > 0.5 or abs(p[1] - q[1]) > 0.5 for q in op)]
                    if only:
                        deltas.append("%s %s 고유 %d" % (ff, label, len(only)))
        if deltas:
            blk_stat.para("개구 차이: " + " · ".join(deltas) + " (A-902 붉은 부분)", pt=PT_NOTE - 0.5, color="#444", bullet="·")
    for t_ in extra_notes:
        blk_stat.para(t_, pt=PT_NOTE - 0.5, color="#444", bullet="·")
    blk_dimnote = Block().head("치수열").para("위: 축선 간격(mm)과 전체 폭 · 왼쪽: 축선 간격" + (" · 전체 깊이" if whole else "(이 장에 보이는 부분)") + " · 오른쪽·아래: 튜브·캡슐 중심선 사이 setout. 파란 치수는 캡슐 폭·튜브 지름.",
                                          pt=PT_NOTE - 0.5, color="#333")
    if role == "overview":
        blk_dimnote.para("※ A3 1:250 = 개요(OVERVIEW). 1:200 평면이 아니다.", pt=PT_NOTE - 0.5, color="#a33", bold=True)

    panel_info = {}
    gdraw_after = []                                       # (x, y) 방위·축척 막대 위치
    bar_xy = (0, 0)
    bar_meters = None
    north_xy = (0, 0)
    if role == "overview":
        px0_, py0_, px1_, py1_ = lay["panel"]
        sh.path([[(px0_, py0_), (px1_, py0_), (px1_, py1_), (px0_, py1_)]], fill="#fff", stroke="#555", w=0.3)
        # Keep true north in its own top strip.  The former bottom-right location
        # overlapped both the physical scale bar and the OVERVIEW warning on A3.
        inner_rect = (px0_ + 4.0, py0_ + 32.0, px1_ - 4.0, py1_ - 32.0)
        # Basement/program-rich floors can produce a longer strategy note than
        # the A3 side panel.  Measure before drawing (retrying after a partial
        # draw would duplicate text) and keep truth/status/legend first.
        essentials = [blk_legend, blk_sym, blk_ref, blk_stat]
        optionals = [blk_dimnote, blk_strat, blk_rel]
        blocks = essentials[:-1]
        panel_w = inner_rect[2] - inner_rect[0]
        panel_h = inner_rect[3] - inner_rect[1]
        used_h = sum(b.height(panel_w) for b in essentials)
        for b_ in optionals:
            h_ = b_.height(panel_w)
            if used_h + h_ <= panel_h:
                blocks.append(b_)
                used_h += h_
        blocks.append(blk_stat)
        panel_info = place_blocks(sh, blocks, inner_rect, 1, name="panel_text")
        bar_xy = (px0_ + 9.0, py1_ - 21.0)
        north_xy = (px1_ - 16.0, py0_ + 15.0)
    elif role == "full":
        px0_, py0_, px1_, py1_ = lay["panel"]
        sh.path([[(px0_, py0_), (px1_, py0_), (px1_, py1_), (px0_, py1_)]], fill="#fff", stroke="#555", w=0.3)
        inner_rect = (px0_ + 6.0, py0_ + 6.0, px1_ - 6.0, py1_ - 40.0)
        blocks = [blk_legend, blk_sym, blk_ref, blk_dimnote, blk_strat, blk_rel, blk_stat]
        panel_info = place_blocks(sh, blocks, inner_rect, 2, gap=8.0, name="panel_text")
        bar_xy = (px0_ + 12.0, py1_ - 24.0)
        north_xy = (px1_ - 20.0, py1_ - 24.0)
    else:
        rx0, ry0, rx1, ry1 = lay["right"]
        bx0b, by0b, bx1b, by1b = lay["band"]
        band_h = by1b - by0b
        # 타일 키(오른쪽 위)
        key_w = rx1 - rx0
        kx0, ky0 = rx0, ry0
        sh.text(kx0, ky0 + 3.0, "타일 키  %s" % tile["id"], 8.0, "bold", "#111")
        scale_k = (key_w - 4.0) / ((bx1 - bx0) + 2.0)
        kh = (by1 - by0) * scale_k
        kox, koy = kx0 + 2.0, ky0 + 7.0

        def KX(x):
            return kox + (x - bx0) * scale_k

        def KY(y):
            return koy + (by1 - y) * scale_k
        sh.path([[(KX(bx0), KY(by1)), (KX(bx1), KY(by1)), (KX(bx1), KY(by0)), (KX(bx0), KY(by0))]], stroke="#555", w=0.25)
        for t_ in (tile, tile_other(tile, bounds=(bx0, by0, bx1, by1), rows=ys, ids=(tile["id"], tile["other"]))):
            w_ = t_["window"]
            cur = t_["index"] == tile["index"]
            ww_ = [(KX(max(w_[0], bx0)), KY(min(w_[3], by1))), (KX(min(w_[2], bx1)), KY(min(w_[3], by1))), (KX(min(w_[2], bx1)), KY(max(w_[1], by0))), (KX(max(w_[0], bx0)), KY(max(w_[1], by0)))]
            sh.path([ww_], fill="#8aa6d6" if cur else "none", stroke="#27457a" if cur else "#8a8a8a", w=0.3 if cur else 0.2, opacity=0.45 if cur else None, dash=None if cur else "1.6,1.0")
            sh.text((ww_[0][0] + ww_[1][0]) / 2, (ww_[0][1] + ww_[3][1]) / 2 + (-2.6 if t_["index"] == 1 else 4.0) * (0.0 if False else 1.0) + 0.9, "%s" % ("1" if t_["index"] == 1 else "2"), 8.0, "bold", "#111", "middle")
        for x in xs:
            sh.line(KX(x), KY(by1), KX(x), KY(by0), 0.05, "#bbb")
        for y in ys:
            sh.line(KX(bx0), KY(y), KX(bx1), KY(y), 0.05, "#bbb")
        sh.line(KX(bx0), KY(tile["match_y"]), KX(bx1), KY(tile["match_y"]), 0.3, "#000", "2.4,0.8,0.4,0.8")
        sh.text(kx0, koy + kh + 4.6, "진한 색 = 이 장 · 점선 = 이웃 장", 6.0, "normal", "#444")
        sh.text(kx0, koy + kh + 8.2, "굵은 점선 = MATCH LINE", 6.0, "normal", "#444")
        sh.claim("tile_key", kx0, ky0, rx1, koy + kh + 10.0)
        y_after_key = koy + kh + 14.0
        # 등록 표식 표
        blk_reg = Block().head("등록 표식 (모델 좌표)", pt=8.0)
        for rm in reg_marks:
            blk_reg.para("%s  격자 %s · x %.2f · y %.2f m" % (rm["id"], rm["grid"], rm["model_xy_m"][0], rm["model_xy_m"][1]), pt=6.5, color="#b0007a")
        blk_reg.para("두 장에서 같은 좌표. 겹쳐 맞출 때 표식 중심을 일치시킨다.", pt=6.5, color="#444")
        blk_sc = Block()
        regh = blk_reg.height(key_w)
        blk_reg.run(sh, rx0, y_after_key, key_w)
        sh.claim("reg_table", rx0, y_after_key, rx1, y_after_key + regh)
        north_xy = (rx1 - 16.0, y_after_key + regh + 14.0)
        sh.north_arrow(north_xy[0], north_xy[1], model.north_deg, r=4.8)
        sh.text(north_xy[0], north_xy[1] + 10.0, "진북 %.1f°" % model.north_deg, 6.0, "normal", "#444", "middle")
        sh.claim("north", north_xy[0] - 9.0, north_xy[1] - 12.0, north_xy[0] + 9.0, north_xy[1] + 11.5)
        # 하단 띠의 높이는 두 타일에서 서로 다르다. 특히 2번 타일은 약 35 mm뿐이므로
        # 긴 문장 블록을 억지로 넣지 않고, 양쪽 장에 같은 압축 범례를 물리 좌표로 그린다.
        sh.text(bx0b + 2.0, by0b + 5.0, "범례  LEGEND", 7.0, "bold", "#111")
        nleg = max(1, len(legend_rows))
        leg_x0 = bx0b + 2.0
        leg_y = by0b + 12.0
        leg_w = (bx1b - bx0b - 4.0) / nleg
        for i_, (no, t_) in enumerate(legend_rows):
            lx = leg_x0 + i_ * leg_w
            num_sym(no)(sh, lx, leg_y)
            sh.text(lx + 7.0, leg_y + 0.8, t_, 6.0, "normal", "#333")
        sh.text(bx0b + 2.0, leg_y + 8.0,
                "실선=MODEL VERIFIED · 회색/점선 가구·구역=CONCEPT PROPOSED · R1~R3=정합 표식",
                6.0, "normal", "#444")
        sh.claim("tile_legend", bx0b, by0b, bx1b, min(by1b, leg_y + 12.0))

        # 상세한 상태·참조는 고정 폭 오른쪽 칸에 두어 1:200 도면 창과 범례를 침범하지 않는다.
        info_y = north_xy[1] + 17.0
        blk_tile = Block().head("상태·참조", pt=8.0)
        blk_tile.badge(STATUS_MV, "모델 윤곽·축선·치수")
        blk_tile.badge(STATUS_CP, "가구·프로그램 표시")
        blk_tile.badge(STATUS_UR, "미모델 벽·문·피난")
        blk_tile.para("MATCH LINE → %s · A1 전체 %s" % (tile["other"], "P-201" if floor == "3F" else "P-202"), pt=6.0, color="#333")
        blk_tile.para("단면 S-301~305 · 입면 E-201~204", pt=6.0, color="#333")
        blk_tile.para("상세 %s" % (" · ".join(used_callouts) if used_callouts else "호출 없음"), pt=6.0, color="#333")
        info_h = blk_tile.height(key_w)
        if info_y + info_h > ry1 - 23.0:
            raise LayoutConflict("tile: 오른쪽 상태·참조 칸이 넘친다(%.1f > %.1f mm)" % (info_y + info_h, ry1 - 23.0))
        blk_tile.run(sh, rx0, info_y, key_w)
        sh.claim("tile_info", rx0, info_y, rx1, info_y + info_h)
        panel_info = {"tile_info": [round(rx0, 3), round(info_y, 3), round(rx1, 3), round(info_y + info_h, 3)]}
        bar_xy = (rx0 + 4.0, ry1 - 10.0)
        bar_meters = [0, 2, 5]

    # ── 방위 · 축척 막대(표준 Sheet.scale_bar: 벡터 실측 대상) ─────────────────────────────────────
    sh.scale_bar(bar_xy[0], bar_xy[1], meters=bar_meters)
    if role != "tile":
        sh.north_arrow(north_xy[0], north_xy[1], model.north_deg, r=4.8)
        sh.text(north_xy[0], north_xy[1] + 10.5, "진북 %.1f°" % model.north_deg, 6.0, "normal", "#444", "middle")
        sh.claim("north", north_xy[0] - 9.0, north_xy[1] - 12.0, north_xy[0] + 9.0, north_xy[1] + 12.5)
    if role == "overview":
        sh.text(bar_xy[0], bar_xy[1] + 10.5, "OVERVIEW 1:%d — 1:200 평면이 아님" % scale, 6.0, "bold", "#a33")
        sh.claim("overview_note", bar_xy[0] - 3.0, bar_xy[1] + 7.5, bar_xy[0] + 85.0, bar_xy[1] + 11.5)
    sh.title_block()

    # ── 저장 ─────────────────────────────────────────────────────────────────────────────────────
    os.makedirs(out_dir, exist_ok=True)
    tagname = file_tag or {"overview": "plan_%s" % floor, "full": "plan_%s_A1_1to%d" % (floor, scale), "tile": "plan_%s_tile%d_1to%d" % (floor, tile["index"] if tile else 0, scale)}[role]
    base = os.path.join(out_dir, "%s_%s" % (sid, tagname))
    pw = png_width or int(round(paper[0] / 25.4 * (150 if paper[0] > 500 else 300)))
    sh.save(base, png_width=pw)
    res = {"sheet": sid, "floor": floor, "applies_to": applies, "scale": "1:%d" % scale, "role": role, "paper": list(paper), "meta": meta, "furniture_count": chk.get("furniture_items"),
           "legend": legend, "callouts": used_callouts, "detail_callouts": detail_info, "axes": {"x": len(xs), "y": len(ys), "x_labels": axis_facts["cols"], "y_labels": axis_facts["rows"]},
           "window_m": [round(v, 4) for v in window], "building_m": [round(v, 4) for v in (bx0, by0, bx1, by1)], "K_mm_per_m": K,
           "frame": {"px0": lay["px0"], "py0": lay["py0"], "matrix": fr.matrix, "plan_rect_mm": [round(v, 3) for v in win_rect]},
           "plan_size_mm": [round((window[2] - window[0]) * K, 2), round((window[3] - window[1]) * K, 2)], "panel": panel_info, "chain_cover": chain_cover,
           "registration_marks": reg_marks, "tile": ({k: (list(v) if isinstance(v, tuple) else v) for k, v in tile.items()} if tile else None), "facts": facts,
           "files": {e: {"path": base + "." + e, "sha256": cm.sha_file(base + "." + e)} for e in ("svg", "pdf", "png")}, "base": base, "scale_bars": sh.bars,
           "sections_marked": [s["sheet"] for s in sec_list], "elevations_marked": [e["sheet"] for e in regs["elev"]["elevations"]], "sheet_obj": sh}
    return res


def tile_other(tile, bounds, rows, ids):
    """같은 층의 이웃 타일 정의(키 그림용)."""
    t2 = make_tiles(bounds, rows, ids if tile["index"] == 1 else (ids[1], ids[0]))
    return t2[1] if tile["index"] == 1 else t2[0]


def load_context(run):
    import book_views as bv
    model = bv.Model(os.path.join(run, "model_cache"), os.path.join(run, "raw_slices", "camera_bounds.json"))
    regs = {"sections": cm.jl(os.path.join(run, "qa", "ref_registries", "section_line_registry.json")), "elev": cm.jl(os.path.join(run, "qa", "ref_registries", "elevation_registry.json"))}
    evidence = cm.jl(os.path.join(run, "00_index", "floor_equivalence_evidence.json"))
    return model, regs, evidence


def main():
    ap = argparse.ArgumentParser(description="C-T14I 평면 시트 한 장(들)을 조립한다. 일괄 생성은 tools/t14i/build_plans.py")
    ap.add_argument("--run", default=cm.RUN_DEFAULT)
    ap.add_argument("--floor", required=True)
    ap.add_argument("--sid", required=True)
    ap.add_argument("--applies", default=None)
    ap.add_argument("--role", choices=["overview", "full", "tile"], default="overview")
    ap.add_argument("--paper", default="420x297")
    ap.add_argument("--scale", type=int, default=250)
    ap.add_argument("--tile", type=int, default=0, help="타일 번호(1|2) — role=tile")
    ap.add_argument("--tile-ids", default="P-211,P-212")
    ap.add_argument("--out-dir", default=None)
    a = ap.parse_args()
    run = os.path.abspath(a.run)
    model, regs, evidence = load_context(run)
    paper = tuple(float(v) for v in a.paper.lower().split("x"))
    raw_dir = cm.v4_dir(run, "plans_raw")
    render_raw(run, a.floor, a.scale, raw_dir)
    sl = pc.load_slice(os.path.join(run, "raw_slices"), a.floor)
    tile = None
    if a.role == "tile":
        cuts = pc.cut_geometries(sl)
        cols = [g.centroid for _, g in cuts.get("column", [])]
        ys_ = legacy.uniq([c.y for c in cols])
        bb = pc.load_bounds(os.path.join(run, "raw_slices"))["building"]
        ids = tuple(a.tile_ids.split(","))
        tile = make_tiles((bb["xmin"], bb["ymin"], bb["xmax"], bb["ymax"]), ys_, ids)[a.tile - 1]
    out_dir = a.out_dir or cm.v4_dir(run, "plans")
    r = compose(run, a.floor, a.sid, (a.applies or a.floor).split("+"), model, regs, evidence, out_dir, paper=paper, scale=a.scale, tile=tile, role=a.role)
    print("PLAN SHEET", r["sheet"], r["floor"], r["role"], r["meta"])
    print(os.path.abspath(r["files"]["pdf"]["path"]))


if __name__ == "__main__":
    main()
