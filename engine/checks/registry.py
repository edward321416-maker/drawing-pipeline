# FILE: checks/registry.py
from __future__ import annotations

from checks.geometry import check_g1_columns, check_g2_fixtures, check_g4_zones, check_g5_walls, check_g7_footprints
from checks.overlaps import check_g3_model_doors, check_g6_overlaps
from checks.restroom_rules import check_g3_restroom_doors, check_r2_restroom
from checks.tube_rules import check_r3_tube
from checks.symbol_rules import check_g3_door_swings, check_r1_stair_core
from checks.text import check_t1_text_overlap, check_t2_text_on_line, check_t3_canvas, check_t4_style

MODEL_CHECKS = {
    "G1": check_g1_columns,
    "G2": check_g2_fixtures,
    "G3": check_g3_model_doors,
    "G4": check_g4_zones,
    "G5": check_g5_walls,
    "G6": check_g6_overlaps,
    "G7": check_g7_footprints,
}
RENDER_CHECKS = {
    "T1": check_t1_text_overlap,
    "T2": check_t2_text_on_line,
    "T3": check_t3_canvas,
    "T4": check_t4_style,
}
# 심볼 단독 검사: 코어 심볼 하나(StairCore)를 받는다
SYMBOL_CHECKS = {
    "R1": check_r1_stair_core,
    "G3": check_g3_door_swings,
}
# 화장실 심볼 단독 검사: 화장실 심볼 하나(Restroom)를 받는다
RESTROOM_CHECKS = {
    "R2": check_r2_restroom,
    "G3": check_g3_restroom_doors,
}
# 튜브 심볼 단독 검사: 튜브 심볼 하나(Tube)를 받는다
TUBE_CHECKS = {
    "R3": check_r3_tube,
}
# TAG(태그 게이트)와 LAYOUT(라벨 배치 실패)은 build.py가 직접 생성한다
CHECK_IDS = frozenset({"TAG", "LAYOUT", *MODEL_CHECKS, *RENDER_CHECKS, *SYMBOL_CHECKS, *RESTROOM_CHECKS, *TUBE_CHECKS})


def run_model_checks(sections, params):
    out = []
    for fn in MODEL_CHECKS.values():
        out += fn(sections, params)
    return out


def run_render_checks(render, params):
    out = []
    for fn in RENDER_CHECKS.values():
        out += fn(render, params)
    return out


def run_symbol_checks(symbol, params):
    out = []
    for fn in SYMBOL_CHECKS.values():
        out += fn(symbol, params)
    return out


def run_restroom_checks(restroom, params):
    out = []
    for fn in RESTROOM_CHECKS.values():
        out += fn(restroom, params)
    return out


def run_tube_checks(tube, params):
    out = []
    for fn in TUBE_CHECKS.values():
        out += fn(tube, params)
    return out
