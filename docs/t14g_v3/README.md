# C-T14G 도면집 Candidate V3 (후보 · NOT FROZEN)

`Candidate_V3_drawing_set.pdf` — A3 31쪽, 3.2 MB. V2(30쪽)에서 **생성기 소스를 고쳐 다시 만든** 도면집이며(PDF 사후 보정 아님), A-902 층별 구성 일람 1장을 더했다. 기존 V3 중간본(`docs/t14f_v3/`, PR #15)은 그대로 두었다.

## 숫자로 본 상태

| 항목 | 값 |
|---|---|
| PDF SHA256 | `3c82aa2a6e6187d757dae1f4ffb53e9f955874edecbb02875d4dd8f09b45ad54` |
| 코드 커밋 | `b5d7492` (브랜치 `claude/t14g-candidate-v3-full`, 기준 `3e2f997` = PR #15 헤드) |
| 모델 원본 | **GLB 없음**(`MODEL_SHA = MISSING`). V2 기록 해시 `b1927ffd…45ab88`은 검증 불가. 검증된 입력은 모델 캐시 `model_world.npz` `992e2ec5…9537b` |
| 전체 테스트 | 86 통과 / 0 실패 (C-T14G 46건 포함) |
| 과거 도면집 QA | 63/63 (V3에서 다시 실행) |
| 독립 PDF 검사 10종 / 스케일바 | 0건 / 25/25 (실측) |
| 의도적 결함 주입 | 13/13 탐지 |
| 치수 사실 | 28/28 |
| 가구 기하 | 5/5 층 통과(겹침 0, 구조 접촉 0, 통로 1.8~2.4 m) |
| 시각 감사 | V2·V3 중간본 30쪽 **완료**(5건), 최종 V3는 일부 쪽만 직접 확인 → `unresolved_design_decisions.md` 1절 |
| FROZEN | **false** |

## 폴더

| 경로 | 내용 |
|---|---|
| `Candidate_V3_drawing_set.pdf`, `Candidate_V3_contact_sheet.png` | 통합 PDF, 번호 붙은 축소 일람 |
| `sheets/{plans,elevations,sections,details,appendix}/` | 시트마다 PDF·SVG·PNG(150 dpi) |
| `before_after/` | 같은 위치 변경 전후 16장 (V2 | V3) |
| `qa_30page_visual_audit_V2_V3i.csv`, `qa_defect_ledger_baseline.csv` | 쪽별 판정·결함 장부(ID, 심각도, 크롭 파일) |
| `tests_report.json`, `tests_report_historical_63.json`, `qa_mutation_report.json`, `scale_bar_report.json`, `dimension_truth_report.json`, `furniture_qa.json` | 실측 검사 결과 |
| `cross_reference_graph.json`, `typical_floor_coverage.json`, `source_manifest.json` | 참조 그래프, 17개 층 일람, 해시·도구 |
| `visual_issues_resolved.md`, `unresolved_design_decisions.md` | 해결한 것 / 못한 것·결정 |
| `source_changes.diff` | PR #15 헤드 대비 `tools/ src/ tests/` unified diff |

## 다시 만들기 (모델 캐시가 든 V2 실행 폴더가 필요)

```
RUN=output/C_T14G_V3_run          # V2 실행 폴더를 복사한 작업 폴더 (gitignore)
export T14_EDITION=V3 T14_ISSUE_DATE=2026-11-12
python -I tools/t14e_make_details.py --run $RUN
for F in 3F 8F 10F 13F 15F; do python -I src/architectural_plan_renderer.py --out $RUN --floor $F --scale 250 \
    --v3layout --bare --cleanline --final-dir $RUN/plans/_raw --name raw_plan_$F --png-width 2000; done
python -I tools/t14e_plan_sheet.py --run $RUN --plans 3F:P-101:3F,8F:P-102:8F+9F,10F:P-103:10F,13F:P-104:13F+14F,15F:P-105:15F
python -I tools/t14e_make_views.py --run $RUN
python -I tools/t14e_make_book.py --run $RUN --head "$(git rev-parse HEAD)"
python tools/t14e_book_qa.py --run $RUN
python -I tools/t14g/mutations.py $RUN/book/drawing_set_candidate_v3.pdf $RUN/00_index/sheet_index.json $RUN/qa_mutation_report.json
python -m pytest tests -q                  # PDF 테스트는 이 폴더의 PDF·sheet_index.json 을 쓴다
```

`--glb`는 선택이다. 없으면 모델 캐시 해시를 기록하고 GLB는 `GLB_ORIGINAL_MISSING__CACHE_ONLY`로 표기한다.

## 하지 않은 것

- A1 1:200·A3 1:200 분할 평면의 실제 출력과 비교(요청 P1 6) — 생성하지 못했다. 사유와 준비 상태는 `unresolved_design_decisions.md`.
- Modal·클라우드 — 잔액·지출 한도를 확인하지 못해 쓰지 않았다. 추가 결제·자동결제 변경 없음.
- 모델이 없어서 못 하는 3D 재생성·상층 내부·구조 규격 — 만들어 내지 않았다 (`BLOCKED_MISSING_SOURCE`).
- 최종 `FREEZE`, `main` 병합 — 하지 않았다.
