# C-T14O: 실제 건축물처럼 보이는 G-002 3D/PBR 재렌더 실행

## 목표와 원인

사용자는 PR #21, #23의 색보정·2.5D 합성 결과가 실제 건축 렌더처럼 보이지 않는다고 판정했다. PR #23의 `tools/t14n/hero_composite.py`는 원본 JPEG 건물에 `ImageEnhance`, 선명도, 색상을 적용하고 AI 배경만 결합한다. 이 경로에는 건물 재질의 BRDF, 반사·투과, 표면 법선에 따른 빛, 정확한 그림자와 GI를 실제로 계산하는 3D 렌더러가 없다.

**핵심 발견:** 과거 `tools/t14i/axon.py`와 `src/book_views.py`는 `model_world.npz`와 `model_objects.json`으로 **전체 모델 정점·삼각형·객체 분류**를 읽는다. 원래 GLB나 전체 `.blend` 장면이 없어도 실제 캐시 메쉬를 Blender에 다시 배치할 수 있다. 이는 원본 캐시의 원래 재질·카메라·조명·환경이 복구되었다는 뜻은 아니다.

## 정확한 기준·출처

- Source manifest: `docs/t14i_v4/source_manifest.json` (원본 GLB는 없고 캐시만 존재함)
- 권위 있는 캐시 `model_world.npz` SHA256 `992e2ec51ec17dc494ed2f99ddb11298671449dd6661d92df3b3536a0049537b`
- 객체 레지스트리 `model_objects.json` SHA256 `722dd7359e2f13534ff4ae91088ba8649e8a8f96b27c60f000ddb09c01106488`
- 사용자의 로컬 입력 후보 경로: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14K\output\C_T14K_run\model_cache`
- 위 입력 경로는 **후보 위치**다. 존재를 가정하지 말고 실제 파일 유무를 확인한다. 다른 빌드의 캐시는 해시가 다르면 무조건 중단한다.
- 최신 베이스: GitHub Draft PR #23, commit `399d3acce7a5d6428373bb52122271876a6a3e9a`.

## 실행 경로 (PowerShell, 로컬 사용자 컴퓨터)

Windows 전용. PowerShell에서 Blender 4.x가 PATH에 이미 설치된 경우를 가정한다. 프로그램 설치·구독·비용 결제는 승인하지 않았다.

```powershell
$Repo = 'D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14O'
$Cache = 'D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14K\output\C_T14K_run\model_cache'
$Run = 'D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14O\output\C_T14O_PBR'
if (!(Test-Path (Join-Path $Cache 'model_world.npz'))) { throw "Missing verified mesh cache: $Cache" }
if (!(Test-Path (Join-Path $Cache 'model_objects.json'))) { throw "Missing object registry: $Cache" }
if (!(Get-Command blender -ErrorAction SilentlyContinue)) { throw 'Blender executable not found in PATH; locate installed Blender before running.' }
Set-Location $Repo

python tools/t14o/cache_validation.py --cache-dir $Cache --expected-npz-sha256 992e2ec51ec17dc494ed2f99ddb11298671449dd6661d92df3b3536a0049537b --expected-objects-sha256 722dd7359e2f13534ff4ae91088ba8649e8a8f96b27c60f000ddb09c01106488 --report (Join-Path $Run 'cache_audit.json')
if ($LASTEXITCODE -ne 0) { throw 'SOURCE_CACHE_QA_FAILED' }

# 새로운 빈 출력 디렉터리만 허용한다. 기존 결과 덮어쓰기를 금지한다.
# 먼저 소형 프리뷰로 면 방향·메시 누락·카메라·그림자를 검사한다.
blender -b --factory-startup -P tools/t14o/blender_pbr_scene.py -- --cache-dir $Cache --out-dir (Join-Path $Run 'G002_A_daylight_PREVIEW') --variant daylight --width 1600 --height 900 --samples 16
if ($LASTEXITCODE -ne 0) { throw 'PREVIEW_PBR_FAILED' }
# 프리뷰의 실물 시각 검수가 통과한 후에만 최종 해상도를 렌더한다.
blender -b --factory-startup -P tools/t14o/blender_pbr_scene.py -- --cache-dir $Cache --out-dir (Join-Path $Run 'G002_A_daylight') --variant daylight --width 4800 --height 2700 --samples 64
if ($LASTEXITCODE -ne 0) { throw 'DAYLIGHT_PBR_FAILED' }
blender -b --factory-startup -P tools/t14o/blender_pbr_scene.py -- --cache-dir $Cache --out-dir (Join-Path $Run 'G002_B_bluehour') --variant bluehour --width 4800 --height 2700 --samples 64
if ($LASTEXITCODE -ne 0) { throw 'BLUEHOUR_PBR_FAILED' }
```

고품질 렌더 후에도 G-002 전용 `CANDIDATE_V4.3` 반영은 자동으로 하지 않는다. 실제 모델·재질·카메라·조명과 기하 검토가 완료되기 전에는 `PBR_PREVIEW_ONLY__HUMAN_GEOMETRY_AND_VISUAL_QA_PENDING`이다.

## 코드가 실제로 하는 일

1. NumPy 캐시의 SHA256, 실제 삼각형 인덱스·객체별 인덱스 범위·중복 구간, 객체 층 태그·전체 높이를 검사한다.
2. 모든 실제 캐시 삼각형을 Blender mesh 객체로 생성한다. 임의로 슬래브나 코어, 튜브를 새로 만들지 않는다.
3. 소스 종류별로 **시각화용 가정** 재질을 지정한다. 슬래브·코어·기둥 = 거친 콘크리트, 유리 튜브 = 투과성 유리, 파사드 종류만 있는 면 = 불투명 중립 재질, 샤프트 = 브러시드 메탈. 파사드가 실제 유리인지 판정되지 않았으므로 전체를 유리로 렌더링하지 않는다. 이것은 실제 건축자재의 확정이 아니다.
4. 광선 추적 Cycles 렌더링, 자연광과 면광원, 유리의 반사·투과 및 물리 기반 셰이딩을 적용한다.
5. 2점 원근 카메라를 **새로 제안**한다. 분실된 G-002 원본 카메라와 일치한다고 주장하지 않는다.
6. 1F 슬래브 높이를 확인한 경우에만 기본 시각화용 지면을 만든다. 실제 측량 지형·신당동 배경은 사용 가능 근거가 없으면 생성하지 않는다.
7. 새로운 후보 `.blend`, 4800x2700 PNG, 원본과 렌더 SHA, 조건 및 경고를 함께 저장한다.

## 무엇을 반드시 검수해야 하는가

- 정점·삼각형 수, 종류별 객체 수, 1F~15F 및 B1/B2 레벨, 4개 코어, T1~T4, 슬래브 보이드·중간정원·지붕 토폴로지에 대한 원본 대조
- 렌더와 원본 G-002의 건축 형상 일치 여부. 새 카메라이므로 무조건 픽셀 비교하지 말고 3D landmark와 도면을 같이 사용
- 유리/콘크리트/금속과 빛의 사실성, 고스트 면·법선 뒤집힘·바닥 매립·잘못된 1F 지면 표시 여부
- 주변 도시·식재·사람의 스케일과 배경은 확인된 자료가 있을 때만 합성, 시각적 가정임을 보고서에 표시
- full-size 100% 이미지와 A3 300dpi 페이지 렌더. 원본 JPG 컬러 필터 결과와 실제 차이가 보여야 한다
- 객관적 전수점검 통과와 별도로 독립 시각 리뷰가 4/5 이상이어야 하는 이전 C-T14N 원칙 유지

## 현재 이 세션의 검증 범위

- [x] 이전 작업의 실패 원인을 실제 GitHub 코드와 QA 자료에서 추적
- [x] 기존 메시 캐시를 Blender에서 사용할 수 있는 소스 코드 경로 확인
- [x] 캐시 검수기 + Blender Cycles 장면 생성기 구현
- [x] 캐시 검수 합성 테스트 9/9 통과 및 Python 소스 문법 검수
- [ ] **실제 캐시 바이너리의 로컬 해시·층수·구조 검증** (현재 작업 컨테이너에 캐시 없음)
- [ ] **Blender PBR 4800×2700 실물 PNG** (현재 작업 컨테이너에 Blender 없음)
- [ ] 실제 외관 시각 품질 승인, 독립 도면 정확성 승인, V4.3 인수

기획만으로 실제 렌더링이 완료되었다고 표시하지 않는다. 사용자 화면에 원본/새 Cycles 이미지를 **실제 픽셀로** 나란히 보여주는 것이 다음 성공 게이트다.