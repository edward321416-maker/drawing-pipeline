# 알려진 문제와 위험 등록

| ID | 내용 | 분류 | 근거 | 조치 |
|---|---|---|---|---|
| KI-01 | 코어 D 계단 중간 랜딩 높이 불일치 최대 176.07 mm (승인 1F 마스터 대 연구 계단) | BLOCKED_USER_DECISION | `R10A_GEOMETRY.json` sheets.A-501 | **미해결, 숨기지 않음.** A-501은 R10-B에서 재생성하지 않았고 R10-A 파일은 바이트 변경 없음(T16). |
| KI-02 | E2 브리지의 실제 지지 경간·받침·정착·배근·재료·내력 | BLOCKED_STRUCTURAL_EVIDENCE | 기하 길이 17.0 m, 폭 2.4 m, 연구 데크 250 mm는 구조 체계가 아님 | S-401 연구도 유지. 부재 크기를 만들지 않음. |
| KI-03 | 전 26실 마감 천장고(CH) | UNVERIFIED | `ceiling_height = null`. 층고(레벨 차)는 모형 값이나 CH가 아님 | ‘CH 미확인’ 표기. |
| KI-04 | GLB의 맥락 매스(`X-CTXT_buildings`) 한 덩어리가 건물 외곽과 겹침 (도면 좌표 x −20.1…3.1, y 20.6…32.3, z 0…14.4 m) | UNVERIFIED (원본 모형 소견) | `SECTION` 절단에서 발견 | 단면에서 제외(1건 기록), **GLB 미수정**, 대지·맥락 확인 필요(HD-04). |
| KI-05 | 지하 외벽·흙막이·기초 | UNVERIFIED | 모형에 없음 | 작도하지 않음. 선큰 코트와 벽만 모형 근거로 표시. |
| KI-06 | 코어 A–D의 내부 계단·승강로 | UNVERIFIED | GLB 코어는 12면 상자(표현 외곽) | 단면은 외곽만. 평면 내부는 PR #30·R8 연구 형상. |
| KI-07 | 가구·설비 치수는 가정값 | FIT_OUT_DEVELOPMENT | `FITOUT_ASSUMPTIONS.md` | 법규·접근성 적합 주장 없음. |
| KI-08 | 문 폭 개별 치수 기입 | PASS_CONDITIONAL | 문 28건 중 24건을 열림 폭으로 기입(KI-17 참조) | 열림 폭 = 문짝 시작점–닫힌 문짝 끝점 거리. |
| KI-09 | T2·PL·FR 튜브의 용도명 | UNVERIFIED | FR은 PR #30 문구 ‘반입 접점’만 근거 | 모형 식별자만 표기. |
| KI-10 | A-501·S-401은 R10-A 그대로(미개발) | NOT_TESTED / carried | 범위 밖 | 후속 승인 후. |
| KI-11 | 실제 프린터 출력 시험 미실시 | NOT_TESTED | 화면 렌더·PDF 벡터 검사만 | — |
| KI-12 | R10-A 생성 스크립트와 R7·R8·R9 입력 폴더가 저장소 밖(로컬)에 있음 | PASS_CONDITIONAL | `REPRODUCTION.md` | 저장소만으로 재현 불가. 로컬 경로·해시를 기록. |
| KI-13 | 2F 외 층 평면·입면·나머지 단면 | FULL_FLOOR_PRODUCTION_PENDING_APPROVAL | 지시 범위 | 독립 검수 승인 전 진행 금지. |
| KI-14 | 홀 동선 검사에서 두 선이 유효폭 0.0 m로 읽힘(PR만 있을 때도 동일), 한 구간 최소 1.26 m | UNVERIFIED | `FITOUT_ASSUMPTIONS.md` | 원인 미확인. 개발 후보가 만든 문제는 아님. |
| KI-15 | 식음 홀 2-10 좌석 88석(15.2 ㎡/좌석): 지시한 이격을 지키면 배치 가능 영역이 358 ㎡뿐 | PARTIAL | 같은 문서 | 이격 기준 완화는 사용자 판단 사항(HD-07). |
| KI-16 | 장애인 큐비클(2-07, 2-19) 크기를 기존 칸막이로 읽을 수 없음 | UNVERIFIED | 같은 문서 | 합격 처리하지 않음. |
| KI-17 | 문 폭 28개 중 4개(실내문 900 mm)는 글자 충돌 방지로 평면에 기입하지 않음 | PARTIAL | `R10B_GEOMETRY.json` door_dims_skipped | 폭은 기록에 있음. |
