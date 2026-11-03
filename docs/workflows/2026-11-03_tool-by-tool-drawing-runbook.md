# 도면 자동화 도구별 실행 매뉴얼 v1.1 (Tool-by-Tool Runbook)

- 작성일: 2026-11-03
- 상태: **구체적 실행 설계안 / 실제 코드는 아직 변경하지 않음**
- 연계 문서: `docs/workflows/2026-11-03_quality-gated-drawing-workflow.md` (G0~G7)
- 기존 기준 커밋: `d553799a6a45057b0db006375ae36239d849bdeb`
- 우선 파일럿: 1층 대지 포함 A3, 1:500. **1층 전체가 사용자가 원하는 공간·가구·제도 품질에 도달하고 명시적으로 승인되기 전에는 최종 동결하지 않는다.** 3F 이상은 그 후 확대.
- 프로젝트 로컬 루트: `D:\Users\admin\Desktop\2학기 논문`
- 주의: 아래 "현재 실행 가능 명령"은 **실제 스크립트의 인자와 코드 경로를 확인한 것**이며 이 문서 작성 과정에서 PC상 실행 성공을 확인한 것은 아니다. 의존성/입력모델 존재 여부는 현장에서 재확인한다.

## 1. 무슨 도구를 왜, 언제 사용하는가

| 도구 | 실제 담당 업무 | 입력 → 출력 | 현재 상태 및 제한 |
|---|---|---|---|
| **ChatGPT (공간 기획/독립 검토)** | 요구/프로그램 매트릭스·이슈 우선순위·Before/After 평가·엔지니어링 지시서 작성 | 모델/도면/참고 이미지/결함 장부 → 명시적 승인 기준 | 도면의 실제 건축 형상 변경 권한 없음; 오류 설명과 계획 담당 |
| **Claude Code / Gemini CLI / Codex 등 로컬 코딩 에이전트(택1)** | 파일 1~소수 개의 구현·회귀 테스트·실행 결과 기록 | GitHub 브랜치+작업 명세 → 코드/테스트/PR | 사용자 로컬 환경에서 직접 실행; 동일 변경을 복수 에이전트가 동시에 편집하지 않음 |
| **Blender 4.2.0 (GUI + headless bpy)** | 마스터 .blend의 태그·구조·문·개구·코어 확인/수정, 각층 z+1.5m 슬라이스 생성 | 태그 마스터 모델 또는 GLB → `raw_slices` 절단 JSON/마스크/AO | 1F는 태그 모델. 상층 GLB는 벽·문 없음; 상층 완성 도면을 직접 제공하지 못함 |
| **Python + Shapely** | 폴리곤 정합, 구획 면적 계산, 동선 네트워크/keep-out, 문·가구 배치, 독립 충돌 분석 | slice JSON/프로그램 계획 → 구조화된 geometry/feature | 기존 `engine`와 `src`에서 사용 중. `STRtree`/prepared geometry 활용은 최적화 제안 |
| **가구 라이브러리(현재 `src/furniture_library.py`)** | 실별 가구 객체 생성(의자/테이블/시장/캡슐)과 공간적 배치 | zone geometry + obstacle + seed + 프로그램 타입 → 가구 개별 객체·배치 결과 | 현행은 실제 가구 수 대신 body polygon 수를 보고. 재설계 필요 |
| **SVG 벡터 렌더러** | 출력 스타일/포셰/해치/마스킹/글자/축척 레이어를 장면에 매핑 | 동일 geometry feature + style tokens → SVG | 현재 `src/architectural_plan_renderer.py`가 A3 실행, 레이아웃과 스타일이 혼재 |
| **CairoSVG** | SVG → PDF/PNG 변환; 인쇄용 벡터 PDF 유지 | SVG → PDF/PNG | 프로젝트 스크립트에서 사용. Windows Cairo 의존성은 확인 필요 |
| **ezdxf** | 공통 객체/레이어를 DXF로 출력 | 공통 geometry/style feature → DXF | 현재 `src/02_topology_to_cad.py`에 별도 렌더 경로 존재. A3 내용과 불일치 |
| **Pillow / NumPy** | 동일 크롭, 시각 차이, 픽셀 오차, 배경 마스크 및 시각 QA 보조 | baseline/후보 PNG → overlay/difference/측정값 | 자동 픽셀 차이는 미적 품질의 대체 기준이 아님 |
| **pytest + `tests/verify_pipeline.py` + `engine/checks`** | 소스 정합, 기하·충돌, 렌더/문자, 출력 포맷, 결함 장부 전용 회귀 테스트 | 모델/JSON/SVG/DXF/PDF/PNG → PASS/FAIL+이슈 좌표 | 현행 검사도 G0 기준본으로 보존. 사용자 지적의 재발 방지 검사는 추가 개발 |
| **Git + GitHub + Draft PR** | 기준 HEAD, 브랜치, 변경 이유, 전후 이미지/품질 비교, 승인·rollback | 변경 전 SHA + 작업 후보 → PR + 검사 근거 → 사용자가 병합 승인 | 현재 GitHub 저장소 연결 가능; main은 사용자 승인 없이 변경하지 않음 |
| **Modal (옵션, 비용 발생 가능)** | 많은 층에 대한 AO/마스크 Blender 작업 병렬 실행 | GLB/스크립트/층목록 → `raw_slices` | `src/modal_render.py`에 구현. 동의 없이 실행/과금 금지; 한 층 프로토타입에는 사용하지 않음 |
| **SVG/PDF 뷰어 및 실제 인쇄** | 크롭·도면 확인, 100% 실제 출력 배율, 가는 선의 인쇄 가독성 검증 | A3 PDF 및 상세 크롭 → 사람 판독/승인 | 검증용 화면/인쇄 도구이며 시각적 수작업 보정이 모델 진실성을 변경해선 안 됨 |

**사용 순서:** AI 기획 → Blender(형상 진실) → Shapely(공간/배치) → SVG 제도 → PDF/PNG/DXF 출력 → 독립 QA → GitHub PR/사람의 판독. 모델/프로그램/표현 수정의 책임 범위를 섞지 않는다.

## 2. 단계별 SOP — 인력, 툴, 입력/산출/검사

| Gate | 담당 툴 | 실제 작업 | 고정 산출물 | 기술적 통과 기준 |
|---|---|---|---|---|
| **G0 비교 스냅샷** | GitHub, Python, Pillow, ChatGPT | 현재 HEAD/모델 hash/5개 고정 뷰/참고 이미지/리스크 등록. 첫 실행에서 현재 1F 이미지 재현 가능한지 분리 확인 | `baseline_manifest.json`, `reference_comparison.md`, `crop_*.png`, defect IDs | 비교용 스냅샷 확보. **품질 승인/FREEZE 아님**; 모델 SHA 및 재렌더가 없으면 검증 미완료로 기록 |
| **G1 공간 기획** | ChatGPT + Python/Shapely, Blender 검토 뷰 | 시장·필로티·캡슐·하역의 활동/사용자/개방성/출입점/동선 그래프와 존 폴리곤 결정. 아직 가구/해치 그리지 않음 | `program_1F.json`, 구획 오버레이, 공간 매트릭스, 면적표 | 필수 존 목적 존재, 구획 면적 모델 계산, 주동선 연결성 및 출입구 접근 |
| **G2 건축 모델** | Blender GUI, 기존 `engine/symbols`, Shapely checks | 기둥 34개 중 렌더 누락된 11개 원인 확인, ㅁ자 vs U자 계단 불일치 해결, 문·층고·화장실 확인. 수정을 원천 모델 작업 복사본에만 반영 | 승인 요청 대상 `1F_master.blend` 후보, object inventory, model-vs-slice diff, 독립 코어 상세 | 중복/매입/실제 충돌 근거 추적; 임의 hide 0; 계단 법규 미확인 별도 이슈 |
| **G3 가구** | Python/Shapely, `furniture_library.py` | 프로그램별 가구 **기종 → 군집 패턴 → 통로 확보 → 세부 배치** 순으로 생성. 물리 footprint와 시각 선 분리 | `furniture_layout_1F.json`, 활동별 크롭, 실제 가구 개수·면적·통로 보고 | 각 프로그램별 가구 종류/위치 타당, body polygon=실물 가구 수 오인 금지, 충돌 0 |
| **G4 제도** | SVG renderer, style tokens, Pillow, PDF 뷰어 | 동일 형태 그대로 선·포셰·해치/점묘/수목 상세, 마스킹/그리기 순서 튜닝. 1:500 본도와 선택형 확대의 LOD 분리 | 한 장의 동일 스타일 테스트 시트, 5개 고정 크롭 Before/After | 실제 크기에서 절단/유리/가구/배경 구분; 주요 선/가구 겹침 증가 없음 |
| **G5 통합 출력** | SVG, CairoSVG, ezdxf, PDF page validator | 공통 DrawingScene의 feature로 SVG/PDF/PNG/DXF 출력. 1F A3 1:500 유지; 3F 1:100 4분할 조립 검증 | `plan_1F_A3_1to500.*`, DXF, output manifest | 도형 ID·위치 정합, A3 물리 크기, 타일 겹침·printable region |
| **G6 독립 QA** | pytest, `engine/checks`, `tests/verify_pipeline.py` | 작성기 통계값을 믿지 않고 실제 산출 SVG/DXF/기하를 재검증; 고의 결함이 실패하는지도 테스트 | `qa_report.json`, negative tests, defect ledger | P0 기하/구조/출력 누락 0, known regression 0; 미확인 법규는 PASS 아님 |
| **G7 동결/승격** | GitHub PR, ChatGPT 비교 분석, 사용자 승인 | 기준/후보를 동일 뷰로 비교; 개선/악화/미해결 기록. 승인된 범위만 승격 | Draft PR, review scorecard, SHA, approved frozen manifest | 변화 유형 1개/PR, 기준본보다 타깃 개선, 비타깃 핵심 항목 퇴보 없음 |

**승인 인터뷰는 3개의 중요한 결정에 한정:** (i) 프로그램/공간 구성 재편, (ii) 구조·계단·피난 및 원천 모델 변경, (iii) 최종 학술지 제출용 도면 스타일/상세 시트 채택. 사소한 크롭·유틸·테스트·배치 세부는 자동 처리한다.

## 3. 현재 코드 기준으로 실제 호출 가능한 명령 (Windows PowerShell)

**주의:** 아래 명령은 실행 계약을 확인한 실행 예시이다. **실제 실행 성공은 미검증**, 해당 경로에 Blender/모델/필요 패키지가 있는지 먼저 확인한다. 새 도면은 기존 출력 폴더에 덮어쓰지 않고 독립 후보 폴더에 저장한다. 현 기준본은 읽기 전용.

### 3-1. 사전 점검 (읽기 전용)

```powershell
Set-Location -LiteralPath 'D:\Users\admin\Desktop\2학기 논문'
$repo = 'D:\Users\admin\Desktop\2학기 논문'
$blender = 'C:\Program Files\Blender Foundation\Blender 4.2\blender.exe'
$model = 'D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\model\1F_master.blend'
$out = 'D:\Users\admin\Desktop\2학기 논문\output\workflow_candidates\1F_candidate_001'
Test-Path -LiteralPath $blender
Test-Path -LiteralPath $model
python --version
& $blender --version
python -m pip show shapely ezdxf svgwrite cairosvg pillow numpy scipy pytest
Get-FileHash -Algorithm SHA256 -LiteralPath $model
```

가정: 프로젝트 루트에 코드가 있고 1층 master 파일 경로가 기존 조사에서 확인된 위치에 존재한다. `Test-Path`가 False라면 **경로·설치 상태 점검부터** 하고 경로 추측으로 실행하지 않는다. 실행 시 후보 폴더 경로는 새 ID로 변경한다.

### 3-2. 빠른 기하 프리뷰 (AO/Modal/합성 생략)

```powershell
# 1) Blender 1층 벡터 절단 정보만 생성 (작업 복사본 출력)
& $blender -b --factory-startup -P "$repo\src\01_headless_slicer.py" -- --input $model --out $out --cut 1.5 --floors 1F --phase slice

# 2) 위상/구획/라벨 및 레거시 CAD 레이어 생성: A3 렌더러가 floor_1F_layout.json을 필요로 함
python -I "$repo\src\02_topology_to_cad.py" --raw "$out\raw_slices" --out $out --floors 1F --scale 200

# 3) A3 1:500 도면과 주요 확대 크롭 생성
python -I "$repo\src\architectural_plan_renderer.py" --out $out --floor 1F --scale 500 --png-width 4096 --crops
```

**현재 구현의 제약:** (2) 단계의 DXF는 `--scale 200` 레거시 CAD 경로로 생성되므로 (3)의 1:500 A3 SVG와 **동일 도면 포맷이라고 주장하지 않는다**. 이 절차는 공간/제도 프리뷰 전용이다. `--phase slice`는 AO 및 cutmask를 생성하지 않으므로 현재 통합 QA를 바로 돌리면 필수 파일 누락으로 실패한다.

### 3-3. 전체 레거시 QA 필요 시 (비용 없는 로컬 Blender부터)

```powershell
# 기존 엔트리포인트는 AO 및 A1 레거시 합성까지 처리한다.
python -I "$repo\run_drawing_pipeline.py" --blend $model --out $out --floors 1F --size 2048 --samples 24 --scale 200 --skip-ai

# 같은 후보 입력에서 A3 1:500 출력 추가 생성
python -I "$repo\src\architectural_plan_renderer.py" --out $out --floor 1F --scale 500 --png-width 4096 --crops

# 레거시 검증(a~d) + A3 사양 검증(e) 재실행
python -I "$repo\tests\verify_pipeline.py" --out $out --floors 1F

# 모델 엔진 단위 테스트 (pytest 설치 시)
python -m pytest "$repo\engine\tests" -q
```

`run_drawing_pipeline.py`는 **A1 레거시 시트와 DXF를 생성하고 A3 정축척 시트는 별도 명령이 필요**하다. 따라서 통합 엔트리포인트가 완성되었다고 표기하지 않는다. 위 커맨드는 기존 코드 로직 기준일 뿐 현재 PC의 패키지와 Blender 실행 성공은 확인하지 않았다. 전체 QA는 빠른 프리뷰를 통과한 후보에만 사용한다.

### 3-4. 결과 검토 및 해시 기록

```powershell
$plan = "$out\final_sheets\plan_1F_A3_1to500.png"
$pdf = "$out\final_sheets\plan_1F_A3_1to500.pdf"
Test-Path -LiteralPath $plan
Test-Path -LiteralPath $pdf
Get-FileHash -Algorithm SHA256 -LiteralPath $plan
Get-FileHash -Algorithm SHA256 -LiteralPath $pdf
```

현재 비교용 1F 기준 파일은 `D:\Users\admin\Desktop\2학기 논문\output\drawing_pipeline_1F_master\final_sheets\plan_1F_A3_1to500.png`. 덮어쓰지 않는다.

## 4. 개선 후 목표 아키텍처 — 무엇을 새로 구현하는가

**기존 구현됨:** `engine/master`, `engine/symbols`, `engine/checks`, `engine/ledger`, `src/01_headless_slicer.py`, `src/02_topology_to_cad.py`, `src/architectural_plan_renderer.py`, `src/furniture_library.py`, `tests/verify_pipeline.py`.

**새로 구현할 인터페이스 (아직 존재하지 않음):**

1. `ProgramSpec` (zone_id, source_id, activity, subprogram, adjacency, entry_ids, planned_clearance_m, evidence_status). **형상은 기존 태그 Blender 모델에서 읽는다.** 임의 좌표를 이 JSON에 몰래 넣지 않는다.
2. `GeometryPlan` (source feature ID, 실제 절단 geometry, floor, source hash, program tags, constraint flags). **기둥 11개를 렌더링 시 임의 삭제하는 기능 금지.**
3. `FurnitureObject` (object_id, family, real_count=1, physical footprint, clearance, body polygons[], lines[], orientation, provenance). 개별 실물과 선/면 도형 수는 별도 집계.
4. `DrawingScene` (feature_id, source_id, geom_m, role, layer, style_token, print_scale, z_order). **종이 기준 선 두께는 한 스타일 표에서 변환**.
5. `Exporters`: 같은 DrawingScene → SVG → PDF/PNG(CairoSVG) + DXF(ezdxf). DXF는 대체로 표준 선가중치 집합만 허용하므로, 현 T1 0.45mm/T3 0.12mm/T5 0.08mm 등은 정확하게 저장되지 않을 수 있다. 지원값으로의 매핑/오차를 명시적으로 기록하고 SVG/PDF의 정확한 종이선폭을 정본으로 둔다.
6. `QAReport` (raw evidence, source-hash, artifact-hash, tests, independent geometry rechecks, printer fit, visual score, defect IDs, accept/reject). 렌더러의 자기 보고값만으로 성공 판정 금지.

**의존성 DAG 및 캐시 무효화:**

| 변경 사항 | 재실행해야 하는 단계 | 생략 가능한 단계 |
|---|---|---|
| 안내·공간 프로그램 명칭/관계만 변경 | ProgramSpec → 가구 → 제도 → QA | Blender 절단(형상 불변일 때) |
| 벽·기둥·문·계단·튜브 형상 변경 | Blender → Shapely → 가구 → 제도 → QA | 없음 |
| 가구 타입/배치 규칙만 변경 | Furniture Planner → 제도 → QA | Blender/기본 구조 절단 |
| 선 두께/해치/명암만 변경 | SVG 스타일 → PDF/PNG/DXF → 출력 QA | Blender/공간·가구 계산 |
| 시트 배치·범례/타일만 변경 | Sheet Layout → 출력 QA | 모델/프로그램/가구 |
| 법규·충돌 검사만 변경 | QA/해당 전용 테스트 | 모델 및 렌더(결과 재사용 가능할 때) |

캐시 키는 `(source_hash, program_spec_hash, geometry_algorithm_version, furniture_rule_hash, style_hash, output_profile_hash, seed)`의 관련 요소를 포함한다. 입력이 같아도 기하 알고리즘 변경 시 캐시를 무효화한다.

## 5. 현행 구조의 실무상 주의점

### 5.1 A3 1:500 vs 상세도

A3 1:500은 주변 맥락과 프로그램 배치를 보여주는 **주요 배치도**다. 참고 이미지 수준의 의자/부스/계단 세부 선을 전부 밀어 넣으면 가독성이 무너질 수 있다. 기존 축척을 바꾸지 않으면서 **별도의 1F 프로그램 상세 도면(축척은 다음 단계에서 검토)**을 제안하는 것이 합리적이다. 상세 시트 채택은 최종 표현 결정이며 사용자 승인 대상이다.

### 5.2 모델 원천과 그래픽 표현

현행 1F는 태그된 `.blend`를 가지고 있으므로 구조와 출입문은 그 모델에서만 확정한다. 프로그램·가구는 `PROPOSED`일 수 있으며 설명용 인필을 모델 확정 데이터로 주장하지 않는다. 상층은 GLB에 벽/문이 없어서 **그려진 것처럼 보이게 SVG에서 가상의 벽을 추가하지 않는다**; 벽과 문을 실제 모델 요소로 생성·검증한 다음 절단한다.

### 5.3 외부 앱/비용/설치

- **무료·현재 보유한 구성 우선**: Python·Blender·기존 로컬 에이전트 및 GitHub. 다른 CAD나 상용 앱을 신규로 도입하지 않는다.
- Modal은 **지금 기본 경로에서 제외**. 병렬 전층 렌더가 반드시 필요해질 때 사용량과 비용을 먼저 확인하고 사용자 승인 후 실행한다.
- Gemini 인필도 초기 S0~S3 단계에서는 건너뛴다. 구조/가구 도면의 진실성을 확인하기 전에는 효과보다 검증 부담이 크다.
- `CairoSVG` 의존성이 없으면 출력 실행을 실패로 기록한다. 사전 확인 없이 설치 완료로 보고하지 않으며, 기존 활성 Python 환경에서 지원되는 안전한 대안을 별도 검증할 때만 전환한다.
- GitHub Actions CI는 현재 저장소 트리에 `.github/workflows`가 확인되지 않았다. 따라서 PR 자동 검사가 이미 구성돼 있다고 가정하지 않는다. 초기에는 로컬 QA 로그와 비교 증거를 PR에 첨부한 뒤 CI를 추후 구축한다.

## 6. 품질을 재현성 있게 비교하는 방식

각 후보에서 **같은 floor, world crop bounds, seed, 종이축척, 렌더 DPI**를 사용한다.

- 자동 비교: (1) 모델/슬라이스의 source_id/폴리곤 개수, (2) 기하 충돌 개수·면적, (3) 개별 가구 물체 수/종류, (4) 기존 코드와 현재 결과가 가진 검사의 통과·실패, (5) A3 출력/가독/인쇄 가능 영역, (6) PNG 차이/변경 경계
- 사람이 비교: (1) 프로그램이 첫눈에 읽히는지, (2) 주동선·빈 공간의 구성, (3) 가구 유형의 개연성, (4) 구조→가구→해치 선 위계, (5) 참고 이미지 수준의 제도 정제도, (6) 실제 1:500 인쇄 적합성
- 거부 요건: 구조 객체 손실, 계단/피난 검증 미확정인데 법규 PASS 주장, 새 선 겹침, 본도 축척 훼손, 타깃 개선 미확인, 기준본보다 명백히 나빠진 항목
- 동일 결함이 **두 번의 미세 수정**에도 재발하면 수치 변경 중단 → 입력 프로그램/모델/렌더 책임 경계 다시 검사

## 7. 우선 구현 순서와 각 PR의 목표

| PR 작업 묶음 | 실제 수정·추가 대상(제안) | 완료 증거 |
|---|---|---|
| **T0 Baseline** | 모델/도면 SHA256 manifest 생성과 다섯 고정 크롭 뷰, JSON 보고서 | 재현되는 기준 크롭과 baseline manifest |
| **T1 Program Planning** | ProgramSpec schema + 동선/구획 충돌 평가 + 1F 프로그램 배치 메타데이터 | 가구가 없어도 공간 활동과 동선이 읽힘 |
| **T2 Model Fidelity** | 11개 기둥의 렌더 생략 차단, 계단 원천 통합, 모델↔slice ID reconciliation | 기둥/계단/문 누락 검증 통과 |
| **T3 Furniture Planning** | object-level furniture metadata와 계획용 keep-out, 활동별 카탈로그 배치 | 공간별 개수/종류/동선 보고 및 크롭 |
| **T4 Style Isolation** | 단일 스타일 표와 변환기, 스타일 테스트 시트, 인쇄 LOD | 시각 Before/After + mm 검증 |
| **T5 Export Consistency** | DrawingScene과 SVG/DXF 공통 feature map, A3 PDF export 검사 | 동일 도형 feature ID 및 위치 일치 |
| **T6 Regression Gate** | 독립 QA 및 negative tests, GitHub PR 체크리스트 | 알려진 회귀 0, 실패 사례에서 올바른 FAIL |

작업 단위는 하나의 문제·한정된 파일 변경으로 유지하며, 사용자 승인 없이 브랜치 코드를 `main`에 병합하지 않는다.

## 8. 가장 가까운 실행 결정

**T0 비교 스냅샷은 이미 확보했다(1층 품질 승인 아님).** 이제 T1 1층 프로그램 기획을 시작하고, T2 모델·T3 가구·T4 스타일·T5 출력·T6 QA를 순서대로 반복 보완한다. 각 후보는 이전 채택본보다 개선될 때만 채택한다. **전체 1층의 공간·구조·가구·제도·인쇄 품질을 사용자가 최종 승인하면 그때만 `1F_FINAL_FROZEN`으로 표시한다.** 참고 도면의 선 느낌을 복제하는 작업은 T4에서 수행한다.

## 기술 근거 (공식 문서)

- Blender 4.2 CLI: https://docs.blender.org/manual/en/4.2/advanced/command_line/arguments.html
- Shapely STRtree: https://shapely.readthedocs.io/en/stable/strtree.html
- CairoSVG: https://cairosvg.org/documentation/
- ezdxf lineweights: https://ezdxf.readthedocs.io/en/stable/concepts/lineweights.html
- Modal 비용 안내: https://modal.com/pricing
