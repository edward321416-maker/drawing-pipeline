# G1/T1.1 — 1층 실제 출입문 앵커의 원천 감사

- 작성일: 2026-11-03
- 상태: **SOURCE PROVENANCE CONFIRMED / PHYSICAL OPENING UNVERIFIED**
- 기준 커밋: `0c35263117d52c9c3713d800bf4707b1fe7805a7` (G1 설계 제안 Draft PR #3)
- 구조·가구·렌더러·기존 1층 도면을 수정하지 않는다. 1층 전체 FREEZE 아님.

## 1. 코드 확인 결과

| 구분 | 실제 원천 | 판정 |
|---|---|---|
| 대지 진입 Main/Subway/Service | `m_site_source.json` → `build_context_objects()` → `context.entrance` | 접근 방향 표지. 물리적인 문 아님 |
| 코어·화장실 출입문 | `build_master.py` → `build_stair_core()` / `build_restroom()` → `door` 객체 | 마스터에서 생성된 실내 문. 외부 커튼월 출입문과 구별 |
| 시장 커튼월 양개문 | `architectural_plan_renderer.py:389` `solve_curtain_doors()` | **렌더러에서 계산한 제도용 5개 문**. 실제 벽 개구 확인 안 됨 |
| 서측 캡슐 이중문 | `architectural_plan_renderer.py:1115+` 캡슐 바깥선을 시장 방향으로 투영 | **제도 표현에서 생성**. `Tube CAP_W`에 물리 개구가 있다는 증거 없음 |
| 1층 문 개구 11개 | `plan_1F_A3_1to500_check.json`의 `door_gaps_punched` | 렌더러 내부 문 개구 처리 수치. 물리 커튼월 개구와 별개 |

GitHub 저장소에는 `.blend` 바이너리와 `raw_slices/floor_1F_slice.json`이 없다. 따라서 이 회차의 감사 결과는 **원천 코드/도면 검사에 따른 provenance 판정**이며 **실제 문 위치의 기하 검증 완료가 아니다**.

## 2. 프로그램 앵커 판정

| 앵커 | 현 상태 | G1에서 허용되는 사용 |
|---|---|---|
| `ENTRY_MAIN` | 사거리→필로티 대지 접근 확인 | 필로티 외부 접근을 설명 |
| `ENTRY_SUBWAY` | 지하철→선큰 접근 확인 | 선큰 접근을 설명 |
| `ENTRY_SERVICE` | 동측 하역 접근 확인 | 서비스 접근을 설명 |
| `PUBLIC_MARKET_DOOR` | **UNVERIFIED_MODEL_OPENING** | 실제 문 검증 전 M01·P01의 확정 폴리곤 기준점으로 사용 금지 |
| `CAPSULE_DOOR` | **UNVERIFIED_MODEL_OPENING** | 실제 문 검증 전 C01·C04의 확정 폴리곤 기준점으로 사용 금지 |

`T1/T3/T4/PL`은 모델 기반 수직 동선 후보지만, 실제 시장 주출입문에서 연결 가능한지 검증되지 않았다. 출입점이 모호하다고 임의 좌표로 보정하지 않는다.

## 3. 현행 모델을 건드리지 않는 T1.1 감사 절차

프로젝트 루트의 **별도 작업 폴더**를 이용한다.

```powershell
Set-Location -LiteralPath 'D:\Users\admin\Desktop\2학기 논문'
$repo = 'D:\Users\admin\Desktop\2학기 논문'
$out = Join-Path $repo 'output\g1_t11_access_candidate'

# 1. 소스 코드·대지 접근점의 출처만 검사 (현재 GitHub 자료로도 가능)
python "$repo\tools\audit_g1_access_anchors.py" --out "$out\access_source_only.json"

# 2. 로컬 마스터 .blend의 위치/블렌더 존재 여부 검증
$model = Join-Path $repo '도면\00_엔진\model\1F_master.blend'
$blender = 'C:\Program Files\Blender Foundation\Blender 4.2\blender.exe'
Test-Path -LiteralPath $model
Test-Path -LiteralPath $blender
Get-FileHash -Algorithm SHA256 -LiteralPath $model

# 3. 둘 다 존재할 때에만 Blender로 1층 절단 JSON 새로 생성
& $blender -b --factory-startup -P "$repo\src\01_headless_slicer.py" -- --input $model --out $out --cut 1.5 --floors 1F --phase slice

# 4. 실제 1층 모델 문 객체와 구획/캡슐 외피의 근접성 감사
python "$repo\tools\audit_g1_access_anchors.py" --slice "$out\raw_slices\floor_1F_slice.json" --out "$out\access_with_slice.json"

# 5. 도구 회귀 테스트 (기존 도면/모델 건드리지 않음)
python -m unittest discover -s tests -p 'test_g1_access_audit.py' -v
```

**실행 전 유의:** 경로는 이전에 보고된 사용자 PC 경로이며 실제 로컬 존재 여부는 확인하지 않았다. `Get-FileHash`는 `Test-Path`가 True일 때만 실행해야 한다. 검사기에서 `ok_source_references=true`는 원천 참조 무결성만 뜻한다. `gate_passed=false`와 `model_opening_verified=false`가 남으면 T1.1 물리 개구 승인이 아니다.

## 4. 왜 출입문을 임의 확정하지 않는가

G1 프로그램 계획의 M01(안내)·P01(필로티 통과)·C01(캡슐 전시 안내)은 출입문 위치에 직접 좌우된다. 문을 시장과 가까운 곳에 임의로 만든 뒤 프로그램 면적을 고정하면, 향후 3D 모델과 충돌하거나 시각적 구획을 다시 그려야 한다.

따라서 다음 작업은 **기존 태그 .blend의 실제 1층 슬라이스를 확보해 감사**하는 것이다. 커튼월 문·캡슐 문이 원천 모델에 없다면 독립적인 건축 상세 결정(출입 위치/폭/문 형식/접근/피난 검토)으로 분리하여 사용자가 최종 모델 형상 변경을 승인한 후 생성한다.

## 5. 자동검사 범위와 다음 단계

- 이번 변경: `tools/audit_g1_access_anchors.py`, `tests/test_g1_access_audit.py`, 소스 감사 JSON 및 이 문서.
- 독립된 작은 기하 fixture에서는 정상/오인/잘못된 층/불확정 출입문 등 테스트 **7/7 PASS**. 이 실행은 **격리 시험용 도형**에 한정된다. GitHub 파일 자체 및 실제 1F Blender 파이프라인 실행은 이 세션에서 수행하지 않았다.
- 실제 `1F` 슬라이스를 읽으면 모델 `door` 객체와 `Zone_Market`, `Capsule_W`의 경계 근접성을 검사한다. **문 근접성은 개구·방화·피난·문 사용 가능성의 인증이 아니다.**
- T1.2: 시장·필로티·서비스·캡슐의 실제 공간 폴리곤을 생성하되, 문 앵커가 검증되지 않으면 출입문 인접 프로그램과 연결 경로는 `PENDING`으로 유지. 실면적과 보호동선이 검증된 후에야 시각 후보를 비교한다.

**결론:** `T1.1 SOURCE_AUDIT_RECORDED`, `PHYSICAL_DOOR_VERIFICATION_PENDING`, `G1_GEOMETRY_PENDING`, `1F_FINAL_FROZEN=false`.
