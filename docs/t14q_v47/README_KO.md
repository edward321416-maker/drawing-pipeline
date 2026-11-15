# C-T14Q — G-002 위치 정합 주변 맥락 + 실사형 메인 투시도

상태: `PHOTOSHOP_FINALS_COMPLETE__HUMAN_ARCHITECTURAL_AND_VISUAL_APPROVAL_PENDING`. 사람의 건축·시각 승인 전에는 G-002를 도면집 정본에 반영하지 않으며 main 병합·FREEZE를 하지 않는다. 기준 PR #25(`b307d7e`), PR #26(`1079ad5`)은 수정하지 않았다.

## 파이프라인 (실제로 수행한 것)
1. **위치·카메라 확정** — 캐시 world = OSM 로컬 + (270.030, 32.811), 회전 0°. 캐시 맥락 정점 892/892이 OSM 건물 정점과 0.1 m 이내 일치. 카메라 37.56436°N 127.00912°E, 1F 기준 127.7 m, 방위 332°. (`tools/t14q/frames.py`, `tests/test_t14q_frames.py` 7 passed)
2. **Site Context Pack** — OSM 799동 건물·도로·보도·횡단·녹지(`site_context/context_pack.json`), 조사 보고서와 출처·라이선스 대장. 높이 115동만 OSM 태그, **684동은 가정값**.
3. **Blender 기준 렌더** — 검증 메시 165객체(32,040 정점) 변경 0, 실제 태양 위치(2026-10-17 15:30 / 18:12 KST 가정), Daylight·Blue Hour 4800×2700, A/B 장면 지문 동일. (`tools/t14q/site_context_scene.py`)
4. **ChatGPT 편집(Chrome 실제 업로드·다운로드)** — Daylight 1672×941, Blue Hour 1672×941 PNG 확보.
5. **Photoshop 2026(27.7.0) 실제 실행** — Blender 렌더 잠금 레이어 + ChatGPT(Preserve Details 확대) + 건축 형상 복원 + CC0 재질 마이크로텍스처 + 깊이 대기감 + 색조·비네트·렌즈 연화·그레인. 11레이어 PSD와 4800×2700 PNG. (`tools/t14q/photoshop_finish.jsx`)
6. **검수·기록** — 3단 비교, 1:1 확대, 정합 계측, 메모리 계측, 라이선스 재검증, A3 가로 PDF.

## 파일
| 구분 | 경로 |
|---|---|
| A3 가로 보고서 | `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14Q\docs\t14q_v47\G002_C-T14Q_Report_A3.pdf` |
| 최종 PNG (Daylight) | `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14Q\docs\t14q_v47\images\G002_A_Urban_Daylight_PHOTOSHOP_FINAL.png` |
| 최종 PNG (Blue Hour) | `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14Q\docs\t14q_v47\images\G002_B_Blue_Hour_PHOTOSHOP_FINAL.png` |
| 편집 가능 PSD 2종 (git 제외, 각 약 320 MB) | `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14Q\output\C_T14Q_run\final_q\G002_A_Urban_Daylight_PHOTOSHOP_FINAL.psd`, `...\G002_B_Blue_Hour_PHOTOSHOP_FINAL.psd` |
| Blender 4800 px 기준본·ID·Depth·.blend (git 제외) | `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14Q\output\C_T14Q_run\blender_base\` 및 `...\blender_base_v2\` |
| SHA256 대장 | `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14Q\docs\t14q_v47\SHA256_MANIFEST.json` |
| 검수·정합·메모리 기록 | `docs\t14q_v47\qa\`, `docs\t14q_v47\memory_audit\` |
| 출처·라이선스 | `docs\t14q_v47\site_context\` (`photo_licences.json`, `licence_reverification_2026-11-15.json`, `textures_manifest.json`, `context_sources.json`) |
| ChatGPT 프롬프트 | `docs\t14q_v47\G002_CHATGPT_SITE_CONTEXT_PROMPTS_KO.md` |

## 기록해야 할 사실과 한계
- ChatGPT 대화: Daylight `https://chatgpt.com/c/6af93c24-fc48-83e8-898a-c7010b02b6cd`, Blue Hour `https://chatgpt.com/c/6af9406c-7e54-83e8-b3b0-92f95b747e67`. 업로드 JPEG·다운로드 PNG의 SHA256은 `qa\`와 `images\`에 있다.
- ChatGPT 유래 내용의 실효 해상도는 1672 px급이다. 4800 px 파일은 확대와 Blender 구조층으로 만든 것이다.
- Blue Hour Photoshop 1차본은 저층 로비가 탁해져 폐기(`..._v1_SUPERSEDED`로 보존)했고 어두운 영역을 복원층에서 제외한 2차본을 채택했다.
- 최초 Blue Hour 4800×2700/96샘플 시도는 시스템 메모리 부족으로 중단되었다(기록 보존). 해상도별 계측 후 64샘플 Beauty만 안전 하한 위에서 완료했다(`memory_audit\`).
- 검수는 자동 계측과 작성자의 육안 1차이며 독립 사람 검수가 아니다. 항목별 점수·승인 없음.
- 참고 사진 14장은 시각 참고 전용이며 픽셀을 복사하지 않았다.

## 재현
```powershell
python tools/t14q/build_context_pack.py --out <dir>\context_pack.json
powershell -File tools/t14q/run_blender_monitored.ps1 -Variant bluehour -Width 4800 -Height 2700 -Samples 64 -OutDir <new empty dir> -Report <json> -MinFreeGB 3.5
python tools/t14q/prepare_photoshop_inputs.py --variant daylight ...   # 그 뒤 Photoshop COM으로 tools/t14q/photoshop_finish.jsx 실행
python tools/t14q/build_report_q.py --out <pdf>
```
