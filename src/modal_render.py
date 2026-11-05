"""Modal에서 층별 Blender 렌더를 병렬로 돌린다 (Claude 토큰이 아니라 Modal 크레딧을 쓴다).

    modal run src/modal_render.py --glb <model.glb> --out output/drawing_pipeline [--size 4096] [--samples 24] [--cut 1.5] [--floors 1F,2F]

층 목록을 주지 않으면 <out>/raw_slices/floors.json(로컬 절단 단계가 만든 것)에서 읽는다.
각 층은 별도 컨테이너(8 vCPU)에서 01_headless_slicer.py를 그대로 실행한다. 로컬과 같은 Blender 4.2.0을 쓴다.
결과(floor_<층>_slice.json, _ao.png, _cutmask.png, camera_bounds.json)를 <out>/raw_slices에 쓴다.
"""
import json
import os
import subprocess
import tempfile

import modal

BLENDER_URL = "https://download.blender.org/release/Blender4.2/blender-4.2.0-linux-x64.tar.xz"
HERE = os.path.dirname(os.path.abspath(__file__))

app = modal.App("thesis-drawing-pipeline")
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("wget", "xz-utils", "libxi6", "libxxf86vm1", "libxfixes3", "libxrender1", "libgl1", "libegl1",
                 "libxkbcommon0", "libsm6", "libice6", "libxext6", "libx11-6")
    .run_commands(
        f"wget -q {BLENDER_URL} -O /tmp/blender.tar.xz",
        "mkdir -p /opt/blender && tar -xf /tmp/blender.tar.xz -C /opt/blender --strip-components=1",
        "rm /tmp/blender.tar.xz",
    )
)


@app.function(image=image, cpu=8, memory=8192, timeout=3600)
def render_floor(glb_bytes: bytes, script_text: str, floor: str, size: int, samples: int, cut: float, model_name: str = "model.glb", frame_ref_text: str = "") -> dict:
    work = tempfile.mkdtemp()
    glb = os.path.join(work, "model" + os.path.splitext(model_name)[1].lower())
    script = os.path.join(work, "slicer.py")
    out = os.path.join(work, "out")
    with open(glb, "wb") as fh:
        fh.write(glb_bytes)
    with open(script, "w", encoding="utf-8") as fh:
        fh.write(script_text)
    cmd = ["/opt/blender/blender", "-b", "--factory-startup", "-P", script, "--", "--input", glb, "--out", out,
           "--floors", floor, "--size", str(size), "--samples", str(samples), "--cut", str(cut), "--threads", "8"]
    if frame_ref_text:                                                     # 1층 기준 도면 방향(진북각). 없으면 층마다 90° 어긋난 틀이 나올 수 있다
        ref = os.path.join(work, "frame_ref.json")
        with open(ref, "w", encoding="utf-8") as fh:
            fh.write(frame_ref_text)
        cmd += ["--frame-ref", ref]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    raw = os.path.join(out, "raw_slices")
    files = {}
    if os.path.isdir(raw):
        for name in os.listdir(raw):
            with open(os.path.join(raw, name), "rb") as fh:
                files[name] = fh.read()
    tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-12:])
    return {"floor": floor, "returncode": proc.returncode, "files": files, "log_tail": tail}


@app.local_entrypoint()
def main(glb: str, out: str, size: int = 4096, samples: int = 24, cut: float = 1.5, floors: str = "", frame_ref: str = ""):
    raw = os.path.join(os.path.abspath(out), "raw_slices")
    if floors:
        names = [f.strip() for f in floors.split(",") if f.strip()]
    else:
        fp = os.path.join(raw, "floors.json")
        if not os.path.exists(fp):
            raise SystemExit("floors.json이 없다. 먼저 로컬에서 --phase slice로 절단 단계를 한 번 돌리거나 --floors를 지정하라: " + fp)
        with open(fp, encoding="utf-8") as fh:
            names = list(json.load(fh)["floors"].keys())
    with open(os.path.abspath(glb), "rb") as fh:
        glb_bytes = fh.read()
    with open(os.path.join(HERE, "01_headless_slicer.py"), encoding="utf-8") as fh:
        script_text = fh.read()
    os.makedirs(raw, exist_ok=True)
    ref_text = open(os.path.abspath(frame_ref), encoding="utf-8").read() if frame_ref else ""
    args = [(glb_bytes, script_text, f, size, samples, cut, os.path.basename(glb), ref_text) for f in names]
    failed = []
    print("Modal 렌더 시작: %d개 층, %d px, %d 샘플" % (len(names), size, samples), flush=True)
    for res in render_floor.starmap(args, order_outputs=False):          # 끝나는 층부터 받아 쓴다
        for name, data in res["files"].items():
            with open(os.path.join(raw, name), "wb") as fh:
                fh.write(data)
        ok = res["returncode"] == 0 and any(n.endswith("_ao.png") for n in res["files"])
        print(("OK   " if ok else "FAIL ") + res["floor"], "->", raw, flush=True)
        if not ok:
            failed.append(res["floor"])
            print(res["log_tail"])
    if failed:
        raise SystemExit("실패한 층: " + ", ".join(failed))
    print("DONE_MODAL", raw)
