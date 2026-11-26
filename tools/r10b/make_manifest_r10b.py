"""SHA-256 manifest of everything under review/wp0_r10_b (run LAST, after packaging, validation and documents)."""
import hashlib
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT = os.path.join(ROOT, "review", "wp0_r10_b")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


files = []
for dp, _, fs in os.walk(OUT):
    for fn in fs:
        if fn == "manifest.json":
            continue
        full = os.path.join(dp, fn)
        files.append(dict(path=os.path.relpath(full, OUT).replace("\\", "/"), bytes=os.path.getsize(full), sha256=sha(full)))
files.sort(key=lambda r: r["path"])
pdf = "pdf/WP0_R10B_Representative_A2.pdf"
with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(dict(base="review/wp0_r10_b", algorithm="SHA-256", artifact_count=len(files),
                   pdf=dict(path=pdf, sha256=sha(os.path.join(OUT, pdf))), files=files), f, ensure_ascii=False, indent=2)
    f.write("\n")
print("manifest:", os.path.join(OUT, "manifest.json"), "artifacts:", len(files))
