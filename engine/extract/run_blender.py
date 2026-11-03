# FILE: extract/run_blender.py
from __future__ import annotations

import glob
import os
import subprocess
from pathlib import Path
from shutil import which

EXPORT_SCRIPT = Path(__file__).with_name("blender_export.py")


def find_blender() -> Path | None:
    candidates = []
    env = os.environ.get("BLENDER_EXE")
    if env:
        candidates.append(env)
    candidates += sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender *\blender.exe"), reverse=True)
    for c in candidates:
        if Path(c).exists():
            return Path(c)
    found = which("blender")
    return Path(found) if found else None


def run_blender_script(blend, script, *args, timeout: int = 300) -> subprocess.CompletedProcess:
    exe = find_blender()
    if exe is None:
        raise RuntimeError("Blender 실행 파일을 찾을 수 없습니다 (환경변수 BLENDER_EXE 설정)")
    cmd = [str(exe), "-b"]
    if blend is not None:
        cmd.append(str(blend))
    cmd += ["--python-exit-code", "1", "--python", str(script), "--", *map(str, args)]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Blender 실패({proc.returncode}):\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
    return proc


def export_model(blend, out_json) -> Path:
    out_json = Path(out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    if out_json.exists():
        out_json.unlink()
    run_blender_script(blend, EXPORT_SCRIPT, out_json)
    if not out_json.exists():
        raise RuntimeError("Blender가 모델 JSON을 만들지 못했습니다")
    return out_json
