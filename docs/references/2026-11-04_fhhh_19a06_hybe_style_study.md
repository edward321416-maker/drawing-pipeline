# FHHH Friends HYBE (19A06) 레퍼런스 수집 및 1F 스타일 적용

- 작성일: 2026-11-04
- 상태: **REFERENCE_CAPTURE_PENDING / STYLE_SPEC_PROVISIONAL**
- 원본 프로젝트: https://fhhhfriends.com/19a06
- 공동설계사 시각 참고: https://c-o-m.kr/hybe/office
- 추가 프로젝트 설명: https://www.archdaily.com/1016294/hybe-headquarters-office-com-plus-fhhh-friends

## 원본 수집 상태

사용자가 요청한 원본 19A06의 **모든 이미지와 도면 다운로드는 이 실행 환경에서 완료되지 않았다.** 외부 이미지 호스트에 대한 실제 파일 다운로드 및 로컬 Chromium 브라우저의 URL 탐색이 차단되어 있기 때문이다. 원본 갤러리의 전체 자산 개수도 확인되지 않았다.

사용자에게 별도의 `reference/19A06_HYBE` ZIP 아티팩트를 제공한다. 이 패키지에는 다음이 포함된다.

- `scripts/capture_reference.py`: 공개 페이지 스크롤·갤러리 캡처, HTML/DOM/이미지 응답 URL 수집, 원본 미디어 저장
- `scripts/analyze_reference.py`: SHA256·이미지 특성 기반 임시 분류·컨택트시트·HTML 갤러리
- `analysis/STYLE_AUDIT.md`: 출처/확인 사실 구분, 1F 스타일 적용 초안
- `analysis/style_tokens.proposed.json`: 1F A3 1:500 제도 레이어 제안값. FHHH 원본 선폭 추출값이 아님
- `analysis/CLAUDE_C_T13B_STYLE_APPLICATION.md`: Claude Code 실행 지시서
- `our_baseline/1F_Program_Concept_V2_B.png`: 사용자 제공 이전 도면
- `tests/test_reference_utils.py`: 로컬 오프라인 테스트 6/6 PASS. **사이트 원본 수집 성공 테스트는 아님**

사용자 PC의 도면 저장소 `D:\Users\admin\Desktop\drawing-pipeline-repo`에서 ZIP을 압축 해제한 다음 아래 명령을 실행한다.

```powershell
Set-Location -LiteralPath 'D:\Users\admin\Desktop\drawing-pipeline-repo'
python reference\19A06_HYBE\scripts\capture_reference.py --url 'https://fhhhfriends.com/19a06' --output 'reference\19A06_HYBE'
python reference\19A06_HYBE\scripts\analyze_reference.py --root 'reference\19A06_HYBE'
```

실제 완료는 `manifests/capture_manifest.json`의 `downloaded_unique`, `download_failed`, 갤러리 페이지 수 및 스크롤 캡처를 직접 교차검증해야 선언한다. 미수집 상태를 완료로 위장하지 않는다. 공개 원본 이미지는 개인 연구용으로 수집하고, 저작권/촬영자 출처를 유지한다. 원본 바이너리는 GitHub PR에 배포하지 않는다.

## 출처 근거와 1F 적용 규칙

1. FHHH의 19A06은 HYBE 프로젝트이고 공동 설계자는 FHHH friends + studio COM이다.
2. studio COM의 공개 HYBE 8–16층 평면은 코어·기둥이 흑백 대비로 강조되고 사무 가구가 정렬된 구조를 보여준다. 이것은 원본 19A06 페이지 전체 이미지를 직접 검토한 결과가 아니라 **공동 설계사의 보조 도면 관찰**이다.
3. ArchDaily 프로젝트 설명에는 500×500mm 가구 모듈을 기반으로 한 공간 유연성이 기록된다. **우리 상업시설의 가구 정렬에 선택적으로 참고**할 뿐 기존 프로그램과 공간 형상을 복제하지 않는다.
4. 우리 1층 적용 제안(종이 mm): 구조 절단 0.45, 코어/주요 문 0.18~0.25, 유리·프로그램 0.12, 가구 외곽/내부 0.10/0.07, 조경 0.05~0.09, 도시 맥락 0.04~0.05. **FHHH 공식 수치가 아닌 권장 스타일 토큰**이다.
5. 서측 산책로·조경의 의도적 진동선, 폴리라인 꺾임, 가구 중복선을 구분하여 수정. 구조와 실제 출입문/피난을 글로벌 simplify 처리해 옮기지 않는다.
6. 기존 승인된 시장 M01–M06, 필로티 P01–P04, 서비스 S01–S04, 캡슐 C01–C04는 보존하고, 실제 모델 기하/기둥34/코어/튜브/화장실을 변경하지 않는다.
7. 스타일 A(강한 구조 포셰·단정한 가구), 스타일 B(조경 노이즈 최소화·프로그램 가구 강조)를 실제 3D 원천의 **동일한 geometry**로 출력한다.

## Claude 실행 완료 게이트

- 19A06 실제 원본 이미지의 목록/다운로드 해시/성공·실패 수 및 연락판
- 도면·단면·다이어그램·사진을 **실제로 시각 검토**하고, 이미지 ID가 연결된 분석표
- 1층 A3 가로 1:500 SVG/PDF/PNG 300dpi **실제 A/B 도면**
- 기존 V2-B와 고정 5개 확대 크롭 Before/After
- 구조·기둥34·프로그램18·미확정 출입구 상태·동일 geometry hash 회귀 검사
- 수정 소스 unified diff + 실제 단위/렌더 QA + 증거
- 사용자 승인 전 `1F_FINAL_FROZEN=false`, Draft PR 미병합

**원본 이미지 수집 및 도면 구현은 현재 이 문서에 의해 자동 실행된 것이 아니다.**
