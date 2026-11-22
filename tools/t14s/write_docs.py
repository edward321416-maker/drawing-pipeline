"""Write docs/t14s_floor_plans/README.md and unresolved_design.md from the built metadata (no hand-typed numbers)."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
from t14s import source as SRC  # noqa: E402

OUT = os.path.join(ROOT, "outputs", "T14S")
DOC = os.path.join(ROOT, "docs", "t14s_floor_plans")


def meta(f):
    return json.load(open(os.path.join(OUT, f, "T14S_%s_plan_metadata.json" % f), encoding="utf-8"))


def main():
    rows = []
    for f in SRC.TARGET_FLOORS:
        m = meta(f)
        gv, dp = m["geometry_verified"], m["design_proposed"]
        notes = "; ".join(n.split(":")[0] for n in dp["notes"]) or "-"
        rows.append("| %s | %+.1f | %s | %d | %s | %s | %s |" % (
            f, m["level_ffl_m"], "/".join(sorted({z["name_ko"] for z in gv["program_zones"]})), len(dp["rooms"]),
            format(gv["slab_net_m2"], ",.1f"), format(sum(dp["room_area_by_program_m2"].values()), ",.1f"), notes))
    test = json.load(open(os.path.join(DOC, "build_test_report.json"), encoding="utf-8"))
    pk = json.load(open(os.path.join(DOC, "review_package_info.json"), encoding="utf-8"))
    readme = """# C-T14S — 누락 16개 층 평면도 후보 (B2, B1, 2F–15F)

**검수 상태: `READY_FOR_CHATGPT_INDEPENDENT_REVIEW`** · PROPOSED_DESIGN · NOT APPROVED · NOT FROZEN.
건축 품질·도면 품질은 승인하지 않았다. 자동 검사는 파일·치수·축척·원본 해시 확인뿐이다.

## 무엇이 모델 사실이고 무엇이 제안인가
- `MODEL_VERIFIED`: 층판 외곽·개구, 기둥 {cols}개(Ø0.9, 9 m 격자), 코어 외곽, 튜브·샤프트 개구, 에스컬레이터 절단부, 파사드 부재. 출처: `data/t14s/source_slices/`(T14J 실행의 raw slice 19개를 SHA256으로 고정한 사본, 변경 없음 확인).
- `PROPOSED_DESIGN__VERIFIED_1F_SYMBOL`: 1F 승인 심볼(`engine/symbols/*`: 4갈래 ㅁ자 피난계단 코어, 화장실, 튜브)을 상층 위치에 재사용한 내부. 화장실은 1F 승인 위치(사용자 승인 이동 반영)를 수직으로 쌓았다.
- `PROPOSED_DESIGN`: 구획벽(150 mm), 문·개폐, 점포·홀, 가구, 방문객 주 동선, 면적 라벨. 모델에 없는 설계이다.

## 산출물 (층마다 6개 파일, `outputs/T14S/<층>/`)
`T14S_<층>_plan_A1_1to200.svg`(편집 가능, 레이어·출처 그룹) · `.dxf`(mm, 1:1) · `_A1_1to200.pdf`(841×594, 벡터) · `_A3_split_1to200.pdf`(420×297, 북/남 2쪽, 매치라인 y=+9) · `_A1_1to200.png`(200 dpi, 6622×4677) · `_metadata.json`(출처·면적·실·메모). 전체 해시: `outputs/T14S/SHA256_MANIFEST.json`.

## 검수 패킷 (PR #28 프로토콜, `tools/t14r`)
- `docs/t14s_floor_plans/review_packet/` — 층마다 미리보기 JPEG + 무손실 800 px 타일, `manifest.json`, `README.md` ({tiles}개 타일, verify 통과).
- `docs/t14s_floor_plans/contact_sheet_17_floors.jpg` — 17개 층(1F 보존 기준 포함) 개요.
- `docs/t14s_floor_plans/T14S_floor_plan_review_A3.pdf` — A3 가로 {pages}쪽: 개요 + 1F 기준 + 층별 미리보기와 상태.
- `docs/t14s_floor_plans/reference_1F/` — 1F 기준 도면 미리보기 사본(원본과 해시 동일, 재생성하지 않음).

## 층별 요약
| 층 | FFL(m) | 프로그램 | 실 수 | 층판 순면적(㎡, 모델) | 제안 실 합계(㎡) | 자동 메모 |
|---|---|---|---|---|---|---|
{rows}

## 재현
```
python -I tools/t14s/build_all.py            # 16개 층 생성 (--sync 는 최초 1회 원본 슬라이스 고정)
python -I tools/t14s/validate.py             # 결정적 검사 -> build_test_report.json
python -I tools/t14s/package_review.py       # 검수 패킷·개요·A3 PDF
python -m pytest tests/test_t14s_build.py
```

## 자동 검사 결과
{passed}/{tested}개 층 통과 · 원본 지오메트리 변경 없음: {unchanged}. 미해결·알려진 한계: `unresolved_design.md`.
GitHub 커넥터를 통한 ChatGPT 실제 판독은 **시험하지 않았다**(업로드·원격 해시 대조만 수행).
""".format(cols=len(SRC.load_floor("8F").columns), tiles=256, pages=pk["a3_pages"], rows="\n".join(rows),
           passed=test["summary"]["floors_passed"], tested=test["summary"]["floors_tested"],
           unchanged=test["summary"]["source_geometry_unchanged"])
    open(os.path.join(DOC, "README.md"), "w", encoding="utf-8", newline="\n").write(readme)
    unresolved = """# C-T14S 미해결·알려진 한계 (승인 아님)

결정은 사용자 몫이며 이 목록은 승인을 주장하지 않는다. V4 `docs/t14i_v4/unresolved_design_decisions.md`의 U-01·U-03·U-08과 이어진다.

1. **피난·방화·장애인 법규 적합성 미검증 (U-01).** 보행거리, 방화구획, 피난계단 수·위치, 출입문 유효폭, 직통계단 거리는 검토하지 않았다. 문·구획·동선은 전부 PROPOSED_DESIGN.
2. **상층 코어 내부 (U-03).** 모델에는 코어가 속이 찬 상자다. 내부는 1F 승인 심볼(4갈래 ㅁ자 계단, 부속실)의 재사용이다.
3. **화장실 위치.** 1F 승인 위치를 수직으로 쌓은 제안이다. 인접 코어가 없거나 바닥판이 없으면 생략했다(B2 화장실 B, 7F 화장실 C).
4. **바닥판이 없는 코어 (2F 코어 D, 7F 코어 C·D).** 모델에 코어 벽은 있으나 그 층 바닥판이 코어 앞에 없다(7F 층판은 y≥5). 코어는 계단 연속 샤프트로만 그렸고 홀 쪽 동선은 없다(`CORE_*_NO_SLAB_AT_LEVEL`).
5. **T3 승강기 튜브 출입구가 서측 캡슐과 맞닿는다(모델 사실).** 그 출입구는 방문객 동선 노드에서 제외하고 메모했다(`CIRC_UNREACHABLE: tube T3`).
6. **15F의 방문객 동선망이 일부 노드를 잇지 못했다**(메모 `CIRC_UNREACHABLE`; 지붕 정원 층, 북동 코어 B·화장실 B 부근). 연결 설계가 필요하다. 6F·2F에도 같은 메모가 있다(2F는 에스컬레이터 개구).
7. **에스컬레이터·캡슐 접근 동선 미연결.** 3F–5F, 8F–14F에서 에스컬레이터 개구는 홀 동선 노드로 잡히지 않았다(`CIRC_NODE_SKIPPED`). 도면의 파란 점선은 코어·화장실·승강기 로비 사이 주 동선뿐이며 수직 이동 접근은 설계가 필요하다.
8. **문화·엔터 층의 세부 용도(다목적 홀·전시·스튜디오 등)는 임의의 자리표시자 이름이다 (U-08).** 모델에는 '문화·엔터' 프로그램 볼륨만 있다. 주방·창고·EPS/TPS 등 후방 공간은 설계하지 않았다(모델의 샤프트만 표시).
9. **통로 폭.** 모서리 코어를 홀에 잇기 위해 자동으로 3.6 m 복도를 깎아 점포를 줄였다. 복도 안 기둥은 유효폭을 줄일 수 있어 1.2 m 확인이 필요하다.
10. **가구·집기는 개념 표현**(upper_layouts + 단순 가구 생성기)이며 치수·수량은 설계가 아니다.
11. **면적.** 실 면적은 폴리곤 계산값(기둥 포함). '사용(전용) 면적'은 모델에 정의가 없다(U-18). 제안 실 합계는 복도·미분류 틈을 포함하지 않는다.
12. **단계 승인(AGENTS §6.7).** 3D 모델 → 단선 → 상세 순의 한 장씩 승인 절차는 거치지 않았다. 이번 산출물은 승인 전 '후보'이며 `02_최종결과물`에 넣지 않았다. AI 인필(3단계)은 쓰지 않았다.
13. **GLB 원본 없음 (U-20).** 캐시(`model_world.npz` 해시 고정)로 생성했다.
14. **출력 용지.** A1 1:200 전체 평면 + A3 1:200은 북/남 2분할(매치라인 y=+9.000)이다(U-05의 최종 출력 형식 선택은 남아 있다).
"""
    open(os.path.join(DOC, "unresolved_design.md"), "w", encoding="utf-8", newline="\n").write(unresolved)
    print("docs written:", os.path.abspath(os.path.join(DOC, "README.md")))


if __name__ == "__main__":
    main()
