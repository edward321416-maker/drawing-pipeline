"""floorplan-incremental-build helper (stdlib only). It plans and audits a selective rebuild; it does not build or validate floors itself.

    incremental.py scope --base REF [--floors 3F 8F] [--root .]        # FLOOR_SCOPED or ALL_FLOORS_REGRESSION + ordered command plan
    incremental.py snapshot --outputs outputs/T14T --out snap.json      # SHA256 of every deliverable, per floor, before the build
    incremental.py verify-untouched --outputs outputs/T14T --snapshot snap.json --floors 3F 8F
    incremental.py change-record --issue ISSUE --floors 3F --outputs outputs/T14T --out change_records.json \
        [--snapshot snap.json] [--test NAME=PASS|FAIL|NOT_RUN] [--decision D-01] [--provenance PROPOSED_DESIGN]

The builders and validators stay the project's own (tools/t14s/build_all.py, tools/t14s/validate_t14t.py).
Exit status: 0 = ok, 1 = violation (untouched floor changed, manifest stale, bad record), 2 = usage error.
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

FLOOR = re.compile(r"^(B[1-9]|[1-9][0-9]?F)$")
SHARED_GENERATOR = ["src/**", "tools/*/build*.py", "tools/*/validate*.py", "tools/*/package*.py", "tests/**", ".gitattributes"]
PROVENANCE = {"MODEL_VERIFIED", "APPROVED_DESIGN", "PROPOSED_DESIGN"}
TEST_STATES = {"PASS", "FAIL", "NOT_RUN"}
DEFAULT_BUILD = "python -I tools/t14s/build_all.py --floors {floors}"
DEFAULT_VALIDATE = "python -I tools/t14s/validate_t14t.py --floors {floors}"
DEFAULT_REGRESSION = "python -I tools/t14s/validate_t14t.py"
SCHEMA = "C-T14-CHANGE-RECORDS-1.0"
SELF = ".claude/skills/floorplan-incremental-build/scripts/incremental.py"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for part in iter(lambda: f.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def glob_match(path: str, pat: str) -> bool:
    path = path.replace("\\", "/")
    if pat.endswith("/**"):
        return path.startswith(pat[:-2])
    return fnmatch.fnmatch(path, pat)


def floors_arg(values: list[str]) -> list[str]:
    bad = [v for v in values if not FLOOR.match(v)]
    if bad:
        raise ValueError("not floor names (expected B1, B2, 2F ... 15F): %s" % bad)
    return values


def changed_paths(root: Path, base: str) -> list[str]:
    def run(*a):
        r = subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, encoding="utf-8")
        if r.returncode:
            raise RuntimeError(r.stderr.strip() or "git failed")
        return r.stdout
    out = set(run("diff", "--name-only", "--no-renames", base + "...HEAD").splitlines())
    for line in run("status", "--porcelain", "--untracked-files=all").splitlines():
        out.add(line[3:].strip().strip('"'))
    return sorted(p for p in out if p)


# ------------------------------------------------------------------ scope
def plan_scope(paths: list[str], floors: list[str], build_cmd=DEFAULT_BUILD, validate_cmd=DEFAULT_VALIDATE, regression_cmd=DEFAULT_REGRESSION) -> dict:
    shared = [p for p in paths if any(glob_match(p, g) for g in SHARED_GENERATOR)]
    from_paths = sorted({m.group(1) for p in paths for m in [re.match(r"outputs/[^/]+/([^/]+)/", p)] if m and FLOOR.match(m.group(1))})
    fl = sorted(set(floors) | set(from_paths), key=lambda f: (f[0] != "B", f))
    reasons = []
    if shared:
        reasons.append("shared generator / test files changed: %s" % ", ".join(shared[:5]))
    if not fl:
        reasons.append("no affected floor given or found in outputs paths")
    scope = "ALL_FLOORS_REGRESSION" if shared else "FLOOR_SCOPED"
    arg = " ".join(fl)
    steps = [{"step": 1, "name": "snapshot deliverables", "cmd": "python -I %s snapshot --outputs <outputs-dir> --out <snapshot.json>" % SELF},
             {"step": 2, "name": "focused build (affected floors only)", "cmd": build_cmd.format(floors=arg)},
             {"step": 3, "name": "focused validation (affected floors)", "cmd": validate_cmd.format(floors=arg)}]
    if scope == "ALL_FLOORS_REGRESSION":
        steps.append({"step": 4, "name": "cross-floor regression: re-validate every floor against its committed output", "cmd": regression_cmd})
    steps.append({"step": len(steps) + 1, "name": "other floors byte-identical, manifest consistent", "cmd": "python -I %s verify-untouched --outputs <outputs-dir> --snapshot <snapshot.json> --floors %s" % (SELF, arg)})
    return {"scope": scope, "floors": fl, "reasons": reasons, "plan": steps, "rule": "never regenerate all floors unless a shared generator changed or the issue names every floor"}


# ------------------------------------------------------------------ snapshot / verify
def snapshot(outputs: Path) -> dict:
    floors = {}
    for d in sorted(p for p in outputs.iterdir() if p.is_dir() and FLOOR.match(p.name)):
        floors[d.name] = {f.name: sha256_file(f) for f in sorted(d.iterdir()) if f.is_file()}
    man = outputs / "SHA256_MANIFEST.json"
    return {"schema": "C-T14-SNAPSHOT-1.0", "outputs": outputs.name, "floors": floors, "manifest_sha256": sha256_file(man) if man.exists() else None}


def verify_untouched(outputs: Path, snap: dict, in_scope: list[str]) -> dict:
    now = snapshot(outputs)["floors"]
    violations, scoped_changes = [], {}
    for f in sorted(set(snap["floors"]) | set(now)):
        before, after = snap["floors"].get(f, {}), now.get(f, {})
        changed = sorted([n for n in set(before) | set(after) if before.get(n) != after.get(n)])
        if f in in_scope:
            scoped_changes[f] = changed
        elif changed:
            violations.append("floor %s is out of scope but %d file(s) changed: %s" % (f, len(changed), changed[:4]))
    stale = []
    man = outputs / "SHA256_MANIFEST.json"
    if man.exists():
        listed = json.loads(man.read_text(encoding="utf-8")).get("floors", {})
        for f in now:
            if f not in listed:
                stale.append("manifest drops floor %s" % f)
        for f, files in listed.items():
            for n, v in files.items():
                p = outputs / f / n
                if not p.exists() or sha256_file(p) != v["sha256"]:
                    stale.append("manifest entry stale: %s/%s" % (f, n))
    return {"ok": not violations and not stale, "out_of_scope_violations": violations, "manifest_problems": stale[:30],
            "changed_in_scope": scoped_changes, "in_scope_unchanged": sorted(f for f, c in scoped_changes.items() if not c)}


# ------------------------------------------------------------------ change record
def make_record(issue: str, floors: list[str], outputs: Path, snap: dict | None, tests: dict, decisions: list[str], provenance: str, approval_ref: str | None) -> dict:
    if provenance not in PROVENANCE:
        raise ValueError("provenance must be one of %s" % sorted(PROVENANCE))
    if provenance == "APPROVED_DESIGN" and not approval_ref:
        raise ValueError("APPROVED_DESIGN needs --approval-ref (the user's decision); do not infer approval")
    bad = {k: v for k, v in tests.items() if v not in TEST_STATES}
    if bad:
        raise ValueError("test states must be PASS, FAIL or NOT_RUN: %s" % bad)
    files = []
    for f in floors:
        d = outputs / f
        if not d.is_dir():
            raise ValueError("no output folder for floor %s under %s" % (f, outputs))
        for p in sorted(x for x in d.iterdir() if x.is_file()):
            if snap is not None and snap["floors"].get(f, {}).get(p.name) == sha256_file(p):
                continue                                         # unchanged since the snapshot: not a generated file of this issue
            files.append({"path": "%s/%s/%s" % (outputs.name, f, p.name), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    return {"issue_id": issue, "floors": floors, "provenance": provenance, "approval_ref": approval_ref, "generated_files": files,
            "tests": tests, "tests_all_pass": bool(tests) and all(v == "PASS" for v in tests.values()), "unresolved_decisions": sorted(set(decisions))}


def upsert(path: Path, rec: dict) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"schema": SCHEMA, "records": []}
    doc["records"] = sorted([r for r in doc["records"] if r["issue_id"] != rec["issue_id"]] + [rec], key=lambda r: r["issue_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return doc


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")           # a cp949 console must not crash on arrows or check marks
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scope")
    s.add_argument("--base", required=True)
    s.add_argument("--floors", nargs="*", default=[])
    s.add_argument("--root", default=".")
    s.add_argument("--build-cmd", default=DEFAULT_BUILD)
    s.add_argument("--validate-cmd", default=DEFAULT_VALIDATE)
    n = sub.add_parser("snapshot")
    n.add_argument("--outputs", required=True)
    n.add_argument("--out", required=True)
    v = sub.add_parser("verify-untouched")
    v.add_argument("--outputs", required=True)
    v.add_argument("--snapshot", required=True)
    v.add_argument("--floors", nargs="+", required=True)
    c = sub.add_parser("change-record")
    c.add_argument("--issue", required=True)
    c.add_argument("--floors", nargs="+", required=True)
    c.add_argument("--outputs", required=True)
    c.add_argument("--out", required=True)
    c.add_argument("--snapshot")
    c.add_argument("--test", action="append", default=[], help="NAME=PASS|FAIL|NOT_RUN")
    c.add_argument("--decision", action="append", default=[])
    c.add_argument("--provenance", default="PROPOSED_DESIGN")
    c.add_argument("--approval-ref")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "scope":
            res = plan_scope(changed_paths(Path(a.root).resolve(), a.base), floors_arg(a.floors), a.build_cmd, a.validate_cmd)
            ok = bool(res["floors"])
        elif a.cmd == "snapshot":
            res = snapshot(Path(a.outputs))
            Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
            res, ok = {"floors": len(res["floors"]), "files": sum(len(v) for v in res["floors"].values()), "out": str(Path(a.out).resolve())}, True
        elif a.cmd == "verify-untouched":
            res = verify_untouched(Path(a.outputs), json.loads(Path(a.snapshot).read_text(encoding="utf-8")), floors_arg(a.floors))
            ok = res["ok"]
        else:
            tests = dict(t.split("=", 1) for t in a.test)
            snap = json.loads(Path(a.snapshot).read_text(encoding="utf-8")) if a.snapshot else None
            rec = make_record(a.issue, floors_arg(a.floors), Path(a.outputs), snap, tests, a.decision, a.provenance, a.approval_ref)
            upsert(Path(a.out), rec)
            res, ok = {"issue_id": rec["issue_id"], "generated_files": len(rec["generated_files"]), "tests_all_pass": rec["tests_all_pass"], "out": str(Path(a.out).resolve())}, True
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 2 if isinstance(e, ValueError) else 1
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
