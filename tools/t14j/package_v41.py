"""Package C-T14J Candidate V4.1 without touching V4 or the technical appendix."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def copy(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--tests-report", type=Path)
    a = ap.parse_args()
    run, repo = a.run.resolve(), a.repo.resolve()
    out = repo / "docs" / "t14j_v41"
    out.mkdir(parents=True, exist_ok=True)
    book = run / "v41" / "book" / "Graduation_Drawing_Book_Candidate_V4_1.pdf"
    qa = run / "v41" / "qa"
    products = [copy(book, out / book.name),
                copy(qa / "Graduation_Drawing_Book_Contact_Sheet.png", out / "Graduation_Drawing_Book_Contact_Sheet.png")]
    sheet_map = {
        "G-002": (run / "v4" / "appendix_docs" / "G-002", "project_information"),
        "G-106": (run / "v4" / "partI" / "G-106_representative_plans", "representative_plans"),
        "G-108": (run / "v4" / "partI" / "G-108_elevations", "elevations"),
        "G-109": (run / "v4" / "partI" / "G-109_sections", "sections"),
        "G-111": (run / "v4" / "partI" / "G-111_details", "details"),
        "G-112": (run / "v4" / "partI" / "G-112_floor_experience", "floor_experience"),
    }
    sheets = out / "sheets"
    for sid, (base, label) in sheet_map.items():
        for ext in ("pdf", "svg", "png"):
            products.append(copy(base.with_suffix("." + ext), sheets / f"{sid}_{label}.{ext}"))
    copy(run / "v4" / "appendix_docs" / "G-002_layout.json", out / "G-002_layout.json")
    shutil.copytree(qa / "before_after", out / "before_after", dirs_exist_ok=True)
    shutil.copytree(qa / "full_180dpi", out / "qa" / "full_180dpi", dirs_exist_ok=True)
    shutil.copytree(qa / "key_300dpi", out / "qa" / "key_300dpi", dirs_exist_ok=True)
    for name in ("visual_qa_report.json", "print_legibility_panel_balance.md"):
        copy(qa / name, out / name)
    if a.tests_report and a.tests_report.exists():
        copy(a.tests_report.resolve(), out / "tests_report.json")

    baseline_tech = repo / "docs" / "t14i_v4" / "Technical_Drawing_Appendix_Candidate_V4.pdf"
    a003 = run / "plans" / "A-003_site_plan_1F_1to400.pdf"
    model = run / "model_cache" / "model_world.npz"
    manifest = {
        "edition": "V4.1", "project": "C-T14J", "part_i_pdf": str((out / book.name).resolve()),
        "part_i_sha256": sha256(out / book.name),
        "technical_appendix": {"path": str(baseline_tech.resolve()), "sha256": sha256(baseline_tech),
                                 "status": "UNCHANGED_NOT_REBUILT"},
        "protected_sources": {
            "A-003": {"path": str(a003.resolve()), "sha256": sha256(a003), "modified": False},
            "model_world.npz": {"path": str(model.resolve()), "sha256": sha256(model), "modified": False},
        },
        "products": [{"path": str(p.resolve()), "sha256": sha256(p), "bytes": p.stat().st_size} for p in products],
    }
    (out / "source_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    source_paths = ["tools/t14i/build_books.py", "tools/t14i/config.py", "tools/t14i/partI_front.py",
                    "tools/t14j", "tests/test_t14j_editorial_v41.py"]
    diff = subprocess.run(["git", "diff", "--cached", "--no-ext-diff", "--unified=3", "--", *source_paths],
                          cwd=repo, check=True, capture_output=True, text=True, encoding="utf-8").stdout
    if not diff:
        diff = subprocess.run(["git", "diff", "--no-ext-diff", "--unified=3", "--", *source_paths], cwd=repo,
                              check=True, capture_output=True, text=True, encoding="utf-8").stdout
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=repo, check=True,
                               capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
    for rel in sorted(p for p in untracked if p.startswith("tools/t14j/") or p == "tests/test_t14j_editorial_v41.py"):
        text = (repo / rel).read_text(encoding="utf-8").splitlines(keepends=True)
        diff += "".join(difflib.unified_diff([], text, fromfile="/dev/null", tofile="b/" + rel, n=3))
    # The diff is itself a tracked deliverable.  Strip trailing whitespace from
    # its display lines so repository-wide `git diff --check` also remains clean.
    diff = "\n".join(line.rstrip() for line in diff.splitlines()) + "\n"
    (out / "source_changes.diff").write_text(diff, encoding="utf-8")
    hashes = []
    for path in sorted(p for p in out.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt"):
        hashes.append(f"{sha256(path)}  {path.relative_to(out).as_posix()}")
    (out / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    print(str(out.resolve()))


if __name__ == "__main__":
    main()
