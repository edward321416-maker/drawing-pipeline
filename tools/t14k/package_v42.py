"""Package C-T14K Candidate V4.2 and its source/QA evidence."""
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
    out, book, qa = repo / "docs" / "t14k_v42", run / "v42" / "book", run / "v42" / "qa"
    out.mkdir(parents=True, exist_ok=True)
    part_i = book / "Graduation_Drawing_Book_Candidate_V4_2.pdf"
    part_ii = book / "Technical_Drawing_Appendix_Candidate_V4_2.pdf"
    products = [copy(part_i, out / part_i.name), copy(part_ii, out / part_ii.name),
                copy(qa / "Graduation_Drawing_Book_Contact_Sheet.png", out / "Graduation_Drawing_Book_Contact_Sheet.png"),
                copy(book / "Technical_Appendix_Contact_Sheet_V4_2.png", out / "Technical_Appendix_Contact_Sheet.png")]
    sheet_map = {
        "G-001": (run / "v4" / "partI" / "G-001_cover", "text_cover"),
        "G-002": (run / "v4" / "partI" / "G-002_architectural_render", "architectural_render"),
        "G-003": (run / "v4" / "appendix_docs" / "G-003", "project_information"),
    }
    for sid, (base, label) in sheet_map.items():
        for ext in ("pdf", "svg", "png"):
            products.append(copy(base.with_suffix("." + ext), out / "first3" / f"{sid}_{label}.{ext}"))
    copy(run / "v4" / "appendix_docs" / "G-003_layout.json", out / "G-003_layout.json")
    copy(repo / "assets" / "t14k" / "architectural_exterior_render.jpg", out / "source" / "architectural_exterior_render.jpg")
    for folder in ("before_after", "full_180dpi", "first3_300dpi", "technical_300dpi"):
        shutil.copytree(qa / folder, out / "qa" / folder, dirs_exist_ok=True)
    for name in ("visual_qa_report.json", "render_source_verification.json", "render_source_verification.md",
                 "print_legibility_panel_balance.md"):
        copy(qa / name, out / name)
    if a.tests_report and a.tests_report.exists():
        products.append(copy(a.tests_report.resolve(), out / "tests_report.json"))
        for test_artifact in (a.tests_report.parent / "pytest_full.xml", a.tests_report.parent / "pytest_full.log"):
            if test_artifact.exists():
                products.append(copy(test_artifact.resolve(), out / test_artifact.name))

    final_idx = json.loads((book / "Technical_Drawing_Appendix_Candidate_V4_2_index.json").read_text(encoding="utf-8"))
    manifest = {
        "edition": "V4.2", "project": "C-T14K",
        "part_i": {"path": str((out / part_i.name).resolve()), "sha256": sha256(out / part_i.name), "pages": 16},
        "part_ii": {"path": str((out / part_ii.name).resolve()), "sha256": sha256(out / part_ii.name), "pages": 49,
                    "technical_source_sheets_preserved": 47, "updated_document_sheets": ["A-000", "A-001"]},
        "protected_sources": {
            "A-003": {"path": str((run / "plans" / "A-003_site_plan_1F_1to400.pdf").resolve()),
                      "sha256": sha256(run / "plans" / "A-003_site_plan_1F_1to400.pdf"), "modified": False},
            "model_world.npz": {"path": str((run / "model_cache" / "model_world.npz").resolve()),
                                "sha256": sha256(run / "model_cache" / "model_world.npz"), "modified": False},
            "architectural_render": {"path": str((repo / "assets" / "t14k" / "architectural_exterior_render.jpg").resolve()),
                                     "sha256": sha256(repo / "assets" / "t14k" / "architectural_exterior_render.jpg"), "modified": False},
        },
        "technical_index_sheets": len(final_idx["sheets"]),
        "products": [{"path": str(p.resolve()), "sha256": sha256(p), "bytes": p.stat().st_size} for p in products],
    }
    (out / "source_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    source_paths = ["tools/t14i/build_books.py", "tools/t14i/config.py", "tools/t14i/partI_front.py",
                    "tools/t14k", "tests/test_t14k_editorial_v42.py", "assets/t14k"]
    diff = subprocess.run(["git", "diff", "--cached", "--no-ext-diff", "--unified=3", "--", *source_paths], cwd=repo,
                          check=True, capture_output=True, text=True, encoding="utf-8").stdout
    if not diff:
        diff = subprocess.run(["git", "diff", "--no-ext-diff", "--unified=3", "--", *source_paths], cwd=repo,
                              check=True, capture_output=True, text=True, encoding="utf-8").stdout
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=repo, check=True,
                               capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
    for rel in sorted(p for p in untracked if p.startswith("tools/t14k/") or p == "tests/test_t14k_editorial_v42.py"):
        lines = (repo / rel).read_text(encoding="utf-8").splitlines(keepends=True)
        diff += "".join(difflib.unified_diff([], lines, fromfile="/dev/null", tofile="b/" + rel, n=3))
    diff = "\n".join(line.rstrip() for line in diff.splitlines()) + "\n"
    (out / "source_changes.diff").write_text(diff, encoding="utf-8")
    hashes = [f"{sha256(p)}  {p.relative_to(out).as_posix()}" for p in sorted(out.rglob("*"))
              if p.is_file() and p.name != "SHA256SUMS.txt"]
    (out / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    print(str(out.resolve()))


if __name__ == "__main__":
    main()
