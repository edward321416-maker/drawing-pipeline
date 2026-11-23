# Harvest decision rules

Apply in order. Stop at the first rule that matches.

| # | Condition | Action |
|---|---|---|
| 1 | The method is a repository fact (path, naming, a one-off setting) | Put it in `AGENTS.md`, not in a skill |
| 2 | A script or test can enforce it fully | Automate it. A skill is only for judgement that remains |
| 3 | It fits inside an installed skill's trigger | `IMPROVE_EXISTING` with `improve_target`. Edit that skill's references or script |
| 4 | Seen in one task only | `OBSERVED_ONCE`. Record evidence, expected reuse unknown. No skill |
| 5 | Evidence from 2 or more distinct tasks and no comparable skill | `CANDIDATE` (new skill) |
| 6 | Evidence from 2 or more tasks but comparable skills exist | Write `why_not_improve` or switch to rule 3 |
| 7 | Skill written, linted, positive and negative tests pass | `IMPLEMENTED_CANDIDATE`, `independent_review: PENDING` |
| 8 | Same, and the author recommends promotion | `PROMOTION_RECOMMENDED` (needs `tests_passed`). Still not verified |
| 9 | An independent reviewer accepted it | Reviewer sets `VERIFIED` with `reviewer_ref`. Never the author |

## Evidence line
`task` (which completed task), `ref` (`path:`, `pr:`, `branch:`, `brief:` or `doc:` prefix; `path:` must exist), `reduced` (the error, repeat or manual step it removed, stated factually).

## Personal vs project
Project first. A skill is a personal-install candidate only if it names no repository path, tool or schema. Write the recommendation in `docs/claude_skills/PERSONAL_INSTALL_RECOMMENDATION.md`. Installing globally needs the user's explicit instruction.

## Workflow-lesson entries
A repeated build failure or review finding becomes a line under the owning skill's registry entry (`notes`) with the evidence, and later a change to that skill's references. It is not a new skill.
