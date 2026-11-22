# C-T14T — PR #29 평면도 정정 (16개 층)

**상태: `C_T14T_READY_FOR_CHATGPT_INDEPENDENT_REVIEW`** · PROPOSED_DESIGN · NOT APPROVED · NOT FROZEN.
건축·도면 품질은 승인하지 않았다. 자동 검사는 파일·치수·축척·원본 해시·경로 기하·출처 표기만 확인한다.

기준: PR #29, 커밋 `f2ba1d9881f222df91e797a0b2c375d32689a4c2` (`outputs/T14S/`는 그대로 보존, 정정 전 기준). 이 브랜치는 그 위에 쌓였다.
`main`, PR #28·#29, 1F 원본, 고정된 원본 슬라이스(`data/t14s/source_slices/`)는 바꾸지 않았다.

## 무엇을 정정했나 (전체 재생성 아님: 같은 생성기에 정정 로직을 얹고 16개 층의 영향받은 부분만 다시 그림)
- **P0 동선**: 층마다 기하 보행 그래프를 만든다(`src/t14s/walknet.py`, `src/t14s/planner.py`). 노드 = 코어 문, 화장실, 승강기 로비, 에스컬레이터 승·하차 랜딩(모델의 에스컬레이터 **축**에서 계산), FR 반입 접점, 점포 문 앞. 경로는 벽 이격 0.35 m, 기둥 면에서 0.62 m(통로 1.2 m 확보), 문 개폐 반경·개구·코어를 피해 래스터 위에서 계산한다. 연결 불가는 연결한 척하지 않고 미결로 기록한다.
- **P1 표기**: 바닥판 없음·개구부 = 하부 개방 해칭, 자유 개구부 제안 난간(미검증), 개방부를 관통하는 기둥(점선 링), 투영 에스컬레이터 축(보라색), 출입 불가 코어, `A-VERT-ELEV_car_*` 등 내부 식별자는 도면에서 제거하고 메타데이터에만 둠.
- **P2 프로그램**: 점포를 판매·객석·문화 주 공간과 지원(BOH) 실로 분리(창고·세척·주방), 서비스 문 → FR 반입 접점 서비스 경로, 11F–14F 문화 운영 개념(공연·전시·공방·교육), 정원(6F·15F) 산책로·식재·벤치·그늘.

## 해결 불가(검증 지오메트리를 바꿔야 함) → 결정 패킷
`decision_packet.md` (D-01 에스컬레이터 랜딩이 개구·코어 안, D-02 바닥판 없는 코어, D-03 승강기 출입구 회전, D-05 FR 접점, D-06 후방 동선, D-07 난간, D-08 T1 램프 출입, D-09 문화·정원 개념). 검증 지오메트리는 고치지 않았다.

## 산출물
- `outputs/T14T/<층>/`: `T14T_<층>_plan_A1_1to200.{svg,pdf,png}`, `T14T_<층>_plan_A3_split_1to200.pdf`, `T14T_<층>_plan.dxf`, `T14T_<층>_plan_metadata.json`; 해시 `outputs/T14T/SHA256_MANIFEST.json`.
- `review_packet/`: 층별 미리보기 JPEG + 무손실 800 px 타일(PR #28/T14R 프로토콜), `manifest.json`.
- `before_after/<층>_before_after.jpg`: 정정 전(PR #29)/후 + 정정 사유.
- `contact_sheet_17_floors_T14T.jpg` (1F 보존 기준 포함), `T14T_correction_review_A3.pdf` (한글 A3 가로).
- `build_test_report.json`: 결정적 검사 결과(미결 동선 포함).

## 재현
```
python -I tools/t14s/build_all.py            # 16개 층 -> outputs/T14T
python -I tools/t14s/validate_t14t.py        # 결정적 검사 -> build_test_report.json
python -I tools/t14s/package_t14t.py         # 검수 패킷, 전/후, 개요, A3 PDF, 결정 패킷
python -m pytest tests/test_t14t_build.py tests/test_t14s_build.py
```
`tools/t14s/build_all.py`는 이제 T14T 출력을 만든다. T14S 산출물은 정정 전 기준으로 고정되어 있다.

## 하지 않은 것
독립 건축·시각 검수, 법규(피난·방화·장애인) 검토, 층별 단계 승인(AGENTS §6.7), `02_최종결과물` 반영. ChatGPT GitHub 커넥터 판독은 시험하지 않았다.
