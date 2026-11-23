"""Builds the audit reconciliation pack (Markdown, CSV, JSON, Korean A3 PDF, page previews, SHA256 manifest) from measured data.

    python -I tools/t14s/package_audit_r1.py            # writes docs/t14t_audit_r1/*

Inputs (all read only): docs/t14t_audit_r1/data/*.json (authored), docs/t14t_audit_r1/measurements/measurements.json,
docs/t14t_audit_r1/evidence/*.json (re-run checks), outputs/T14T/<floor>/*_metadata.json, docs/t14t_audit_r1/source/pr30_review_comments_20261123.md.
Nothing under outputs/ or data/ is touched. The pack contains no approval and no architectural design change.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "docs" / "t14t_audit_r1"
BASE_SHA = "1164fc0f58d943598d8e48146a02fcb3214c852e"
FONT = Path(r"C:\Windows\Fonts\malgun.ttf")
FONT_B = Path(r"C:\Windows\Fonts\malgunbd.ttf")
A3 = (1190.55, 841.89)
M = 36.0
STATUS_COLOR = {"RESOLVED_VERIFIED": (0.80, 0.93, 0.80), "RESOLVED_UNVERIFIED": (0.90, 0.95, 0.80), "STILL_OPEN": (0.99, 0.90, 0.75),
                "BLOCKED_BY_DESIGN_DECISION": (0.96, 0.80, 0.80), "NOT_APPLICABLE": (0.88, 0.88, 0.88)}


def jl(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ computed facts
def programme_facts() -> dict:
    out = {}
    for f in ["3F", "4F", "5F", "6F", "7F", "8F", "9F", "10F", "11F", "12F", "13F", "14F", "15F"]:
        m = jl(ROOT / "outputs" / "T14T" / f / ("T14T_%s_plan_metadata.json" % f))
        rooms = m["design_proposed"]["rooms"]
        out[f] = {"halls_m2": [round(r["area_m2"], 1) for r in rooms if r["kind"] == "hall"], "units": sorted(r["area_m2"] for r in rooms if r["kind"] == "unit"),
                  "support_n": sum(1 for r in rooms if r["kind"] == "support"), "support_m2": round(sum(r["area_m2"] for r in rooms if r["kind"] == "support"), 1),
                  "by_program_m2": m["design_proposed"]["room_area_by_program_m2"]}
    retail = [out[f]["units"] for f in ["3F", "4F", "5F", "6F", "7F", "8F", "9F"]]
    cnt = Counter(a for u in retail for a in set(u))
    out["_repetition_3F_9F"] = {"units": sum(len(u) for u in retail), "distinct_areas": len(cnt), "areas_on_5_or_more_floors": sorted(a for a, n in cnt.items() if n >= 5),
                                "areas_on_3_or_more_floors": sorted(a for a, n in cnt.items() if n >= 3)}
    return out


PROG_KO = {"retail": "판매", "fnb": "F&B", "culture": "문화", "garden": "정원", "restroom": "화장실"}


def prog_text(d: dict) -> str:
    return " · ".join("%s %.1f" % (PROG_KO.get(k, k), v) for k, v in d.items())


def p4_summary(pdf: dict) -> dict:
    bad = [(r["floor"], r["checks"]["P4_main_room_areas_printed"]["detail"]) for r in pdf["floors"] if not r["checks"]["P4_main_room_areas_printed"]["pass"]]
    return {"floors_failing": len(bad), "floors": [b[0] for b in bad]}


# ------------------------------------------------------------------ markdown
def md_reconciliation(items) -> str:
    c = Counter(i["status"] for i in items["items"])
    lines = ["# 01 Reconciliation (documented issues)", "", "**%s**" % items["basis"], "", "| status | count |", "|---|---|"]
    lines += ["| %s | %d |" % (s, c.get(s, 0)) for s in items["status_values"]]
    lines += ["", "| id | group | floors | status | issue | evidence | note |", "|---|---|---|---|---|---|---|"]
    for i in items["items"]:
        lines.append("| %s | %s | %s | `%s` | %s | %s | %s |" % (i["id"], i["group"], i["floors"], i["status"], i["title_ko"], "<br>".join("`%s`" % e for e in i["evidence"]) or "-", i["note_ko"]))
    return "\n".join(lines) + "\n"


def md_alternatives(meas, prog, pdf) -> str:
    d01, d02, d03 = meas["d01"], meas["d02"], meas["d03"]
    where = Counter(r["end_lies_in"] for r in d01)
    cap = [r for r in d01 if r["end_lies_in"] != "core"]                   # B1->1F starts inside a core: options A and C do not apply to it
    deck = [r["altA_new_deck_m2"] for r in cap]
    pct = [r["altA_deck_pct_of_opening"] for r in cap if r["altA_deck_pct_of_opening"] != ""]
    shift = [r["altC_shift_outward_to_slab_m"] for r in cap if r["altC_shift_outward_to_slab_m"] != ""]
    comb = sorted({(r["floor"], r["altA_floor_combined_deck_m2"]) for r in cap})
    L = ["# 02 P0 alternatives with geometry provenance", "",
         "All numbers are %s. Source: hash-pinned slices (`data/t14s/source_slices`, unchanged, verified %s). Parameters: landing depth %.1f m and entry apron %.1f x %.1f m are the C-T14T builder values, not code requirements; deck width = escalator width (3.6 m) from the model."
         % (meas["method"], meas["source_geometry"]["ok"], meas["parameters"]["landing_depth_m"], 2.6, 2.6), "",
         "## D-01 escalator landings (25)", "",
         "End position: %s." % ", ".join("%s %d" % (k, v) for k, v in sorted(where.items())), "",
         "| Option | What changes | Measured | Needs approval | Not measured |", "|---|---|---|---|---|",
         "| A local landing decks / bridges (study) | proposed new deck in the capsule opening or notch, verified slab and opening untouched in the model | new deck per landing %.1f-%.1f m2, %.1f-%.1f %% of the 156 m2 opening, no column within any deck footprint, per-floor combined %.1f-%.1f m2 | yes (structure, opening, egress) | deck thickness against sections, truss/pit interplay, continuous clear width, fire/egress |"
         % (min(deck), max(deck), min(pct), max(pct), min(c for _, c in comb), max(c for _, c in comb)),
         "| B no-escalator operation | escalators stay as void and visual; vertical use by cores and lifts | verified cores connected on every floor except D-02 floors; lift lobbies T3/T4 connected; EV1/EV2/PL not assessed | yes (programme and thesis) | lift and stair capacity, evacuation |",
         "| C relocate escalator geometry | move the escalator end onto verified slab | outward translation needed %.1f-%.1f m, the same order as the escalator length (%.1f-%.1f m) | yes (verified model change) | structural and programme consequences |" % (min(shift), max(shift), min(r["escalator_length_m"] for r in cap), max(r["escalator_length_m"] for r in cap)), "",
         "The 24 capsule landings (opening or notch) are measured above; B1 to 1F starts inside core D, so A and C do not apply to it (a core would have to move). Per landing rows: `measurements/d01_escalator_landings.csv`. Section evidence for these options is UNVERIFIED (the V4.2 section sheets were not compared; WP0).", "",
         "## D-02 cores without slab (3)", "",
         "| Core | Core area on slab | Nearest verified slab | Apron 2.6 m on slab (S/N/W/E) |", "|---|---|---|---|"]
    for r in d02:
        a = r["apron_by_side"]
        L.append("| %s | %.1f m2 | %.1f m | %s |" % (r["id"], r["core_on_slab_m2"], r["nearest_slab_m"], " / ".join("%.0f %%" % a[s]["on_slab_pct"] for s in "SNWE")))
    L += ["", "- Option 1 keep as pass-through shaft (current drawing, marked not enterable): no geometry change; needs an egress and exit-capacity assessment by the user's engineers.",
          "- Option 2 connect the core to slab: the nearest verified slab is 17.0 m away, so this is not a local apron but a deck or bridge of about 17 m: a structural study, not a drawing edit.", "",
          "## D-03 lift entry rotations (15)", "", "| Floor | Tube | Proposed turn | Apron on slab unrotated -> proposed | Blocked unrotated by |", "|---|---|---|---|---|"]
    for r in d03:
        L.append("| %s | %s | %+.0f deg | %.1f %% -> %.1f %% | %s |" % (r["floor"], r["tube"], r["proposed_turn_deg"], r["unrotated_apron_on_slab_pct"], r["proposed_apron_on_slab_pct"], ", ".join(r["unrotated_blocked_by"]) or "-"))
    s12 = [r for r in d03 if r["floor"] == "12F"][0]["sweep"]
    L += ["", "- Every unrotated apron overlaps the capsule tube (capW for T3, capE for T4). 6F T4 is 100 %% on slab but still touches capE.",
          "- 12F T4: -45 deg leaves the apron %.1f %% on slab (the 12F void edge), -75 deg %.1f %%; that is why 12F differs." % (s12["-45"]["on_slab_pct"], s12["-75"]["on_slab_pct"]),
          "- Keeping the 1F orientation (0 deg) is not usable in any of the 15 cases. Door clear opening, lobby threshold and tube interior conflicts are NOT measured (WP0).", "",
          "## Programme measurements behind R-10 to R-16", "", "| Floor | Hall m2 | Units (n, largest m2) | Support rooms (n, m2) | Programme m2 |", "|---|---|---|---|---|"]
    for f in ["10F", "11F", "12F", "13F", "14F", "6F", "15F"]:
        p = prog[f]
        L.append("| %s | %s | %d, %.1f | %d, %.1f | %s |" % (f, ", ".join("%.1f" % h for h in p["halls_m2"]), len(p["units"]), max(p["units"] or [0]), p["support_n"], p["support_m2"], prog_text(p["by_program_m2"])))
    rep = prog["_repetition_3F_9F"]
    L += ["", "3F-9F: %d units, %d distinct unit areas; areas present on 5 or more of the 7 floors: %s." % (rep["units"], rep["distinct_areas"], rep["areas_on_5_or_more_floors"]),
          "", "## Printed-area finding (PDF)", "", "Support rooms and restrooms without a printed area: %d (all of them). Floors where a unit, hall or garden area is not printed: %d (%s)." % (pdf["summary"]["F4_area_not_printed"], p4_summary(pdf)["floors_failing"], ", ".join(p4_summary(pdf)["floors"]))]
    return "\n".join(L) + "\n"


def md_packages(wp) -> str:
    L = ["# 03 Work packages", "", wp["note"], ""]
    for p in wp["packages"]:
        L += ["## %s (%s) %s: %s" % (p["id"], p["priority"], p["state"], p["title_ko"]), "", "- Floors: %s" % p["floors"], "- Source files: %s" % "; ".join("`%s`" % s for s in p["source_files"]),
              "- Existing failure: %s" % p["failure_ko"], "- Evidence: %s" % "; ".join("`%s`" % e for e in p["evidence"]), "- Correction: %s" % p["correction_ko"], "- Dependencies: %s" % "; ".join(p["depends_on"]),
              "- Verification: %s" % p["verification"], "- Acceptance: %s" % p["acceptance"], "- Approval: %s" % p["approval"], ""]
    return "\n".join(L)


def md_decisions(dec) -> str:
    return "\n".join(["# 04 Decisions and inputs needed from the user", ""] + ["- **%s** (%s): %s _needed for %s_" % (d["id"], d["ref"], d["ask_ko"], d["needed_for"]) for d in dec["decisions"]]) + "\n"


def md_state(facts) -> str:
    L = ["# 00 State and integrity", "", "Pinned audited commit: `%s` (PR #30). This branch is stacked on PR #31 (`%s`)." % (BASE_SHA, facts["base_head"]), "",
         "## Audit files named in the handoff", "", "| Path | Found |", "|---|---|"]
    L += ["| `%s` | %s |" % (k, v) for k, v in facts["audit_files"].items()]
    L += ["", "Checked: all remote branches (`git ls-tree`), every local worktree under the project folder, Downloads and Desktop folders (names `independent_audit`, `register`, `Independent_Review_A3`). The two PR #30 review comments say the files were delivered to the user in the ChatGPT conversation and were not added to GitHub.", "",
          "C-T14U: no branch, commit message, PR or local worktree/folder named T14U exists. Duplicate work could not be checked.", "",
          "## Captured source text", "", "`source/pr30_review_comments_20261123.md` (the two independent-review comments, SHA256 `%s`)." % facts["comments_sha"], "",
          "## Re-run checks (this session)", "", "| Check | Result |", "|---|---|"]
    L += ["| %s | %s |" % (k, v) for k, v in facts["checks"].items()]
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ PDF
class Pdf:
    def __init__(self, footer):
        self.doc = fitz.open()
        self.f = fitz.Font(fontfile=str(FONT))
        self.fb = fitz.Font(fontfile=str(FONT_B))
        self.footer = footer
        self.page = None
        self.y = 0.0
        self.n = 0

    def tl(self, t, size, bold=False):
        return (self.fb if bold else self.f).text_length(t, fontsize=size)

    def new(self, title):
        self.page = self.doc.new_page(width=A3[0], height=A3[1])
        self.page.insert_font(fontname="mg", fontfile=str(FONT))
        self.page.insert_font(fontname="mgb", fontfile=str(FONT_B))
        self.n += 1
        self.page.draw_rect(fitz.Rect(0, 0, A3[0], 34), color=None, fill=(0.12, 0.16, 0.22))
        self.page.insert_text((M, 23), title, fontsize=15, fontname="mgb", color=(1, 1, 1))
        self.page.insert_text((M, A3[1] - 16), self.footer, fontsize=8.5, fontname="mg", color=(0.35, 0.35, 0.35))
        self.page.insert_text((A3[0] - M - 40, A3[1] - 16), "%d" % self.n, fontsize=9, fontname="mgb", color=(0.2, 0.2, 0.2))
        self.y = 54.0

    def wrap(self, text, size, width, bold=False):
        out = []
        for para in str(text).split("\n"):
            line = ""
            for word in para.split(" "):
                cand = (line + " " + word).strip()
                if self.tl(cand, size, bold) <= width:
                    line = cand
                    continue
                if line:
                    out.append(line)
                line = ""
                for ch in word:
                    if self.tl(line + ch, size, bold) > width and line:
                        out.append(line)
                        line = ch
                    else:
                        line += ch
            out.append(line)
        return out or [""]

    def text(self, t, size=10.5, bold=False, width=None, color=(0.1, 0.1, 0.1), gap=3.0, x=None):
        width = width or (A3[0] - 2 * M)
        x = M if x is None else x
        for ln in self.wrap(t, size, width, bold):
            if self.y + size * 1.3 > A3[1] - 30:
                self.new("(계속)")
            self.page.insert_text((x, self.y + size), ln, fontsize=size, fontname="mgb" if bold else "mg", color=color)
            self.y += size * 1.3
        self.y += gap

    def table(self, header, rows, widths, size=8.6, status_col=None):
        total = sum(widths)
        widths = [w * (A3[0] - 2 * M) / total for w in widths]
        pad = 3.0

        def row(cells, head=False):
            wr = [self.wrap(c, size, w - 2 * pad, head) for c, w in zip(cells, widths)]
            h = max(len(x) for x in wr) * size * 1.25 + 2 * pad
            if self.y + h > A3[1] - 30:
                self.new("(계속)")
                row(header, True)
            x = M
            for i, (lines, w) in enumerate(zip(wr, widths)):
                fill = (0.82, 0.86, 0.92) if head else (STATUS_COLOR.get(cells[i]) if status_col == i else None)
                r = fitz.Rect(x, self.y, x + w, self.y + h)
                self.page.draw_rect(r, color=(0.6, 0.6, 0.6), fill=fill, width=0.4)
                for k, ln in enumerate(lines):
                    self.page.insert_text((x + pad, self.y + pad + size * (k + 1) * 1.15), ln, fontsize=size, fontname="mgb" if head else "mg", color=(0.05, 0.05, 0.05))
                x += w
            self.y += h
        row(header, True)
        for r in rows:
            row([str(c) for c in r])
        self.y += 8

    def save(self, path):
        self.doc.save(str(path), garbage=4, deflate=True)


def build_pdf(items, meas, prog, pdf_ev, wp, dec, facts, out_pdf):
    P = Pdf("C-T14T 독립 감사 정합 · PROPOSED_DESIGN · NOT APPROVED · NOT FROZEN · 기준 PR #30 %s" % BASE_SHA[:10])
    c = Counter(i["status"] for i in items["items"])
    P.new("C-T14T 독립 감사 정합·작업 패키지 (한글 A3)")
    P.text("상태: AUDIT_REGISTER_47_UNAVAILABLE · 건축 승인 아님 · 검증 지오메트리 수정 없음", 13, True, color=(0.6, 0.1, 0.1))
    P.text("요약", 12, True)
    P.text("• 핸드오프가 지정한 감사 파일(47개 항목 대장 CSV/JSON, 10쪽 A3 PDF, 영문 브리프)은 GitHub 어느 브랜치에도, 로컬 어느 폴더에도 없었다. PR #30 검토 코멘트는 파일이 ChatGPT 대화에만 전달되었다고 적고 있다. 따라서 47개 항목 대조(Stage A)는 완료하지 못했다.\n"
           "• 대신 PR #30의 독립 검토 코멘트 두 건에 적힌 문제 %d개(R-01~R-%02d)를 현재 저장소 상태와 대조했다: %s.\n"
           "• C-T14U 구현은 GitHub(PR·브랜치·커밋)와 로컬 어디에도 없어 중복 여부를 확인하지 못했다.\n"
           "• 고정 슬라이스에서 D-01 랜딩 25곳, D-02 코어 3곳, D-03 회전 15건을 실측해 대안 A/B/C의 규모를 숫자로 제시했다(설계 유효성·법규 적합 아님).\n"
           "• 검증기 재실행: 기술 PASS 16/16, 단 동선 완결 2/16(B2·3F)이며 감사 도구는 COMPLETE 0층으로 판정. A1/A3 PDF 정합 검사: 쪽수·크기·벡터·층·축척·레벨 16/16 통과, 면적 인쇄는 12개 층 불합격, 지원실·화장실 161개 면적 미인쇄.\n"
           "• 도면·모델은 하나도 바꾸지 않았다. 승인 의존 항목은 대안과 결정 목록으로 남겼다." % (len(items["items"]), len(items["items"]), ", ".join("%s %d" % (k, v) for k, v in c.items())), 10.5)
    P.text("확인된 상태", 12, True)
    P.table(["항목", "결과"], [[k, v] for k, v in facts["checks"].items()] + [["감사 파일 위치 확인", "; ".join("%s: %s" % (k.split('/')[-1], v) for k, v in facts["audit_files"].items())]], [1.3, 4.7])
    P.new("대조표 R-01 ~ R-%02d (PR #30 검토 코멘트의 문제 항목)" % len(items["items"]))
    P.text(items["basis"], 9, False, color=(0.4, 0.1, 0.1))
    P.table(["ID", "구분", "층", "상태", "문제", "비고(실측·근거)"], [[i["id"], i["group"], i["floors"], i["status"], i["title_ko"], i["note_ko"]] for i in items["items"]], [0.45, 0.4, 0.8, 1.35, 3.0, 4.6], size=8.3, status_col=3)
    P.new("P0 대안 1/2 — D-01 에스컬레이터 랜딩 25곳 실측 (고정 슬라이스, 계산만)")
    P.text("랜딩 깊이 2.6 m·데크 폭 3.6 m는 C-T14T 빌더 값이며 법규값이 아님. 대안 A=국소 데크·브리지 연구, B=에스컬레이터 비운영, C=에스컬레이터 이동. 구조·피난 검토 전에는 어떤 대안도 모델에 반영하지 않는다.", 9.5)
    P.table(["층", "에스컬레이터", "구분", "끝점 위치", "바닥판까지 축 방향 m", "랜딩 사각형 보행 m²", "A: 신설 데크 m²", "A: 개구 대비 %", "C: 필요 이동 m"],
            [[r["floor"], r["escalator"], r["role"], r["end_lies_in"], r["gap_to_walkable_slab_along_axis_m"], r["landing_rect_walkable_m2"], r["altA_new_deck_m2"], r["altA_deck_pct_of_opening"], r["altC_shift_outward_to_slab_m"]] for r in meas["d01"]],
            [0.4, 0.8, 0.6, 1.5, 1.0, 1.0, 0.9, 0.9, 0.9], size=8.2)
    d01 = [r for r in meas["d01"] if r["end_lies_in"] != "core"]            # B1->1F starts inside a core: A and C do not apply
    deck = [r["altA_new_deck_m2"] for r in d01]
    shift = [r["altC_shift_outward_to_slab_m"] for r in d01 if r["altC_shift_outward_to_slab_m"] != ""]
    P.text("B1→1F는 코어 외곽 안에서 시작하므로 A·C가 해당하지 않는다(코어를 옮겨야 함). 나머지 24곳: A: 랜딩당 신설 데크 %.1f~%.1f m²(개구 156 m²의 6~12 %%), 데크 범위 안 기둥 0개, 층별 합계 18.6~37.9 m². B: 코어·승강기 로비 T3/T4로만 수직 이동(EV1·EV2·PL 미평가, 수용력 미검토). C: 랜딩이 바닥판 위에 놓이려면 %.1f~%.1f m 이동(에스컬레이터 길이 %.1f~%.1f m와 같은 규모)이라 검증 모델의 재작성에 가깝다. 단면 근거는 UNVERIFIED(V4.2 단면 시트 미대조)." % (min(deck), max(deck), min(shift), max(shift), min(r["escalator_length_m"] for r in d01), max(r["escalator_length_m"] for r in d01)), 10)
    P.new("P0 대안 2/2 — D-02 코어 3곳과 D-03 승강기 출입구 회전 15건 실측")
    P.table(["코어", "코어 면적 중 바닥판 m²", "가장 가까운 검증 바닥판 m", "전실 2.6 m 바닥판 비율 S/N/W/E"],
            [[r["id"], "%.1f" % r["core_on_slab_m2"], "%.1f" % r["nearest_slab_m"], " / ".join("%.0f%%" % r["apron_by_side"][s]["on_slab_pct"] for s in "SNWE")] for r in meas["d02"]], [1.4, 1.2, 1.4, 2.0], size=9)
    P.text("D-02 옵션 1: 통과 전용 샤프트 유지(현재, 출입 불가 표기) — 지오메트리 변경 없음, 피난 수용력 검토 필요. 옵션 2: 가장 가까운 검증 바닥판이 17.0 m 떨어져 있어 국소 전실이 아니라 약 17 m의 데크·브리지 구조 연구가 된다.", 10)
    P.table(["층", "튜브", "제안 회전", "회전 전 전실 바닥판 %", "제안 전실 바닥판 %", "회전 전 막는 것"],
            [[r["floor"], r["tube"], "%+.0f°" % r["proposed_turn_deg"], "%.1f" % r["unrotated_apron_on_slab_pct"], "%.1f" % r["proposed_apron_on_slab_pct"], ", ".join(r["unrotated_blocked_by"]) or "-"] for r in meas["d03"]], [0.5, 0.5, 0.8, 1.4, 1.4, 1.6], size=8.6)
    s12 = [r for r in meas["d03"] if r["floor"] == "12F"][0]["sweep"]
    P.text("15건 모두 회전 전 전실이 캡슐 튜브와 겹친다(T3=capW, T4=capE). 6F T4는 바닥판 위 100 %%지만 capE와 접한다. 12F T4는 -45°에서 전실이 바닥판 위 %.1f %%(12F 보이드 가장자리)라 -75°(%.1f %%)가 선택됐다. 1F 방향 유지(0°)는 15건 모두 사용 불가. 문 유효 개구·문턱·튜브 내부 충돌은 미측정." % (s12["-45"]["on_slab_pct"], s12["-75"]["on_slab_pct"]), 10)
    P.new("프로그램·인쇄 면적 실측 (R-10~R-18)")
    P.table(["층", "홀 m²", "실 수·최대 m²", "지원실 수·합 m²", "프로그램별 m²"],
            [[f, ", ".join("%.1f" % h for h in prog[f]["halls_m2"]), "%d, %.1f" % (len(prog[f]["units"]), max(prog[f]["units"] or [0])), "%d, %.1f" % (prog[f]["support_n"], prog[f]["support_m2"]), prog_text(prog[f]["by_program_m2"])] for f in ["6F", "10F", "11F", "12F", "13F", "14F", "15F"]], [0.5, 1.6, 1.0, 1.1, 3.6], size=9)
    rep = prog["_repetition_3F_9F"]
    P.text("3F~9F: 점포 %d개, 서로 다른 면적 %d종, 7개 층 중 5개 이상에 나타나는 면적 %s m². 10F 지원실 합 %.1f m²는 F&B 프로그램 %.1f m²의 %.1f %%(주방 요건 판정 아님)." % (rep["units"], rep["distinct_areas"], rep["areas_on_5_or_more_floors"], prog["10F"]["support_m2"], prog["10F"]["by_program_m2"].get("fnb", 0), 100 * prog["10F"]["support_m2"] / max(prog["10F"]["by_program_m2"].get("fnb", 1), 1)), 10)
    pe = p4_summary(pdf_ev)
    P.text("A1/A3 PDF 정합 검사(결정적, 육안 검토 아님): P1 쪽수·크기, P2 벡터, P3 층·축척·레벨, P5 식별자 없음, P6 레벨 스택, P7 표제 일치는 모두 16/16(또는 층 간) 통과. P4 단위·홀·정원 면적 인쇄는 %d개 층(%s) 불합격. F4 지원실·화장실 %d개는 면적이 인쇄되지 않음 → 실·면적 일람표 필요." % (pe["floors_failing"], ", ".join(pe["floors"]), pdf_ev["summary"]["F4_area_not_printed"]), 10)
    P.new("작업 패키지 WP0~WP4")
    P.table(["ID", "우선", "상태", "제목·층", "기존 실패와 근거", "제안 보정", "선행·검증", "승인"],
            [[p["id"], p["priority"], p["state"], p["title_ko"] + " / " + p["floors"], p["failure_ko"] + " 근거: " + "; ".join(p["evidence"]), p["correction_ko"], "선행: " + "; ".join(p["depends_on"]) + " 검증: " + p["verification"] + " 합격: " + p["acceptance"], p["approval"]] for p in wp["packages"]],
            [0.4, 0.4, 1.3, 1.4, 2.0, 2.0, 2.6, 1.0], size=7.8)
    P.new("사용자 승인·입력이 필요한 결정 목록과 한계")
    P.table(["ID", "대상", "요청", "필요한 곳"], [[d["id"], d["ref"], d["ask_ko"], d["needed_for"]] for d in dec["decisions"]], [0.5, 1.2, 6.0, 1.3], size=9)
    P.text("NOT_RUN / 한계", 12, True)
    P.text("• 47개 항목 대장 대조, 단면·입면 대조(R-19), 원본 GLB 대비 검증(R-25), 법규 검토(R-27), A1/A3 32쪽 육안 검토는 수행하지 않았다.\n"
           "• 위 숫자는 고정 슬라이스에서의 기하 계산이며, 대안이 유효하다거나 법규에 적합하다는 뜻이 아니다. 어떤 대안도 승인되지 않았고 모델은 수정되지 않았다.\n"
           "• 재실행 검사는 제작 세션(Claude Code)이 수행했고 검토자(ChatGPT)의 독립 재실행이 아니다.", 10)
    P.save(out_pdf)
    return P.n


def main() -> int:
    items, wp, dec = jl(D / "data" / "reconciliation_items.json"), jl(D / "data" / "work_packages.json"), jl(D / "data" / "decisions.json")
    meas = jl(D / "measurements" / "measurements.json")
    ev = D / "evidence"
    pdf_ev, val, gm, gs, cir, pk = (jl(ev / "pdf_consistency.json"), jl(ev / "validator_rerun_report.json"), jl(ev / "guard_manifests.json"), jl(ev / "guard_sources.json"),
                                    jl(ev / "circulation_audit.json"), jl(ev / "review_packet_local_check.json"))
    prog = programme_facts()
    verdicts = Counter(f["verdict"] for f in cir["floors"])
    facts = {"base_head": "64f811484c18abb3de0b7629f87548c298cbfda0", "comments_sha": sha(D / "source" / "pr30_review_comments_20261123.md"),
             "audit_files": {"docs/t14t_corrections/independent_audit_20261123/ (Korean A3 PDF)": "NOT FOUND", "…/ 47-item register CSV": "NOT FOUND", "…/ 47-item register JSON": "NOT FOUND", "…/ English Claude Code brief": "NOT FOUND"},
             "checks": {"검증기 재실행 (validate_t14t, 16층)": "기술 PASS %d/%d, 원본 지오메트리 불변=%s, 동선 완결 %d층, 미결 %d건" % (val["summary"]["floors_technical_pass"], val["summary"]["floors_tested"], val["summary"]["source_geometry_unchanged"], len(val["summary"]["floors_circulation_complete"]), val["summary"]["open_circulation_items"]),
                        "동선 감사 도구(PR #31)": ", ".join("%s %d" % kv for kv in sorted(verdicts.items())),
                        "고정 슬라이스·매니페스트 재해시": "슬라이스 %d/%d 일치, 매니페스트 파일 %d개 일치" % (gs["original_checked"], gs["files"], gm["files_checked"]),
                        "검수 패킷 로컬 검증": "%d자산 %d타일, %s" % (pk["assets"], pk["tiles"], pk["t14r_verify"]),
                        "A1/A3 PDF 정합 검사": "층별 전체 통과 %d/%d, 층 간 일치=%s, 면적 미인쇄 지원실·화장실 %d개" % (pdf_ev["summary"]["floors_all_pass"], pdf_ev["summary"]["floors"], pdf_ev["summary"]["cross_floor_pass"], pdf_ev["summary"]["F4_area_not_printed"])}}
    (D / "00_STATE_AND_INTEGRITY.md").write_text(md_state(facts), encoding="utf-8")
    (D / "01_RECONCILIATION.md").write_text(md_reconciliation(items), encoding="utf-8")
    with (D / "01_RECONCILIATION.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "group", "floors", "status", "issue_ko", "evidence", "note_ko"])
        for i in items["items"]:
            w.writerow([i["id"], i["group"], i["floors"], i["status"], i["title_ko"], "; ".join(i["evidence"]), i["note_ko"]])
    (D / "02_P0_ALTERNATIVES.md").write_text(md_alternatives(meas, prog, pdf_ev), encoding="utf-8")
    (D / "03_WORK_PACKAGES.md").write_text(md_packages(wp), encoding="utf-8")
    (D / "04_DECISIONS_FOR_USER.md").write_text(md_decisions(dec), encoding="utf-8")
    (D / "05_PROGRAMME_MEASUREMENTS.json").write_text(json.dumps(prog, ensure_ascii=False, indent=1), encoding="utf-8")
    pdf_path = D / "T14T_audit_reconciliation_A3_KO.pdf"
    n = build_pdf(items, meas, prog, pdf_ev, wp, dec, facts, pdf_path)
    prev = D / "preview"
    prev.mkdir(exist_ok=True)
    with fitz.open(str(pdf_path)) as doc:
        for i, pg in enumerate(doc, 1):
            pg.get_pixmap(dpi=80).save(str(prev / ("page_%02d.png" % i)))
    files = sorted(p for p in D.rglob("*") if p.is_file() and p.name != "SHA256_MANIFEST.txt")
    (D / "SHA256_MANIFEST.txt").write_text("\n".join("%s  %s" % (sha(p), p.relative_to(D).as_posix()) for p in files) + "\n", encoding="utf-8")
    print("pages:", n, "| files hashed:", len(files), "|", pdf_path.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
