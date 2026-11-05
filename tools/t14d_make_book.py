"""C-T14D 6단계: 표지·목차·층 정보표·미확정 목록을 만들고 모든 시트를 하나의 벡터 PDF(Drawing_Set_Candidate_V1.pdf)로 조립한다.

    python -I tools/t14d_make_book.py --run <도면집 후보 폴더> --glb <전층.glb> --head <git HEAD>

모든 숫자·표기는 레지스트리·감사 증거에서 읽는다. 평면이 없는 층은 '평면 미발행'으로 표기한다(합치지 않는다).
"""
import argparse
import csv
import datetime
import hashlib
import json
import math
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)
import fitz  # noqa: E402
from t14d_sheet import Sheet  # noqa: E402


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def jl(p):
    return json.load(open(p, encoding="utf-8"))


def table(sh, x, y, widths, header, rows, row_h=6.2, pt=6.5, head_pt=6.8):
    x1 = x + sum(widths)
    sh.path([[(x, y), (x1, y), (x1, y + row_h), (x, y + row_h)]], fill="#eee", stroke="#222", w=0.2)
    cx = x
    for w, h in zip(widths, header):
        sh.text(cx + 1.5, y + row_h * 0.7, h, head_pt, "bold", "#111")
        cx += w
    for i, r in enumerate(rows):
        yy = y + row_h * (i + 1)
        sh.line(x, yy + row_h, x1, yy + row_h, 0.1, "#999")
        cx = x
        for w, c in zip(widths, r):
            sh.text(cx + 1.5, yy + row_h * 0.7, c, pt, "normal", "#222")
            cx += w
    return y + row_h * (len(rows) + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--glb", required=True)
    ap.add_argument("--head", required=True)
    a = ap.parse_args()
    run = os.path.abspath(a.run)
    now = datetime.date.today().isoformat()
    ev = jl(os.path.join(run, "00_index", "floor_equivalence_evidence.json"))
    cov = jl(os.path.join(run, "00_index", "floor_coverage_audit.json"))
    plans = jl(os.path.join(run, "01_plans", "plan_registry.json"))["plans"]
    elev = jl(os.path.join(run, "02_elevations", "elevation_registry.json"))
    secr = jl(os.path.join(run, "03_sections", "section_line_registry.json"))
    det = jl(os.path.join(run, "04_details", "detail_registry.json"))["details"]
    mo = jl(os.path.join(run, "model_cache", "model_objects.json"))
    fr = elev["frame"]
    floors = ev["floor_z_m"]
    ff = ev["floor_to_floor_m"]
    ffl0 = floors["1F"]
    roof_z = max(o["zmax"] for o in mo["objects"] if o["kind"] == "roof")
    matrix = {r["floor"]: r for r in csv.DictReader(open(os.path.join(run, "00_index", "floor_typology_matrix.csv"), encoding="utf-8-sig"))}

    # ── 시트 목록(순서 = 도면집 페이지 순서) ─────────────────────────────────────────────────
    site_pdf = os.path.join(run, "01_plans", "A-003_site_plan_1F_1to400.pdf")
    shutil.copy(os.path.join(run, "reference_1F", "1F_CleanLine_FIXED_user_supplied.pdf"), site_pdf)
    listing = [("A-000", "표지", "—", "DOCUMENT", None), ("A-001", "도면 목록·시트 상태표", "—", "DOCUMENT", None), ("A-002", "층고·층별 프로그램·범례·방위", "—", "DOCUMENT + MODEL_DATA", None),
               ("A-003", "배치도 / 1층 계획 (사용자 제공 1F_CleanLine_FIXED)", "1:400", "USER_SUPPLIED · 1층 프로그램 T13B-B 후보(승인 전)", site_pdf)]
    for p in plans:
        t = "%d층 기준층 평면 (적용: %s)" % (int(p["floor"][:-1]), "·".join(p["applies_to"]))
        listing.append((p["sheet"], t, "1:200", "MODEL_GEOMETRY · Level S (벽·문 미검증, 가구 PROPOSED_ONLY)", p["files"]["pdf"]["path"]))
    for e in elev["elevations"]:
        listing.append((e["sheet"], "%s측 입면도" % {"N": "북", "E": "동", "S": "남", "W": "서"}[e["name"]], e["scale"], "MODEL_GEOMETRY", e["files"]["pdf"]["path"]))
    listing.append(("S-301", "단면 키플랜", "1:400", "MODEL_GEOMETRY", secr["section_locator"]["files"]["pdf"]["path"]))
    for s in secr["sections"]:
        listing.append((s["sheet"], "단면도 %s" % s["name"], s["scale"], "MODEL_GEOMETRY · 실제 메시 절단", s["files"]["pdf"]["path"]))
    for d in det:
        listing.append((d["sheet"], d["title"], d["scale"], d["grade"].split(" · ")[0], d["files"]["pdf"]["path"]))
    listing.append(("A-900", "미확정 설계·도면 단계 표기", "—", "DOCUMENT", None))

    # ── 층 → 평면 시트 매핑 ──────────────────────────────────────────────────────────────────
    plan_of = {"1F": "A-003 (1:400 배치+1층)"}
    for p in plans:
        for m in p["applies_to"]:
            plan_of[m] = p["sheet"] if m == p["floor"] else "%s (차이 표기)" % p["sheet"]
    published = [f for f in floors if f in plan_of]

    # ── A-002 층 정보 ────────────────────────────────────────────────────────────────────────
    s2 = Sheet("A-002", "층고·층별 프로그램·범례·방위", None, "DOCUMENT + MODEL_DATA", subtitle="모든 높이는 GLB 층판 윗면(A-FLOR_s7_*)에서 읽음 · 기준 GL = 1F FFL ±0.000",
               extra_lines=["평면 도면이 없는 층은 '평면 미발행'(사용자 지시: 기준층만 발행). 기준층이 아닌 층을 다른 층에 합쳐 표기하지 않음",
                            "좌표틀: 1층 마스터와 동일, 건물축 theta=%.3f°, 진북 = 도면 위쪽에서 시계 방향 %.1f°, 원점 = 도면틀 건물 최소점" % (fr["theta_deg"], fr["north_deg"])])
    sh = s2
    sh.text(14, 16, "층별 정보", 9, "bold", "#111")
    rows = []
    order = ["B2", "B1"] + ["%dF" % i for i in range(1, 16)]
    for f in order:
        h = ff.get(f)
        if f == "15F":
            h = round(roof_z - floors["15F"], 3)
        rows.append([f, "%+.3f" % (floors[f] - ffl0), ("%.3f" % h) if h is not None else "-", matrix[f]["program"][:34], plan_of.get(f, "평면 미발행")])
    rows.append(["ROOF", "%+.3f" % (roof_z - ffl0), "-", "A-ROOF_slab", "E-201~204 · S-302~305 · D-410"])
    y_end = table(sh, 14, 20, [14, 20, 22, 92, 58], ["층", "FFL (m)", "층고 (m)", "프로그램(구역명 면적㎡)", "평면 시트"], rows, row_h=7.4, pt=6.2)
    sh.text(14, y_end + 6, "※ 층고 = 다음 층 FFL과의 차이. 15F는 지붕 슬래브 윗면까지.", 5.5, "normal", "#666")
    sh.text(262, 16, "선 위계 (A3 종이 mm)", 9, "bold", "#111")
    legend = [(0.45, "#000", "절단 포셰·기둥·코어 벽·입면 전체 윤곽"), (0.25, "#222", "슬래브·코어·튜브의 보이는 윤곽"), (0.15, "#444", "기둥·외피 부재·에스컬레이터 윤곽"),
              (0.10, "#999", "레벨선·치수선·보조선(점선)"), (0.05, "#ccc", "구조 격자·배경")]
    for i, (w, col, t) in enumerate(legend):
        yy = 26 + i * 7.5
        sh.line(262, yy, 290, yy, w, col, "2.2,1.6" if w == 0.10 else None)
        sh.text(294, yy + 1.0, "%.2f mm  %s" % (w, t), 6, "normal", "#333")
    sh.text(262, 70, "표기", 9, "bold", "#111")
    for i, t in enumerate(["검은 원(실선) = 모델 기둥 / 점선 원 = 코어 인접 모델 기둥(1층 규칙상 생략 대상)", "회색 사각 = 가구·부스 (PROPOSED_ONLY, 설계 데이터 아님)", "SCHEMATIC = 상층 구획벽·문 미검증(모델에 없음)",
                           "MODEL_GEOMETRY = 3D 모델 메시에서 직접 파생", "SCHEMATIC / CONCEPT_DETAIL / BLOCKED_MISSING_SOURCE = 사실성 등급 표기"]):
        sh.text(262, 77 + i * 6.2, t, 5.8, "normal", "#333")
    sh.north_arrow(385, 112, fr["north_deg"], r=7)
    sh.text(262, 118, "도면 위쪽에서 진북 %.1f° (시계 방향)" % fr["north_deg"], 6, "normal", "#333")
    sh.text(262, 128, "3D 모델 (GLB)", 9, "bold", "#111")
    kinds = {}
    for o in mo["objects"]:
        kinds[o["kind"]] = kinds.get(o["kind"], 0) + 1
    ml = ["객체 %d개 · sha256 %s…" % (len(mo["objects"]), secr["model"]["sha256"][:16]), "기둥 %d · 층판 %d · 튜브 %d · 샤프트 %d · 에스컬레이터 %d" % (kinds.get("column", 0), kinds.get("slab", 0), kinds.get("tube_wall", 0), kinds.get("shaft", 0), kinds.get("stair", 0)),
          "외피 부재 %d · 코어 벽 %d · 램프 %d · 지붕 %d" % (kinds.get("facade", 0), kinds.get("core_wall", 0), kinds.get("ramp", 0), kinds.get("roof", 0)), "상층에는 외벽·구획벽·실내 문·창·가구·재료 정보가 없다."]
    for i, t in enumerate(ml):
        sh.text(262, 135 + i * 6, t, 6, "normal", "#333")
    sh.title_block()
    s2.save(os.path.join(run, "00_index", "A-002_levels_legend"))

    # ── A-001 목차 ───────────────────────────────────────────────────────────────────────────
    s1 = Sheet("A-001", "도면 목록·시트 상태표", None, "DOCUMENT", subtitle="발행 시트 %d장 (페이지 순서) · 후보 V1 · FREEZE 아님" % len(listing),
               extra_lines=["발행 시트와 참조로 커버되는 층을 구분: 평면은 3F·8F(+9F)·13F(+14F)와 1F(A-003)만 발행, 나머지 층은 층 정보표(A-002)에만 있음",
                            "축척 확정 미정(SCALE_PROFILE_DECISION_PENDING): 평면 1:200, 입면·단면 1:400, 상세 1:50(D-408은 1:100), 배치도 1:400"])
    rows = [[sid, t, sc, g, str(n + 1)] for n, (sid, t, sc, g, _) in enumerate(listing)]
    y_end = table(s1, 10, 14, [14, 112, 14, 230, 16], ["번호", "제목", "축척", "사실성 등급 / 상태", "쪽"], rows, row_h=7.6, pt=6.0)
    s1.text(10, y_end + 5, "사실성 등급: MODEL_GEOMETRY = 3D 메시에서 직접 파생 · SCHEMATIC = 설명용(검증 불완전) · USER_SUPPLIED = 사용자 제공 1층 시트(승인 전 후보) · BLOCKED_MISSING_SOURCE = 근거 부재로 미작성", 5.6, "normal", "#555")
    s1.title_block()
    s1.save(os.path.join(run, "00_index", "A-001_sheet_index"))

    # ── A-900 미확정 ────────────────────────────────────────────────────────────────────────
    s9 = Sheet("A-900", "미확정 설계·도면 단계 표기", None, "DOCUMENT", subtitle="이 도면집은 후보(CANDIDATE V1)이며 1층 최종 FREEZE가 아니다",
               extra_lines=["아래 항목은 모델에 근거가 없거나 사용자 결정 전이라 도면에 확정하지 않았다"])
    items = ["D-01  상층 실내 구획벽·출입문·화장실·피난 경로: 모델에 없음. 그리지 않음(건축 결정 필요)", "D-02  서측·동측 캡슐 출입구: 모델에 문 없음, 사용자 미승인 → 벽을 닫아 둠",
             "D-03  코어 A~D 상층 내부(계단·부속실·승강기): GLB는 외곽 벽만 → D-404는 1층 마스터만, 상층은 BLOCKED_MISSING_SOURCE",
             "D-05  외피(A-FACD) 성격(유리 커튼월/벽/난간): 모델 부재만 표시, 재료·접합 미검증", "D-06  코어 인접 기둥 10개: 상층에서 점선 원으로 표기(1층 규칙의 삭제를 상층에 적용할지 결정)",
             "D-07  3F 범례의 '시장 홀' 이름: A-PROG '판매' 구역의 렌더러 해석", "D-08  최종 축척: 평면 1:200, 입면·단면 1:400, 상세 1:50 — 논문 제출 규격 선택 대기",
             "D-09  13F·14F '문화·엔터' 구역: 좌석 등 가구 배치를 만들지 않음(결정 후 PROPOSED_ONLY로 추가 가능)", "층 평면: 3F·8F·13F만 발행(사용자 지시). 4F·5F는 3F와 동등하지 않아(검증) 합치지 않음. 나머지 층 평면 미발행",
             "8F~9F·13F~14F: '수직동선 개구만 다름(검증됨)'. 에스컬레이터·승강기 위치 차이는 각 시트 범례에 표기. EQUIVALENCE VERIFIED 아님",
             "입면: 기준 GL = 1F FFL. 대지 지형·지하 옹벽·지하층 맥락 입면은 모델에 없어 미작성(UNVERIFIED)", "단면 위치는 모델의 T1~T4·캡슐 위치에서 계산. 지반·옹벽 표시 없음",
             "상세 D-409 화물 승강기: 기계·하역 동선 미검증(SCHEMATIC). D-408 선큰: 계단 폭·단높이 속성 없음(단 수·방향·윤곽만)", "배치도 A-003은 사용자 제공 1F_CleanLine_FIXED 그대로(승인 전 후보 시트, 1층 최종 확정 아님)",
             "클라우드(Modal·Claude API) 미사용. 모든 시트는 로컬에서 생성", "ChatGPT 시각 검토·리터치는 후보 V1 이후 단계. 리터치 이미지는 정본에 합성하지 않음"]
    for i, t in enumerate(items):
        s9.text(14, 22 + i * 10.5, t, 6.8, "normal", "#222")
    s9.title_block()
    s9.save(os.path.join(run, "00_index", "A-900_unresolved"))

    # ── A-000 표지 ──────────────────────────────────────────────────────────────────────────
    s0 = Sheet("A-000", "표지", None, "DOCUMENT", subtitle="")
    s0.text(210, 80, "다층 상업시설 건축 도면집", 26, "bold", "#111", "middle")
    s0.text(210, 98, "수직 보행 연구 — 모델 기반 도면 파생 (후보 V1)", 12, "normal", "#444", "middle")
    s0.line(80, 108, 340, 108, 0.5, "#111")
    for i, t in enumerate(["54 × 54 m · 지하 2층(B2) ~ 지상 15층(15F) · 지붕 %+.1f m" % (roof_z - ffl0), "도면집 후보 V1 · %s" % now, "상태: CANDIDATE — NOT FROZEN (1층 최종 FREEZE 아님)",
                           "3D 모델: GMC-ZZ-ZZ-M3-0701.glb  sha256 %s…" % secr["model"]["sha256"][:20], "생성: drawing-pipeline %s" % a.head.split(" ")[0][:12] + " + 미커밋 작업트리",
                           "수록: 배치도·기준층 평면 3·입면 4·단면 4+키플랜·상세 10 (총 %d장)" % len(listing)]):
        s0.text(210, 125 + i * 9.5, t, 9, "normal", "#222", "middle")
    s0.north_arrow(210, 215, fr["north_deg"], r=9)
    s0.text(210, 238, "상층 벽·문·재료는 모델에 없어 확정하지 않음 · 모든 도면은 3D 모델에서 파생", 7, "normal", "#777", "middle")
    s0.save(os.path.join(run, "00_index", "A-000_cover"))

    # ── 조립 ─────────────────────────────────────────────────────────────────────────────────
    pdfs = {"A-000": os.path.join(run, "00_index", "A-000_cover.pdf"), "A-001": os.path.join(run, "00_index", "A-001_sheet_index.pdf"),
            "A-002": os.path.join(run, "00_index", "A-002_levels_legend.pdf"), "A-900": os.path.join(run, "00_index", "A-900_unresolved.pdf")}
    book = fitz.open()
    toc, pages = [], []
    for sid, title, sc, grade, path in listing:
        src = fitz.open(path or pdfs[sid])
        book.insert_pdf(src)
        n = len(book)
        toc.append([1, "%s  %s" % (sid, title), n])
        pages.append({"page": n, "sheet": sid, "title": title, "scale": sc, "grade": grade, "source_pdf": path or pdfs[sid], "source_sha256": sha(path or pdfs[sid])})
    book.set_toc(toc)
    book.set_metadata({"title": "다층 상업시설 건축 도면집 — 후보 V1 (C-T14D)", "author": "drawing-pipeline", "subject": "CANDIDATE — NOT FROZEN",
                       "keywords": "model-derived drawing set; Level S upper floors", "creator": "t14d_make_book.py", "producer": "PyMuPDF"})
    out = os.path.join(run, "05_book", "Drawing_Set_Candidate_V1.pdf")
    book.save(out, garbage=4, deflate=True)
    book.close()

    # 미리보기: 전 시트 썸네일 + 대표 6장 큰 이미지
    from PIL import Image
    d = fitz.open(out)
    thumbs = []
    for pg in d:
        pm = pg.get_pixmap(dpi=36)
        thumbs.append(Image.frombytes("RGB", (pm.width, pm.height), pm.samples))
    tw, th = thumbs[0].size
    cols = 6
    rows_n = math.ceil(len(thumbs) / cols)
    sheet = Image.new("RGB", (cols * (tw + 12) + 12, rows_n * (th + 30) + 12), "#dddddd")
    from PIL import ImageDraw, ImageFont
    dr = ImageDraw.Draw(sheet)
    ft = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 14)
    for i, im in enumerate(thumbs):
        x, y = 12 + (i % cols) * (tw + 12), 12 + (i // cols) * (th + 30)
        sheet.paste(im, (x, y + 20))
        dr.text((x, y), pages[i]["sheet"] + "  " + pages[i]["title"][:20], font=ft, fill="#111")
    prev = os.path.join(run, "05_book", "Drawing_Set_Candidate_V1_preview.png")
    sheet.save(prev)
    big = ["A-003", "P-102", "E-201", "S-302", "S-304", "D-407"]
    bigs = []
    for sid in big:
        pgn = next(p["page"] for p in pages if p["sheet"] == sid)
        pm = d[pgn - 1].get_pixmap(dpi=110)
        pth = os.path.join(run, "05_book", "preview_%s.png" % sid)
        pm.save(pth)
        bigs.append(pth)
    meta = {"pdf": out, "pdf_sha256": sha(out), "pages": len(d), "preview": prev, "large_previews": bigs, "sheets": pages, "git_head": a.head,
            "model_sha256": secr["model"]["sha256"], "date": now, "published_floor_plans": published, "unpublished_floors": [f for f in order if f not in plan_of], "status": "CANDIDATE — NOT FROZEN"}
    json.dump(meta, open(os.path.join(run, "05_book", "book_registry.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(run, "00_index", "sheet_index.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["page", "sheet", "title", "scale", "grade"])
        for p in pages:
            w.writerow([p["page"], p["sheet"], p["title"], p["scale"], p["grade"]])
    print("BOOK", out, "pages", len(pages))
    print("PREVIEW", prev)


if __name__ == "__main__":
    main()
