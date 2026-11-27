# WP0 미작성·누락 도면 등록부 (R10-C REF1)

생성: 2026-11-27 16:06 (REF1 개정, 기준본 등록부를 정정·확장). 68개 색인 항목의 분류 결과입니다. 시트 수는 품질 지표로 쓰지 않았습니다.

## 1. 원천이 없어 그릴 수 없는 도면 (MISSING_SOURCE)

| 시트 | 제목 | 없는 입력 |
|---|---|---|
| A-502 | 코어 A 상세 평·단면도 | core A detail: core interior (stairs/shafts) is not modelled in the GLB; only the 6x7 m envelope is verified |
| A-503 | 코어 B 상세 평·단면도 | core B detail: same missing source |
| A-504 | 코어 C 상세 평·단면도 | core C detail: same missing source |
| A-517 | 지붕·상층 후퇴부 | roof/setback waterproofing and finish design does not exist |
| A-518 | 화물 승강기·하역 동선 | freight lift / loading design does not exist (FR is only a 'delivery interface' label) |
| A-519 | 선큰 계단·마당 연결 | ground / retaining condition at the sunken stair: unresolved detail, no design source |
| S-102 | 기초·지하 흙막이 평면 | foundation / retaining wall / excavation design is absent |
| S-301 | 구조 단면 (부재 치수) | member sizes, spans, loads and seismic data are absent (no structural design) |
| A-601 | 천장 평면도 (전형) | ceiling plan: ceiling heights, ceiling system and plenum zone exist nowhere in the project sources (HD-03) |
| A-904 | 마감·천장 일람 | finish and ceiling schedule: finishes and ceiling heights are not found anywhere |

## 2. 다른 번호로 이미 책에 포함된 항목 (기준본 등록부의 오기 정정)

기준본 등록부는 아래 항목을 '포함하지 못함'으로 적었으나 실제로는 포함되어 있습니다 (번호만 다름).

| 색인 번호 | 실제 위치 | 비고 |
|---|---|---|
| S-409 (R9 D-7F) | 건축북 A-522 | 건축 상세로 분류하여 번호 변경 |
| S-410 (R9 B-2F-D) | 건축북 A-531 | 〃 |
| S-411 (R9 B-7F-C) | 건축북 A-532 | 〃 |
| S-412 (R9 B-7F-D) | 건축북 A-533 | 〃 |
| A-001 표지·도면 목록 | 건축북 FRONT-01, FRONT-02, FRONT-IDX-01 | 표지·개요·목록 |
| A-901 검증 기록 | 기술 부록 APX-04 (치수·형상 보존 시험) | 일부 |
| A-906 미결 사항 등록부 | 기술 부록 APX-05a, APX-08 | 일부 |
| A-905 증거·해시·재현 기록 | manifest.json, QA 보고서, evidence/ | 도면이 아닌 문서로 제공 |

## 3. 원천은 있으나 이번 책에 아직 포함하지 못한 도면 (미작성) — 기준본 보고에서 빠져 있던 항목

| 시트 | 제목 | 사유 |
|---|---|---|
| A-511 | T1 나선 램프 확대 | GLB 절단 엔진으로 만들 수 있으나 이번 책에서 작성하지 않음 |
| A-512 | T2 빛 튜브와 층판 관통 | 〃 |
| A-513 | T3/T4 전망 승강기 튜브 | 〃 |
| A-514 | 캡슐-층판 접속 | A-302 상세 D1이 일부 대신함 (확대 상세는 별도 미작성) |
| A-515 | 에스컬레이터 개구 (8F-9F) | R9 랜딩 쪽(A-521/522)이 일부 대신함, 8F-9F 개구 상세는 미작성 |
| A-516 | 전형층 외피·층판 가장자리 (6F) | 형상만 가능, 재료는 모델에 없음. 미작성 |
| A-002 | 범례·증거 등급·선 두께·약어 | 독립 쪽 없음 (각 시트에 범례가 있음) |
| A-902 | 실·면적 일람 B2~15F | 독립 쪽 없음 (각 평면의 실 목록과 FRONT-02 면적표가 일부 대신함) |
| A-903 | 문 개구 일람 (폭·개폐 방향) | 독립 쪽 없음 (평면에 문 폭 치수만 있음) |

## 4. 주 책에서 제외한 중복·대체 표현 (원천 파일은 삭제하지 않음)

| 시트 | 제목 | 사유 |
|---|---|---|
| A-003 | 층 레벨·층고 일람 (B2~ROOF) | floor level / storey table is part of the design-overview floor-area schedule (same data, one representation) |
| A-004 | 방위·그리드·절단선·입면 키 플랜 | key plan content duplicated by the section/elevation marks on every plan and the key plans on A-301/A-302 |
| A-303 | 단면도 C-C (x=3.0, +X: T1 나선 램프·서측 캡슐·T3 승강기) | additional section beyond the required longitudinal/transverse pair; source kept (build_r10b.py cfg), not in the primary book |
| A-304 | 단면도 D-D (x=31.0, +X: T2 빛 튜브·T4 승강기·동측) | additional section beyond the required pair; source kept |
| A-305 | 단면도 E-E (x~41, +X: 코어 B·C·화물 승강기 FR) | additional section beyond the required pair; source kept |

## 5. 참고 도면집 (REF1: 누락 해소)

- `Jangsan_Architecture_A2.pdf`, `Jangsan_Structure_A3.pdf`: **입수·검증 완료**. 같은 이름의 낱개 PDF는 이 컴퓨터 어디에도 없었고(드라이브 전체 검색), 내용은 `<USER_HOME>\Documents\카카오톡 받은 파일\Jangsan_reference_archive.zip` 안의 `Jangsan_Architecture_A2.pdf`(15쪽)와 `Jangsan_Structure_A3.pdf`(6쪽)입니다. 파일명에 `-복사`가 없으므로 같은 자료인지 사용자 확인이 필요합니다. 쪽수·용지는 요청과 일치합니다.
- 기준본 등록부의 '장산 도면집 미확보' 서술은 이 개정으로 대체됩니다. 재열지원 두 도면집은 기준본과 같은 해시입니다.

## 6. REF1에서 새로 확인한 격차 (참고 도면집 4권과의 비교, APX-06·07 참조)

위치도(설계개요)·구조 부재 일람표/부재 기호·지반 해치와 재료 지시선·코어 A~C 상세·외벽 평입단 상세 1:70·평면의 실별 FL/SL 표기: 원천 자료가 없거나 평면 재생성이 필요하여 이번 개정에서 작성하지 않았습니다.
