"""drawing-source-guard checks (stdlib only; reuses src/t14s/source.py for the pinned-slice check).

    python -I guard_check.py sources                       # pinned verified slices: copy == manifest (existing verify_sources)
    python -I guard_check.py manifests [--root .]           # frozen SHA256 manifests still match the files on disk
    python -I guard_check.py diff --base <ref> [--root .]   # git changes touching protected paths
    python -I guard_check.py claims FILE [FILE ...]         # unsupported approval / freeze claims in text or JSON metadata

Exit status: 0 = clean, 1 = violation found, 2 = usage or configuration error.
A clean result proves only that the checked bytes and claims are unchanged. It is not an architectural approval.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG = SKILL_DIR / "references" / "protected_paths.json"

ALLOWED_APPROVAL_VALUES = {"NOT_APPROVED", "PENDING", "NONE", ""}
ALLOWED_STATUS_TOKENS = ("NOT_APPROVED", "NOT FROZEN", "NOT_FROZEN", "NOT_DESIGN_APPROVED", "AWAITING", "PENDING", "FOR_CHATGPT")
CLAIM_EN = re.compile(r"\b(approved|signed[- ]off|frozen|code[- ]compliant|fully compliant|meets code|passes code)\b", re.I)
CLAIM_KO = re.compile(r"(최종\s*승인|승인\s*(됨|완료)|확정\s*(됨|완료)|동결\s*(됨|완료)|법규\s*(적합|충족|만족))")
NEGATION = re.compile(r"(\bnot\b|\bno\b|\bnever\b|\bnothing\b|\bnone\b|\bneither\b|\bun-?|\bwithout\b|\bpending\b|\bawaiting\b|\bif\b|\bbefore\b|미|않|아님|전까지|금지|전에는)", re.I)


def load_config(path: Path = CONFIG) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def glob_match(path: str, pattern: str) -> bool:
    """`dir/**` protects everything below dir; other patterns use fnmatch on the posix path."""
    path = path.replace("\\", "/")
    if pattern.endswith("/**"):
        return path.startswith(pattern[:-2])
    return fnmatch.fnmatch(path, pattern)


# ------------------------------------------------------------------ sources
def check_sources(root: Path) -> dict:
    """Delegates to the project's own pinned-slice check so the logic is not duplicated."""
    sys.path.insert(0, str(root / "src"))
    from t14s import source  # noqa: E402  (project module, not a dependency)
    res = source.verify_sources()
    return {"check": "sources", "ok": bool(res["ok"]), "files": res["files"], "original_checked": res["original_checked"], "problems": res["problems"]}


# ------------------------------------------------------------------ manifests
def _manifest_entries(data: dict):
    """Yield (relative file path inside the manifest's folder, sha256) for both manifest layouts seen in this repo."""
    if "floors" in data:                       # outputs/T14*/SHA256_MANIFEST.json: floors -> file -> {sha256, bytes}
        for floor, files in data["floors"].items():
            for name, v in files.items():
                yield "%s/%s" % (floor, name), v["sha256"]
    elif "files" in data:                      # data/t14s/source_slices/manifest.json: files -> name -> sha256
        for name, h in data["files"].items():
            yield name, h


def check_manifests(root: Path, manifests: list[str]) -> dict:
    problems, checked = [], 0
    for rel in manifests:
        mp = root / rel
        if not mp.exists():
            problems.append("manifest missing: %s" % rel)
            continue
        base = mp.parent
        for name, want in _manifest_entries(json.loads(mp.read_text(encoding="utf-8"))):
            fp = base / name
            checked += 1
            if not fp.exists():
                problems.append("missing: %s/%s" % (rel, name))
            elif sha256_file(fp) != want:
                problems.append("sha mismatch: %s/%s" % (rel, name))
    return {"check": "manifests", "ok": not problems, "files_checked": checked, "problems": problems[:50]}


# ------------------------------------------------------------------ diff
def git_changes(root: Path, base: str) -> list[tuple[str, str]]:
    def run(*args):
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or "git failed")
        return r.stdout
    out = []
    for line in run("diff", "--name-status", "--no-renames", base + "...HEAD").splitlines():
        st, _, p = line.partition("\t")
        out.append((st[:1], p))
    for line in run("status", "--porcelain", "--untracked-files=all").splitlines():  # uncommitted work counts too
        st, p = line[:2].strip() or "M", line[3:].strip().strip('"')
        out.append(("A" if st == "??" else st[:1], p))
    return out


def check_diff(root: Path, base: str, extra: list[str]) -> dict:
    cfg = load_config()
    pats = list(cfg["protected_globs"]) + list(extra)
    hits = sorted({(st, p) for st, p in git_changes(root, base) if any(glob_match(p, q) for q in pats)})
    return {"check": "diff", "ok": not hits, "base": base, "protected_patterns": len(pats),
            "violations": ["%s %s" % h for h in hits[:80]], "violation_count": len(hits)}


# ------------------------------------------------------------------ claims
def scan_text(text: str, name: str) -> list[str]:
    found, fenced = [], False
    for no, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        scrub = line
        for tok in ALLOWED_STATUS_TOKENS:                      # status vocabulary of this repo is explicitly allowed
            scrub = scrub.replace(tok, " ").replace(tok.lower(), " ")
        for rx in (CLAIM_EN, CLAIM_KO):
            for m in rx.finditer(scrub):
                window = scrub[max(0, m.start() - 48):m.end() + 12]
                if not NEGATION.search(window):
                    found.append("%s:%d: unsupported claim '%s'" % (name, no, m.group(0)))
    return found


def scan_json(data, name: str, path: str = "$") -> list[str]:
    found = []
    if isinstance(data, dict):
        for k, v in data.items():
            p = "%s.%s" % (path, k)
            if k == "approval" and isinstance(v, str) and v.upper() not in ALLOWED_APPROVAL_VALUES:
                found.append("%s:%s: approval=%r (expected NOT_APPROVED)" % (name, p, v))
            if k == "frozen" and v is True:
                found.append("%s:%s: frozen=true" % (name, p))
            if k == "review_state" and isinstance(v, str) and re.search(r"APPROVED|FROZEN|FINAL", v) and not re.search(r"NOT_|FOR_LAYOUT_NOT", v):
                found.append("%s:%s: review_state=%r claims approval" % (name, p, v))
            found += scan_json(v, name, p)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            found += scan_json(v, name, "%s[%d]" % (path, i))
    return found


def check_claims(files: list[str]) -> dict:
    found, scanned = [], 0
    for f in files:
        p = Path(f)
        if not p.exists():
            found.append("%s: file not found" % f)
            continue
        scanned += 1
        text = p.read_text(encoding="utf-8", errors="replace")
        if p.suffix.lower() == ".json":
            try:
                found += scan_json(json.loads(text), p.name)
            except json.JSONDecodeError as e:
                found.append("%s: invalid JSON (%s)" % (p.name, e))
        else:
            found += scan_text(text, p.name)
    return {"check": "claims", "ok": not found, "files_scanned": scanned, "violations": found[:80],
            "note": "pattern lint: flags candidates for a human; a clean result is not an approval"}


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")           # a cp949 console must not crash on arrows or check marks
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("sources", "manifests", "diff"):
        p = sub.add_parser(name)
        p.add_argument("--root", default=".")
    sub.choices["diff"].add_argument("--base", required=True, help="PR base ref or starting SHA")
    sub.choices["diff"].add_argument("--protect", action="append", default=[], help="extra protected glob (repeatable)")
    sub.choices["manifests"].add_argument("--manifest", action="append", help="relative manifest path (default: protected_manifests of the config)")
    c = sub.add_parser("claims")
    c.add_argument("files", nargs="+")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "claims":
            res = check_claims(a.files)
        else:
            root = Path(a.root).resolve()
            if a.cmd == "sources":
                res = check_sources(root)
            elif a.cmd == "manifests":
                res = check_manifests(root, a.manifest or load_config()["protected_manifests"])
            else:
                res = check_diff(root, a.base, a.protect)
    except (RuntimeError, OSError, KeyError, ImportError, json.JSONDecodeError) as e:
        print(json.dumps({"check": a.cmd, "ok": False, "error": repr(e)}, ensure_ascii=False))
        return 2
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
