# 재현 방법

상태: **PASS_CONDITIONAL** — 저장소만으로는 재현할 수 없습니다(R10-A 생성 코드와 R7·R8·R9 입력이 로컬 폴더에 있음).

필요 로컬 입력(경로·해시는 `validation/R10B_GEOMETRY.json` protected_sources 와 `R10A_GEOMETRY.json`):
- 원본 GLB: `D:\Users\admin\Desktop\5-2\설계스튜디오\중간발표\07_representation\render\out\GMC-ZZ-ZZ-M3-0701.glb`
- R10-A 작성 코드와 R7·R8·R9 입력: `D:\Users\admin\Desktop\2학기 논문\도면\01_과정\01_기획_구획_베이스\WP0_R10_A_대표도면\` 및 동일 부모의 `WP0_R7_20261125`, `WP0_R8_20261125`, `WP0_R9_기술도면집`
- 참고 PDF 3개: `D:\Temp\` (비교 이미지 생성에만 필요)
- Python 3.14: shapely, PyMuPDF, trimesh, DracoPy, matplotlib, numpy, Pillow

```
python -I -X utf8 tools/r10b/validate_cut_vs_r10a.py
python -I -X utf8 tools/r10b/select_section_b.py 1.5 ; python -I -X utf8 tools/r10b/select_section_b.py refine
python -I -X utf8 tools/r10b/build_r10b.py --out <빌드 폴더> --sheets A-201,A-301,A-302
python -I -X utf8 tools/r10b/package_r10b.py --build <빌드 폴더>
python -I -X utf8 tools/r10b/validate_preservation_r10b.py
python -I -X utf8 tools/r10b/validate_xref_r10b.py --build <빌드 폴더>
python -I -X utf8 tools/r10b/make_docs_r10b.py --build <빌드 폴더>
```
PDF의 날짜 문자열은 실행일이라 빌드마다 해시가 달라집니다. 기하·치수는 결정적입니다(무작위 없음).
