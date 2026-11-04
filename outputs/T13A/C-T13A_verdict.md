# C-T13A 판정 — 1층 도면 Clean Line Pass

- 일자: 2026-11-04
- 브랜치: `claude/t13a-cleanline` (기준: `claude/t13-1f-concept-v2` `891e5bd`, V2-B r2)
- 판정: **ACCEPT (그래픽 정제 후보로, 조건부)** · 사용자 시각 승인 전 · `1F_FINAL_FROZEN=false`
- 18개 프로그램·면적·가구 인벤토리·구조 34개 기둥 원본·코어·튜브·화장실은 V2-B와 동일(QA 게이트로 확인). 출입문은 계속 점선 후보(PROPOSED_ONLY)이고 피난·법규·화장실 슬라이딩 문 검증은 미완료다.

## 실제 도면 (전체 절대 경로)

- 수정 도면: `D:\Users\admin\Desktop\drawing-pipeline-T13A\outputs\T13A\1F_Program_CleanLine_V2A.png` (4961×3508 px = 300.0 dpi) · `.pdf` (실측 420.0×297.0 mm, 1쪽, cairo 벡터, 내장 래스터 이미지 0) · `.svg`
- Before/After 비교판: `D:\Users\admin\Desktop\drawing-pipeline-T13A\outputs\T13A\1F_CleanLine_Before_After.png`
- 전후 크롭 5구간 × 2: `D:\Users\admin\Desktop\drawing-pipeline-T13A\outputs\T13A\crops\` (`crop_01_north_market_before/after.png` … `crop_05_legend_text_*`)
- 래스터↔벡터 비교: `D:\Users\admin\Desktop\drawing-pipeline-T13A\outputs\T13A\1F_CleanLine_Raster_vs_Vector_Check.png`
- 보고서: `line_hygiene_report.json`, `qa_report.json`, `manifest.json` (같은 폴더)

## 원인 진단 (실제 코드 위치와 증거)

| # | 문제 | 있었나 | 발생 함수 | 증거 | 조치 |
|---|---|---|---|---|---|
| 1 | 기하 | 있음 | `program_planner.partition`(래스터 L∞ 분할) → `draw_program_overlay` | 구획 경계 조각 1081개 중 917개가 2 m 미만. 계단 모양 경계가 사선 대시 파편으로 보임 | 경계 노드 병합, 7 m 미만·사선 조각 제외, 축에 정렬한 긴 직선만 유지. 바닥 채움은 래스터 잔여 띠가 섞이기 전 **벡터 복도**(둥근 링+직교 띠)로 |
| 2 | 렌더링 | **없음** | cairosvg | SVG·PDF·PNG 같은 구역 평균 밝기 차 PDF 4.0, PNG 5.5(0~255, 렌더러 안티앨리어싱 차이). 계단 현상은 경로 자체 문제 | PNG를 4096→4961 px(300 dpi)로. SVG→PDF 직접 생성 유지 |
| 3 | 레이어 중복 | 있음 | `draw_program_overlay`(공유 경계 2회), 대지 경계 `site.boundary.buffer(0.0005)` 폴리곤(양면 2회)+후퇴선 겹침 | 점선 중복 비율 **16.6% → 0.1%** | 병합·평행 중복 제거(0.2 m)·구조 격자 겹침 제외, 대지 경계 한 겹 선. 가구 body 고스트는 전후 모두 0 |
| 4 | 표현(의도적 불규칙) | 있음 | `wobble_ring`·`tree_shapes`·`branch_lines`·`plant_bed`·`stipple_points` → `draw_trees`, `design_site` | 참 원이 아닌 식재 윤곽 288개 → 0개, 점묘 점 11137 → 3755 | 수관=참 원+줄기 점, 관목·화단=참 원, 가지·로제트·빗살 제거, 점묘 1/3. **난수열 소비는 그대로라 수목·보행로 위치 불변** |
| 5 | 선 위계 | 있음 | `RESTYLE`(조경·이웃 건물이 가구 토큰 T5와 동급), 프로그램 표시 | before: 조경 외곽·이웃 윤곽·구획 경계가 가구와 같은 0.08~0.12 mm #666~#444 | `restyle_clean`: 조경 0.06 #A8A8A8, 이웃 윤곽 0.08 #8E8E8E, 프로그램 표시(흐름 0.08 #777, 경계 0.055 #8A8A8A, 칩 외곽 0.06 #8A8A8A). 구조 T1~T5 불변 |

수정한 코드: `src/line_hygiene.py`(신규: 호 적합·평활·경로 생성·독립 표본화), `src/monograph_plan_renderer.py`(`Canvas.path_poly/stroke_line` clean 모드), `src/architectural_plan_renderer.py`(`TCanvas`, `restyle_clean`, `draw_trees`, `design_site`, `draw_program_overlay`, 대지 경계, `--cleanline`), `src/program_planner.py`(반환값에 `m06_vector`만 추가. 구획·면적 로직 불변).

## 곡선 정책 (일괄 simplify 없음)

- 구조·가구·문·외피 층: **호(A) 적합만**. 평활 없음. 호로 인정하려면 꼭짓점이 원 위(≤4 mm)이고 변이 원에서 ≤7 mm, 누적 꺾임 일관 조건을 모두 만족해야 한다.
- 조경(landscape·plants) 층만 모서리 28° 보존 Catmull-Rom 베지어 평활(편차 ≤ 5 cm).
- 변환 결과: 호 1123개·베지어 83개. 변환 로그 최대 편차는 구조 층 ≤ 4 mm, 조경 베지어 ≤ 27.5 mm.
- **독립 검증**(변환 로그가 아니라 실제 SVG 경로를 표본화해 before와 쌍으로 비교): 기둥 최대 1.4 mm, 벽·튜브 6.5 mm, 문 3.1 mm, 외피 2.3 mm, 가구 body 6.7 mm. 허용 12 mm 초과 0건.

작업 중 이 독립 검증이 **실제 오류를 잡았다**. (a) 둥근 네모 의자 좌판을 원으로 잘못 변환(모서리 꼭짓점만 원 위에 있어서), (b) 직선에 가까운 열이 큰 원으로 맞는 오판, (c) 시작점=끝점인 폴리라인이 호 하나로 변환돼 도형이 사라지는 오류(벽 6개가 최대 5.6 m 어긋남). 전부 규칙과 단위 시험으로 고쳤다.

## 지표 전후 (SVG)

| | before V2-B | after CleanLine |
|---|---:|---:|
| 요소 수 | 4,544 | 2,108 |
| 꼭짓점·명령 수 | 48,086 | 14,838 (-69%) |
| 호 A / 베지어 C | 0 / 0 | 1,123 / 83 |
| 꺾임 지그재그(선분<1 m, >25°) | 1,672 | 0 |
| 미세 선분(<0.1 mm 종이) | 15,408 | 6,822 |
| 점묘 점 | 11,137 | 3,755 |
| 점선 중복 | 16.6% | 0.1% |
| 참 원 아닌 식재 윤곽 | 288 | 0 |
| 가구 body 겹침·동일 경로 | 0 | 0 |
| SVG 크기 | 1.50 MB | 0.59 MB |

## 5개 확대 구간별 판정

| 구간 | 판정 | 내용 |
|---|---|---|
| 1 북측 시장 | **개선** | 사선 점선 파편·M06 가장자리 계단 제거, 순환 복도가 둥근 링과 직교 띠로 읽힘 |
| 2 중앙 홀 | **개선 + 일부 퇴보** | 파편 제거로 판독성 상승. 반면 M02/M04 등 구획 점선 경계가 대부분 사라져 구획 구분은 ID 칩과 가구 군집에 의존 |
| 3 서측 캡슐 | **개선** | 사선 파편 제거, 캡슐 벽은 정확한 호, 바닥 마감선 간격 2배 |
| 4 필로티·조경 | **개선 + 일부 퇴보** | 흔들리는 수관·가지 선 제거, 점묘 1/3로 질감 정돈. 다만 겹친 원들이 비눗방울처럼 보이고 식재의 풍부함은 줄었다 |
| 5 범례·텍스트 | **미미한 개선** | 범례판을 불투명하게 해서 뒤 잔선 제거. 제목은 아직 "V2-B"로 표기 |

## 테스트·QA (모두 실제 실행)

- 저장소 전체 `unittest discover tests` **40/40 OK**(신규 선 정리 9, 기존 31). 기존 `tests/verify_pipeline.py` 1F **19/19**.
- 산출물 QA 게이트 15개 전부 PASS: A3 420×297 1쪽, 1:500·스케일바 10 m = 20 mm, PNG ≥ 300 dpi, SVG에 래스터 이미지 없음, PDF 내장 이미지 0, 프로그램 18개·면적 V2-B와 동일, 가구 인벤토리 동일, 기둥 34/그림 23(V2-B와 동일), 구조 형상 편차 ≤ 12 mm, 가구 고스트 0, 점선 중복 감소, 지그재그 0, 출입구 승격 0, 문 스윙 충돌 0, 가구-구조 접촉 0.
- 최종 도면은 기존 PNG를 배경으로 깔지 않는다. SVG를 실제 기하에서 생성하고 PDF는 그 SVG에서 직접 만든다.

## 해시 (SHA-256)

- 원본 `.blend`: `30da41d693a967f9628da843f5ec6b6be40f410eeaa209c643d1cb8fdb3f1f1e` (수정하지 않음)
- 1F 슬라이스: `2795a1215a0a3f47c0d2146b06cb643b253c90842d87c5d3e023f8d2535bd006`
- 출력 전체 해시: `manifest.json` (`1F_Program_CleanLine_V2A.svg` 등)

## 해결하지 못한 결함 · 다음 작업

1. 구획 점선 경계가 거의 사라졌다. 축에 정렬한 긴 직선만 남겼기 때문이다. 구획 구분을 도면에서 더 읽히게 하려면 `program_planner`의 래스터 분할을 직교 분할(구조 격자 기준 벡터 분할)로 바꿔야 한다. 이번엔 구획·면적을 바꾸지 않는다는 범위 때문에 하지 않았다.
2. 바닥 채움은 벡터 복도라 M06 338.25 ㎡, P01 227.92 ㎡이고 구획 폴리곤은 363.96·267.16 ㎡다(차이는 래스터 잔여 띠). 범례 면적은 구획 폴리곤 값(V2-B 동일).
3. 수관 원이 겹쳐 보이는 문제와 조경의 풍부함 감소: 수관을 한 겹 원으로 두되 겹침 간격을 두는 조정이 필요할 수 있다.
4. 범례 제목 "V2-B"를 CleanLine 후보로 바꿀지 결정해야 한다.
5. 미세 선분 6,822개는 대부분 격자·해치·점선 조각이라 위생 문제는 아니지만 더 줄일 여지가 있다.
6. 상층 1:100 도면과 DXF에는 이번 선 정리를 적용하지 않았다.
7. 미완료로 남긴 것: 시장·캡슐 출입문 위치·폭·형식(점선 후보), 피난·장애인 접근 법규, 화장실 B/C 슬라이딩 문 직렬화(C-T11B), 보행 최소 실폭.

## 종료 한 줄

`HEAD 891e5bd(+커밋 후 PR) | TESTS 40/40 OK + verify_pipeline 19/19 | MODEL_SHA blend 30da41d6…1f1e · slice 2795a121…d006 | OUTPUTS CleanLine V2A SVG·PDF·PNG·비교판·크롭10·라스터검사·보고서2·manifest | GATE ACCEPT(조건부), 1F_FINAL_FROZEN=false | TOKENS UNKNOWN`
