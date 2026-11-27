# WP0 R10-C REF1 도면집 QA 보고서

생성 2026-11-27 16:06. 작업 트리 `<USER_HOME>\Desktop\중간마감\drawing-pipeline-R10C` 브랜치 `r10c-local-assembly` HEAD `a571e2b86e0fe3b1e3e622c0815fa476be4ad8f8` (R10-B1 기준 커밋). 작업은 로컬에서 수행했고, 이 검토 패키지는 사용자 승인에 따라 브랜치 `review/wp0-r10-c-reference-integrated`에 게시했습니다 (`PUBLICATION_STATUS.md`). 참고 도면집 원본 PDF는 게시하지 않았습니다.
**독립 검증 전에는 제출 가능을 주장하지 않습니다. 다음 단계는 독립 검토자의 전체 책 시각·기술 검토입니다.**

## 0. 게시 상태 (게시 시점에 갱신)
- 작성 시점(게시 전): 저장소 가시성이 PUBLIC이라 비공개 전용 게이트가 실패했고 원격 쓰기를 하지 않았습니다.
- 갱신: 사용자가 저장소 공개가 의도된 것임을 확인하고 업로드를 승인했습니다. 이 저장소에 대한 비공개 전용 게이트는 해제되었고, 푸시 URL을 복원했습니다. 저장소 가시성은 변경하지 않았고 `main`에 병합하지 않았습니다. 제3자 참고 도면집 PDF는 재배포 권한이 확인되지 않아 게시하지 않았습니다.
- 이 보고서의 로컬 경로와 제3자 이름은 게시본에서 가려졌습니다 (`evidence/redaction_log.json`).

## 1. 책 (REF1)
| 구분 | 파일 | 쪽수 | 크기 | SHA-256 |
|---|---|---|---|---|
| ARCH | WP0_Architectural_Drawing_Book_A2.pdf | 34 | 5.7 MB | f090cad4fef0320c492e71c0f67869e8d40aafbd7d39b5c74d045faeda90f978 |
| STRUCT | WP0_Structural_Drawing_Book_A3.pdf | 47 | 2.1 MB | 77cdd16472d7106d87baecd53b63523f5fdc97e47b155e3e8ac2c36054120ebd |
| APPX | WP0_Technical_Verification_Appendix.pdf | 18 | 14.6 MB | 324ad281e0db1f4cd1302699e31fb2c25f59fd149bed16652d8388ea9c0e3846 |
| COMBINED | WP0_Complete_Drawing_Book.pdf | 99 | 22.1 MB | 6545ab258e047c8c122adbccf48cec5c7fee284aad984880f0958bf93128db6c |

기준본(R10-C) 해시: 건축북 `f090cad4fef0320c492e71c0f67869e8d40aafbd7d39b5c74d045faeda90f978` (REF1 건축북과 동일: 예), 구조북 `a137fd0599b4e0446dfec30d5d400de609481fd0eff4ad8ec90bd7b55e1af8b8`, 부록 `79b19ef1493af731718afa7b48e6444de021efd400f3d97fedadd142a7a7e7b6`, 합본 `07928c801d107300a4b50ecd06e39b87b6c7a71f8e218a0500a520515267d48c`.

## 2. 페이지 단위 측정 (99쪽 전부 렌더·계측)
```json
{
 "pages": 99,
 "sizes": {
  "594x420": 48,
  "420x594": 4,
  "420x297": 47
 },
 "blank": 0,
 "with_replacement_char": 0,
 "pages_with_overlaps": 2,
 "pages_with_unresolved_refs": 0,
 "pages_with_raster": 5,
 "plan_scale_measured": 16,
 "issue_count": 2
}
```
지적 사항 (전부 공개):
- p.95 N-2F: 6 word-box overlaps
- p.96 N-7F: 6 word-box overlaps

- **정정**: 위 N-2F·N-7F의 '단어 상자 겹침 6건'은 R9 원본 쪽의 텍스트 층에 보이는 제목 밑으로 **가려진 중복 제목**(`2층 통합 보행 평면도`, `A2 SCALE 1:200`)이 남아 있기 때문입니다. 화면에는 한 개의 제목만 렌더됩니다(크롭 KD-02/KD-03). 시각 결함이 아니라 텍스트 추출 시 중복으로 보이는 문제입니다.
- 글리프 검사(새로 추가): Malgun Gothic 구간 15,342개 검사, 누락 글리프 쪽 0개. (새 쪽에서 `−`(U+2212)가 네모로 나오는 결함을 찾아 `-`로 바꾼 뒤 통과.)

## 3. 이번 개정에서 바뀐 것 / 바뀌지 않은 것
- 바뀜: 구조북 + FRONT-S02 설계개요(A3), 구조 목록 쪽 재생성, 기술 부록 + APX-06/07/08 및 쪽 순서 정리. 합본 99쪽.
- 바뀌지 않음: 건축북 34쪽 전체(바이트 동일), 구조북 기존 44쪽, 기존 부록 15쪽의 내용. **승인 설계는 수정하지 않았습니다.**
- 참고 도면집 반영 근거와 미반영 사유: 부록 APX-06/07/08, `evidence/reference_template_spec.json`.

## 4. 시험 재실행
- 형상 보존 T01-T18: {'PASS': 18, 'FAIL': 0, 'NOT_TESTED': 0} (`evidence/preservation_tests_REF1.txt`; R10-B1 커밋 `a571e2b86e0f…` 대비, 변경은 `tools/r10c/`에 한정).
- 치수 독립 검증 159/159 (A-201/301/302): 기준본 실행 결과이며 해당 3개 시트는 REF1 건축북에서 바이트 동일 (`evidence/dimension_qa_baseline.json`). 이번 개정에서 다시 실행하지는 않았습니다.
- 다른 층 평면의 치수 검증은 에이전트가 실행한 결과이며 오케스트레이터가 재실행하지 않았습니다.

## 5. 이번 점검에서 새로 확인한 한계 (이전 보고의 정정 포함)
1. **R9 틀 쪽 22장**: 건축 5(A-521, A-522, A-531~533), 구조 7(S-402~S-408), 부록 10장은 R9 원본의 틀·표제란을 그대로 쓰며 인쇄된 도면번호가 R9 번호(예 D-2F)입니다. 기준 도면집에서 만든 R10-C 틀로 옮겨지지 않았습니다. 이전 보고의 '모든 시트를 기준 틀로 옮김'은 R10 양식 쪽(77장)에만 해당합니다 (크롭 KD-12).
2. **미작성 도면 정정**: 기준본 등록부는 S-409~S-412를 '미포함'으로 적었으나 A-522·A-531~533으로 포함되어 있습니다. 반대로 A-511~A-516(튜브·캡슐·에스컬레이터 개구·6F 외피 상세) 등 원천이 있는 상세 도면은 작성되지 않았습니다 (`evidence/WP0_Missing_Drawings_Register_REF1.md`).
3. A-501 시트에는 HD-01의 176.07 mm 불일치가 문구로 인쇄되어 있지 않습니다 (176.07·HD-01·미해결·불일치 검색 결과 없음). 등록부에만 기록되어 있고 A-501은 재생성하지 않았습니다 (크롭 KD-01).
4. 장산 두 도면집은 zip 안의 원본이며 사용자가 적은 이름(`…-복사.pdf`)과 파일명이 다릅니다. 쪽수·용지는 일치.
5. 구조 부재 크기·보·기초는 원천이 없어 구조북은 PARTIAL입니다. 천장고(CH)는 전 실 '미확인'입니다.

## 6. 미해결 결함·결정 (요약)
- 코어 D 랜딩 176.07 mm(HD-01), E2 브리지 구조 증거 없음(HD-02): 미해결.
- HD-10 개정 가구 후보는 경로 11·13의 기존 가구 관통을 해소하지 못했고 경로 5는 1.26 m 병목입니다. 통행·피난·접근성 충족을 주장하지 않습니다.
- 표지 투시도는 AI 보정·승인 대기. A-100 신규 해치와 숲 계획은 사용자 검토 대기. 입면 방위 명칭(E/S), A-103 그리드 라벨 축 교환, 마스터-slice 면적 차이(1,894.1 vs 2,560.2 ㎡).
- 새 결정 D-REF-1~5 (APX-08).

## 7. 검토 패키지 (로컬 스테이징)
미리보기 99장(180 dpi JPEG, 최대 1.39 MB), 확대 크롭 54장, 대조표 9장, `evidence/page_map.csv`(쪽별 매핑). 위치: `<USER_HOME>\Desktop\2학기 논문\도면\WP0_Complete_Drawing_Book_RefIntegrated\review_package`.

## 8. 실행 기록 상태
`evidence/execution_log_REF1.json`에 단계별 기록. 토큰 사용량은 측정하지 못했고 추정치입니다 (이번 단계는 하위 에이전트를 쓰지 않았고 주 세션에서 약 0.4~0.8 백만 토큰 규모로 추정).

## 9. 독립 참고 핸드오프 기준 점검 (게시 직전 추가)
`references/academic_drawing_books/CHATGPT_REFERENCE_HANDOFF.md` (커밋 `8d5e5d1e21ca`)를 기준 명세로 사용해 `evidence/HANDOFF_CHECKLIST_REF1.md`, `evidence/scale_verification_REF1.json`, `evidence/handoff_crosscheck_references.json`, `evidence/route5_width_reconciliation.json`을 추가했습니다. 설계 개정은 하지 않았습니다.
