# 2단계 튜브 심볼 시트 검토

## 만든 것
- 시트: `D:\Users\admin\Desktop\2학기 논문\도면\01_과정\01_기획_구획_베이스\1F_튜브심볼_시트.png` (+ `...\1F_튜브심볼_시트.report.json`). 1:50, 200 dpi. 마스터 모델에는 조립하지 않았다.
- 심볼: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\symbols\tube.py` (T1 나선 램프, T2 빛 튜브, T3·T4 전망 승강기, 서측 캡슐)
- 그리기: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\render\tube_draw.py`, `...\render\tube_sheet.py`
- 시트 생성: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\master\tube_sheet.py` (`python master\tube_sheet.py`)
- 검사 R3: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\checks\tube_rules.py` (registry의 TUBE_CHECKS, run_tube_checks, CHECK_IDS에 R3)
- 장부 D-015: `...\ledger\ledger.yaml`, 회귀 시험 `test_d015_tube_column_shaft_and_lobby_rules` (R3 본문을 `return []`로 막으면 실패함을 확인)

## 구성 (AGENTS.md §3)
- T1: 바깥 림 Ø9.0 m + 안쪽 림 Ø3.9 m의 2중 동심원, 사이가 램프 통로(폭 2.4 m). 매끄러운 아르키메데스 나선 화살표 1개(300°), 방사형 해치 없음.
- T3·T4: 유리 원통 Ø8.0 m. 안에 독립 승강로 2대(외곽 2.6 m 정사각형, 벽 0.15, X 표시, 문 1.2 m), 앞(남쪽, -y)에 승강 로비 20.5 ㎡와 슬라이딩 출입구 2.4 m. 승강로는 유리 벽 안쪽에서 0.3 m 이상 떨어지도록 y를 계산해 놓음(로비 깊이 3.5 m).
- T2, 서측 캡슐(8.0 x 21.0 m): 유리 링만.
- 선: 유리·승강로 벽 cut_medium, 문·X선 projection_light, 나선 화살표 cut_medium(촉 cut_heavy), 기둥 cut_heavy 채움. 글자는 title/room/sub 위계만 사용.

## 파라미터와 출처 (`model\params.yaml`의 `tube:`, `engine_params.py`의 TubeParams)
- glass_t 0.15: build_master.py GLASS_T.
- 튜브 중심·반지름: m_1f_source.json (T1 (12,12) r4.5, T2 (40,12) r4.5, T3 (12,42) r4.0, T4 (40,42) r4.0, 월드 좌표). 캡슐은 wkt cap_w.
- min_ramp_w 1.2, min_door_w 1.2, lobby_min_depth 1.5: 통로 최소폭 1,200 mm, 휠체어 회전 1.5 m.
- **설계값(사용자 검토 대상)**: ramp_w 2.4, shaft_outer 2.6(24인승 가정), shaft_gap 0.3, shaft_to_glass 0.3, entry_w 2.4, car_door 1.2, 나선 300°·시작 -120°, 로비가 남쪽을 향함.

## 검사 결과
R3, T1~T4 위반 0건. 시험 176개 모두 통과(기존 165 + 신규 11).
튜브와 실제 기둥 최소 이격(`.report.json`): T1 1.76 m, T2 0.88 m, T3·T4와 캡슐도 겹침 없음. 튜브 윤곽은 건물 외곽(1층 판 바깥 윤곽) 안에 있음.

## 마스터와의 충돌
없음. 튜브 윤곽에서 0.5 m 안에 들어오는 기둥 외 객체(코어, 화장실, 샤프트, 보이드 등)도 없었다. 기둥은 어느 튜브와도 겹치지 않는다.

## 보아야 할 점
1. 나선 방향(반시계)과 램프 폭 2.4 m. 2. 승강로 크기(외곽 2.6 m)와 두 대 배치, 로비를 남쪽으로 둔 것. 3. 출입구를 한 곳으로만 둔 것(T3·T4). 4. 심볼은 원을 128각형으로 그려 마스터(48각형)와 미세하게 다르다(조립 때 통일 필요).