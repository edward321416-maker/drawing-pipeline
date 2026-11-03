# C-T13 — 1층 프로그램 컨셉 V1을 실모델 기반 V2 도면으로 구현

작성: 2026-11-03  
상태: **Claude Code 로컬 실행 대기 / 실제 3D 모델과 final 도면 미수정**

## 승인 업데이트 — 1층 프로그램은 확정된 기획 방향

사용자가 1층 V1 시안을 확인하고 “프로그램 오케이”라고 명시했으므로, `docs/decisions/2026-11-03_1f_program_intent_approved.md`의 **PROGRAM_INTENT_APPROVED**를 현재 유효한 결정으로 사용한다. 

시장 M01~M06, 필로티 P01~P04, 서비스 S01~S04, 캡슐 C01~C04의 **기능 구성과 기본 조직 방향을 다시 승인받으려 하지 말고** 즉시 실모델 기반 V2 A/B 기하·가구·도면 생성으로 진행한다. 기존 `program_spec.json`의 `PROPOSED_UNAPPROVED`는 최초 작성 상태를 보존한 것으로, 최신 프로그램 의도 승인 결정을 무효화하지 않는다.

**승인 제외:** 잠정 면적 비율, 확정 폴리곤, 문 위치·폭·형식, 법규 적합성, 가구의 정확한 수·위치, 그래픽 최종본, 1층 전체 FREEZE. 실제 모델과 충돌할 경우 프로그램 자체를 교체하지 말고, 배치 대안과 충돌 근거를 도면으로 보고한다.

## 작업의 핵심

이번 작업에서 ChatGPT가 다음 실제 시각 산출물을 제공했다.

- `1F_Program_Concept_V1.png` — 기존 1F A3 평면에 프로그램 존/가구 유형/방문객 흐름을 중첩한 **시각 검토용 제안**
- `1F_Program_Concept_V1_zoom.png` — 건물 내부 동일 제안 확대
- `1F_Program_Concept_V1_comparison.png` — 기존 평면과 제안 시안의 동일 크롭 비교
- `1F_Program_Concept_V1.pdf` — A3 420×297mm 용지
- `1F_Program_Concept_V1.svg` — SVG 벡터 기호와 기존 PNG underlay 결합
- `1F_Program_Concept_V1_manifest.json` — 추적 정보, source 구분, 미검증 내용
- `Claude_C_T13_1F_Program_Concept_V2_Implementation.md` — 상세 Claude 실행 지시서

이 이미지 파일은 **사용자와 공유한 ChatGPT 대화의 파일**이며 아직 GitHub 바이너리로 커밋하지 않았다. Claude는 사용자가 다운로드한 ZIP을 참조할 수 있으나, 이 이미지의 픽셀 좌표를 실제 설계 형상으로 전용하면 안 된다.

이번 V1은 *기하 정확성을 입증한 신축 도면*이 아니며, 원본 이미지 위에 건축 모델 기반 주요 장애물과 잠정 프로그램·가구를 시각적으로 중첩한 **계획 검토 패널**이다.

## 확정 모델 사실 (변경 금지)

- 1F 직렬화 모델 189개 객체, 기둥 34개, 내부 문 11개(코어 8 / 화장실 3), 튜브/샤프트/필로티/서비스.
- 사용자 로컬 .blend와 JSON 같은 버전: Claude C-T11 보고 기준.
- 시장 커튼월 5개 문은 렌더러의 그래픽으로 생성되고 실제 3D 외피 문이 아니다.
- 서측 캡슐 문 그래픽도 실제 개구 형상이 아닌 렌더러 투영이다.
- 화장실 B/C 슬라이딩 문은 설계 소스에 있지만 `build_master.py`의 `if d.swing is not None` 조건 때문에 직렬화 누락됨 (별도 C-T11B 버그).
- 사용자 승인된 선큰·코어 B 문·WC B/C 이동은 유지.
- 도면 확정 축척은 1층 A3 가로 1:500, 상층 A3 1:100. 오래된 `AGENTS.md`와 차이는 별도 이슈 기록.

## C-T13 진행 범위

1. **Git 원천 구분:** 논문 프로젝트의 `origin=vertical-commercial-pedestrian-flow`는 도면 저장소가 아니다. `D:\Users\admin\Desktop\drawing-pipeline-repo` (`origin=drawing-pipeline`)에서 새 독립 worktree와 `claude/t13-1f-concept-v2` 브랜치를 생성하라. 작업 시작 전에 `git status --short`로 원본과 검증 worktree의 미커밋 변경을 확인하라. 기존 원본 93건 변경을 지우거나 강제 checkout하지 마라.
2. **실제 모델 사용:** `engine/model/1F_master.model.json`, `m_1f_source.json`, 검증된 원본 `.blend`, `raw_slices/floor_1F_slice.json`을 읽고 source ID별 세계좌표를 재확인하라. 모델에서 진실을 구하고 V1의 자의적인 주석 픽셀 좌표를 새 기하 원천으로 쓰지 마라.
3. **프로그램 구획:** `docs/plans/2026-11-03_1f_program_spec.json`을 기반으로 M01~M06(안내/상설판매/팝업/식음/착석/순환), P01~P04(필로티), S01~S04(서비스), C01~C04(캡슐) 폴리곤을 실제 바닥·기둥·코어·튜브·WC 형상에서 생성하라. 하위 구획의 정확한 ㎡는 Shapely `polygon.area`에서 계산하고 연성 비율은 설계 목표로만 다뤄라.
4. **동선 우선:** 장벽·문/계단/승강기 대기·주통로/부통로 keep-out을 가구보다 먼저 확정하라. 주동선 목표 2.4m, 보조 1.8m는 법규 확정치가 아닌 계획 기준이다. 공공/서비스 흐름 분리. 실제 출입문이 없는 영역은 `PROPOSED_ONLY`와 `ACCESS_PENDING` 유지.
5. **가구의 개별 인스턴스:** 판매대·팝업 시연대·결제/안내대·푸드카운터·2/4인/공용테이블·갤러리 플린스·벤치를 프로그램별로 배치하라. 실물 개체 수와 SVG body polygon 수를 별도로 산정하라. 기존 반복 격자 최대화 금지.
6. **제도:** 구조 절단벽/유리/문/가구/식재의 종이 기준 선 두께 위계를 적용하고, 원본 가구선이 새 가구 아래 중복되는 **고스트 현상**을 없애라. 기존 A1 레거시 파이프라인을 A3 최종 출력과 혼동하지 마라. A3 PDF 물리 크기 420×297mm, 인쇄 여백/실축척 검증.
7. **최소 두 가지 실제 렌더 후보:** A=공공 통과축 중심+상업 프로그램 군집, B=진입 분산 가설+다중 활동 군집. 두 후보의 원천 3D는 동일하고 미승인 출입구는 점선/주석으로만 표현. 배치 후보의 건축적·미적 장단점을 비교하라.
8. **QA:** 기둥 ID 34개 source-vs-output reconciliation, 코어/WC/튜브 불변, 프로그램 존의 중복·영역 유출 0, 가구-구조 충돌 0, 가구 중복/고스트 0, 출입문 가상→실물 승격 0, SVG/PDF/PNG 동일 레이어/축척. 원인 검증 없이 '34개 다 보이도록 그려라'가 아니라 매입 구조/겹침을 설명하라.
9. **이미지 제출 의무:** 문서만 내면 미완료. 반드시 `1F_Program_Concept_V2_A.png`, `_B.png`, A/B PDF, 5개 표준 크롭, before/after 비교판, 계산된 구획면적/가구 인벤토리/QA JSON/manifest SHA를 **실제 파일로 생성**하라.
10. **승인:** 시장·캡슐의 실제 문 위치·폭·형식은 사용자에게 계획 후보 이미지+근거를 보여주기 전 모델에 반영하지 마라. 이번 단계는 1층 전체 FREEZE가 아니다. 모델/코드 변경은 독립 Draft PR에서만 하고 자동 병합 금지.

## 종료 보고 최소 템플릿

- HEAD, source `.blend` SHA256, 1F 슬라이스 SHA256, 새 출력 SHA256
- 변경 범위 및 unified diff, 테스트 정확한 통과/실패 수
- 실측 면적표, 프로그램/가구 수, 보행 이격·제약
- PNG/PDF/SVG 실제 전체 절대 경로
- A/B 도면 비교, 기존보다 개선된 점, 남은 결함
- 출입구 및 WC 슬라이딩 문 처리: 실제 모델 승인/미승인/별도 결함을 분리
- `PASS / HOLD / FAIL` + `1F_FINAL_FROZEN=false`
- `HEAD | TESTS | MODEL_SHA | OUTPUTS | GATE | TOKENS_ESTIMATED_OR_UNKNOWN`
- Google Sheet `AI_Execution_Log` 접근이 없다면 로컬 pending 문서에 기록하고 **NOT SYNCED** 명시.

**본 문서는 작업 지시서이며 Claude Code, Blender 및 자동 QA를 실행했다는 주장이 아니다.**
