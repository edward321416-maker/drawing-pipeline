# 03 Work packages

No package changes verified geometry. READY = reversible and independent of the open decisions. Packages marked CHECK_C_T14U must first be compared with the C-T14U work, which could not be found.

## WP0 (P0) READY_FOR_STUDY / APPROVAL_BLOCKED: D-01·D-02·D-03 모델 보존 건축 대안 비교 연구

- Floors: B1, 2F-15F
- Source files: `data/t14s/source_slices/floor_<층>_slice.json (읽기 전용)`; `src/t14s/source.py`; `tools/t14s/audit_measurements.py`
- Existing failure: 랜딩 25곳이 바닥판 위가 아님, 코어 3곳 바닥판 0 m², 승강기 출입구 회전 15건 미승인.
- Evidence: `measurements/measurements.json`; `02_P0_ALTERNATIVES`
- Correction: 대안 A(국소 데크·브리지)·B(에스컬레이터 비운영)·C(에스컬레이터 이동)를 별도 Draft 레이어와 단면으로 그려 비교. 검증 슬래브·코어·개구는 수정하지 않음.
- Dependencies: 사용자 방향 결정; 구조·피난 검토 의뢰(별도)
- Verification: 대안마다 경로 그래프를 재계산해 25개 랜딩이 ON_SLAB이 되는지, 남는 개구 면적, 연속 유효폭, 단면에서의 데크 두께·춤을 보고.
- Acceptance: 각 대안의 실측표 + 평면·단면 + 그래프 영향이 있고, 어떤 대안도 승인 표기가 없으며, 원본 슬라이스 해시가 불변.
- Approval: 필수 (구조·슬래브·코어·개구 변경은 사용자 승인 후에만 모델에 반영)

## WP1 (P0) READY: 완전한 접근 그래프와 연속 유효폭 측정

- Floors: 전 층
- Source files: `src/t14s/planner.py`; `src/t14s/walknet.py`; `tools/t14s/validate_t14t.py`
- Existing failure: 승강기 EV1·EV2·PL·FR·T1 램프가 그래프 밖, 0.55 m 허용은 연속 유효폭이 아님, 검증기가 완결성을 과장.
- Evidence: `evidence/circulation_audit.json`; `evidence/validator_rerun_report.json`
- Correction: 교통 노드(EV1·EV2·PL·FR)를 그래프에 추가하거나 명시적 제외로 기록, 경로를 따라 장애물까지 거리를 재어 최소 유효폭 보고, circulation_complete를 vertical-circulation-audit 규칙과 일치시킴.
- Dependencies: EV1·EV2·PL 역할 결정(사용자); C-T14U 대조
- Verification: 결정적 테스트 + 전 층 재실행(validate_t14t) + 감사 도구 재실행.
- Acceptance: 모든 경로의 최소 유효폭이 숫자로 보고되고 1.2 m 미만 구간은 목록화, COMPLETE 판정은 감사 규칙과 동일.
- Approval: 측정·보고 변경은 불필요, 도면 변경이 생기면 층별 확인

## WP2 (P1) CHECK_C_T14U / PARTLY_DECISION_BLOCKED: 층별 기능·프로그램 보완

- Floors: B2, B1, 6F, 10F-15F, 3F-9F
- Source files: `src/t14s/program.py`; `src/t14s/planner.py`
- Existing failure: 10F 지원 6.9 %, 11F 홀 1,773.8 대비 최대 실 83.2, 12F·13F·14F 실 합계 167-301 m², 정원 접근, 3F-9F 반복 점포.
- Evidence: `02_P0_ALTERNATIVES (프로그램 실측)`; `reconciliation R-10..R-16`
- Correction: 층별 프로그램을 PROPOSED_DESIGN으로 보완(주방·세척·저장·폐기물 동선, 공연·전시·공방·교육 실 구성, 정원 보행·가장자리·운영, 점포 유형 차별화).
- Dependencies: D-05·D-06·D-09 결정; 정원 접근은 D-01·D-07; C-T14U 대조
- Verification: 층별 면적표, 접근 그래프, A1/A3 PDF 재검사, 전후 비교.
- Acceptance: 층별 목표 실 구성이 합의된 뒤 면적·동선·인쇄 면적이 일치하고 법규 적합이라는 주장이 없음.
- Approval: 프로그램 방향은 사용자 확인

## WP3 (P1) PARTLY_DONE: 실제 A1/A3 PDF 32쪽 렌더링·검증과 층 간 일관성

- Floors: 전 층
- Source files: `outputs/T14T/<층>/T14T_<층>_plan_A1_1to200.pdf`; `tools/t14s/audit_pdf_consistency.py`
- Existing failure: PDF가 육안으로 검토되지 않았고 면적 인쇄가 불완전(P4 12개 층 불합격, 지원실 161개 면적 미인쇄).
- Evidence: `evidence/pdf_consistency.json`
- Correction: 면적 라벨 인쇄 규칙 보완 또는 실 일람표 추가, 32쪽을 렌더링해 층별 육안 검토 기록.
- Dependencies: 도면 변경이 있을 때만 재생성
- Verification: audit_pdf_consistency.py 전 항목 통과 + 렌더링 페이지 육안 기록.
- Acceptance: P1-P7 16/16 통과, 실·면적 일람과 메타데이터 일치.
- Approval: 일람표 서식은 사용자 확인 권장

## WP4 (P2) BLOCKED: V4.2 65쪽 도면집에 정정 평면 통합

- Floors: 전 층
- Source files: `docs/t14k_v42/README.md`; `docs/t14i_v4/Technical_Drawing_Appendix_Candidate_V4_index.csv`
- Existing failure: PR #30의 16개 평면이 V4.2 후보와 통합되지 않았고 단면·입면과의 대응이 미확인.
- Evidence: `reconciliation R-19, R-21`
- Correction: 사용자가 승인한 도면만 통합, 단면·입면·상세와 층 대응표 작성.
- Dependencies: WP0-WP3 결과; 사용자 승인
- Verification: 쪽별 대응표와 PDF 렌더링 검사.
- Acceptance: 통합 쪽의 도면 ID·레벨·축척이 정본과 일치하고 미승인 도면이 포함되지 않음.
- Approval: 필수 (도면집 반영·동결은 명시 승인 전 금지)
