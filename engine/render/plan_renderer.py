# FILE: render/plan_renderer.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import PathPatch  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402
from shapely.geometry import LineString, Polygon, box  # noqa: E402
from shapely.geometry.base import BaseGeometry  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from extract.schema import CONTEXT_KINDS  # noqa: E402
from extract.slicer import filled_shell  # noqa: E402
from layout.labels import LabelSolver  # noqa: E402
from render.annotations import (  # noqa: E402
    Annotation, annotation_factor, draw_annotations, draw_site_annotations, draw_site_legend, grid_positions,
    site_canvas)
from render.style import (  # noqa: E402
    FONT_FAMILY, HATCH, HATCH_LINEWIDTH, KIND_STYLE, LINE_CLASSES, TEXT_ROLES)

plt.rcParams["hatch.linewidth"] = HATCH_LINEWIDTH   # 해치 선 두께(pt)
from render.restroom_draw import draw_restroom  # noqa: E402
from render.symbol_draw import draw_stair_details  # noqa: E402
from symbols.restroom import build_restroom  # noqa: E402
from symbols.stair_core import build_stair_core  # noqa: E402

LABELED_KINDS = ("zone", "tube_wall", "void", "shaft", "site", "road", "context_building", "exterior_space", "subway_exit",
                 "sunken_stair", "entrance")
INTERIOR_OBSTACLE_KINDS = ("tube_wall", "void", "shaft")
ENCLOSURE_KINDS = ("core_wall", "partition_wall")  # 닫힌 코어·화장실 벽 — 안쪽에도 라벨이 들어가면 안 된다
SYMBOL_DRAWN_KINDS = ("stair", "door")  # 심볼(상세 모드)이 직접 그린다. 일반 객체 그리기에서는 건너뛴다
Z_ORDER = {"road": 0.1, "sidewalk": 0.2, "context_building": 0.3, "site": 0.5, "setback": 0.6,
           "road_marking": 0.15, "exterior_space": 0.7, "sunken_stair": 0.75, "tree": 0.8, "subway_exit": 0.9, "entrance": 0.95,
           "zone": 1.0, "void": 1.5, "shaft": 2.0, "stair": 2.0, "tube_wall": 3.0, "partition_wall": 3.0,
           "exterior_wall": 3.0, "core_wall": 3.0, "fixture": 4.0, "column": 5.0}


@dataclass
class TextRecord:
    owner: str
    text: str
    role: str
    size: float
    bbox: tuple


@dataclass
class LineRecord:
    owner: str
    klass: str
    lw: float
    geom: BaseGeometry
    filled: bool = False
    leader: bool = False


@dataclass
class RenderResult:
    png_path: Path
    texts: list
    lines: list
    canvas: tuple


_CATEGORY = ("zone", "tube_wall", "shaft", "void", "room", "exterior_space", "sunken_stair", "entrance", "subway_exit")
_TUBE_KEYS = {"T1": "T1 나선 램프", "T2": "T2 빛 튜브", "T3": "전망 승강기 튜브 (T3·T4)", "T4": "전망 승강기 튜브 (T3·T4)",
              "CAP_W": "서측 캡슐"}
_SHAFT_KEYS = {"EV1": "비상용 승강기 (EV1·EV2)", "EV2": "비상용 승강기 (EV1·EV2)", "PL": "광장 승강기", "FR": "화물 승강기",
               "M1": "설비 샤프트 (M1·M2)", "M2": "설비 샤프트 (M1·M2)"}


def _legend_key(o):
    """범례 이름(같은 이름은 같은 번호). None이면 번호 없이 글자 이름을 그대로 적는다."""
    k = o.kind
    if k == "zone":
        return o.name_ko
    if k == "tube_wall":
        return _TUBE_KEYS.get(o.props.get("tube_id"), o.name_ko)
    if k == "shaft":
        return _SHAFT_KEYS.get(o.props.get("shaft_id"), o.name_ko)
    if k == "void":
        return "선큰 연결 개구부"
    if k == "room":
        return {"stair_core": "특별피난계단 코어", "restroom": "화장실"}.get(o.props.get("symbol"))
    if k == "exterior_space":
        return o.props.get("label_text") or o.name_ko
    if k == "sunken_stair":
        detail_text = o.props.get("label_text") or o.name_ko
        return f"선큰 계단 ({detail_text})"
    if k == "entrance":
        return o.props.get("label_text") or o.name_ko
    if k == "subway_exit":
        return "지하철 출구"
    return None


def _hatch_spec(o):
    if o.kind == "exterior_space":
        return HATCH.get("use:" + str(o.props.get("use")))
    if o.kind == "zone":
        return HATCH.get("zone:" + str(o.props.get("use")))
    return HATCH.get(o.kind)


def _build_legend(model, drawn):
    """번호 매기기: 범주 순서(건물 공간 -> 외부공간 -> 동선)와 모델 순서로 같은 이름에 같은 번호를 준다."""
    drawn_names = {o.name for o, _g, _k, _f in drawn}
    cands = []
    for idx, o in enumerate(model.objects):
        if o.kind not in _CATEGORY or o.props.get("label") in (False, 0):
            continue
        if o.kind == "room" and (not o.props.get("symbol") or len(o.verts) == 0):
            continue
        if o.kind != "room" and o.name not in drawn_names:
            continue
        key = _legend_key(o)
        if key:
            cands.append((_CATEGORY.index(o.kind), idx, key, o))
    cands.sort(key=lambda c: (c[0], c[1]))
    numbering, entries = {}, []
    for _c, _i, key, o in cands:
        if key not in numbering:
            numbering[key] = len(numbering) + 1
            entries.append({"number": numbering[key], "name": key})
    return numbering, entries


SPECKLE_PER_M2 = 0.55      # 대지 바닥 점 질감 밀도(점/㎡). 참고 도면의 옅은 점 노이즈
SPECKLE_SEED = 11


def _draw_ground_speckle(ax, drawn, sections, model) -> None:
    """대지 안쪽(건물 바닥판 제외)에 고정 시드의 옅은 점을 흩뿌린다. 검사 기록에 넣지 않는 바탕 질감이다."""
    import numpy as np
    from shapely import contains_xy

    lots = [g for o, g, _k, _f in drawn if o.kind == "site"]
    slabs = [sections.footprint(o.name) for o in model.by_kind("slab") if len(o.verts)]
    if not lots:
        return
    area = unary_union(lots).difference(filled_shell(unary_union(slabs)) if slabs else Polygon())
    x0, y0, x1, y1 = area.bounds
    rng = np.random.default_rng(SPECKLE_SEED)
    pts = rng.uniform((x0, y0), (x1, y1), size=(int(area.area * SPECKLE_PER_M2 * 1.7), 2))
    pts = pts[contains_xy(area, pts[:, 0], pts[:, 1])]
    ax.scatter(pts[:, 0], pts[:, 1], s=0.35, c="#6f6f6f", alpha=0.28, linewidths=0, zorder=0.55, rasterized=True)


def _draw_sunken_stair(pen, o) -> list:
    """선큰 계단: 단 선(props treads개)과 하향 화살표. 라벨이 피해야 할 기하를 돌려준다."""
    x0, y0, x1, y1 = (float(o.props[k]) for k in ("bx0", "by0", "bx1", "by1"))
    n = int(round(float(o.props["treads"])))
    sign = 1 if str(o.props.get("down", "+u")).startswith("+") else -1
    obs = []
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        ln = LineString([(x, y0), (x, y1)])
        pen.line(f"{o.name}:tread{i}", ln, "projection_light", 0.76)
        obs.append(ln.buffer(0.15))
    yc = (y0 + y1) / 2
    a, b = (x0 + 1.5, x1 - 1.5) if sign > 0 else (x1 - 1.5, x0 + 1.5)
    shaft = LineString([(a, yc), (b - sign * 1.5, yc)])
    pen.line(f"{o.name}:arrow", shaft, "cut_medium", 0.77)
    head = Polygon([(b, yc), (b - sign * 1.6, yc + 0.8), (b - sign * 1.6, yc - 0.8)])
    pen.polygon(f"{o.name}:arrow_head", head, "cut_heavy", "#000000", 0.77)
    return obs + [shaft.buffer(0.2), head.buffer(0.1)]


def _polys(geom):
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    return [g for g in geom.geoms if g.geom_type == "Polygon"]


def _path_for(poly):
    verts, codes = [], []
    for ring in [poly.exterior, *poly.interiors]:
        pts = list(ring.coords)
        verts += pts
        codes += [MplPath.MOVETO] + [MplPath.LINETO] * (len(pts) - 2) + [MplPath.CLOSEPOLY]
    return MplPath(verts, codes)


class Pen:
    """그리는 도구. 그린 선·글자를 검사용 기록의 재료로 함께 남긴다."""

    def __init__(self, ax):
        self.ax = ax
        self.line_artists = []  # (artist, LineRecord)
        self.text_artists = []  # (artist, owner, text, role)

    def polygon(self, owner, geom, klass, fill, zorder, outline_only=False):
        spec = LINE_CLASSES[klass]
        for poly in _polys(geom):
            patch = PathPatch(
                _path_for(poly), facecolor=fill or "none", edgecolor=spec.color,
                linewidth=spec.lw, linestyle=spec.linestyle, zorder=zorder,
            )
            self.ax.add_patch(patch)
            filled = fill is not None and not outline_only
            self.line_artists.append((patch, LineRecord(owner, klass, spec.lw, poly, filled=filled)))

    def hatch(self, owner, geom, pattern, color, alpha, zorder):
        """해치 면(검사 기록에 넣지 않는 바탕 무늬). 윤곽선은 polygon()이 따로 그린다."""
        for poly in _polys(geom):
            self.ax.add_patch(PathPatch(_path_for(poly), facecolor="none", edgecolor=color, linewidth=0, hatch=pattern,
                                        alpha=alpha, zorder=zorder))

    def line(self, owner, geom, klass, zorder, leader=False):
        spec = LINE_CLASSES[klass]
        parts = [geom] if geom.geom_type == "LineString" else list(getattr(geom, "geoms", []))
        for part in parts:
            if part.geom_type != "LineString" or part.length < 1e-6:
                continue
            xs, ys = part.xy
            (line,) = self.ax.plot(list(xs), list(ys), color=spec.color, linewidth=spec.lw,
                                   linestyle=spec.linestyle, zorder=zorder, solid_capstyle="butt")
            self.line_artists.append((line, LineRecord(owner, klass, spec.lw, part, leader=leader)))

    def text(self, owner, text, role, x, y, ha="center", va="center", rotation=0.0, zorder=10.0):
        spec = TEXT_ROLES[role]
        artist = self.ax.text(
            x, y, text, ha=ha, va=va, rotation=rotation, fontsize=spec.size, fontweight=spec.weight,
            color=spec.color, fontfamily=FONT_FAMILY, zorder=zorder,
            bbox=dict(boxstyle="square,pad=0.2", facecolor="white", edgecolor="none"),
        )
        self.text_artists.append((artist, owner, text, role))


def finish_render(fig, ax, pen, out_png, dpi, canvas) -> RenderResult:
    """그린 뒤 검사용 기록을 만든다: 글자는 실제 그려진 경계 상자, 선은 아티스트에서 읽은 두께. 그리고 PNG로 저장한다."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    texts = []
    for artist, owner, text, role in pen.text_artists:
        bb = artist.get_window_extent(renderer)
        (bx0, by0), (bx1, by1) = inv.transform([[bb.x0, bb.y0], [bb.x1, bb.y1]])
        texts.append(TextRecord(owner, text, role, float(artist.get_fontsize()), (bx0, by0, bx1, by1)))
    lines = []
    for artist, rec in pen.line_artists:
        rec.lw = float(artist.get_linewidth())  # 의도한 값이 아니라 실제 아티스트에서 읽는다
        lines.append(rec)

    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=dpi, facecolor="white")
    plt.close(fig)
    return RenderResult(out_png, texts, lines, canvas)


def render_plan(sections, params, out_png, annotation: Annotation | None = None, detail: bool = False,
                scope: str = "building") -> RenderResult:
    """detail=True이면 `symbol` 태그가 붙은 방(코어)의 상세선을 심볼로 그린다. False이면 단선 평면이다.

    scope="building"은 건물만(대지 맥락은 그리지 않는다), scope="site"는 대지 경계·건축한계선·도로·보도·이웃 건물을 함께 그린다.
    축척은 params.scale_denominator로 정한다(건물 도면 1:200, 대지 도면 1:400은 호출하는 쪽이 정해 넘긴다)."""
    if scope not in ("building", "site"):
        raise ValueError(f"scope는 'building' 또는 'site'여야 합니다: {scope}")
    model = sections.model
    cut = params.plan_cut_height_m
    k = annotation_factor(params)

    drawn = []
    for o in model.objects:
        style = KIND_STYLE.get(o.kind)
        if style is not None and o.props.get("thin"):
            style = ("projection_light", "#444444")   # 큐비클 칸막이 같은 가는 칸막이 (AGENTS.md §3.2 lw 0.6)
        if style is None or len(o.verts) == 0 or o.kind in SYMBOL_DRAWN_KINDS:
            continue
        if o.kind in CONTEXT_KINDS and scope != "site":
            continue
        geom = sections.at(cut).get(o.name) if o.zmin <= cut <= o.zmax else None
        if geom is None or geom.is_empty:
            geom = sections.footprint(o.name)  # 절단면 위/아래 요소는 투영(바닥 윤곽)으로 그린다
        if geom.is_empty:
            continue
        drawn.append((o, geom, style[0], style[1]))
    if not any(o.kind not in CONTEXT_KINDS for o, _g, _k, _f in drawn):
        raise ValueError("그릴 객체가 없습니다")

    # 대지 도면: 보이는 창 = 대지 경계 + 바깥 여유. 창 밖은 자른다(이웃 건물·도로는 원래 모델에 전체가 있다)
    window = None
    if scope == "site":
        lots = [g for o, g, _k, _f in drawn if o.kind == "site"]
        if not lots:
            raise ValueError("대지 도면인데 대지(site) 객체가 없습니다")
        lx0, ly0, lx1, ly1 = unary_union(lots).bounds
        ml_, mb_, mr_, mt_ = params.site_context_margin_m
        window = (lx0 - ml_, ly0 - mb_, lx1 + mr_, ly1 + mt_)
        clip = box(*window)
        clipped = []
        for o, g, klass, fill in drawn:
            if o.kind in CONTEXT_KINDS and o.kind != "site":
                g = g.intersection(clip)
                if g.is_empty:
                    continue
            clipped.append((o, g, klass, fill))
        drawn = clipped

    # 건물 윤곽: 외벽 데이터가 없는 층은 바닥판 외곽을 윤곽선으로 쓴다(표기 모드에서만 그린다)
    outline = None
    if annotation is not None:
        slabs = [sections.footprint(o.name) for o in model.by_kind("slab") if len(o.verts)]
        parts = _polys(unary_union(slabs)) if slabs else []
        if parts:
            outline = Polygon(max(parts, key=lambda p: p.area).exterior)

    # 대지 도면: 도면 안에는 번호만, 이름은 범례에. 번호와 범례 항목은 모델 객체에서 만든다
    numbering, legend_entries = {}, []
    if scope == "site":
        numbering, legend_entries = _build_legend(model, drawn)

    content = unary_union([g for o, g, _, _ in drawn if o.kind not in CONTEXT_KINDS])
    x0, y0, x1, y1 = (outline or content).bounds   # 건물 외곽(대지 도면에서도 격자·표기의 기준은 건물이다)
    if annotation is not None:
        ml, mb, mr, mt = (v * k for v in params.annotation_margins_m)
    else:
        ml = mb = mr = mt = params.margin_m
    canvas = (x0 - ml, y0 - mb, x1 + mr, y1 + mt)
    if window is not None:
        canvas = site_canvas(window, params, len(legend_entries)) if annotation is not None else window

    inch_per_m = 1.0 / (params.scale_denominator * 0.0254)
    fig = plt.figure(
        figsize=((canvas[2] - canvas[0]) * inch_per_m, (canvas[3] - canvas[1]) * inch_per_m),
        dpi=params.dpi, facecolor="white",
    )
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(canvas[0], canvas[2])
    ax.set_ylim(canvas[1], canvas[3])
    ax.set_aspect("equal")
    ax.axis("off")
    pen = Pen(ax)

    # 구조 격자
    from shapely.geometry import LineString

    for x in grid_positions(x0, x1, params.grid_spacing_m):
        pen.line("grid", LineString([(x, y0 - 1), (x, y1 + 1)]), "grid", 0.5)
    for y in grid_positions(y0, y1, params.grid_spacing_m):
        pen.line("grid", LineString([(x0 - 1, y), (x1 + 1, y)]), "grid", 0.5)

    if scope == "site":
        _draw_ground_speckle(ax, drawn, sections, model)
    for o, geom, klass, fill in drawn:
        # 대지 맥락의 채움은 바탕이므로 그 위에 이름을 적는 것은 정상이다. 검사에는 윤곽선만 남긴다
        spec = _hatch_spec(o) if scope == "site" else None
        if scope == "site" and o.kind in ("road", "sidewalk", "context_building", "exterior_space", "tree"):
            fill = None   # 색 대신 해치(참고 도면)
        pen.polygon(o.name, geom, klass, fill, Z_ORDER.get(o.kind, 2.0), outline_only=o.kind in CONTEXT_KINDS)
        if spec:
            pen.hatch(f"{o.name}:hatch", geom, *spec, zorder=Z_ORDER.get(o.kind, 2.0) + 0.01)
    if outline is not None:
        # 필로티(열린 바닥) 쪽 가장자리는 닫힌 외피가 아니므로 바닥판 가장자리로 얇게, 나머지는 건물 윤곽(굵게)으로 그린다
        piloti = unary_union([g for o, g, _k, _f in drawn if o.kind == "zone" and o.props.get("use") == "piloti_plaza"])
        open_band = piloti.buffer(0.05)
        ring = outline.boundary
        open_part, closed_part = ring.intersection(open_band), ring.difference(open_band)
        pen.line("Slab_1F:outline", closed_part, "cut_heavy", 6.0)
        pen.line("Slab_1F:outline_open", open_part, "projection_light", 6.0)
        if window is not None:
            draw_site_annotations(pen, window, params, annotation, bool(legend_entries))
            draw_site_legend(pen, window, params, legend_entries)
        else:
            draw_annotations(pen, (x0, y0, x1, y1), params, annotation)

    # 상세 모드: 코어 심볼의 디딤판·절단선·문 호·화살표. 모델의 방(room) 태그(core_id, ves_side, 외곽)에서 심볼을 다시 만든다.
    symbol_cores, symbol_restrooms = {}, {}
    if detail:
        for o in model.objects:
            if o.kind == "room" and o.props.get("symbol") == "stair_core":
                bounds = tuple(float(o.props[k]) for k in ("bx0", "by0", "bx1", "by1"))
                core = build_stair_core(str(o.props["core_id"]), bounds, str(o.props["ves_side"]), params.stair,
                                        hall_door_offset=float(o.props.get("hall_door_offset", 0.0)))
                symbol_cores[o.name] = (core, unary_union(draw_stair_details(pen, core)))
        # 화장실: 방(room)마다 같은 심볼을 한 번만 다시 만들고 세면대 볼·회전 원·문 호를 그린다
        built_restrooms = {}
        for o in model.objects:
            if o.kind == "room" and o.props.get("symbol") == "restroom":
                wid = str(o.props["wc_id"])
                if wid not in built_restrooms:
                    bounds = tuple(float(o.props[k]) for k in ("bx0", "by0", "bx1", "by1"))
                    rr = build_restroom(wid, bounds, str(o.props["program"]), params.restroom)
                    built_restrooms[wid] = unary_union(draw_restroom(pen, rr, only_details=True))
                symbol_restrooms[o.name] = built_restrooms[wid]

    # 라벨: 장애물 = 그려진 선(채움은 면, 윤곽은 가는 띠)
    slab_footprints = [sections.footprint(o.name) for o in model.by_kind("slab") if len(o.verts)]
    building_footprint = filled_shell(unary_union(slab_footprints)) if slab_footprints else Polygon()   # 튜브 구멍도 건물 안
    extra_obs = []
    for o, _g, _k, _f in drawn:
        if o.kind == "sunken_stair":
            extra_obs += _draw_sunken_stair(pen, o)
    line_obs, interior_obs = list(extra_obs), []
    for o, geom, klass, fill in drawn:
        if o.kind == "zone":
            continue
        # 대지 맥락은 채움 면이 아니라 윤곽선만 장애물이다(도로 위에 도로 이름이 놓여야 한다)
        line_obs.append(geom if (fill is not None and o.kind not in CONTEXT_KINDS) else geom.boundary.buffer(0.05))
        if o.kind in INTERIOR_OBSTACLE_KINDS:
            interior_obs.append(filled_shell(geom))
    # 구획존 윤곽선도 장애물이다. 튜브·보이드 라벨이 존 경계선을 가로지르면 T2 위반이 된다.
    zone_outlines = [geom.boundary.buffer(0.05) for o, geom, _k, _f in drawn if o.kind == "zone"]
    if outline is not None:
        zone_outlines.append(outline.boundary.buffer(0.05))
    enclosures = [g for o, g, _k, _f in drawn if o.kind in ENCLOSURE_KINDS]
    enclosure_interior = [filled_shell(unary_union(enclosures))] if enclosures else []
    # 코어·화장실 방의 안쪽(문 개구가 있어도 닫힌 방으로 본다)에는 다른 라벨이 들어가지 않는다
    rooms = [sections.footprint(o.name) for o in model.objects if o.kind == "room" and len(o.verts) and o.props.get("symbol")]
    room_interior = [unary_union(rooms)] if rooms else []
    # 상세 심볼(디딤판·문 호·회전 원)은 자기 방뿐 아니라 모든 라벨의 장애물이다. 이웃한 코어 라벨이 화장실 문 호 위에 놓이지 않도록.
    symbol_detail = [d for _c, d in symbol_cores.values()] + list(symbol_restrooms.values())
    line_obstacle = unary_union(line_obs + zone_outlines + enclosure_interior + room_interior + symbol_detail)
    zone_obstacle = unary_union(line_obs + zone_outlines + interior_obs + enclosure_interior + room_interior + symbol_detail)

    # 표기 모드에서는 지시선 라벨도 건물 둘레 1 m 안에만 둔다(치수·격자 기호 영역을 침범하지 않도록)
    label_canvas = box(x0 - 1, y0 - 1, x1 + 1, y1 + 1) if annotation is not None else box(*canvas)
    if window is not None:   # 대지 도면: 도로·이웃 건물 이름도 도면 창 안 어디든 놓을 수 있다(표제·방위표 띠는 제외)
        label_canvas = box(*window)
    solver = LabelSolver(params, label_canvas)
    label_items = []  # (owner, placement)
    ordered = [d for d in drawn if d[0].kind == "zone"] + [d for d in drawn if d[0].kind != "zone"]
    for o, geom, klass, fill in ordered:
        # label=False는 Blender를 거치면 정수 0이 되므로 둘 다 "라벨 없음"으로 본다
        if o.kind not in LABELED_KINDS or o.props.get("label") in (False, 0):
            continue
        if o.kind == "zone":
            region, obstacles, area = geom, zone_obstacle, geom.area
        else:
            shell = filled_shell(geom)
            # 대지 맥락 이름은 자기 영역의 경계선에 닿지 않도록 안쪽 여유를 더 준다(글자가 경계 띠와 겹치면 T2)
            gap = params.label_gap_m * (5 if o.kind in CONTEXT_KINDS else 1)
            region = shell.buffer(-gap)
            region = region if not region.is_empty else shell
            obstacles, area = line_obstacle, shell.area
            if o.kind in CONTEXT_KINDS:   # 대지·도로·이웃 건물 이름은 건물 위에 놓이면 안 된다
                obstacles = unary_union([line_obstacle, building_footprint])
        role = o.props.get("label_role", "room")
        lines = [(str(o.props.get("label_text") or o.name_ko), role)]
        if o.kind not in ("road", "context_building", "subway_exit", "sunken_stair", "entrance"):   # 면적을 적지 않는 것들
            lines.append((f"{area:,.0f}㎡", "sub"))
        if numbering.get(_legend_key(o)):
            lines = [(str(numbering[_legend_key(o)]), "sub")]   # 이름은 범례에 있고 도면에는 번호만(참고 도면: 보통 굵기의 작은 글자)
        label_items.append((o.name, solver.place(region, lines, obstacles)))

    # room: 그리지 않고 이름·면적 라벨만 붙인다(코어·화장실의 안쪽 영역). 자기 벽은 이미 장애물에 들어 있다.
    plain_obstacle = unary_union(line_obs + zone_outlines + symbol_detail)
    for o in model.objects:
        if o.kind != "room" or len(o.verts) == 0 or o.props.get("label") in (False, 0):
            continue
        if o.props.get("context") and window is None:
            continue   # 도로 이름 같은 대지 맥락 글자는 대지 도면에서만
        region, obstacles = sections.footprint(o.name), plain_obstacle
        if o.props.get("context"):   # 도면 창 안쪽에서만 글자를 놓는다. 건물 위는 피한다
            region = region.intersection(box(*window).buffer(-params.label_gap_m * 5))
            obstacles = unary_union([plain_obstacle, building_footprint])
            if region.is_empty:
                continue
        area = region.area
        if o.name in symbol_cores:  # 상세 모드의 코어: 가운데 빈 곳에 놓고 디딤판·문·화살표를 피한다
            core, detail_obstacle = symbol_cores[o.name]
            region, obstacles = core.opening, unary_union([plain_obstacle, detail_obstacle])
        elif o.name in symbol_restrooms:  # 화장실의 방: 회전 원·문 호를 피한다
            obstacles = unary_union([plain_obstacle, symbol_restrooms[o.name]])
        lines = [(str(o.props.get("label_text") or o.name_ko), o.props.get("label_role", "room"))]
        if not o.props.get("no_area"):
            lines.append((f"{area:,.0f}㎡", "sub"))
        if numbering.get(_legend_key(o)):
            lines = [(str(numbering[_legend_key(o)]), "sub")]
        label_items.append((o.name, solver.place(region, lines, obstacles)))

    for owner, placement in label_items:
        if placement.leader is not None:
            pen.line(owner, placement.leader, "detail", 9.0, leader=True)
        for (text, role), (cx, cy) in zip(placement.lines, placement.line_centers):
            pen.text(owner, text, role, cx, cy)

    return finish_render(fig, ax, pen, out_png, params.dpi, canvas)
