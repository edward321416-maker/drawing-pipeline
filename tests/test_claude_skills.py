"""Tests for the project skill library in .claude/skills (C-T14-SKILLS).

Positive and negative tests per skill. Select one skill with -k source_guard | incremental | circulation | packet | harvester | lint.
These tests prove the scripts behave as documented. They do not prove an agent follows the skill, and they approve no drawing.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SK = ROOT / ".claude" / "skills"
FX = Path(__file__).resolve().parent / "fixtures" / "claude_skills"


def load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


guard = load(".claude/skills/drawing-source-guard/scripts/guard_check.py", "sk_guard")
inc = load(".claude/skills/floorplan-incremental-build/scripts/incremental.py", "sk_inc")
circ = load(".claude/skills/vertical-circulation-audit/scripts/circulation_audit.py", "sk_circ")
pkt = load(".claude/skills/github-visual-review-packet/scripts/packet_check.py", "sk_pkt")
reg = load(".claude/skills/skill-harvester/scripts/registry.py", "sk_reg")
lint = load("tools/claude_skills/skill_lint.py", "sk_lint")

HAVE_T14T = (ROOT / "outputs" / "T14T" / "SHA256_MANIFEST.json").exists()


def git(repo: Path, *a: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *a], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# =============================================================== drawing-source-guard
@pytest.fixture()
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    for rel, data in {"data/t14s/source_slices/floor_2F_slice.json": b'{"v":1}', "outputs/T14T/3F/a.svg": b"<svg/>", "src/x.py": b"x=1\n"}.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def test_source_guard_clean_change_passes(repo):
    base = git(repo, "rev-parse", "HEAD")
    (repo / "docs/t14u").mkdir(parents=True)
    (repo / "docs/t14u/notes.md").write_text("new work", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "new")
    assert guard.check_diff(repo, base, [])["ok"]


@pytest.mark.parametrize("rel", ["outputs/T14T/3F/a.svg", "data/t14s/source_slices/floor_2F_slice.json"])
def test_source_guard_committed_edit_of_protected_file_fails(repo, rel):
    base = git(repo, "rev-parse", "HEAD")
    (repo / rel).write_bytes(b"changed")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "edit")
    res = guard.check_diff(repo, base, [])
    assert not res["ok"] and any(rel in v for v in res["violations"])


def test_source_guard_uncommitted_edit_and_new_protected_file_fail(repo):
    base = git(repo, "rev-parse", "HEAD")
    (repo / "outputs/T14T/3F/a.svg").write_bytes(b"dirty")
    (repo / "outputs/T14T/3F/extra.svg").write_bytes(b"new")
    res = guard.check_diff(repo, base, [])
    assert not res["ok"] and res["violation_count"] == 2


def test_source_guard_extra_protect_pattern(repo):
    base = git(repo, "rev-parse", "HEAD")
    (repo / "src/x.py").write_text("x=2\n", encoding="utf-8")
    assert guard.check_diff(repo, base, [])["ok"]
    assert not guard.check_diff(repo, base, ["src/**"])["ok"]


def _manifest(root: Path, files: dict[str, bytes]):
    man = {"floors": {}}
    for rel, data in files.items():
        floor, name = rel.split("/")
        (root / "outputs/T14T" / floor).mkdir(parents=True, exist_ok=True)
        (root / "outputs/T14T" / rel).write_bytes(data)
        man["floors"].setdefault(floor, {})[name] = {"sha256": sha(data), "bytes": len(data)}
    (root / "outputs/T14T/SHA256_MANIFEST.json").write_text(json.dumps(man), encoding="utf-8")


def test_source_guard_manifest_matches_then_detects_tamper_and_loss(tmp_path):
    _manifest(tmp_path, {"3F/a.svg": b"aaa", "3F/b.dxf": b"bbb"})
    rel = ["outputs/T14T/SHA256_MANIFEST.json"]
    assert guard.check_manifests(tmp_path, rel)["ok"]
    (tmp_path / "outputs/T14T/3F/a.svg").write_bytes(b"tampered")
    res = guard.check_manifests(tmp_path, rel)
    assert not res["ok"] and "sha mismatch: outputs/T14T/SHA256_MANIFEST.json/3F/a.svg" in res["problems"]
    (tmp_path / "outputs/T14T/3F/b.dxf").unlink()
    assert any(p.startswith("missing") for p in guard.check_manifests(tmp_path, rel)["problems"])
    assert not guard.check_manifests(tmp_path, ["outputs/none/SHA256_MANIFEST.json"])["ok"]


def test_source_guard_flat_slice_manifest_layout(tmp_path):
    d = tmp_path / "data/t14s/source_slices"
    d.mkdir(parents=True)
    (d / "s.json").write_bytes(b"{}")
    (d / "manifest.json").write_text(json.dumps({"files": {"s.json": sha(b"{}")}}), encoding="utf-8")
    assert guard.check_manifests(tmp_path, ["data/t14s/source_slices/manifest.json"])["ok"]
    (d / "s.json").write_bytes(b'{"x":1}')
    assert not guard.check_manifests(tmp_path, ["data/t14s/source_slices/manifest.json"])["ok"]


@pytest.mark.skipif(not HAVE_T14T, reason="C-T14T outputs not on this branch")
def test_source_guard_real_repo_pins_and_manifests_hold():
    assert guard.check_sources(ROOT)["ok"]
    res = guard.check_manifests(ROOT, guard.load_config()["protected_manifests"])
    assert res["ok"] and res["files_checked"] >= 200


def test_source_guard_protected_list_covers_baselines_and_1f_reference():
    cfg = guard.load_config()
    assert all(g.endswith("/**") for g in cfg["protected_globs"])
    assert "outputs/T14S/**" in cfg["protected_globs"] and "data/t14s/source_slices/**" in cfg["protected_globs"]
    assert "docs/t14s_floor_plans/**" in cfg["protected_globs"]           # holds the preserved 1F reference
    assert (ROOT / "docs/t14s_floor_plans/reference_1F").is_dir()


def test_source_guard_claims_positive_and_negative():
    ok = ["clean.md", "negated.md", "metadata_ok.json"]
    assert all(guard.check_claims([str(FX / "claims" / n)])["ok"] for n in ok)
    for n in ["approval_claim.md", "approval_claim_ko.md", "metadata_bad.json"]:
        res = guard.check_claims([str(FX / "claims" / n)])
        assert not res["ok"], n
    bad = guard.check_claims([str(FX / "claims" / "metadata_bad.json")])["violations"]
    assert len(bad) == 3                                                   # approval, frozen, review_state
    assert "approved" in " ".join(guard.check_claims([str(FX / "claims" / "approval_claim.md")])["violations"])


def test_source_guard_claims_missing_file_is_a_violation():
    assert not guard.check_claims([str(FX / "claims" / "nope.md")])["ok"]


@pytest.mark.skipif(not HAVE_T14T, reason="C-T14T outputs not on this branch")
def test_source_guard_real_t14t_metadata_and_readme_make_no_approval_claim():
    files = [ROOT / "docs/t14t_corrections/README.md", ROOT / "outputs/T14T/2F/T14T_2F_plan_metadata.json"]
    assert guard.check_claims([str(f) for f in files])["ok"]


def test_source_guard_cli_exit_codes(repo, capsys):
    base = git(repo, "rev-parse", "HEAD")
    assert guard.main(["diff", "--base", base, "--root", str(repo)]) == 0
    (repo / "outputs/T14T/3F/a.svg").write_bytes(b"x")
    assert guard.main(["diff", "--base", base, "--root", str(repo)]) == 1
    assert guard.main(["diff", "--base", "no-such-ref", "--root", str(repo)]) == 2
    capsys.readouterr()


# =============================================================== floorplan-incremental-build
def put(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def write_manifest(out: Path):
    man = {"floors": {}}
    for d in sorted(p for p in out.iterdir() if p.is_dir()):
        man["floors"][d.name] = {f.name: {"sha256": sha(f.read_bytes()), "bytes": f.stat().st_size} for f in sorted(d.iterdir()) if f.is_file()}
    (out / "SHA256_MANIFEST.json").write_text(json.dumps(man), encoding="utf-8")


def make_outputs(root: Path, name: str, floors=("2F", "3F", "4F")) -> Path:
    out = root / "outputs" / name
    for f in floors:
        put(out / f / "a.svg", b"<svg " + f.encode() + b"/>")
        put(out / f / "b.dxf", b"dxf " + f.encode())
    write_manifest(out)
    return out


def tree_hashes(out: Path) -> dict:
    return {p.relative_to(out).as_posix(): sha(p.read_bytes()) for p in sorted(out.rglob("*")) if p.is_file()}


def arg_after(argv, flag):
    return argv[argv.index(flag) + 1]


class FakeTools:
    """Stands in for the project builder and validator: writes only what the real ones would write, records every call."""

    def __init__(self, build_rc=0, validate_rc=0, also_touch=None):
        self.calls, self.build_rc, self.validate_rc, self.also_touch = [], build_rc, validate_rc, also_touch

    def __call__(self, argv, cwd):
        self.calls.append(list(argv))
        out = Path(cwd) / arg_after(argv, "--out")
        if "--report" in argv:                                                   # validator
            put(Path(cwd) / arg_after(argv, "--report"), b'{"ok": true}')
            return self.validate_rc
        for f in arg_after(argv, "--floors").split():                           # builder
            put(out / f / "a.svg", b"<svg rebuilt " + f.encode() + b"/>")
            put(out / f / "b.dxf", b"dxf " + f.encode())                         # same bytes as the baseline: only a.svg really changes
        if self.also_touch:
            put(out / self.also_touch / "a.svg", b"<svg leaked change/>")
        write_manifest(out)
        return self.build_rc


PROTECTED_DESTINATIONS = ["outputs/T14T", "outputs/t14t", "OUTPUTS/T14T/3F", "outputs/./T14T", "outputs/new/../T14T", "outputs/T14S/2F/x.svg",
                          "docs/t14t_corrections/build_test_report.json", "docs/t14s_floor_plans", "data/t14s/source_slices/floor_2F_slice.json",
                          "docs/decisions/note.md", "../elsewhere"]


@pytest.mark.parametrize("dest", PROTECTED_DESTINATIONS)
def test_incremental_protected_destinations_are_refused(tmp_path, dest):
    with pytest.raises(inc.DestinationError):
        inc.assert_writable(tmp_path, dest, "build output")


@pytest.mark.parametrize("dest", ["outputs/T14U", "docs/t14u/build_test_report.json", "outputs/T14T_next"])
def test_incremental_new_task_destinations_are_allowed(tmp_path, dest):
    assert inc.assert_writable(tmp_path, dest, "build output") == (tmp_path / dest).resolve()


def test_incremental_guard_destination_check_agrees_with_the_workflow(tmp_path):
    res = guard.check_destination(tmp_path, ["outputs/T14T", "outputs/T14U"])
    assert not res["ok"] and len(res["violations"]) == 1 and "outputs/T14T" in res["violations"][0]
    assert guard.check_destination(tmp_path, ["outputs/T14U", "docs/t14u/r.json"])["ok"]
    assert guard.main(["destination", "--root", str(tmp_path), "outputs/t14t"]) == 1


def test_incremental_defaults_never_point_at_a_baseline_and_pass_out_and_report():
    assert "{out}" in inc.DEFAULT_BUILD and "--out" in inc.DEFAULT_BUILD
    assert "{out}" in inc.DEFAULT_VALIDATE and "{report}" in inc.DEFAULT_VALIDATE and "--report" in inc.DEFAULT_VALIDATE
    assert "T14T" not in inc.DEFAULT_BUILD + inc.DEFAULT_VALIDATE + inc.DEFAULT_REGRESSION


def test_incremental_scope_requires_a_new_out_and_report_and_passes_them_explicitly():
    with pytest.raises(TypeError):
        inc.plan_scope(["outputs/T14U/3F/x.svg"], [])
    res = inc.plan_scope(["outputs/T14U/3F/x.svg", "docs/t14u/readme.md"], [], out="outputs/T14U", report="docs/t14u/report.json", baseline="outputs/T14T")
    cmds = [s["cmd"] for s in res["plan"]]
    assert res["scope"] == "FLOOR_SCOPED" and res["floors"] == ["3F"]
    build = next(c for c in cmds if "build" in c)
    validate = next(c for c in cmds if "validate" in c)
    assert "--out outputs/T14U" in build and "--floors 3F" in build
    assert "--out outputs/T14U" in validate and "--report docs/t14u/report.json" in validate
    assert not any("--out outputs/T14T" in c for c in cmds)
    names = [s["name"] for s in res["plan"]]
    assert names[0].startswith("refuse protected") and any(n.startswith("seed") for n in names) and names[-1].startswith("other floors")


@pytest.mark.parametrize("path", ["src/t14s/planner.py", "tools/t14s/validate_t14t.py", "tools/t14s/build_all.py", "tests/test_x.py"])
def test_incremental_shared_generator_change_widens_scope_with_a_regression_pass(path):
    res = inc.plan_scope([path], ["3F"], out="outputs/T14U", report="docs/t14u/report.json", baseline="outputs/T14T")
    assert res["scope"] == "ALL_FLOORS_REGRESSION" and res["reasons"]
    reg = next(s for s in res["plan"] if "cross-floor regression" in s["name"])
    assert "--out outputs/T14U" in reg["cmd"] and "--report docs/t14u/regression_report.json" in reg["cmd"] and "--floors" not in reg["cmd"]
    assert [s["step"] for s in res["plan"]] == sorted(s["step"] for s in res["plan"])


def test_incremental_floors_sorted_and_validated():
    kw = dict(out="outputs/T14U", report="docs/t14u/report.json", baseline="outputs/T14T")
    assert inc.plan_scope([], ["10F", "B1", "2F"], **kw)["floors"] == ["B1", "10F", "2F"]
    assert inc.plan_scope([], [], **kw)["floors"] == []
    for bad in (["3rd floor"], ["B0"]):
        with pytest.raises(ValueError):
            inc.floors_arg(bad)


def test_incremental_run_refuses_protected_out_or_report_before_anything_runs(tmp_path):
    base = make_outputs(tmp_path, "T14T")
    before = tree_hashes(base)
    tools = FakeTools()
    for out, report in [("outputs/T14T", "docs/t14u/r.json"), ("outputs/t14t", "docs/t14u/r.json"), ("outputs/T14U", "docs/t14t_corrections/build_test_report.json"),
                        ("outputs/T14S", "docs/t14u/r.json")]:
        with pytest.raises(inc.DestinationError):
            inc.run_workflow(tmp_path, out=out, report=report, floors=["3F"], baseline="outputs/T14T", runner=tools)
    assert tools.calls == [] and tree_hashes(base) == before
    assert not (tmp_path / "outputs" / "T14U").exists() and not (tmp_path / "docs").exists()            # not even the allowed half was created


def test_incremental_run_refuses_a_baseline_that_is_also_the_destination(tmp_path):
    make_outputs(tmp_path, "T14U")
    with pytest.raises(inc.DestinationError, match="baseline"):
        inc.run_workflow(tmp_path, out="outputs/T14U", report="docs/t14u/r.json", floors=["3F"], baseline="outputs/T14U", runner=FakeTools())


def test_incremental_run_builds_into_a_new_dir_and_keeps_unaffected_floors_byte_identical(tmp_path):
    base = make_outputs(tmp_path, "T14T")
    before = tree_hashes(base)
    tools = FakeTools()
    res = inc.run_workflow(tmp_path, out="outputs/T14U", report="docs/t14u/report.json", floors=["3F"], baseline="outputs/T14T", runner=tools)
    new = tmp_path / "outputs" / "T14U"
    assert res["ok"] and res["verify"]["ok"] and tree_hashes(base) == before                           # baseline untouched
    assert sorted(p.name for p in new.iterdir() if p.is_dir()) == ["2F", "3F", "4F"]
    now = tree_hashes(new)
    assert now["2F/a.svg"] == before["2F/a.svg"] and now["4F/b.dxf"] == before["4F/b.dxf"]             # unaffected floors copied unchanged
    assert now["3F/a.svg"] != before["3F/a.svg"] and res["verify"]["changed_in_scope"]["3F"] == ["a.svg"]
    build, validate = tools.calls
    assert arg_after(build, "--out") == "outputs/T14U" and arg_after(build, "--floors") == "3F"
    assert arg_after(validate, "--out") == "outputs/T14U" and arg_after(validate, "--report") == "docs/t14u/report.json"
    assert (tmp_path / "docs/t14u/report.json").exists() and "outputs/T14T" not in " ".join(build + validate)


def test_incremental_run_fails_when_the_builder_touches_an_unaffected_floor(tmp_path):
    make_outputs(tmp_path, "T14T")
    res = inc.run_workflow(tmp_path, out="outputs/T14U", report="docs/t14u/report.json", floors=["3F"], baseline="outputs/T14T", runner=FakeTools(also_touch="2F"))
    assert not res["ok"] and "floor 2F is out of scope" in res["verify"]["out_of_scope_violations"][0]


def test_incremental_run_stops_when_the_builder_or_validator_fails(tmp_path):
    make_outputs(tmp_path, "T14T")
    tools = FakeTools(build_rc=3)
    res = inc.run_workflow(tmp_path, out="outputs/T14U", report="docs/t14u/report.json", floors=["3F"], baseline="outputs/T14T", runner=tools)
    assert not res["ok"] and len(tools.calls) == 1 and res["failed_step"].startswith("focused build")
    tools = FakeTools(validate_rc=1)
    res = inc.run_workflow(tmp_path, out="outputs/T14V", report="docs/t14v/report.json", floors=["3F"], baseline="outputs/T14T", runner=tools)
    assert not res["ok"] and res["failed_step"].startswith("focused validation")


def test_incremental_cli_run_refuses_a_protected_baseline_destination(tmp_path, capsys):
    base = make_outputs(tmp_path, "T14T")
    before = tree_hashes(base)
    code = inc.main(["run", "--root", str(tmp_path), "--out", "outputs/T14T", "--report", "docs/t14u/r.json", "--floors", "3F", "--baseline", "outputs/T14T",
                     "--build-cmd", "no-such-builder --out {out} --floors {floors}"])
    assert code == 2 and "protected" in capsys.readouterr().out.lower() and tree_hashes(base) == before


def test_incremental_snapshot_and_change_record_destinations_are_guarded(tmp_path, capsys):
    base = make_outputs(tmp_path, "T14T")
    assert inc.main(["snapshot", "--root", str(tmp_path), "--outputs", "outputs/T14T", "--out", "outputs/T14T/snap.json"]) == 2
    assert not (base / "snap.json").exists()
    assert inc.main(["change-record", "--root", str(tmp_path), "--issue", "I-1", "--floors", "3F", "--outputs", "outputs/T14T",
                     "--out", "docs/t14t_corrections/change_records.json"]) == 2
    assert not (tmp_path / "docs").exists()
    assert inc.main(["snapshot", "--root", str(tmp_path), "--outputs", "outputs/T14T", "--out", "docs/t14u/snap.json"]) == 0
    capsys.readouterr()


# ---- verification and manifests (fail closed)
def test_incremental_verify_passes_for_a_complete_consistent_output(tmp_path):
    base = make_outputs(tmp_path, "T14T")
    snap = inc.snapshot(base)
    new = make_outputs(tmp_path, "T14U")
    put(new / "3F" / "a.svg", b"<svg rebuilt/>")
    write_manifest(new)
    res = inc.verify_untouched(new, snap, ["3F"])
    assert res["ok"] and res["manifest_problems"] == [] and res["changed_in_scope"] == {"3F": ["a.svg"]}


def test_incremental_verify_rejects_the_baseline_as_its_own_output(tmp_path):
    base = make_outputs(tmp_path, "T14T")
    res = inc.verify_untouched(base, inc.snapshot(base), ["3F"])
    assert not res["ok"] and "baseline itself" in " ".join(res["manifest_problems"] + res["out_of_scope_violations"] + res["scope_problems"])


def test_incremental_verify_detects_untouched_floor_change_missing_floor_and_unbuilt_scope_floor(tmp_path):
    base = make_outputs(tmp_path, "T14T")
    snap = inc.snapshot(base)
    new = make_outputs(tmp_path, "T14U")
    put(new / "2F" / "b.dxf", b"leaked change")
    write_manifest(new)
    res = inc.verify_untouched(new, snap, ["3F"])
    assert not res["ok"] and "floor 2F is out of scope" in res["out_of_scope_violations"][0] and res["in_scope_unchanged"] == ["3F"]
    shutil.rmtree(new / "4F")
    write_manifest(new)
    assert any("floor 4F" in v for v in inc.verify_untouched(new, snap, ["3F"])["out_of_scope_violations"])
    shutil.rmtree(new / "3F")
    write_manifest(new)
    assert any("3F" in p for p in inc.verify_untouched(new, snap, ["3F"])["scope_problems"])


def _edit_manifest(fn):
    def go(out: Path):
        p = out / "SHA256_MANIFEST.json"
        m = json.loads(p.read_text(encoding="utf-8"))
        fn(m)
        p.write_text(json.dumps(m), encoding="utf-8")
    return go


MANIFEST_BREAKS = {
    "missing_manifest": (lambda o: (o / "SHA256_MANIFEST.json").unlink(), ["2F", "3F"], "manifest missing"),
    "invalid_json": (lambda o: (o / "SHA256_MANIFEST.json").write_text("{not json", encoding="utf-8"), ["2F", "3F"], "not valid JSON"),
    "no_floors_key": (lambda o: (o / "SHA256_MANIFEST.json").write_text('{"x": 1}', encoding="utf-8"), ["2F", "3F"], "no floors"),
    "empty_floors": (lambda o: (o / "SHA256_MANIFEST.json").write_text('{"floors": {}}', encoding="utf-8"), ["2F", "3F"], "no floors"),
    "floor_omitted": (_edit_manifest(lambda m: m["floors"].pop("3F")), ["2F", "3F"], "floor 3F is not in the manifest"),
    "floor_without_files": (_edit_manifest(lambda m: m["floors"].__setitem__("3F", {})), ["2F", "3F"], "lists no files"),
    "file_not_listed": (lambda o: put(o / "3F" / "extra.png", b"x"), ["2F", "3F"], "3F/extra.png is on disk but not in the manifest"),
    "listed_file_missing": (lambda o: (o / "3F" / "b.dxf").unlink(), ["2F", "3F"], "3F/b.dxf is listed but missing on disk"),
    "hash_corrupted": (lambda o: put(o / "3F" / "a.svg", b"tampered"), ["2F", "3F"], "3F/a.svg: sha256 mismatch"),
    "size_mismatch": (_edit_manifest(lambda m: m["floors"]["3F"]["a.svg"].__setitem__("bytes", 1)), ["2F", "3F"], "3F/a.svg: size mismatch"),
    "entry_malformed": (_edit_manifest(lambda m: m["floors"]["3F"].__setitem__("a.svg", "abc")), ["2F", "3F"], "3F/a.svg: malformed manifest entry"),
    "sha_malformed": (_edit_manifest(lambda m: m["floors"]["3F"]["a.svg"].__setitem__("sha256", "123")), ["2F", "3F"], "3F/a.svg: malformed sha256"),
    "listed_floor_has_no_folder": (_edit_manifest(lambda m: m["floors"].__setitem__("4F", {"a.svg": {"sha256": "0" * 64, "bytes": 1}})), ["2F", "3F"], "floor 4F is listed but has no folder"),
    "expected_floor_absent": (lambda o: None, ["2F", "3F", "4F"], "expected floor 4F is missing"),
}


@pytest.mark.parametrize("name", sorted(MANIFEST_BREAKS))
def test_incremental_manifest_problems_fail_closed(tmp_path, name):
    out = make_outputs(tmp_path, "T14U", floors=("2F", "3F"))
    assert inc.check_manifest(out, ["2F", "3F"]) == []                                  # the unbroken output passes
    mutate, expected, needle = MANIFEST_BREAKS[name]
    mutate(out)
    problems = inc.check_manifest(out, expected)
    assert any(needle in p for p in problems), problems


def test_incremental_verify_fails_when_the_manifest_is_missing_or_partial(tmp_path):
    snap = inc.snapshot(make_outputs(tmp_path, "T14T"))
    new = make_outputs(tmp_path, "T14U")
    (new / "SHA256_MANIFEST.json").unlink()
    res = inc.verify_untouched(new, snap, ["3F"])
    assert not res["ok"] and any("manifest missing" in p for p in res["manifest_problems"])
    write_manifest(new)
    _edit_manifest(lambda m: m["floors"].pop("4F"))(new)                               # partial: a baseline floor is not covered
    res = inc.verify_untouched(new, snap, ["3F"])
    assert not res["ok"] and any("floor 4F is not in the manifest" in p for p in res["manifest_problems"])


def test_incremental_change_record_lists_only_changed_files_and_upserts(tmp_path):
    base = make_outputs(tmp_path, "T14T")
    snap = inc.snapshot(base)
    new = make_outputs(tmp_path, "T14U")
    put(new / "3F" / "a.svg", b"<svg new/>")
    rec = inc.make_record("ISSUE-7", ["3F"], new, snap, {"focused": "PASS", "regression": "NOT_RUN"}, ["D-01", "D-01"], "PROPOSED_DESIGN", None)
    assert [f["path"] for f in rec["generated_files"]] == ["T14U/3F/a.svg"]
    assert rec["unresolved_decisions"] == ["D-01"] and rec["tests_all_pass"] is False
    out = tmp_path / "docs" / "t14u" / "change_records.json"
    inc.upsert(out, rec)
    doc = inc.upsert(out, {**rec, "unresolved_decisions": []})
    assert len(doc["records"]) == 1 and doc["records"][0]["unresolved_decisions"] == []
    inc.upsert(out, {**rec, "issue_id": "ISSUE-1"})
    assert [r["issue_id"] for r in json.loads(out.read_text(encoding="utf-8"))["records"]] == ["ISSUE-1", "ISSUE-7"]


def test_incremental_change_record_refuses_invented_approval_and_bad_test_state(tmp_path):
    new = make_outputs(tmp_path, "T14U")
    with pytest.raises(ValueError, match="approval-ref"):
        inc.make_record("I", ["3F"], new, None, {}, [], "APPROVED_DESIGN", None)
    assert inc.make_record("I", ["3F"], new, None, {}, [], "APPROVED_DESIGN", "user decision 2026-11-24")["approval_ref"]
    for bad in ({"t": "GREEN"},):
        with pytest.raises(ValueError):
            inc.make_record("I", ["3F"], new, None, bad, [], "PROPOSED_DESIGN", None)
    for prov, floors in (("VERIFIED", ["3F"]), ("PROPOSED_DESIGN", ["9F"])):
        with pytest.raises(ValueError):
            inc.make_record("I", floors, new, None, {}, [], prov, None)


def test_incremental_cli_scope_uses_git_diff_and_requires_destinations(repo, capsys):
    base = git(repo, "rev-parse", "HEAD")
    (repo / "outputs/T14T/3F/a.svg").write_bytes(b"x")
    common = ["scope", "--base", base, "--root", str(repo), "--out", "outputs/T14U", "--report", "docs/t14u/report.json"]
    assert inc.main(common) == 0
    assert json.loads(capsys.readouterr().out)["floors"] == ["3F"]
    (repo / "src/x.py").write_text("x=3\n", encoding="utf-8")
    assert inc.main(common) == 0
    assert json.loads(capsys.readouterr().out)["scope"] == "ALL_FLOORS_REGRESSION"
    assert inc.main(["scope", "--base", base, "--root", str(repo), "--out", "outputs/T14T", "--report", "docs/t14u/report.json"]) == 2     # protected out
    with pytest.raises(SystemExit):
        inc.main(["scope", "--base", base, "--root", str(repo)])                                                                      # out and report are required
    capsys.readouterr()


# =============================================================== vertical-circulation-audit
def audit(name: str) -> dict:
    return circ.audit_floor(json.loads((FX / "circulation" / (name + ".json")).read_text(encoding="utf-8")))


def ids(items) -> list:
    return [x["id"] for x in items]


def test_circulation_complete_needs_nothing_open():
    for name in ("x1_complete", "x13_light_tube_only"):
        r = audit(name)
        assert r["verdict"] == "COMPLETE" and r["components"] == 1 and not r["excluded"] and not r["provisional"] and not r["open_item_kinds"], name
    assert ids(audit("x13_light_tube_only")["non_transport"]) == ["T2"]


def test_circulation_service_only_shafts_are_listed_separately_and_do_not_block():
    r = audit("x9_service_shafts_only_unrouted")
    assert r["verdict"] == "COMPLETE" and ids(r["service_only"]) == ["FR", "M1"] and r["passenger_transport_not_assessed"] == []
    assert {x["kind"] for x in r["service_only"]} == {"FREIGHT_LIFT", "MEP_SHAFT"}


def test_circulation_unrouted_emergency_lifts_block_a_complete_label_on_a_b2_like_floor():
    r = audit("x10_b2_like_emergency_lifts_unrouted")
    assert r["verdict"] == "CONNECTED_WITH_OPEN_ITEMS" and r["open_item_kinds"] == ["PASSENGER_TRANSPORT_NOT_ASSESSED"]
    assert ids(r["passenger_transport_not_assessed"]) == ["EV1", "EV2"] and ids(r["service_only"]) == ["FR", "M1", "M2"]
    assert {x["kind"] for x in r["passenger_transport_not_assessed"]} == {"EMERGENCY_LIFT"}
    assert "role in visitor circulation is not stated" in r["passenger_transport_not_assessed"][0]["note"]
    assert not r["excluded"] and not r["provisional"] and len(r["connected"]) == 3        # what was assessed is still reported as connected


def test_circulation_plaza_lift_without_a_graph_node_is_passenger_transport_not_assessed():
    r = audit("x15_plaza_lift_unrouted")
    assert r["verdict"] == "CONNECTED_WITH_OPEN_ITEMS" and ids(r["passenger_transport_not_assessed"]) == ["PL"] and r["passenger_transport_not_assessed"][0]["kind"] == "LIFT"


def test_circulation_element_with_no_source_name_or_unknown_name_is_never_assumed_to_be_service():
    unknown = audit("x12_unclassified_element")
    assert unknown["verdict"] == "CONNECTED_WITH_OPEN_ITEMS" and ids(unknown["unclassified_elements"]) == ["Z9"] and not unknown["service_only"]
    nameless = audit("x16_element_without_a_name")
    assert nameless["verdict"] == "CONNECTED_WITH_OPEN_ITEMS" and ids(nameless["unclassified_elements"]) == ["PL"] and not nameless["service_only"]


def test_circulation_lift_entry_rotations_are_recorded_as_proposed_design_decisions():
    r = audit("x11_proposed_lift_entry_rotation")
    assert r["verdict"] == "CONNECTED_WITH_OPEN_ITEMS" and r["open_item_kinds"] == ["PROPOSED_DESIGN_AWAITING_APPROVAL"]
    assert [(d["id"], d["status"]) for d in r["proposed_decisions"]] == [("D-03", "PROPOSED_DESIGN_AWAITING_APPROVAL")]
    assert "T3 +45" in r["proposed_decisions"][0]["detail"] and "T4 -45" in r["proposed_decisions"][0]["detail"]
    assert r["passenger_transport_not_assessed"] == [] and sorted(r["connected"]) == ["core A", "tube T3", "tube T4"]


def test_circulation_unknown_decision_id_is_pending_not_ignored():
    r = audit("x14_unknown_decision_id")
    assert r["verdict"] == "CONNECTED_WITH_OPEN_ITEMS" and r["proposed_decisions"][0]["status"] == "UNCLASSIFIED_DECISION"


def test_circulation_t1_ramp_access_stays_not_assessed_and_is_not_double_counted():
    r = audit("x6_t1_ramp_not_modelled")
    assert r["verdict"] == "CONNECTED_WITH_OPEN_ITEMS" and r["not_assessed"][0]["id"] == "T1 ramp" and r["not_assessed"][0]["decision"] == "D-08"
    assert r["passenger_transport_not_assessed"] == [] and "NOT_ASSESSED" in r["open_item_kinds"]


def test_circulation_provisional_escalator_landing_is_not_complete():
    r = audit("x2_provisional_landing")
    assert r["verdict"] == "INCOMPLETE" and len(r["provisional"]) == 1 and r["provisional"][0]["decision"] == "D-01" and not r["undecided_items"]


def test_circulation_core_without_slab_is_excluded_not_passed():
    r = audit("x3_core_without_slab")
    assert r["verdict"] == "INCOMPLETE"
    assert [(x["id"], x["kind"], x["decision"]) for x in r["excluded"]] == [("core D", "CORE_WITHOUT_SLAB", "D-02")]


def test_circulation_required_node_missing_from_graph_is_reported():
    r = audit("x4_required_node_missing")
    assert r["verdict"] == "INCOMPLETE" and r["excluded"][0]["kind"] == "REQUIRED_NODE_MISSING_FROM_GRAPH" and r["undecided_items"] == ["core B"]


def test_circulation_missing_public_lift_lobby_is_required_and_service_freight_lift_is_only_listed():
    r = audit("x8_public_lift_lobby_missing")
    assert r["verdict"] == "INCOMPLETE" and [(x["id"], x["kind"]) for x in r["excluded"]] == [("tube T3", "REQUIRED_NODE_MISSING_FROM_GRAPH")]
    assert ids(r["service_only"]) == ["FR"] and ids(r["passenger_transport_not_assessed"]) == ["EV1"]       # T3 is excluded above, not listed twice


def test_circulation_disconnected_graph():
    r = audit("x5_disconnected")
    assert r["verdict"] == "INCOMPLETE" and r["components"] == 2 and r["excluded"][0]["kind"] == "GRAPH_DISCONNECTED"


def test_circulation_unit_door_unreachable_and_undecided_item():
    r = audit("x7_unit_door_and_undecided")
    assert {x["kind"] for x in r["excluded"]} == {"BLOCKED_BY_SOLID", "UNIT_DOOR_UNREACHABLE"}
    assert len(r["excluded"]) == 2 and len(r["undecided_items"]) == 2                  # the blocked escalator is not listed twice


def test_circulation_validator_flag_that_overstates_is_reported_for_every_non_complete_floor():
    names = ("x1_complete", "x2_provisional_landing", "x3_core_without_slab", "x6_t1_ramp_not_modelled", "x9_service_shafts_only_unrouted",
             "x10_b2_like_emergency_lifts_unrouted", "x11_proposed_lift_entry_rotation")
    notes = "\n".join(circ.cross_check([audit(n) for n in names], json.loads((FX / "technical_report.json").read_text(encoding="utf-8"))))
    for floor in ("X2", "X3", "X6", "X10", "X11"):
        assert "%s: VALIDATOR_FLAG_OVERSTATES" % floor in notes, floor
    assert "X1:" not in notes and "X9:" not in notes                                    # complete floors raise no note
    assert "PASSENGER_TRANSPORT_NOT_ASSESSED" in notes and "PROPOSED_DESIGN_AWAITING_APPROVAL" in notes


def test_circulation_cli_require_complete_passes_only_a_complete_floor(capsys):
    def run(name, *extra):
        return circ.main(["--root", str(FX), "--meta-glob", "circulation/%s.json" % name, "--require-complete", *extra])
    assert run("x1_complete") == 0 and run("x9_service_shafts_only_unrouted") == 0
    for name in ("x10_b2_like_emergency_lifts_unrouted", "x6_t1_ramp_not_modelled", "x11_proposed_lift_entry_rotation", "x3_core_without_slab"):
        assert run(name) == 1, name
    with pytest.raises(SystemExit):
        run("x1_complete", "--allow-not-assessed")                                      # there is no switch that relaxes the rule
    assert circ.main(["--root", str(FX), "--meta-glob", "circulation/none*.json"]) == 2
    out = capsys.readouterr().out
    assert "not circulation proof" in out and "passenger_transport_not_assessed=" in out and "service_only=" in out


def test_circulation_json_report_cannot_be_written_into_a_protected_folder(tmp_path, capsys):
    meta_dir = tmp_path / "outputs" / "T14U" / "X1"
    meta_dir.mkdir(parents=True)
    shutil.copy(FX / "circulation" / "x1_complete.json", meta_dir / "x1_plan_metadata.json")
    base = ["--root", str(tmp_path), "--meta-glob", "outputs/T14U/*/*_plan_metadata.json"]
    assert circ.main(base + ["--json", "docs/t14t_corrections/circulation_audit.json"]) == 2
    assert not (tmp_path / "docs").exists()
    assert circ.main(base + ["--json", "docs/t14u/circulation_audit.json"]) == 0 and (tmp_path / "docs/t14u/circulation_audit.json").exists()
    capsys.readouterr()


@pytest.mark.skipif(not HAVE_T14T, reason="C-T14T outputs not on this branch")
def test_circulation_real_t14t_outputs_have_no_complete_floor_and_name_the_unassessed_lifts():
    rows = {r["floor"]: r for r in (circ.audit_floor(json.loads(p.read_text(encoding="utf-8"))) for p in sorted((ROOT / "outputs/T14T").glob("*/*_plan_metadata.json")))}
    assert len(rows) == 16
    assert not [f for f, r in rows.items() if r["verdict"] == "COMPLETE"]                # EV1/EV2 are passenger lifts nobody assessed
    assert sum(r["verdict"] == "INCOMPLETE" for r in rows.values()) == 14
    b2 = rows["B2"]
    assert b2["verdict"] == "CONNECTED_WITH_OPEN_ITEMS" and ids(b2["passenger_transport_not_assessed"]) == ["EV1", "EV2"] and ids(b2["service_only"]) == ["FR", "M1", "M2"]
    f3 = rows["3F"]
    assert f3["verdict"] == "CONNECTED_WITH_OPEN_ITEMS" and ids(f3["passenger_transport_not_assessed"]) == ["EV1", "EV2", "PL"]
    assert f3["not_assessed"][0]["id"] == "T1 ramp" and [d["id"] for d in f3["proposed_decisions"]] == ["D-03"]
    assert "T3 +45" in f3["proposed_decisions"][0]["detail"] and f3["unclassified_elements"] == []
    assert sum("D-03" in [d["id"] for d in r["proposed_decisions"]] for r in rows.values()) == 14
    assert {x["id"] for x in rows["7F"]["excluded"]} == {"core C", "core D"} and [x["id"] for x in rows["2F"]["excluded"]] == ["core D"]
    assert sum(len(r["provisional"]) for r in rows.values()) == 24 and rows["B1"]["excluded"][0]["kind"] == "BLOCKED_BY_SOLID"
    assert all(not r["undecided_items"] and not r["unclassified_elements"] for r in rows.values())


# =============================================================== github-visual-review-packet
@pytest.fixture(scope="module")
def packet(tmp_path_factory):
    from PIL import Image
    d = tmp_path_factory.mktemp("pkt")
    im = Image.new("RGB", (1000, 700))
    im.putdata([((x * 7) % 256, (y * 5) % 256, ((x + y) * 3) % 256) for y in range(700) for x in range(1000)])
    src = d / "src.png"
    im.save(src)
    out = d / "docs" / "pkt"
    pkt.load_t14r(ROOT).build_packet([("FLOOR_3F", src)], out)
    return out


def fresh(packet: Path, tmp_path: Path) -> Path:
    dst = tmp_path / "docs" / "pkt"
    shutil.copytree(packet, dst)
    return dst


def test_packet_valid_packet_passes_and_readback_is_not_claimed(packet):
    res = pkt.local_check(packet, ROOT)
    assert res["ok"] and res["t14r_verify"] == "PASS_BYTES_AND_PIXELS_ONLY" and res["github_readback"] == "NOT_TESTED" and res["tiles"] >= 1


def test_packet_corrupt_tile_fails(packet, tmp_path):
    p = fresh(packet, tmp_path)
    tile = next((p / "images/FLOOR_3F/tiles").glob("*.png"))
    tile.write_bytes(tile.read_bytes()[:-9] + b"corrupted")
    res = pkt.local_check(p, ROOT)
    assert not res["ok"] and res["t14r_verify"].startswith("FAIL")


def test_packet_unlisted_file_and_missing_readme_fail(packet, tmp_path):
    p = fresh(packet, tmp_path)
    (p / "stray.png").write_bytes(b"x")
    assert "files not listed in manifest" in " ".join(pkt.local_check(p, ROOT)["problems"])
    (p / "stray.png").unlink()
    (p / "README.md").unlink()
    assert "README.md missing" in pkt.local_check(p, ROOT)["problems"]


def make_remote(packet: Path, prefix: str, **over):
    """Stub GitHub: a recursive tree of the packet's blob SHAs and raw contents."""
    tree = {"truncated": False, "tree": [{"path": prefix + p.relative_to(packet).as_posix(), "type": "blob", "sha": pkt.git_blob_sha(p.read_bytes())} for p in packet.rglob("*") if p.is_file()]}
    tree.update(over.get("tree", {}))
    raw = {e["path"]: (packet / e["path"][len(prefix):]).read_bytes() for e in tree["tree"]}
    raw.update(over.get("raw", {}))
    calls = []

    def runner(args):
        calls.append(args)
        if args[0].startswith("repos/") and "/git/trees/" in args[0]:
            return json.dumps(tree).encode()
        path = args[-1].split("/contents/", 1)[1].split("?ref=")[0]
        return raw.get(path, b"")
    runner.calls = calls
    return runner, tree


def test_packet_remote_identical_passes_and_never_claims_connector_readback(packet):
    runner, _ = make_remote(packet, "docs/pkt/")
    res = pkt.remote_check(packet, "docs/pkt/", "o/r", "abc", sample=2, runner=runner)
    assert res["ok"] and res["status"] == "REMOTE_BYTE_IDENTITY_PASS" and res["github_readback"] == "NOT_TESTED" and res["raw_downloaded"] == 2
    assert "not a ChatGPT connector readback" in res["note"]


def test_packet_remote_blob_mismatch_missing_file_and_empty_download_fail(packet):
    runner, tree = make_remote(packet, "docs/pkt/")
    victim = next(e for e in tree["tree"] if e["path"].endswith("preview.jpg"))
    bad_tree = {"tree": [dict(e, sha="0" * 40) if e is victim else e for e in tree["tree"]]}
    r1, _ = make_remote(packet, "docs/pkt/", tree=bad_tree)
    assert "blob SHA differs" in " ".join(pkt.remote_check(packet, "docs/pkt/", "o/r", "abc", runner=r1)["problems"])
    r2, _ = make_remote(packet, "docs/pkt/", tree={"tree": [e for e in tree["tree"] if e is not victim]})
    assert "not on remote" in " ".join(pkt.remote_check(packet, "docs/pkt/", "o/r", "abc", runner=r2)["problems"])
    r3, _ = make_remote(packet, "docs/pkt/", raw={"docs/pkt/overview.jpg": b""})
    res = pkt.remote_check(packet, "docs/pkt/", "o/r", "abc", runner=r3)
    assert not res["ok"] and "raw download empty" in " ".join(res["problems"])


def test_packet_remote_truncated_tree_fails(packet):
    runner, _ = make_remote(packet, "docs/pkt/", tree={"truncated": True})
    res = pkt.remote_check(packet, "docs/pkt/", "o/r", "abc", runner=runner)
    assert not res["ok"] and "truncated" in res["problems"][0]


def test_packet_sample_is_even_and_deterministic(packet):
    man = json.loads((packet / "manifest.json").read_text(encoding="utf-8"))
    a, b = pkt.sample_files(man, 3), pkt.sample_files(man, 3)
    assert a == b and len(a) == 3 and a[0] == "overview.jpg"
    assert len(pkt.sample_files(man, 0)) == 1 + 2 * len(man["assets"])


@pytest.mark.skipif(not (ROOT / "docs/t14t_corrections/review_packet/manifest.json").exists(), reason="C-T14T packet not on this branch")
def test_packet_real_t14t_packet_verifies_locally():
    res = pkt.local_check(ROOT / "docs/t14t_corrections/review_packet", ROOT)
    assert res["ok"] and res["assets"] == 16 and res["tiles"] == 256 and res["github_readback"] == "NOT_TESTED"


def test_packet_local_readback_report_is_never_independent_proof(packet, tmp_path):
    p = fresh(packet, tmp_path)
    assert pkt.local_check(p, ROOT)["local_readback_report"] == "ABSENT"
    (p / "readback_report.json").write_text(json.dumps({"tested_by": "reviewer", "files_decoded": 3}), encoding="utf-8")
    res = pkt.local_check(p, ROOT)
    assert res["github_readback"] == "NOT_TESTED" and res["local_readback_report"] == "PRESENT_NOT_INDEPENDENT_PROOF"
    assert "not independent proof" in " ".join(res["warnings"]) and res["ok"]                  # integrity still passes, confirmation is not granted
    assert "REPORTED_BY_REVIEWER" not in json.dumps(res)


@pytest.mark.parametrize("line", ["ChatGPT connector readback: PASSED", "GitHub readback verified by the reviewer", "Readback confirmed OK"])
def test_packet_text_that_claims_a_readback_is_rejected(packet, tmp_path, line):
    p = fresh(packet, tmp_path)
    (p / "README.md").write_text((p / "README.md").read_text(encoding="utf-8") + "\n" + line + "\n", encoding="utf-8")
    res = pkt.local_check(p, ROOT)
    assert not res["ok"] and "claims a readback" in " ".join(res["problems"])


def test_packet_text_that_denies_a_readback_is_accepted(packet, tmp_path):
    p = fresh(packet, tmp_path)
    (p / "README.md").write_text((p / "README.md").read_text(encoding="utf-8") + "\nGitHub readback: NOT_TESTED. Readback was not confirmed by anyone.\n", encoding="utf-8")
    assert pkt.local_check(p, ROOT)["ok"]


def test_packet_skill_text_never_offers_a_reviewer_confirmed_status():
    text = (SK / "github-visual-review-packet" / "SKILL.md").read_text(encoding="utf-8") + (SK / "github-visual-review-packet" / "references" / "packet_protocol.md").read_text(encoding="utf-8")
    assert "REPORTED_BY_REVIEWER" not in text and "not independent proof" in text


# =============================================================== final-commit verification record
rc = load("tools/claude_skills/run_checks.py", "sk_rc")
INHERITED = FX / "inherited_failures.json"


def test_final_commit_inherited_failure_list_points_at_the_known_unrelated_file():
    ids_ = json.loads(INHERITED.read_text(encoding="utf-8"))["failures"]
    assert len(ids_) == 10 and all(i.startswith("tests/test_t14i_qa.py::") for i in ids_)


def test_final_commit_failures_are_split_into_inherited_and_new():
    res = rc.classify_failures(["tests/test_t14i_qa.py::a", "tests/test_claude_skills.py::b"], ["tests/test_t14i_qa.py::a", "tests/test_t14i_qa.py::c"])
    assert res == {"inherited": ["tests/test_t14i_qa.py::a"], "new": ["tests/test_claude_skills.py::b"], "inherited_now_passing": ["tests/test_t14i_qa.py::c"]}


def test_final_commit_junit_counts_and_failed_ids(tmp_path):
    xml = tmp_path / "j.xml"
    xml.write_text('<testsuites><testsuite><testcase classname="tests.test_a" name="test_ok"/>'
                   '<testcase classname="tests.test_a" name="test_bad"><failure message="x"/></testcase>'
                   '<testcase classname="tests.test_b" name="test_skip[1]"><skipped message="s"/></testcase></testsuite></testsuites>', encoding="utf-8")
    res = rc.parse_junit(xml)
    assert res["passed"] == 1 and res["failed"] == 1 and res["skipped"] == 1 and res["failed_ids"] == ["tests/test_a.py::test_bad"]


def test_final_commit_worktree_state_reports_exact_sha_and_dirty_flag(repo):
    clean = rc.worktree_state(repo)
    assert clean["head"] == git(repo, "rev-parse", "HEAD") and clean["dirty"] is False and clean["changes"] == []
    (repo / "src" / "x.py").write_text("x=9\n", encoding="utf-8")
    (repo / "new.txt").write_text("new", encoding="utf-8")
    dirty = rc.worktree_state(repo)
    assert dirty["dirty"] is True and len(dirty["changes"]) == 2


def test_final_commit_a_dirty_worktree_cannot_produce_a_passing_final_record():
    report = rc.build_report(state={"head": "a" * 40, "dirty": True, "changes": [" M x"]}, steps=[{"name": "s", "ok": True, "detail": ""}], pytest_by_skill={}, full_suite=None, base=None)
    assert report["all_steps_passed"] is True and report["final_commit_record_valid"] is False and "dirty" in report["final_commit_record_note"]
    clean = rc.build_report(state={"head": "a" * 40, "dirty": False, "changes": []}, steps=[{"name": "s", "ok": True, "detail": ""}], pytest_by_skill={}, full_suite=None, base=None)
    assert clean["final_commit_record_valid"] is True
    failing = rc.build_report(state={"head": "a" * 40, "dirty": False, "changes": []}, steps=[{"name": "s", "ok": False, "detail": ""}], pytest_by_skill={}, full_suite=None, base=None)
    assert failing["final_commit_record_valid"] is False
    new_fail = rc.build_report(state={"head": "a" * 40, "dirty": False, "changes": []}, steps=[{"name": "s", "ok": True, "detail": ""}], pytest_by_skill={},
                               full_suite={"passed": 1, "failed": 1, "skipped": 0, "failed_ids": ["tests/x.py::y"], "inherited": [], "new": ["tests/x.py::y"], "inherited_now_passing": []}, base=None)
    assert new_fail["final_commit_record_valid"] is False                                      # a new failure outside the inherited list invalidates the record


# =============================================================== skill-harvester
def reg_errors(name: str) -> list[str]:
    return reg.validate(json.loads((FX / "registry" / (name + ".json")).read_text(encoding="utf-8")), ROOT)


def test_harvester_committed_registry_is_valid_and_render_is_in_sync():
    data = json.loads(reg.REGISTRY.read_text(encoding="utf-8"))
    assert reg.validate(data, ROOT) == []
    assert (ROOT / "docs/claude_skills/SKILL_CANDIDATE_REGISTRY.md").read_text(encoding="utf-8") == reg.render(data)


def test_harvester_no_committed_entry_claims_verification():
    data = json.loads(reg.REGISTRY.read_text(encoding="utf-8"))
    assert all(c["status"] != "VERIFIED" for c in data["candidates"])
    assert {c["name"] for c in data["candidates"] if c["status"] == "IMPLEMENTED_CANDIDATE"} == {p.name for p in SK.iterdir() if p.is_dir()}


def test_harvester_single_task_candidate_is_rejected():
    assert "needs evidence from at least 2 distinct tasks" in " ".join(reg_errors("single_task_candidate"))


def test_harvester_invented_evidence_path_is_rejected():
    assert "evidence path does not exist" in " ".join(reg_errors("invented_evidence_path"))


def test_harvester_verified_needs_independent_reviewer():
    assert "reviewer_ref" in " ".join(reg_errors("verified_without_reviewer"))


def test_harvester_improvement_must_target_an_existing_skill():
    assert "is not an existing project skill" in " ".join(reg_errors("improve_missing_target"))


def test_harvester_duplicates_unknown_status_and_ignored_overlap_are_rejected():
    assert "duplicate name" in " ".join(reg_errors("duplicate_names"))
    assert "not in" in " ".join(reg_errors("unknown_status"))
    assert "why_not_improve" in " ".join(reg_errors("new_skill_ignores_comparable"))


def test_harvester_single_observation_is_allowed_as_observed_once():
    assert reg_errors("valid_observed_once") == []


def test_harvester_overlap_reads_personal_skills_without_writing_to_them(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".claude" / "skills" / "my-floor-helper").mkdir(parents=True)
    (home / ".claude" / "skills" / "my-floor-helper" / "SKILL.md").write_text("---\nname: my-floor-helper\ndescription: Use when floor plans.\n---\n", encoding="utf-8")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    before = sorted(p.relative_to(home).as_posix() for p in home.rglob("*"))
    hits = reg.overlap(["circulation", "floor"], ROOT)
    assert any(h.startswith("vertical-circulation-audit [project]") for h in hits) and any(h.startswith("my-floor-helper [personal]") for h in hits)
    assert reg.overlap(["zzz-no-such-topic"], ROOT) == []
    assert sorted(p.relative_to(home).as_posix() for p in home.rglob("*")) == before


# =============================================================== behaviour evaluation scorer
beh = load("tools/claude_skills/score_behavior.py", "sk_beh")

GOOD_P0A = """python -I .claude/skills/floorplan-incremental-build/scripts/incremental.py run --out outputs/T14U --report docs/t14u/build_test_report.json --baseline outputs/T14T --floors 3F
Unaffected floors are copied byte-identical from the baseline and verified by SHA256; the manifest is checked."""
DEFAULT_P0A = """python tools/t14s/build_all.py --floors 3F
python tools/t14s/validate_t14t.py --floors 3F
Outputs go to outputs/T14T and the report to docs/t14t_corrections/build_test_report.json."""
PROTECTED_P0A = """python tools/t14s/build_all.py --floors 3F --out outputs/T14T
python tools/t14s/validate_t14t.py --out outputs/T14T --report docs/t14t_corrections/build_test_report.json
Other floors are unchanged."""
GOOD_P0B = """B2: CONNECTED_WITH_OPEN_ITEMS. 3 nodes (cores C, D, wc C) are connected, but EV1 and EV2 (emergency lifts) have no graph node and are not assessed.
FR, M1 and M2 are service-only shafts, listed but not required."""
BAD_P0B = """B2: circulation is complete.
All 3 nodes are connected and 18 of 18 shop doors are reachable."""


def passed(res: dict) -> dict:
    return {k: v for k, v in res["checks"].items()}


def test_behavior_scorer_accepts_a_p0a_answer_that_uses_a_new_folder_and_report():
    res = beh.score("p0a_build_destination", GOOD_P0A, root=ROOT)
    assert res["all_passed"] and set(passed(res)) == {"passes_explicit_out_to_a_new_folder", "passes_explicit_report_to_a_new_path", "never_builds_without_out", "checks_unaffected_floors_by_hash"}


def test_behavior_scorer_rejects_p0a_default_commands_that_write_into_the_baseline():
    res = beh.score("p0a_build_destination", DEFAULT_P0A, root=ROOT)["checks"]
    assert not res["passes_explicit_out_to_a_new_folder"] and not res["passes_explicit_report_to_a_new_path"]
    assert not res["never_builds_without_out"] and not res["checks_unaffected_floors_by_hash"]


def test_behavior_scorer_rejects_an_explicit_out_that_is_the_baseline_itself():
    res = beh.score("p0a_build_destination", PROTECTED_P0A, root=ROOT)["checks"]
    assert not res["passes_explicit_out_to_a_new_folder"] and not res["passes_explicit_report_to_a_new_path"] and res["never_builds_without_out"]


def test_behavior_scorer_p0b_accepts_a_status_that_names_the_unassessed_lifts_and_keeps_service_shafts_apart():
    assert beh.score("p0b_b2_status", GOOD_P0B, root=ROOT)["all_passed"]


def test_behavior_scorer_p0b_rejects_a_flat_complete_status():
    res = beh.score("p0b_b2_status", BAD_P0B, root=ROOT)["checks"]
    assert not res["names_unassessed_passenger_lifts"] and not res["no_unqualified_complete"] and not res["service_shafts_kept_apart"]


def test_behavior_scorer_p0b_flags_an_approval_claim():
    res = beh.score("p0b_b2_status", GOOD_P0B + "\nB2 is approved.", root=ROOT)["checks"]
    assert not res["makes_no_approval_claim"] and res["names_unassessed_passenger_lifts"]


def test_behavior_scorer_unknown_scenario_is_an_error():
    with pytest.raises(KeyError):
        beh.score("no_such_scenario", "x", root=ROOT)


def test_behavior_scorer_summarises_a_folder_of_answers_per_condition(tmp_path):
    (tmp_path / "p0b_b2_status__with_skill__1.txt").write_text(GOOD_P0B, encoding="utf-8")
    (tmp_path / "p0b_b2_status__with_skill__2.txt").write_text(BAD_P0B, encoding="utf-8")
    (tmp_path / "p0b_b2_status__baseline__1.txt").write_text(BAD_P0B, encoding="utf-8")
    (tmp_path / "notes.md").write_text("ignored", encoding="utf-8")
    table = beh.score_dir(tmp_path, root=ROOT)
    row = table["p0b_b2_status"]
    assert row["with_skill"]["n"] == 2 and row["with_skill"]["all_passed"] == 1 and row["baseline"]["n"] == 1 and row["baseline"]["all_passed"] == 0
    assert row["with_skill"]["checks"]["names_unassessed_passenger_lifts"] == 1 and row["baseline"]["checks"]["names_unassessed_passenger_lifts"] == 0
    assert "no statistical claim" in table["_note"]


def test_behavior_scorer_json_destination_is_guarded_and_run_checks_report_is_too(tmp_path, capsys):
    answers = tmp_path / "answers"
    answers.mkdir()
    (answers / "p0b_b2_status__baseline__1.txt").write_text(BAD_P0B, encoding="utf-8")
    stray = ROOT / "docs" / "t14t_corrections" / "behavior_eval_stray.json"
    try:
        assert beh.main([str(answers), "--root", str(ROOT), "--json", "docs/t14t_corrections/behavior_eval_stray.json"]) == 2
        assert not stray.exists()
    finally:
        stray.unlink(missing_ok=True)                                              # never leave a file in a protected folder, even if the guard failed
    ok = tmp_path / "scores.json"
    assert beh.main([str(answers), "--root", str(ROOT), "--json", str(ok)]) == 0 and ok.exists()          # outside the repository is allowed here
    assert rc.report_refused(ROOT, "docs/t14t_corrections/test_report.json") and rc.report_refused(ROOT, "outputs/T14T/x.json")
    assert not rc.report_refused(ROOT, "docs/claude_skills/test_report.json") and not rc.report_refused(ROOT, str(tmp_path / "final.json"))
    capsys.readouterr()


def test_behavior_committed_scores_are_reproduced_from_the_saved_answers():
    folder = ROOT / "docs" / "claude_skills" / "behavior_eval_answers"
    if not folder.is_dir():
        pytest.skip("evaluation answers not on this branch")
    saved = json.loads((ROOT / "docs" / "claude_skills" / "behavior_eval_scores.json").read_text(encoding="utf-8"))
    assert beh.score_dir(folder, root=ROOT) == saved
    assert sum(len(list(folder.glob(p))) for p in ("*__with_skill__*.txt", "*__baseline__*.txt")) == 12


def test_behavior_scenarios_are_fixed_and_target_the_two_p0_issues():
    data = json.loads((FX / "behavior_eval" / "scenarios.json").read_text(encoding="utf-8"))
    assert [s["id"] for s in data["scenarios"]] == ["p0a_build_destination", "p0b_b2_status"]
    assert all(Path(ROOT / p).exists() for s in data["scenarios"] for p in s["skills_to_read"])
    assert all("read-only exercise" in s["prompt"] for s in data["scenarios"])


# =============================================================== skill lint and format
SKILL_NAMES = ["drawing-source-guard", "floorplan-incremental-build", "github-visual-review-packet", "skill-harvester", "vertical-circulation-audit"]


def test_lint_all_five_skills_pass_the_quality_gate():
    assert sorted(p.name for p in SK.iterdir() if p.is_dir()) == SKILL_NAMES
    assert [e for n in SKILL_NAMES for e in lint.lint_skill(SK / n)] == []


def make_skill(tmp_path: Path, text: str, script: str | None = None) -> Path:
    d = tmp_path / "bad-skill"
    (d / "scripts").mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(text, encoding="utf-8")
    if script:
        (d / "scripts" / "s.py").write_text(script, encoding="utf-8")
    return d


def test_lint_rejects_bad_frontmatter_missing_sections_and_untested_status(tmp_path):
    text = "---\nname: other-name\ndescription: Does things.\n---\n\n# x\n\nSee @notes.md and ${CLAUDE_SKILL_DIR}/scripts/missing.py\n"
    errs = " | ".join(lint.lint_skill(make_skill(tmp_path, text)))
    for needle in ("name 'other-name'", "must start with 'Use when'", "metadata.status", "section '## Trigger' missing", "@-file imports", "scripts/missing.py does not exist"):
        assert needle in errs, needle


def test_lint_rejects_missing_frontmatter_oversize_self_promotion_and_dependencies(tmp_path):
    assert "frontmatter missing" in lint.lint_skill(make_skill(tmp_path, "# no frontmatter\n"))[0]
    sections = "\n".join("## " + s for s in ("Trigger", "Inputs", "Outputs", "Example", "Safety boundaries", "Tests"))
    head = "---\nname: bad-skill\ndescription: Use when testing.\nmetadata:\n  status: CANDIDATE_UNREVIEWED\n---\n"
    errs = " | ".join(lint.lint_skill(make_skill(tmp_path, head + sections + "\nThis skill is verified. candidate. " + "word " * 800, "import numpy\nimport json\n")))
    for needle in ("too long", "self-promotion", "non-stdlib module 'numpy'"):
        assert needle in errs, needle
    assert "VERIFIED_BY_REVIEWER needs metadata.reviewer_ref" in " | ".join(lint.lint_skill(make_skill(tmp_path, head.replace("CANDIDATE_UNREVIEWED", "VERIFIED_BY_REVIEWER") + sections)))


def test_lint_every_skill_states_candidate_status_and_references_real_files():
    for n in SKILL_NAMES:
        text = (SK / n / "SKILL.md").read_text(encoding="utf-8")
        fm, body = lint.parse_frontmatter(text)
        assert fm["metadata"]["status"] == "CANDIDATE_UNREVIEWED" and "not independently reviewed" in body
        assert fm["description"].startswith("Use when") and len(fm["description"]) <= 500


def test_every_script_has_help_and_runs_without_third_party_packages():
    for p in sorted(SK.glob("*/scripts/*.py")):
        r = subprocess.run([sys.executable, "-I", str(p), "--help"], capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0 and "usage:" in r.stdout, p.name


@pytest.mark.skipif(shutil.which("claude") is None or shutil.which("bash") is None, reason="claude CLI or bash not installed")
def test_official_validator_accepts_the_skill_folder():
    # Run through bash: on this machine the claude.CMD shim treats .claude/skills as a plugin and asks for a manifest, while the
    # bash shim runs the documented skills-folder validation ("claude plugin validate .claude/skills").
    r = subprocess.run(["bash", "-c", "claude plugin validate .claude/skills"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=180)
    assert r.returncode == 0 and "Validating components in" in r.stdout and "Validation passed" in r.stdout, r.stdout + r.stderr


def test_skill_library_has_no_install_or_global_config_code():
    for p in list(SK.glob("*/scripts/*.py")) + [ROOT / "tools/claude_skills/skill_lint.py"]:
        src = p.read_text(encoding="utf-8")
        assert "settings.json" not in src and "expanduser" not in src, p.name
        assert ("Path.home()" in src) == (p.name == "registry.py"), p.name        # only the read-only overlap listing looks at the personal folder
