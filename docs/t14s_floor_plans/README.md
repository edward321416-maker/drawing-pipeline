# C-T14S — 누락 16개 층 평면도 후보 (B2, B1, 2F–15F)

**검수 상태: `READY_FOR_CHATGPT_INDEPENDENT_REVIEW`** · PROPOSED_DESIGN · NOT APPROVED · NOT FROZEN.
건축 품질·도면 품질은 승인하지 않았다. 자동 검사는 파일·치수·축척·원본 해시 확인뿐이다.

## 무엇이 모델 사실이고 무엇이 제안인가
- `MODEL_VERIFIED`: 층판 외곽·개구, 기둥 34개(Ø0.9, 9 m 격자), 코어 외곽, 튜브·샤프트 개구, 에스컬레이터 절단부, 파사드 부재. 출처: `data/t14s/source_slices/`(T14J 실행의 raw slice 19개를 SHA256으로 고정한 사본, 변경 없음 확인).
- `PROPOSED_DESIGN__VERIFIED_1F_SYMBOL`: 1F 승인 심볼(`engine/symbols/*`: 4갈래 ㅁ자 피난계단 코어, 화장실, 튜브)을 상층 위치에 재사용한 내부. 화장실은 1F 승인 위치(사용자 승인 이동 반영)를 수직으로 쌓았다.
- `PROPOSED_DESIGN`: 구획벽(150 mm), 문·개폐, 점포·홀, 가구, 방문객 주 동선, 면적 라벨. 모델에 없는 설계이다.

## 산출물 (층마다 6개 파일, `outputs/T14S/<층>/`)
`T14S_<층>_plan_A1_1to200.svg`(편집 가능, 레이어·출처 그룹) · `.dxf`(mm, 1:1) · `_A1_1to200.pdf`(841×594, 벡터) · `_A3_split_1to200.pdf`(420×297, 북/남 2쪽, 매치라인 y=+9) · `_A1_1to200.png`(200 dpi, 6622×4677) · `_metadata.json`(출처·면적·실·메모). 전체 해시: `outputs/T14S/SHA256_MANIFEST.json`.

## 검수 패킷 (PR #28 프로토콜, `tools/t14r`)
- `docs/t14s_floor_plans/review_packet/` — 층마다 미리보기 JPEG + 무손실 800 px 타일, `manifest.json`, `README.md` (256개 타일, verify 통과).
- `docs/t14s_floor_plans/contact_sheet_17_floors.jpg` — 17개 층(1F 보존 기준 포함) 개요.
- `docs/t14s_floor_plans/T14S_floor_plan_review_A3.pdf` — A3 가로 18쪽: 개요 + 1F 기준 + 층별 미리보기와 상태.
- `docs/t14s_floor_plans/reference_1F/` — 1F 기준 도면 미리보기 사본(원본과 해시 동일, 재생성하지 않음).

## 층별 요약
| 층 | FFL(m) | 프로그램 | 실 수 | 층판 순면적(㎡, 모델) | 제안 실 합계(㎡) | 자동 메모 |
|---|---|---|---|---|---|---|
| B2 | -11.0 | 판매 | 27 | 2,847.0 | 2,770.1 | RESTROOM_B_OMITTED |
| B1 | -5.5 | F&B/판매 | 21 | 2,605.6 | 2,435.1 | - |
| 2F | +6.0 | F&B | 13 | 2,002.5 | 1,868.6 | CORE_D_NO_SLAB_AT_LEVEL; CIRC_UNREACHABLE |
| 3F | +11.0 | 판매 | 19 | 2,477.4 | 2,306.9 | CIRC_NODE_SKIPPED esc 3F-4F_W_3F (not in hall space); CIRC_UNREACHABLE |
| 4F | +16.0 | F&B/판매 | 20 | 2,449.6 | 2,279.4 | CIRC_NODE_SKIPPED esc 4F-5F_W_4F (not in hall space); CIRC_UNREACHABLE |
| 5F | +21.0 | 판매 | 18 | 2,449.6 | 2,279.3 | CIRC_NODE_SKIPPED esc 5F-6F_W_5F (not in hall space); CIRC_UNREACHABLE |
| 6F | +26.0 | F&B/garden/판매 | 14 | 2,449.6 | 2,279.0 | CIRC_UNREACHABLE |
| 7F | +31.0 | F&B/판매 | 10 | 1,415.6 | 1,322.0 | CORE_C_NO_SLAB_AT_LEVEL; CORE_D_NO_SLAB_AT_LEVEL; RESTROOM_C_OMITTED; LABEL_FORCED_TAG room 07 (식음 홀, 19.2 m2) |
| 8F | +36.0 | 판매 | 11 | 2,339.3 | 2,169.4 | CIRC_NODE_SKIPPED esc 7F-10F_X7F-10F (not in hall space); CIRC_NODE_SKIPPED esc 8F-9F_E_8F (not in hall space) |
| 9F | +40.5 | 판매 | 14 | 2,339.5 | 2,169.6 | CIRC_NODE_SKIPPED esc 7F-10F_X7F-10F (not in hall space); CIRC_NODE_SKIPPED esc 9F-10F_E_9F (not in hall space) |
| 10F | +45.0 | F&B | 10 | 2,339.5 | 2,169.6 | CIRC_NODE_SKIPPED esc 10F-11F_E_10F (not in hall space); CIRC_NODE_SKIPPED esc 10F-12F_X10F-12F (not in hall space) |
| 11F | +51.0 | 문화·엔터 | 9 | 2,354.3 | 2,184.4 | CIRC_NODE_SKIPPED esc 10F-12F_X10F-12F (not in hall space); CIRC_NODE_SKIPPED esc 11F-12F_E_11F (not in hall space) |
| 12F | +57.0 | 문화·엔터 | 9 | 2,012.2 | 1,842.3 | CIRC_NODE_SKIPPED esc 12F-13F_E_12F (not in hall space); CIRC_NODE_SKIPPED esc 12F-15F_X12F-15F (not in hall space) |
| 13F | +61.5 | 문화·엔터 | 9 | 2,343.3 | 2,173.4 | CIRC_NODE_SKIPPED esc 12F-15F_X12F-15F (not in hall space); CIRC_NODE_SKIPPED esc 13F-14F_E_13F (not in hall space) |
| 14F | +66.0 | 문화·엔터 | 9 | 2,343.3 | 2,173.4 | CIRC_NODE_SKIPPED esc 12F-15F_X12F-15F (not in hall space); CIRC_NODE_SKIPPED esc 14F-15F_E_14F (not in hall space) |
| 15F | +70.5 | F&B/garden | 8 | 2,343.3 | 2,173.4 | CIRC_UNREACHABLE |

## 재현
```
python -I tools/t14s/build_all.py            # 16개 층 생성 (--sync 는 최초 1회 원본 슬라이스 고정)
python -I tools/t14s/validate.py             # 결정적 검사 -> build_test_report.json
python -I tools/t14s/package_review.py       # 검수 패킷·개요·A3 PDF
python -m pytest tests/test_t14s_build.py
```

## 자동 검사 결과
16/16개 층 통과 · 원본 지오메트리 변경 없음: True. 미해결·알려진 한계: `unresolved_design.md`.
GitHub 커넥터를 통한 ChatGPT 실제 판독은 **시험하지 않았다**(업로드·원격 해시 대조만 수행).
