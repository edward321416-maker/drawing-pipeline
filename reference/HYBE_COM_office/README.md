# reference/HYBE_COM_office — studio COM 'HYBE office' 페이지 수집 (보조 도면 자료)

- 출처: https://c-o-m.kr/hybe/office (사용자 승인 2026-11-04, 개인 학술 비교용)
- 실행: `reference/19A06_HYBE/scripts/capture_reference.py --url https://c-o-m.kr/hybe/office --output reference/HYBE_COM_office`, 이어서 `analyze_reference.py`
- 결과: 다운로드 49개 중 **프로젝트 이미지 43개**, 사이트 아이콘·로고 6개. 실패 0.
  - 평면도 1: `02_hybe_8-16f.jpg` (8~16F 사무층). **1F 평면은 이 페이지에 없다.**
  - 액소노 개념 스케치 4: `04_hybe_office-diagram_01~04.jpg` (OFFICE SYSTEM - Early Concept Sketch)
  - 천장 분해 다이어그램: `00_hybe_diagram_ceiling.jpg`
  - 나머지는 실내·디테일 사진
- 원본 이미지(`originals/`, `captures/`, `contact_sheets/`)와 수집 manifest 는 `.gitignore` 로 Git 에서 제외했다. 저장소에는 `manifests/project_assets.json`(URL·sha256·분류)만 둔다.
- 저작물은 studio COM·FHHH friends 및 촬영자에게 있다. 논문·발표 삽입 전 허락과 출처를 확인한다.
