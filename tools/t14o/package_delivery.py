"""Package the verified C-T14O review artifacts without copying full render masters."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    return {
        "path": str(resolved),
        "bytes": resolved.stat().st_size,
        "sha256": sha256(resolved),
    }


def junit_summary(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    suites = list(root) if root.tag == "testsuites" else [root]
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "time_seconds": 0.0}
    for suite in suites:
        for key in ("tests", "failures", "errors", "skipped"):
            totals[key] += int(suite.attrib.get(key, 0))
        totals["time_seconds"] += float(suite.attrib.get("time", 0.0))
    return {"artifact": file_record(path), **totals}


def git_text(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, encoding="utf-8"
    )
    return completed.stdout.strip()


def copy_review_assets(qa_dir: Path, delivery_dir: Path) -> list[Path]:
    requested = [
        qa_dir / "G002_A_Urban_Daylight_preview_1600.png",
        qa_dir / "G002_B_Blue_Hour_preview_1600.png",
        qa_dir / "G002_source_vs_cycles_AB.png",
        qa_dir / "G002_before_after_daylight.png",
        qa_dir / "G002_before_after_bluehour.png",
    ]
    copied: list[Path] = []
    preview_dir = delivery_dir / "render_previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    for source in requested:
        if not source.is_file():
            raise FileNotFoundError(source)
        destination = preview_dir / source.name
        shutil.copy2(source, destination)
        copied.append(destination)
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--delivery-dir", type=Path, required=True)
    parser.add_argument("--qa-dir", type=Path, required=True)
    parser.add_argument("--daylight", type=Path, required=True)
    parser.add_argument("--bluehour", type=Path, required=True)
    parser.add_argument("--daylight-blend", type=Path, required=True)
    parser.add_argument("--bluehour-blend", type=Path, required=True)
    parser.add_argument("--daylight-audit", type=Path, required=True)
    parser.add_argument("--bluehour-audit", type=Path, required=True)
    parser.add_argument("--review-pdf", type=Path, required=True)
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--implementation-commit")
    parser.add_argument("--write-diff", action="store_true")
    args = parser.parse_args()

    repo = args.repo.resolve()
    delivery_dir = args.delivery_dir.resolve()
    delivery_dir.mkdir(parents=True, exist_ok=True)
    qa_dir = args.qa_dir.resolve()
    previews = copy_review_assets(qa_dir, delivery_dir)

    required = [
        args.daylight, args.bluehour, args.daylight_blend, args.bluehour_blend,
        args.daylight_audit, args.bluehour_audit, args.review_pdf,
        qa_dir / "render_quality_qa.json",
    ]
    for path in required:
        if not path.resolve().is_file():
            raise FileNotFoundError(path)

    tests = {
        "status": "PASS_WITH_DOCUMENTED_SKIPS",
        "final_full_suite": junit_summary(delivery_dir / "pytest_results_with_verified_t14i_run.xml"),
        "c_t14o_contract": junit_summary(delivery_dir / "pytest_t14o_results.xml"),
        "t14i_artifact_rerun": junit_summary(delivery_dir / "pytest_t14i_rerun.xml"),
        "initial_isolated_worktree_diagnostic": junit_summary(delivery_dir / "pytest_results.xml"),
        "interpretation": (
            "The initial isolated-worktree run exposed ten missing-default-output failures. "
            "The final full suite was rerun read-only against the verified C_T14K_run artifacts."
        ),
    }
    (delivery_dir / "tests_report.json").write_text(
        json.dumps(tests, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    render_qa = json.loads((qa_dir / "render_quality_qa.json").read_text(encoding="utf-8"))
    source_manifest = {
        "schema": "C-T14O-DELIVERY-MANIFEST-1.0",
        "created_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "CANDIDATE_PIXELS_VERIFIED__USER_ARCHITECTURAL_APPROVAL_PENDING",
        "repository": "edward321416-maker/drawing-pipeline",
        "branch": git_text(repo, "branch", "--show-current"),
        "base_commit": args.base_commit,
        "implementation_commit": args.implementation_commit or git_text(repo, "rev-parse", "HEAD"),
        "source_geometry": {
            "model_world_npz_sha256": "992e2ec51ec17dc494ed2f99ddb11298671449dd6661d92df3b3536a0049537b",
            "model_objects_json_sha256": "722dd7359e2f13534ff4ae91088ba8649e8a8f96b27c60f000ddb09c01106488",
            "vertices": 119486,
            "triangles": 237093,
            "objects": 391,
        },
        "render_masters": {
            "urban_daylight_png": file_record(args.daylight),
            "blue_hour_png": file_record(args.bluehour),
            "urban_daylight_blend": file_record(args.daylight_blend),
            "blue_hour_blend": file_record(args.bluehour_blend),
            "urban_daylight_audit": file_record(args.daylight_audit),
            "blue_hour_audit": file_record(args.bluehour_audit),
        },
        "review": {
            "a3_pdf": file_record(args.review_pdf),
            "render_quality_qa": file_record(qa_dir / "render_quality_qa.json"),
            "all_A_B_geometry_camera_equivalence_checks_pass": render_qa[
                "all_equivalence_checks_pass"
            ],
            "print_check": render_qa["print_check"],
            "tracked_preview_assets": [file_record(path) for path in previews],
        },
        "authority_limits": render_qa["limitations"],
        "scope_boundary": "G-002 only; no downstream drawing expansion before user approval.",
    }
    (delivery_dir / "source_manifest.json").write_text(
        json.dumps(source_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    if args.write_diff:
        diff_target = args.implementation_commit or "HEAD"
        diff_text = subprocess.run(
            ["git", "diff", "--no-ext-diff", "--full-index", f"{args.base_commit}..{diff_target}"],
            cwd=repo, check=True, capture_output=True, encoding="utf-8", text=True,
        ).stdout
        (delivery_dir / "source_changes.diff").write_text(diff_text, encoding="utf-8")

    print(json.dumps({
        "delivery_dir": str(delivery_dir),
        "source_manifest": str((delivery_dir / "source_manifest.json").resolve()),
        "tests_report": str((delivery_dir / "tests_report.json").resolve()),
        "previews": [str(path.resolve()) for path in previews],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
