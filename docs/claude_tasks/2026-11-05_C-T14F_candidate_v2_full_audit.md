# C-T14F: Candidate V2 도면집 독립 전수 QA + V3 실제 개선 (Claude Code Cloud)

## Source of truth
- Repo: edward321416-maker/drawing-pipeline; main at 5b109d71505bc6373264c3488c11550c3789bb01 (2026-11-05).
- PDF: docs/t14e_v2/drawing_set_candidate_v2.pdf (30 pages, 17,144,061 bytes). Recorded SHA256: 9104E66B6C74504604EF970AC567157A5320B9EED500E3C375F0C26E00AFABAB.
- Evidence: docs/t14e_v2/{sheet_index.json,sheet_manifest.json,dimension_coverage_report.json,equivalence_check_report.json,tests_report.json,visual_issues_resolved.md,unresolved_design_decisions.md,phase1_floor_audit_summary.md}.
- Caveat: Our initial ChatGPT review inspected the GitHub source and QA records but COULD NOT visually render the private 17MB V2 PDF. The attached 17-page older PDF is V1, NOT this 30-page V2. You MUST render and visually inspect every V2 page.

## Cloud preflight
- First read AGENTS.md and README.md; inspect project stack metadata files as text, never execute configuration files. Read source signatures using rg/AST before editing.
- Start an isolated Draft PR branch from the current main SHA. Preserve original main, separate thesis repo, preexisting PRs and historical HOLD records. Do not merge or freeze.
- PR #12 and #13 merged. PR #8 is merged, #9 remains Draft/open. Do not remerge overlapping history.
- No full-building GLB is committed to this GitHub repo; if source mesh is missing, proceed with PDF QA, code/registry/typography fixes and regression tests, flag geometry-dependent rebuild as MODEL_REBUILD_BLOCKED. No imaginary mesh or automatic upload of private model.
- No extra cash costs, no Modal/Claude API job without verified balances/spend limits. Claude Code Cloud subscription usage is different from Anthropic API credits.

## Confirmed source defects to fix first
1. tools/t14e_plan_sheet.py hardcodes D-407 and D-410 callout scale=50, but actual detail sheets D-407 and D-410 are 1:100. Replace all callout scales with dynamically resolved registry scales; verify reciprocal sheet/detail links and missing references.
2. tools/t14e_make_details.py ends with two scale_bar calls disabled using `if False else None`. Draw graphic scale bars for ALL ten D-401..D-410 at real print length, with no collision with title/keyplan/dimension table. A scale string alone is not sufficient.
3. tools/t14e_make_book.py uses Windows-specific font paths; tools/t14d_sheet.py retains hardcoded C-T14D title block/date. Provide portable licensed CJK font discovery, per-page embedding/test, edition/date metadata from registry. Do not redistribute font files.
4. tools/t14e_plan_sheet.py legend cross-references A-002 as floor-height info, but V2 puts the floor table at A-901. Fix stale references, and create annotation companion for A-003 without altering the user-supplied 1F PDF.
5. Q12 tests raw model check, not final composed SVG/PDF; Q13 checks selected text bounds but not title/scale bar/legend overlaps; Q14 relies on legend wording, Q15 only furniture count >=30, Q16 compares whole SVG hashes rather than furniture-only layouts; Q60 only exact-segment duplicates; Q90 FINAL negative test uses a literal stub. Add independent final geometry and visually tested mutation QA.
6. D-407 ~25 degree incline comes from minimum rotated rectangle of a 3D vertical section polygon, an apparent-slope approximation; cross-check genuine 3D travel-axis rise/run before declaring physical angle. Verify T3/T4 actual congruence, D-408 stair rise unknown, and D-409 circular-shaft Ø label only if actually circular.

## Sheet coverage and scaling
- Current PDF has 5 upper plan sheets at A3 1:250 covering 3F, 8F(+9F), 10F, 13F(+14F), 15F, plus source 1F A-003. B2,B1,2F,4F,5F,6F,7F,11F,12F are not graphically covered by their own plans.
- Source floor audit says STRICT equivalence pairs=0; only 8F/9F and 13F/14F have vertical circulation differences. Preserve user preference for representative typical floors rather than 17 duplicate full plans, BUT provide measured delta insets, floor typology matrices and source-backed plan/keyplan for every floor including 6F garden, 7F reductions, 11/12F culture and basement levels.
- A3 1:250 is not an authorized replacement for 1:200. At 1:200 the 54 x 54m building alone occupies 270 x 270mm, too tall for 3 dimension chains/title on single A3. Generate actual A1 1:200 sample AND tiled A3 1:200 sample; compare, retain existing A3 1:250 only explicitly as OVERVIEW. Never falsify scale labels.
- 1F program composition (18 subprograms) remains PROGRAM_INTENT_APPROVED; detailed location, physical market/capsule entrances, egress and construction details not approved. Existing geometry and 1F PDF preserved, no 1F_FINAL_FROZEN.

## Deliverables / gate
- Render pages 1..30 at >=150dpi and important pages at >=300dpi. Inspect every page for paper/line clarity, label crowding, clipping, graphic scale bar, dimension sources, callout direction, actual floor geometry, and font/text extraction; produce numbered contact sheet and 30-page PASS/FAIL/HOLD audit CSV with visual evidence.
- Add 12+ same-crop Before/After panels, test screenshots, cross_reference_graph.json, dimensional_truth_report.json, typical_floor_coverage.json, qa_mutation_report.json, PDF print-length QA, source_manifest.json, unresolved_design_decisions.md.
- Make Candidate_V3_drawing_set.pdf and per-sheet PDF/SVG/PNG where source access allows; if GLB is unavailable, submit actual PDF-level fixes and independent tests and mark remaining model-dependent outputs BLOCKED, not fake DONE.
- Re-run existing source tests, the 63 historical QA checks, and new negative controls (wrong callout scale, missing graphic scale, clipped legend, duplicate furniture, missing referenced sheet). Report measured pass/fail, not copies of old reports.
- New isolated Draft PR only. No auto-merge or freeze. First show real output images and PDF, then root causes, unified diffs, SHA evidence, open blockers, and decision log.
- Report: HEAD | PDF_SHA | MODEL_SHA_OR_MISSING | PAGES_RENDERED | QA_PASSED/FAILED | ACTUAL_OUTPUTS | GATE | FROZEN=false.
