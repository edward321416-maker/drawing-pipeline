"""중간발표 설계의 대지·외부공간과 실측(OSM) 도로·이웃 건물을 논문 작업공간의 JSON으로 고정(freeze)한다.

읽기 전용이다. 중간발표 폴더에는 아무것도 쓰지 않는다(바이트코드도 만들지 않는다).
사용: python master\\extract_site_source.py
출력: model\\m_site_source.json  (대지 좌표 u, v — 1F 원천 m_1f_source.json과 같은 좌표계)

- 대지 경계(SITE)·건축한계선(BUILD)·외부공간(PLAZA, GROVE, SUNKEN)·수목(GTREES)은 s7.py·plans_s7.py의 값이다.
- 소방차 구획, 지하철 출구, 선큰 계단, 출입구 동선은 중간발표 배치도 site_plan_master.py에 대지 좌표로 적힌 값을 옮겨 적었다.
- 도로·이웃 건물은 실측(OSM) 자료 02_site_analysis\\data\\osm_ddp.json을 대지 좌표로 옮긴 것이다.
  좌표 변환은 mass_sketch.to_frame과 같다(대지 중심을 원점으로 옮기고 -63.2° 회전).
  현재 대지 위에 서 있는 건물(굿모닝시티)은 이 계획으로 대체되므로 뺀다.
- 차도 폭은 OSM의 차로 수 x 3.5 m, 없으면 등급별 기본값이다(실측 폭이 아니다). 조각난 차도는 하나로 합친다.
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

from shapely import affinity
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

MIDTERM = r"D:\Users\admin\Desktop\5-2\설계스튜디오\중간발표"
MIDTERM_07 = os.path.join(MIDTERM, "07_representation")
DATA = os.path.join(MIDTERM, "02_site_analysis", "data")
OUT = Path(__file__).resolve().parent.parent / "model" / "m_site_source.json"
ANG = 63.2
EXTRACT_MARGIN_M = 75.0     # 대지 외곽에서 이만큼 안의 실측 자료를 고정한다(도면에서는 더 좁은 창으로 자른다)

ROAD_NAMES = {"을지로": "Eulji", "장충단로": "Jangchungdan"}
ROAD_WIDTH_M = {"primary_link": 5.0, "unclassified": 6.0, "residential": 6.0, "service": 4.0}   # primary는 차로 수 x 3.5
CLOSE_M = 2.5               # 차도 조각 사이 틈·쐐기를 메우는 닫힘 연산 반경
MIN_ROAD_HOLE_M2 = 600.0    # 차도 안의 이보다 작은 구멍(도로 갈래 사이 조각)은 메운다
MIN_ROAD_PART_M2 = 80.0
LABEL_MIN_LEVELS = 8        # 이 층수 이상인 이웃 건물만 이름을 적는다(작은 상가 이름은 도면을 어지럽힌다)
# 중간발표 배치도의 값 (대지 좌표 u, v)
FIRE_LANE = (17.0, -32.0, 44.0, -26.0)        # site_plan_master.py:279 소방차 전용 주차구획 6x27 m
SUBWAY_EXITS = (("14", 18.0, -46.0), ("13", -52.0, -46.0), ("12", -70.0, -32.0))   # site_plan_master.py:228-230, 캐노피 3.2 x 6.4 m
SUNKEN_STAIR = {"bounds": [-30.0, -34.5, -16.0, -18.0], "treads": 12, "down": "+u", "label": "하향 12단 (FL -5.5 m)"}  # :266-271
# 출입구 화살표 (시작, 끝). 끝은 건물·선큰 계단 가장자리에서 멈춘다. 방향은 site_plan_master.py:377-396의 보행·차량 동선
ENTRANCES = (
    ("Main", "주출입구 (사거리 광장 → 필로티 시장 광장)", (-40.0, -18.0), (-9.0, -4.3)),
    ("Subway", "지하철 직결 진입 (2·4·5호선 → 선큰 계단)", (-55.0, -42.0), (-30.0, -27.5)),
    ("Service", "차량·하역 진입", (42.0, 52.0), (42.0, 36.3)),
)
GROVE_PATH = ((-56, 12), (-45, 16), (-35, 20), (-25, 18), (-16, 14), (-9, 6))   # site_plan_master.py:253 숲 마당 산책로 중심선


def _ring(r):
    return [[round(x, 3), round(y, 3)] for x, y in list(r.coords)[:-1]]


def _rings(geom, min_area=0.5):
    """다각형 목록. 각 항목 {"shell": 바깥 고리, "holes": 구멍 고리들}. 구멍(도로로 둘러싸인 블록 등)을 버리지 않는다."""
    polys = [geom] if geom.geom_type == "Polygon" else [g for g in getattr(geom, "geoms", []) if g.geom_type == "Polygon"]
    return [{"shell": _ring(p.exterior), "holes": [_ring(h) for h in p.interiors if Polygon(h).area > min_area]}
            for p in polys if p.area > min_area]


def _levels(value) -> float:
    """OSM의 층수·차로 수 값("3", "3.5", "2;3", 없음)을 안전하게 숫자로. 읽지 못하면 0."""
    try:
        return float(str(value).replace(",", ";").split(";")[0])
    except ValueError:
        return 0.0


def _fill_small_holes(geom, max_area):
    polys = [geom] if geom.geom_type == "Polygon" else list(getattr(geom, "geoms", []))
    return unary_union([Polygon(p.exterior, [h for h in p.interiors if Polygon(h).area > max_area]) for p in polys])


def main() -> int:
    sys.dont_write_bytecode = True
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, MIDTERM_07)
    sys.path.insert(0, os.path.join(MIDTERM_07, "drawings"))
    os.chdir(MIDTERM_07)
    import s7  # noqa: E402  (중간발표 작업공간 모듈)
    import plans_s7 as plans  # noqa: E402

    env = json.load(open(os.path.join(DATA, "envelope.json"), encoding="utf-8"))
    osm = json.load(open(os.path.join(DATA, "osm_ddp.json"), encoding="utf-8"))
    center = Polygon(env["site_xy"]).centroid

    def to_frame(g):
        return affinity.rotate(affinity.translate(g, -center.x, -center.y), -ANG, origin=(0, 0))

    site = s7.SITE
    window = box(*site.bounds).buffer(EXTRACT_MARGIN_M)

    road_parts, buildings, skipped = [], [], []   # 도로 조각: (이름, 도형, 중심선, 차로 수)
    for f in osm["features"]:
        t, pts = f["tags"], f["xy"]
        if len(pts) < 2:
            continue
        name = t.get("name", "")
        if "highway" in t:
            hw = t["highway"]
            if "지하" in name or t.get("tunnel") or str(t.get("layer", "0")).startswith("-"):
                continue
            if hw == "primary" or hw in ROAD_WIDTH_M:
                lanes = t.get("lanes")
                n_lanes = _levels(lanes)
                width = n_lanes * 3.5 if (hw == "primary" and n_lanes) else (7.0 if hw == "primary" else ROAD_WIDTH_M[hw])
                line = to_frame(LineString(pts))
                g = line.buffer(width / 2, cap_style=2).intersection(window)
                if not g.is_empty:
                    road_parts.append((name, g, line.intersection(window), int(n_lanes)))
        elif "building" in t and f["closed"] and len(pts) >= 4:
            g = to_frame(Polygon(pts)).buffer(0)
            if g.is_empty or not g.intersects(window):
                continue
            if g.intersection(site).area > 0.3 * g.area:
                skipped.append(name or "(이름 없음)")   # 대지 위의 현재 건물: 이 계획으로 대체된다
                continue
            levels = t.get("building:levels")
            tall = bool(name) and _levels(levels) >= LABEL_MIN_LEVELS
            buildings.append({"name_ko": f"{name} {levels}F" if tall else (name or "건물"), "label": tall, "rings": _rings(g)})

    # 차도: 모든 도로 조각을 하나로 합치고, 갈래 사이 틈·쐐기·작은 구멍을 메운다
    carriage = unary_union([g for _n, g, _l, _k in road_parts]).buffer(CLOSE_M).buffer(-CLOSE_M)
    carriage = _fill_small_holes(carriage, MIN_ROAD_HOLE_M2).intersection(window)
    parts = [carriage] if carriage.geom_type == "Polygon" else list(carriage.geoms)
    carriage = unary_union([p for p in parts if p.area >= MIN_ROAD_PART_M2])
    road_names = {}   # 도로 이름 글자를 놓을 영역(차도 위 해당 도로 조각)
    for name, key in ROAD_NAMES.items():
        g = unary_union([pg for n, pg, _l, _k in road_parts if n == name]).intersection(carriage)
        road_names[key] = {"name_ko": name, "rings": _rings(g)}
    # 중앙 차선: 차로 수가 짝수인 간선도로(OSM은 방향별로 나뉘어 있어 중심선이 차로 사이 구분선이다)
    centerlines = [[[round(x, 2), round(y, 2)] for x, y in ln.coords] for n, _g, line, k in road_parts
                   if n in ROAD_NAMES and k >= 2 and k % 2 == 0
                   for ln in ([line] if line.geom_type == "LineString" else list(getattr(line, "geoms", [])))]

    exits = []
    for n, u, v in SUBWAY_EXITS:   # 중간발표의 출구 위치가 실측 차도 위로 떨어지면 신뢰할 수 없어 뺀다
        canopy = box(u - 1.6, v - 3.2, u + 1.6, v + 3.2)
        if canopy.intersection(carriage).area > 0.3 * canopy.area:
            skipped.append(f"지하철 {n}번 출구(차도 위)")
            continue
        exits.append({"name_ko": f"지하철 {n}번 출구", "center": [u, v]})

    sunken, plaza, grove = s7.SUNKEN, s7.PLAZA.difference(s7.SUNKEN), s7.GROVE   # 선큰이 광장 위에 그려졌다(중간발표 z 순서)
    exterior = {
        "Plaza": {"name_ko": "사거리 공개공지 광장", "use": "plaza", "rings": _rings(plaza)},
        "Grove": {"name_ko": "그늘 숲 마당", "use": "grove", "rings": _rings(grove)},
        "Sunken": {"name_ko": "선큰 광장 (B1)", "use": "sunken", "rings": _rings(sunken)},
        "FireLane": {"name_ko": "소방차 전용 구획", "use": "fire_lane", "rings": _rings(box(*FIRE_LANE))},
    }
    data = {
        "provenance": {
            "source": f"{MIDTERM_07}\\s7.py(SITE, BUILD, PLAZA, GROVE, SUNKEN), drawings\\plans_s7.py(GTREES), "
                      f"drawings\\site_plan_master.py(소방차 구획, 지하철 출구, 선큰 계단, 출입구 동선), {DATA}\\osm_ddp.json(도로·이웃 건물)",
            "extracted": datetime.date.today().isoformat(),
            "frame": "대지 좌표 (u, v) m. m_1f_source.json과 같다. 마스터 모델은 u+9, v+18로 환산한다",
            "road_width": "OSM 차로 수 x 3.5 m (primary), 없으면 등급별 기본값. 실측 폭이 아니다",
            "excluded": skipped,
            "omitted": "횡단보도, DDP 건물(OSM에 건물 윤곽 없음 또는 창 밖), 실측 보행로 조각(보도는 차도를 따라 일정 폭으로 계산)",
        },
        "site": {"name_ko": "대지", "rings": _rings(site)},
        "buildable": {"name_ko": "건축한계선", "rings": _rings(s7.BUILD)},
        "carriageway": {"name_ko": "차도", "rings": _rings(carriage)},
        "road_names": road_names,
        "road_centerlines": centerlines,
        "context_buildings": buildings,
        "exterior_spaces": exterior,
        "sunken_stair": SUNKEN_STAIR,
        "entrances": [{"key": k, "name_ko": n, "start": list(a), "end": list(b)} for k, n, a, b in ENTRANCES],
        "grove_path_centerline": [list(map(float, p)) for p in GROVE_PATH],
        "trees": [[round(u, 3), round(v, 3), float(r)] for (u, v), r in plans.GTREES],
        "subway_exits": exits,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"고정 완료: {os.path.abspath(OUT)}")
    print(f"차도 조각 {len(data['carriageway']['rings'])}, 중앙 차선 {len(centerlines)}, 이웃 건물 {len(buildings)} "
          f"(이름 표기 {sum(b['label'] for b in buildings)}), 외부공간 {len(exterior)}, 지하철 출구 {len(exits)}")
    print(f"제외: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
