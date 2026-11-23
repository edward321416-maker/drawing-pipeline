# Personal installation recommendation (not executed)

Nothing in this branch writes to `C:\Users\admin\.claude\skills\`, changes global Claude configuration or enables cross-project behaviour. This note only says what could be copied later, after independent review and the user's explicit instruction.

## Today: install none of the five as they are
They name this repository's paths, tools or metadata schema, so in another repository they would trigger and then fail.

| Skill | Why it stays project-only | Reusable part, if extracted |
|---|---|---|
| `drawing-source-guard` | protected list and `t14s.source` are repository specific | the approval and freeze wording lint (`scan_text`) |
| `floorplan-incremental-build` | `outputs/T14T`, `build_all.py`, `validate_t14t.py` | the snapshot and untouched-floor check for any folder with a SHA manifest |
| `vertical-circulation-audit` | reads the C-T14T metadata fields | none until a second builder shares the schema |
| `github-visual-review-packet` | needs `tools/t14r/export_visual_review.py` | remote byte-identity check (git blob SHA against the tree of a pushed commit) |
| `skill-harvester` | registry entries are about this repository | the rules in `references/decision_rules.md` and `registry.py` with an empty registry |

## Candidates worth writing for personal use (none exists yet)
1. `stacked-draft-pr-delivery`. Evidence in the registry: PR chain #29, #30 and the tracking-branch trap seen in this task. It needs no repository path. Status `CANDIDATE`, to be written and tested first.
2. `github-remote-byte-identity`, extracted from `packet_check.py remote`. Depends on the `gh` CLI only.
3. `skill-harvester` with an empty registry, after one more harvest cycle shows it changes decisions.

## If the user decides to install one later
Copy the skill folder to `~/.claude/skills/<name>/`, remove repository-specific paths, run `claude plugin validate ~/.claude/skills` and re-run the tests for the extracted copy. A personal skill overrides a project skill of the same name, so use a different name.
