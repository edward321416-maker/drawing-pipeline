# C-T14J 건축 졸업 도면집 Candidate V4.1

## 주요 산출물

- 졸업 도면집 PDF: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14J\docs\t14j_v41\Graduation_Drawing_Book_Candidate_V4_1.pdf`
- 전체 contact sheet: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14J\docs\t14j_v41\Graduation_Drawing_Book_Contact_Sheet.png`
- 개별 시트 PDF·SVG·PNG: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14J\docs\t14j_v41\sheets`
- 수정 전후 비교 6장: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14J\docs\t14j_v41\before_after`
- 전체 180dpi QA: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14J\docs\t14j_v41\qa\full_180dpi`
- 핵심 6쪽 300dpi QA: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14J\docs\t14j_v41\qa\key_300dpi`
- 검증 보고서: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14J\docs\t14j_v41\visual_qa_report.json`
- 테스트 보고서: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14J\docs\t14j_v41\tests_report.json`
- 통합 diff: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14J\docs\t14j_v41\source_changes.diff`
- 전체 해시: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14J\docs\t14j_v41\SHA256SUMS.txt`

## 편집 변경

- G-002는 장문 목차를 제거하고 위치도·배치도·건축개요·층별 프로그램/면적의 동일한 194×114mm 패널 네 개로 재구성했다. 패널 간격은 가로·세로 모두 8mm다.
- G-106은 P-201의 3F 평면을 주도면으로 확대하고 P-202의 13F를 보조 도면으로 배치했다.
- G-108은 E-201 북측 입면을 주도면, E-202 동측 입면을 보조 도면으로 구성했다.
- G-109는 S-303 B-B를 주단면, S-302 A-A를 보조 단면으로 구성했다.
- G-111은 D-401 나선 램프의 평면과 수직 관계를 확대하고 D-404를 보조 자료로 배치했다.
- G-112는 모델 형상과 제안된 가구·사용 장면의 범례를 분리했다.
- 재편집된 기술 도면은 모두 NTS이며 정확한 원본 시트 번호를 명시했다.

## 검증 결과

- 최종 PDF: 15쪽, A3 가로 420×297mm
- 전 페이지 180dpi: PASS
- G-002·106·108·109·111·112 300dpi: PASS
- 검색 가능한 글자 6pt 미만: 0건
- G-002 패널 좌표·크기·간격: PASS
- 전체 테스트: 299 passed, 10 skipped, 0 failed
- 기존 회귀: 274 passed, 신규 편집·변이 검사: 25 passed
- 기술 부록 49쪽: 재생성하지 않음, 기존 SHA256 `5ba6b3495717a39a9f3554a9dcb94058e968869d61c75dab6adf3aaa066cb15d`
- 모델 캐시 SHA256: `992e2ec51ec17dc494ed2f99ddb11298671449dd6661d92df3b3536a0049537b`

## 사실성 원칙

위치도에 검증되지 않은 지명·도로명·좌표를 추가하지 않았다. 면적 표는 프로그램 볼륨의 수평 투영 면적과 층판 순면적을 구분하며, 프로그램 볼륨 투영을 전용면적 또는 법정 연면적으로 표현하지 않는다. 원본 A-003, 기술 도면, 모델 캐시는 수정하지 않았다.
