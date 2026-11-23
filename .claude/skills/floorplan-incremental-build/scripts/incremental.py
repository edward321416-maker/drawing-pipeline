"""floorplan-incremental-build helper (stdlib only). It plans, guards and audits a selective rebuild into a NEW output folder.

    incremental.py scope  --base REF --out NEW_DIR --report NEW_REPORT [--baseline OLD_DIR] [--floors 3F 8F] [--root .]
    incremental.py run    --out NEW_DIR --report NEW_REPORT --baseline OLD_DIR --floors 3F 8F [--regression] [--root .]
    incremental.py seed   --baseline OLD_DIR --out NEW_DIR --floors 3F 8F [--root .]
    incremental.py snapshot --outputs DIR --out snap.json [--root .]
    incremental.py verify-untouched --outputs NEW_DIR (--baseline OLD_DIR | --snapshot snap.json) --floors 3F 8F [--expected-floors ...]
    incremental.py change-record --issue ID --floors 3F --outputs NEW_DIR --out records.json [--snapshot snap.json] [--test NAME=PASS|FAIL|NOT_RUN]

The baseline (earlier PR outputs, pinned slices, earlier reports) is never a destination: every path the workflow writes is checked against
the protected list of the drawing-source-guard skill BEFORE anything is created, and the builder and validator receive explicit --out / --report.
Unaffected floors are copied byte-for-byte from the baseline into the new folder, then verified by hash. Manifests fail closed.
The builders and validators stay the project's own (tools/t14s/build_all.py, tools/t14s/validate_t14t.py).
Exit status: 0 = ok, 1 = verification or build failure, 2 = refused (protected or outside-repo destination, bad arguments).
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import importlib.util
import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath

FLOOR = re.compile(r"^(B[1-9]|[1-9][0-9]?F)$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
SHARED_GENERATOR = ["src/**", "tools/*/build*.py", "tools/*/validate*.py", "tools/*/package*.py", "tests/**", ".gitattributes"]
PROVENANCE = {"MODEL_VERIFIED", "APPROVED_DESIGN", "PROPOSED_DESIGN"}
TEST_STATES = {"PASS", "FAIL", "NOT_RUN"}
DEFAULT_BUILD = "python -I tools/t14s/build_all.py --floors {floors} --out {out}"
DEFAULT_VALIDATE = "python -I tools/t14s/validate_t14t.py --floors {floors} --out {out} --report {report}"
DEFAULT_REGRESSION = "python -I tools/t14s/validate_t14t.py --out {out} --report {report}"
SCHEMA = "C-T14-CHANGE-RECORDS-1.0"
SELF = ".claude/skills/floorplan-incremental-build/scripts/incremental.py"
GUARD = ".claude/skills/drawing-source-guard/scripts/guard_check.py"


class DestinationError(ValueError):
    """A path the workflow would write is protected, outside the repository, or the baseline itself."""


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


def _guard():
    """The protected list lives in one place, the drawing-source-guard skill. Without it nothing may be written."""
    p = Path(__file__).resolve().parents[2] / "drawing-source-guard" / "scripts" / "guard_check.py"
    if not p.exists():
        raise DestinationError("drawing-source-guard skill not found: refusing to write anywhere (fail closed)")
    spec = importlib.util.spec_from_file_location("guard_check_for_incremental", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def assert_writable(root, path, label: str) -> Path:
    """Resolved destination, or DestinationError. Called before any directory or file is created."""
    why = _guard().destination_problem(Path(root), str(path))
    if why:
        raise DestinationError("%s: %s" % (label, why))
    return (Path(root).resolve() / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()


def rel_posix(root, p: Path) -> str:
    return p.resolve().relative_to(Path(root).resolve()).as_posix()


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
def plan_scope(paths: list[str], floors: list[str], *, out: str, report: str, baseline: str | None = None,
               build_cmd: str = DEFAULT_BUILD, validate_cmd: str = DEFAULT_VALIDATE, regression_cmd: str = DEFAULT_REGRESSION) -> dict:
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
    fmt = dict(floors=arg, out=out, report=report)
    steps = [{"step": 1, "name": "refuse protected destinations", "cmd": "python -I %s destination --root . %s %s" % (GUARD, out, report)}]
    if baseline:
        steps.append({"step": 2, "name": "seed unaffected floors from the baseline (byte copy)", "cmd": "python -I %s seed --baseline %s --out %s --floors %s" % (SELF, baseline, out, arg)})
    steps.append({"step": len(steps) + 1, "name": "focused build (affected floors only, new output folder)", "cmd": build_cmd.format(**fmt)})
    steps.append({"step": len(steps) + 1, "name": "focused validation (affected floors, new report)", "cmd": validate_cmd.format(**fmt)})
    if scope == "ALL_FLOORS_REGRESSION":
        reg_report = str(PurePosixPath(report).with_name("regression_report.json"))
        steps.append({"step": len(steps) + 1, "name": "cross-floor regression: re-validate every floor against its output", "cmd": regression_cmd.format(floors=arg, out=out, report=reg_report)})
    src = "--baseline %s" % baseline if baseline else "--snapshot <baseline snapshot.json>"
    steps.append({"step": len(steps) + 1, "name": "other floors byte-identical, manifest consistent", "cmd": "python -I %s verify-untouched --outputs %s %s --floors %s" % (SELF, out, src, arg)})
    return {"scope": scope, "floors": fl, "reasons": reasons, "plan": steps, "out": out, "report": report, "baseline": baseline,
            "rule": "never regenerate all floors unless a shared generator changed or the issue names every floor; never write into a baseline"}


# ------------------------------------------------------------------ snapshot, manifest, verification
def snapshot(outputs: Path) -> dict:
    floors = {}
    for d in sorted(p for p in outputs.iterdir() if p.is_dir() and FLOOR.match(p.name)):
        floors[d.name] = {f.name: sha256_file(f) for f in sorted(d.iterdir()) if f.is_file()}
    man = outputs / "SHA256_MANIFEST.json"
    return {"schema": "C-T14-SNAPSHOT-1.0", "outputs": outputs.name, "path": str(outputs.resolve()), "floors": floors,
            "manifest_sha256": sha256_file(man) if man.exists() else None}


def check_manifest(outputs: Path, expected_floors: list[str]) -> list[str]:
    """Problems with outputs/SHA256_MANIFEST.json. An empty list is the only pass: a missing, partial or corrupt manifest never passes."""
    mp = outputs / "SHA256_MANIFEST.json"
    if not mp.exists():
        return ["manifest missing: %s" % mp.name]
    try:
        man = json.loads(mp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return ["manifest is not valid JSON: %s" % e]
    listed = man.get("floors") if isinstance(man, dict) else None
    if not isinstance(listed, dict) or not listed:
        return ["manifest has no floors"]
    problems = []
    on_disk = {d.name: d for d in outputs.iterdir() if d.is_dir() and FLOOR.match(d.name)}
    for f in sorted(set(expected_floors) | set(on_disk)):
        if f not in listed:
            problems.append("floor %s is not in the manifest" % f)
        if f in expected_floors and f not in on_disk:
            problems.append("expected floor %s is missing from the output folder" % f)
    for f, files in sorted(listed.items()):
        if f not in on_disk:
            problems.append("floor %s is listed but has no folder" % f)
            continue
        if not isinstance(files, dict) or not files:
            problems.append("floor %s lists no files" % f)
            continue
        disk = {p.name for p in on_disk[f].iterdir() if p.is_file()}
        for name in sorted(disk - set(files)):
            problems.append("%s/%s is on disk but not in the manifest" % (f, name))
        for name, ent in sorted(files.items()):
            if not isinstance(ent, dict) or "sha256" not in ent or "bytes" not in ent:
                problems.append("%s/%s: malformed manifest entry" % (f, name))
            elif not isinstance(ent["sha256"], str) or not SHA_RE.match(ent["sha256"]):
                problems.append("%s/%s: malformed sha256" % (f, name))
            elif name not in disk:
                problems.append("%s/%s is listed but missing on disk" % (f, name))
            else:
                p = on_disk[f] / name
                if p.stat().st_size != ent["bytes"]:
                    problems.append("%s/%s: size mismatch" % (f, name))
                if sha256_file(p) != ent["sha256"]:
                    problems.append("%s/%s: sha256 mismatch" % (f, name))
    return problems


def verify_untouched(outputs: Path, snap: dict, in_scope: list[str], expected_floors: list[str] | None = None) -> dict:
    if snap.get("path") and snap["path"] == str(outputs.resolve()):
        return {"ok": False, "out_of_scope_violations": ["the verified output folder is the baseline itself: nothing was compared"], "scope_problems": [],
                "manifest_problems": [], "changed_in_scope": {}, "in_scope_unchanged": []}
    now = snapshot(outputs)["floors"]
    violations, scoped_changes, scope_problems = [], {}, []
    for f in sorted(set(snap["floors"]) | set(now)):
        before, after = snap["floors"].get(f, {}), now.get(f, {})
        changed = sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n))
        if f in in_scope:
            scoped_changes[f] = changed
        elif changed:
            violations.append("floor %s is out of scope but %d file(s) changed: %s" % (f, len(changed), changed[:4]))
    for f in in_scope:
        if not now.get(f):
            scope_problems.append("in-scope floor %s was not built (no output files)" % f)
    expected = sorted(set(expected_floors) if expected_floors else set(snap["floors"]) | set(in_scope))
    manifest_problems = check_manifest(outputs, expected)
    return {"ok": not violations and not scope_problems and not manifest_problems, "out_of_scope_violations": violations, "scope_problems": scope_problems,
            "manifest_problems": manifest_problems[:30], "changed_in_scope": scoped_changes, "in_scope_unchanged": sorted(f for f, c in scoped_changes.items() if not c)}


def seed_unaffected(baseline: Path, out: Path, in_scope: list[str]) -> list[str]:
    """Byte-for-byte copy of every baseline floor that is not in scope. Never overwrites a floor already in the new folder."""
    seeded = []
    for d in sorted(p for p in baseline.iterdir() if p.is_dir() and FLOOR.match(p.name) and p.name not in in_scope):
        if not (out / d.name).exists():
            shutil.copytree(d, out / d.name)
            seeded.append(d.name)
    return seeded


# ------------------------------------------------------------------ run
def default_runner(argv: list[str], cwd: Path) -> int:
    argv = [sys.executable if argv[0] == "python" else argv[0], *argv[1:]]
    return subprocess.run(argv, cwd=str(cwd)).returncode


def run_workflow(root, *, out: str, report: str, floors: list[str], baseline: str, build_cmd: str = DEFAULT_BUILD, validate_cmd: str = DEFAULT_VALIDATE,
                 regression: bool = False, regression_cmd: str = DEFAULT_REGRESSION, runner=default_runner) -> dict:
    root = Path(root)
    floors_arg(floors)
    out_p = assert_writable(root, out, "build output folder")
    rep_p = assert_writable(root, report, "validation report")
    reg_rel = str(PurePosixPath(rel_posix(root, rep_p)).with_name("regression_report.json"))
    if regression:
        assert_writable(root, reg_rel, "regression report")
    base_p = (root / baseline).resolve()
    if not base_p.is_dir():
        raise DestinationError("baseline folder %s does not exist" % baseline)
    if base_p == out_p:
        raise DestinationError("baseline %s is also the destination: a build must go to a new task folder" % baseline)
    # ---- every check passed; only now may anything be created
    snap = snapshot(base_p)
    out_rel, rep_rel = rel_posix(root, out_p), rel_posix(root, rep_p)
    out_p.mkdir(parents=True, exist_ok=True)
    seeded = seed_unaffected(base_p, out_p, floors)
    steps, fmt = [], dict(floors=" ".join(floors), out=out_rel, report=rep_rel)

    def finish(failed, verify=None):
        return {"ok": failed is None and bool(verify and verify["ok"]), "failed_step": failed, "steps": steps, "seeded": seeded, "verify": verify, "out": out_rel, "report": rep_rel}

    def step(name, cmd):
        rc = runner(shlex.split(cmd.format(**fmt)), root)
        steps.append({"name": name, "rc": rc, "cmd": cmd.format(**fmt)})
        return rc == 0
    rep_p.parent.mkdir(parents=True, exist_ok=True)
    if not step("focused build (affected floors only, new output folder)", build_cmd):
        return finish("focused build (affected floors only, new output folder)")
    if not step("focused validation (affected floors, new report)", validate_cmd):
        return finish("focused validation (affected floors, new report)")
    if regression:
        fmt["report"] = reg_rel
        if not step("cross-floor regression", regression_cmd):
            return finish("cross-floor regression")
    return finish(None, verify_untouched(out_p, snap, floors))


# ------------------------------------------------------------------ change record
def make_record(issue: str, floors: list[str], outputs: Path, snap: dict | None, tests: dict, decisions: list[str], provenance: str, approval_ref: str | None) -> dict:
    if provenance not in PROVENANCE:
        raise ValueError("provenance must be one of %s" % sorted(PROVENANCE))
    if provenance == "APPROVED_DESIGN" and not approval_ref:
        raise ValueError("APPROVED_DESIGN needs --approval-ref (the user's decision); do not infer approval")
    bad = {k: v for k, v in tests.items() if v not in TEST_STATES}
    if bad:
        raise ValueError("test states must be PASS, FAIL or NOT_RUN: %s" % bad)
    floors_arg(floors)
    files = []
    for f in floors:
        d = outputs / f
        if not d.is_dir():
            raise ValueError("no output folder for floor %s under %s" % (f, outputs))
        for p in sorted(x for x in d.iterdir() if x.is_file()):
            if snap is not None and snap["floors"].get(f, {}).get(p.name) == sha256_file(p):
                continue                                         # unchanged since the baseline: not a generated file of this issue
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

    def common(p):
        p.add_argument("--root", default=".")
    s = sub.add_parser("scope")
    common(s)
    s.add_argument("--base", required=True)
    s.add_argument("--out", required=True, help="NEW task output folder (never a baseline)")
    s.add_argument("--report", required=True, help="NEW validation report path (never an earlier report)")
    s.add_argument("--baseline")
    s.add_argument("--floors", nargs="*", default=[])
    s.add_argument("--build-cmd", default=DEFAULT_BUILD)
    s.add_argument("--validate-cmd", default=DEFAULT_VALIDATE)
    r = sub.add_parser("run")
    common(r)
    r.add_argument("--out", required=True)
    r.add_argument("--report", required=True)
    r.add_argument("--baseline", required=True)
    r.add_argument("--floors", nargs="+", required=True)
    r.add_argument("--build-cmd", default=DEFAULT_BUILD)
    r.add_argument("--validate-cmd", default=DEFAULT_VALIDATE)
    r.add_argument("--regression", action="store_true")
    sd = sub.add_parser("seed")
    common(sd)
    sd.add_argument("--baseline", required=True)
    sd.add_argument("--out", required=True)
    sd.add_argument("--floors", nargs="+", required=True)
    n = sub.add_parser("snapshot")
    common(n)
    n.add_argument("--outputs", required=True)
    n.add_argument("--out", required=True)
    v = sub.add_parser("verify-untouched")
    common(v)
    v.add_argument("--outputs", required=True)
    v.add_argument("--baseline")
    v.add_argument("--snapshot")
    v.add_argument("--floors", nargs="+", required=True)
    v.add_argument("--expected-floors", nargs="*")
    c = sub.add_parser("change-record")
    common(c)
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
    root = Path(a.root).resolve()
    try:
        if a.cmd == "scope":
            assert_writable(root, a.out, "build output folder")
            assert_writable(root, a.report, "validation report")
            res = plan_scope(changed_paths(root, a.base), floors_arg(a.floors), out=a.out, report=a.report, baseline=a.baseline,
                             build_cmd=a.build_cmd, validate_cmd=a.validate_cmd)
            ok = bool(res["floors"])
        elif a.cmd == "run":
            res = run_workflow(root, out=a.out, report=a.report, floors=a.floors, baseline=a.baseline, build_cmd=a.build_cmd,
                               validate_cmd=a.validate_cmd, regression=a.regression)
            ok = res["ok"]
        elif a.cmd == "seed":
            dst = assert_writable(root, a.out, "build output folder")
            dst.mkdir(parents=True, exist_ok=True)
            res, ok = {"seeded": seed_unaffected((root / a.baseline).resolve(), dst, floors_arg(a.floors))}, True
        elif a.cmd == "snapshot":
            dst = assert_writable(root, a.out, "snapshot file")
            snap = snapshot((root / a.outputs).resolve())
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(json.dumps(snap, indent=1), encoding="utf-8")
            res, ok = {"floors": len(snap["floors"]), "files": sum(len(x) for x in snap["floors"].values()), "out": str(dst)}, True
        elif a.cmd == "verify-untouched":
            target = assert_writable(root, a.outputs, "verified build output folder")
            if bool(a.baseline) == bool(a.snapshot):
                raise ValueError("give exactly one of --baseline or --snapshot")
            snap = snapshot((root / a.baseline).resolve()) if a.baseline else json.loads(Path(a.snapshot).read_text(encoding="utf-8"))
            res = verify_untouched(target, snap, floors_arg(a.floors), a.expected_floors)
            ok = res["ok"]
        else:
            dst = assert_writable(root, a.out, "change record file")
            tests = dict(t.split("=", 1) for t in a.test)
            snap = json.loads(Path(a.snapshot).read_text(encoding="utf-8")) if a.snapshot else None
            rec = make_record(a.issue, floors_arg(a.floors), (root / a.outputs).resolve(), snap, tests, a.decision, a.provenance, a.approval_ref)
            upsert(dst, rec)
            res, ok = {"issue_id": rec["issue_id"], "generated_files": len(rec["generated_files"]), "tests_all_pass": rec["tests_all_pass"], "out": str(dst)}, True
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 2 if isinstance(e, ValueError) else 1
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
