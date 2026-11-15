# C-T14R | GitHub에서 ChatGPT가 **실제로 열어볼 수 있는 이미지** 제출 규칙

이 저장소의 건축 렌더링·리터치·도면·보고서 작업에 적용. PR #27 G-002의 대용량 최종 PNG는 GitHub에 존재하지만, 현 연결에서 `fetch_file(encoding=base64)`이 **빈 이미지 데이터**를 반환하여 ChatGPT가 직접 확대 검수할 수 없었던 사례를 개선한다.

## 필수 산출물 (각 렌더/다이어그램/도면)

1. **원본 MASTER**: 기존 PNG/PSD/Blend 원본은 수정하지 않는다. 가능하면 GitHub로 원본도 저장하되, 저장소 용량/라이선스/개인정보를 준수한다. 320 MB PSD는 외부 원본 보관 + SHA 증빙으로 충분하며 GitHub에 강제로 넣지 않는다.
2. **전체 미리보기**: 품질 높은 JPEG, 예: 1600×900, 최대 **400 KiB**. 프레임 전체를 실제로 확인할 수 있어야 한다.
3. **무손실 원본 픽셀 타일**: 4800×2700 이미지의 실제 RGB 픽셀을 좌표별 PNG로 저장. **각 이미지 ≤400 KiB**. 용량이 넘으면 더 작게 자동 분할. 색감 변경/스케일링/AI 재해석 금지. 100% 비율로 확대 검수 가능해야 한다.
4. **`manifest.json`**: 원본 SHA256, 해상도, 타일 박스 좌표·파일 SHA, 원본 RGB 픽셀 해시, 프리뷰 SHA, 요약 이미지 SHA.
5. **`README.md`**: 브라우저·GitHub·ChatGPT 연결에서 바로 열 수 있는 미리보기와 주요 확대 타일 목록.
6. **시각 검수용 자료**: Blender 원본 / ChatGPT raw / Photoshop final의 대표 이미지, 파사드 수직 핀·진입 램프·옥상 개구부·튜브·코어·중정 확대 비교. 자동 검수와 독립 사람 검수를 분리한다.

## 로컬 실행 — 실제 T14Q 파일을 사용

저장소 루트에서, 기존 작업본을 읽기 전용 입력으로 사용한다. 실제 명령은 로컬 실행 환경에서 다음과 같이 수행한다.

```powershell
python -m tools.t14r.export_visual_review pack `
  --out "docs\t14r_visual_review\G002_C_T14Q_R1" `
  --asset "DAYLIGHT_FINAL=D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14Q\output\C_T14Q_run\final_q\G002_A_Urban_Daylight_PHOTOSHOP_FINAL.png" `
  --asset "BLUEHOUR_FINAL=D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14Q\output\C_T14Q_run\final_q\G002_B_Blue_Hour_PHOTOSHOP_FINAL.png"

python -m tools.t14r.export_visual_review verify `
  --packet "docs\t14r_visual_review\G002_C_T14Q_R1"
```

다음으로 반드시 **해당 경로의 파일들을 GitHub 작업 브랜치에 커밋하고 push**한다. 검증 없이 로컬 생성만 하는 것은 사용자 요청 미완료다.

```powershell
git status --short
git add -- "docs/t14r_visual_review/G002_C_T14Q_R1"
git diff --cached --stat
git commit -m "C-T14R: add GitHub-inspectable G002 visual review evidence"
git push origin HEAD
```

**절대 제약**: 기존 원본·PR #27·main·기술도면을 덮어쓰지 않는다. 타일 파일은 텍스트 전용 GitHub 연결로도 실제 읽히는지 실측해야 한다. PR에서 소량의 JPEG/PNG를 `fetch_file(encoding=base64)`로 반환받아 헤더/바이트/해시를 검사하고 사용자가 아닌 **ChatGPT가 실제 픽셀을 볼 수 있는 상태인지** 확인한다. 빈 데이터 또는 용량 차단 시 파일을 더 작은 타일로 쪼개 별도 커밋; 단, 원본 SHA 대장은 보존한다.

검수 담당자는 ① 전체 프리뷰 ② 중요 영역의 **좌표가 명시된 무손실 타일** ③ 원본 vs 최종 이미지 비교 ④ QA 매니페스트를 열어 확인해야 한다. 단순 `git push` 성공, PDF 생성, SHA 정상은 시각 승인과 무관하다.

## 성공/실패 상태

- `REVIEW_PACKET_LOCAL_ONLY`: 로컬 생성됨; **GitHub 접근 불가**
- `GITHUB_PUSHED_UNREADABLE`: PR에 있지만 연결에서 PNG 데이터가 반환되지 않음
- `GITHUB_CONNECTOR_READBACK_PASS`: 샘플링한 프리뷰/타일을 실제 다운로드·디코딩 및 SHA 검증함
- `INDEPENDENT_VISUAL_REVIEW_PENDING`: 픽셀 접근 가능하지만 아직 독립 시각 검수하지 않음
- `GEOMETRY_REWORK_REQUIRED` / `VISUAL_NOT_APPROVED`: 형상·표현 검수에서 반려
- `APPROVED_FOR_LAYOUT_NOT_DESIGN_APPROVED`: 별도 사람 검수 이후의 레이아웃 인수 승인, 설계 승인 아님

## 작업 보고·인수 필수값

PR URL, 최신 HEAD, 패킷 `README.md` GitHub 링크, 원본/타일 SHA256, 타일 개수, 원본 픽셀 재조립 검증 결과, GitHub 연결을 통한 **실제 이미지 열람 결과**, 승인/보류 상태, 실패 타일과 필요한 후속 작업. 진짜 파일을 확인하지 않았는데도 독립 시각 검수가 완료됐다고 보고하지 않는다.

사용자에게 제출할 기획/완료 보고는 **PDF도 항상 제공**한다. 단, PDF만 제출하고 이미지 직접 열람이 불가능하면 완성으로 처리하지 않는다.