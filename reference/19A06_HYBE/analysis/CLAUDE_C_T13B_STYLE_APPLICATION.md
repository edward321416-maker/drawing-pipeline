# C-T13B — HYBE 19A06 레퍼런스 수집·도면 스타일 적용 실행 지시

**상태:** 실행 전. **완료 조건:** 원본 수집 + 검증 가능한 스타일 분석 + 실제 1층 새 도면 A/B를 모두 생성. 지시서나 자동 요약만으로 완료 처리하지 않는다.

## 0. 작업 대상과 권한

- 참고 원본: <https://fhhhfriends.com/19a06> (FHHH friends + studio COM, HYBE).
- 보조 자료(출처를 별도로 표기): <https://c-o-m.kr/hybe/office>, <https://www.archdaily.com/1016294/hybe-headquarters-office-com-plus-fhhh-friends>.
- 도면 저장소: `D:\Users\admin\Desktop\drawing-pipeline-repo`, 원본 연구 저장소: `vertical-commercial-pedestrian-flow` (93개 미커밋 변경이 있었으므로 **절대 정리하거나 초기화하지 않음**).
- 참고 수집 폴더: `[drawing-pipeline-repo]\reference\19A06_HYBE`.
- 원본 모델 위치: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\model\1F_master.blend`.
- 기준 이미지: `our_baseline\1F_Program_Concept_V2_B.png`.
- **승인된 1층 18개 프로그램 유지.** 공간·기둥·피난·커튼월 개구·캡슐 출입문을 스타일 변경으로 수정하지 않는다.

## 1. 이미지 및 도면 원본 전수 수집

1. Git 상태와 `origin`을 확인하고 **격리 작업 브랜치/worktree**를 구성한다. 기존 PR이나 `main`을 강제로 병합·수정하지 않는다.
2. 사용자가 전달한 `reference/19A06_HYBE` 폴더를 별도 작업 공간에 복사한다. 브라우저는 현재 PC에 이미 설치된 Chrome/Edge를 우선 사용한다.
3. `python reference/19A06_HYBE/scripts/capture_reference.py --url https://fhhhfriends.com/19a06 --output reference/19A06_HYBE` 를 실행한다. 실행 환경에서 설치된 Playwright가 없을 때만 무료·신뢰 가능한 격리 환경에 버전을 고정해 설치한다. 브라우저 인증/쿠키 추출 및 우회 금지.
4. 웹페이지를 끝까지 스크롤하고 이미지/슬라이드가 늦게 뜨는지 확인한다. 스크립트가 누락한 슬라이드는 브라우저의 **공개 페이지 UI를 직접 탐색**해서 추가 캡처한다. 갤러리 번호와 `capture_manifest.json`의 목록을 비교한다.
5. 모든 이미지·도면·사진을 원본 파일 포맷으로 보존하고 `sha256`, URL, 촬영일, 이미지별 파일명, 성공/실패 원인을 등록한다. 원본을 크롭/압축해 덮어쓰지 않는다.
6. `python reference/19A06_HYBE/scripts/analyze_reference.py --root reference/19A06_HYBE` 로 contact sheet 및 자동 1차 분류를 만든다. 분류는 OCR이나 실제 건축적 도면 검증이 아니므로 **사람이 반드시 전체 썸네일을 확인**한다.
7. `analysis/ASSET_REVIEW.md`에 이미지/평면/단면/다이어그램/현장사진을 직접 구분해 번호·관찰·기여 가능성을 기록한다. 자료가 보이지 않거나 다운로드가 막히면 HOLD를 보고하고 `all_media_captured=true`를 표시하지 않는다.
8. 원본 이미지는 내부 개인 학술 분석용으로 사용한다. 사진/도면의 재배포 권한이 확인되지 않은 경우 GitHub PR에는 URL·메타데이터·해시·해석과 **직접 제작한 비교 결과물만** 넣고, 원본 사진·원본 도면 바이너리는 커밋하지 않는다.

## 2. 구체적인 스타일 분석

위 `analysis/STYLE_AUDIT.md`는 **직접 19A06 원본 이미지 검토 전의 잠정 분석**이다. 먼저 자료를 모은 뒤 아래 항목을 자료별로 검증한다.

- 평면도: 구조 절단벽/기둥의 채움, 문·창호·유리선, 선폭 계층, 가구 외곽, 표기/치수, 바닥 패턴, 음영·포셰, 범례와 축척.
- 단면·입면: 구조/외피 명도 대비, 점선/투영선, 재료 경계, 원호 품질.
- 실내사진: 재료·가구의 모듈화, 색상/명도, 보행공간과 가구의 관계. **사진의 원근·물리 형태를 평면도의 선폭에 곧바로 적용하지 않음.**
- 원본 프로젝트 특징과 확인 가능한 내용만 `SOURCE_OBSERVED`로 기록. 모듈 그리드 500×500mm 등의 설명은 해당 보조문헌 출처를 유지.

분석표에는 모든 결론마다 (a) 출처 이미지 ID, (b) 확인 위치, (c) 해석, (d) 우리 도면 적용 규칙, (e) 코드 변경 함수, (f) 미검증 조건을 연결한다. 구체 선폭/명도 수치가 원본 이미지 파일의 측정 결과가 아니면 `DESIGN_PROPOSAL`이라고 표기한다.

## 3. 우리 도면에 스타일 적용

- 입력 도면은 실제 1층 Blender 슬라이스/원천 모델에서 나온 동일 feature만 사용하고, **PNG 밑그림 전체를 트레이싱하거나 재활용하지 않는다**.
- `analysis/style_tokens.proposed.json`을 검토하되 원본 FHHH의 정확한 선폭값으로 속이지 않는다. `TCanvas/restyle`, `Canvas.stroke_poly/stroke_line`, `draw_furniture`, `design_site`, `wobble_ring/tree_shapes` 등을 최소 범위 변경한다.
- `STYLE_A`: 건축 포셰·기둥/코어의 대비가 강하고 가구는 선명한 중명도의 단정한 흑백 도면.
- `STYLE_B`: 구조 강조를 유지하며 서측 공원 식재 및 바닥점묘는 더 최소화하고, 시장 프로그램별 가구의 판독성을 상대적으로 높인 도면.
- 중복·미세 꺾임·찌글선 문제를 **SVG 원본부터** 해결한다. 구조/경계 기하를 전역 `simplify()`로 바꾸지 않는다. 이미지 변환의 해상도 문제는 SVG와 PDF 확대 비교로 분리한다.
- studio COM의 사무용 500mm 모듈 개념은 상업시설 가구 정렬을 위한 **선택적 규칙**으로만 사용한다. 기존 18개 프로그램/가구 종류를 HYBE 오피스 배치로 교체하지 않는다.

## 4. 강제 QA 및 실제 산출물

- `1F_HYBE_ReferenceStyle_A.svg/.pdf/.png`, `1F_HYBE_ReferenceStyle_B.svg/.pdf/.png`.
- 5개 고정 크롭 × Before/After 비교, 전체 도면 A/B 비교판, 참고 도면 검토용 contact sheet.
- `reference_capture_manifest.json`, `style_evidence_matrix.csv`, `style_application_diff.json`, `qa_report.json`, `C_T13B_verdict.md`.
- A3 가로 420×297mm, 1:500 출력의 물리 치수 확인, 최소 300dpi PNG.
- 원본 세계좌표/구조 ID/34개 기둥/승강기/코어/튜브의 비의도 변경 0, 프로그램 18개 유지, 고스트 가구선 0, 의도하지 않은 선 중복 0, 법규미확인은 PENDING으로 남길 것.
- 두 버전은 **정말 같은 기하에 스타일만 다른 것인지** feature hash로 비교할 것. 건축 형상·공용 동선·문 개구를 바꾸지 않는다.
- 렌더러의 실제 소스 변경은 unified diff와 회귀 테스트로 보고하며, 수정은 새 Draft PR에 남긴다. 별도 승인 없이 최종 1F FREEZE나 기존 main 병합 금지.

## 5. 완료 및 실패 처리

**원본 다운로드가 막히면:** 사진을 가져온 척 하거나 검색 결과 이미지를 임의 대체하지 말고 `REFERENCE_CAPTURE_HOLD`로 보고. 경로·갤러리 번호·요청 URL·HTTP/브라우저 오류를 남기고 가능한 자료만 분리한다.

**분석만 되고 새 도면이 없으면:** `STYLE_RESEARCH_DONE / APPLICATION_NOT_DONE`으로 명확히 보고.

**정상 완료:** 수집 성공/누락 개수, 전체 이미지 폴더, 모든 도면/사진 출처, 수정 코드 unified diff, A/B PNG/PDF 링크, 5개 before/after 크롭, 모델 SHA, 실제 QA 통과·실패, 개선/퇴보 판정을 제출한다.

마지막 체크포인트: `HEAD | ORIGINAL_IMAGES_CAPTURED/TOTAL_DISCOVERED | DRAWINGS_REVIEWED | QA_PASS/TOTAL | OUTPUT_SHA | VERDICT | TOKENS_ESTIMATED_OR_UNKNOWN`.
