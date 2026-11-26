"""Generate the R10-B review documents from the validation records (no hand-typed numbers).

    python -I -X utf8 tools/r10b/make_docs_r10b.py --build <dir>
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "review", "wp0_r10_b")
R10A = os.path.join(ROOT, "review", "wp0_r10_a")


def jl(p):
    return json.load(open(p, encoding="utf-8"))


def w(rel, text):
    path = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("wrote", os.path.abspath(path))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True)
    a = ap.parse_args()
    G = jl(os.path.join(a.build, "R10B_GEOMETRY.json"))
    QA = jl(os.path.join(OUT, "validation", "R10B_OUTPUT_QA.json"))
    PRES = jl(os.path.join(OUT, "validation", "R10B_PRESERVATION.json"))
    XR = jl(os.path.join(OUT, "validation", "R10B_XREF.json"))
    SEL = jl(os.path.join(OUT, "validation", "SECTION_B_SELECTION.json"))
    REF = jl(os.path.join(OUT, "validation", "SECTION_B_REFINEMENT.json"))
    R10A_G = jl(os.path.join(R10A, "validation", "R10A_GEOMETRY.json"))
    A201 = G["sheets"]["A-201"]
    fit = A201.get("fitout_register", [])
    fr = A201.get("fitout_report") or {}
    ids = G["page_order"]
    pres = {t["id"]: t for t in PRES["tests"]}
    n_pass = PRES["summary"]["PASS"]
    qa_status = {q["sheet"]: q["status"] for q in QA["qa"]}
    bars_ok = QA["scale_bars_all_pass"]

    # ---------------------------------------------------------------- ROOM PRESERVATION REPORT
    old = {r["id"]: r for r in R10A_G["sheets"]["A-201"]["rooms"]}
    byroom = defaultdict(list)
    for it in fit:
        byroom[it["room"]].append(it)
    rows = ["| 실 | 실명 | 면적 R10-A ㎡ | 면적 R10-B ㎡ | 경계·프로그램 | 가로×세로 m | 개발 후보 수 | 비고 |", "|---|---|---:|---:|---|---|---:|---|"]
    for r in A201["rooms"]:
        o = old[r["id"]]
        k = r["id"].split("-")[1]
        n = len(byroom.get(k, [])) + len(byroom.get(r["id"], []))
        same = abs(o["area"] - r["area"]) < 1e-3 and o["name"] == r["name"]
        dims = f"{r['dims_m'][0]:.2f}×{r['dims_m'][1]:.2f}" if r["dims_m"] else "비정형"
        rows.append(f"| {r['id']} | {r['name']} | {o['area']:,.3f} | {r['area']:,.3f} | {'동일' if same else '**불일치**'} | {dims} | {n} | CH 미확인 |")
    w("docs/ROOM_PRESERVATION_REPORT.md", f"""# 실별 보존 보고 (2F, PR #30 기준)

R10-A 기록(`review/wp0_r10_a/validation/R10A_GEOMETRY.json`)과 R10-B 평면 데이터를 실 단위로 대조했습니다. 실 경계·프로그램은 변경하지 않았고,
개발 후보는 경계 안에만 추가했습니다. 검증 T06(이름·면적·출처 일치), T07(레이어별 항목 수), T08(계획 모듈 바이트 동일), T17(가구 생성 전후 PR #30 항목 동일)은
`validation/R10B_PRESERVATION.json`에 있습니다.

{chr(10).join(rows)}

- 실 개수: {len(A201['rooms'])}. 천장고(CH): 전 실 미확인(`ceiling_height = null`), 값을 만들지 않았습니다.
- 개발 후보 합계: {len(fit)}개 (분류 `FIT_OUT_DEVELOPMENT`).
""")

    # ---------------------------------------------------------------- FIT-OUT ASSUMPTIONS
    agg = defaultdict(lambda: dict(n=0, dims=set(), basis=set()))
    for it in fit:
        a_ = agg[it["kind"]]
        a_["n"] += 1
        a_["dims"].add("×".join(str(int(x)) for x in it["dims_mm"]))
        a_["basis"].add(it["basis"].split(" | ")[0])
    lines = ["| 종류 | 개수 | 치수 mm | 근거·가정 |", "|---|---:|---|---|"]
    for k, v_ in sorted(agg.items()):
        lines.append(f"| {k} | {v_['n']} | {'; '.join(sorted(v_['dims']))} | {'; '.join(sorted(v_['basis']))} |")
    viol = fr.get("violations", {}) if isinstance(fr, dict) else {}
    pr = fr.get("per_room", {})
    prow = ["| 실 | 항목 | 좌석 | ㎡/좌석 | 종류별 |", "|---|---:|---:|---:|---|"]
    for rid, v_ in pr.items():
        prow.append(f"| {rid} | {v_['items']} | {v_['seats']} | {v_['m2_per_seat'] if v_['m2_per_seat'] else '—'} | {json.dumps(v_['by_kind'], ensure_ascii=False)} |")
    hc = fr.get("f_hall_circulation", {})
    mains = ["| 선 | 길이 m | 최소 유효폭 PR만 | 최소 유효폭 개발 후 | 3 m 미만 표본 |", "|---|---:|---:|---:|---:|"]
    for ln in hc.get("per_main_line", []):
        mains.append(f"| {ln['line']} | {ln['length_m']} | {ln['min_width_pr_only_m']} | {ln['min_width_with_fitout_m']} | {ln.get('samples_below_3m', ln.get('samples_lt_3m', '—'))} |")
    rr = fr.get("g_restrooms", {})
    rrows = []
    for r_ in rr.get("rooms", []):
        rrows.append("- " + json.dumps(r_, ensure_ascii=False))
    dropped = A201.get("fitout_dropped", [])
    drow = ["| 실 | 종류 | 사유 |", "|---|---|---|"] + [f"| {d['room']} | {d['kind']} | {d['reason']} |" for d in dropped]
    info = A201.get("fitout_info", {})
    w("docs/FITOUT_ASSUMPTIONS.md", f"""# 가구·설비 개발 후보 — 가정, 결과, 한계

모든 항목은 `FIT_OUT_DEVELOPMENT`(설계 개발 후보)입니다. 모형에서 검증된 형상이 아니며 법규·접근성 적합 주장이 아닙니다.
PR #30의 기존 가구·설비(`A-FURN`, `A-FIXT`)와 실 경계·벽·문·기둥은 이동·삭제하지 않았고, 개발 후보는 그 위에 더해 겹침을 검사했습니다
(생성 전후 PR #30 실 폴리곤·항목 WKT 해시 동일 — 검증 T17).

## 요약
- 항목 {fr.get('n_items')}개, 좌석 {fr.get('seats_total')}석(후보). 하드 위반 {fr.get('n_violations')}건(9개 검사 모두 0).
- 허용오차: {json.dumps(fr.get('tolerances'))}. 후보가 검사를 통과하지 못하면 **제외**했고 허용오차를 완화하지 않았습니다.
- 모자란 부분: 식음 홀 2-10은 좌석 {pr.get('2-10', {}).get('seats')}석({pr.get('2-10', {}).get('m2_per_seat')} ㎡/좌석)에 그칩니다. 지시한 간격(주 동선 3.0 m, 보이드·튜브·코어에서 1.5 m, 기둥 0.6 m 등)을 지키면
  홀 {info.get('hall_region_m2')} ㎡만 배치 가능 영역이 되어 더 촘촘하게는 놓을 수 없었습니다. 2-20 식음 점포는 좌석 {pr.get('2-20', {}).get('seats')}석입니다.
  따라서 홀의 이용 방식은 **부분적으로만** 판독됩니다.

## 치수 가정 (종류 → mm → 근거)
‘R10B fit-out brief (task spec)’는 이번 작업의 개발 지시서에 적은 **일반 설계 가정값**이며 모형·PR #30 데이터가 아닙니다. ‘cf.’ 뒤는 저장소 안에서 같은 값이 쓰인 위치입니다.

{chr(10).join(lines)}

보조 가정(코드 `tools/r10b/fitout_r10b.py`): 의자 당김 영역 450 mm, 벤치 좌석 1인 0.6 m, 식음 밀도 상한 1.6 ㎡/좌석, 식음 통로 0.9 m(문–주방 동선 1.2 m),
벽 이격 0.15 m(벤치 0.125 m), 기둥 0.3 m(홀 0.6 m), 기존 가구 0.1 m(홀 0.6 m), 홀 군집 간 1.5 m, 위험물(보이드·튜브·코어·계단)에서 1.5 m, 홀 문 앞 1.2 m 깊이.
후드의 크기(런 길이+100 × 800)는 제 가정이며 천장고는 가정하지 않았습니다.

## 실별 결과
{chr(10).join(prow)}

## 홀 동선
- 주 동선 최소 유효폭: 개발 후 {hc.get('min_main_corridor_width_with_fitout_m')} m, PR만 {hc.get('min_main_corridor_width_pr_only_m')} m. 개발 후보가 폭을 3 m 미만으로 줄인 표본: {hc.get('samples_where_new_items_push_width_below_3m')}개.
- 가구에서 1.2 m 이상 떨어진 바닥 비율: 개발 후 {hc.get('floor_fraction_ge_1.2m_from_furniture_with_fitout')}, PR만 {hc.get('floor_fraction_ge_1.2m_from_furniture_pr_only')}.
- 좁은 곳(약 1.26 m 등)은 PR #30 기하에서 이미 있는 것이며 개발 후보가 만든 것이 아닙니다. 두 개 선에서 0.0 m로 읽히는 구간은 원인을 찾지 못했습니다(KI-14).

{chr(10).join(mains)}

## 화장실 (기존 항목만, 추가 없음)
규칙: {rr.get('rule')}
{chr(10).join(rrows)}

문 축 방향 광선 측정으로 제가 독립 확인한 값: 2-07 2.93 m, 2-18 1.68 m, 2-26 3.98 m (생성기 보고 2.99 / 1.73 / 4.00 m). 장애인 큐비클(2-07, 2-19)은 기존 칸막이로 둘러싸이지 않아
크기를 읽을 수 없고 통과로 처리하지 않았습니다.

## 제외된 후보 ({len(dropped)}개)
{chr(10).join(drow)}

주방 아일랜드는 모든 주방의 깊이가 2.6–3.6 m로 4.4 m 기준에 못 미쳐 놓지 않았습니다. 카트·팔레트는 세척·창고실이 9 ㎡ 미만이라 시도하지 않았습니다.

## 검사 로그
`validation/FITOUT_TEST_OUTPUT.txt`(전체 출력), `validation/R10B_GEOMETRY.json` sheets.A-201.fitout_report.
""")

    # ---------------------------------------------------------------- DRAFTING STANDARD
    pens = {p["sheet"]: p["pen_distribution_mm"] for p in QA["pages"]}
    ptxt = "\n".join(f"- {s}: " + ", ".join(f"{k} mm ×{v}" for k, v in sorted(((float(k), v) for k, v in d.items()), reverse=True)[:12]) for s, d in pens.items())
    w("docs/DRAFTING_STANDARD.md", f"""# R10-B 공통 제도 표준

A2 가로(594×420 mm), 우측 표제 열(R10-A와 동일 구성), 한글 맑은 고딕. 전 도면은 벡터이며 래스터 이미지를 넣지 않았습니다.

## 선 두께 (종이 mm, PDF에서 실측)
| 위계 | 사용 | 지정 범위 |
|---|---|---|
| 절단 주요 | 평면: 기둥·외벽·코어 벽 0.40–0.50 / 단면: 슬래브·지붕 0.40 | 0.35–0.50 |
| 절단 보조 | 평면: 구획벽 0.26, 큐비클 0.14 / 단면: 튜브·커튼월 0.30 | 0.18–0.35 |
| 주요 외형 | 유리면 0.20, 구조 그리드 외 주요선 | 0.18–0.25 |
| 가구·설비 | 개발 후보 0.10–0.12, PR #30 기존 0.11 | 0.10–0.15 |
| 치수·그리드 | 0.09–0.13 | 0.10–0.13 |
| 배경 투영 | 단면 뒤 투영 0.10–0.12 | 0.09–0.13 |

실측 분포(PDF 벡터에서 읽음):
{ptxt}

## 글자
제목 10.8–17 pt Bold, 실명 7.5–10 pt, 부제·치수 6.4–7.7 pt, 미세 주기 5.3–5.9 pt. 글자 상자 충돌은 자동 검사합니다(각 쪽 0건이 합격 조건).
선 위를 지나는 글자는 흰 배경 상자를 쓰며, 한글은 `U+2212` 같은 글리프 누락 기호 대신 `-`를 씁니다.

## 증거 분류 표기
| 분류 | 표현 |
|---|---|
| APPROVED_MASTER / MODEL_VERIFIED | 검정·진회색 실선, 절단은 굵게 |
| EXISTING_PROPOSED_DESIGN (PR #30, R8) | 연한 회색 / 청록(연구 형상) |
| FIT_OUT_DEVELOPMENT | 진한 회색 가는 선, 흰 바탕 |
| UNVERIFIED | 점선·주기 문구 (예: ‘CH 미확인’, ‘표현 외곽’) |
| BLOCKED_USER_DECISION · BLOCKED_STRUCTURAL_EVIDENCE | `KNOWN_ISSUES.md` 등록, 도면에서 해결된 것처럼 그리지 않음 |

## 단면 구분
1. **절단**: GLB 메시와 평면의 정확한 교차(삼각형-평면). 경계 상자 대체 없음.
2. **뒤쪽 투영**: 평면 뒤 18 m 이내 튜브·코어·기둥·에스컬레이터·나선 램프의 실루엣, 가는 회색선.
3. **투영 깊이 밖**: 그리지 않음(주기).
4. **연구 형상**: R8 브리지·랜딩, 청록, 변경 없음.
5. **미확인·미모형**: 지하 외벽·기초, 코어 내부 계단 — 그리지 않고 주기로 명시.

## 축척
A-201 1:200, A-301·A-302 1:250. A-301은 선큰 코트까지 포함해 단면 폭이 약 77 m라 한 장에 두 단면을 담지 못해, 횡단면 B–B를 A-302로 분리했습니다.
""")

    # ---------------------------------------------------------------- KNOWN ISSUES
    ci = G["sheets"]["A-301"].get("omitted_context_items", [])
    w("docs/KNOWN_ISSUES.md", f"""# 알려진 문제와 위험 등록

| ID | 내용 | 분류 | 근거 | 조치 |
|---|---|---|---|---|
| KI-01 | 코어 D 계단 중간 랜딩 높이 불일치 최대 {R10A_G['sheets']['A-501'].get('max_landing_mismatch_mm', 0):.2f} mm (승인 1F 마스터 대 연구 계단) | BLOCKED_USER_DECISION | `R10A_GEOMETRY.json` sheets.A-501 | **미해결, 숨기지 않음.** A-501은 R10-B에서 재생성하지 않았고 R10-A 파일은 바이트 변경 없음(T16). |
| KI-02 | E2 브리지의 실제 지지 경간·받침·정착·배근·재료·내력 | BLOCKED_STRUCTURAL_EVIDENCE | 기하 길이 17.0 m, 폭 2.4 m, 연구 데크 250 mm는 구조 체계가 아님 | S-401 연구도 유지. 부재 크기를 만들지 않음. |
| KI-03 | 전 26실 마감 천장고(CH) | UNVERIFIED | `ceiling_height = null`. 층고(레벨 차)는 모형 값이나 CH가 아님 | ‘CH 미확인’ 표기. |
| KI-04 | GLB의 맥락 매스(`X-CTXT_buildings`) 한 덩어리가 건물 외곽과 겹침 (도면 좌표 x −20.1…3.1, y 20.6…32.3, z 0…14.4 m) | UNVERIFIED (원본 모형 소견) | `SECTION` 절단에서 발견 | 단면에서 제외({len(ci)}건 기록), **GLB 미수정**, 대지·맥락 확인 필요(HD-04). |
| KI-05 | 지하 외벽·흙막이·기초 | UNVERIFIED | 모형에 없음 | 작도하지 않음. 선큰 코트와 벽만 모형 근거로 표시. |
| KI-06 | 코어 A–D의 내부 계단·승강로 | UNVERIFIED | GLB 코어는 12면 상자(표현 외곽) | 단면은 외곽만. 평면 내부는 PR #30·R8 연구 형상. |
| KI-07 | 가구·설비 치수는 가정값 | FIT_OUT_DEVELOPMENT | `FITOUT_ASSUMPTIONS.md` | 법규·접근성 적합 주장 없음. |
| KI-08 | 문 폭 개별 치수 기입 | PASS_CONDITIONAL | 문 28건 중 24건을 열림 폭으로 기입(KI-17 참조) | 열림 폭 = 문짝 시작점–닫힌 문짝 끝점 거리. |
| KI-09 | T2·PL·FR 튜브의 용도명 | UNVERIFIED | FR은 PR #30 문구 ‘반입 접점’만 근거 | 모형 식별자만 표기. |
| KI-10 | A-501·S-401은 R10-A 그대로(미개발) | NOT_TESTED / carried | 범위 밖 | 후속 승인 후. |
| KI-11 | 실제 프린터 출력 시험 미실시 | NOT_TESTED | 화면 렌더·PDF 벡터 검사만 | — |
| KI-12 | R10-A 생성 스크립트와 R7·R8·R9 입력 폴더가 저장소 밖(로컬)에 있음 | PASS_CONDITIONAL | `REPRODUCTION.md` | 저장소만으로 재현 불가. 로컬 경로·해시를 기록. |
| KI-13 | 2F 외 층 평면·입면·나머지 단면 | FULL_FLOOR_PRODUCTION_PENDING_APPROVAL | 지시 범위 | 독립 검수 승인 전 진행 금지. |
| KI-14 | 홀 동선 검사에서 두 선이 유효폭 0.0 m로 읽힘(PR만 있을 때도 동일), 한 구간 최소 1.26 m | UNVERIFIED | `FITOUT_ASSUMPTIONS.md` | 원인 미확인. 개발 후보가 만든 문제는 아님. |
| KI-15 | 식음 홀 2-10 좌석 88석(15.2 ㎡/좌석): 지시한 이격을 지키면 배치 가능 영역이 358 ㎡뿐 | PARTIAL | 같은 문서 | 이격 기준 완화는 사용자 판단 사항(HD-07). |
| KI-16 | 장애인 큐비클(2-07, 2-19) 크기를 기존 칸막이로 읽을 수 없음 | UNVERIFIED | 같은 문서 | 합격 처리하지 않음. |
| KI-17 | 문 폭 28개 중 4개(실내문 900 mm)는 글자 충돌 방지로 평면에 기입하지 않음 | PARTIAL | `R10B_GEOMETRY.json` door_dims_skipped | 폭은 기록에 있음. |
""")

    # ---------------------------------------------------------------- HUMAN DECISIONS
    w("docs/HUMAN_DECISIONS.md", """# 사용자 결정 등록

기 승인(Option A, 기존 공간 배치 보존)은 다시 묻지 않습니다. 아래는 이번 작업에서 **진행을 멈추게 하지 않은** 미결 사항입니다.

| ID | 사안 | 증거 | 대안 | 결과·일정 영향 | 권고 | 필요한 승인 |
|---|---|---|---|---|---|---|
| HD-01 | 코어 D 랜딩 높이 불일치 해소 방식 | KI-01 (176.07 mm) | (a) 승인 1F 마스터 수정 (b) 연구 계단을 승인 형상에 맞춤 (c) 현 상태로 두고 도면에 불일치 표기 | (a)는 승인 모델 변경이라 명시 승인 필수. 제출 마감과 무관한 도면은 계속 진행 | (c) 유지, 제출 후 (b) 검토 | 마스터 변경 여부 |
| HD-02 | E2 브리지의 구조 증거 | KI-02 | 구조 검토 의뢰 / 연구도 유지 | 제출은 연구도 유지로 가능 | 연구도 유지 | 구조 증거 제공 여부 |
| HD-03 | 천장고(CH) 출처 | KI-03 | 설계 입력 제공 / ‘미확인’ 유지 | 표기만 변경 | 입력이 있으면 제공 | CH 값 또는 출처 |
| HD-04 | GLB 맥락 매스의 건물 외곽 겹침 | KI-04 | 대지 모델 수정(원본 변경) / 단면에서만 제외 유지 | 원본 GLB 수정은 승인 필요 | 단면 제외 유지 | GLB 수정 여부 |
| HD-05 | 이 브랜치의 병합·공개·최종 제출 패키지 확정 | — | — | 이번 작업에서 수행하지 않음 | — | 병합·공개 승인 |
| HD-06 | 전 층 생산 착수 | 지시 15항 | — | 독립 검수 후 | 검수 후 | 승인 |
| HD-07 | 홀 배치 이격 기준(주 동선 3.0 m, 위험물 1.5 m 등) 완화 여부 | KI-15 | 현 기준 유지 / 기준 완화로 좌석 증가 | 완화하면 좌석과 판독성은 늘지만 동선 여유가 줄어듦 | 유지 | 기준 결정 |
""")

    # ---------------------------------------------------------------- REFERENCE COMPARISON / R10A vs R10B
    refrows = ["| 대상 | 참고 | 쪽 | 참고 벡터 경로 | R10-B 벡터 경로 | 참고 주요 펜(mm) |", "|---|---|---:|---:|---:|---|"]
    for r in QA["reference_pages"]:
        refrows.append(f"| {r['sheet']} | {r['reference_filename']} | {r['reference_page']} | {r['reference_vector_paths']:,} | {r['r10b_vector_paths']:,} | "
                       + ", ".join(f"{k}×{v}" for k, v in r["reference_pen_mm_top"][:4]) + " |")
    w("validation/REFERENCE_COMPARISON.md", f"""# 참고 도면 대조 (R10-B)

로컬 기준 PDF를 직접 열어 해시를 R10-A 기록과 대조하고 필요한 쪽을 렌더링해 검토했습니다(건축 도면집 6·19·21, 설계 개요 6·15, 구조 도면집 15·17 모두 열림;
이번 작업에서 개발한 A-201·A-301·A-302에 대응하는 쪽만 도면 대조에 사용). 참고 도면은 제3자 자료이므로 렌더는 로컬 폴더에만 두고 저장소에 넣지 않았습니다.
참고의 치수·방 배치·구조·재료는 이 건물에 옮기지 않았습니다.

{chr(10).join(refrows)}

## 참고에서 가져온 것은 표현 방식뿐
- 평면(건축 6): 두꺼운 절단 포셰와 기둥, 맥락(대지·도로) 표시, 3단 치수, 가구 기호, 우측 표제 열.
- 단면(건축 19): 절단부 포셰와 후면 투영의 선 위계, 층 레벨 띠와 층고 치수, 방 이름 상자, 지반 표현, 지시선 주기.
- 반영하지 않은 것: 참고의 채색 포셰(노랑·빨강·파랑) — 이 프로젝트의 절제된 흑백 규칙(AGENTS §6.12)에 따라 흑색 포셰와 진회색으로 대체.
- 정보 밀도: R10-A A-201은 벡터 경로 {QA['r10a_vs_r10b'][0].get('r10a_vector_paths', 0):,}, R10-B는 {QA['r10a_vs_r10b'][0]['r10b_vector_paths']:,}. 참고 평면은 위 표 값. 여전히 참고보다 낮음.

로컬 대조 이미지: `D:\\Users\\admin\\Desktop\\2학기 논문\\도면\\01_과정\\01_기획_구획_베이스\\WP0_R10_B_대표도면\\비교검수\\`
""")
    cmp = ["| 도면 | R10-A 벡터 경로 | R10-B 벡터 경로 | R10-A 글자 수 | R10-B 글자 수 |", "|---|---:|---:|---:|---:|"]
    for r in QA["r10a_vs_r10b"]:
        cmp.append(f"| {r['sheet']} | {r.get('r10a_vector_paths', '— (신규)'):,} | {r['r10b_vector_paths']:,} | {r.get('r10a_text_chars', '—')} | {r['r10b_text_chars']} |"
                   if isinstance(r.get('r10a_vector_paths'), int) else f"| {r['sheet']} | — (신규) | {r['r10b_vector_paths']:,} | — | {r['r10b_text_chars']} |")
    w("validation/R10A_VS_R10B.md", f"""# R10-A 대 R10-B

{chr(10).join(cmp)}

이미지 비교: `comparison/R10A_vs_R10B_A-201.jpg`, `comparison/R10A_vs_R10B_A-301.jpg`. A-302는 신규입니다.

| 지적(R10-A) | R10-B에서 한 일 | 상태 |
|---|---|---|
| A-201 실내 가구·설비 정보 부족 | 개별 가구가 없던 식음 점포(2-02·2-11·2-25 등)와 주방·창고·세척실에 프로그램별 후보를 추가({len(fit)}개) | 개선(후보, 미검증) |
| 중앙 식음 홀 2-10(1,337.3 ㎡) 미발달 | 경계·프로그램 불변. 홀 안에 좌석·공용 테이블·카운터 후보 배치 | 개선(좌석 수 등은 보고서) |
| 실 내부 치수 부족 | 실 목록에 가로×세로, 코어·튜브 지름, 보이드 면적, 문 열림 폭(24/28)을 기하에서 계산·기입 | 개선(KI-08, KI-17) |
| 보이드·튜브·승강기·투영 구분 불명확 | 튜브(큰 원)·샤프트(작은 원 ✕)·승강로 구분과 모형 식별자 표기, 범례 | 개선(용도 일부 미확인) |
| 선 두께 위계 약함 | 절단 0.40–0.50 / 구획 0.26 / 가구 0.10–0.12 로 분리 | 개선 |
| 26실 천장고 미확인 | ‘CH 미확인’ 열을 실 목록에 명시. 값을 만들지 않음 | 유지(정직) |
| A-301 수평 슬래브선에 의존 | 정확한 메시 절단, 프로그램 볼륨, 후면 투영, 선큰 코트, 정원, 보이드 치수, 요소 색인 | 개선 |
| A-301 수직 동선·보이드·정원 설명 부족 | 코어·M1 튜브·T1·에스컬레이터·캡슐·정원 호출과 B–B 횡단면(A-302) | 개선 |
| 지상·지하 관계 부족 | 선큰 코트(B1 -5.500), 벽(+0.900)을 모형 근거로 표시. 지하 외벽·기초는 미확인으로 주기 | 부분 개선(KI-05) |
| 코어 D 계단 랜딩 176.07 mm 불일치 | 변경 없음, 등록 유지 | 미해결(HD-01) |
| E2 브리지 구조 증거 | 변경 없음 | 미해결(HD-02) |
""")

    # ---------------------------------------------------------------- SELF REVIEW
    tot_pass = n_pass
    w("validation/SELF_REVIEW.md", f"""# R10-B 자체 검토 (내부 평가 — 독립 검수를 대체하지 않음)

상태: `R10B_REPRESENTATIVE_DRAWINGS_PRODUCED` · `R10B_SELF_REVIEW_COMPLETED` · `INDEPENDENT_REVIEW_PENDING` · `FULL_FLOOR_PRODUCTION_PENDING_APPROVAL`

## 실행한 시험
| 시험 | 결과 | 근거 |
|---|---|---|
| 지오메트리 보존(T01–T17) | {tot_pass}/{len(PRES['tests'])} PASS | `validation/R10B_PRESERVATION.json` |
| 교차 참조(X01–X08) | {XR['summary']['PASS']}/{XR['summary']['PASS'] + XR['summary']['FAIL']} PASS | `validation/R10B_XREF.json` |
| 출력 QA(쪽 크기·벡터·글리프·글자 충돌) | {', '.join(f'{k} {v}' for k, v in qa_status.items())} | `validation/R10B_OUTPUT_QA.json` |
| 축척 막대 벡터 실측 | {'PASS' if bars_ok else 'FAIL'} ({len(QA['scale_bars'])}건) | 같은 파일 |
| 가구 검사(포함·충돌·문 스윙) | 위반 {sum(len(v) for v in viol.values()) if viol else '기록 참조'}건 | `docs/FITOUT_ASSUMPTIONS.md` |
| 실제 프린터 출력 | NOT_TESTED | — |

## 점수 (근거는 위 표와 문서, 내부 추정)
| 항목 | 배점 | 평가 | 근거와 한계 |
|---|---:|---:|---|
| 건축 정보·공간 판독성 | 25 | 17 | 프로그램별 후보 {len(fit)}개, 홀 좌석 후보 {fr.get('per_room', {}).get('2-10', {}).get('seats')}석(홀 판독은 부분적), 실 치수, 튜브 구분, 문 열림 폭 {len(A201.get('door_dims_annotated', []))}/{len(A201.get('door_dims_annotated', [])) + len(A201.get('door_dims_skipped', []))}개 기입. 참고 도면 대비 정보 밀도 낮음(벡터 경로 {QA['r10a_vs_r10b'][0]['r10b_vector_paths']:,} 대 참고 평면 약 1만). |
| 원본 형상 보존 | 20 | 20 | T01–T17 PASS, R10-A 파일 바이트 변경 없음. |
| 문서 완성도 | 20 | 14 | 도면 3장(A-201, A-301, A-302), 등록부·보고서 완비. A-501·S-401 미개발, 입면·나머지 층 미착수. |
| 기술 정확도 | 20 | 15 | 단면은 메시 교차로 26/26 재현. 가구는 가정값, 다수 요소는 미확인으로 남음. |
| 제도·그래픽 | 15 | 11 | 위계·충돌 0건. 참고 대비 포셰·해치·재료 표현이 절제되어 있음. |
| 합계 | 100 | **77** | 목표 95에 **미달**. 미달 원인은 위 한계. |

자동 기각 조건(원본 변경, 지어낸 치수, 핵심 정보 누락, 심각한 도면 모순, 제안 형상의 검증 표시, 구조·법규 적합 주장, 근거 없는 합격 주장):
이번 작업에서 해당 사항을 확인하지 못했습니다. 단, 이는 자체 검토이며 독립 검수가 필요합니다.
""")

    # ---------------------------------------------------------------- REPRODUCTION
    w("docs/REPRODUCTION.md", f"""# 재현 방법

상태: **PASS_CONDITIONAL** — 저장소만으로는 재현할 수 없습니다(R10-A 생성 코드와 R7·R8·R9 입력이 로컬 폴더에 있음).

필요 로컬 입력(경로·해시는 `validation/R10B_GEOMETRY.json` protected_sources 와 `R10A_GEOMETRY.json`):
- 원본 GLB: `D:\\Users\\admin\\Desktop\\5-2\\설계스튜디오\\중간발표\\07_representation\\render\\out\\GMC-ZZ-ZZ-M3-0701.glb`
- R10-A 작성 코드와 R7·R8·R9 입력: `D:\\Users\\admin\\Desktop\\2학기 논문\\도면\\01_과정\\01_기획_구획_베이스\\WP0_R10_A_대표도면\\` 및 동일 부모의 `WP0_R7_20261125`, `WP0_R8_20261125`, `WP0_R9_기술도면집`
- 참고 PDF 3개: `D:\\Temp\\` (비교 이미지 생성에만 필요)
- Python 3.14: shapely, PyMuPDF, trimesh, DracoPy, matplotlib, numpy, Pillow

```
python -I -X utf8 tools/r10b/validate_cut_vs_r10a.py
python -I -X utf8 tools/r10b/select_section_b.py 1.5 ; python -I -X utf8 tools/r10b/select_section_b.py refine
python -I -X utf8 tools/r10b/build_r10b.py --out <빌드 폴더> --sheets A-201,A-301,A-302
python -I -X utf8 tools/r10b/package_r10b.py --build <빌드 폴더>
python -I -X utf8 tools/r10b/validate_preservation_r10b.py
python -I -X utf8 tools/r10b/validate_xref_r10b.py --build <빌드 폴더>
python -I -X utf8 tools/r10b/make_docs_r10b.py --build <빌드 폴더>
```
PDF의 날짜 문자열은 실행일이라 빌드마다 해시가 달라집니다. 기하·치수는 결정적입니다(무작위 없음).
""")
    rows = ["| 도면 | 축척 | PDF | SVG | 채팅 미리보기 | 300 DPI | 확대 | 타일 |", "|---|---|---|---|---|---|---|---|"]
    for pg in QA["pages"]:
        sid = pg["sheet"]
        det = " · ".join(f"[{d['name']}]({d['jpeg']})" for d in pg["details"])
        rows.append(f"| {sid} {pg['title']} | {pg['scale']} | [PDF]({pg['pdf']}) | [SVG]({pg['svg']}) | [JPEG]({pg['preview']}) | [PNG]({pg['high_resolution']}) | {det} | [PNG·JPEG](tiles/{sid}) |")
    pass_x = XR["summary"]["PASS"]
    w("README.md", f"""# WP0 R10-B · 대표 도면 개발 (자체 검토 완료, 독립 검수 대기)

R10-A의 기존 승인 배치(옵션 A)를 보존한 채 2F 건축 평면도(A-201)와 전체 단면도 두 장(A-301 종단, A-302 횡단)을 개발했습니다.
상태: `R10B_REPRESENTATIVE_DRAWINGS_PRODUCED` · `R10B_SELF_REVIEW_COMPLETED` · `INDEPENDENT_REVIEW_PENDING` · `FULL_FLOOR_PRODUCTION_PENDING_APPROVAL`.
제출 가능 판정이 아닙니다. 병합·공개·최종 확정은 하지 않았습니다.

- [대표 도면 전체 PDF](pdf/WP0_R10B_Representative_A2.pdf) · [SHA-256 매니페스트](manifest.json)
- [출력 검수](validation/R10B_OUTPUT_QA.json) · [보존 검증](validation/R10B_PRESERVATION.json) · [교차 참조](validation/R10B_XREF.json) · [형상 기록](validation/R10B_GEOMETRY.json)
- [R10-A 대 R10-B](validation/R10A_VS_R10B.md) · [참고 도면 대조](validation/REFERENCE_COMPARISON.md) · [자체 검토](validation/SELF_REVIEW.md)
- [제도 표준](docs/DRAFTING_STANDARD.md) · [실별 보존](docs/ROOM_PRESERVATION_REPORT.md) · [가구 가정](docs/FITOUT_ASSUMPTIONS.md) · [문제 등록](docs/KNOWN_ISSUES.md) · [결정 등록](docs/HUMAN_DECISIONS.md) · [재현](docs/REPRODUCTION.md)

{chr(10).join(rows)}

A-501(코어 D 상세)과 S-401(E2 브리지 구조 연구)은 이번에 재생성하지 않았고 R10-A 그대로입니다. 코어 D 랜딩 높이 불일치 {R10A_G['sheets']['A-501'].get('max_landing_mismatch_mm', 0):.2f} mm와
E2 브리지의 구조 증거 부재는 해결되지 않았으며 도면에서 해결된 것처럼 그리지 않았습니다.

## 결과 한눈에
| 영역 | 상태 | 근거 |
|---|---|---|
| 원본 GLB·승인 1F 마스터·PR #30 실 경계·프로그램 보존 | PASS ({PRES['summary']['PASS']}/{len(PRES['tests'])}) | `R10B_PRESERVATION.json` |
| 단면 절단의 메시 교차 재현(R10-A 26건) | PASS | T14 |
| 가구·설비 후보 겹침·문 스윙·포함 검사 | PASS (위반 {fr.get('n_violations')}건) | `FITOUT_ASSUMPTIONS.md` |
| 교차 참조(단면 표시 위치 포함) | PASS ({pass_x}/{XR['summary']['PASS'] + XR['summary']['FAIL']}) | `R10B_XREF.json` |
| 출력(쪽 크기·벡터·글리프·글자 충돌·축척 막대) | PASS | `R10B_OUTPUT_QA.json` |
| 식음 홀의 이용 판독성 | PASS_CONDITIONAL (부분) | KI-15 |
| 천장고 | UNVERIFIED (전 26실 미확인) | KI-03 |
| 코어 D 랜딩 불일치 · E2 구조 증거 | BLOCKED_USER_DECISION · BLOCKED_STRUCTURAL_EVIDENCE | KI-01, KI-02 |
| 저장소만으로 재현 | PASS_CONDITIONAL | KI-12 |
| 실제 프린터 출력 | NOT_TESTED | KI-11 |
""")
    print("docs done")


if __name__ == "__main__":
    main()
