"""V1 ↔ V2 비교 이미지: 같은 종류의 시트를 나란히(왼쪽 V1 PDF 사본, 오른쪽 V2 PDF)."""
import argparse
import json
import os
import sys

import fitz
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")


def render(pdf, page, dpi):
    d = fitz.open(pdf)
    pm = d[page - 1].get_pixmap(dpi=dpi)
    return Image.frombytes("RGB", (pm.width, pm.height), pm.samples)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    run = os.path.abspath(a.run)
    v1 = os.path.join(run, "comparisons", "Drawing_Set_Candidate_V1_reference_COPY.pdf")
    v2 = os.path.join(run, "book", "drawing_set_candidate_v2.pdf")
    idx = {r["sheet"]: r["page"] for r in json.load(open(os.path.join(run, "00_index", "sheet_index.json"), encoding="utf-8"))["sheets"]}
    v1p = {"A-002": 3, "A-003": 4, "P-101": 5, "P-103": 7, "E-201": 8, "S-302": 13}
    jobs = [("compare_1F_plan_A-003", "A-003", "A-003", "1층 배치·평면 (A-003)", "V1 A-003 | V2 A-003 — 사용자 제공 파일이라 동일(쪽 번호표만 추가). V2에서 1층을 새 템플릿으로 다시 그리지 않음"),
            ("compare_3F_plan", "P-101", "P-101", "3층 평면", "V1: 치수·축선·단면/입면 표시 없음, 범례 작음 | V2: 치수열·축선 기호·단면/입면/상세 표시·큰 범례 패널"),
            ("compare_13F_plan", "P-103", "P-104", "13층 평면 (문화·엔터)", "V1: 3F와 같은 형식, 가구 적음 | V2: 이벤트 무대·계단 객석·전시 좌대·라운지 포드, 치수·축선 추가"),
            ("compare_elevation_E-201", "E-201", "E-201", "북측 입면도", "V1: 레벨 문자만(치수·축선 없음, +76.499 노이즈) | V2: 전체 폭·축선·층고 체인·전체 높이·높이표·상세 호출·GL"),
            ("compare_section_S-302", "S-302", "S-302", "단면도 A–A", "V1: 레벨 + 절단 요소 문장(치수·축선·키플랜 없음) | V2: 치수 체인·축선·키플랜 절단선·절단 요소 높이표"),
            ("compare_legend_A-002", "A-002", "A-002", "범례 (A-002)", "V1: 층 표 + 선 위계 + 문장 표기(기호 도형 없음) | V2: 범례·기호·축척·사실성 등급·상태 전용 시트(실제 기호 도형)")]
    ft = ImageFont.truetype(r"C:\Windows\Fonts\malgunbd.ttf", 26)
    fs = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 20)
    out = []
    for name, s1, s2, title, note in jobs:
        A = render(v1, v1p[s1], 90)
        B = render(v2, idx[s2], 90)
        W = A.width + B.width + 30
        H = max(A.height, B.height) + 110
        im = Image.new("RGB", (W, H), "#e6e6e6")
        dr = ImageDraw.Draw(im)
        dr.text((10, 8), "%s   (왼쪽 V1 %s · 오른쪽 V2 %s)" % (title, s1, s2), font=ft, fill="#111")
        dr.text((10, 48), note, font=fs, fill="#444")
        im.paste(A, (10, 100))
        im.paste(B, (A.width + 20, 100))
        dr.rectangle([10, 100, 10 + A.width, 100 + A.height], outline="#888")
        dr.rectangle([A.width + 20, 100, 20 + A.width + B.width, 100 + B.height], outline="#888")
        p = os.path.join(run, "comparisons", name + ".png")
        im.save(p)
        out.append(p)
        print("COMPARE", os.path.abspath(p))
    json.dump({"v1_pdf": v1, "v2_pdf": v2, "images": out, "note": "V1 쪽 번호는 V1 book_registry 기준(A-002=3, A-003=4, P-101=5, P-103=7, E-201=8, S-302=13)"}, open(os.path.join(run, "comparisons", "comparison_manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
