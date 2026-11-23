"""github-visual-review-packet checks. Reuses tools/t14r/export_visual_review.py (pack / verify) and adds what it does not cover.

    packet_check.py local  --packet docs/<task>/review_packet [--root .]
    packet_check.py remote --packet docs/<task>/review_packet --repo OWNER/REPO --ref <commit SHA> [--root .] [--sample 6]

local : T14R verify (tile coverage, pixel SHA) + every file in the packet is listed in the manifest + each size within the item budget
        + README present + no packet text claiming a readback. github_readback is always NOT_TESTED here: a local readback_report.json is
        reported as PRESENT_NOT_INDEPENDENT_PROOF and never counted, because only the reviewer can confirm a connector readback.
remote: after the push, compares the packet's git blob SHAs with the GitHub tree of <ref> and downloads a sample of files raw
        (preview, overview, first tile per asset) to check they are non-empty and byte-identical.
        This is REMOTE_BYTE_IDENTITY. It is not a ChatGPT connector readback and never reports one.
Exit status: 0 = pass, 1 = failed check, 2 = usage / environment error.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

MAGIC = {".png": b"\x89PNG\r\n\x1a\n", ".jpg": b"\xff\xd8"}
README_NAMES = ("README.md", "manifest.json")


def load_t14r(root: Path):
    p = root / "tools" / "t14r" / "export_visual_review.py"
    spec = importlib.util.spec_from_file_location("t14r_export_visual_review", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def listed_files(manifest: dict) -> set[str]:
    out = {manifest["overview"]["path"]}
    for a in manifest["assets"]:
        out.add(a["preview"]["path"])
        out.update(t["path"] for t in a["tiles"])
    return out


def local_check(packet: Path, root: Path) -> dict:
    problems = []
    try:
        res = load_t14r(root).verify_packet(packet)
    except Exception as e:  # noqa: BLE001 - any verify failure is a failed check, reported verbatim
        return {"check": "local", "ok": False, "t14r_verify": "FAIL: %r" % e, "problems": [repr(e)]}
    man = json.loads((packet / "manifest.json").read_text(encoding="utf-8"))
    want = listed_files(man)
    disk = {p.relative_to(packet).as_posix() for p in packet.rglob("*") if p.is_file()}
    orphans = sorted(disk - want - set(README_NAMES) - {"readback_report.json"})
    missing = sorted(want - disk)
    big = sorted(p for p in want & disk if (packet / p).stat().st_size > man["max_item_bytes"])
    if orphans:
        problems.append("files not listed in manifest: %s" % orphans[:5])
    if missing:
        problems.append("manifest files missing: %s" % missing[:5])
    if big:
        problems.append("over item budget (%d B): %s" % (man["max_item_bytes"], big[:5]))
    if not (packet / "README.md").exists():
        problems.append("README.md missing")
    problems += readback_claims(packet)
    warnings = []
    local_report = "ABSENT"
    if (packet / "readback_report.json").exists():
        local_report = "PRESENT_NOT_INDEPENDENT_PROOF"
        warnings.append("readback_report.json is a local file: it is not independent proof of a reviewer readback and is not counted")
    return {"check": "local", "ok": not problems, "t14r_verify": res["status"], "assets": res["assets"], "tiles": res["tiles"],
            "github_readback": "NOT_TESTED", "local_readback_report": local_report, "problems": problems, "warnings": warnings,
            "note": "bytes and pixels only; connector readback is confirmed only by the reviewer's own review, never by a file in the packet"}


READBACK_CLAIM = re.compile(r"read-?back\b[^.\n]{0,60}?\b(pass(?:ed)?|verified|confirmed|ok|succe(?:ss|eded))\b", re.I)
NEGATION = re.compile(r"\b(not|never|no|un\w+|without|pending|awaiting|if|until|before)\b", re.I)


def readback_claims(packet: Path) -> list[str]:
    """Text inside the packet that states a readback happened. Only the reviewer can confirm one, so any such claim is a problem."""
    found = []
    for p in sorted(packet.rglob("*.md")):
        for no, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for m in READBACK_CLAIM.finditer(line):
                if not NEGATION.search(line[max(0, m.start() - 24):m.end()]):
                    found.append("%s:%d: claims a readback (%r); only the reviewer's own review can confirm one" % (p.name, no, m.group(0)))
    return found


# ------------------------------------------------------------------ remote
def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def gh_runner(args: list[str]) -> bytes:
    r = subprocess.run(["gh", "api", *args], capture_output=True)
    if r.returncode:
        raise RuntimeError(r.stderr.decode("utf-8", "replace")[:300])
    return r.stdout


def sample_files(man: dict, n: int) -> list[str]:
    picks = [man["overview"]["path"]]
    for a in man["assets"]:
        picks += [a["preview"]["path"], a["tiles"][0]["path"]]
    if not n or len(picks) <= n:
        return picks
    return [picks[i * len(picks) // n] for i in range(n)]            # evenly spread, deterministic


def remote_check(packet: Path, prefix: str, repo: str, ref: str, sample: int = 6, runner=gh_runner) -> dict:
    man = json.loads((packet / "manifest.json").read_text(encoding="utf-8"))
    tree = json.loads(runner(["repos/%s/git/trees/%s?recursive=1" % (repo, ref)]))
    if tree.get("truncated"):
        return {"check": "remote", "ok": False, "problems": ["GitHub tree truncated: cannot confirm; verify files individually"]}
    remote = {e["path"]: e["sha"] for e in tree["tree"] if e["type"] == "blob"}
    files = sorted(p.relative_to(packet).as_posix() for p in packet.rglob("*") if p.is_file())
    absent, differ = [], []
    for rel in files:
        key = prefix + rel
        if key not in remote:
            absent.append(rel)
        elif remote[key] != git_blob_sha((packet / rel).read_bytes()):
            differ.append(rel)
    bad, downloaded = [], 0
    for rel in sample_files(man, sample):
        if prefix + rel not in remote:
            continue                                                       # already counted as absent
        downloaded += 1
        data = runner(["-H", "Accept: application/vnd.github.raw", "repos/%s/contents/%s%s?ref=%s" % (repo, prefix, rel, ref)])
        magic = MAGIC.get(Path(rel).suffix.lower())
        if not data or data != (packet / rel).read_bytes() or (magic and not data.startswith(magic)):
            bad.append(rel)
    problems = (["not on remote: %s" % absent[:5]] if absent else []) + (["blob SHA differs: %s" % differ[:5]] if differ else []) + (["raw download empty/different: %s" % bad[:5]] if bad else [])
    return {"check": "remote", "ok": not problems, "ref": ref, "files_compared": len(files), "raw_downloaded": downloaded,
            "status": "REMOTE_BYTE_IDENTITY_PASS" if not problems else "REMOTE_BYTE_IDENTITY_FAIL", "problems": problems,
            "github_readback": "NOT_TESTED", "note": "this is not a ChatGPT connector readback"}


def repo_prefix(packet: Path) -> str:
    r = subprocess.run(["git", "-C", str(packet), "rev-parse", "--show-prefix"], capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError("packet is not inside a git work tree")
    return r.stdout.strip()


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")           # a cp949 console must not crash on arrows or check marks
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("local", "remote"):
        p = sub.add_parser(n)
        p.add_argument("--packet", required=True)
        p.add_argument("--root", default=".")
    r = sub.choices["remote"]
    r.add_argument("--repo", required=True)
    r.add_argument("--ref", required=True)
    r.add_argument("--sample", type=int, default=6)
    a = ap.parse_args(argv)
    packet, root = Path(a.packet).resolve(), Path(a.root).resolve()
    try:
        res = local_check(packet, root) if a.cmd == "local" else remote_check(packet, repo_prefix(packet), a.repo, a.ref, a.sample)
    except (OSError, RuntimeError, KeyError, json.JSONDecodeError) as e:
        print(json.dumps({"check": a.cmd, "ok": False, "error": repr(e)}, ensure_ascii=False))
        return 2
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
