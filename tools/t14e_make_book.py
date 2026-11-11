"""V2 도면집 조립: 표지·목록·범례·미확정·층 동등성/치수 현황 시트를 만들고 30장 전체를 하나의 벡터 PDF로 합친다.

    python -I tools/t14e_make_book.py --run <V2 루트> --glb <glb> --head <git HEAD>

모든 숫자는 레지스트리·감사 증거에서 읽는다. 목록의 쪽 번호는 실제 조립된 PDF 쪽에서 계산한다(목록 = 쪽수 일치는 QA에서 다시 검사).
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
import t14d_sheet as _ts  # noqa: E402
from t14g import config as cfg, modelsrc, registry as sheetreg  # noqa: E402
from t14f import fonts as cjk_fonts  # noqa: E402
from t14g import make_coverage  # noqa: E402
cfg.apply(_ts)
from t14d_sheet import Sheet  # noqa: E402
import t14e_dims as dm  # noqa: E402

ED = cfg.EDITION


def detail_scale_text():
    """'상세 1:50 (D-407·408·410은 1:100)' built from the registry, not typed."""
    by = {}
    for sid, den in sheetreg.DETAIL_SCALE.items():
        by.setdefault(den, []).append(sid)
    base = max(by, key=lambda d: len(by[d]))
    others = "·".join(s.replace("D-", "") if i else s for i, s in enumerate(sorted(sum((v for d, v in by.items() if d != base), []))))
    odd = sorted({d for d in by if d != base})
    return "상세 1:%d(%s은 1:%s)" % (base, others, "·".join(str(d) for d in odd)) if odd else "상세 1:%d" % base


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
    ap.add_argument("--glb", default=None, help="원본 GLB(없어도 됨)")
    ap.add_argument("--head", required=True)
    a = ap.parse_args()
    run = os.path.abspath(a.run)
    P = lambda *x: os.path.join(run, *x)
    now = datetime.date.today().isoformat()
    ev = jl(P("00_index", "floor_equivalence_evidence.json"))
    plans = jl(P("plans", "plan_sheets.json"))
    elev = jl(P("elevations", "elevation_registry.json"))
    secr = jl(P("sections", "section_line_registry.json"))
    det = jl(P("details", "detail_registry.json"))["details"]
    mo = jl(P("model_cache", "model_objects.json"))
    fr = elev["frame"]
    floors, ff = ev["floor_z_m"], ev["floor_to_floor_m"]
    ffl0 = floors["1F"]
    roof_z = max(o["zmax"] for o in mo["objects"] if o["kind"] == "roof")
    matrix = {r["floor"]: r for r in csv.DictReader(open(P("00_index", "floor_typology_matrix.csv"), encoding="utf-8-sig"))}
    group_of = {}
    for g in ev["groups"]:
        for f in g["floors"]:
            group_of[f] = g
    site_pdf = P("plans", "A-003_site_plan_1F_1to400.pdf")
    shutil.copy(P("reference_1F", "1F_CleanLine_FIXED_user_supplied.pdf"), site_pdf)

    # ── 시트 목록 ──────────────────────────────────────────────────────────────────────────────
    L = [("A-000", "표지", "—", "DOCUMENT", P("appendix", "A-000_cover.pdf"), "appendix"),
         ("A-001", "도면 목록·시트 상태표", "—", "DOCUMENT", P("appendix", "A-001_sheet_index.pdf"), "appendix"),
         ("A-002", "범례·기호·축척·사실성 등급·상태 표기", "—", "DOCUMENT", P("appendix", "A-002_legend_notation.pdf"), "appendix"),
         ("A-003", "배치도 / 1층 계획 (사용자 제공 1F_CleanLine_FIXED, 수정 없음)", "1:400", "USER_SUPPLIED · 1층 프로그램 후보(승인 전)", site_pdf, "plans")]
    plan_of = {"1F": "A-003 (1:400 배치+1층)"}
    cov_pdf, cov_json, _cov = make_coverage.build(run, P("appendix", "A-902_floor_overview"))        # 17개 층 전부의 구성·차이(B2~15F)
    for p in plans:
        t = "%s 평면 (치수·축선·범례, 가구 PROPOSED_ONLY)" % "·".join(p["applies_to"])
        L.append((p["sheet"], t, p["scale"], "MODEL_GEOMETRY · LEVEL S · PROPOSED_ONLY · NOT FINAL", p["files"]["pdf"]["path"], "plans"))
        for m in p["applies_to"]:
            plan_of[m] = p["sheet"] if m == p["floor"] else "%s (공통, 차이 표기)" % p["sheet"]
    for e in elev["elevations"]:
        L.append((e["sheet"], "%s측 입면도" % {"N": "북", "E": "동", "S": "남", "W": "서"}[e["name"]], e["scale"], "MODEL_GEOMETRY", e["files"]["pdf"]["path"], "elevations"))
    L.append(("S-301", "단면 키플랜", "1:400", "MODEL_GEOMETRY", secr["section_locator"]["files"]["pdf"]["path"], "sections"))
    for s in secr["sections"]:
        L.append((s["sheet"], "단면도 %s" % s["name"], s["scale"], "MODEL_GEOMETRY · 실제 메시 절단", s["files"]["pdf"]["path"], "sections"))
    for d in det:
        L.append((d["sheet"], d["title"], d["scale"], d["grade"], d["files"]["pdf"]["path"], "details"))
    L.append(("A-900", "미확정 설계 결정·도면 한계", "—", "DOCUMENT", P("appendix", "A-900_unresolved.pdf"), "appendix"))
    L.append(("A-901", "층별 동등성 판정·평면 발행표·치수 포함 현황", "—", "DOCUMENT + MODEL_DATA", P("appendix", "A-901_floor_matrix_dimension_coverage.pdf"), "appendix"))
    L.append(("A-902", "층별 구성 일람 (B2~15F 17개 층, 1:1000)", "1:1000", "DOCUMENT + MODEL_DATA", cov_pdf, "appendix"))
    N = len(L)

    # ── A-000 표지 ─────────────────────────────────────────────────────────────────────────────
    s0 = Sheet("A-000", "표지", None, "DOCUMENT", subtitle="")
    s0.text(210, 78, "다층 상업시설 건축 도면집", 26, "bold", "#111", "middle")
    s0.text(210, 96, "수직 보행 연구 — 3D 모델에서 파생한 도면 (후보 %s)" % ED, 12, "normal", "#444", "middle")
    s0.line(80, 106, 340, 106, 0.5, "#111")
    ident = modelsrc.identity(run, a.glb)
    for i, t in enumerate(["54 × 54 m · 지하 2층(B2) ~ 지상 15층(15F) · 지붕 %+.1f m" % (roof_z - ffl0), "도면집 후보 %s · 개정 %s · 출력 %s" % (ED, cfg.REVISION, cfg.ISSUE_DATE),
                           "상태: CANDIDATE — NOT FROZEN · 상층 LEVEL S · 가구 PROPOSED_ONLY · NOT FINAL",
                           "3D 모델: GMC-ZZ-ZZ-M3-0701.glb (V2 기록 sha256 %s…, 원본 파일 없음) · 시트는 모델 캐시 %s…에서 생성" % ((ident["glb_sha256_recorded_by_v2"] or "?")[:12], ident["cache_sha256"].get("model_world.npz", "?")[:12]) if not ident["glb_present"]
                           else "3D 모델: GMC-ZZ-ZZ-M3-0701.glb  sha256 %s…" % ident["glb_sha256_verified"][:20],
                           "수록 %d장: 배치도·평면 %d·입면 %d·단면 %d(+키플랜)·상세 %d·부록" % (N, len(plans), len(elev["elevations"]), len(secr["sections"]), len(det))]):
        s0.text(210, 122 + i * 9.5, t, 9, "normal", "#222", "middle")
    s0.north_arrow(210, 205, fr["north_deg"], r=9)
    s0.text(210, 232, "상층에는 벽·문·창·재료 정보가 모델에 없어 확정하지 않았다 · 배치도(A-003)는 사용자 제공 파일을 그대로 수록", 7, "normal", "#777", "middle")
    s0.text(14, 286, "A-000", 10, "bold", "#111")
    s0.text(34, 286, "표지 · 도면집 후보 %s · CANDIDATE — NOT FROZEN" % ED, 7, "normal", "#555")
    s0.save(P("appendix", "A-000_cover"))

    # ── A-001 목록 ─────────────────────────────────────────────────────────────────────────────
    s1 = Sheet("A-001", "도면 목록·시트 상태표", None, "DOCUMENT", subtitle="발행 시트 %d장 = PDF %d쪽 (쪽 번호는 조립된 PDF에서 확인)" % (N, N),
               extra_lines=["평면은 1F(A-003)·3F·8F(+9F)·10F·13F(+14F)·15F만 발행. 나머지 층은 A-901 표에서 이유와 함께 '미발행' 표기",
                            "평면 1:250(A3에 치수·축선·범례·제목란을 함께 담는 최대 정수 축척) · 입면·단면 1:400 · %s" % detail_scale_text()])
    rows = [[sid, t, sc, g, str(n + 1), folder] for n, (sid, t, sc, g, _, folder) in enumerate(L)]
    table(s1, 10, 8, [14, 112, 14, 160, 12, 40], ["번호", "제목", "축척", "사실성 등급 / 상태", "쪽", "폴더"], rows, row_h=6.7, pt=5.8)
    s1.title_block()
    s1.save(P("appendix", "A-001_sheet_index"))

    # ── A-002 범례·기호 ────────────────────────────────────────────────────────────────────────
    s2 = Sheet("A-002", "범례·기호·축척·사실성 등급·상태 표기", None, "DOCUMENT", subtitle="모든 시트가 같은 기호와 선 위계를 쓴다 · 평면 시트의 상세 범례(구역 번호·가구 전략)는 각 평면 우측 패널",
               extra_lines=["진북 도면 위쪽에서 시계 방향 %.1f° · 좌표틀 = 1층 마스터와 동일 · 레벨 기준 GL = 1F FFL ±0.000" % fr["north_deg"]])
    sh = s2
    sh.text(14, 14, "1  선 위계 (A3 종이 mm)", 9, "bold", "#111")
    for i, (w, col, t, dsh) in enumerate([(0.45, "#000", "절단 포셰·기둥·코어 벽·입면 전체 윤곽", None), (0.25, "#222", "슬래브·코어·튜브 보이는 윤곽", None), (0.15, "#444", "기둥·외피 부재·에스컬레이터", None),
                                         (0.10, "#999", "레벨선·치수선·보조선 (점선)", "2.2,1.6"), (0.05, "#ccc", "구조 격자·배경", None)]):
        yy = 22 + i * 7.5
        sh.line(14, yy, 44, yy, w, col, dsh)
        sh.text(48, yy + 1.0, "%.2f mm  %s" % (w, t), 6.5, "normal", "#333")
    sh.text(14, 66, "2  기호", 9, "bold", "#111")
    dm.bubble(sh, 20, 76, "A", r=3.6)
    sh.text(27, 77.2, "축선 기호 (가로 A…, 세로 1…, 건물축 기준)", 6.5, "normal", "#333")
    dm.section_tag(sh, 20, 90, "A", "S-302", arrow=(0, -1))
    sh.text(32, 91.2, "단면 표시 (문자 + 보는 방향 + 참조 시트)", 6.5, "normal", "#333")
    dm.elevation_tag(sh, 20, 106, "E-201", (0, -1))
    sh.text(32, 107.2, "입면 표시 (번호 + 바라보는 방향)", 6.5, "normal", "#333")
    dm.detail_tag(sh, 18, 124, "D-401", dashed_r=5.0)
    sh.text(40, 125.2, "상세 호출 (점선 원 = 확대 위치, 번호 + 축척)", 6.5, "normal", "#333")
    dm.dim_h(sh, 14, 54, 140, "9000", pt=6.0)
    sh.text(58, 141.2, "치수선 (mm 정수, 10 mm 반올림, 모델에서 읽음)", 6.5, "normal", "#333")
    sh.path([[(20, 150.0), (24, 154.5), (16, 154.5)]], fill="#000", stroke="#000", w=0.1, closed=True)
    sh.text(27, 153.8, "레벨 기호  +0.000 = 1F FFL", 6.5, "normal", "#333")
    sh.north_arrow(20, 166, fr["north_deg"], r=5)
    sh.text(30, 167.2, "방위 (진북 %.1f° 시계 방향)" % fr["north_deg"], 6.5, "normal", "#333")
    # 해칭
    for k_ in range(0, 28, 2):
        sh.line(14 + k_, 182, 14 + k_ + 6, 176, 0.05, "#777")
    sh.path([[(14, 176), (42, 176), (42, 182), (14, 182)]], stroke="#000", w=0.3)
    sh.text(46, 180.4, "사선 해칭 = 모델에서 절단된 고체(재료 미확정, 일반 표기)", 6.5, "normal", "#333")
    sh.text(14, 196, "3  축척 정책", 9, "bold", "#111")
    for i, t in enumerate(["배치도·1층: 1:400 (사용자 제공 시트 그대로)", "평면: 1:250 — A3(420×297)에 54 m 건물·치수 3열·축선·우측 범례·제목란을 함께 담을 수 있는 가장 큰 정수 축척. 1:200 불가(건물 270 mm + 치수·범례 > 용지)",
                           "입면·단면: 1:400 · %s · 평면·입면·단면·상세 모든 축척 시트에 그래픽 스케일바" % detail_scale_text()]):
        sh.text(14, 204 + i * 6.2, t, 6, "normal", "#333")
    sh.text(212, 14, "4  사실성 등급", 9, "bold", "#111")
    for i, (g, t) in enumerate([("MODEL_GEOMETRY", "3D 모델 메시에서 직접 파생 (입면·단면·평면의 기둥·튜브·층판·램프·에스컬레이터)"), ("MODEL DETAIL", "상세도: 모델에서 읽은 형상·치수만 사용"),
                                ("CONCEPT DETAIL", "제안 단계 표현(근거 없는 시공 상세를 만들지 않음). 이번 도면집에는 없음"), ("UNRESOLVED DETAIL", "모델·결정 근거 부재 — 그리지 않고 사유를 적음"),
                                ("USER_SUPPLIED", "사용자가 제공한 시트를 수정 없이 수록 (A-003)"), ("PROPOSED_ONLY", "가구·프로그램 배치는 제안일 뿐 설계 데이터가 아님"),
                                ("LEVEL S", "상층 평면 = 기둥·튜브·코어·층판 + 제안 가구. 벽·문 없음"), ("NOT FINAL / NOT FROZEN", "최종 확정·동결 아님")]):
        sh.text(212, 22 + i * 7.6, g, 6.5, "bold", "#a33")
        sh.text(252, 22 + i * 7.6, t, 6, "normal", "#333")
    sh.text(212, 88, "5  가구·프로그램 표기 (평면 시트에서 사용)", 9, "bold", "#111")
    X0 = 214
    sh.path([[(X0, 96), (X0 + 12, 96), (X0 + 12, 100), (X0, 100)]], fill="#e9e9e9", stroke="#555", w=0.15)
    sh.text(X0 + 16, 99.2, "판매 섬 부스 A형 (2F–5F·B1·B2: 가로열 3.0×1.2 m, 외곽 선반)", 6, "normal", "#333")
    sh.path([[(X0 + 2, 104), (X0 + 5, 104), (X0 + 5, 112), (X0 + 2, 112)], [(X0 + 7, 104), (X0 + 10, 104), (X0 + 10, 112), (X0 + 7, 112)]], fill="#e9e9e9", stroke="#555", w=0.15)
    sh.text(X0 + 16, 109.2, "판매 섬 부스 B형 (6F–9F·11F 등: 세로 쌍 1.4×4.0 m) — 3F와 다른 배치", 6, "normal", "#333")
    sh.path([[(X0 + 6 + 3 * math.cos(t / 20 * 2 * math.pi), 119 + 3 * math.sin(t / 20 * 2 * math.pi)) for t in range(21)]], fill="#fff", stroke="#555", w=0.15)
    sh.text(X0 + 16, 120.2, "F&B 좌석: 4인 클러스터·벤치 열·공용 장탁자·바 카운터와 스툴", 6, "normal", "#333")
    sh.path([[(X0, 126), (X0 + 12, 126), (X0 + 12, 132), (X0, 132)]], fill="#f4f4f4", stroke="#555", w=0.15)
    sh.text(X0 + 16, 130.4, "문화·엔터: 이벤트 무대·계단 객석·전시 좌대·라운지 포드 (판매 부스 반복 없음)", 6, "normal", "#333")
    sh.path([[(X0 + 6 + 3 * math.cos(t / 20 * 2 * math.pi), 139 + 3 * math.sin(t / 20 * 2 * math.pi)) for t in range(21)]], fill="#dcdcdc", stroke="#555", w=0.15)
    sh.text(X0 + 16, 140.2, "정원·테라스: 식재 띠·수목·테라스 테이블 세트", 6, "normal", "#333")
    sh.text(212, 156, "6  입면·단면·상세 표기", 9, "bold", "#111")
    for i, t in enumerate(["레벨: 각 층 FFL(GL = 1F = ±0.000) 5 mm 반올림, 지붕 상단 별도 표기", "치수: 전체 폭 + 축선 간격 + 층고 체인 + 전체 높이 + 주요 요소 높이표", "입면 방위: 건물 면에 수직 정투영, 면 법선 방위로 N/E/S/W 명명",
                           "단면: 모델 메시 실제 절단(포셰 = 절단 고체), 절단선 위치는 S-301 키플랜", "숨은 선: 앞 객체로 가려진 부분은 제거(백색 덧칠 없음)"]):
        sh.text(212, 164 + i * 6.2, t, 6, "normal", "#333")
    sh.title_block()
    s2.save(P("appendix", "A-002_legend_notation"))

    # ── A-900 미확정 ──────────────────────────────────────────────────────────────────────────
    s9 = Sheet("A-900", "미확정 설계 결정·도면 한계", None, "DOCUMENT", subtitle="이 도면집은 후보(%s)이며 FREEZE가 아니다 · 아래 항목은 근거 부재 또는 사용자 결정 전이라 확정하지 않았다" % ED)
    items = ["U-01  상층 외벽·구획벽·실내 문·창·화장실·피난 경로: 모델에 없음 → 평면은 LEVEL S(기둥·튜브·코어·층판 + 제안 가구)",
             "U-02  캡슐(서측·동측) 출입구·문: 모델에 없고 사용자 미승인 → 벽을 닫아 둠 (D-405)", "U-03  코어 A~D 상층 내부(계단·부속실·승강기): GLB는 외곽 벽만 → D-404는 1층 마스터만, 상층은 UNRESOLVED DETAIL",
             "U-04  외피(A-FACD) 성격과 접합(유리 커튼월·벽·난간): 모델 부재 형상만 표시, 재료·접합 UNRESOLVED (D-406)", "U-05  평면 축척 1:250: 요구 1:200은 A3에 치수·범례 포함 불가 → 1:100 타일 분할 또는 A1 대판은 사용자 결정 대기",
             "U-06  8F~9F·13F~14F 공통 평면: 면적·프로그램 동일, 수직 개구만 다름(검증됨) → 한 장에 공통 + 차이 표기, '동등함'은 주장하지 않음", "U-07  B2·B1·2F·4F·5F·6F·7F·11F·12F는 3F 등과 같지 않아(프로그램·층판 차이) 합치지 않고 개별 평면을 발행하지 않음 → A-902 층별 구성 일람(17개 층)에서 확인",
             "U-08  가구·프로그램: 모두 PROPOSED_ONLY. 3F 판매 A형 / 8F·9F 판매 B형 / 10F·15F F&B 좌석 유형 구분 / 13F·14F 문화·엔터(판매 부스 반복 없음) / 정원층 식재·테라스",
             "U-09  치수: 모델 값을 10 mm 단위로 반올림(모델 노이즈 0.6 mm 수준). 구조 부재 두께·재료 규격은 모델에 없어 표기하지 않음", "U-10  선큰(D-408): 계단 폭·단높이는 마스터에 없고 단 수·방향·윤곽만. 지반·옹벽 미표시",
             "U-11  화물 승강기(D-409): 카·기계·승강장 문·하역 차량 동선 모델 없음 → 형상만 MODEL, 나머지 UNRESOLVED", "U-12  입면 대지 지형·지하 옹벽·인접 건물은 모델에 없어 그리지 않음 (GL = 1F FFL만)",
             "U-13  배치도 A-003은 사용자 제공 1F_CleanLine_FIXED 그대로 수록(승인 전 후보 시트). 원본·plans 사본은 수정 없음, 도면집 4쪽에만 'A-003' 쪽 번호표를 붙임", "U-14  클라우드(Modal·Claude API) 미사용, 신규 결제 없음. 모든 시트는 로컬에서 생성",
             "U-15  PDF 텍스트 추출 시 공백이 빠질 수 있음(cairosvg 글리프 출력). 화면·인쇄에는 영향 없음, 텍스트 검색 시 공백 없이 검색"]
    for i, t in enumerate(items):
        s9.text(14, 18 + i * 10.4, t, 6.8, "normal", "#222")
    s9.title_block()
    s9.save(P("appendix", "A-900_unresolved"))

    # ── A-901 층 매트릭스 + 치수 포함 현황 ────────────────────────────────────────────────────
    s91 = Sheet("A-901", "층별 동등성 판정·평면 발행표·치수 포함 현황", None, "DOCUMENT + MODEL_DATA", subtitle="판정 허용오차: 면적 대칭차 ≤ %.2f ㎡, Hausdorff ≤ %.2f m (층판·코어·튜브·외피·램프·구역)" % (ev["tolerance"]["sym_diff_m2"], ev["tolerance"]["hausdorff_m"]),
                extra_lines=["STRICT(완전 동일 쌍) 0건. 8F~9F·13F~14F는 수직동선 개구만 다름(CIRCULATION_ONLY). 3F~5F·8F~10F 동일 가설은 반증됨 — EQUIVALENCE VERIFIED 주장 없음"])
    order = ["B2", "B1"] + ["%dF" % i for i in range(1, 16)]
    rows = []
    for f in order:
        g = group_of.get(f, {})
        h = ff.get(f)
        if f == "15F":
            h = round(roof_z - floors["15F"], 3)
        r5_ = lambda v: round(v / 0.005) * 0.005                                      # 입면·단면과 같은 5 mm 반올림(7F +31.001 → +31.000)
        why = {"1F": "A-003 사용자 제공", "3F": "기준층(판매 A형)", "8F": "기준층(판매 B형, 9F 공통)", "9F": "8F와 공통 (개구 차이 표기)", "10F": "F&B 기준층", "13F": "문화·엔터 기준층, 14F 공통", "14F": "13F와 공통 (개구 차이 표기)", "15F": "F&B·정원 기준층"}.get(f, "사용자 지시(기준층만)에 따라 미발행")
        rows.append([f, "%+.3f" % r5_(floors[f] - ffl0), ("%.3f" % r5_(h)) if h is not None else "-", g.get("id", "-") + " " + {"INDEPENDENT": "독립", "TYPICAL_WITH_CIRCULATION_VARIATION": "공통+개구 차이"}.get(g.get("kind", ""), g.get("kind", "")), matrix[f]["program"], plan_of.get(f, "A-902 일람만"), why])
    y_end = table(s91, 10, 14, [12, 18, 15, 50, 76, 40, 68], ["층", "FFL (m)", "층고 (m)", "그룹 · 종류(증거)", "프로그램(구역 ㎡)", "평면 시트", "발행 이유"], rows, row_h=6.3, pt=5.6)
    y0 = y_end + 6
    s91.text(10, y0, "시트별 치수·참조 기호 포함 현황 (레지스트리에서 읽음)", 8, "bold", "#111")
    crow = []
    for p in plans:
        m = p["meta"]
        crow.append([p["sheet"], "평면", str(m["overall_chains"]), str(m["grid_chains"] + m["setout_chains"]), str(m["major_dims"]), str(m["axis_bubbles"]), str(m["section_tags"]), str(m["elevation_tags"]), str(m["detail_callouts"])])
    for e in elev["elevations"]:
        m = e["dimension_meta"]
        crow.append([e["sheet"], "입면", str(m["overall_chains"]), str(m["grid_chains"]), str(m["major_dims"]), str(m["axis_bubbles"]), "-", "-", str(m["detail_callouts"])])
    for s in secr["sections"]:
        m = s["dimension_meta"]
        crow.append([s["sheet"], "단면", str(m["overall_chains"]), str(m["grid_chains"]), str(m["major_dims"]), str(m["axis_bubbles"]), "-", "-", str(m["detail_callouts"])])
    for d in det:
        m = d["dimension_meta"]
        crow.append([d["sheet"], "상세", "-", "-", str(len(d["dimensions"])), "-", "-", "-", "—"])
    table(s91, 10, y0 + 2, [20, 14, 20, 22, 24, 20, 20, 20, 22], ["시트", "종류", "전체치수열", "축선/배치열", "주요치수", "축선기호", "단면표시", "입면표시", "상세호출"], crow[:12], row_h=4.9, pt=5.2, head_pt=5.4)
    table(s91, 212, y0 + 2, [20, 14, 20, 22, 24, 20, 20, 20, 22], ["시트", "종류", "전체치수열", "축선/배치열", "주요치수", "축선기호", "단면표시", "입면표시", "상세호출"], crow[12:], row_h=4.9, pt=5.2, head_pt=5.4)
    s91.title_block()
    s91.save(P("appendix", "A-901_floor_matrix_dimension_coverage"))

    # ── 조립 ──────────────────────────────────────────────────────────────────────────────────
    book = fitz.open()
    toc, pages = [], []
    for sid, title, sc, grade, path, folder in L:
        src = fitz.open(path)
        book.insert_pdf(src)
        n = len(book)
        if sid == "A-003":                                   # 도면집 쪽에만 쪽 번호표를 붙인다(plans\A-003 사본과 원본은 수정 없음). 우측 흰 범례 상자의 빈 하단
            pg_ = book[n - 1]
            pg_.insert_text((922, 812), "A-003", fontname="cjkb", fontfile=cjk_fonts.resolve("bold")[0], fontsize=8, color=(0.07, 0.07, 0.07))
            pg_.insert_text((950, 812), "도면집 %s · 사용자 제공 시트(쪽 번호표만 추가, 본문 수정 없음)" % ED, fontname="cjkr", fontfile=cjk_fonts.resolve("regular")[0], fontsize=6, color=(0.3, 0.3, 0.3))
        toc.append([1, "%s  %s" % (sid, title), n])
        pages.append({"page": n, "sheet": sid, "title": title, "scale": sc, "grade": grade, "folder": folder, "source_pdf": path, "source_sha256": sha(path)})
    book.set_toc(toc)
    book.set_metadata({"title": "다층 상업시설 건축 도면집 — 후보 %s" % ED, "author": "drawing-pipeline", "subject": "CANDIDATE — NOT FROZEN", "keywords": "model-derived drawing set; Level S upper floors", "creator": "t14e_make_book.py", "producer": "PyMuPDF"})
    book_name = "drawing_set_candidate_%s" % ED.lower()
    out = P("book", book_name + ".pdf")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    book.subset_fonts()                                      # 시트마다 들어 있는 전체 글꼴 사본(V2: 17 MB)을 쓰인 글리프만 남긴다
    book.save(out, garbage=4, deflate=True)
    book.close()
    # 쪽 번호가 들어간 A-001 다시 만들기 위해 목록 쪽 = 실제 쪽 확인
    d = fitz.open(out)
    assert len(d) == N, (len(d), N)
    from PIL import Image, ImageDraw, ImageFont
    thumbs = []
    for pg in d:
        pm = pg.get_pixmap(dpi=36)
        thumbs.append(Image.frombytes("RGB", (pm.width, pm.height), pm.samples))
    tw, th = thumbs[0].size
    cols = 6
    sheet = Image.new("RGB", (cols * (tw + 12) + 12, math.ceil(len(thumbs) / cols) * (th + 30) + 12), "#dddddd")
    dr = ImageDraw.Draw(sheet)
    ft = ImageFont.truetype(cjk_fonts.resolve("regular")[0], 14)
    for i, im in enumerate(thumbs):
        x, y = 12 + (i % cols) * (tw + 12), 12 + (i // cols) * (th + 30)
        sheet.paste(im, (x, y + 20))
        dr.text((x, y), pages[i]["sheet"] + "  " + pages[i]["title"][:20], font=ft, fill="#111")
    prev = P("book", book_name + "_preview.png")
    sheet.save(prev)
    meta = {"pdf": out, "pdf_sha256": sha(out), "pages": len(d), "preview": prev, "sheets": pages, "git_head": a.head, "model_sha256": secr["model"]["sha256"], "date": now,
            "published_floor_plans": sorted(plan_of), "unpublished_floors": [f for f in order if f not in plan_of], "status": "CANDIDATE — NOT FROZEN"}
    json.dump(meta, open(P("book", "book_registry.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"edition": ED, "pages": len(d), "sheets": [{k: p[k] for k in ("page", "sheet", "title", "scale", "grade", "folder", "source_sha256")} for p in pages]},
              open(P("00_index", "sheet_index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(P("00_index", "sheet_index.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["page", "sheet", "title", "scale", "grade", "folder"])
        for p in pages:
            w.writerow([p["page"], p["sheet"], p["title"], p["scale"], p["grade"], p["folder"]])
    print("BOOK", os.path.abspath(out), "pages", len(pages))
    print("PREVIEW", os.path.abspath(prev))


if __name__ == "__main__":
    main()
