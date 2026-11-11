"""Portable CJK font resolver (replaces hard-coded C:\\Windows\\Fonts paths).

Search order for each logical face ('regular', 'bold'):
  1. $T14_FONT_DIR (any of the candidate file names below)
  2. Windows font folder (Malgun Gothic, the face the V1/V2 sheets were drawn with)
  3. Linux/macOS system folders (NanumBarunGothic, NanumGothic, Noto Sans CJK KR)
  4. fontconfig (fc-match) as a last resort
No font binary is shipped in the repository. Malgun Gothic is a Windows system font and is
only used when it is already installed; Nanum and Noto are SIL OFL 1.1.
"""
import os
import shutil
import subprocess

CANDIDATES = {
    "regular": ["malgun.ttf", "NanumBarunGothic.ttf", "NanumGothic.ttf", "NotoSansCJKkr-Regular.otf",
                "NotoSansKR-Regular.otf", "NotoSansCJK-Regular.ttc"],
    "bold": ["malgunbd.ttf", "NanumBarunGothicBold.ttf", "NanumGothicBold.ttf", "NotoSansCJKkr-Bold.otf",
             "NotoSansKR-Bold.otf", "NotoSansCJK-Bold.ttc"],
}
DIRS = [
    os.environ.get("T14_FONT_DIR", ""),
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
    "/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.fonts"),
    os.path.expanduser("~/.local/share/fonts"), "/Library/Fonts", os.path.expanduser("~/Library/Fonts"),
]


def _walk(d):
    for root, _dirs, files in os.walk(d):
        for f in files:
            yield root, f


def resolve(face="regular"):
    """Return (absolute path, family label) for the first available candidate."""
    names = CANDIDATES[face]
    found = {}
    for d in DIRS:
        if d and os.path.isdir(d):
            for root, f in _walk(d):
                if f in names and f not in found:
                    found[f] = os.path.join(root, f)
    for n in names:
        if n in found:
            return found[n], os.path.splitext(n)[0]
    if shutil.which("fc-match"):
        style = "Bold" if face == "bold" else "Regular"
        out = subprocess.run(["fc-match", "-f", "%{file}", f":lang=ko:style={style}"],
                             capture_output=True, text=True).stdout.strip()
        if out and os.path.exists(out):
            return out, os.path.basename(out)
    raise FileNotFoundError(
        "No Korean font found. Install fonts-nanum (apt) or Noto Sans CJK, or set T14_FONT_DIR. "
        "Font files are not distributed with this repository.")


def describe():
    out = {}
    for face in CANDIDATES:
        try:
            p, fam = resolve(face)
            out[face] = {"path": p, "family": fam}
        except FileNotFoundError as e:
            out[face] = {"error": str(e)}
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(describe(), ensure_ascii=False, indent=1))
