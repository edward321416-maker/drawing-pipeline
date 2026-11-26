# WP0 R10-B · 대표 도면 개발 (자체 검토 완료, 독립 검수 대기)

R10-A의 기존 승인 배치(옵션 A)를 보존한 채 2F 건축 평면도(A-201)와 전체 단면도 두 장(A-301 종단, A-302 횡단)을 개발했습니다.
상태: `R10B_REPRESENTATIVE_DRAWINGS_PRODUCED` · `R10B_SELF_REVIEW_COMPLETED` · `INDEPENDENT_REVIEW_PENDING` · `FULL_FLOOR_PRODUCTION_PENDING_APPROVAL`.
제출 가능 판정이 아닙니다. 병합·공개·최종 확정은 하지 않았습니다.

- [대표 도면 전체 PDF](pdf/WP0_R10B_Representative_A2.pdf) · [SHA-256 매니페스트](manifest.json)
- [출력 검수](validation/R10B_OUTPUT_QA.json) · [보존 검증](validation/R10B_PRESERVATION.json) · [교차 참조](validation/R10B_XREF.json) · [형상 기록](validation/R10B_GEOMETRY.json)
- [R10-A 대 R10-B](validation/R10A_VS_R10B.md) · [참고 도면 대조](validation/REFERENCE_COMPARISON.md) · [자체 검토](validation/SELF_REVIEW.md)
- [제도 표준](docs/DRAFTING_STANDARD.md) · [실별 보존](docs/ROOM_PRESERVATION_REPORT.md) · [가구 가정](docs/FITOUT_ASSUMPTIONS.md) · [문제 등록](docs/KNOWN_ISSUES.md) · [결정 등록](docs/HUMAN_DECISIONS.md) · [재현](docs/REPRODUCTION.md)

| 도면 | 축척 | PDF | SVG | 채팅 미리보기 | 300 DPI | 확대 | 타일 |
|---|---|---|---|---|---|---|---|
| A-201 2층 전체 건축 평면도 | 1:200 | [PDF](pdf/A-201.pdf) | [SVG](svg/A-201.svg) | [JPEG](previews/A-201.jpg) | [PNG](high_resolution/A-201.png) | [room_2-03](details/A-201_room_2-03.jpg) · [room_2-16](details/A-201_room_2-16.jpg) · [room_2-20](details/A-201_room_2-20.jpg) · [room_2-10](details/A-201_room_2-10.jpg) | [PNG·JPEG](tiles/A-201) |
| A-301 전체 건축 종단면도 A–A | 1:250 | [PDF](pdf/A-301.pdf) | [SVG](svg/A-301.svg) | [JPEG](previews/A-301.jpg) | [PNG](high_resolution/A-301.png) | [sunken_court](details/A-301_sunken_court.jpg) · [bridge_zone](details/A-301_bridge_zone.jpg) · [roof_garden](details/A-301_roof_garden.jpg) | [PNG·JPEG](tiles/A-301) |
| A-302 전체 건축 횡단면도 B–B | 1:250 | [PDF](pdf/A-302.pdf) | [SVG](svg/A-302.svg) | [JPEG](previews/A-302.jpg) | [PNG](high_resolution/A-302.png) | [west_capsule](details/A-302_west_capsule.jpg) · [east_capsule_roof](details/A-302_east_capsule_roof.jpg) · [east_facade](details/A-302_east_facade.jpg) | [PNG·JPEG](tiles/A-302) |

A-501(코어 D 상세)과 S-401(E2 브리지 구조 연구)은 이번에 재생성하지 않았고 R10-A 그대로입니다. 코어 D 랜딩 높이 불일치 176.07 mm와
E2 브리지의 구조 증거 부재는 해결되지 않았으며 도면에서 해결된 것처럼 그리지 않았습니다.

## 결과 한눈에
| 영역 | 상태 | 근거 |
|---|---|---|
| 원본 GLB·승인 1F 마스터·PR #30 실 경계·프로그램 보존 | PASS (17/17) | `R10B_PRESERVATION.json` |
| 단면 절단의 메시 교차 재현(R10-A 26건) | PASS | T14 |
| 가구·설비 후보 겹침·문 스윙·포함 검사 | PASS (위반 0건) | `FITOUT_ASSUMPTIONS.md` |
| 교차 참조(단면 표시 위치 포함) | PASS (8/8) | `R10B_XREF.json` |
| 출력(쪽 크기·벡터·글리프·글자 충돌·축척 막대) | PASS | `R10B_OUTPUT_QA.json` |
| 식음 홀의 이용 판독성 | PASS_CONDITIONAL (부분) | KI-15 |
| 천장고 | UNVERIFIED (전 26실 미확인) | KI-03 |
| 코어 D 랜딩 불일치 · E2 구조 증거 | BLOCKED_USER_DECISION · BLOCKED_STRUCTURAL_EVIDENCE | KI-01, KI-02 |
| 저장소만으로 재현 | PASS_CONDITIONAL | KI-12 |
| 실제 프린터 출력 | NOT_TESTED | KI-11 |
