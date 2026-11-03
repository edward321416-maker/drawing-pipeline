# 도면 파이프라인 (전체 건물 층별 평면도)

모델의 수평 단면(바닥 위 1.5 m)에서 층별 평면도를 파생한다. 그림 코드에 좌표를 쓰지 않는다(AGENTS.md §6.1). 탐색 결과와 한계는 `D:\Users\admin\Desktop\2학기 논문\docs\pipeline_discovery.md`.

## 실행

```
python run_drawing_pipeline.py --blend "D:\Users\admin\Desktop\5-2\설계스튜디오\중간발표\07_representation\render\out\GMC-ZZ-ZZ-M3-0701.glb" --modal --skip-ai
```

| 옵션 | 뜻 |
|---|---|
| `--blend` | 모델 파일. `.glb` 또는 `.blend` |
| `--cut-z` | 바닥 위 절단 높이(m). 기본 1.5(승인된 규칙) |
| `--modal` | 렌더를 Modal 컨테이너에서 층별 병렬로. 크레딧을 쓰고 로컬 CPU는 쓰지 않는다 |
| `--size` `--samples` | 렌더 해상도와 샘플. 기본 4096 px, 64 |
| `--skip-ai` | AI 인필을 건너뛰고 오프화이트 종이 바탕을 쓴다 |
| `--ai-mode export-drive` | AI 인필용 전달 패키지(AO 그림 + 프롬프트)를 만든다 |
| `--ai-mode import` | 돌려받은 텍스처를 검사한다 |
| `--floors 1F,2F` | 일부 층만 |
| `--skip-render` | 이미 있는 `raw_slices`를 재사용 |

산출물은 `D:\Users\admin\Desktop\2학기 논문\output\drawing_pipeline` 아래:

- `raw_slices\` — `camera_bounds.json`, `floors.json`, `floor_<층>_slice.json`, `floor_<층>_ao.png`, `floor_<층>_cutmask.png`
- `cad\floor_<층>.dxf` — AIA 레이어 DXF(치수 객체 포함)
- `vector\floor_<층>_vector.svg`, `floor_<층>_layout.json`
- `final_sheets\floor_<층>_sheet.pdf|.png|.svg` — A1 가로 합성 시트
- `qa_report.json` — 자동 검증 결과

## 단계

1. `src\01_headless_slicer.py` (Blender) — 이름 규칙으로 분류(없으면 빌드 거부), 층 높이를 층판 윗면에서 읽음, 건물 축에 맞춘 도면 좌표계 결정, 절단 선분·층판 투영·영역·에스컬레이터 방향 추출, 정사영 AO 렌더와 정렬 마스크
2. `src\02_topology_to_cad.py` — 폐곡선 복원, 3단 치수(1.2·2.0·2.8 m), 라벨 배치(겹침 방지), SVG·DXF
3. `src\03_gemini_retoucher.py` — AI 인필. 기본은 건너뜀. `export-drive`는 API 키 없이 Google Drive + Gemini 앱으로 처리하는 경로
4. `src\04_hybrid_compositor.py` — 재질 바탕 × AO × 벡터 선, 도곽·진북·그래픽 스케일·면적표
5. `tests\verify_pipeline.py` — 자동 검증(폐곡선, Y축·정렬, DXF, 글자 충돌, 합성 정렬)

## 알려진 한계

- 이 모델에는 벽·문·창·가구·방 경계가 없다. 도면에는 층판 윤곽, 기둥, 튜브, 코어 외곽, 에스컬레이터, 프로그램 영역만 나온다. 코어 내부 계단은 모델에 없어 해치로 표시한다.
- 정렬 마스크는 층판이 기둥·코어를 가로질러 일부 가려지므로(코어 D 등) 기둥·튜브 위주로 검증한다.
- Gemini API 호출(`--ai-mode api`)은 키가 없어 시험하지 못했다.
- 도면 승인 전에는 `도면\02_최종결과물`로 옮기지 않는다(AGENTS.md §4).

## 모노그래프 렌더러 (흑백 번호 + 범례 스타일)

```
python src\monograph_plan_renderer.py --out output\drawing_pipeline_1F_master --floor 1F [--with-dims] [--seed 7] [--png-width 4096]
python src\monograph_plan_renderer.py --out output\drawing_pipeline_1F_master --test-furniture
```

- 입력: 02 단계가 만든 `raw_slices\floor_<층>_slice.json`과 `vector\floor_<층>_layout.json`. 외부공간·선큰 계단은 모델의 태그 객체에서, 수목 위치는 모델의 고정 원천 데이터(`도면\00_엔진\model\m_site_source.json`, `grove_design.json`)에서 온다.
- 출력(`final_sheets\`): `monograph_<층>.svg|pdf|png`, `monograph_site_plan.png`, `monograph_<층>_check.json`(자체 점검).
- 시트는 A2 가로, 1:200. 평면 안 글자는 번호뿐이고 이름은 좌하단 범례에만 있다. 치수 체인은 기본 꺼짐(`--with-dims`).
- 가구·수목·점묘는 설명용 표현이다. 모델에 수목이 없는 방향의 수목 18그루는 표현용으로 흩어 놓은 것이며 설계 데이터가 아니다(시트 각주에 표기).
- 가구 생성기는 교실·사무·회의·화장실·침실·실험실·시장·하역 8종. 1층에는 시장 홀(좌판)과 하역·서비스(팔레트)만 적용되고, 나머지는 `--test-furniture` 시트로 시험한다.

## A3 정축척 렌더러 (대지 맥락 + 프로그램 기호)

```
python src\architectural_plan_renderer.py --out output\drawing_pipeline_1F_master --floor 1F            # 1층: 1:500 배치 포함
python src\architectural_plan_renderer.py --out output\drawing_pipeline --floor 3F --scale 200          # 상층: 1:200
```

- 용지는 A3 가로 420 × 297 mm 고정, 1 m = 1000/축척 mm. 자동 맞춤 없음. 1:500은 시트가 210 × 148.5 m. 54 × 54 m 건물은 A3에서 1:100이 불가능(540 mm 필요)하므로 상층은 1:200을 쓰고 시트에 명시한다(`--scale 100`은 경고 후 건물이 시트 밖으로 나간다).
- 1층 대지 맥락(대지경계선, 건축한계선, 도로, 보도, 이웃 건물 47채, 차선, 출입구, 지하철 출구, 선큰 계단)은 `1F_master.blend`의 태그 객체에서 `01_headless_slicer.py`가 slice JSON의 `context`로 뽑는다. 수목은 숲 마당·보도 위의 것만 남긴다.
- 시장 홀 둘레의 유리 커튼월(이중선 0.30 mm, 멀리언 1.8 m, 출입구 양개 문)은 모델의 영역 경계에서 파생한 표현이다. 모델에 유리벽 객체는 없다.
- 기호는 이름으로 정해진다: 승강기(이중 승강로·단일 승강로, 카 박스 + X + 개폐문), 샤프트(X + 배관 원), 나선 램프(방사 눈금 + 반시계 화살표), 빛 튜브, 캡슐(이중 벽·멀리언·라운지), 코어(챌판 300 mm·핸드레일·UP·절단선), 선큰(슬래브 가장자리·난간선·계단·하부 포장), 하역(트럭 베이·도크·경사 화살표·볼라드), 시장 홀(3.0 × 3.0 m 부스 + 통로 2.4 m).
- 가구는 기둥(+0.3 m)·튜브·코어·화장실·선큰·문 앞(1.8 m)·승강기 둘레를 뺀 자유 공간에만 놓이고, 마지막에 필터로 한 번 더 거른다. 번호 후광 반지름은 종이 1.8 mm.
- 출력: `final_sheets\plan_<층>_A3_1to<축척>.svg|pdf|png`, `..._check.json`(축척·충돌 자체 점검).

### A3 렌더러 v2 변경 (2026-11-03)

- 범례는 건축 프로그램 9개(시장 홀, 필로티 광장, 하역·서비스, 선큰 마당, 서측 캡슐, 나선 램프 튜브, 빛 튜브, 화장실, 코어)만. 승강기·샤프트에는 번호를 달지 않는다. 코어·화장실 번호는 r = 1.2 mm로 작게, 계단·UP·문 스윙·기물을 피해 놓는다.
- 문 객체(1/4 부채꼴)와 출입구 객체의 상자는 그리지 않는다. 문은 힌지·문짝·호로 다시 그리고 벽에 개구부를 뚫는다.
- 코어는 모델의 안쪽 칸막이로 나뉜 계단실에 U자형(계단참 + 평행한 2개 계단단, 챌판 300 mm는 진행 방향으로만, 30° 이중 절단선, UP)으로 그린다. 모델의 코어 계단은 4갈래 ㅁ자형(AGENTS.md §3)이므로 이 표현은 그래픽 지시를 따른 것이다.
- 시장 홀의 닫힌 경계(바깥 윤곽 + 필로티·하역과의 경계)에 이중선 커튼월(150 mm, 0.22 mm, 2 m마다 솔리드 사각 멀리언)과 양개 출입문을 둔다. 타일·점묘은 캡슐·튜브·코어·화장실·선큰 안에는 들어가지 않는다.
- 조경(서측 공원 산책로 4개·식재 섬·벤치, 남측 진입 광장 3 m 모듈 포장·테라스·횡단보도, 북·동측 보행로와 가로수, 북측 서비스 진입로)은 대지경계선·건물·출입구에서 계산한 설계 표현이다.

### A3 렌더러 v3 변경 (2026-11-03)

- **구조 컬링:** 코어·화장실·캡슐·튜브 외곽 + 1.8 m(`core_exclusion`)에 기둥 가장자리가 닿으면 그 점 기둥은 그리지 않는다(모델 34개 → 23개). 구조 격자선은 모델의 전체 기둥 위치로 긋되 코어·튜브 벽에서 0.3 m 떨어져 끝난다.
- **문 충돌 해결기(`solve_doors`):** ① 문설주가 수직 벽 면에서 250 mm 안이면 문설주를 밀고 문폭을 줄이며(최소 0.8 m) 빈틈은 벽으로 채운다, ② 힌지 좌·우 × 스윙 안·밖 4가지를 시험해 스윙 부채꼴(20 mm 안쪽 줄임)이 벽·다른 문·위생도기와 겹치는 면적이 가장 작은 것(동률이면 원래 방향)을 고른다, ③ 개구부 상자(문폭 × 벽두께 3배)를 벽·유리 커튼월·투영선(슬래브 점선)에서 뺀다. 스윙(+150 mm) 안의 위생도기는 그리지 않는다.
- **6단계 선 위계(종이 mm):** 1단계 절단벽·코어·기둥 0.45~0.50 #000000 / 2단계 커튼월·선큰 슬래브 가장자리 0.22 #1A1A1A / 3단계 문짝·칸막이 0.18 #222222 / 4단계 계단·램프·승강기 카·이웃 건물 윤곽 0.12 #444444 / 5단계 스윙 호·위생도기·좌판·가구·샤프트 X 0.08 #777777 / 6단계 타일·점묘·격자·식재 0.05~0.06 #B0B0B0~#C4C4C4. SVG 선폭 = 종이 mm × 축척/1000. DXF 레이어 선 두께도 같은 위계로 맞췄다.
- **점검 이미지:** `--crops`를 주면 `final_sheets\crop_core_restroom.png`, `crop_tube_capsule.png`(800×800 px)를 만든다.
