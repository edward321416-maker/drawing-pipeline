# drawing-pipeline

대한건축학회 투고 논문용 다층 상업시설(54×54 m, 17층)의 **평면도 자동 생성 파이프라인**. 평면도를 손으로 그리지 않고 3D 모델에서 파생한다. 이 저장소는 사람(연구자), Claude Code, ChatGPT가 같은 자료를 읽고 이어서 작업하도록 만든 공유용 사본이다.

> ChatGPT에게: 먼저 `AGENTS.md`(`rules/AGENTS.md`와 같은 내용)와 이 README를 읽고, 이해한 내용을 5줄로 요약한 뒤 작업하라. 사용자 규칙이 아래 기본값보다 우선한다. 파일 경로를 말할 때는 이 저장소 안의 상대 경로를 써라.

## 지금 상태 (2026-11-03)
- 1층(대지 포함) A3 1:500 한 장, 상층 A3 1:100은 같은 축척으로 2×2 네 장 타일.
- 자동 검사(`tests/verify_pipeline.py`): 1층 19/19, 3층 34/34 통과.
- 최신 작업 보고서: `rules/.gemini_sync.md`. 미해결 과제도 거기에 있다.
- 현재 사용자 승인 전 단계다. 승인 없이 "최종 결과물"로 표시하지 않는다.

## 먼저 볼 파일
| 목적 | 파일 |
|---|---|
| 규칙(절대 원칙) | `rules/AGENTS.md`, `rules/GEMINI.md` |
| 최신 사양서(커튼월·가구·선 위계) | `docs/specs/2026-11-03_curtainwall_furniture_spec.md` |
| 무오류 생성 설계 | `docs/specs/2026-11-01-drawing-errorfree-generation-design.md` |
| 파이프라인 설명 | `docs/drawing_pipeline_README.md`, `docs/pipeline_discovery.md` |
| ChatGPT 인수 프롬프트 | `docs/chatgpt_handoff_prompt.md` |
| 결과물(이미지) | `sheets/1F_1to500/`, `sheets/3F_1to100/` |

## 코드
| 파일 | 역할 |
|---|---|
| `src/01_headless_slicer.py` | Blender 헤드리스로 바닥 위 1.5 m에서 절단, 절단 벡터·마스크 생성 |
| `src/02_topology_to_cad.py` | 위상 정리, 라벨 배치, SVG/DXF(AIA 레이어) |
| `src/architectural_plan_renderer.py` | **A3 정축척 렌더러**(가장 많이 수정되는 파일): 6단계 선 위계, 커튼월 이중선, 문 솔버, 기둥 제거, 번호·범례, 타일 모드 |
| `src/furniture_library.py` | 가구 심볼(시장 섬 부스, 카페 테이블, 안내 바, 플랜터 벤치, 캡슐 갤러리, 상층 가구) |
| `src/monograph_plan_renderer.py` | 모노그래프풍 렌더러(공통 캔버스) |
| `src/03_gemini_retoucher.py`, `src/04_hybrid_compositor.py` | AI 인필, A1 합성기(A3 잠금 미적용) |
| `src/modal_render.py` | Modal 클라우드에서 층별 Blender 렌더 |
| `tests/verify_pipeline.py` | 자동 검사 a~e |
| `engine/` | 1층 마스터 모델 엔진(데이터·검사·렌더). `.blend` 바이너리는 제외했고 `engine/model/m_1f_source.json`이 형상 원본이다 |

## 실행 (Windows, Python 3.11+, Blender 4.2)
```
python -I src/architectural_plan_renderer.py --out <출력폴더> --floor 1F --png-width 4096 --crops
python -I src/architectural_plan_renderer.py --out <출력폴더> --floor 3F --png-width 4096
python -I tests/verify_pipeline.py --out <출력폴더> --floors 1F
```
필요 패키지: shapely, ezdxf, svgwrite, cairosvg, Pillow, numpy, scipy. 렌더러는 `<출력폴더>\vector\floor_<층>_layout.json` 등 슬라이서 산출물을 입력으로 쓰므로, 처음부터 돌리려면 `run_drawing_pipeline.py`를 쓴다. 이 저장소에는 입력 모델(.blend, glb)이 없어 ChatGPT 환경에서 그대로 실행되지는 않는다. 코드 읽기·검토·수정안 작성용이다.

## 핵심 설계 규칙 요약
- 단일 원천: 모델에서 파생, 그림 코드에 숫자 좌표 금지, 면적은 폴리곤 계산값.
- 선 위계(A3 종이 mm): 0.45 #000 절단벽·기둥 / 0.18 문짝·칸막이 / 0.12 계단·램프·승강기 / 0.09 #4A4A4A 유리 / 0.08 #666 가구·스윙·샤프트 X / 0.05 #CCC 격자·점묘·식재.
- 가구는 `#FFFFFF` 불투명 채움이라 바닥 격자가 비치지 않는다.
- 도면 글자는 번호만, 이름은 범례. 텍스트는 선 위에 겹치지 않는다.
- 1층 1:500, 그 밖 1:100(A3 4장 타일), 도면 종이는 A3 420×297 mm.

## 미해결 (요약)
1. 상층(2F 이상)은 glb에 벽·문이 없다.
2. 04 합성기와 DXF가 새 위계·가구·커튼월을 아직 따르지 않는다.
3. 피난계단: 규칙 문서 ㅁ자 4갈래 vs 그래픽 지시 U자(현재 U자).
4. 3F 슬라이스에 `source` 플래그가 없어 코어 번호가 붙지 않는다.

## 협업 방법 (ChatGPT와 Claude Code)
- 브랜치 `main`은 사용자 승인본만. 작업은 `chatgpt/<주제>` 또는 `claude/<주제>` 브랜치에서 하고 PR로 올린다.
- 변경 후에는 `tests/verify_pipeline.py` 결과를 PR 본문에 적는다.
- 사용자 지적이 새로 나오면 `rules/AGENTS.md`와 `rules/GEMINI.md`에 규칙으로 추가하고 검사를 늘린다.
