# C-T14T 47-item audit — recovered text handoff and preliminary crosswalk
Date (KST): 2026-11-23
State: `SOURCE_TEXT_RESTORED_TO_STUDY_BRANCH / RECONCILIATION_PRELIMINARY / DRAWINGS_NOT_CORRECTED / NOT_APPROVED`

## Source provenance and binary limitation
The original ChatGPT Library contains four files:
1. `C_T14T_PR30_Issue_Register_47.json` (47 issues, X-01..X-15 + 32 floor-specific IDs).
2. `C_T14T_PR30_Issue_Register_47.csv` (47-issue CSV).
3. `C_T14T_PR30_Full_Floor_Plan_Audit_and_Correction_Plan_A3_20261123.pdf` (10-page original A3 independent review).
4. `C_T14T_PR30_Claude_Code_Correction_Brief_EN.md` (architecture-first instructions).

**Raw-byte materialization of Library originals FAILED in the current session.** To unblock the issue mapping, the **full text** of item 1 and item 4 was retrieved from Library and written into this new study-branch directory. Their content is inspectable and the JSON parses with exactly 47 distinct IDs. Original binary byte/hash identity is **NOT** certified. A fresh CSV was produced deterministically from the parsed JSON as `C_T14T_PR30_Issue_Register_47_from_JSON.csv` (not named as the original CSV). The **original 10-page PDF was NOT copied**; keep it as a missing original binary in this worktree and request the original from the user's ChatGPT Library only if byte-level PDF verification is required. This PDF is DIFFERENT from PR #32's 7-page reconciliation PDF.

Protected baseline references:
- PR #30 audited `1164fc0f58d943598d8e48146a02fcb3214c852e`.
- Draft PR #32 HEAD `f364a642675b08788750ca9646dd7dddbdb02c64`.
- All new files are only in `study/t14t-wp0-options-20261123`; no original 1F, source slice, floorplan outputs or V4.2 book modified.

## Preliminary reconciliation
- Original IDs read from the source JSON: **47** = common **15** + floor-specific **32**; priorities **P0 25, P1 19, P2 3**.
- Existing PR #32 R-01..R-29: **29** separate reviewer issue records (8 blocked, 15 still open, 2 resolved-unverified, 3 resolved-verified, 1 not-applicable). These status counts are NOT a resolved count for the 47 original IDs.
- D-01 measured landings **25**, D-02 no-slab cores **3**, D-03 tube-entry proposed turns **15**, i.e. **43** physical instances, not 43 more original issues.
- `AUDIT_47_TO_PR32_R29_CROSSWALK_PRELIMINARY.csv` preserves every original ID, floor, priority, classification, original acceptance text and evidence locator; links related R IDs, R statuses and relevant D01/D02/D03 measurement-instance IDs. Links are **topic/floor associations**, not independent resolution findings. **B2-01** has no exact matching R item; it remains open for WP2.
- Each original ID is conservatively `OPEN_REQUIRES_REVIEW` because cross-reference alone does not establish actual design correction or independent acceptance. Never copy R's `RESOLVED_VERIFIED` directly onto an original ID.
- The original source `12F-02` refers to a 1,558.5 m² lobby; PR #32 floor metadata gives 1,585.8 m². Record as **UNRESOLVED_AREA_DISCREPANCY** until floor-geometry and extraction are checked; don't silently overwrite the source.
- C-T14U has no confirmed delivered branch/commit/PR/artifacts; record `C_T14U_OUTPUT_UNAVAILABLE`. Do not block text reconciliation on duplicate-work checking; do not claim C-T14U completed.

## Existing study assets and where to start
- `studies/t14t_wp0_r1/overlays/`: **15** conceptual source-preserving SVGs for B1, 2F–15F. They mark problem locations only; NOT measured buildable decks/approved sections.
- `studies/t14t_wp0_r1/WP0_GEOMETRY_ACTION_REGISTER_43.csv`: 43 measured issue instances.
- `studies/t14t_wp0_r1/WP1_BASELINE_GRAPH_GAPS.csv`: 16-floor graph snapshot, 0 independently COMPLETE floors, real continuous clear width `NOT_MEASURED`.

## User decision boundary, already supplied
- U-01: original ZIP delivery was designated sufficient by user, but **this study branch currently contains source-text records, not original PDF or ZIP bytes**. The 47-issue machine-readable reconciliation can proceed; exact original-packet delivery still remains a separate step.
- U-02: `C_T14U_OUTPUT_UNAVAILABLE` until proven otherwise.
- U-03..U-08: research options A/B/C first; explicit user decisions only for real changes to protected slab, core, escalator or equivalent impactful design geometry.
- U-09: spatial programme improvement **without geometry changes** is authorized to proceed as a proposal.
- U-10: only a **separate book candidate** can be made; do not edit/integrate the 65-page V4.2 protected original or freeze.
- U-11: `CODE_COMPLIANCE_NOT_VERIFIED`, separate structural/egress/accessibility audit required before final design approval.

## Next deliverable gates
1. Independently review/verify the 47 crosswalk associations one by one against source issue wording, PR #32 R-01..R-29, floor metadata/visual tile and 43 metric instances. Attach exact evidence URLs and decide OPEN / UNVERIFIED / REVIEWED statuses; no automatic closure.
2. WP0: produce separate dimensioned architectural plan **and section** A/B/C alternatives for problem locations (especially B1 core exception, 2F, 7F, 12F) and test actual continuous slab, structural/egress assumptions explicitly. Do not alter verified geometry without approval.
3. WP1: add omitted passenger transport roles, evaluate physical clearance against actual free-space polygons; no floor `COMPLETE` until every required node & route assessed.
4. WP2: non-geometry program improvements floor by floor, separate proposal versions and measured area tables.
5. WP3: render and visually inspect all 32 PDF outputs and actual print scale; WP4: separate 65-page book candidate only. All original V4.2 sheets remain protected pending review.
6. Note the old producer report's two background shell tasks `b4b6m3b8f` and `bcys0oddq` have no demonstrated completion; do not claim background execution.

**No merge, deployment, Freeze, original-model mutation, user architectural approval, or code compliance was performed in this handoff.**
