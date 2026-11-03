# FILE: engine_params.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).parent / "model" / "params.yaml"


@dataclass(frozen=True)
class StairParams:
    """특별피난계단 코어 심볼 규격. 값의 출처는 중간발표 s7.py·law_s7.py와 편의법 시행규칙 별표 1 제8호."""
    wall_t_m: float
    vestibule_depth_m: float
    partition_t_m: float
    flight_w_m: float
    tread_m: float
    riser_m: float
    floor_height_m: float
    door_w_m: float
    cut_height_m: float
    min_flight_w_m: float
    min_tread_m: float
    max_riser_m: float
    min_vestibule_area_m2: float
    min_door_w_m: float
    sheet_scale_denominator: float
    sheet_dpi: int


@dataclass(frozen=True)
class RestroomParams:
    """화장실 심볼 규격. 출처: AGENTS.md §3.2(큐비클·진입 통로), 장애인 편의시설 기준."""
    wall_t_m: float
    thin_t_m: float
    door_w_m: float
    sliding_door_w_m: float
    min_door_w_m: float
    cubicle_general_m: tuple[float, float]       # (짧은 변, 긴 변) 이상
    cubicle_accessible_m: tuple[float, float]
    stall_depth_m: float
    accessible_depth_m: float
    turning_circle_d_m: float
    entry_clear_m: float
    corridor_min_w_m: float
    basin_w_m: float
    basin_d_m: float
    urinal_w_m: float
    urinal_d_m: float
    urinal_pitch_m: float
    bowl_w_m: float
    bowl_d_m: float
    sheet_scale_denominator: float
    sheet_dpi: int


@dataclass(frozen=True)
class TubeParams:
    """튜브 심볼 규격. 출처: AGENTS.md §3(나선 램프·승강기 튜브 표준), build_master.py GLASS_T, 장애인 편의시설 기준."""
    glass_t_m: float
    ramp_w_m: float
    min_ramp_w_m: float
    spiral_turn_deg: float
    spiral_start_deg: float
    spiral_margin_m: float
    shaft_outer_m: float
    shaft_wall_t_m: float
    shaft_gap_m: float
    shaft_to_glass_m: float
    car_door_w_m: float
    entry_w_m: float
    min_door_w_m: float
    lobby_min_depth_m: float
    entry_clear_m: float
    context_column_m: float
    sheet_scale_denominator: float
    sheet_dpi: int


@dataclass(frozen=True)
class Params:
    plan_cut_height_m: float
    check_heights_m: tuple[float, ...]
    grid_spacing_m: float
    grid_tolerance_m: float
    furniture_to_column_m: float
    zone_overlap_tolerance_m2: float
    zone_coverage_tolerance_ratio: float
    scale_denominator: float          # 나머지 도면(건물만) 축척 분모
    site_scale_denominator: float     # 전체 1층 도면(대지 포함) 축척 분모
    site_context_margin_m: tuple[float, float, float, float]  # 좌, 하, 우, 상
    annotation_base_scale: float      # annotation.* m 값이 맞춰진 축척 분모
    margin_m: float
    dpi: int
    label_gap_m: float
    label_pad_m: float
    text_collision_tolerance_m2: float
    dim_tier1_m: float
    dim_tier2_m: float
    bubble_offset_m: float
    bubble_radius_m: float
    annotation_margins_m: tuple[float, float, float, float]  # 좌, 하, 우, 상
    scale_bar_m: float
    stair: StairParams
    restroom: RestroomParams
    tube: TubeParams


def load_params(path: Path | None = None) -> Params:
    raw = yaml.safe_load(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"))
    ann = raw["annotation"]
    st = raw["stair_core"]
    stair = StairParams(
        wall_t_m=float(st["wall_t_m"]),
        vestibule_depth_m=float(st["vestibule_depth_m"]),
        partition_t_m=float(st["partition_t_m"]),
        flight_w_m=float(st["flight_w_m"]),
        tread_m=float(st["tread_m"]),
        riser_m=float(st["riser_m"]),
        floor_height_m=float(st["floor_height_m"]),
        door_w_m=float(st["door_w_m"]),
        cut_height_m=float(st["cut_height_m"]),
        min_flight_w_m=float(st["min_flight_w_m"]),
        min_tread_m=float(st["min_tread_m"]),
        max_riser_m=float(st["max_riser_m"]),
        min_vestibule_area_m2=float(st["min_vestibule_area_m2"]),
        min_door_w_m=float(st["min_door_w_m"]),
        sheet_scale_denominator=float(st["sheet_scale_denominator"]),
        sheet_dpi=int(st["sheet_dpi"]),
    )
    rt = raw["restroom"]
    restroom = RestroomParams(
        wall_t_m=float(rt["wall_t_m"]), thin_t_m=float(rt["thin_t_m"]),
        door_w_m=float(rt["door_w_m"]), sliding_door_w_m=float(rt["sliding_door_w_m"]),
        min_door_w_m=float(rt["min_door_w_m"]),
        cubicle_general_m=tuple(float(v) for v in rt["cubicle_general_m"]),
        cubicle_accessible_m=tuple(float(v) for v in rt["cubicle_accessible_m"]),
        stall_depth_m=float(rt["stall_depth_m"]), accessible_depth_m=float(rt["accessible_depth_m"]),
        turning_circle_d_m=float(rt["turning_circle_d_m"]), entry_clear_m=float(rt["entry_clear_m"]),
        corridor_min_w_m=float(rt["corridor_min_w_m"]),
        basin_w_m=float(rt["basin_w_m"]), basin_d_m=float(rt["basin_d_m"]),
        urinal_w_m=float(rt["urinal_w_m"]), urinal_d_m=float(rt["urinal_d_m"]),
        urinal_pitch_m=float(rt["urinal_pitch_m"]),
        bowl_w_m=float(rt["bowl_w_m"]), bowl_d_m=float(rt["bowl_d_m"]),
        sheet_scale_denominator=float(rt["sheet_scale_denominator"]), sheet_dpi=int(rt["sheet_dpi"]),
    )
    tb = raw["tube"]
    tube = TubeParams(**{k: (int(v) if k == "sheet_dpi" else float(v)) for k, v in tb.items()})
    params = Params(
        plan_cut_height_m=float(raw["slice"]["plan_cut_height_m"]),
        check_heights_m=tuple(float(h) for h in raw["slice"]["check_heights_m"]),
        grid_spacing_m=float(raw["grid"]["spacing_m"]),
        grid_tolerance_m=float(raw["grid"]["tolerance_m"]),
        furniture_to_column_m=float(raw["clearance"]["furniture_to_column_m"]),
        zone_overlap_tolerance_m2=float(raw["zones"]["overlap_tolerance_m2"]),
        zone_coverage_tolerance_ratio=float(raw["zones"]["coverage_tolerance_ratio"]),
        scale_denominator=float(raw["render"]["scale_denominator"]),
        site_scale_denominator=float(raw["render"]["site_scale_denominator"]),
        site_context_margin_m=tuple(float(v) for v in raw["render"]["site_context_margin_m"]),
        annotation_base_scale=float(ann["base_scale_denominator"]),
        margin_m=float(raw["render"]["margin_m"]),
        dpi=int(raw["render"]["dpi"]),
        label_gap_m=float(raw["render"]["label_gap_m"]),
        label_pad_m=float(raw["render"]["label_pad_m"]),
        text_collision_tolerance_m2=float(raw["text"]["collision_tolerance_m2"]),
        dim_tier1_m=float(ann["dim_tier1_m"]),
        dim_tier2_m=float(ann["dim_tier2_m"]),
        bubble_offset_m=float(ann["bubble_offset_m"]),
        bubble_radius_m=float(ann["bubble_radius_m"]),
        annotation_margins_m=tuple(float(v) for v in ann["margins_m"]),
        scale_bar_m=float(ann["scale_bar_m"]),
        stair=stair,
        restroom=restroom,
        tube=tube,
    )
    if params.plan_cut_height_m not in params.check_heights_m:
        raise ValueError("plan_cut_height_m must be one of check_heights_m")
    if len(params.annotation_margins_m) != 4:
        raise ValueError("annotation.margins_m must have 4 values (left, bottom, right, top)")
    return params
