# 01 Reconciliation (documented issues)

**AUDIT_REGISTER_47_NOT_AVAILABLE: the 47-item register (CSV/JSON), the 10-page A3 PDF and the English brief were never added to GitHub and are not in any local folder (checked). Items below are the issues stated in the two independent-review comments on PR #30 (2026-11-23), numbered R-01.. by this audit. They are NOT a mapping of the 47 IDs; the 47-item reconciliation stays open until the files are supplied.**

| status | count |
|---|---|
| RESOLVED_VERIFIED | 3 |
| RESOLVED_UNVERIFIED | 2 |
| STILL_OPEN | 15 |
| BLOCKED_BY_DESIGN_DECISION | 8 |
| NOT_APPLICABLE | 1 |

| id | group | floors | status | issue | evidence | note |
|---|---|---|---|---|---|---|
| R-01 | P0 | B1, 2F, 4F-15F | `BLOCKED_BY_DESIGN_DECISION` | 에스컬레이터 승·하차 랜딩 25곳이 검증된 바닥판 위에 없음 (D-01) | `measurements/d01_escalator_landings.csv`<br>`docs/t14t_corrections/decision_packet.md#D-01` | 실측: 개구 안 20, 외곽 노치 밖 4(2F·7F), 코어 안 1(B1). 검증 형상은 변경하지 않았다. 대안 A/B/C와 실측치는 02_P0_ALTERNATIVES. |
| R-02 | P0 | 2F, 7F | `BLOCKED_BY_DESIGN_DECISION` | 바닥판 없는 코어: 2F 코어 D, 7F 코어 C·D (D-02) | `measurements/d02_cores_without_slab.csv`<br>`docs/t14t_corrections/decision_packet.md#D-02` | 실측: 3개 코어 모두 코어 면적 0 m²가 바닥판 위, 가장 가까운 검증 바닥판 17.0 m, 4면 전실 2.6 m 모두 바닥판 0 %. |
| R-03 | P0 | 2F-15F | `BLOCKED_BY_DESIGN_DECISION` | T3·T4 승강기 출입구 회전 15건 제안 (12F T4 -75°) (D-03) | `measurements/d03_lift_entry_rotations.csv`<br>`docs/t14t_corrections/decision_packet.md#D-03` | 실측: 회전 전 전실은 15건 모두 캡슐 튜브와 겹침. 12F T4는 -45°에서 바닥판 위 94.9 %라 -75°(100 %). 층별 문턱·유리문 개구·튜브 내부 충돌은 미측정. |
| R-04 | P0 | B1, 2F-5F | `BLOCKED_BY_DESIGN_DECISION` | T1 나선 램프(B1-5F) 승·하차 지점이 모델에 없음 (D-08) | `docs/t14t_audit_r1/evidence/circulation_audit.json`<br>`docs/t14t_corrections/decision_packet.md#D-08` | 동선 감사 도구가 not_assessed로 유지(5개 층). 모델·1F 심볼에 접점 정의 없음. |
| R-05 | P0 | B2-15F | `STILL_OPEN` | B2 등 승객용 승강기(EV1·EV2·PL)가 보행 그래프에서 빠짐 | `evidence/circulation_audit.json`<br>`.claude/skills/vertical-circulation-audit/SKILL.md` | PR #31 도구가 보고는 바로잡음(B2=CONNECTED_WITH_OPEN_ITEMS, EV1·EV2 미평가). 그래프·도면은 그대로. EV1·EV2의 방문객 이용 여부는 사용자 결정. |
| R-06 | P0 | 3F, B2 | `STILL_OPEN` | 기술 PASS 16/16과 circulation_complete 2/16이 완결성을 과장함 (3F는 T1 미모델) | `evidence/validator_rerun_report.json`<br>`evidence/circulation_audit.json` | 검증기 재실행: 16/16 기술 PASS, 완결 2층(B2·3F). 감사 도구: COMPLETE 0층. 검증기·build_test_report.json 자체는 수정하지 않았다. |
| R-07 | P0 | 전 층 | `STILL_OPEN` | 경로 중심선-기둥 0.55 m 허용은 연속 유효폭 1.2 m 검증이 아님 | `tools/t14s/validate_t14t.py (corridor_to_column_clearance)` | 연속 유효폭을 재는 검사가 없다. WP1. |
| R-08 | P0 | 8F | `BLOCKED_BY_DESIGN_DECISION` | 8F→9F 에스컬레이터 랜딩-바닥판 4.2 m 불일치 | `docs/t14t_corrections/decision_packet.md#D-01`<br>`measurements/d01_escalator_landings.csv` | 결정 패킷 표에서 보행면까지 4.2 m가 유일한 이상치(나머지 2.3-3.0 m). D-01에 포함. |
| R-09 | P1 | 12F | `BLOCKED_BY_DESIGN_DECISION` | 12F 중앙 보이드 약 342 m²의 가장자리와 제안 난간 | `docs/t14t_corrections/decision_packet.md#D-07` | 난간은 PROPOSED(붉은 점선). 규격은 D-07 결정 전. |
| R-10 | P1 | 10F | `STILL_OPEN` | 10F 약 1,660 m² F&B 홀에 주방·세척·창고·폐기물·FR 지원이 불충분 | `outputs/T14T/10F/T14T_10F_plan_metadata.json`<br>`02_P0_ALTERNATIVES (프로그램 실측)` | 메타데이터: 홀 1,660.1 m², 지원실 14개 합 146.6 m²(F&B 2,118.2 m²의 6.9 %). 주방 요건 판정은 하지 않음(법규 미검토). WP2. |
| R-11 | P1 | 11F | `STILL_OPEN` | 11F 로비 1,773.8 m² 대비 블랙박스 극장 약 83.2 m² | `outputs/T14T/11F/T14T_11F_plan_metadata.json` | 메타데이터와 일치(홀 1,773.8, 최대 실 83.2 m²). WP2. |
| R-12 | P1 | 12F | `STILL_OPEN` | 12F 전시 로비 대비 소형 갤러리 (48-59 m²) | `outputs/T14T/12F/T14T_12F_plan_metadata.json` | 메타데이터: 홀 1,585.8 m²(검토 코멘트의 1,558.5는 자리 바뀜으로 보임), 실 48.6/59.4/59.4 m². WP2. |
| R-13 | P1 | 13F | `STILL_OPEN` | 13F 공방 홀 1,779 m²에 실제 점유 프로그램이 희박 | `outputs/T14T/13F/T14T_13F_plan_metadata.json` | 메타데이터: 홀 1,779.2 m², 실 5개 합 301.3 m². WP2. |
| R-14 | P1 | 14F | `STILL_OPEN` | 14F 커뮤니티 라운지 약 1,933 m²에 프로그램 희박 | `outputs/T14T/14F/T14T_14F_plan_metadata.json` | 메타데이터: 홀 1,933.3 m², 실 3개 합 172.6 m². WP2. |
| R-15 | P1 | 6F, 15F | `STILL_OPEN` | 6F·15F 정원의 보행 접근·가장자리·운영 설명 | `outputs/T14T/6F/T14T_6F_plan_metadata.json`<br>`outputs/T14T/15F/T14T_15F_plan_metadata.json` | 정원 1,078.8 / 1,296.6 m². 정원 접근은 수직 연결(D-01)과 가장자리 규격(D-07)에 의존. WP2. |
| R-16 | P1 | 3F-9F | `STILL_OPEN` | 3F-9F 판매 점포·가구의 반복적 일반 배치 | `02_P0_ALTERNATIVES (반복 실측)` | 점포 면적 반복을 실측(아래 표). 프로그램 차별화는 미수행. WP2. |
| R-17 | P1 | 전 층 | `RESOLVED_UNVERIFIED` | 문 스윙·기둥·칸막이 충돌 | `evidence/validator_rerun_report.json` | 결정적 기준(문 스윙-기둥, 스윙 겹침, 칸막이-기둥, 스윙-칸막이 교차) 16/16 통과를 재실행으로 확인. 시각 재검토는 하지 않음. |
| R-18 | P1 | 전 층 | `STILL_OPEN` | 실·면적 일람표(도면에 인쇄되는 면적) | `evidence/pdf_consistency.json` | 실측: 지원실·화장실 161개 전부 면적 미인쇄(F4). 단위·홀·정원 면적 미인쇄가 12개 층에서 발견(P4 불합격). |
| R-19 | P2 | 전 층 | `STILL_OPEN` | 단면·평면 층 대응 (V4.2 단면 시트 대비) | `docs/t14i_v4/Technical_Drawing_Appendix_Candidate_V4_index.csv` | 이번 감사에서 대조하지 못함(NOT_RUN). WP4. |
| R-20 | P2 | 전 층 | `RESOLVED_UNVERIFIED` | 검증 구조와 제안 칸막이·가구의 구분 표기 | `evidence/validator_rerun_report.json (provenance_labels)` | 출처 레이어 검사 16/16 통과. 인쇄 도면의 가독성 시각 검토는 하지 않음. |
| R-21 | P2 | 전 층 | `BLOCKED_BY_DESIGN_DECISION` | PR #30의 16개 평면을 V4.2 65쪽 도면집에 통합 | `docs/t14k_v42/README.md` | 사용자 승인된 도면만 통합 가능. 승인 전에는 수행하지 않음. WP4. |
| R-22 | P1 | 전 층 | `BLOCKED_BY_DESIGN_DECISION` | D-05(FR 반입), D-06(후방 동선), D-09(문화·정원 개념) 미결 | `docs/t14t_corrections/decision_packet.md` | 사용자 결정 필요. |
| R-23 | P1 | 전 층 | `STILL_OPEN` | 실제 A1/A3 PDF 32개 페이지의 내용과 층 간 일관성이 검토되지 않음 | `evidence/pdf_consistency.json` | 결정적 검사를 수행: 쪽수·크기·벡터·층·축척·레벨 16/16, 층 간 레벨 스택·표제 문자열 일치. 면적 인쇄(P4)는 12개 층 불합격. 페이지 육안 검토는 NOT_RUN. |
| R-24 | P2 | 전 층 | `RESOLVED_VERIFIED` | 이미지 SHA256 재구성이 제작자 보고였음 | `evidence/guard_manifests.json`<br>`evidence/review_packet_local_check.json` | 재실행: 매니페스트 211개 파일 일치, 검수 패킷 16자산·256타일 픽셀 재구성 통과. 제작 세션(Claude Code)이 재실행한 것이며 검토자(ChatGPT)의 독립 재실행은 아님. |
| R-25 | P2 | 전 층 | `STILL_OPEN` | 원본 GLB 대비 고정 지오메트리 캐시 검증 | `evidence/guard_sources.json` | 고정 슬라이스의 복사본·원본 해시는 일치(19/19). GLB 대비 검증은 NOT_RUN. |
| R-26 | P2 | 전 층 | `RESOLVED_VERIFIED` | 인쇄 물리 축척 측정 | `evidence/validator_rerun_report.json (physical_scale_1to200)` | 검증기 재실행: 기둥 원 4.5 mm, 기둥열 폭 264 mm가 16/16 층에서 통과(A1 벡터 PDF). |
| R-27 | P2 | 전 층 | `STILL_OPEN` | 피난·방화·장애인 접근 법규 적합성 | - | 검토하지 않았고 승인도 아님(범위 밖). 사용자가 법규 검토를 지시하면 별도 작업. |
| R-28 | P2 | 2F, 7F, 11F, 14F | `RESOLVED_VERIFIED` | 도면 안에 내부 식별자(A-VERT-ELEV_car_* 등) 노출 | `evidence/pdf_consistency.json (P5)`<br>`evidence/validator_rerun_report.json` | A1·A3 PDF 텍스트 16/16, SVG·DXF 검사 16/16에서 식별자 없음. |
| R-29 | P2 | - | `NOT_APPLICABLE` | C-T14U와의 중복 방지 | `00_STATE_AND_INTEGRITY` | C-T14U 구현은 GitHub(PR·브랜치·커밋)와 로컬(워크트리·폴더) 어디에도 없었다. 대조할 대상이 없어 중복 여부를 판정하지 못했다. 위치를 알려 주면 WP2 착수 전에 대조한다. |
