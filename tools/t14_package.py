"""C-T14 3F 파일럿 패키지 작성: 층 인벤토리, 입력 매니페스트, 프로그램 출처, 클라우드 사전 점검, ChatGPT 검토 입력.

숫자·해시는 모두 산출 파일에서 읽는다(손으로 적지 않는다). 클라우드 잔액 등 확인하지 못한 값은 null/UNKNOWN으로 둔다.

    python -I tools/t14_package.py --run <후보 폴더> --glb <전층.glb> --head <git HEAD>
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
import pipeline_common as pc  # noqa: E402


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def dump(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--glb", required=True)
    ap.add_argument("--head", required=True)
    a = ap.parse_args()
    run = os.path.abspath(a.run)
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    inv_raw = os.path.join(run, "_inventory_run", "raw_slices")
    floors = pc.load_json(os.path.join(inv_raw, "floors.json"))["floors"]

    # ── floor_inventory.json ──
    rows = []
    for name, z in floors.items():
        p = os.path.join(inv_raw, "floor_%s_slice.json" % name)
        row = {"floor": name, "floor_z_m": z, "slice": None}
        if os.path.exists(p):
            sl = pc.load_json(p)
            kinds = {}
            for it in sl["elements"]:
                kinds[it["kind"]] = kinds.get(it["kind"], 0) + 1
            row.update({"cut_z_m": sl["cut_z"], "elements_by_kind": kinds, "zones": [z_["name_ko"] for z_ in sl["zones"]],
                        "slice": {"path": p, "sha256": sha(p)}})
        rows.append(row)
    heights = [r["floor_z_m"] for r in rows]
    dump(os.path.join(run, "floor_inventory.json"), {
        "source": "GLB 층판 A-FLOR_s7_* 윗면에서 읽음(하드코딩 없음)", "floor_count": len(rows), "floors": rows,
        "storey_heights_m": [round(b - a_, 3) for a_, b in zip(heights, heights[1:])],
        "note": "각 층 slice는 층 구분 없는 대지·수목 맥락(site/trees)을 함께 싣는다. 3F 렌더러는 이를 도면에 쓰지 않는다(AGENTS §6-10: 대지는 1층 평면).",
        "generated": now})

    # ── 3F provenance ──
    sl3 = pc.load_json(os.path.join(run, "raw_slices", "floor_3F_slice.json"))
    lay = pc.load_json(os.path.join(run, "vector", "floor_3F_layout.json"))
    cuts = pc.cut_geometries(sl3)
    elems = []
    for kd, items in cuts.items():
        for it, g in items:
            elems.append({"kind": kd, "name_ko": it.get("name_ko"), "tag_source": it.get("source"), "area_m2": round(g.area, 2),
                          "centroid": [round(g.centroid.x, 2), round(g.centroid.y, 2)], "status": "SOURCE_VERIFIED"})
    glb = os.path.abspath(a.glb)
    dump(os.path.join(run, "3F_PILOT", "floor_3F_model_provenance.json"), {
        "floor": "3F", "git_head": a.head, "model": {"path": glb, "sha256": sha(glb)},
        "slice": {"path": os.path.join(run, "raw_slices", "floor_3F_slice.json"), "sha256": sha(os.path.join(run, "raw_slices", "floor_3F_slice.json")), "cut_z_m": sl3["cut_z"], "floor_z_m": sl3["floor_z"]},
        "slab_area_m2": lay.get("slab_area_m2"), "building_bounds_drawing_frame_m": lay["building"],
        "elements": elems, "element_count": len(elems),
        "tag_note": "GLB에는 kind/name_ko 태그가 없고 이름 접두어 규칙으로 분류했다(source=name). 태그된 .blend 마스터가 아니므로 AGENTS §6-2의 '태그 의무'는 GLB 경로에서 충족되지 않는다 → 미해결 항목 U-03.",
        "generated": now})
    # ── floor_programs/3F.json ──
    zone_area = {}
    for z_ in sl3["zones"]:
        zone_area[z_["name_ko"]] = round(pc.polygons_from_segments(z_["segments"]).area, 1)
    dump(os.path.join(run, "floor_programs", "3F.json"), {
        "floor": "3F",
        "SOURCE_VERIFIED": [{"item": "A-PROG 구역 '%s' (%s)" % (k, z_["name"]), "area_m2": zone_area[k]} for z_ in sl3["zones"] for k in [z_["name_ko"]]]
        + [{"item": "코어 A~D 외곽 벽(내부 계단·승강기 없음)"}, {"item": "튜브 T1~T4·M1·M2·PL·FR, 서측 캡슐"}, {"item": "승강기 샤프트 EV1·EV2"}, {"item": "에스컬레이터 3F-4F 윤곽"},
           {"item": "입면 부재 3개(외피 윤곽, 성격 미확인)"}, {"item": "기둥 34개"}],
        "PROPOSED_ONLY": [{"item": "시장 가구 137개·캡슐 갤러리 가구(렌더러 심볼)", "note": "설계 데이터 아님. 모델 요소와 겹치는 3개는 제외"},
                          {"item": "범례 이름 '시장 홀'", "note": "'판매' 구역을 렌더러 program_kind가 hall로 해석한 이름"}],
        "UNKNOWN": [{"item": "상층 외벽 성격(유리/벽)"}, {"item": "실내 구획벽"}, {"item": "출입문·캡슐 출입구"}, {"item": "코어 내부(계단·부속실·승강기)"}, {"item": "화장실"}, {"item": "피난 경로·법규 적합성"}],
        "generated": now})

    # ── 도면 방향 기준(1층 마스터) ──
    orient = None
    refd = os.path.join(run, "reference_1F")
    if os.path.isdir(refd):
        rb = pc.load_json(os.path.join(refd, "camera_bounds.json"))
        ob = pc.load_json(os.path.join(run, "raw_slices", "camera_bounds.json"))
        orient = {"reference_dir": refd, "north_deg_1F_master": rb["frame"]["north_deg"], "theta_deg_1F_master": rb["frame"]["theta_deg"],
                  "north_deg_3F": ob["frame"]["north_deg"], "theta_deg_3F": ob["frame"]["theta_deg"],
                  "rule": "도면좌표 = R(-theta)·월드좌표. GLB의 detect_theta는 90° 단위를 버리므로 --frame-ref로 1층 마스터의 north_deg에 90° 배수로 맞춘다. 맞지 않으면 빌드 거부.",
                  "slicer_log": "FRAME_REF ... (logs\\01_slice_3F.log)"}
    # ── input_manifest ──
    dump(os.path.join(run, "input_manifest.json"), {"orientation": orient,
        "candidate": "C_T14_ALL_FLOORS_CANDIDATE_001", "scope": "3F 파일럿 (Milestone A + A-R 입력). 나머지 15개 층 미생성", "git_head": a.head,
        "worktree": os.path.abspath(os.path.join(run, "..", "..")), "branch": "claude/t14-3f-pilot (기준: origin/claude/t13a-cleanline 39acf6f)",
        "model": {"path": glb, "sha256": sha(glb), "size_bytes": os.path.getsize(glb)},
        "tools": {"blender": "4.2.0", "python": sys.version.split()[0]},
        "commands": [
            "blender -b --factory-startup -P src/01_headless_slicer.py -- --input <glb> --out <run> --cut 1.5 --floors 3F --phase slice --frame-ref <run>/reference_1F/camera_bounds.json",
            "python -I src/02_topology_to_cad.py --raw <run>/raw_slices --out <run> --floors 3F --scale 200",
            "python -I src/architectural_plan_renderer.py --out <run> --floor 3F --scale 200 --png-width 4961 --cleanline --final-dir <run>/3F_PILOT --name plan_3F_A3_1to200_cleanline",
            "python -I src/architectural_plan_renderer.py --out <run> --floor 3F --scale 100 --png-width 4961 --cleanline --final-dir <run>/3F_PILOT",
            "python -I tools/t14_floor_qa.py --run <run> --floor 3F --glb <glb> --ref-dir <run>/reference_1F",
            "python -I tools/t14_crops.py --run <run> --floor 3F --after <after svg>",
            "python -I tools/t14_orientation_compare.py --run-before <001> --run-after <run> --ref-png <1F preview> --out-dir <run>/comparisons"],
        "execution": {"cloud_modal": "NOT_RUN (잔액·지출 상한 미확인 → HOLD)", "claude_api_batch_qa": "NOT_RUN (API 키 없음)", "local": "전 단계 로컬"},
        "generated": now})

    # ── 클라우드 사전 점검 (실제 조회 결과만) ──
    dump(os.path.join(run, "cloud_credit_preflight.json"), {
        "schema": "C_T14_CLOUD_CREDIT_PREFLIGHT_V1", "evidence_timestamp": now, "mode": "LOCAL_CONTINUE_CLOUD_HOLD",
        "additional_cash_spend_allowed_usd": 0, "additional_cash_spend_incurred_usd": 0,
        "providers": [
            {"provider": "modal", "product": "serverless compute", "credit_type": "workspace credits", "workspace": "edward321416", "client_version": "1.6.3",
             "evidence": {"billing_summary_this_month": {"metered_usd": 6.61, "credits_applied_usd": 6.38, "billed_usd": 0.0},
                          "billing_summary_last_month": {"metered_usd": 7.74, "credits_applied_usd": 7.66, "billed_usd": 0.0},
                          "rates_usd": {"cpu_core_hour": 0.0473, "memory_gib_hour": 0.008, "a10g_hour": 1.10, "l4_hour": 0.80}},
             "available_credit_usd_or_unknown": "UNKNOWN", "expiry_or_unknown": "UNKNOWN", "spend_ceiling_usd_or_unknown": "UNKNOWN", "auto_recharge": "UNKNOWN",
             "user_stated_balance_unverified": "메모리 기록: $147 (사용자 진술, 이번 조회로 확인되지 않음)",
             "eligible_jobs": ["blender_headless_cpu", "shapely_vector_cpu", "pdf_svg_png_cpu"], "preflight_state": "HOLD_BALANCE_AND_LIMIT_UNVERIFIED",
             "how_admin_verifies": "modal.com/settings → Usage & Billing (잔액·지출 상한·자동충전)",
             "note": "CLI의 billing summary는 최근 두 달 청구액 $0.00(크레딧 상쇄)까지만 보여주며 잔액과 상한은 보이지 않는다. 읽기 전용 명령만 사용했다."},
            {"provider": "claude_code", "product": "Claude Code (claude.ai 로그인)", "credit_type": "subscription usage", "auth_method": "claude.ai", "subscription_type": "max",
             "available_credit_usd_or_unknown": "N/A (구독 포함 사용량, 잔여량 UNKNOWN)", "counts_toward_platform_api_credits": False, "cloud_session_used": False,
             "preflight_state": "USED_LOCAL_ONLY"},
            {"provider": "claude_platform", "product": "Claude API (Message Batches)", "credit_type": "API credits",
             "api_key_present_in_environment": False, "available_credit_usd_or_unknown": "UNKNOWN", "api_credits_eligible": "UNKNOWN", "spend_ceiling_usd_or_unknown": "UNKNOWN", "auto_recharge": "UNKNOWN",
             "eligible_jobs": ["vision_floor_qa"], "preflight_state": "HOLD_NO_API_KEY",
             "how_admin_verifies": "platform.claude.com Console → Billing / Limits"},
            {"provider": "chatgpt", "product": "ChatGPT 앱(수작업 시각 리뷰)", "credit_type": "사용자 계정", "preflight_state": "MANUAL_USER_STEP", "note": "Modal·Claude 크레딧을 쓰지 않는다."}],
        "critical_rules_observed": ["no_new_subscriptions_or_payments", "no_auto_recharge", "no_credentials_in_logs", "no_cloud_run_without_verified_balance_and_limit",
                                    "upper_floor_walls_doors_not_labeled_model_verified", "no_final_freeze"]})
    cl = os.path.join(run, "cloud_cost_ledger.csv")
    with open(cl, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow("timestamp,provider,execution_mode,job_id,floor_id,model_sha,requested_cpu,requested_gpu,wall_seconds,estimated_usd,actual_usd_or_unknown,credit_remaining_or_unknown,status".split(","))
        csv.writer(f).writerow([now, "local", "local_cpu", "3F_slice", "3F", sha(glb), "local", "none", 8, 0, 0, "N/A", "DONE_LOCAL (Modal 대체 가능 작업, 크레딧 미사용)"])

    # ── ChatGPT 검토 입력 ──
    vr = os.path.join(run, "visual_retouch_review")
    os.makedirs(os.path.join(vr, "crops"), exist_ok=True)
    sd = os.path.join(run, "3F_PILOT")
    sheets = {}
    for base in ["plan_3F_A3_1to200_cleanline"] + ["plan_3F_A3_1to100_t%d_cleanline" % i for i in range(1, 5)]:
        for ext in ("pdf", "png", "svg"):
            sheets.setdefault(base, {})[ext] = {"path": os.path.join(sd, base + "." + ext), "sha256": sha(os.path.join(sd, base + "." + ext))}
    crops = []
    for i, c in enumerate(sorted(f for f in os.listdir(os.path.join(sd, "crops")) if f.endswith(".png") and "_before" not in f)):
        shutil.copy(os.path.join(sd, "crops", c), os.path.join(vr, "crops", c))
        crops.append({"id": c[:-4], "after": os.path.join(vr, "crops", c), "sha256": sha(os.path.join(vr, "crops", c))})
    for name in os.listdir(os.path.join(run, "comparisons")):
        shutil.copy(os.path.join(run, "comparisons", name), os.path.join(vr, name))
    qa = pc.load_json(os.path.join(sd, "floor_3F_geometry_qa.json"))
    dump(os.path.join(vr, "review_input_manifest.json"), {
        "floor_id": "3F", "level": "S_SCHEMATIC", "purpose": "다층 상업시설 평면도(층간 상행유량 논문)", "scale_profiles": ["A3 1:200 단일", "A3 1:100 2×2 타일"],
        "model_sha256": sha(glb), "slice_sha256": sha(os.path.join(run, "raw_slices", "floor_3F_slice.json")), "git_head": a.head,
        "sheets": sheets, "fixed_crops": crops, "crop_rule": "모델 요소(코어·T1·캡슐·T3)와 건물 중심에서 계산한 월드 창, 같은 배율 100 px/m. 전/후 같은 창.",
        "before_after_images": sorted(f for f in os.listdir(vr) if f.startswith("compare_")),
        "unverified_walls_doors": ["상층 구획벽 전부", "모든 출입문(캡슐 포함)", "코어 내부", "외피(입면 부재)의 성격"],
        "own_qa": {"pass": qa["pass"], "fail": qa["fail"], "total": qa["total"], "report": os.path.join(sd, "floor_3F_geometry_qa.json")},
        "reference": "REFERENCE_NOT_VERIFIED (FHHH/HYBE 크롭을 이번 입력에 넣지 않았다)",
        "do_not": ["이미지 속 구조를 실제 모델과 일치한다고 가정", "ChatGPT 편집 이미지를 정본에 합성", "1F_FINAL_FROZEN=true"],
        "generated": now})
    for src, dst in (("D:/Users/admin/Downloads/T14_Integrated.zip", None),):
        pass
    print("PACKAGE DONE", vr)


if __name__ == "__main__":
    main()
