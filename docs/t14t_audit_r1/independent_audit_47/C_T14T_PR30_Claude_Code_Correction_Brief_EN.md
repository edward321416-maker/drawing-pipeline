# C-T14V — Architecture-first correction brief from independent PR #30 floor-plan audit

## Grounded review baseline
Repo: edward321416-maker/drawing-pipeline
HEAD: `1164fc0f58d943598d8e48146a02fcb3214c852e`
Draft PR #30: https://github.com/edward321416-maker/drawing-pipeline/pull/30
Review packet manifest: `https://github.com/edward321416-maker/drawing-pipeline/blob/1164fc0f58d943598d8e48146a02fcb3214c852e/docs/t14t_corrections/review_packet/manifest.json`
Source of issue IDs: `C_T14T_PR30_Issue_Register_47.json` attached alongside this brief. The document contains 47 actionable items and pinned image/tile paths.

**Independent ChatGPT image review:** All 16 floor-plan JPEG previews and all 256/256 lossless native-resolution PNG tiles from PR #30 were opened and inspected. The preserved 1F reference was viewed as a preview. Original source GLB and 32 A1/A3 output PDFs were NOT independently rendered/verified in this review. The producer's deterministic PASS is not a human architectural or code-compliance approval.

## Mission
Produce a coordinated, architecturally credible graduation drawing-book candidate. Stop skill-library work. Claude Code owns drawing generation and deterministic checks only; ChatGPT independently reviews the real GitHub drawings. Preserve every prior baseline, including source slices, the original 1F reference, outputs/T14S, outputs/T14T, main, and existing PRs. Never merge/freeze/release without the user.

### Work packages — priority order
**WP0 / C-T14U architectural decisions:** Resolve 25 D-01 escalator-landing conflicts, D-02 2F core D and 7F cores C/D with no slab, D-03 all 15 T3/T4 rotated lift entry proposals (12F -75 degrees requires a dedicated close-up), and D-08 T1 spiral-ramp access from B1 through 5F. Reuse any already-running C-T14U production; do not start a duplicate task. For structural geometry-changing solutions, produce separate `PROPOSED_ONLY` A/B/C plan and section alternatives first, with supports, slab/void conflicts, floor-level connectivity, and approval consequences. Do not modify verified geometry or claim a design option is approved.

**WP1 / correct access and clearance reporting:** Audit floor-by-floor every core, EV1/EV2/PL, T3/T4, T1, escalator, freight lift FR, public entrance, unit door and WC. Explicitly list REQUIRED/CONNECTED/PROVISIONAL/EXCLUDED/NOT_ASSESSED nodes, including B2's EV1/EV2 and 3F's T1. Do not claim `COMPLETE` unless all required circulation elements are assessed and connected on verified walkable slabs. Compute clearance against actual door swings, columns, furniture and corridor free-area POLYGONS, not centerline-only separation. Separate code-compliance review from deterministic geometry audit.

**WP2 / floor-by-floor architectural program, not generic furniture:** Use the issue register's 32 floor-specific items. Refine B2/B1 market and food logistics; 2F south-west no-slab and retail; 3F-5F differentiated retail/experience; 6F intermediate garden + food; 7F partial slab/capsule; 8F-9F differentiated retail and atypical 8F->9F 4.2m gap; 10F kitchen/serving/washing/refuse/store/FR; 11F stage/backstage/audience/foyer scale; 12F 342m2 central void/exhibition with protected edge; 13F actual workshop material/ventilation/storage flow; 14F community rooms with meaningful program; 15F public roof garden + food operation. DO NOT invent supporting structural design, legal egress or approved operational programs. Use clear `PROPOSED_DESIGN` layers.

**WP3 / drafting and multi-level QA:** Produce 1:200 vector plans with readable wall/cut hierarchy, room numbers and schedules, actual main dimensions, column/core/capsule and void boundaries, door swings, section callouts, levels, north symbol/scale bar and clear provenance legend. Keep 1F at its established 1:400 site-plan status unchanged. Cross-reference each escalator/shaft on the levels above and below; render A1 and A3 PDFs independently and publish small actual page previews/tiles for all 32 new PDF outputs. Test physical scale and readability. Never assume the prior technical test suffices.

**WP4 / coordinated drawing book:** The previous V4.2 candidate contains Part I 16 A3 pages and Part II 49 pages. These are an EXISTING CANDIDATE, not a finished book. Make a sheet/issue dependency matrix for G-106 plan, G-108 elevations, G-109 sections, G-111 details, A-003 1F reference, 16 new floor plans, E-201..204, S-301..305, D-401..410. Update only drawings that actually depend on an approved correction. Preserve earlier candidate pages until the user approves replacement. Avoid duplicate old 1:250 program overviews masquerading as detailed floor plans.

### Production gates
G0: pinned source geometry and first-floor master unchanged; guard SHA and protected paths.
G1: deliver alternative decision plans/sections for every geometry-affecting proposal, without source modification.
G2: once decisions are authorized, change only affected floors and related sections. For common generator edits run ALL-FLOORS regression. Use new output and report paths, no overwrites.
G3: each corrected PDF/PNG/SVG/DXF exported validly, no text/geometry clipping, sheet size and scale measured.
G4: publish each changed floor preview + native-pixel lossless tiles and a concise A3 review PDF to a Draft PR. Differentiate `REMOTE_BYTE_IDENTITY_PASS` from real ChatGPT connector readback, which only ChatGPT can attest.
G5: hand back exact PR/HEAD, 47 IDs classified RESOLVED/OPEN/UNVERIFIED with evidence links, and the proposed book page mapping. Independent review and user architectural approval remain pending.

**Do not implement or upgrade custom Claude Code skills, change global config, or build a new workflow framework for this work. Focus only on architectural drawing quality and the integrated book.**