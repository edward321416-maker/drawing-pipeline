# Claude Code 실행 지시서 C-T11 — 1층 모델·출입문 원천 대조

- 작성: 2026-11-03
- 상태: **실행 지시서 / 실제 로컬 Claude Code 미실행**
- 프로젝트: `D:\Users\admin\Desktop\2학기 논문`
- GitHub: https://github.com/edward321416-maker/drawing-pipeline
- 지시서 브랜치: `chatgpt/claude-t11-execution-brief-20261103`; **코드 기준은 PR #4 HEAD `85b8742f5a66c07162c941c86248d6c65a77e77c`**이며, 실제 작업 HEAD는 시작 시 SHA로 기록한다.
- 연결 이력: S0 비교 스냅샷 PR #2 → 프로그램 기획 PR #3 → 출입문 감사 PR #4
- 이번 목표: **로컬 .blend를 검증하고 실제 1층 절단 JSON과 3D 마스터 JSON의 문 객체를 대조한 증거 확보**. 건축 형상·가구·제도 스타일을 수정하지 않는다.

## 1. Claude Code에게 전달하는 작업 계약

1. 원본 `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\model\1F_master.blend`를 읽기 전용으로 감사하고 SHA256/Blender 버전/모델 객체 목록을 기록한다.
2. GitHub 직렬화된 3D 모델 `D:\Users\admin\Desktop\2학기 논문_T11_검증\engine\model\1F_master.model.json`과 실제 .blend 모델 사이의 소스 버전 차이를 구분한다. **두 포맷의 파일 해시 자체를 서로 비교하는 오류 금지.**
3. Blender 4.2 헤드리스 절단기로 실제 `floor_1F_slice.json`을 새 후보 폴더에 만든다. 자산이 없으면 오류를 숨기지 말고 HOLD를 기록한다.
4. `tools/audit_g1_access_anchors.py`의 source-only 및 actual-slice 모드를 실행하고, `tests/test_g1_access_audit.py` 및 `tests/test_g1_program_spec.py`를 실제 환경에서 돌린다.
5. 출입문을 코어/화장실, 공공 시장 커튼월, 캡슐, 대지 접근 화살표로 **원천 출처별 분리**한다. 가까운 문/렌더러 문은 모델에 실제 개구가 있다는 증거가 아니다.
6. 실제 모델에 없는 외벽 개구부와 문은 **임의로 생성하지 않는다**. 설계결정 필요로 분리하고 다음 작업의 후보를 제시한다.
7. 로그/해시/중단 사유와 전체 경로를 근거로 PASS/HOLD/FAIL 판정한다. 최종 도면 FREEZE 금지.

## 2. 변경 권한과 안전 규칙

- **금지**: 원본 .blend, 기존 `D:\Users\admin\Desktop\2학기 논문\도면\02_최종결과물` 및 기준 PNG 덮어쓰기; 임의 기둥/계단/벽/도어 이동·삭제·추가; main 병합; PR #2~#4 수정; 강제 push; reset --hard/clean -fd; Modal 과금/클라우드 렌더; 불필요한 패키지 설치.
- `D:\Users\admin\Desktop\2학기 논문\AGENTS.md` 및 `D:\Users\admin\Desktop\2학기 논문\rules\AGENTS.md`를 먼저 읽는다. 1:400/1:200과 최근 A3 1:500/1:100의 충돌은 변경하지 않고 기록한다.
- 사용자 PC의 원본 브랜치를 전환하지 않도록 **별도 worktree**를 사용한다. 원본이 dirty라도 stash/reset/삭제하지 않는다.
- 진단용 스크립트 버그만 재현 후 국소 수정 가능. 변경하려면 **unified diff**와 실패를 고정하는 회귀 테스트가 필요하다.
- 본 작업의 모델 변경 범위는 **0**. 새로운 실제 문 위치/형식은 건축 설계에 영향을 주는 중요 결정이므로 사용자 승인이 필요하다.
- 소스/입력·출력 파일은 보고서에 항상 전체 절대 경로를 표기한다.

## 3. PowerShell: 안전한 분리 작업공간

아래는 사용자 PC에서 Claude Code가 실제 환경·경로를 확인하고 실행할 명령 예시다. 미리 성공을 선언하지 않는다.

```powershell
$root = 'D:\Users\admin\Desktop\2학기 논문'
$wt = 'D:\Users\admin\Desktop\2학기 논문_T11_검증'
$basePolicy = '85b8742f5a66c07162c941c86248d6c65a77e77c'
$sourceBranch = 'chatgpt/claude-t11-execution-brief-20261103'
$localBranch = 'claude/t11-local-validation-20261103'

git -C $root rev-parse --show-toplevel
git -C $root remote get-url origin
git -C $root status --short
git -C $root fetch origin $sourceBranch
$expected = git -C $root rev-parse "origin/$sourceBranch"
git -C $root merge-base --is-ancestor $basePolicy $expected
if ($LASTEXITCODE -ne 0) { throw "감사 코드 기준 PR #4의 후속 브랜치가 아닙니다: $expected" }

if (Test-Path -LiteralPath $wt) { throw "기존 작업 폴더가 있습니다: $wt" }
git -C $root worktree add -b $localBranch $wt $expected
$actual = git -C $wt rev-parse HEAD
if ($actual -ne $expected) { throw "예상 HEAD 불일치: $actual" }

$model = 'D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\model\1F_master.blend'
$blender = 'C:\Program Files\Blender Foundation\Blender 4.2\blender.exe'
$out = Join-Path $wt 'output\g1_t11_local_001'
Test-Path -LiteralPath $model
Test-Path -LiteralPath $blender
python --version
python -c "import shapely; print(shapely.__version__)"
```

작업 폴더가 이미 있거나 정확한 Git 브랜치/커밋이 다르면 안전한 독립 위치를 다시 조사한다. **기존 폴더를 지우거나 덮어쓰지 않는다.**

## 4. 실제 검증 명령

```powershell
Set-Location -LiteralPath $wt

# 현재 체크아웃된 마스터 JSON의 Git blob SHA가 원본과 같은지 대조
git hash-object "$wt\engine\model\1F_master.model.json"
# 예상: a1651daefd8dafec3e9b089abd3803ac6776164b

# 원본 .blend가 실제 있을 때만 개별 파일 해시 기록
if (Test-Path -LiteralPath $model) {
    Get-FileHash -Algorithm SHA256 -LiteralPath $model
}
Get-FileHash -Algorithm SHA256 -LiteralPath "$wt\engine\model\1F_master.model.json"

# 실제 테스트로 PASS/FAIL 수집
python -m unittest discover -s tests -p 'test_g1_program_spec.py' -v
python -m unittest discover -s tests -p 'test_g1_access_audit.py' -v

New-Item -ItemType Directory -Path $out -Force | Out-Null

# 모델 JSON 기반 출입문 원천 검사
python "$wt\tools\audit_g1_access_anchors.py" --out "$out\access_source_only.json"

# 실제 입력이 없는 경우 여기부터는 실행하지 말고 HOLD 근거로 남긴다
if (-not (Test-Path -LiteralPath $model)) { throw "1F 원본 blend 없음: 절단 보류" }
if (-not (Test-Path -LiteralPath $blender)) { throw "Blender 4.2 없음: 절단 보류" }

# 1F 1.5m 단면만 생성, 무거운 렌더 없음
& $blender -b --factory-startup -P "$wt\src\01_headless_slicer.py" -- --input $model --out $out --cut 1.5 --floors 1F --phase slice
if ($LASTEXITCODE -ne 0) { throw "Blender 절단 실패 ($LASTEXITCODE)" }

$slice = "$out\raw_slices\floor_1F_slice.json"
if (-not (Test-Path -LiteralPath $slice)) { throw "절단 JSON 미생성: $slice" }
Get-FileHash -Algorithm SHA256 -LiteralPath $slice

# 모델 문과 시장/캡슐 외피의 위치 근접성만 확인
python "$wt\tools\audit_g1_access_anchors.py" --slice $slice --out "$out\access_with_slice.json"
if ($LASTEXITCODE -ne 0) { throw "출입문 감사 실패 ($LASTEXITCODE)" }
```

실패하면 우선 그 지점까지의 성과를 문서화한다. Blender 경로가 없으면 임의 설치하지 않고, 원본 파일/도구의 실제 위치 확인 결과를 남긴다.

## 5. 구체적인 비교 대상

| 항목 | GitHub 기준 기대값(확인 사실) | 사용자 로컬에서 해야 할 검사 |
|---|---|---|
| 3D 직렬화 마스터 객체 | 189개 | 실제 .blend 객체 태그별 개수 |
| 기둥 | 34개 | .blend + slice의 개별 구조기둥 |
| 모델 문 | 11개(코어 8·화장실 3) | 실제 .blend/slice에서 모두 대조 |
| 시장 커튼월 문 | 렌더러에서 생성한 5개 그래픽 | 3D 개구/문이 실제로 있는지 검증 |
| 캡슐 출입문 | 렌더러에서 캡슐 외곽점 투영 | 3D 개구/문이 실제로 있는지 검증 |
| Main/Subway/Service | 대지 접근 표식 3개 | 물리 출입문과 혼동 금지 |
| 위계·축척·가구 | 이번 범위에서 미수정 | 변경 없음을 Git diff로 확인 |

서로 다른 버전이면 로컬 .blend를 임의로 GitHub JSON에 맞추지 않는다. **어떤 버전이 최신·승인된 원천인지 우선 증거를 정리**한다.

## 6. 산출물

아래 경로의 새로운 폴더에만 생성한다.

- `D:\Users\admin\Desktop\2학기 논문_T11_검증\output\g1_t11_local_001\access_source_only.json`
- `D:\Users\admin\Desktop\2학기 논문_T11_검증\output\g1_t11_local_001\raw_slices\floor_1F_slice.json` (실행 성공 시)
- `D:\Users\admin\Desktop\2학기 논문_T11_검증\output\g1_t11_local_001\access_with_slice.json` (실행 성공 시)
- `D:\Users\admin\Desktop\2학기 논문_T11_검증\output\g1_t11_local_001\source_manifest.json` (HEAD, 세 가지 입력/출력 해시, Python/Blender 버전)
- `D:\Users\admin\Desktop\2학기 논문_T11_검증\output\g1_t11_local_001\T11_verdict.md` (PASS/HOLD/FAIL, 테스트 수, 출처별 문 목록, 누락·충돌 근거, 다음 설계 승인 사항)

종료 보고서 필수:
1. 정확한 HEAD와 작업한 모델/절단 JSON의 SHA256.
2. GitHub 189/34/11 기준과 로컬 검출 수치 차이 및 원인.
3. 모델 문/커튼월 렌더 그래픽/캡슐 렌더 그래픽을 구분한 결론.
4. 실제 실행한 테스트의 통과·실패 수와 로그.
5. `gate_passed=false`를 데이터 출처 검사 성공과 구분. 실제 개구부/접근성 검증이 없다면 `HOLD_DESIGN_DECISION`.
6. 소스 변경이 없으면 `NO_CODE_CHANGE`, 수정 시 unified diff와 회귀 테스트.
7. 한 줄 체크포인트: `HEAD | TESTS_PASS/TOTAL | MODEL_HASH | SLICE_HASH_OR_MISSING | DOOR_PROVENANCE | VERDICT | TOKENS_UNKNOWN_OR_ESTIMATED`.
8. 기록 목적지가 승인되어 접근 가능할 때만 지정 Google Sheet `1vR-DWvzcq904to6ltLxXZ1w_vPo8e9MLOh_IgMwJbdQ`의 `AI_Execution_Log`를 갱신한다. 인증이 없으면 로컬 기록을 만들고 **PENDING / NOT SYNCED**로 표기한다.

## 7. 종료 조건

실제 자료가 확인됐으면 결과를 증거와 함께 제출한다. 자료가 없으면 **어디까지 확인했는지와 결손 입력**을 제시하는 HOLD 보고서를 제출한다. 중요 설계 결정인 시장/캡슐의 실제 문 위치·폭·개구 형식은 이번 작업에서 묻거나 생성하지 말고 다음 건축 설계 단계로 이관한다.

**이번 작업은 도면 재생성이 아니라 원본-절단-출입문 감사다.** 1층 전체 최종 FREEZE는 사용자 승인 때까지 금지한다.
