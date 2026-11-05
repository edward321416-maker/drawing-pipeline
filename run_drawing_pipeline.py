"""도면 파이프라인 단일 진입점.

    python run_drawing_pipeline.py --blend <모델.glb|.blend> [--cut-z 1.5] [--skip-ai] [--modal] [--floors 1F,2F] [--size 4096]

단계: 1) 헤드리스 절단·렌더 (Blender, 로컬 또는 --modal) → 2) 위상 복원·DXF/SVG → 3) AI 인필(--skip-ai면 건너뜀) → 4) 합성 → QA 검증.
QA가 실패하면 비정상 종료한다(AGENTS.md §6.4: 통과본만 제시). 산출물은 output/drawing_pipeline 아래에 둔다.
승인 전에는 도면\\02_최종결과물로 옮기지 않는다 (AGENTS.md §4).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
BLENDER = os.environ.get("BLENDER_EXE", r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe")
MODAL = os.environ.get("MODAL_EXE", r"C:\Users\admin\anaconda3\Scripts\modal.exe")


def run(cmd, env=None):
    print("$", " ".join('"%s"' % c if " " in c else c for c in cmd), flush=True)
    r = subprocess.run(cmd, env={**os.environ, "PYTHONUTF8": "1", **(env or {})})
    if r.returncode:
        raise SystemExit("실패(종료 코드 %d): %s" % (r.returncode, cmd[0]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True, help="모델 파일 (.glb 또는 .blend)")
    ap.add_argument("--out", default=os.path.join(ROOT, "output", "drawing_pipeline"))
    ap.add_argument("--cut-z", type=float, default=1.5, help="바닥 위 절단 높이(m). 승인된 규칙 = 1.5")
    ap.add_argument("--floors", default="")
    ap.add_argument("--size", type=int, default=4096)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--scale", type=int, default=200)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--skip-ai", action="store_true")
    ap.add_argument("--ai-mode", choices=("export-drive", "import", "api"), default=None)
    ap.add_argument("--modal", action="store_true", help="렌더를 Modal 컨테이너에서 병렬로 (로컬 CPU·시간 절약)")
    ap.add_argument("--skip-render", action="store_true", help="이미 있는 raw_slices를 재사용")
    ap.add_argument("--frame-ref", default="", help="1층 마스터의 camera_bounds.json. GLB 상층 도면의 방향을 1층과 맞춘다(없으면 90° 어긋날 수 있음)")
    a = ap.parse_args()
    model, out = os.path.abspath(a.blend), os.path.abspath(a.out)
    raw = os.path.join(out, "raw_slices")
    os.makedirs(out, exist_ok=True)
    print("모델:", model)
    print("출력:", out)

    fr = ["--frame-ref", os.path.abspath(a.frame_ref)] if a.frame_ref else []
    if not a.skip_render:
        if a.modal:
            if not os.path.exists(os.path.join(raw, "floors.json")):                          # 층 목록은 가벼운 로컬 절단으로 먼저 얻는다
                run([BLENDER, "-b", "--factory-startup", "-P", os.path.join(SRC, "01_headless_slicer.py"), "--",
                     "--input", model, "--out", out, "--cut", str(a.cut_z), "--phase", "slice"] + fr)
            cmd = [MODAL, "run", os.path.join(SRC, "modal_render.py"), "--glb", model, "--out", out, "--size", str(a.size),
                   "--samples", str(a.samples), "--cut", str(a.cut_z)] + fr
            if a.floors:
                cmd += ["--floors", a.floors]
            run(cmd)
        else:
            cmd = [BLENDER, "-b"] + (["--factory-startup"] if model.lower().endswith((".glb", ".gltf")) else [model])
            cmd += ["-P", os.path.join(SRC, "01_headless_slicer.py"), "--", "--out", out, "--cut", str(a.cut_z),
                    "--size", str(a.size), "--samples", str(a.samples)]
            if model.lower().endswith((".glb", ".gltf", ".blend")):
                cmd += ["--input", model]
            cmd += fr
            if a.floors:
                cmd += ["--floors", a.floors]
            run(cmd)

    py = sys.executable
    fl = ["--floors", a.floors] if a.floors else []
    run([py, "-I", os.path.join(SRC, "02_topology_to_cad.py"), "--raw", raw, "--out", out, "--scale", str(a.scale)] + fl)
    ai = [py, "-I", os.path.join(SRC, "03_gemini_retoucher.py"), "--raw", raw, "--out", out] + fl
    ai += ["--skip-ai"] if (a.skip_ai or not a.ai_mode) else ["--mode", a.ai_mode]
    run(ai)
    run([py, "-I", os.path.join(SRC, "04_hybrid_compositor.py"), "--raw", raw, "--out", out, "--scale", str(a.scale), "--dpi", str(a.dpi)] + fl)
    run([py, "-I", os.path.join(ROOT, "tests", "verify_pipeline.py"), "--out", out] + fl)
    print("완료: 모든 단계 통과. 시트:", os.path.join(out, "final_sheets"))


if __name__ == "__main__":
    main()
