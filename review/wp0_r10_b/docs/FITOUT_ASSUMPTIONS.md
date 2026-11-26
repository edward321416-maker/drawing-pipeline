# 가구·설비 개발 후보 — 가정, 결과, 한계

모든 항목은 `FIT_OUT_DEVELOPMENT`(설계 개발 후보)입니다. 모형에서 검증된 형상이 아니며 법규·접근성 적합 주장이 아닙니다.
PR #30의 기존 가구·설비(`A-FURN`, `A-FIXT`)와 실 경계·벽·문·기둥은 이동·삭제하지 않았고, 개발 후보는 그 위에 더해 겹침을 검사했습니다
(생성 전후 PR #30 실 폴리곤·항목 WKT 해시 동일 — 검증 T17).

## 요약
- 항목 266개, 좌석 170석(후보). 하드 위반 0건(9개 검사 모두 0).
- 허용오차: {"TOL_AREA_m2": 1e-06, "COVER_EPS_m": 1e-06, "DIST_EPS_m": 1e-09}. 후보가 검사를 통과하지 못하면 **제외**했고 허용오차를 완화하지 않았습니다.
- 모자란 부분: 식음 홀 2-10은 좌석 88석(15.2 ㎡/좌석)에 그칩니다. 지시한 간격(주 동선 3.0 m, 보이드·튜브·코어에서 1.5 m, 기둥 0.6 m 등)을 지키면
  홀 358.3 ㎡만 배치 가능 영역이 되어 더 촘촘하게는 놓을 수 없었습니다. 2-20 식음 점포는 좌석 2석입니다.
  따라서 홀의 이용 방식은 **부분적으로만** 판독됩니다.

## 치수 가정 (종류 → mm → 근거)
‘R10B fit-out brief (task spec)’는 이번 작업의 개발 지시서에 적은 **일반 설계 가정값**이며 모형·PR #30 데이터가 아닙니다. ‘cf.’ 뒤는 저장소 안에서 같은 값이 쓰인 위치입니다.

| 종류 | 개수 | 치수 mm | 근거·가정 |
|---|---:|---|---|
| banquette | 9 | 1800×550; 3600×550 | R10B fit-out brief (task spec): wall banquette 0.55 m deep (cf. src/furniture_library.py:412 banquette 0.55); seat 0.6 m/person = generic design-development assumption |
| cash_counter | 6 | 1200×600 | R10B fit-out brief (task spec): service/cash counter 1.2x0.6 m (cf. src/furniture_library.py:352 cash_counter 1.2x0.6) |
| chair | 132 | 420×420 | R10B fit-out brief (task spec): dining chair 0.42x0.42 m (cf. src/furniture_library.py:26 chair s=0.42); pull-out zone 0.45 m behind = generic design-development assumption |
| dish_table | 2 | 1200×700 | R10B fit-out brief (task spec): dish table 1.2x0.7 m (cf. src/t14s/program.py boh_items (L249-L300): L298 table 1.8x0.8) |
| fridge | 4 | 700×800 | R10B fit-out brief (task spec): reach-in refrigerator 0.7x0.8 m |
| hood | 9 | 1700×800; 2500×800; 3300×800; 900×800 | exhaust hood outline over a range run, 0.8 m deep = range 0.7 m + 0.1 m front overhang (generic design-development assumption); overhead, drawn dashed; ceiling height NOT assumed |
| rack | 4 | 1784×500; 2120×500 | R10B fit-out brief (task spec): shelving rack 0.5 m deep (cf. src/t14s/program.py boh_items (L249-L300): L305 rack 0.5) |
| range | 20 | 800×700 | src/t14s/program.py boh_items (L249-L300): cooking range 0.8x0.7 m (L276-L281) |
| service_counter | 2 | 3000×800 | R10B fit-out brief (task spec): hall service counter 3.0x0.8 m with stools (cf. src/upper_layouts.py:fnb bar counters) |
| shelf | 4 | 1000×450; 1100×450; 1200×450 | R10B fit-out brief (task spec): wall shelf 0.45 m deep (cf. src/t14s/program.py boh_items (L249-L300): L301 wall_strips depth 0.45) |
| sink_double | 6 | 1200×600 | R10B fit-out brief (task spec): double sink 1.2x0.6 m |
| sink_wash | 10 | 700×600 | src/t14s/program.py boh_items (L249-L300): washing sink 0.7x0.6 m (L293) |
| stool | 8 | 360×360 | stool dia 0.36 m = src/furniture_library.py:41 stool r=0.18; pull-out 0.45 m = generic design-development assumption |
| table_2top | 20 | 700×700 | R10B fit-out brief (task spec): 2-top table 0.7x0.7 m |
| table_4top | 27 | 900×900 | R10B fit-out brief (task spec): 4-top table 0.9x0.9 m (cf. src/t14s/fitout.py:_fnb table 0.9x0.9) |
| table_comm | 3 | 2400×900 | R10B fit-out brief (task spec): communal table 2.4x0.9 m, 8 chairs (cf. src/furniture_library.py:402 communal_table) |

보조 가정(코드 `tools/r10b/fitout_r10b.py`): 의자 당김 영역 450 mm, 벤치 좌석 1인 0.6 m, 식음 밀도 상한 1.6 ㎡/좌석, 식음 통로 0.9 m(문–주방 동선 1.2 m),
벽 이격 0.15 m(벤치 0.125 m), 기둥 0.3 m(홀 0.6 m), 기존 가구 0.1 m(홀 0.6 m), 홀 군집 간 1.5 m, 위험물(보이드·튜브·코어·계단)에서 1.5 m, 홀 문 앞 1.2 m 깊이.
후드의 크기(런 길이+100 × 800)는 제 가정이며 천장고는 가정하지 않았습니다.

## 실별 결과
| 실 | 항목 | 좌석 | ㎡/좌석 | 종류별 |
|---|---:|---:|---:|---|
| 2-01 | 7 | 0 | — | {"range": 4, "hood": 1, "sink_double": 1, "fridge": 1} |
| 2-02 | 11 | 9 | 3.31 | {"cash_counter": 1, "banquette": 1, "table_4top": 2, "chair": 6, "table_2top": 1} |
| 2-03 | 29 | 23 | 3.87 | {"cash_counter": 1, "banquette": 1, "table_4top": 5, "chair": 20, "table_2top": 2} |
| 2-04 | 7 | 0 | — | {"range": 4, "hood": 1, "sink_double": 1, "fridge": 1} |
| 2-05 | 5 | 0 | — | {"sink_wash": 2, "dish_table": 1, "shelf": 2} |
| 2-06 | 2 | 0 | — | {"rack": 2} |
| 2-08 | 13 | 11 | 3.73 | {"cash_counter": 1, "banquette": 1, "table_4top": 3, "chair": 8} |
| 2-09 | 7 | 0 | — | {"range": 3, "hood": 2, "sink_double": 1, "fridge": 1} |
| 2-10 | 110 | 88 | 15.2 | {"service_counter": 2, "stool": 8, "banquette": 1, "table_4top": 7, "chair": 74, "table_2top": 15, "table_comm": 3} |
| 2-11 | 7 | 7 | 4.11 | {"banquette": 1, "table_4top": 2, "chair": 4} |
| 2-12 | 3 | 0 | — | {"sink_wash": 2, "shelf": 1} |
| 2-13 | 3 | 0 | — | {"sink_wash": 2, "shelf": 1} |
| 2-14 | 4 | 0 | — | {"range": 2, "hood": 1, "sink_double": 1} |
| 2-15 | 3 | 0 | — | {"range": 2, "hood": 1} |
| 2-16 | 15 | 14 | 4.11 | {"cash_counter": 1, "banquette": 2, "table_4top": 4, "chair": 8} |
| 2-17 | 2 | 0 | — | {"rack": 2} |
| 2-20 | 4 | 2 | 22.5 | {"cash_counter": 1, "table_2top": 1, "chair": 2} |
| 2-21 | 3 | 0 | — | {"sink_wash": 2, "dish_table": 1} |
| 2-22 | 6 | 0 | — | {"range": 3, "hood": 1, "sink_double": 1, "fridge": 1} |
| 2-23 | 2 | 0 | — | {"sink_wash": 2} |
| 2-24 | 5 | 0 | — | {"range": 2, "hood": 2, "sink_double": 1} |
| 2-25 | 18 | 16 | 2.53 | {"cash_counter": 1, "banquette": 2, "table_4top": 4, "chair": 10, "table_2top": 1} |

## 홀 동선
- 주 동선 최소 유효폭: 개발 후 0.0 m, PR만 0.0 m. 개발 후보가 폭을 3 m 미만으로 줄인 표본: 0개.
- 가구에서 1.2 m 이상 떨어진 바닥 비율: 개발 후 0.5534, PR만 0.6772.
- 좁은 곳(약 1.26 m 등)은 PR #30 기하에서 이미 있는 것이며 개발 후보가 만든 것이 아닙니다. 두 개 선에서 0.0 m로 읽히는 구간은 원인을 찾지 못했습니다(KI-14).

| 선 | 길이 m | 최소 유효폭 PR만 | 최소 유효폭 개발 후 | 3 m 미만 표본 |
|---|---:|---:|---:|---:|
| 0 | 15.87 | 3.86 | 3.86 | — |
| 1 | 23.28 | 2.39 | 2.39 | — |
| 2 | 7.05 | 1.94 | 1.94 | — |
| 3 | 25.05 | 4.29 | 4.29 | — |
| 4 | 13.24 | 2.16 | 2.16 | — |
| 5 | 6.45 | 1.26 | 1.26 | — |
| 6 | 30.08 | 2.93 | 2.93 | — |
| 7 | 7.54 | 3.02 | 3.02 | — |
| 8 | 3.75 | 4.99 | 4.99 | — |
| 9 | 6.48 | 5.38 | 5.38 | — |
| 10 | 2.15 | 6.0 | 6.0 | — |
| 11 | 5.05 | 0.0 | 0.0 | — |
| 12 | 6.75 | 2.45 | 2.45 | — |
| 13 | 15.6 | 0.0 | 0.0 | — |
| 14 | 1.85 | 5.72 | 5.72 | — |

## 화장실 (기존 항목만, 추가 없음)
규칙: AGENTS.md 3.2 / params.yaml restroom: >= 1.2 m clear inside the door; general cubicle >= 0.9 x 1.2 m, accessible >= 1.6 x 2.0 m
- "2-07"
- "2-18"
- "2-19"
- "2-26"

문 축 방향 광선 측정으로 제가 독립 확인한 값: 2-07 2.93 m, 2-18 1.68 m, 2-26 3.98 m (생성기 보고 2.99 / 1.73 / 4.00 m). 장애인 큐비클(2-07, 2-19)은 기존 칸막이로 둘러싸이지 않아
크기를 읽을 수 없고 통과로 처리하지 않았습니다.

## 제외된 후보 (17개)
| 실 | 종류 | 사유 |
|---|---|---|
| 2-01 | dishwasher | no free wall run 0.7 x 0.7 m with 1.0 m working aisle outside door swing/apron/existing furniture |
| 2-04 | dishwasher | no free wall run 0.7 x 0.7 m with 1.0 m working aisle outside door swing/apron/existing furniture |
| 2-09 | dishwasher | no free wall run 0.7 x 0.7 m with 1.0 m working aisle outside door swing/apron/existing furniture |
| 2-11 | cash_counter | no free wall run for 1.2x0.6 + 0.9 m front inside the room outside door swing/apron/lane |
| 2-12 | dish_table | no free wall run 1.2x0.7 with 0.9 m aisle |
| 2-13 | dish_table | no free wall run 1.2x0.7 with 0.9 m aisle |
| 2-14 | range | only 2 of the 3-4 ranges fit (0 existing PR range + 2 new): no free wall run with 1.0 m working aisle outside door swings |
| 2-14 | fridge | no free wall run 0.7 x 0.8 m with 1.0 m working aisle outside door swing/apron/existing furniture |
| 2-14 | dishwasher | no free wall run 0.7 x 0.7 m with 1.0 m working aisle outside door swing/apron/existing furniture |
| 2-15 | range | only 2 of the 3-4 ranges fit (0 existing PR range + 2 new): no free wall run with 1.0 m working aisle outside door swings |
| 2-15 | sink_double | no free wall run 1.2 x 0.6 m with 1.0 m working aisle outside door swing/apron/existing furniture |
| 2-15 | fridge | no free wall run 0.7 x 0.8 m with 1.0 m working aisle outside door swing/apron/existing furniture |
| 2-15 | dishwasher | no free wall run 0.7 x 0.7 m with 1.0 m working aisle outside door swing/apron/existing furniture |
| 2-22 | dishwasher | no free wall run 0.7 x 0.7 m with 1.0 m working aisle outside door swing/apron/existing furniture |
| 2-23 | dish_table | no free wall run 1.2x0.7 with 0.9 m aisle |
| 2-24 | fridge | no free wall run 0.7 x 0.8 m with 1.0 m working aisle outside door swing/apron/existing furniture |
| 2-24 | dishwasher | no free wall run 0.7 x 0.7 m with 1.0 m working aisle outside door swing/apron/existing furniture |

주방 아일랜드는 모든 주방의 깊이가 2.6–3.6 m로 4.4 m 기준에 못 미쳐 놓지 않았습니다. 카트·팔레트는 세척·창고실이 9 ㎡ 미만이라 시도하지 않았습니다.

## 검사 로그
`validation/FITOUT_TEST_OUTPUT.txt`(전체 출력), `validation/R10B_GEOMETRY.json` sheets.A-201.fitout_report.
