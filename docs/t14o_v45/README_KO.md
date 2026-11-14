# C-T14O G-002 Cycles PBR 후보 패키지

이 패키지는 검증된 `model_world.npz`와 `model_objects.json`에서 정점·삼각형을 복원하여 Blender Cycles로 다시 렌더한 G-002 후보이다. 기존 JPG의 색보정이나 AI 배경 합성이 아니다.

## 실제 산출물

- Urban Daylight 4800×2700 PNG: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14O\output\C_T14O_run\final_v2\G002_A_Urban_Daylight\G002_daylight_CYCLES_PBR_SOURCE_MESH.png`
- Blue Hour 4800×2700 PNG: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14O\output\C_T14O_run\final_v2\G002_B_Blue_Hour\G002_bluehour_CYCLES_PBR_SOURCE_MESH.png`
- Urban Daylight Blender 장면: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14O\output\C_T14O_run\final_v2\G002_A_Urban_Daylight\G002_daylight_SOURCE_MESH_LOOKDEV.blend`
- Blue Hour Blender 장면: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14O\output\C_T14O_run\final_v2\G002_B_Blue_Hour\G002_bluehour_SOURCE_MESH_LOOKDEV.blend`
- A3 가로 검토 PDF: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14O\docs\t14o_v45\G002_Cycles_PBR_A3_Review_Candidate.pdf`
- 전체 검토 contact sheet: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14O\docs\t14o_v45\G002_A3_Review_Contact_Sheet.png`
- 원본·A·B 비교: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14O\docs\t14o_v45\render_previews\G002_source_vs_cycles_AB.png`

## 검증 상태

- 캐시 SHA256 2개 일치
- 119,486 정점, 237,093 삼각형, 391 객체 복원
- A/B의 메시, 카메라, 건축 bbox와 객체 분류 동등성 검사 통과
- 4800px를 396mm 폭에 배치할 때 307.88dpi
- 전체 회귀검사 360 passed, 10 skipped, 0 failed
- C-T14O 계약 검사 14 passed

현재 상태는 `CANDIDATE_PIXELS_VERIFIED__USER_ARCHITECTURAL_APPROVAL_PENDING`이다. 재질·조명·신규 시각화 카메라는 시각화 제안이며, 원 설계 재료 사양이나 기존 G-002 카메라의 복원이라고 주장하지 않는다. 사용자 승인 전에는 다른 도면으로 확대하지 않는다.

