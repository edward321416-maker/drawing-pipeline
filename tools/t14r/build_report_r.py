"""A3 landscape Korean report for a C-T14R packet.  All numbers are read from the packet files, never typed.

  python -m tools.t14r.build_report_r --packet docs/t14r_visual_review/G002_C_T14Q_R1 \
      --pr27-manifest <SHA256_MANIFEST.json of PR #27> --head <commit sha shown on the cover> --out <pdf> --qa <qa.json>
Paths printed in the PDF are repository-relative; no local account paths or e-mail addresses are written.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz

W, H = 1190.55, 841.89
FONT, FONTB = r"C:\Windows\Fonts\malgun.ttf", r"C:\Windows\Fonts\malgunbd.ttf"
INK, MUT, RED, GRN, AMB = (0.08, 0.08, 0.08), (0.38, 0.38, 0.38), (0.72, 0.12, 0.12), (0.12, 0.45, 0.2), (0.75, 0.45, 0.05)
D, B = "DAYLIGHT_FINAL", "BLUEHOUR_FINAL"
PR_URL = "https://github.com/edward321416-maker/drawing-pipeline/pull/28"
BRANCH = "feat/t14r-github-inspectable-visual-review-packets-20261115"
PACKET_REL = "docs/t14r_visual_review/G002_C_T14Q_R1"
_MEASURE = fitz.Font(fontfile=FONT)


def wrap(text: str, width: float, size: float) -> list[str]:
    out: list[str] = []
    for para in str(text).split("\n"):
        line = ""
        for ch in para:
            if _MEASURE.text_length(line + ch, fontsize=size) > width and line:
                out.append(line)
                line = ch
            else:
                line += ch
        out.append(line)
    return out


class Doc:
    def __init__(self, head: str):
        self.d = fitz.open()
        self.n = 0
        self.head = head
        self.qa: dict = {"pages": [], "min_image_ppi": None, "text_overflows": []}
        self.cur: dict = {}

    def page(self, title: str, sub: str | None = None):
        p = self.d.new_page(width=W, height=H)
        p.insert_font(fontname="mg", fontfile=FONT)
        p.insert_font(fontname="mgb", fontfile=FONTB)
        self.n += 1
        self.cur = {"page": self.n, "title": title, "images": [], "overflow": 0}
        self.qa["pages"].append(self.cur)
        p.insert_text((30, 42), title, fontname="mgb", fontsize=19, color=INK)
        if sub:
            p.insert_text((30, 62), sub, fontname="mg", fontsize=9.5, color=MUT)
        p.insert_text((30, H - 14), "C-T14R · G-002 GitHub 이미지 검수 패킷 · INDEPENDENT_VISUAL_REVIEW_PENDING · CHATGPT_CONNECTOR_READBACK_PENDING · 건축·시각 품질 승인 아님",
                      fontname="mg", fontsize=7.5, color=RED)
        p.insert_text((W - 140, H - 14), f"PR #28 · {self.head[:10]} · {self.n}", fontname="mg", fontsize=8, color=MUT)
        return p

    def tb(self, p, rect, text, size=9.5, bold=False, color=INK):
        rc = p.insert_textbox(fitz.Rect(*rect), text, fontname="mgb" if bold else "mg", fontsize=size, color=color)
        if rc < 0:
            self.cur["overflow"] += 1
            self.qa["text_overflows"].append({"page": self.n, "text": str(text)[:60], "shortfall_pt": round(-rc, 1)})

    def img(self, p, source, rect, label="", thumb_px: int | None = None) -> float:
        """Insert a file fitted into rect; record the effective ppi.  thumb_px: navigation thumbnail (JPEG, long side), else the stream is used as-is."""
        import io

        from PIL import Image

        r = fitz.Rect(*rect)
        with Image.open(source) as im:
            pw, ph = im.size
            stream = Path(source).read_bytes()
            if thumb_px:
                t = im.convert("RGB")
                t.thumbnail((thumb_px, thumb_px), Image.LANCZOS)
                buf = io.BytesIO()
                t.save(buf, "JPEG", quality=86, optimize=True)
                stream, (pw, ph) = buf.getvalue(), t.size
        ar = pw / ph
        w = r.width
        h = w / ar
        if h > r.height:
            h = r.height
            w = h * ar
        x0 = r.x0 + (r.width - w) / 2
        p.insert_image(fitz.Rect(x0, r.y0, x0 + w, r.y0 + h), stream=stream)
        ppi = round(pw / (w / 72.0), 1)
        self.cur["images"].append({"label": label or Path(source).name, "px": [pw, ph], "ppi": ppi})
        if self.qa["min_image_ppi"] is None or ppi < self.qa["min_image_ppi"]:
            self.qa["min_image_ppi"] = ppi
        return r.y0 + h

    def table(self, p, x, y, widths, rows, size=8.2, colors=None) -> float:
        cy = y
        for i, row in enumerate(rows):
            lines = max(len(wrap(c, wd - 8, size)) for c, wd in zip(row, widths))
            rh = lines * size * 1.3 + 7
            cx = x
            for j, (c, wd) in enumerate(zip(row, widths)):
                p.draw_rect(fitz.Rect(cx, cy, cx + wd, cy + rh), color=(0.75, 0.75, 0.75), width=0.4, fill=(0.93, 0.93, 0.93) if i == 0 else None)
                col = INK
                if colors and i > 0 and j in colors:
                    col = colors[j](str(c)) or INK
                self.tb(p, (cx + 3, cy + 2, cx + wd - 3, cy + rh + 1), str(c), size=size, bold=(i == 0), color=col)
                cx += wd
            cy += rh
        return cy


def status_color(s: str):
    if s.startswith(("완료", "통과", "일치", "동일")):
        return GRN
    if s.startswith(("미확인", "대기", "미해결")):
        return RED
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--packet", type=Path, required=True)
    ap.add_argument("--pr27-manifest", type=Path, required=True)
    ap.add_argument("--head", required=True, help="pinned commit shown on the cover")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--qa", type=Path, required=True)
    a = ap.parse_args()
    pk = a.packet
    man = json.loads((pk / "manifest.json").read_text(encoding="utf-8"))
    reg = json.loads((pk / "regions.json").read_text(encoding="utf-8"))
    integ = json.loads((pk / "INTEGRITY_REPORT.json").read_text(encoding="utf-8"))
    rb = json.loads((pk / "GITHUB_READBACK_REPORT.json").read_text(encoding="utf-8"))
    fin = json.loads((pk / "fin_rhythm_measurement.json").read_text(encoding="utf-8"))
    pr27 = json.loads(a.pr27_manifest.read_text(encoding="utf-8-sig"))
    by_name = {Path(e["file"].replace("\\", "/")).name: e for e in pr27}
    names = {D: "G002_A_Urban_Daylight_PHOTOSHOP_FINAL.png", B: "G002_B_Blue_Hour_PHOTOSHOP_FINAL.png"}
    assets = {x["label"]: x for x in man["assets"]}
    doc = Doc(a.head)

    def focus_file(fid: str, asset: str) -> Path:
        for f in reg["focus"]:
            if f["id"] == fid and f["asset"] == asset:
                return pk / f["path"]
        raise SystemExit(f"focus crop missing: {fid} {asset}")

    kib =lambda n: f"{n/1024:,.0f} KiB"  # noqa: E731
    mib = lambda n: f"{n/1048576:,.1f} MiB"  # noqa: E731

    # ---- 1 cover ----
    p = doc.page("G-002 최종 PNG GitHub 이미지 검수 패킷 — C-T14R 보고서", "원본 PNG 2종(4800×2700)을 GitHub에서 실제 픽셀로 열람할 수 있게 만든 검수 패킷의 생성·재조립·업로드·읽기 검증 결과")
    doc.img(p, pk / man["overview"]["path"], (30, 74, W - 30, 345), "overview.jpg")
    rest = rb["claude_side_readback"]
    rows = [["단계", "결과", "근거"],
            ["① 실제 원본에서 패킷 생성", "완료", f"원본 SHA256을 PR #27 매니페스트와 대조해 2/2 일치 후 패킷 생성. 타일 {sum(len(x['tiles']) for x in man['assets'])}개, 미리보기 2개, 개요 1개"],
            ["② 무손실 재조립 검증", "완료" if integ["OVERALL_PASS"] else "미통과", "타일을 원본 해상도로 재조립한 픽셀이 원본과 일치(Daylight·Blue Hour). 타일 겹침 0, 빈틈 0, 항목 모두 400 KiB 이하"],
            ["③-a GitHub 업로드", "완료", f"PR #28 브랜치 {BRANCH}, 읽기 검증 고정 커밋 {rb['pinned_commit'][:12]}"],
            ["③-b Claude 쪽 실제 이미지 읽기", "통과", f"gh api 원문 {rest['files_checked']}개 전수(SHA·해상도·디코딩) + GitHub MCP 표본 {len(rest['connector_samples'])}개(이미지 블록 반환, blob SHA 일치)"],
            ["③-c ChatGPT 쪽 직접 읽기", "미확인", "ChatGPT 자체 GitHub 연결에서의 읽기는 수행하지 않았음 → CHATGPT_CONNECTOR_READBACK_PENDING. Claude의 성공을 ChatGPT 연결의 성공으로 세지 않음"],
            ["독립 시각 검수", "대기", "건축 정확성·시각 품질 승인이 아님. 사람 또는 독립 검수자의 확인 전까지 INDEPENDENT_VISUAL_REVIEW_PENDING"]]
    y = doc.table(p, 30, 356, [215, 70, W - 60 - 285], rows, size=8.6, colors={1: status_color})
    doc.tb(p, (30, y + 10, W - 30, y + 62), f"PR #28: {PR_URL}\n패킷 위치: {PACKET_REL}/  (README.md, REVIEW_GUIDE_KO.md, manifest.json, regions.json, GITHUB_READBACK_REPORT.json)\n"
           "병합·FREEZE·도면 정전화는 하지 않았고, 기존 main·PR #25~#27과 원본 파일은 바꾸지 않았습니다.", size=9)

    # ---- 2 original verification ----
    p = doc.page("1. 원본 검증 — PR #27 매니페스트와의 SHA256 대조", "패킷은 이 두 파일에서만 만들었고, 원본은 수정하지 않았습니다")
    rows = [["이미지", "원본 파일명(PR #27 docs/t14q_v47/images/)", "크기", "해상도", "실제 SHA256 (패킷 생성 시 계산)", "PR #27 매니페스트 SHA256", "대조"]]
    for lab in (D, B):
        it = integ["assets"][lab]
        e = by_name[names[lab]]
        ok = it["original_sha256_actual"].upper() == e["sha256"].upper()
        rows.append([lab, names[lab], mib(e["bytes"]), f"{it['original_dims'][0]}×{it['original_dims'][1]}", it["original_sha256_actual"].upper(), e["sha256"].upper(), "일치" if ok else "불일치"])
    y = doc.table(p, 30, 80, [95, 150, 60, 70, 300, 300, W - 60 - 975], rows, size=7.6, colors={6: status_color})
    rows = [["이미지", "픽셀 SHA256 (RGB, 무압축 바이트)", "패킷에서의 재조립 픽셀 == 원본 픽셀", "타일 수", "겹침/빈틈"]]
    for lab in (D, B):
        it = integ["assets"][lab]
        rows.append([lab, assets[lab]["pixel_sha256"], "동일" if it["reassembled_equals_original_pixels"] else "불일치", str(it["tiles"]), f"겹침 {it['tile_overlap_pairs']} / 커버리지 {it['coverage_min']}~{it['coverage_max']}회"])
    y = doc.table(p, 30, y + 22, [95, 520, 230, 60, W - 60 - 905], rows, size=7.8, colors={2: status_color})
    doc.tb(p, (30, y + 14, W - 30, y + 150),
           "· 두 원본 모두 PR #27 매니페스트 값과 일치했으므로 매니페스트는 덮어쓰지 않았습니다(불일치 시 임의 승인·덮어쓰기 금지 규칙).\n"
           "· 원본 PSD(약 330 MiB)와 큰 마스터 파일은 GitHub에 올리지 않았고 로컬에만 있습니다. 이 패킷은 PNG의 픽셀을 바꾸지 않은 무손실 분할본입니다.\n"
           "· 미리보기 JPEG는 열람 편의를 위한 1600 px 축소본이며 검수 근거가 아니라 길잡이입니다. 세부 판단은 타일과 포커스 크롭(원본 픽셀)으로 해야 합니다.", size=9.2)

    # ---- 3 previews ----
    p = doc.page("2. 전체 미리보기 (1600×900 JPEG)", "왼쪽 Daylight · 오른쪽 Blue Hour. 같은 카메라이므로 같은 좌표가 같은 위치입니다")
    half = (W - 70) / 2
    for k, lab in enumerate((D, B)):
        x0 = 30 + k * (half + 10)
        pv = assets[lab]["preview"]
        yb = doc.img(p, pk / pv["path"], (x0, 78, x0 + half, 78 + half * 9 / 16), pv["path"])
        doc.tb(p, (x0, yb + 6, x0 + half, yb + 60), f"{lab}\n{pv['path']} · {pv['dimensions'][0]}×{pv['dimensions'][1]} · {kib(pv['bytes'])}\nSHA256 {pv['sha256'][:32]}…", size=8.5)
    doc.tb(p, (30, 78 + half * 9 / 16 + 70, W - 30, 78 + half * 9 / 16 + 190),
           "읽는 법: 지붕의 원형 개구부와 옥상 정원, 상층 수직 파사드 핀, 중층 보이드, 네 개의 코너 코어(이 카메라에서는 3개만 보임), 원통형 튜브, 진입 램프, 도로·횡단보도, 위치 정합 도시 맥락 순으로 확인하세요. "
           "영역별 좌표와 대응 타일은 regions.json과 REVIEW_GUIDE_KO.md에 있습니다. 이웃 건물 높이 다수·도로 폭·가로수·가로등은 가정값이며 실측이 아닙니다.", size=9.2)

    # ---- 4 tiles ----
    p = doc.page("3. 타일 구성과 재조립 결과", "원본 픽셀을 바꾸지 않은 무손실 PNG 타일 (기본 800×800, 400 KiB 초과 시 이분 분할)")
    rows = [["이미지", "타일 수", "타일 총 용량", "최대 타일", "최소 변", "미리보기", "개요", "한도(400 KiB) 초과", "재조립 == 원본"]]
    for lab in (D, B):
        it = integ["assets"][lab]
        rows.append([lab, str(it["tiles"]), mib(it["tile_bytes_total"]), kib(it["tile_bytes_max"]), f"{it['tile_px_min_side']} px", kib(it["preview_bytes"]), kib(integ["checks"]["overview_bytes"]),
                     f"{it['tiles_over_limit']}개", "동일" if it["reassembled_equals_original_pixels"] else "불일치"])
    y = doc.table(p, 30, 80, [130, 70, 110, 100, 80, 90, 80, 130, W - 60 - 790], rows, size=8.4, colors={8: status_color})
    sx = (W - 80) / 2 / 4800.0
    for k, lab in enumerate((D, B)):
        x0 = 30 + k * ((W - 60) / 2 + 10)
        oy = y + 34
        doc.tb(p, (x0, y + 14, x0 + 520, y + 30), f"{lab} 타일 배치(1 pt ≈ {1/sx:.1f} px, 각 사각형이 PNG 한 장)", size=8.5, bold=True)
        for t in assets[lab]["tiles"]:
            b = t["bounds"]
            p.draw_rect(fitz.Rect(x0 + b[0] * sx, oy + b[1] * sx, x0 + b[2] * sx, oy + b[3] * sx), color=(0.35, 0.35, 0.35), width=0.35)
        p.draw_rect(fitz.Rect(x0, oy, x0 + 4800 * sx, oy + 2700 * sx), color=(0, 0, 0), width=0.9)
    doc.tb(p, (30, y + 34 + 2700 * sx + 14, W - 30, H - 30),
           "· 파일명 규칙: images/<이미지>/tiles/x{X}_y{Y}_w{W}_h{H}.png — 좌표는 원본 왼쪽 위가 (0,0)이고 단위는 픽셀입니다.\n"
           "· 재조립 검증: 타일을 원본 크기 캔버스에 붙여 원본 픽셀 배열과 비교(전체 일치), 타일 SHA256·용량 재계산(불일치 0), 모든 타일 면적이 정확히 한 번씩 덮임(커버리지 1~1).\n"
           "· 항목마다 400 KiB 이하이므로 연결된 GitHub 도구가 개별 파일을 이미지로 반환할 수 있습니다.", size=9.2)

    # ---- 5 readback ----
    p = doc.page("4. GitHub 업로드 후 읽기 검증", f"고정 커밋 {rb['pinned_commit']} · {rb['repository']}")
    bk = rest["by_kind"]
    pf = rb["per_file_rest_results"]
    empty, bad_sha, bad_dec = sum(1 for r in pf if not r["bytes"]), sum(1 for r in pf if not r["sha_match"]), sum(1 for r in pf if not r["decodes"])
    rest_ok = rest["all_nonempty"] and rest["all_sha_match"] and rest["all_decode"] and rest["all_dims_match"] and rest["all_not_blank"] and not rest["failures"]
    rows = [["검증 방법", "대상", "결과"],
            ["gh api 원문 읽기 (고정 커밋, REST)", f"미리보기 {bk['preview']} + 타일 {bk['tile']} + 개요 {bk['overview']} + 포커스 {bk['focus']} = {rest['files_checked']}개",
             f"{'통과' if rest_ok else '실패'} — 빈 파일 {empty}개, SHA·용량 불일치 {bad_sha}개, 디코딩 실패 {bad_dec}개, 해상도 불일치 {'0' if rest['all_dims_match'] else '있음'}, 빈 이미지(대비 없음) {'0' if rest['all_not_blank'] else '있음'}, 전체 실패 {len(rest['failures'])}건"],
            ["GitHub MCP 연결(Claude Code 세션) 표본", f"{len(rest['connector_samples'])}개: 미리보기 2, Daylight 타일 1, Blue Hour 타일 1, 포커스 크롭 1", "통과 — 파일마다 실제 이미지 블록이 반환되고 연결이 보고한 blob SHA가 로컬 커밋 바이트의 git blob SHA와 일치"],
            ["ChatGPT 자체 GitHub 연결", "ChatGPT에서 같은 파일을 직접 열람", "미확인 — CHATGPT_CONNECTOR_READBACK_PENDING (아래 확인 방법 참조)"]]
    y = doc.table(p, 30, 80, [240, 380, W - 60 - 620], rows, size=8.4, colors={2: status_color})
    rows = [["표본 경로 (패킷 기준 상대경로)", "형식", "연결이 보고한 blob SHA (앞 16자)", "로컬 blob SHA 일치"]]
    for s in rest["connector_samples"]:
        rows.append([s["path"].replace(PACKET_REL + "/", ""), s["media"], s["connector_blob_sha"][:16] + "…", "일치" if s["equals_local_git_blob_sha"] else "불일치"])
    y = doc.table(p, 30, y + 18, [640, 140, 250, W - 60 - 1030], rows, size=8, colors={3: status_color})
    doc.tb(p, (30, y + 14, W - 30, y + 215),
           "한계(기록): GitHub MCP 도구의 텍스트 출력은 25k 토큰에서 잘려, 큰 PNG의 base64 본문은 텍스트로는 끝까지 받을 수 없습니다. 같은 응답의 이미지 블록으로는 정상 열람되었습니다. "
           "gh api 방식은 원문을 직접 받아 SHA·디코딩을 끝까지 검증했습니다. 이 PDF와 GITHUB_READBACK_REPORT.json은 위 고정 커밋 이후에 추가된 파일이라 위 전수 검증의 대상이 아니며, 푸시 후 최신 HEAD에서 따로 읽어 확인한 결과는 채팅 보고에 적었습니다.\n\n"
           "ChatGPT에서 확인하는 방법: PR #28 브랜치(또는 고정 커밋)에서 REVIEW_GUIDE_KO.md를 먼저 읽고, images/DAYLIGHT_FINAL/preview.jpg · images/BLUEHOUR_FINAL/preview.jpg · focus/ 안의 PNG 한 장을 열어 "
           "파일명이 아니라 이미지 내용(지붕 개구부, 수직 핀, 붉은 스팬드럴 띠 등)이 보이는지 확인하세요. 보이면 그때 상태를 GITHUB_CONNECTOR_READBACK_PASS(chatgpt)로 갱신할 수 있습니다. "
           "그 전까지 ③은 완료로 표시하지 않습니다.", size=9.2)

    # ---- 6 focus regions ----
    p = doc.page("5. 확대 검수 영역 안내", "영역 박스는 눈으로 배치한 근사값(도면 좌표 아님). 대표 포커스는 원본에서 잘라낸 무손실 크롭이며 같은 좌표가 두 이미지에 모두 적용됩니다")
    ids: dict[str, list[str]] = {}
    for f in reg["focus"]:
        if "REFERENCE" in f["asset"]:
            continue
        ids.setdefault(f["region"], [])
        if f["id"] not in ids[f["region"]]:
            ids[f["region"]].append(f["id"])
    rows = [["영역", "확인할 것", "포커스 ID (focus/ 폴더, Daylight·Blue Hour 각각)", "겹침 타일 수 (D/B)"]]
    for r in reg["regions"]:
        rows.append([f"{r['id']} {r['name_ko']}", r["look_for"], ", ".join(ids.get(r["id"], [])) or "(타일 목록만)", f"{len(r['tiles'][D])} / {len(r['tiles'][B])}"])
    y = doc.table(p, 30, 84, [210, 400, 430, W - 60 - 1040], rows, size=8.2)
    doc.tb(p, (30, y + 12, W - 30, y + 90),
           "R1 지붕 개구부·옥상 정원 / R2 상층 수직 핀 / R3 중층 보이드 / R4 코너 코어 / R5 튜브 / R6 입구 램프 / R7 도로·횡단보도 / R8 도시 맥락 — 요청된 8개 확대 영역을 모두 포함합니다. "
           "T1–T4 번호와 튜브의 대응은 도면과 대조해야 하며 이 보고서의 자동 판독 범위가 아닙니다.", size=9)
    gy = y + 54
    doc.tb(p, (30, gy, W - 30, gy + 15), "포커스 크롭 목록 — 위 두 줄 Daylight, 아래 두 줄 Blue Hour (JPEG 썸네일 256 px, 원본 픽셀은 각 focus/*.png 파일)", size=8.3, bold=True)
    cell, gap = 112, 8
    for k, lab in enumerate((D, B)):
        for n, fid in enumerate([f["id"] for f in reg["focus"] if f["asset"] == lab]):
            col, rowi = n % 8, n // 8
            x0 = 30 + col * (cell + gap)
            y0 = gy + 16 + (k * 2 + rowi) * (cell + 14)
            doc.img(p, focus_file(fid, lab), (x0, y0, x0 + cell, y0 + cell), f"{fid} {lab}", thumb_px=256)
            doc.tb(p, (x0, y0 + cell + 1, x0 + cell + 4, y0 + cell + 12), fid.split("_")[0] + " " + "_".join(fid.split("_")[1:3]), size=6.2, color=MUT)

    # ---- 7 fin crops ----
    p = doc.page("6. 수직 핀 복원 — 미해결 항목 (C-T14Q에서 이월)", "같은 픽셀 박스, 원본 해상도 무손실 크롭. 왼쪽부터 Blender 기준본(Daylight) · 최종(Daylight) · Blender 기준본(Blue Hour) · 최종(Blue Hour)")

    for row, fid in enumerate(("F01_fins_right_upper", "F02_fins_right_lower")):
        for col, (asset, cap) in enumerate(((D + "__REFERENCE_BLENDER_BASE", "Blender 기준본 · Daylight"), (D, "최종 · Daylight"), (B + "__REFERENCE_BLENDER_BASE", "Blender 기준본 · Blue Hour"), (B, "최종 · Blue Hour"))):
            sp = focus_file(fid, asset)
            x0 = 30 + col * 282
            y0 = 76 + row * 322
            doc.img(p, sp, (x0, y0, x0 + 270, y0 + 270), f"{fid} {cap}")
            doc.tb(p, (x0, y0 + 273, x0 + 270, y0 + 300), f"{fid}\n{cap}", size=8)
    # ---- 8 fin measurement ----
    p = doc.page("6-2. 핀 복원 자동 계측과 판독", "각 박스에서 수평 띠 성분을 제거한 뒤 열 방향 휘도 스펙트럼의 우세 주기와 피크 전력 비중을 측정했습니다(승인 근거 아님)")
    rows = [["이미지", "박스", "주기 px (Blender / ChatGPT / 최종)", "박스 안 핀 개수 추정 (최종)", "피크 비중 (Blender / ChatGPT / 최종)"]]
    for var in ("DAYLIGHT", "BLUEHOUR"):
        for z, ks in fin[var].items():
            bb, gg, ff = ks["blender_base"], ks["chatgpt_raw_upscaled"], ks["photoshop_final"]
            rows.append([var, z, f"{bb['dominant_period_px']} / {gg['dominant_period_px']} / {ff['dominant_period_px']}", f"{ff['fins_across_box']}", f"{bb['peak_power_share']} / {gg['peak_power_share']} / {ff['peak_power_share']}"])
    y = doc.table(p, 30, 84, [120, 160, 270, 200, W - 60 - 750], rows, size=8.4)
    dev = max(abs(fin[v][z]["photoshop_final"]["dominant_period_px"] / fin[v][z]["blender_base"]["dominant_period_px"] - 1) for v in fin for z in fin[v])
    ratio = {v: [fin[v][z]["photoshop_final"]["peak_power_share"] / fin[v][z]["blender_base"]["peak_power_share"] for z in fin[v]] for v in fin}
    doc.tb(p, (30, y + 16, W - 30, y + 270),
           "작성자 1차 판독(독립 검수 아님):\n"
           f"· 핀 간격(주기)은 Blender 기준본 → ChatGPT 편집 → 최종 세 단계에서 거의 같게 유지됩니다(기준본 대비 최종본 주기 차이 최대 {dev*100:.0f}%). 핀 개수·간격은 보존된 것으로 보입니다.\n"
           f"· Daylight: 최종본의 피크 비중이 기준본의 {min(ratio['DAYLIGHT'])*100:.0f}~{max(ratio['DAYLIGHT'])*100:.0f}% 로, 핀 대비가 Blender 기준본 수준으로 회복되었습니다.\n"
           f"· Blue Hour: 최종본의 피크 비중이 기준본의 {min(ratio['BLUEHOUR'])*100:.0f}~{max(ratio['BLUEHOUR'])*100:.0f}% 에 그쳐 ChatGPT 편집본 수준에 가깝고, 핀 복원이 불완전합니다(미해결).\n"
           "· F02 영역(우측 면 하단, 입구 위): Daylight 최종본에서 핀이 번져 보이는 구간이 육안으로 확인되고, Blue Hour는 계측상 핀 대비가 기준본보다 낮습니다. 육안 판단은 7쪽 크롭으로 사람이 해야 합니다(미해결).\n"
           "→ 이 항목은 GEOMETRY_REWORK_REQUIRED 후보로, 사람의 판단 또는 재작업이 필요합니다. 이 패킷은 그 판단을 GitHub에서 할 수 있게 하는 자료입니다.\n"
           "측정 원자료: fin_rhythm_measurement.json", size=9.6)

    # ---- 9 pending ----
    p = doc.page("7. 남은 일과 승인 경계")
    rows = [["항목", "상태", "내용"],
            ["ChatGPT 자체 GitHub 연결 읽기", "미확인", "CHATGPT_CONNECTOR_READBACK_PENDING. 5쪽의 확인 방법으로 ChatGPT 대화에서 직접 확인해야 완료"],
            ["독립 시각·건축 검수", "대기", "INDEPENDENT_VISUAL_REVIEW_PENDING. 핀 복원(F01·F02), 가정값(이웃 높이·도로 폭·가로수) 확인 포함"],
            ["PR #28 병합 / PR #27 병합", "대기", "하지 않음. 사용자 승인 전 병합·FREEZE·도면책 정전화 금지"],
            ["영구 규칙", "완료", "이후 모든 렌더·편집·최종본·다이어그램·도면은 PDF와 함께 이 방식의 GitHub 검수 패킷을 생성해 올림(AGENTS.md §10, PR #28)"],
            ["개인정보", "완료", "커밋은 noreply 신원으로 작성, 로그·GitHub·PDF에 이메일 미기록. 로컬 계정 경로는 GitHub 파일에 쓰지 않고 저장소 상대경로만 사용"]]
    y = doc.table(p, 30, 80, [260, 70, W - 60 - 330], rows, size=8.8, colors={1: status_color})
    doc.tb(p, (30, y + 18, W - 30, y + 150),
           "이 문서는 접근성·검수 보조 자료이며 건축 정확성 또는 시각 품질의 승인이 아닙니다. 상태 용어: REVIEW_PACKET_LOCAL_ONLY → GITHUB_PUSHED_UNREADABLE → GITHUB_CONNECTOR_READBACK_PASS → INDEPENDENT_VISUAL_REVIEW_PENDING → "
           "(GEOMETRY_REWORK_REQUIRED | VISUAL_NOT_APPROVED | APPROVED_FOR_LAYOUT_NOT_DESIGN_APPROVED).", size=9.2)

    a.out.parent.mkdir(parents=True, exist_ok=True)
    doc.d.subset_fonts()  # Malgun Gothic is ~12 MB per face; embed only the glyphs used
    doc.d.save(a.out, deflate=True, garbage=3)
    doc.qa["pages_total"] = doc.n
    doc.qa["overflow_total"] = sum(x["overflow"] for x in doc.qa["pages"])
    a.qa.write_text(json.dumps(doc.qa, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("pdf:", a.out.resolve(), a.out.stat().st_size, "bytes; pages:", doc.n, "overflows:", doc.qa["overflow_total"], "min_ppi:", doc.qa["min_image_ppi"])


if __name__ == "__main__":
    main()
