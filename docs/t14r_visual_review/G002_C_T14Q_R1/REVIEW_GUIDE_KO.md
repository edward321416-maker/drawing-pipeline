# G-002 GitHub 검수 가이드 (C-T14R · 패킷 G002_C_T14Q_R1)

**상태:** `PACKET_VERIFIED_LOSSLESS` · `INDEPENDENT_VISUAL_REVIEW_PENDING` · 건축 정확성·시각 품질 **승인 아님**.

이 폴더의 모든 이미지는 4800×2700 최종 PNG(Photoshop 2026)에서 **픽셀을 바꾸지 않고** 자른 무손실 PNG이거나(`images/…/tiles`, `focus/`), 열람용 JPEG 미리보기입니다. 원본 PNG는 수정하지 않았고 SHA256으로만 연결됩니다.

## 1. 먼저 열 것

- 전체 요약판: [`overview.jpg`](overview.jpg) (138 KiB)
- Daylight 전체 미리보기 1600×900: [`images/DAYLIGHT_FINAL/preview.jpg`](images/DAYLIGHT_FINAL/preview.jpg)
- Blue Hour 전체 미리보기 1600×900: [`images/BLUEHOUR_FINAL/preview.jpg`](images/BLUEHOUR_FINAL/preview.jpg)
- 모든 타일 목록과 SHA256: [`README.md`](README.md), 기계 판독: [`manifest.json`](manifest.json), 영역→타일 색인: [`regions.json`](regions.json)
- 무결성 보고: [`INTEGRITY_REPORT.json`](INTEGRITY_REPORT.json)

## 2. 원본 정보

| 이미지 | 원본 SHA256 | 해상도 | 타일 수 | 픽셀 SHA256(RGB) |
|---|---|---|---|---|
| DAYLIGHT_FINAL | `b99cc66cdadd72be52461c25b0002cbb5ab08add26dc3a7933e3f1e4f12af80b` | 4800×2700 | 78 | `db38eb3e98044336…` |
| BLUEHOUR_FINAL | `ad5b9b07033ab258201173b48042849d3cf6575756511d103c6f3970129b1f57` | 4800×2700 | 75 | `1d5065421b620c92…` |

좌표는 원본 이미지의 왼쪽 위가 (0,0)이고 단위는 픽셀입니다. 타일 파일명은 `x{X}_y{Y}_w{W}_h{H}.png` 입니다.

## 3. 검수 영역 지도 (같은 카메라이므로 두 이미지의 좌표가 같습니다)

영역 박스는 눈으로 배치한 근사값이며 도면 좌표가 아닙니다. '대표 포커스'는 원본에서 잘라낸 **무손실 512 px급 크롭**(각 ≤400 KiB)입니다.

| 영역 | 확인할 것 | Daylight 대표 포커스 | Blue Hour 대표 포커스 | 영역 겹침 타일(D/B) |
|---|---|---|---|---|
| **R1_roof** 지붕 원형 개구부와 옥상 정원<br>박스 [[1560, 30, 3300, 480]] | 원형 개구 4개, 옥상 원통 구조물, 옥상 정원 윤곽, 지붕 모서리 | [1760,20..2272,532](focus/F04_roof_left_opening__DAYLIGHT_FINAL__x01760_y00020_w0512_h0512.png) · 371 KiB `F04_roof_left_opening`<br>[2780,40..3292,552](focus/F06_roof_right_cylinder_garden__DAYLIGHT_FINAL__x02780_y00040_w0512_h0512.png) · 383 KiB `F06_roof_right_cylinder_garden` | [1760,20..2272,532](focus/F04_roof_left_opening__BLUEHOUR_FINAL__x01760_y00020_w0512_h0512.png) · 357 KiB `F04_roof_left_opening`<br>[2780,40..3292,552](focus/F06_roof_right_cylinder_garden__BLUEHOUR_FINAL__x02780_y00040_w0512_h0512.png) · 333 KiB `F06_roof_right_cylinder_garden` | 12 / 12 |
| **R2_fins** 상층부 수직 파사드 핀<br>박스 [[1650, 480, 2230, 1250], [2380, 480, 3260, 1250]] | 수직 핀 간격·개수와 수평 띠 위치. C-T14Q 검수의 미해결 항목 | [2544,544..3056,1056](focus/F01_fins_right_upper__DAYLIGHT_FINAL__x02544_y00544_w0512_h0512.png) · 366 KiB `F01_fins_right_upper`<br>[2500,1560..3012,2072](focus/F02_fins_right_lower__DAYLIGHT_FINAL__x02500_y01560_w0512_h0512.png) · 377 KiB `F02_fins_right_lower`<br>[1700,700..2212,1212](focus/F03_fins_left_upper__DAYLIGHT_FINAL__x01700_y00700_w0512_h0512.png) · 392 KiB `F03_fins_left_upper` | [2544,544..3056,1056](focus/F01_fins_right_upper__BLUEHOUR_FINAL__x02544_y00544_w0512_h0512.png) · 339 KiB `F01_fins_right_upper`<br>[2500,1560..3012,2072](focus/F02_fins_right_lower__BLUEHOUR_FINAL__x02500_y01560_w0512_h0512.png) · 336 KiB `F02_fins_right_lower`<br>[1700,700..2212,1212](focus/F03_fins_left_upper__BLUEHOUR_FINAL__x01700_y00700_w0512_h0512.png) · 345 KiB `F03_fins_left_upper` | 15 / 15 |
| **R3_mid_void** 중층부 보이드와 정원<br>박스 [[1700, 1150, 3250, 1480]] | 중층 개방 슬롯, 기둥, 정원 식재, 슬롯 안 원통 | [2450,1150..2962,1662](focus/F07_mid_slot_right__DAYLIGHT_FINAL__x02450_y01150_w0512_h0512.png) · 378 KiB `F07_mid_slot_right`<br>[1850,1150..2362,1662](focus/F08_mid_notch_left__DAYLIGHT_FINAL__x01850_y01150_w0512_h0512.png) · 389 KiB `F08_mid_notch_left` | [2450,1150..2962,1662](focus/F07_mid_slot_right__BLUEHOUR_FINAL__x02450_y01150_w0512_h0512.png) · 337 KiB `F07_mid_slot_right`<br>[1850,1150..2362,1662](focus/F08_mid_notch_left__BLUEHOUR_FINAL__x01850_y01150_w0512_h0512.png) · 356 KiB `F08_mid_notch_left` | 10 / 10 |
| **R4_cores** 코너 코어<br>박스 [[2140, 280, 2380, 2280], [3150, 200, 3300, 1900], [1540, 60, 1690, 1750]] | 화면에서 보이는 코어 3개. 네 번째 코어는 이 카메라에서 가려짐 | [2004,900..2516,1412](focus/F09_core_front__DAYLIGHT_FINAL__x02004_y00900_w0512_h0512.png) · 377 KiB `F09_core_front`<br>[2980,600..3492,1112](focus/F10_core_right__DAYLIGHT_FINAL__x02980_y00600_w0512_h0512.png) · 374 KiB `F10_core_right` | [2004,900..2516,1412](focus/F09_core_front__BLUEHOUR_FINAL__x02004_y00900_w0512_h0512.png) · 356 KiB `F09_core_front`<br>[2980,600..3492,1112](focus/F10_core_right__BLUEHOUR_FINAL__x02980_y00600_w0512_h0512.png) · 340 KiB `F10_core_right` | 26 / 26 |
| **R5_tubes** 수직 튜브 (T1–T4 계열, 지붕·중층·지상)<br>박스 [[2150, 100, 3050, 430], [2450, 1200, 3150, 1480], [2500, 1780, 2800, 2080]] | 원통형 튜브의 지붕 상단, 중층 슬롯, 지상 진입부. T1–T4 번호 대응은 도면 대조가 필요 | [2300,100..2812,612](focus/F05_roof_tubes__DAYLIGHT_FINAL__x02300_y00100_w0512_h0512.png) · 387 KiB `F05_roof_tubes`<br>[2450,1760..2962,2272](focus/F11_tube_ground__DAYLIGHT_FINAL__x02450_y01760_w0512_h0512.png) · 379 KiB `F11_tube_ground` | [2300,100..2812,612](focus/F05_roof_tubes__BLUEHOUR_FINAL__x02300_y00100_w0512_h0512.png) · 337 KiB `F05_roof_tubes`<br>[2450,1760..2962,2272](focus/F11_tube_ground__BLUEHOUR_FINAL__x02450_y01760_w0512_h0512.png) · 341 KiB `F11_tube_ground` | 10 / 9 |
| **R6_entrance** 저층부 진입 램프와 1층 기둥<br>박스 [[2150, 1750, 3000, 2330]] | 램프 쐐기, 1층 기둥열, 캐노피, 선큰 진입 | [2200,1900..2712,2412](focus/F12_entrance_ramp__DAYLIGHT_FINAL__x02200_y01900_w0512_h0512.png) · 370 KiB `F12_entrance_ramp` | [2200,1900..2712,2412](focus/F12_entrance_ramp__BLUEHOUR_FINAL__x02200_y01900_w0512_h0512.png) · 338 KiB `F12_entrance_ramp` | 6 / 5 |
| **R7_streets** 건물 주변 도로·횡단보도<br>박스 [[500, 2000, 4800, 2700]] | 차로, 차선, 횡단보도, 보도, 가로수 배치 | [1700,2188..2212,2700](focus/F13_crosswalk_plaza_edge__DAYLIGHT_FINAL__x01700_y02188_w0512_h0512.png) · 380 KiB `F13_crosswalk_plaza_edge`<br>[3500,2000..3971,2471](focus/F14_avenue_trees_cars__DAYLIGHT_FINAL__x03500_y02000_w0471_h0471.png) · 388 KiB `F14_avenue_trees_cars` | [1700,2188..2212,2700](focus/F13_crosswalk_plaza_edge__BLUEHOUR_FINAL__x01700_y02188_w0512_h0512.png) · 340 KiB `F13_crosswalk_plaza_edge`<br>[3500,2000..3971,2471](focus/F14_avenue_trees_cars__BLUEHOUR_FINAL__x03500_y02000_w0471_h0471.png) · 351 KiB `F14_avenue_trees_cars` | 17 / 17 |
| **R8_context** 실제 위치와 연결되는 도시 맥락<br>박스 [[0, 0, 1560, 900], [3300, 150, 4800, 1800]] | 이웃 건물 규모감, 스카이라인, 유리 커튼월 건물. 높이 다수는 가정값 | [300,100..812,612](focus/F15_context_skyline__DAYLIGHT_FINAL__x00300_y00100_w0512_h0512.png) · 362 KiB `F15_context_skyline`<br>[3600,700..4112,1212](focus/F16_context_glass_tower__DAYLIGHT_FINAL__x03600_y00700_w0512_h0512.png) · 352 KiB `F16_context_glass_tower` | [300,100..812,612](focus/F15_context_skyline__BLUEHOUR_FINAL__x00300_y00100_w0512_h0512.png) · 341 KiB `F15_context_skyline`<br>[3600,700..4112,1212](focus/F16_context_glass_tower__BLUEHOUR_FINAL__x03600_y00700_w0512_h0512.png) · 362 KiB `F16_context_glass_tower` | 32 / 31 |

## 4. 수직 파사드 핀 복원 (C-T14Q에서 미해결로 남은 항목)

비교 크롭(같은 픽셀 박스): 왼쪽 Blender 기준본, 오른쪽 최종본.

| 영역 | Blender 기준본 (Daylight) | 최종 (Daylight) | Blender 기준본 (Blue Hour) | 최종 (Blue Hour) |
|---|---|---|---|---|
| `F01_fins_right_upper` | [2544,544..3056,1056](focus/F01_fins_right_upper__DAYLIGHT_FINAL__REFERENCE_BLENDER_BASE__x02544_y00544_w0512_h0512.png) · 205 KiB | [2544,544..3056,1056](focus/F01_fins_right_upper__DAYLIGHT_FINAL__x02544_y00544_w0512_h0512.png) · 366 KiB | [2544,544..3056,1056](focus/F01_fins_right_upper__BLUEHOUR_FINAL__REFERENCE_BLENDER_BASE__x02544_y00544_w0512_h0512.png) · 128 KiB | [2544,544..3056,1056](focus/F01_fins_right_upper__BLUEHOUR_FINAL__x02544_y00544_w0512_h0512.png) · 339 KiB |
| `F02_fins_right_lower` | [2500,1560..3012,2072](focus/F02_fins_right_lower__DAYLIGHT_FINAL__REFERENCE_BLENDER_BASE__x02500_y01560_w0512_h0512.png) · 208 KiB | [2500,1560..3012,2072](focus/F02_fins_right_lower__DAYLIGHT_FINAL__x02500_y01560_w0512_h0512.png) · 377 KiB | [2500,1560..3012,2072](focus/F02_fins_right_lower__BLUEHOUR_FINAL__REFERENCE_BLENDER_BASE__x02500_y01560_w0512_h0512.png) · 151 KiB | [2500,1560..3012,2072](focus/F02_fins_right_lower__BLUEHOUR_FINAL__x02500_y01560_w0512_h0512.png) · 336 KiB |
| `F03_fins_left_upper` | [1700,700..2212,1212](focus/F03_fins_left_upper__DAYLIGHT_FINAL__REFERENCE_BLENDER_BASE__x01700_y00700_w0512_h0512.png) · 248 KiB | [1700,700..2212,1212](focus/F03_fins_left_upper__DAYLIGHT_FINAL__x01700_y00700_w0512_h0512.png) · 392 KiB | [1700,700..2212,1212](focus/F03_fins_left_upper__BLUEHOUR_FINAL__REFERENCE_BLENDER_BASE__x01700_y00700_w0512_h0512.png) · 186 KiB | [1700,700..2212,1212](focus/F03_fins_left_upper__BLUEHOUR_FINAL__x01700_y00700_w0512_h0512.png) · 345 KiB |

### 자동 계측 (핀 주기 분석, 승인 근거 아님)

각 박스에서 수평 띠 성분을 제거한 뒤 열 방향 휘도 스펙트럼의 우세 주기와 그 피크의 전력 비중을 측정했습니다. 주기가 같으면 간격이 유지된 것이고, 비중이 낮으면 핀의 대비가 약해진 것입니다. [`fin_rhythm_measurement.json`](fin_rhythm_measurement.json)

| 이미지 | 박스 | 주기 px (Blender / ChatGPT / 최종) | 피크 비중 (Blender / ChatGPT / 최종) |
|---|---|---|---|
| DAYLIGHT | right_face_upper | 34.55 / 34.55 / 34.55 | 0.491 / 0.407 / 0.484 |
| DAYLIGHT | right_face_lower | 16.75 / 17.18 / 16.34 | 0.206 / 0.159 / 0.202 |
| DAYLIGHT | left_face_upper | 23.04 / 22.08 / 23.04 | 0.344 / 0.215 / 0.346 |
| BLUEHOUR | right_face_upper | 34.55 / 34.55 / 34.55 | 0.448 / 0.295 / 0.304 |
| BLUEHOUR | right_face_lower | 16.34 / 17.18 / 17.18 | 0.176 / 0.153 / 0.158 |
| BLUEHOUR | left_face_upper | 23.04 / 23.04 / 23.04 | 0.391 / 0.304 / 0.315 |

**읽는 법(작성자 1차 판독):** 간격(주기)은 세 단계에서 같게 유지됩니다. Daylight는 최종본의 핀 대비가 Blender 기준본 수준으로 회복되었습니다. **Blue Hour는 최종본의 핀 대비가 ChatGPT 편집본과 비슷한 수준에 머물러 복원이 불완전합니다.** `F02` 영역(우측 면 하단, 입구 위)은 두 이미지 모두 육안으로도 핀이 번져 보입니다. 이 판독은 자동 계측과 작성자의 육안 1차이며 독립 사람 검수가 아닙니다.

## 5. 다른 확인 항목 바로가기

- 지붕 원형 개구부·옥상 정원: `F04`, `F06`, 영역 `R1`  ·  지붕 원통 튜브: `F05`
- 중층 보이드·정원: `F07`, `F08`  ·  코너 코어: `F09`, `F10`  ·  지상 튜브: `F11`  ·  진입 램프: `F12`
- 횡단보도와 광장 가장자리: `F13`  ·  가로수·차량·차선: `F14`  ·  도시 맥락: `F15`, `F16`
- 이웃 건물 높이의 85.6%, 도로 폭, 가로수, 가로등은 가정값입니다(`docs/t14q_v47` 보고서 참조). 참고 사진 픽셀은 사용하지 않았습니다.

## 6. 읽기 검증 상태

- GitHub 업로드와 Claude 쪽 GitHub 접근 읽기 검증 결과는 PR #28 보고서와 `GITHUB_READBACK_REPORT.json`에 기록됩니다.
- **ChatGPT GitHub 연결에서의 직접 읽기는 이 패킷을 만든 시점에 확인되지 않았습니다 (`CHATGPT_CONNECTOR_READBACK_PENDING`).** Claude의 성공을 ChatGPT 연결의 성공으로 간주하지 않습니다.

GitHub 경로 형식: `docs/t14r_visual_review/G002_C_T14Q_R1/focus/<파일>` @ 브랜치 `feat/t14r-github-inspectable-visual-review-packets-20261115`
