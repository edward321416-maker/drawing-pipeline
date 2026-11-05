"""C-T14 고정 확대 크롭 5개 + 전후 비교 이미지.

크롭 위치는 모델 slice의 요소(코어·튜브·캡슐)와 건물 중심에서 계산한다(좌표 직접 입력 없음).
전(before)·후(after) SVG는 같은 월드 창을 같은 배율(100 px/m)로 잘라 비교한다.

    python -I tools/t14_crops.py --run <후보 폴더> --floor 3F --before <전 SVG> --after <후 SVG> --glb-sha <sha>
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
import pipeline_common as pc  # noqa: E402

PX_PER_M = 100
FONT = r"C:\Windows\Fonts\malgun.ttf"
FONT_B = r"C:\Windows\Fonts\malgunbd.ttf"


def anchors(sl, lay):
    cuts = pc.cut_geometries(sl)
    bx0, by0, bx1, by1 = lay["building"]
    out = []
    cores = [(it, g) for it, g in cuts.get("core_wall", [])]
    it, g = max(cores, key=lambda t: (t[1].centroid.y, t[1].centroid.x))                  # 위·오른쪽 끝 코어
    out.append(("crop_01_core", "%s (북동 끝)" % it["name_ko"], g.centroid, 16.0))
    tubes = {it["name_ko"]: g for it, g in cuts.get("tube_wall", [])}
    t1 = next(g for n, g in tubes.items() if n.endswith("T1"))
    out.append(("crop_02_spiral_T1", "나선 램프 튜브 T1", t1.centroid, 16.0))
    cap = next(g for n, g in tubes.items() if "캡슐" in n)
    out.append(("crop_03_capsule", "서측 캡슐(벽·에스컬레이터 윤곽)", cap.centroid, 26.0))
    t3 = next(g for n, g in tubes.items() if n.endswith("T3"))
    out.append(("crop_04_elevator_T3", "승강기 튜브 T3", t3.centroid, 16.0))
    from shapely.geometry import Point
    out.append(("crop_05_center_grid", "건물 중심: 기둥 격자·점선 기둥·시장 가구", Point((bx0 + bx1) / 2, (by0 + by1) / 2), 26.0))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--floor", default="3F")
    ap.add_argument("--before", default=None, help="없으면 after 크롭만 만든다(방향이 바뀐 시트는 같은 창으로 전/후 비교가 안 된다)")
    ap.add_argument("--after", required=True)
    ap.add_argument("--outdir", default=None)
    a = ap.parse_args()
    import cairosvg
    from PIL import Image, ImageDraw, ImageFont
    Image.MAX_IMAGE_PIXELS = None
    run = os.path.abspath(a.run)
    sl = pc.load_json(os.path.join(run, "raw_slices", "floor_%s_slice.json" % a.floor))
    lay = pc.load_json(os.path.join(run, "vector", "floor_%s_layout.json" % a.floor))
    bx0, by0, bx1, by1 = lay["building"]
    b0, b3 = (bx0 + bx1) / 2 - 42.0, (by0 + by1) / 2 + 29.7                               # 1:200 시트의 월드 창 좌상단
    od = a.outdir or os.path.join(run, "3F_PILOT", "crops")
    cmp_dir = os.path.join(run, "comparisons")
    os.makedirs(od, exist_ok=True)
    os.makedirs(cmp_dir, exist_ok=True)
    rast = {}
    for key, p in (("before", a.before), ("after", a.after)):
        if p is None:
            continue
        tmp = os.path.join(od, "_tmp_%s.png" % key)
        cairosvg.svg2png(url=p, write_to=tmp, output_width=84 * PX_PER_M, background_color="white")
        rast[key] = Image.open(tmp).convert("RGB")
    f_t = ImageFont.truetype(FONT_B, 34)
    f_s = ImageFont.truetype(FONT, 26)
    log = []
    for cid, label, c, size in anchors(sl, lay):
        half = size / 2
        cxp, cyp = (c.x - b0) * PX_PER_M, (b3 - c.y) * PX_PER_M
        W_, H_ = rast["after"].size
        hp = int(half * PX_PER_M)
        cxp = min(max(cxp, hp), W_ - hp)                                                   # 시트 밖으로 나가지 않게 창을 안으로 민다(검은 띠 방지)
        cyp = min(max(cyp, hp), H_ - hp)
        box = (int(cxp - hp), int(cyp - hp), int(cxp + hp), int(cyp + hp))
        crops = {k: im.crop(box) for k, im in rast.items()}
        crops["after"].save(os.path.join(od, cid + ".png"))
        w, h = crops["after"].size
        log.append({"id": cid, "label": label, "center_world": [round(c.x, 3), round(c.y, 3)], "size_m": size, "px": [w, h], "window_px_at_100px_per_m": list(box)})
        if "before" not in crops:
            continue
        crops["before"].save(os.path.join(od, cid + "_before.png"))
        s = 1100.0 / w
        wv, hv = int(w * s), int(h * s)
        sheet = Image.new("RGB", (wv * 2 + 30, hv + 110), "white")
        d = ImageDraw.Draw(sheet)
        sheet.paste(crops["before"].resize((wv, hv), Image.LANCZOS), (0, 110))
        sheet.paste(crops["after"].resize((wv, hv), Image.LANCZOS), (wv + 30, 110))
        d.text((10, 10), "%s — %s   (월드 중심 %.2f, %.2f · 한 변 %.0f m · 1:200 시트 기준)" % (cid, label, c.x, c.y, size), font=f_t, fill="#111")
        d.text((10, 62), "BEFORE  T13A 렌더러 그대로 (Level S 처리 전)", font=f_s, fill="#a33")
        d.text((wv + 40, 62), "AFTER  Level S + 모델 요소 복원 + 점선 기둥", font=f_s, fill="#173")
        d.line([(wv + 15, 110), (wv + 15, hv + 110)], fill="#999", width=2)
        sheet.save(os.path.join(cmp_dir, "compare_%s.png" % cid))
    if "before" not in rast:
        for k in rast:
            os.remove(os.path.join(od, "_tmp_%s.png" % k))
        json.dump(log, open(os.path.join(od, "crops_manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        for e in log:
            print("CROP", e["id"], os.path.abspath(os.path.join(od, e["id"] + ".png")))
        return
    # 전체 시트 전후
    wv = 1800
    hb = int(rast["before"].size[1] * wv / rast["before"].size[0])
    full = Image.new("RGB", (wv * 2 + 30, hb + 110), "white")
    d = ImageDraw.Draw(full)
    full.paste(rast["before"].resize((wv, hb), Image.LANCZOS), (0, 110))
    full.paste(rast["after"].resize((wv, hb), Image.LANCZOS), (wv + 30, 110))
    d.text((10, 10), "3F A3 1:200 — BEFORE | AFTER", font=f_t, fill="#111")
    d.text((10, 62), "BEFORE: T13A 렌더러 그대로 (외피 없음·기둥 10개 삭제·캡슐 입구 임의 생성·에스컬레이터/입면 부재 누락)", font=f_s, fill="#a33")
    d.text((wv + 40, 62), "AFTER: 외피 윤곽·기둥 34개(점선 10)·캡슐 벽 닫힘·Level S 표기·막대 이동", font=f_s, fill="#173")
    full.save(os.path.join(cmp_dir, "compare_3F_1to200_full_before_after.png"))
    for k in rast:
        os.remove(os.path.join(od, "_tmp_%s.png" % k))
    json.dump(log, open(os.path.join(od, "crops_manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for e in log:
        print("CROP", e["id"], os.path.abspath(os.path.join(od, e["id"] + ".png")))
    print("DONE", os.path.abspath(cmp_dir))


if __name__ == "__main__":
    main()
