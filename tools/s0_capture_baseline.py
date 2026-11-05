"""S0 기준본: A3 종이 mm 좌표로 같은 영역을 다시 자르는 보조도구.

이 스크립트는 3D 설계 좌표를 변경하지 않는다. 입력 이미지는 읽기 전용으로 사용한다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def mm_to_px(rect, paper, size):
    x0, y0, x1, y1 = map(float, rect)
    pw, ph = map(float, paper)
    w, h = size
    if not (0 <= x0 < x1 <= pw and 0 <= y0 < y1 <= ph and pw > 0 and ph > 0):
        raise ValueError("크롭 좌표가 종이 범위 밖에 있거나 뒤집혔다")
    return tuple(round(v) for v in (x0 * w / pw, y0 * h / ph, x1 * w / pw, y1 * h / ph))


def font(size):
    for name in ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                 "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf",
                 "C:/Windows/Fonts/malgun.ttf"):
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def fit_white(im, size):
    return ImageOps.pad(im.convert("RGB"), size, method=Image.Resampling.LANCZOS, color="white")


def capture(source: Path, reference: Path, config: Path, out: Path):
    cfg = json.loads(config.read_text(encoding="utf-8"))
    page = Image.open(source).convert("RGB")
    ref = Image.open(reference).convert("RGB")
    pw, ph = cfg["sheet_mm"]
    if abs((page.width / page.height) / (pw / ph) - 1) > 0.005:
        raise ValueError("입력 이미지 종횡비가 A3 가로와 맞지 않는다")
    if len(set(v["id"] for v in cfg["views"])) != len(cfg["views"]):
        raise ValueError("중복 크롭 ID")
    out.mkdir(parents=True, exist_ok=True)
    (out / "crops").mkdir(exist_ok=True)
    overlay = page.copy()
    d = ImageDraw.Draw(overlay)
    colors = [(172,55,60),(54,105,170),(27,117,101),(151,97,39),(110,62,146)]
    views = []
    thumbnails = []
    for i, item in enumerate(cfg["views"]):
        box = mm_to_px(item["rect_mm"], cfg["sheet_mm"], page.size)
        crop = fit_white(page.crop(box), tuple(cfg["crop_output_px"]))
        path = out / "crops" / (item["id"] + ".png")
        crop.save(path)
        color = colors[i % len(colors)]
        d.rectangle(box, outline=color, width=max(3, page.width // 350))
        x,y = box[:2]
        d.rectangle((x,max(0,y-36),x+155,y),fill=color)
        d.text((x+8,max(0,y-34)),item["id"][:9],font=font(16),fill="white")
        views.append({"id": item["id"], "rect_mm":item["rect_mm"], "rect_px":list(box),
                      "path":"crops/"+path.name,"sha256":sha256(path)})
        thumbnails.append((item["label"],crop))
    overlay_path=out/"overview_annotated.png"
    overlay.save(overlay_path)
    sheet=Image.new("RGB",(1820,2370),"#F6F6F6")
    td=ImageDraw.Draw(sheet)
    td.text((40,24),"S0 | 1층 기준본 / 고정 크롭 5개",font=font(34),fill="#222222")
    sheet.paste(fit_white(overlay,(1240,860)),(30,75))
    sheet.paste(fit_white(ref,(490,490)),(1300,120))
    td.text((1310,625),"참고 이미지: 표현 품질만 비교",font=font(16),fill="#444444")
    td.text((1310,660),"평면/프로그램/크기 직접 대응 금지",font=font(16),fill="#777777")
    td.text((40,943),"동일 종이좌표(mm)·축척·원본 프레임으로 후보 비교",font=font(21),fill="#333333")
    for i,(label,thumb) in enumerate(thumbnails):
        x,y=30+(i%2)*890,1000+(i//2)*450
        sheet.paste(fit_white(thumb,(425,405)),(x,y+35))
        td.text((x+5,y),f"{i+1}. {label}",font=font(21),fill="#222222")
    sheet_path=out/"contact_sheet.png"
    sheet.save(sheet_path)
    manifest={"status":"IMAGE_SNAPSHOT_LOCKED_MODEL_AND_RERENDER_PENDING",
              "source_sha256":sha256(source),"reference_sha256":sha256(reference),
              "config_sha256":sha256(config),"source_pixels":list(page.size),"views":views,
              "contact_sheet_sha256":sha256(sheet_path),"overlay_sha256":sha256(overlay_path),
              "meaning":"Same paper-coordinate crops; model SHA and rerender unverified"}
    (out/"capture_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("S0 captured:",out.resolve(),"views:",len(views))
    return manifest


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--reference",type=Path,required=True)
    p.add_argument("--config",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    capture(a.source,a.reference,a.config,a.out)


if __name__=="__main__":
    main()
