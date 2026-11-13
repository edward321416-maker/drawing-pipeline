"""Part II document sheets: appendix cover (A-000), sheet index (A-001), legend/notation (A-002), unresolved decisions (A-900).

All numbers come from the run (model cache identity, registries, counts); nothing about the building is typed here.
"""
import math

import t14i  # noqa: F401
from t14i import config as cfg
from t14i import common
from t14d_sheet import Sheet
import t14e_dims as dm
from t14g import modelsrc

A3 = cfg.PAPER_A3


def _table(sh, x, y, widths, header, rows, row_h=4.6, pt=6.5, head_pt=7.0, zebra=True):
    x1 = x + sum(widths)
    sh.path([[(x, y), (x1, y), (x1, y + row_h + 0.6), (x, y + row_h + 0.6)]], fill="#eee", stroke="#222", w=0.2)
    cx = x
    for w, h in zip(widths, header):
        sh.text(cx + 1.2, y + row_h * 0.8, h, head_pt, "bold", "#111")
        cx += w
    y += row_h + 0.6
    for i, r in enumerate(rows):
        if zebra and i % 2:
            sh.path([[(x, y), (x1, y), (x1, y + row_h), (x, y + row_h)]], fill="#f7f7f7", stroke=None, w=0.0)
        cx = x
        for w, c in zip(widths, r):
            sh.text(cx + 1.2, y + row_h * 0.78, c, pt, "normal", "#222")
            cx += w
        y += row_h
        sh.line(x, y, x1, y, 0.06, "#bbb")
    return y


def build_cover(run, out_base, counts, ident, head):
    s = Sheet("A-000", "기술 도면 부록 표지", None, "DOCUMENT · NOT FROZEN", subtitle="PART II  Technical Drawing Appendix")
    s.text(210, 62, "다층 상업시설 — 기술 도면 부록", 24, "bold", "#111", "middle")
    s.text(210, 76, "PART II  Technical Drawing Appendix (후보 %s · NOT FROZEN)" % cfg.EDITION, 12, "normal", "#444", "middle")
    s.line(70, 84, 350, 84, 0.5, "#111")
    lines = ["이 부록은 Part I(졸업 설계 도면집)의 근거가 되는 기술 도면이다: 층별 평면·4면 입면·4개 단면·상세 D-401~D-410·치수/출처/검증 기록.",
             "수록: %s" % counts,
             "모델 출처: 전층 GLB '%s' — %s" % (ident["glb_name"], "이 컴퓨터에 없음(BLOCKED_MISSING_SOURCE). 시트는 모델 캐시 model_world.npz sha256 %s…에서 생성" % ident["cache_sha256"].get("model_world.npz", "?")[:16]
                                                if not ident["glb_present"] else "sha256 %s…" % ident["glb_sha256_verified"][:16]),
             "V2가 기록한 GLB sha256 %s… 는 원본이 없어 검증하지 못했다(기록값일 뿐)." % (ident.get("glb_sha256_recorded_by_v2") or "?")[:16],
             "코드 커밋 %s · 개정 %s (%s) · 출력 %s" % (head[:10], cfg.REVISION, cfg.EDITION, cfg.ISSUE_DATE)]
    for i, t in enumerate(lines):
        s.text(210, 98 + i * 8.0, t, 8, "normal", "#222", "middle")
    y0 = 152
    s.text(40, y0, "표기 등급 (모든 도면 요소는 하나에 속한다)", 10, "bold", "#111")
    rows = [(cfg.MODEL_VERIFIED, "모델 캐시의 메시·슬라이스·1층 마스터에서 코드가 직접 읽고 측정한 값(객체 이름을 근거로 적음)"),
            ("DERIVED", "모델 값으로 한 계산(예: 5500÷12). 도면에 '계산값'으로 표시, 승인 치수 아님"),
            (cfg.CONCEPT_PROPOSED, "근거 없는 제안(재료·접합·난간·가구·동선·서술). 시공 확정 정보가 아님. 제품명·규격 없음"),
            (cfg.UNRESOLVED, "모델·결정 근거가 없어 그리지 않고 사유를 적음(상층 벽·문·피난, 캡슐 출입구, 선큰 단 형식, 지붕 개방 …)")]
    for i, (k, t) in enumerate(rows):
        yy = y0 + 10 + i * 12
        if k in cfg.CLASS_COLOR:
            common.badge(s, 40, yy - 4.2, k, w=42, h=6.0, pt=7.0)
        else:
            s.path([[(40, yy - 4.2), (82, yy - 4.2), (82, yy + 1.8), (40, yy + 1.8)]], fill="#fff", stroke="#555", w=0.3)
            s.text(61, yy, k, 7, "bold", "#555", "middle")
        s.text(88, yy, t, 7.5, "normal", "#222")
    s.text(40, 224, "글자 크기: 자체 품질 목표(A3 인쇄) — 기호·미세 주석 ≥ 6 pt, 주요 주석 ≥ 7 pt (법정 최소값이 아니다).", 7.5, "normal", "#555")
    s.text(40, 232, "A1 1:200 시트(P-201·P-202)는 접이식/별도 출력, 나머지는 A3 가로. 목록 A-001에 쪽 번호와 용지를 적었다.", 7.5, "normal", "#555")
    s.north_arrow(380, 84, 63.2, r=6.0)
    s.title_block()
    return common.sheet_row(s, s.save(out_base), "기술 도면 부록 표지", "DOCUMENT", "appendix", None, A3)


def build_index(run, out_base, entries, sid="A-001", title="도면 목록 (두 도면집 전체)"):
    """entries: dicts(sheet, title, part, page, paper, scale, status). Two columns, row height 4.2 mm."""
    s = Sheet(sid, title, None, "DOCUMENT · NOT FROZEN", subtitle="Part I = %s · Part II = %s (쪽 번호는 각 PDF 안의 쪽)" % (cfg.OUT_BOOK_I, cfg.OUT_BOOK_II))
    n = len(entries)
    per = math.ceil(n / 2)
    cols = [entries[:per], entries[per:]]
    for ci, chunk in enumerate(cols):
        x = 10 + ci * 205
        rows = [[e["sheet"], e["title"][:40], e["scale"], e["paper"], "%s-%s" % (e["part"], e["page"]), (e.get("status") or "")[:18]] for e in chunk]
        _table(s, x, 8, [14, 92, 13, 10, 12, 54 - 0], ["번호", "제목", "축척", "용지", "쪽", "등급"], rows, row_h=4.35, pt=6.0, head_pt=6.5)
    s.title_block()
    return common.sheet_row(s, s.save(out_base), title, "DOCUMENT", "appendix", None, A3)


def build_legend(run, out_base, north_deg):
    s = Sheet("A-002", "범례·기호·축척 정책·표기 등급", None, "DOCUMENT · NOT FROZEN", subtitle="모든 시트가 같은 선 위계·기호·표기 등급을 쓴다",
              extra_lines=["진북: 도면 위쪽에서 시계 방향 %.1f° · 좌표틀 = 1층 마스터 · 레벨 기준 GL = 1F FFL ±0.000" % north_deg])
    s.text(14, 14, "1  선 위계 (A3 종이 mm)", 9, "bold", "#111")
    for i, (w, col, t, dsh) in enumerate([(0.45, "#000", "절단 포셰·기둥·코어 벽·입면 전체 윤곽", None), (0.25, "#222", "슬래브·코어·튜브 보이는 윤곽", None), (0.15, "#444", "기둥·외피 부재·에스컬레이터", None),
                                         (0.10, "#999", "레벨선·치수선·보조선 (점선)", "2.2,1.6"), (0.05, "#ccc", "구조 격자·배경", None)]):
        yy = 22 + i * 7.5
        s.line(14, yy, 44, yy, w, col, dsh)
        s.text(48, yy + 1.0, "%.2f mm  %s" % (w, t), 7, "normal", "#333")
    s.text(14, 66, "2  기호", 9, "bold", "#111")
    dm.bubble(s, 20, 76, "A", r=3.6)
    s.text(27, 77.2, "축선 기호 (가로 A…, 세로 1…, 건물축 기준)", 7, "normal", "#333")
    dm.section_tag(s, 20, 90, "A", "S-302", arrow=(0, -1))
    s.text(32, 91.2, "단면 표시 (문자 + 보는 방향 + 참조 시트)", 7, "normal", "#333")
    dm.elevation_tag(s, 20, 106, "E-201", (0, -1))
    s.text(32, 107.2, "입면 표시 (번호 + 바라보는 방향)", 7, "normal", "#333")
    dm.detail_tag(s, 18, 124, "D-401", dashed_r=5.0)
    s.text(40, 125.2, "상세 호출 (점선 원 = 확대 위치, 번호 + 축척)", 7, "normal", "#333")
    dm.dim_h(s, 14, 54, 140, "9000", pt=7.0)
    s.text(58, 141.2, "치수선 (mm, 10 mm 반올림, 모델에서 읽음)", 7, "normal", "#333")
    s.path([[(20, 150.0), (24, 154.5), (16, 154.5)]], fill="#000", stroke="#000", w=0.1, closed=True)
    s.text(27, 153.8, "레벨 기호  +0.000 = 1F FFL", 7, "normal", "#333")
    s.north_arrow(20, 166, north_deg, r=5)
    s.text(30, 167.2, "방위 (진북 %.1f° 시계 방향)" % north_deg, 7, "normal", "#333")
    for k_ in range(0, 28, 2):
        s.line(14 + k_, 182, 14 + k_ + 6, 176, 0.05, "#777")
    s.path([[(14, 176), (42, 176), (42, 182), (14, 182)]], stroke="#000", w=0.3)
    s.text(46, 180.4, "사선 해칭 = 모델에서 절단된 고체(재료 미확정, 일반 표기)", 7, "normal", "#333")
    s.text(14, 196, "3  축척 정책 (평면)", 9, "bold", "#111")
    pol = ["A3 1:250 = OVERVIEW(개요도). 1:200이라고 쓰지 않는다 — 54 m = 216 mm, 치수열·범례·제목란을 함께 담는 가장 큰 A3 정수 축척",
           "A1 1:200 = 전체 평면(P-201 3F, P-202 13F, 841×594 mm). A3 1:200 = 분할 평면(P-211·212 3F, P-213·214 13F, 정합 표식 MATCH LINE)",
           "입면·단면 1:400 · 배치 A-003 1:400 · 층별 일람 A-902 1:1000 · 상세 1:50 / 1:100 (상세 시트마다 레지스트리 값, 그래픽 스케일바 필수)"]
    for i, t in enumerate(pol):
        s.text(14, 204 + i * 6.4, t, 7, "normal", "#333")
    s.text(212, 14, "4  표기 등급 (모든 요소는 하나에 속함)", 9, "bold", "#111")
    for i, (g, t) in enumerate([(cfg.MODEL_VERIFIED, "모델 메시·슬라이스·마스터에서 코드가 읽고 측정"), ("DERIVED", "모델 값의 계산(예: 5500÷12). 승인 치수 아님"),
                                (cfg.CONCEPT_PROPOSED, "제안(재료·접합·난간·가구·동선·서술). 시공 확정 아님, 제품 없음"), (cfg.UNRESOLVED, "근거·결정 없음 → 그리지 않고 사유 표기"),
                                ("USER_SUPPLIED", "사용자 제공 시트를 수정 없이 수록 (A-003)"), ("PROPOSED_ONLY", "가구·프로그램 배치는 제안일 뿐 설계 데이터가 아님"),
                                ("LEVEL S", "상층 평면 = 기둥·튜브·코어·층판 + 제안 가구. 벽·문 없음"), ("NOT FINAL / NOT FROZEN", "최종 확정·동결 아님")]):
        s.text(212, 22 + i * 7.6, g, 7, "bold", cfg.CLASS_COLOR.get(g, "#a33"))
        s.text(262, 22 + i * 7.6, t, 7, "normal", "#333")
    s.text(212, 88, "5  글자 크기 정책 (자체 품질 목표, 법정 최소값 아님)", 9, "bold", "#111")
    for i, t in enumerate(["기호·미세 주석 ≥ 6 pt (A3 인쇄), 주요 주석(실명·치수·설명) ≥ 7 pt를 목표로 한다.", "독립 검사기가 완성 PDF의 모든 글자 크기를 읽어 6 pt 미만을 결함으로 센다.", "6~7 pt 구간은 정보로 집계한다."]):
        s.text(212, 96 + i * 6.2, t, 7, "normal", "#333")
    s.text(212, 120, "6  입면·단면·상세 표기", 9, "bold", "#111")
    for i, t in enumerate(["레벨: 각 층 FFL(GL = 1F = ±0.000) 5 mm 반올림, 지붕·튜브 상단 별도 표기", "치수: 전체 폭 + 축선 간격 + 층고 체인 + 전체 높이 + 주요 요소 높이표",
                           "입면 방위: 건물 면에 수직 정투영, 면 법선 방위로 N/E/S/W 명명", "단면: 모델 메시 실제 절단(포셰 = 절단 고체), 절단선 위치는 S-301", "숨은 선: 앞 객체로 가려진 부분은 제거(백색 덧칠 없음)"]):
        s.text(212, 128 + i * 6.2, t, 7, "normal", "#333")
    s.title_block()
    return common.sheet_row(s, s.save(out_base), "범례·기호·축척 정책·표기 등급", "DOCUMENT", "appendix", None, A3)


UNRESOLVED_ITEMS = [
    ("U-01", "상층 외벽·구획벽·문·창·화장실·피난 경로", "모델에 없음 → LEVEL S, 그리지 않음", "설계 여부(피난·방화 설계는 임의 확정하지 않음)"),
    ("U-02", "캡슐 출입구·문", "닫힘 (D-405)", "위치·형식"),
    ("U-03", "상층 코어 내부(계단·부속실·승강기)", "1F 마스터만 MODEL, 상층 코어 단면은 D-404에 CONCEPT PROPOSED로 분리", "상층 코어 설계"),
    ("U-04", "외피 성격과 접합(커튼월·벽·난간)", "형상만 MODEL. D-406 접합 원리는 CONCEPT PROPOSED", "외피 구분·재료"),
    ("U-05", "평면 축척 채택", "A1 1:200 · A3 1:200 분할을 생성함. A3 1:250은 OVERVIEW", "최종 출력 형식 선택"),
    ("U-06", "8F~9F · 13F~14F 공통 평면", "공통 + 차이 표기(A-902 붉은 부분), 동등 주장 없음", "받아들일지"),
    ("U-07", "평면 미발행 층", "B2·B1·2F·6F·7F·11F·12F 평면(P-106~112)과 차이도(A-904) 추가", "4F·5F 별도 평면 필요 여부"),
    ("U-08", "가구·프로그램·동선", "전부 PROPOSED_ONLY / CONCEPT PROPOSED", "어느 안을 채택할지"),
    ("U-09", "치수 반올림·구조 규격", "10 mm 반올림. 부재 규격·재료는 모델에 없음", "구조 규격 자료"),
    ("U-10", "선큰 계단의 단 형식", "12단·−5.5 m = 모델 사실. 458 mm는 계산값(승인 치수 아님)", "보행 계단인지 객석형 단인지, 단 수의 뜻"),
    ("U-11", "화물 승강기 동선", "형상만 MODEL, 하역→보관→승강로 동선은 CONCEPT PROPOSED", "화물 동선·카·승강장"),
    ("U-12", "입면 대지 지형", "GL = 1F", "대지 모델"),
    ("U-13", "배치도 A-003", "사용자 제공, 수정 없음", "1층 최종 승인"),
    ("U-14", "클라우드·Modal", "미사용(잔액·지출 한도 미확인), 결제 변경 없음", "필요 시 별도 승인"),
    ("U-16", "지붕 개방 여부", "단면에 슬래브의 모델 범위만 표기", "지붕 슬래브 범위"),
    ("U-17", "EV 피트 −16.5 m", "단면은 B2−1.5 m에서 절단하고 기재", "피트 도시 여부"),
    ("U-18", "프로그램 면적의 정의", "'프로그램 볼륨 투영 면적'과 사용 면적은 다름(A-903)", "순 사용 면적 정의"),
    ("U-19", "Part I 서술(개념·시나리오)", "작성자 해석 = CONCEPT PROPOSED", "작성자 검토·수정"),
    ("U-20", "원본 GLB", "BLOCKED_MISSING_SOURCE — 캐시로 생성, 원본 해시 미검증", "GLB 제공 시 재검증"),
]


def build_unresolved(run, out_base, extra_items=()):
    s = Sheet("A-900", "미확정 설계 결정·도면 한계", None, "DOCUMENT · UNRESOLVED 목록", subtitle="이 도면집은 후보(%s)이며 FREEZE가 아니다 · 아래 항목은 근거 부재 또는 사용자 결정 전이라 확정하지 않았다" % cfg.EDITION)
    rows = [list(r) for r in UNRESOLVED_ITEMS] + [list(r) for r in extra_items]
    _table(s, 10, 8, [12, 80, 150, 148], ["번호", "항목", "현재 처리", "필요한 결정"], rows, row_h=7.4, pt=7.0, head_pt=7.5)
    s.title_block()
    return common.sheet_row(s, s.save(out_base), "미확정 설계 결정·도면 한계", "DOCUMENT", "appendix", None, A3)
