"""STEP 3 — AI 재질 인필 (Gemini). 구조 권한이 없다: 벽·기둥·글자·치수는 STEP 4가 벡터로 다시 덮는다 (AGENTS.md §6.6).

세 가지 방식:
    --skip-ai                 아무것도 하지 않는다. 합성기는 따뜻한 오프화이트 종이 바탕을 쓴다 (기본).
    --mode export-drive       AO 밑그림 + 프롬프트를 <out>/ai_handoff/ 에 묶는다. 사용자가 Google Drive에 올려 Gemini 앱에서 처리하고
                              결과를 <out>/ai_textures/floor_<층>_texture.png 로 돌려놓는다. API 키가 필요 없다.
    --mode import             돌려받은 텍스처를 검사한다(크기 1:1, 구조 윤곽 일치). 통과하면 합성기가 쓴다.
    --mode api                GEMINI_API_KEY가 있을 때 google-genai로 직접 호출한다 (이 환경에서는 키가 없어 시험하지 못했다).

프롬프트에는 글자·숫자·치수선·가짜 벽·원근 왜곡 금지를 명시한다.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline_common as pc  # noqa: E402

NEGATIVE = ("Strictly NO text, NO numbers, NO dimension lines, NO fake walls, NO perspective distortion. "
            "Maintain exact top-down orthographic pixel alignment with the input image; do not move, add, remove or redraw any wall, "
            "column, tube or opening. Only recolor and texture the floor surfaces and the outside ground.")

# 프로그램 이름 키워드 → 재질 (층의 영역 이름에서 찾는다)
MATERIALS = [
    ("판매", "light oak plank flooring with a subtle warm tone"),
    ("F&B", "warm terrazzo flooring"),
    ("문화", "polished pale concrete flooring"),
    ("엔터", "polished pale concrete flooring"),
    ("서비스", "matte grey stone tile"),
    ("전시", "light grey polished concrete"),
]
DEFAULT_MATERIAL = "light oak plank flooring"


def program_notes(layout: dict) -> str:
    rows = []
    for z in layout.get("zones", []):
        mat = next((m for key, m in MATERIALS if key in z["name"]), DEFAULT_MATERIAL)
        rows.append("- program '%s' (about %s sq m): %s" % (z["name"], format(round(z["area_m2"]), ","), mat))
    return "\n".join(rows) or "- single open floor: %s" % DEFAULT_MATERIAL


def build_prompt(floor: str, layout: dict) -> str:
    return (
        "This is a top-down orthographic clay render of floor %s of a multi-storey commercial building (white clay, ambient occlusion only). "
        "Apply subtle, high-end architectural presentation materials to the floor surfaces while preserving the exact pixel boundaries "
        "of the input image:\n%s\n- light matte stone paving and sparse low greenery for the outside area around the building, kept very pale.\n"
        "Keep the palette restrained and desaturated like an architecture-competition presentation sheet.\n%s" % (floor, program_notes(layout), NEGATIVE))


def load_layout(out: str, floor: str) -> dict:
    p = os.path.join(out, "vector", "floor_%s_layout.json" % floor)
    return pc.load_json(p) if os.path.exists(p) else {}


def export_drive(raw, out, floors):
    pack = os.path.join(out, "ai_handoff")
    os.makedirs(pack, exist_ok=True)
    lines = ["# Gemini 인필 전달 패키지", "",
             "1. 이 폴더의 `floor_<층>_ao.png`와 `floor_<층>_prompt.txt`를 Google Drive에 올린다.",
             "2. Gemini 앱에서 이미지를 첨부하고 프롬프트 파일의 내용을 붙여 넣어 결과 이미지를 받는다 (이미지 크기·구도는 그대로여야 한다).",
             "3. 받은 이미지를 `%s` 에 `floor_<층>_texture.png` 이름으로 저장한다." % os.path.abspath(os.path.join(out, "ai_textures")),
             "4. `python src/03_gemini_retoucher.py --mode import ...`로 검사한 뒤 합성기를 다시 돌린다.", ""]
    for f in floors:
        src = os.path.join(raw, "floor_%s_ao.png" % f)
        if not os.path.exists(src):
            print("건너뜀(AO 없음):", f)
            continue
        shutil.copy2(src, os.path.join(pack, "floor_%s_ao.png" % f))
        with open(os.path.join(pack, "floor_%s_prompt.txt" % f), "w", encoding="utf-8") as fh:
            fh.write(build_prompt(f, load_layout(out, f)))
        lines.append("- %s: %s" % (f, os.path.abspath(os.path.join(pack, "floor_%s_ao.png" % f))))
    with open(os.path.join(pack, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("HANDOFF", os.path.abspath(pack))


def edge_map(img: Image.Image, n=512) -> np.ndarray:
    g = np.asarray(img.convert("L").resize((n, n)), dtype=np.float32) / 255.0
    gx = np.abs(np.diff(g, axis=1, prepend=g[:, :1]))
    gy = np.abs(np.diff(g, axis=0, prepend=g[:1, :]))
    return gx + gy


def check_texture(raw, out, floor, min_corr=0.25):
    """텍스처가 AO와 1:1로 정렬되는지 본다. 크기가 다르면 같은 비율일 때만 리사이즈한다."""
    ao = Image.open(os.path.join(raw, "floor_%s_ao.png" % floor))
    tp = os.path.join(out, "ai_textures", "floor_%s_texture.png" % floor)
    if not os.path.exists(tp):
        return None, "텍스처 없음"
    tx = Image.open(tp)
    if tx.size != ao.size:
        if abs(tx.size[0] / tx.size[1] - ao.size[0] / ao.size[1]) > 0.005:
            return False, "화면비 다름 %s vs %s" % (tx.size, ao.size)
        tx = tx.resize(ao.size, Image.LANCZOS)
        tx.save(tp)
    a, b = edge_map(ao), edge_map(tx)
    a, b = a - a.mean(), b - b.mean()
    corr = float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-9))
    return corr >= min_corr, "윤곽 상관 %.3f (기준 %.2f)" % (corr, min_corr)


def call_api(raw, out, floors, model):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY가 없다. --skip-ai 또는 --mode export-drive를 쓰라.")
    from google import genai      # pip install google-genai
    from google.genai import types
    client = genai.Client(api_key=key)
    os.makedirs(os.path.join(out, "ai_textures"), exist_ok=True)
    for f in floors:
        ao = Image.open(os.path.join(raw, "floor_%s_ao.png" % f))
        res = client.models.generate_content(model=model, contents=[build_prompt(f, load_layout(out, f)), ao],
                                             config=types.GenerateContentConfig(response_modalities=["IMAGE"]))
        for part in res.candidates[0].content.parts:
            if getattr(part, "inline_data", None):
                import io
                Image.open(io.BytesIO(part.inline_data.data)).convert("RGB").resize(ao.size, Image.LANCZOS).save(
                    os.path.join(out, "ai_textures", "floor_%s_texture.png" % f))
                break
        ok, msg = check_texture(raw, out, f)
        print("API", f, "OK" if ok else "검사 실패", msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--floors", default="")
    ap.add_argument("--mode", choices=("export-drive", "import", "api"), default=None)
    ap.add_argument("--skip-ai", action="store_true")
    ap.add_argument("--model", default="gemini-2.5-flash-image")
    a = ap.parse_args()
    raw, out = os.path.abspath(a.raw), os.path.abspath(a.out)
    floors = [f for f in a.floors.split(",") if f] or pc.list_floors(raw)
    if a.skip_ai or a.mode is None:
        print("SKIP_AI: AI 인필 없음. 합성기는 오프화이트 종이 바탕을 쓴다.")
        return
    if a.mode == "export-drive":
        export_drive(raw, out, floors)
    elif a.mode == "import":
        bad = 0
        for f in floors:
            ok, msg = check_texture(raw, out, f)
            print("IMPORT", f, {True: "OK", False: "FAIL", None: "없음"}[ok], msg)
            bad += ok is False
        if bad:
            raise SystemExit("텍스처 검사 실패 %d건" % bad)
    else:
        call_api(raw, out, floors, a.model)


if __name__ == "__main__":
    main()
