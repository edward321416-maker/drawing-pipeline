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


TEXT = (".json", ".md", ".txt", ".svg", ".py")
CRLF, LF = bytes([13, 10]), bytes([10])
# Python on Windows writes text with CRLF, git stores LF: normalise first so the manifest describes the stored bytes.
fixed = []
for dp, _, fs in os.walk(OUT):
    for fn in fs:
        if fn.lower().endswith(TEXT):
            full = os.path.join(dp, fn)
            raw = open(full, "rb").read()
            if CRLF in raw:
                open(full, "wb").write(raw.replace(CRLF, LF))
                fixed.append(os.path.relpath(full, OUT).replace(os.sep, "/"))
print("normalised CRLF -> LF:", fixed)
files = []
for dp, _, fs in os.walk(OUT):
    for fn in fs:
        if fn == "manifest.json":
            continue
        full = os.path.join(dp, fn)
        files.append(dict(path=os.path.relpath(full, OUT).replace(os.sep, "/"), bytes=os.path.getsize(full), sha256=sha(full)))
files.sort(key=lambda r: r["path"])
pdf = "pdf/WP0_R10B_Representative_A2.pdf"
with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(dict(base="review/wp0_r10_b", algorithm="SHA-256", artifact_count=len(files),
                   pdf=dict(path=pdf, sha256=sha(os.path.join(OUT, pdf))), files=files), f, ensure_ascii=False, indent=2)
    f.write("\n")
print("manifest:", os.path.join(OUT, "manifest.json"), "artifacts:", len(files))
