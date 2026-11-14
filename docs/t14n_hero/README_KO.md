# C-T14N G-002 히어로 렌더 검토 패키지

이 패키지는 실제 원본, A/B AI 원시 시안, 중앙 건물을 제거한 배경 플레이트, 원본 건물 기반 2.5D 보정본, 전후 비교, 확대 검수, 자동 지표와 A3 보고서를 포함한다.

## 판정

- AI 원시 A/B: 시각적 표현 참고용이지만 건축 형상이 달라 `REJECTED_NOT_FOR_BOOK`.
- 2.5D 보정 A/B: 원본 건물을 공간 정본으로 유지했으나 전체 타워 Blender 장면과 동일 카메라가 없어 재질·실내광 검증에 한계가 있다.
- 최종 상태: `VISUAL_QUALITY_NOT_APPROVED`, `HUMAN_REVIEW_REQUIRED`.
- G-103·G-106·G-111로 확장하지 않았다.

## 핵심 파일

- A 보정본: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14N\docs\t14n_hero\composites\G002_A_Urban_Daylight_geometry_corrected.png`
- B 보정본: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14N\docs\t14n_hero\composites\G002_B_Blue_Hour_geometry_corrected.png`
- A 비교: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14N\docs\t14n_hero\comparisons\G002_A_Urban_Daylight_source_raw_corrected.png`
- B 비교: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14N\docs\t14n_hero\comparisons\G002_B_Blue_Hour_source_raw_corrected.png`
- 검수 매니페스트: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14N\docs\t14n_hero\qa\G002_hero_manifest.json`
- 시각 품질 점검: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14N\docs\t14n_hero\qa\G002_visual_craft_review.json`
