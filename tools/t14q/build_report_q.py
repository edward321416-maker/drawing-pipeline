"""A3 landscape report for C-T14Q (Korean).  Run: python tools/t14q/build_report_q.py --out <pdf>"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz

R = Path(r"D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14Q\output\C_T14Q_run")
W, H = 1190.55, 841.89
FONT, FONTB = r"C:\Windows\Fonts\malgun.ttf", r"C:\Windows\Fonts\malgunbd.ttf"
INK, MUT, RED, GRN, AMB = (0.08, 0.08, 0.08), (0.38, 0.38, 0.38), (0.72, 0.12, 0.12), (0.12, 0.45, 0.2), (0.75, 0.45, 0.05)


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


class Doc:
    def __init__(self):
        self.d = fitz.open()
        self.n = 0

    def page(self, title, sub=None):
        p = self.d.new_page(width=W, height=H)
        p.insert_font(fontname="mg", fontfile=FONT)
        p.insert_font(fontname="mgb", fontfile=FONTB)
        self.n += 1
        p.insert_text((30, 42), title, fontname="mgb", fontsize=19, color=INK)
        if sub:
            p.insert_text((30, 62), sub, fontname="mg", fontsize=9.5, color=MUT)
        p.insert_text((30, H - 14), "C-T14Q · G-002 위치 정합 실사형 메인 투시도 · 상태: 사람의 건축·시각 최종 승인 대기(HUMAN_REVIEW_PENDING) · 인쇄 승인 아님",
                      fontname="mg", fontsize=7.5, color=RED)
        p.insert_text((W - 60, H - 14), f"{self.n}", fontname="mg", fontsize=8, color=MUT)
        return p


def tb(p, rect, text, size=9.5, bold=False, color=INK):
    p.insert_textbox(fitz.Rect(*rect), text, fontname="mgb" if bold else "mg", fontsize=size, color=color)


def img(p, path, rect):
    import io

    from PIL import Image

    r = fitz.Rect(*rect)
    im = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90, subsampling=0, optimize=True)
    ar = im.width / im.height
    w = r.width
    h = w / ar
    if h > r.height:
        h = r.height
        w = h * ar
    x0 = r.x0 + (r.width - w) / 2
    p.insert_image(fitz.Rect(x0, r.y0, x0 + w, r.y0 + h), stream=buf.getvalue())
    return r.y0 + h


def table(p, x, y, widths, rows, size=8.2, head=True, rowh=None, colors=None):
    cy = y
    for i, row in enumerate(rows):
        lines = 1
        for c, wd in zip(row, widths):
            lines = max(lines, int(len(str(c)) * size * 0.56 / max(wd - 6, 10)) + 1 + str(c).count("\n"))
        rh = rowh or (lines * size * 1.32 + 6)
        cx = x
        for j, (c, wd) in enumerate(zip(row, widths)):
            p.draw_rect(fitz.Rect(cx, cy, cx + wd, cy + rh), color=(0.75, 0.75, 0.75), width=0.4,
                        fill=(0.93, 0.93, 0.93) if (head and i == 0) else None)
            col = INK
            if colors and i > 0 and j in colors:
                col = colors[j](str(c)) or INK
            p.insert_textbox(fitz.Rect(cx + 3, cy + 2, cx + wd - 3, cy + rh), str(c), fontname="mgb" if (head and i == 0) else "mg", fontsize=size, color=col)
            cx += wd
        cy += rh
    return cy


def grade_color(s: str):
    if s.startswith("verified"):
        return GRN
    if s.startswith("assumed") or s.startswith("미확인"):
        return RED
    if s.startswith("likely"):
        return AMB
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    fin = R / "final_q"
    ver = json.loads((fin / "final_verification.json").read_text(encoding="utf-8"))
    day_drift = json.loads((R / "qa_q" / "day_gpt" / "drift_daylight.json").read_text())
    blu_drift = json.loads((R / "qa_q" / "blue_gpt" / "drift_bluehour.json").read_text())
    mem = {k: json.loads((R / "memory_audit" / f"bluehour_{k}.json").read_text(encoding="utf-8-sig")) for k in ("memtest_1600", "memtest_2400", "memtest_3200", "final_4800")}
    day_aud = json.loads((R / "blender_base" / "G002_A_Urban_Daylight" / "G002_daylight_site_context_audit.json").read_text(encoding="utf-8"))
    blu_aud = json.loads((R / "blender_base_v2" / "G002_B_Blue_Hour" / "G002_bluehour_site_context_audit.json").read_text(encoding="utf-8"))
    refs = json.loads((R / "site_context" / "refs" / "refs_manifest.json").read_text(encoding="utf-8"))
    refs = refs["photos"] if isinstance(refs, dict) and "photos" in refs else refs
    D = Doc()

    # ---- 1 summary ----
    p = D.page("G-002 위치 정합 실사형 메인 투시도 — C-T14Q 결과 보고서", "서울 중구 장충단로 247(굿모닝시티 블록) · Blender 기준본 → ChatGPT 실제 편집 → Photoshop 2026 최종 · 2026-11-15")
    img(p, R / "qa_q" / "day_3stage" / "three_stage_overview_daylight.png", (30, 80, W - 30, 330))
    img(p, R / "qa_q" / "blue_3stage_v2" / "three_stage_overview_bluehour.png", (30, 335, W - 30, 585))
    tb(p, (30, 592, 585, 805),
       "완료된 것 (실제 파일로 확인)\n"
       "· Blender Cycles 기준 렌더 Daylight / Blue Hour 4800×2700 (검증 메시 변경 0, A/B 장면 지문 동일)\n"
       "· Chrome ChatGPT 실제 업로드→편집→PNG 다운로드 2종 (각각 1672×941)\n"
       "· Photoshop 2026(27.7.0) 실제 실행: 11레이어 PSD 2종 + 4800×2700 PNG 2종 (원본 Blender 레이어 잠금)\n"
       "· 3단 비교(Blender→ChatGPT→Photoshop), 확대 검수, 메모리 계측, 사진 라이선스 재검증\n\n"
       "미완료 / 제한\n"
       "· 사람의 건축·시각 최종 승인 없음 → 인쇄·제출 승인 아님\n"
       "· ChatGPT 유래 내용의 실효 해상도는 1672 px급 (4800 px는 Preserve Details 확대 + Blender 구조층)\n"
       "· 주변 건물 높이 85.6%, 도로 폭, 가로수·가로등은 가정값 (실측 아님)", 9.2)
    fp = {k: ver[k] for k in ("daylight", "bluehour")}
    tb(p, (600, 592, W - 30, 805),
       "최종 파일 (SHA256 앞 16자)\n"
       f"· Daylight PNG  {sha(fin / 'G002_A_Urban_Daylight_PHOTOSHOP_FINAL.png')[:16]}…  4800×2700, 300 dpi 메타\n"
       f"· Daylight PSD  {sha(fin / 'G002_A_Urban_Daylight_PHOTOSHOP_FINAL.psd')[:16]}…  11 레이어, 9 채널\n"
       f"· BlueHour PNG  {sha(fin / 'G002_B_Blue_Hour_PHOTOSHOP_FINAL.png')[:16]}…  4800×2700, 300 dpi 메타\n"
       f"· BlueHour PSD  {sha(fin / 'G002_B_Blue_Hour_PHOTOSHOP_FINAL.psd')[:16]}…  11 레이어, 9 채널\n\n"
       "경로: D:\\Users\\admin\\Desktop\\중간마감\\drawing-pipeline-T14Q\\output\\C_T14Q_run\\final_q\\\n"
       "비교 이미지: ...\\qa_q\\day_3stage, blue_3stage_v2   메모리 기록: ...\\memory_audit\\\n"
       "원본 보존: blender_base\\ (Daylight 5종), blender_base_v2\\ (Blue Hour), blender_base\\G002_B_Blue_Hour\\ (중단된 최초 시도, 삭제 안 함)", 8.2, False, MUT)

    # ---- 2 location ----
    p = D.page("1. 부지 위치와 G-002 카메라 방향", "좌표 정합: 캐시 world(동/북) = OSM 로컬 + (270.030, 32.811), 회전 0° — 캐시 맥락 정점 892/892이 OSM 건물 정점과 0.1 m 이내 일치")
    img(p, R / "site_context" / "context_pack_plan_v2.png", (30, 75, 640, 810))
    rows = [["항목", "값", "등급"],
            ["대지", "서울 중구 장충단로 247 (을지로6가 18-21·18-220·18-221), 7,792.5 ㎡, 일반상업지역", "likely (로컬 토지이음 조회 2026-10-26)"],
            ["대지 중심 WGS84", "37.5667032°N, 127.0074397°E", "assumed (경계가 OSM 추정)"],
            ["카메라 위치", "37.56436°N, 127.00912°E, 1F 기준 높이 127.7 m, 대지 중심에서 수평 316 m", "verified (T14O 감사값과 일치)"],
            ["시선", "방위 332°(북북서), 하향 18.4°, 55 mm, 화각 36.2°×20.9°", "verified (코드 재현 7 테스트 통과)"],
            ["카메라 위치(건물 기준)", "건물에서 152°(남남동)", "verified"],
            ["태양", "2026-10-17 15:30 KST → 방위 234.3°·고도 25.1° / 18:12 KST → 고도 -4.6°", "assumed (날짜·시각). 기하는 실제 계산, 그림자 방향 실험 검증"],
            ["DDP", "시선 축에서 우측 약 35° 밖 → 화면 밖", "verified"],
            ["시야 맥락 범위", "시선 상단은 지면 약 900 m 앞까지 보임 → 시야 원뿔 ~1.4 km 반영 (기존 캐시는 ±250 m라 배경이 비어 있었음)", "verified"]]
    table(p, 655, 80, [95, 255, 150], rows, 8.0, colors={2: grade_color})

    # ---- 3 context ledger ----
    p = D.page("2. 현실 맥락: 검증 사실 / 태그 값 / 추정값 구분", "OSM 추출 2026-10-26 (ODbL © OpenStreetMap contributors) · 참고 사진 2012–2020 · 아래 '추정'은 렌더에서 사실로 표기하지 않는다")
    nb = len(json.loads((R / "site_context" / "context_pack.json").read_text(encoding="utf-8"))["buildings"])
    rows = [["항목", "값", "근거 / 날짜", "등급"],
            ["이웃 건물 높이", f"OSM 태그(높이·층수) 115동 / 가정 684동 (총 {nb}동, 가정 85.6%)", "OSM 태그 없는 건물은 바닥면적 기반 추정(결정적 해시)", "assumed (684동) / likely (115동)"],
            ["DDP 높이", "29 m (지하3·지상4층)", "서울시 자료. OSM은 20 m로 과소 표기 (화면 밖)", "verified"],
            ["두타 / 현대시티 / 호텔 밀리오레 / 롯데피트인 / apM", "156 / 100 / 91 / 68 / 63 m", "OSM 높이 태그 + 보조 자료(두타는 2차 인용). 건축물대장 원본 미확인", "likely"],
            ["굿모닝시티(대지 내 현 건물)", "렌더에서 제외 (설계안이 대체)", "OSM w358284628 외 1동 제외", "verified (처리 기록)"],
            ["도로 폭", "차선수×3.25 m, 폭 태그 0개", "OSM lanes 태그 17%, 나머지 등급별 기본값", "assumed"],
            ["보도 폭 / 포장", "등급별 1.8–3.15 m / 회색 화강석 판석(참고 사진 2012–2018)", "대지 경계 보정값 3.15 m 재사용", "assumed (폭) / likely (포장 재질)"],
            ["가로수", "1,829그루 배치(수종 불명)", "OSM 수목 태그 사실상 0, 사진엔 소나무류·어린 낙엽수 보임", "assumed"],
            ["가로등", "324개(Blue Hour만, 코브라헤드형 형상 가정)", "OSM 가로등 0, 사진 근거는 형상뿐", "assumed"],
            ["횡단보도·차선", "OSM 횡단 way 29개 / 차선 표시는 규칙 생성", "횡단보도 위치는 태그, 표시선은 생성", "likely / assumed"],
            ["지하철 출구 12·13·14", "대지 남동 모서리 0.5–25 m (OSM)", "카메라 시선 밖(남동 모서리)", "likely"],
            ["신호기·간판·스쿠터·사람", "미확인 → 렌더에 사실로 넣지 않음 (ChatGPT/Photoshop 단계의 생성 요소)", "합법 사진 14장에서 스쿠터 확인 안 됨", "미확인"],
            ["참고 사진", "남동 모서리 2012년 이후 합법 사진 없음", "Wikimedia Commons 14장 (저작자·라이선스 재검증 일치)", "dated"]]
    table(p, 30, 80, [150, 310, 460, 210], rows, 8.3, colors={3: grade_color})

    # ---- 4/5 Daylight ----
    p = D.page("3. Daylight — Blender 기준본 → ChatGPT 편집 → Photoshop 최종", "ChatGPT 열은 1672 px 원본을 비교용으로 2.87× 확대 표시 · 최종본은 4800×2700")
    img(p, R / "qa_q" / "day_3stage" / "three_stage_overview_daylight.png", (30, 78, W - 30, 340))
    for i, k in enumerate(("roof", "mid_garden", "entrance_base")):
        img(p, R / "qa_q" / "day_3stage" / f"three_stage_daylight_{k}.png", (30 + (i % 3) * 0, 345 + i * 150, W - 30, 345 + i * 150 + 146))
    p = D.page("3-1. Daylight 확대 검수 (1:1 크롭 800×440 px)", "지붕 개구·원통 / 중층 정원·기둥 / 저층 진입부·램프 / 우측 가로·가로수 / 좌측 광장")
    for i, k in enumerate(("roof", "mid_garden", "entrance_base", "street_right", "plaza_left")):
        img(p, R / "qa_q" / "day_3stage" / f"three_stage_daylight_{k}.png", (30, 74 + i * 146, W - 30, 74 + i * 146 + 142))

    # ---- 6/7 Blue Hour ----
    p = D.page("4. Blue Hour — Blender 기준본 → ChatGPT 편집 → Photoshop 최종", "1차 Photoshop 결과는 저층 로비 발광이 탁해져 폐기(superseded 보존), 복원층을 어두운 영역에서 제외한 2차를 최종으로 채택")
    img(p, R / "qa_q" / "blue_3stage_v2" / "three_stage_overview_bluehour.png", (30, 78, W - 30, 340))
    for i, k in enumerate(("roof", "mid_garden", "entrance_base")):
        img(p, R / "qa_q" / "blue_3stage_v2" / f"three_stage_bluehour_{k}.png", (30, 345 + i * 150, W - 30, 345 + i * 150 + 146))
    p = D.page("4-1. Blue Hour 확대 검수 (1:1 크롭 800×440 px)", "지붕 / 중층 정원 / 저층 진입부 / 우측 가로 / 좌측 광장")
    for i, k in enumerate(("roof", "mid_garden", "entrance_base", "street_right", "plaza_left")):
        img(p, R / "qa_q" / "blue_3stage_v2" / f"three_stage_bluehour_{k}.png", (30, 74 + i * 146, W - 30, 74 + i * 146 + 142))

    # ---- 8 accuracy ----
    p = D.page("5. 건축 정확성·시각 품질 검수 (자동 계측 + 육안 1차, 독립 사람 검수 대기)")
    bv = day_aud["building_mesh_verification"]
    rows = [["검사", "Daylight", "Blue Hour", "판정"],
            ["건물 메시 (캐시 대비)", f"{bv['objects']}객체 {bv['vertices']:,}정점 {bv['triangles']:,}삼각형, 편차 {bv['max_vertex_deviation_m']} m",
             f"{blu_aud['building_mesh_verification']['vertices']:,}정점, 편차 {blu_aud['building_mesh_verification']['max_vertex_deviation_m']} m", "UNCHANGED (둘 다)"],
            ["A/B 장면 지문 (램프 제외)", day_aud["scene_fingerprint_sha256"][:20] + "…", blu_aud["scene_fingerprint_sha256"][:20] + "…", "동일 → 같은 메시·카메라"],
            ["ChatGPT vs Blender 정합 (탑 블록 중앙 이동)", f"{day_drift['tower']['median_shift_px']} px, 3px 이내 {day_drift['tower']['share_within_3px']*100:.0f}%, 8px 초과 {day_drift['tower']['share_over_8px']*100:.1f}%",
             f"{blu_drift['tower']['median_shift_px']} px, 3px 이내 {blu_drift['tower']['share_within_3px']*100:.0f}%, 8px 초과 {blu_drift['tower']['share_over_8px']*100:.1f}%", "전체 이동 없음, 국소 드리프트만"],
            ["최종 vs Blender 정합 (1672 px 기준)", f"{ver['daylight']['final_vs_blender_registration']['median_shift_px_at_1672']} px, 3px 이내 {ver['daylight']['final_vs_blender_registration']['share_within_3px']*100:.0f}%",
             f"{ver['bluehour']['final_vs_blender_registration']['median_shift_px_at_1672']} px, 3px 이내 {ver['bluehour']['final_vs_blender_registration']['share_within_3px']*100:.0f}%", "구조 위치 유지"],
            ["선예도 (라플라시안 분산)", f"Blender {ver['daylight']['laplacian_variance_blender']} / ChatGPT확대 {ver['daylight']['laplacian_variance_gpt_upscaled']} / 최종 {ver['daylight']['laplacian_variance_final']}",
             f"{ver['bluehour']['laplacian_variance_blender']} / {ver['bluehour']['laplacian_variance_gpt_upscaled']} / {ver['bluehour']['laplacian_variance_final']}", "최종 > ChatGPT 확대, < Blender 원본"],
            ["노출 클리핑", f"백 {ver['daylight']['clipped_white_pct']}% / 흑 {ver['daylight']['crushed_black_pct']}%", f"백 {ver['bluehour']['clipped_white_pct']}% / 흑 {ver['bluehour']['crushed_black_pct']}%", "양호"]]
    y = table(p, 30, 80, [215, 330, 260, 330], rows, 8.5)
    tb(p, (30, y + 14, W - 30, H - 30),
       "관찰된 드리프트와 처리\n"
       "· 수직 핀 리듬이 ChatGPT에서 더 성긴 멀리언 격자로 바뀜(Daylight 지붕·우측 면) → 'TOWER_GEOMETRY_RESTORE' 레이어(Blender 정확 형상 × ChatGPT 저주파 색·빛, 78%)로 복원.\n"
       "· 지붕 아래 좌측 어두운 보이드가 유리 실로 번짐 → 같은 복원층과 마스크로 일부 복원, 완전 일치는 아님(육안 확인).\n"
       "· Blue Hour: ChatGPT가 저층 로비에 따뜻한 조명을 추가(기존 개구부 뒤) → 어두운 영역은 복원층에서 제외해 보존. 최초 버전은 로비가 탁해져 폐기.\n"
       "· ChatGPT 결과에서 새 층·코어·튜브·보이드·지붕 개구·입구 램프가 생기거나 사라진 것은 확인되지 않음 (원 4개, 원통 구조, 정면 슬래브 띠 개수, 중층 정원 슬롯, 램프 쐐기 일치).\n"
       "· 설계안 나무 83그루는 캐시 위치·볼륨을 유지한 채 실제 수관 형태로 교체(조경 look-dev), 건축 메시는 아님.\n\n"
       "한계: 위 검수는 자동 계측과 작성자의 육안 1차이며 독립된 사람 검수가 아니다. 항목별 4/5 이상 점수와 사람의 승인은 받지 않았다. "
       "ChatGPT가 만든 질감·사람·차량은 설계 근거가 아닌 시각화이며 DDP·간판 등 특정 실제 입면을 재현하지 않았다.", 9.0)

    # ---- 9 memory ----
    p = D.page("6. 메모리 계측 기록 (Blue Hour 재렌더 안전성 게이트)", "총 RAM 31.8 GB · RTX 2060 12 GB · 감시자는 Blender만 종료하고 다른 앱은 건드리지 않음 (여유 RAM 하한 설정)")
    rows = [["시험", "해상도 / 샘플", "Blender 최대 작업집합", "시험 중 최저 여유 RAM", "GPU 최대 사용", "결과"]]
    for k, lab in (("memtest_1600", "1600×900 / 16"), ("memtest_2400", "2400×1350 / 16"), ("memtest_3200", "3200×1800 / 16"), ("final_4800", "4800×2700 / 64 (Beauty만)")):
        m = mem[k]
        rows.append([k, lab, f"{m['peak_blender_working_set_gb']} GB", f"{m['min_free_ram_gb_during']} GB (시작 {m['before']['free_ram_gb']} GB)", f"{m['peak_gpu_used_mb']} MB", f"종료코드 {m['exit_code']}, 감시자 중단 {m['aborted_by_watchdog']}"])
    y = table(p, 30, 90, [150, 170, 170, 220, 120, 290], rows, 8.8)
    tb(p, (30, y + 16, W - 30, H - 40),
       "해석\n"
       "· 최초 시도: Daylight 4800×2700/96샘플+ID+Depth는 성공했으나 이어서 시작한 Blue Hour가 '메모리 부족'으로 시스템에 의해 중단됨(저장된 것은 .blend뿐). 기록 보존, 삭제하지 않음.\n"
       "· 샘플 수를 96→64로 줄이는 것만으로 해결됐다고 가정하지 않고, 해상도 단계별 계측을 먼저 수행: 1600→2400에서 작업집합이 1.83→3.20 GB로 증가했으나 3200에서 3.34 GB로 거의 평탄 → 메모리는 해상도보다 장면(약 3 GB)이 지배.\n"
       "· 4800×2700 Beauty는 최대 4.49 GB, 최저 여유 RAM 5.98 GB로 안전 하한(3.5 GB) 위에서 완료(182 s). ID·Depth는 별도 작업으로 분리하고, A/B 장면 지문이 동일해 Daylight의 ID/Depth를 재사용.\n"
       "· GPU는 병목이 아님(최대 1.9 GB / 12 GB). 메모리 부족 재발을 막기 위해 Photoshop(약 1.4–3 GB)은 렌더와 동시에 실행하지 않고 순차 실행했으며, 완료 후 종료.\n"
       "· 사고 기록: 작업 중 Photoshop이 '오류 보고서' 창에서 멈춘 적이 있었음. 보고서 전송 여부는 사용자 결정 사항이라 건드리지 않았고, 창이 사라진 뒤 정상 실행됨.", 9.2)

    # ---- 10 licences ----
    p = D.page("7. 출처·저작자·라이선스 기록", "참고 사진 14장은 시각 참고 전용: 어떤 픽셀도 최종 이미지에 복사·합성하지 않음 → 변형(adaptation) 조건(CC BY-SA 동일조건) 미발생. 저작자 표시는 아래 표로 유지")
    rows = [["ID", "저작자", "라이선스", "촬영/내용"]]
    for r in refs:
        rows.append([r["ref_id"], str(r["author"])[:34], r["licence"], (str(r.get("date_taken", "")) + " · " + str(r.get("what_it_shows", "")))[:92]])
    y = table(p, 30, 80, [40, 190, 90, 395], rows, 7.4)
    rows2 = [["자료", "라이선스 / 조건", "사용 방식"],
             ["OpenStreetMap 추출 (2026-10-26)", "ODbL — © OpenStreetMap contributors, 동일조건·출처표시", "건물·도로·횡단 형상과 일부 높이 태그. 파생 데이터 맥락 팩에 출처 표기"],
             ["Poly Haven asphalt_02 (Rob Tuytel)", "CC0 1.0", "Photoshop 아스팔트 마이크로텍스처(고주파만, 소프트라이트 38%)"],
             ["Poly Haven concrete_pavement_02 (Charlotte Baglioni)", "CC0 1.0", "Photoshop 포장 마이크로텍스처(소프트라이트 32%)"],
             ["ChatGPT 이미지 편집 (Chrome 웹 UI, 로그인 세션)", "서비스 약관", "대화 2건, 업로드 JPEG SHA·다운로드 PNG SHA 기록. 결과는 개념 시각화"],
             ["Blender 4.2.0 / Photoshop 27.7.0", "로컬 설치 앱", "생성형 채우기(크레딧)는 사용하지 않음"]]
    table(p, 30, y + 14, [300, 330, 420], rows2, 8.2)
    tb(p, (30, H - 70, W - 30, H - 24), "개인정보: 조사 에이전트의 Wikimedia 요청 35건 User-Agent에 사용자 이메일이 포함된 사고가 있었다(되돌릴 수 없음). 이후 요청은 개인정보 없는 일반 설정을 사용했고, 로그·문서·GitHub·PDF에는 이메일이 없다(검사함).", 8.4, False, RED)

    # ---- 11 status ----
    p = D.page("8. 완료·미완료 구분과 다음 단계")
    rows = [["항목", "상태", "근거"],
            ["Blender Daylight 4800×2700 + ID + Depth + .blend + audit", "완료", "blender_base\\G002_A_Urban_Daylight (삭제·덮어쓰기 없음)"],
            ["Blender Blue Hour 4800×2700 Beauty", "완료", "blender_base_v2\\G002_B_Blue_Hour, 메모리 게이트 통과 (ID/Depth는 Daylight 재사용)"],
            ["ChatGPT 실제 편집 PNG 2종", "완료", "chatgpt_edits_q\\ (업로드 JPEG·SHA256·대화 URL은 receipt에 기록)"],
            ["Photoshop 실제 실행, PSD 2종 + PNG 2종", "완료", "final_q\\ (PSD 11레이어·9채널, 4800×2700)"],
            ["3단 비교·확대 검수·계측 기록·라이선스 재검증", "완료", "qa_q\\, memory_audit\\, site_context\\refs\\licence_reverification_2026-11-15.json"],
            ["사람의 건축·재료·시각 최종 승인 / 항목별 4-5점 평가", "미완료", "HUMAN_REVIEW_PENDING"],
            ["실측 맥락(지적도, 건물 높이, 도로 폭, 가로수 수종·위치, 간판)", "미완료", "추정값으로만 존재, 표기 규칙 적용"],
            ["ChatGPT 유래 영역의 4800 px 실해상도", "미해결", "원본 1672 px. 4800 px 네이티브 질감은 Blender 구조층에만 존재"],
            ["GitHub 전체 업로드", "부분", "PSD(약 320 MB)와 Blender 4800 px PNG는 용량상 제외, SHA256만 기록"],
            ["main 병합·FREEZE·기존 PR 수정", "수행 안 함", "새 Draft PR만 사용"]]
    y = table(p, 30, 80, [390, 90, 570], rows, 8.8, colors={1: lambda s: GRN if s == "완료" else (RED if s.startswith("미") else AMB)})
    tb(p, (30, y + 16, W - 30, H - 40),
       "다음 단계 권장: (1) 사람이 두 최종 PNG를 확대 검수해 건축 형상·시각 품질 승인/반려 판정, (2) 승인 전에는 G-002를 도면집 정본에 반영하지 않음, (3) 가로수 수종·건물 높이·도로 폭을 실측 자료(지적도·건축물대장·현장 사진)로 교체하면 '추정' 표기를 줄일 수 있음, "
       "(4) 4800 px 실해상도가 필요하면 ChatGPT 대신 Blender의 재질·사람·차량 자산을 보강한 직접 렌더를 늘리는 방법을 검토.", 9.4)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    D.d.save(a.out, deflate=True)
    print("PDF", a.out.resolve(), a.out.stat().st_size, "pages", D.n)


if __name__ == "__main__":
    main()
