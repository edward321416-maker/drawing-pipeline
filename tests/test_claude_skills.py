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
def test_incremental_floor_scoped_plan_and_command_order():
    res = inc.plan_scope(["outputs/T14T/3F/x.svg", "outputs/T14T/3F/x.dxf", "docs/t14u/readme.md"], [])
    assert res["scope"] == "FLOOR_SCOPED" and res["floors"] == ["3F"]
    names = [s["name"] for s in res["plan"]]
    assert names[0].startswith("snapshot") and "focused build" in names[1] and "focused validation" in names[2] and names[-1].startswith("other floors")
    assert "--floors 3F" in res["plan"][1]["cmd"] and "regression" not in " ".join(names)


@pytest.mark.parametrize("path", ["src/t14s/planner.py", "tools/t14s/validate_t14t.py", "tools/t14s/build_all.py", "tests/test_x.py"])
def test_incremental_shared_generator_change_widens_scope(path):
    res = inc.plan_scope([path], ["3F"])
    assert res["scope"] == "ALL_FLOORS_REGRESSION" and res["reasons"]
    assert any("cross-floor regression" in s["name"] for s in res["plan"])
    order = [s["step"] for s in res["plan"]]
    assert order == sorted(order)


def test_incremental_floors_sorted_and_validated():
    assert inc.plan_scope([], ["10F", "B1", "2F"])["floors"] == ["B1", "10F", "2F"]
    assert inc.plan_scope([], [])["floors"] == []
    with pytest.raises(ValueError):
        inc.floors_arg(["3rd floor"])
    with pytest.raises(ValueError):
        inc.floors_arg(["B0"])


@pytest.fixture()
def outputs(tmp_path):
    out = tmp_path / "outputs" / "T14T"
    man = {"floors": {}}
    for f in ("2F", "3F"):
        (out / f).mkdir(parents=True)
        for n, d in (("a.svg", b"<svg " + f.encode() + b"/>"), ("b.dxf", b"dxf" + f.encode())):
            (out / f / n).write_bytes(d)
            man["floors"].setdefault(f, {})[n] = {"sha256": sha(d), "bytes": len(d)}
    (out / "SHA256_MANIFEST.json").write_text(json.dumps(man), encoding="utf-8")
    return out


def _rebuild_manifest(out: Path):
    man = {"floors": {}}
    for d in sorted(p for p in out.iterdir() if p.is_dir()):
        man["floors"][d.name] = {f.name: {"sha256": sha(f.read_bytes()), "bytes": f.stat().st_size} for f in sorted(d.iterdir())}
    (out / "SHA256_MANIFEST.json").write_text(json.dumps(man), encoding="utf-8")


def test_incremental_in_scope_change_with_updated_manifest_passes(outputs):
    snap = inc.snapshot(outputs)
    (outputs / "3F/a.svg").write_bytes(b"<svg new/>")
    _rebuild_manifest(outputs)
    res = inc.verify_untouched(outputs, snap, ["3F"])
    assert res["ok"] and res["changed_in_scope"]["3F"] == ["a.svg"] and res["in_scope_unchanged"] == []


def test_incremental_untouched_floor_change_is_detected(outputs):
    snap = inc.snapshot(outputs)
    (outputs / "2F/b.dxf").write_bytes(b"leaked change")
    _rebuild_manifest(outputs)
    res = inc.verify_untouched(outputs, snap, ["3F"])
    assert not res["ok"] and "floor 2F is out of scope" in res["out_of_scope_violations"][0]
    assert res["in_scope_unchanged"] == ["3F"]                              # a no-op build of the scoped floor is visible


def test_incremental_stale_manifest_and_dropped_floor_are_detected(outputs):
    snap = inc.snapshot(outputs)
    (outputs / "3F/a.svg").write_bytes(b"<svg new/>")                       # manifest not refreshed
    assert any("stale" in p for p in inc.verify_untouched(outputs, snap, ["3F"])["manifest_problems"])
    man = json.loads((outputs / "SHA256_MANIFEST.json").read_text(encoding="utf-8"))
    del man["floors"]["2F"]
    (outputs / "SHA256_MANIFEST.json").write_text(json.dumps(man), encoding="utf-8")
    assert "manifest drops floor 2F" in inc.verify_untouched(outputs, inc.snapshot(outputs), ["3F"])["manifest_problems"]


def test_incremental_change_record_only_lists_changed_files_and_upserts(outputs, tmp_path):
    snap = inc.snapshot(outputs)
    (outputs / "3F/a.svg").write_bytes(b"<svg new/>")
    rec = inc.make_record("ISSUE-7", ["3F"], outputs, snap, {"focused": "PASS", "regression": "NOT_RUN"}, ["D-01", "D-01"], "PROPOSED_DESIGN", None)
    assert [f["path"] for f in rec["generated_files"]] == ["T14T/3F/a.svg"]
    assert rec["unresolved_decisions"] == ["D-01"] and rec["tests_all_pass"] is False
    out = tmp_path / "change_records.json"
    inc.upsert(out, rec)
    doc = inc.upsert(out, {**rec, "unresolved_decisions": []})
    assert len(doc["records"]) == 1 and doc["records"][0]["unresolved_decisions"] == []
    inc.upsert(out, {**rec, "issue_id": "ISSUE-1"})
    assert [r["issue_id"] for r in json.loads(out.read_text(encoding="utf-8"))["records"]] == ["ISSUE-1", "ISSUE-7"]


def test_incremental_change_record_refuses_invented_approval_and_bad_test_state(outputs):
    with pytest.raises(ValueError, match="approval-ref"):
        inc.make_record("I", ["3F"], outputs, None, {}, [], "APPROVED_DESIGN", None)
    assert inc.make_record("I", ["3F"], outputs, None, {}, [], "APPROVED_DESIGN", "user decision 2026-11-24")["approval_ref"]
    with pytest.raises(ValueError):
        inc.make_record("I", ["3F"], outputs, None, {"t": "GREEN"}, [], "PROPOSED_DESIGN", None)
    with pytest.raises(ValueError):
        inc.make_record("I", ["3F"], outputs, None, {}, [], "VERIFIED", None)
    with pytest.raises(ValueError):
        inc.make_record("I", ["9F"], outputs, None, {}, [], "PROPOSED_DESIGN", None)


def test_incremental_cli_scope_uses_git_diff(repo, capsys):
    base = git(repo, "rev-parse", "HEAD")
    (repo / "outputs/T14T/3F/a.svg").write_bytes(b"x")
    assert inc.main(["scope", "--base", base, "--root", str(repo)]) == 0
    assert json.loads(capsys.readouterr().out)["floors"] == ["3F"]
    (repo / "src/x.py").write_text("x=3\n", encoding="utf-8")
    assert inc.main(["scope", "--base", base, "--root", str(repo)]) == 0
    assert json.loads(capsys.readouterr().out)["scope"] == "ALL_FLOORS_REGRESSION"


# =============================================================== vertical-circulation-audit
def audit(name: str) -> dict:
    return circ.audit_floor(json.loads((FX / "circulation" / (name + ".json")).read_text(encoding="utf-8")))


def test_circulation_complete_floor():
    r = audit("x1_complete")
    assert r["verdict"] == "COMPLETE" and r["components"] == 1 and not r["excluded"] and not r["provisional"]


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


def test_circulation_disconnected_graph():
    r = audit("x5_disconnected")
    assert r["verdict"] == "INCOMPLETE" and r["components"] == 2 and r["excluded"][0]["kind"] == "GRAPH_DISCONNECTED"


def test_circulation_not_modelled_stays_separate_from_connected():
    r = audit("x6_not_modelled")
    assert r["verdict"] == "COMPLETE_EXCEPT_NOT_ASSESSED" and r["not_assessed"][0]["id"] == "T1 ramp" and not r["excluded"]


def test_circulation_unit_door_unreachable_and_undecided_item():
    r = audit("x7_unit_door_and_undecided")
    assert {x["kind"] for x in r["excluded"]} == {"BLOCKED_BY_SOLID", "UNIT_DOOR_UNREACHABLE"}
    assert len(r["excluded"]) == 2 and len(r["undecided_items"]) == 2                  # the blocked escalator is not listed twice


def test_circulation_missing_public_lift_lobby_is_required_but_service_shafts_are_only_listed():
    r = audit("x8_unrouted_lifts_and_shafts")
    assert r["verdict"] == "INCOMPLETE" and [(x["id"], x["kind"]) for x in r["excluded"]] == [("tube T3", "REQUIRED_NODE_MISSING_FROM_GRAPH")]
    assert r["unrouted_elements"] == ["EV1", "FR", "T3"]                                  # capW is an opening, T4 is routed
    r = audit("x9_service_shafts_only_is_complete")
    assert r["verdict"] == "COMPLETE" and r["unrouted_elements"] == ["EV1", "EV2", "FR", "M1"]


def test_circulation_validator_flag_that_overstates_is_reported():
    rows = [audit(n) for n in ("x1_complete", "x2_provisional_landing", "x3_core_without_slab", "x6_not_modelled")]
    notes = circ.cross_check(rows, json.loads((FX / "technical_report.json").read_text(encoding="utf-8")))
    text = "\n".join(notes)
    assert "X2: VALIDATOR_FLAG_OVERSTATES" in text and "X3: VALIDATOR_FLAG_OVERSTATES" in text and "X6: VALIDATOR_FLAG_IGNORES_NOT_ASSESSED" in text
    assert "X1:" not in text                                                          # a complete floor raises no note


def test_circulation_cli_require_complete_exit_codes(capsys):
    base = ["--root", str(FX), "--meta-glob", "circulation/x1_complete.json"]
    assert circ.main(base + ["--require-complete"]) == 0
    assert circ.main(["--root", str(FX), "--meta-glob", "circulation/x6_not_modelled.json", "--require-complete"]) == 1
    assert circ.main(["--root", str(FX), "--meta-glob", "circulation/x6_not_modelled.json", "--require-complete", "--allow-not-assessed"]) == 0
    assert circ.main(["--root", str(FX), "--meta-glob", "circulation/x3_core_without_slab.json", "--require-complete", "--allow-not-assessed"]) == 1
    assert circ.main(["--root", str(FX), "--meta-glob", "circulation/none*.json"]) == 2
    out = capsys.readouterr().out
    assert "not circulation proof" in out and "unrouted=0" in out and "have no graph node and were not tested" in out


@pytest.mark.skipif(not HAVE_T14T, reason="C-T14T outputs not on this branch")
def test_circulation_real_t14t_outputs_match_the_documented_findings():
    rows = {r["floor"]: r for r in (circ.audit_floor(json.loads(p.read_text(encoding="utf-8"))) for p in sorted((ROOT / "outputs/T14T").glob("*/*_plan_metadata.json")))}
    assert len(rows) == 16
    assert rows["B2"]["verdict"] == "COMPLETE" and rows["3F"]["verdict"] == "COMPLETE_EXCEPT_NOT_ASSESSED"
    assert sum(r["verdict"] == "INCOMPLETE" for r in rows.values()) == 14
    assert {x["id"] for x in rows["7F"]["excluded"]} == {"core C", "core D"} and [x["id"] for x in rows["2F"]["excluded"]] == ["core D"]
    assert sum(len(r["provisional"]) for r in rows.values()) == 24 and rows["B1"]["excluded"][0]["kind"] == "BLOCKED_BY_SOLID"
    assert all(not r["undecided_items"] for r in rows.values())
    assert rows["B2"]["unrouted_elements"] == ["EV1", "EV2", "FR", "M1", "M2"] and rows["3F"]["verdict"] != "INCOMPLETE"


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


def test_packet_readback_report_needs_a_real_tester(packet, tmp_path):
    p = fresh(packet, tmp_path)
    (p / "readback_report.json").write_text(json.dumps({"files_decoded": 3}), encoding="utf-8")
    assert not pkt.local_check(p, ROOT)["ok"]
    (p / "readback_report.json").write_text(json.dumps({"tested_by": "reviewer", "files_decoded": 3}), encoding="utf-8")
    res = pkt.local_check(p, ROOT)
    assert res["ok"] and res["github_readback"] == "REPORTED_BY_REVIEWER"


def test_packet_blob_sha_equals_git_hash_object(tmp_path):
    f = tmp_path / "f.bin"
    f.write_bytes(b"\x00\x01binary\n\r\n")
    git(tmp_path, "init", "-q")
    assert pkt.git_blob_sha(f.read_bytes()) == git(tmp_path, "hash-object", str(f))


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
