# `reference/19A06_HYBE` — FHHH friends HYBE 도면/이미지 수집·분석 패키지

**수집 상태: `CAPTURE_DONE` (원본 이미지) — 2026-11-04 사용자 PC에서 실행. 프로젝트 이미지 90/90 다운로드, 실패 0. `STYLE_ANALYSIS_DONE`·`STYLE_APPLIED`는 아직 미완료.**

## 수집 결과 (2026-11-04, Claude Code 로컬 실행)

실행: 별도 가상환경(playwright 1.57.0, Pillow 13.0.0 — 12.3.0은 설치 불가여서 최신 사용) + 설치된 Chrome 경로. 지정 URL 한 곳만 열었고 로그인·우회 없음.

- 스크립트가 찾은 prismic 이미지 URL 166개 중 **이 프로젝트(HYBE 19A06) 이미지는 90개**다. 페이지 데이터(`__NEXT_DATA__`)의 `pageData.work` 기준: 썸네일 1 + 본문 블록 16(다이어그램·스케치·액소노·모델) + 사진 갤러리 73(15개 슬라이드 그룹).
- 나머지 74개는 같은 사이트 `works`(다른 FHHH 프로젝트 썸네일), 2개는 사이트 공통 에셋(og.jpg, 로고)이다. 분석 대상이 아니며 `manifests/other_work_assets.json` 에만 목록을 둔다.
- **검증**: 갤러리 슬라이드 그룹 수 15 = 페이지 우측 번호 1~15. 프로젝트 이미지 90개 모두 `originals/` 에 있고 sha256 기록(`manifests/project_assets.json`), 누락 0.
- **한계**: 스크롤 캡처는 1장뿐이다(페이지가 내부 스크롤 컨테이너라 창 스크롤이 먹지 않음). 갤러리 슬라이드 클릭 캡처 0장. 원본 이미지 자체는 데이터에서 직접 받았으므로 영향은 없지만 화면 캡처 증거는 부족하다.
- **이 페이지에는 평면도가 없다.** 자동 분류의 DRAWING_CANDIDATE 9개는 공간 다이어그램, 5 blocks 단면 다이어그램, 단면 스케치, 액소노메트릭, 텍스트 목록이며 사진이 대부분이다(모델 사진, 실내 사진). 평면도(8~16F, 1F)는 보조 출처(studio COM, ArchDaily)에만 있고 이번에 받지 않았다.
- 원본 이미지 합계 약 145 MB는 `.gitignore` 대상이라 Git에 올리지 않는다.

## 원본 및 출처

- FHHH 원본: https://fhhhfriends.com/19a06
- studio COM의 같은 프로젝트 시각 도면(보조 자료): https://c-o-m.kr/hybe/office
- HYBE 프로젝트 설명·도면 목록(보조 자료): https://www.archdaily.com/1016294/hybe-headquarters-office-com-plus-fhhh-friends
- 기타 확인된 개별 공개 URL은 `manifests/source_catalog.json`에 별도 보존.

## 디렉터리

```text
reference/19A06_HYBE/
├─ originals/                    # 페이지 이미지 원본 (현재 비어 있음)
├─ captures/                     # 브라우저 스크롤/갤러리 캡처 (현재 비어 있음)
├─ contact_sheets/               # 자동 표제판/썸네일 (실제 수집 후 생성)
│  └─ index.html                 # 최초 빈 갤러리, 로컬 실행 후 갱신
├─ analysis/
│  ├─ STYLE_AUDIT.md             # 현재 확인 가능한 사실과 잠정 스타일 분석
│  ├─ style_tokens.proposed.json # 우리 도면 적용 제안값(원본 측정값 아님)
│  └─ CLAUDE_C_T13B_STYLE_APPLICATION.md
├─ manifests/
│  ├─ source_catalog.json       # 출처 URL과 미다운로드 상태
│  └─ analysis_manifest.json    # 현재 실제 분석한 외부 원본 0개
├─ our_baseline/
│  └─ 1F_Program_Concept_V2_B.png
├─ scripts/
│  ├─ capture_reference.py      # 전체 페이지 캡처+이미지 원본 다운로드
│  ├─ analyze_reference.py      # 해시/분류/연락판/HTML 갤러리
│  └─ filter_project_assets.py  # 페이지 데이터에서 '이 프로젝트' 이미지만 분리·대조 (2026-11-04 추가)
└─ tests/
   └─ test_reference_utils.py
```

## 사용자 PC에서 실행 (Claude Code)

1. ZIP을 `D:\Users\admin\Desktop\drawing-pipeline-repo\reference\19A06_HYBE`로 풀거나 전체 `reference` 폴더를 복사한다. 기존 데이터가 있다면 **덮어쓰기 전에 확인**한다.
2. `drawing-pipeline-repo`를 대상으로 새 격리 작업 브랜치/작업공간을 이용한다. 다른 연구 프로젝트 `vertical-commercial-pedestrian-flow`는 건드리지 않는다.
3. Python과 **이미 설치된 Chrome 또는 Edge**를 우선 사용한다. 아래 명령은 PowerShell 예시이며 초기 원본은 수정하지 않는다.

```powershell
Set-Location -LiteralPath 'D:\Users\admin\Desktop\drawing-pipeline-repo'
python -c "import playwright, PIL; print('dependencies OK')"
python reference\19A06_HYBE\scripts\capture_reference.py --url 'https://fhhhfriends.com/19a06' --output 'reference\19A06_HYBE'
python reference\19A06_HYBE\scripts\analyze_reference.py --root 'reference\19A06_HYBE'
```

4. `manifests/capture_manifest.json`의 `discovered_image_urls`, `downloaded_unique`, `download_failed`를 확인하고, 갤러리의 실제 번호와 스크롤 캡처 수를 대조한다. 숫자가 불일치하면 `ASSET_MISSING`으로 기록한다.
5. `contact_sheets/index.html`을 열어 도면·사진을 인간이 분류하고 `analysis/STYLE_AUDIT.md`의 잠정 가정을 근거와 비교한다.
6. `analysis/CLAUDE_C_T13B_STYLE_APPLICATION.md`에 따라 기존 1층 도면의 **실제 모델 기반** A/B 새 출력 파일을 생성한다.

**의존성 누락 시:** 사용자가 승인한 기존 환경에서 해결하고, 설치가 꼭 필요하면 별도 가상환경에 무료 `playwright==1.57.0`, `Pillow==12.3.0`을 설치한다. Playwright 브라우저 다운로드가 없어도 설치된 Chrome/Edge의 실행 경로를 `--browser "..."`에 전달할 수 있다. 계정·OAuth·유료 서비스 없이 진행한다.

## 검증/저작권

- 원본 사진·도면은 FHHH friends, studio COM 및 크레딧에 명시된 촬영자 등의 저작물이다. 개인 학술 비교용 내부 자료로 보관하고, 재배포·논문/발표 삽입 시 별도 허락 및 출처 조건을 확인한다.
- GitHub 저장소에는 **원본 이미지 바이너리를 푸시하지 않고** 스타일 토큰/출처 URL/분석/원본 sha256 등 최소 메타데이터만 저장한다. `originals/`, `captures/`, `contact_sheets/`는 `.gitignore`로 제외하는 것이 권장된다.
- 이미 승인된 1층 프로그램 18개는 유지한다. 출입구·피난·모델의 구조 요소는 사진 스타일을 흉내 내기 위해 변경하지 않는다.

### 완료 판정

`CAPTURE_DONE` = 원본 캡처·다운로드와 갤러리 개별 이미지 수 검증 완료.  
`STYLE_ANALYSIS_DONE` = 원본 도면을 사람이 검토하고 근거별 규칙 작성 완료.  
`STYLE_APPLIED` = 우리 1층의 SVG/PDF/PNG A/B 실제 출력과 전후 비교 및 QA 완료.  
현재: `CAPTURE_DONE`(원본 90/90, 스크린샷 증거는 한계 있음) 충족. `STYLE_ANALYSIS_DONE`(사람 검토)·`STYLE_APPLIED`는 미완료.
