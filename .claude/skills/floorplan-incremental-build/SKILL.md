---
name: floorplan-incremental-build
description: Use when a correction names specific floors or issue ids and the 16 generated floor plans (B2, B1, 2F-15F) must be updated without regenerating all of them, or when a shared generator change must be checked against floors that were not meant to change.
metadata:
  status: CANDIDATE_UNREVIEWED
  version: 0.2.0
---

# floorplan-incremental-build

Plans, guards and audits a selective rebuild of floor deliverables (SVG, DXF, A1 PDF, A3 split PDF, PNG, metadata) **into a new task folder**. Status: **candidate, not independently reviewed.**

## Trigger
- A correction brief lists issue ids and affected floors.
- Source under `src/t14s/` or a builder/validator under `tools/` changed and other floors must be shown unaffected.

Not for: a first full build.

## Inputs
Issue id(s), affected floors, PR base ref, the **baseline** output folder (earlier PR outputs, read-only, for example `outputs/T14T`), a **new** task output folder (for example `outputs/T14U`) and a **new** validation report path (for example `docs/t14u/build_test_report.json`).

## Procedure
1. Guard first: `drawing-source-guard` (sources, manifests).
2. `python -I ${CLAUDE_SKILL_DIR}/scripts/incremental.py scope --base <ref> --out outputs/<NEW> --report docs/<new>/build_test_report.json --baseline outputs/<OLD> --floors 3F 8F` prints `FLOOR_SCOPED` or `ALL_FLOORS_REGRESSION` and the ordered commands. A change under `src/**`, `tools/*/build*.py`, `validate*.py`, `package*.py` or `tests/**` widens the scope.
3. `incremental.py run --out outputs/<NEW> --report docs/<new>/build_test_report.json --baseline outputs/<OLD> --floors 3F 8F [--regression]` does the work:
   - refuses, before creating anything, any `--out` or `--report` that is protected (list: `drawing-source-guard`), outside the repository or the baseline itself (case-insensitive, `..` resolved);
   - copies the unaffected floors byte-for-byte from the baseline into the new folder;
   - runs the project builder `tools/t14s/build_all.py --floors ... --out <NEW>` and validator `tools/t14s/validate_t14t.py --floors ... --out <NEW> --report <report>` with those explicit arguments;
   - verifies that unaffected floors are byte-identical and the manifest is complete.
4. Manifests fail closed: a missing, partial, corrupt or inconsistent `SHA256_MANIFEST.json` (floor coverage, file listing, sizes, hashes) fails `verify-untouched`.
5. `incremental.py snapshot --outputs outputs/<OLD> --out docs/<new>/baseline_snapshot.json`, then `incremental.py change-record --issue <ID> --floors 3F --outputs outputs/<NEW> --snapshot docs/<new>/baseline_snapshot.json --out docs/<new>/change_records.json`: one record per issue id (floors, changed files with SHA256, tests, unresolved decision ids, provenance class). Every file this workflow writes is destination-checked.
6. Then `vertical-circulation-audit` for floors with escalators, lifts or cores, and `github-visual-review-packet` for the changed floors only.

## Outputs
Scope plan, the new output folder with manifest, the new report, verification JSON, `C-T14-CHANGE-RECORDS-1.0` records. Exit 0 ok, 1 build or verification failed, 2 refused.

## Example
```
python -I ${CLAUDE_SKILL_DIR}/scripts/incremental.py run --out outputs/T14U --report docs/t14u/build_test_report.json --baseline outputs/T14T --floors 3F
python -I ${CLAUDE_SKILL_DIR}/scripts/incremental.py run --out outputs/T14T ...      # refused (exit 2), nothing created or changed
```

## Safety boundaries
- Never build or validate into a baseline: not `outputs/T14T`, not `docs/t14t_corrections/`, not `data/t14s/source_slices/`. The builder's own default output folder is the baseline, so always pass `--out` and `--report`.
- Never rebuild all floors by default. Never edit a pinned slice or an earlier PR's outputs to make a build pass.
- `change-record` accepts `APPROVED_DESIGN` only with `--approval-ref` naming the user's decision. Default provenance is `PROPOSED_DESIGN`.
- A passing build, validator or verification is a technical result, not an architectural approval.
- Paths in the handoff are written in full, drive letter to extension, in code format (repository `AGENTS.md` section 0).

## Tests
`pytest tests/test_claude_skills.py -k incremental` (protected destinations refused before any write, byte-identical unaffected floors, 14 manifest failure modes, change records).
