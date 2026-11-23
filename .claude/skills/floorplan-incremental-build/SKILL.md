---
name: floorplan-incremental-build
description: Use when a correction names specific floors or issue ids and the 16 generated floor plans (B2, B1, 2F-15F) must be updated without regenerating all of them, or when a shared generator change must be checked against floors that were not meant to change.
metadata:
  status: CANDIDATE_UNREVIEWED
  version: 0.1.0
---

# floorplan-incremental-build

Plans and audits a selective rebuild of floor deliverables (SVG, DXF, A1 PDF, A3 split PDF, PNG, metadata). Status: **candidate, not independently reviewed.**

## Trigger
- A correction brief lists issue ids and affected floors.
- Source under `src/t14s/` or a builder/validator under `tools/` changed and other floors must be shown unaffected.

Not for: a first full build, or tasks that add a new floor family (use the builder's full run).

## Inputs
Issue id(s), affected floors, PR base ref, outputs folder (default `outputs/T14T`).

## Procedure
1. Guard first: `drawing-source-guard` (sources, manifests).
2. `python -I ${CLAUDE_SKILL_DIR}/scripts/incremental.py scope --base <ref> --floors 3F 8F` prints `FLOOR_SCOPED` or `ALL_FLOORS_REGRESSION` and the ordered commands. A change under `src/**`, `tools/*/build*.py`, `validate*.py`, `package*.py` or `tests/**` widens the scope.
3. `incremental.py snapshot --outputs outputs/T14T --out <snap.json>` before building.
4. Run the project builder for the affected floors only, then its focused validator: `python -I tools/t14s/build_all.py --floors 3F 8F`, `python -I tools/t14s/validate_t14t.py --floors 3F 8F`. Focused tests first.
5. If scope is `ALL_FLOORS_REGRESSION`: run `python -I tools/t14s/validate_t14t.py` on every floor. The validator re-plans each floor and compares it with the committed metadata, so an unintended change shows up there.
6. `incremental.py verify-untouched --outputs outputs/T14T --snapshot <snap.json> --floors 3F 8F` fails if any other floor's bytes changed or the manifest is stale or drops a floor.
7. `incremental.py change-record --issue <ID> --floors 3F 8F --outputs outputs/T14T --snapshot <snap.json> --out <docs/task/change_records.json> --test focused=PASS --decision D-01` writes one record per issue id.
8. Then `vertical-circulation-audit` for floors with escalators, lifts or cores, and `github-visual-review-packet` for the changed floors only.

## Outputs
Scope plan, snapshot JSON, verification JSON, and `C-T14-CHANGE-RECORDS-1.0` records: issue id, floors, generated files with SHA256, tests, unresolved decision ids, provenance class.

## Example
```
python -I ${CLAUDE_SKILL_DIR}/scripts/incremental.py scope --base origin/claude/t14t-targeted-corrections-20261123 --floors 3F
{"scope": "FLOOR_SCOPED", "floors": ["3F"], ...}
```

## Safety boundaries
- Never rebuild all floors by default. Never edit `data/t14s/source_slices/` or an earlier PR's `outputs/` folder to make a build pass.
- `change-record` accepts `APPROVED_DESIGN` only with `--approval-ref` naming the user's decision. Default provenance is `PROPOSED_DESIGN`.
- A passing build, validator or `verify-untouched` is a technical result. It is not an architectural approval.
- Paths in the handoff are written in full, drive letter to extension, in code format (repository `AGENTS.md` section 0).

## Tests
`pytest tests/test_claude_skills.py -k incremental`.
