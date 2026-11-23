# C-T14T WP0/WP1 — geometry-preserving design study R1

**State:** `STUDY_ONLY_NOT_APPROVED` · `NOT_FOR_V42_INTEGRATION` · `SECTION_UNVERIFIED` · `CODE_UNVERIFIED`.

## Immutable source and working boundary
- Study branch was created from Draft PR #32 HEAD `f364a642675b08788750ca9646dd7dddbdb02c64`.
- The verified model source remains PR #30 HEAD `1164fc0f58d943598d8e48146a02fcb3214c852e` with pinned `data/t14s/source_slices`; **no original slab, core, escalator, opening, PDF or V4.2 book file was changed**.
- **These SVGs are newly generated review diagrams**, not the previously produced A1/A3 drawings. They trace source slab/core/tube/column cut-line segments but do NOT reconstruct a certifiable floor-plate polygon, demonstrate buildable structures or test clearance.
- No external graphics / remote dependencies, no claim of independent visual verification. Numbers come from existing PR #32 measurement JSON; no newly recomputed physical capacity.
- No PR, merge, FREEZE or final approval requested.

## New spatial study drawings (editable SVG, 15 affected floors)
All measured D01/D02/D03 placements are now represented on separate source-preserving concept overlays for **B1 and every floor 2F–15F**: `overlays/WP0_<floor>_CONCEPT_ONLY.svg`. **B2** has no D01/D02/D03 measured placement and therefore is not included in WP0 overlays. All drawings are only **concept geometry annotations**.

| Floor(s) | Measured items | Required future checks |
|---|---|---|
| B1 | D01 boarding inside core | Core conflict; local patch must not be treated as an approved solution |
| 2F | 2 D01, 1 D02 core-D, 1 D03 T3 | Missing slab for core-D; landings outside slab; proposed entry direction |
| 3F | 1 D03 T3 | Entrance orientation and actual usable threshold |
| 4F–6F | 5 D01, 4 D03 (T3 4F/5F/6F and T4 6F) | End slab continuity, support and entrance feasibility |
| 7F | 2 D01, 2 D02 cores C+D, 1 D03 T4 | South slab missing, 17m core-to-slab distance |
| 8F–11F | 8 D01, 4 D03 T4 | Deck footprints, columns, hall and vertical sections |
| 12F | 2 D01, 1 D03 T4 -75° | Different turn due to slab edge; actual doorway must be checked |
| 13F–14F | 4 D01, 2 D03 T4 | Continuous access and section compatibility |
| 15F | 1 D01, 1 D03 T4 | Arrival landing and garden-level section/access |

Legend: orange dashed footprint = **schematic gross envelope**, derived from the builder's 3.6m escalator width, 2.6m landing, and measured longitudinal gap; it is NOT clipped to verified slab and does NOT equal the audited net deck polygon. Red = unslabbed core/exception. Blue = location of proposed entry direction, **NOT a drawn door**. The drawings use consistent model-coordinate framing, not a certified plotting scale.

## D01 / D02 / D03 measured action linkage
`WP0_GEOMETRY_ACTION_REGISTER_43.csv`: 25 D01 instances, 3 D02 cores, 15 D03 lobby-entry cases. Each row carries floor/source coordinates, design-option study action, known quantitative measurement and missing plan/section evidence. This is **NOT** the separately reported 47-ID audit register; it cannot be claimed as 47 item reconciliation.

Study alternatives (NOT recommendations for construction):
- **A — local landing deck/bridge**: 9.6–19.0m² modeled new area per normal affected end, usually no column within the gross footprint. Structural anchorage, fire separation, escalator pit/truss, edge guard, verified continuous accessible width, slab load and true section must be studied. B1 core exception cannot use A as an ordinary local patch.
- **B — remove escalator from transport network**: does not fix missing slab, demands independent proof of stair/lift capacity and requires a thesis/program choice. Remains a contingency, not a validated workaround.
- **C — move escalator landing onto verified slab**: 12.1–14.7m translations when measurable, same order as escalator body length 9.8–12.4m; changes source model and affects sections, circulation and programme; NOT authorized.
- **D02**: keep shaft/core non-enterable, or study ~17m structural connection; neither counts as accessible core.
- **D03**: proposed +45° T3 / -45° T4, except 12F T4 -75°. Geometrically measured apron-on-slab is not a door/capsule threshold clearance certificate.

## WP1 baseline actually inspected
`WP1_BASELINE_GRAPH_GAPS.csv`: extracted from all 16 original C-T14T metadata files and independent circulation audit at PR #32. The independent status is 2 `CONNECTED_WITH_OPEN_ITEMS`, 14 `INCOMPLETE`, and **0 `COMPLETE`**. EV1/EV2/PL assessed roles not resolved; T1 ramps not fully modeled on some levels. `actual_min_clear_width_m` is intentionally `NOT_MEASURED`, not an inferred 1.2m clearance.

## Production gates before any approved drawing correction
1. Reconcile the separate 47-ID register with existing 29 reviewer items and 43 D01/D02/D03 measured instances, preserving original identifiers and explicit many-to-many linkage.
2. Complete plan/section proposals on every affected floor, including independently determined deck footprint, structural support, guards, escalator truss/pit, equipment swing and accessible route geometry.
3. For WP1, add all visitor-relevant lift/stair/ramp nodes to a 3D building graph; make exclusions explicit, and independently measure minimum continuous clear width with door openings and partition geometry considered. `circulation_complete` must agree with independent audit, not just floor-plan route connectivity.
4. Do not alter verified geometry or V4.2, approve, merge, freeze, or claim code compliance without separate user authorisation and technical review.

## Verification performed for this study
- All 4 SVGs committed in separate branch and fetched back via GitHub; source warning and XML open/close confirmed, no remote assets or scripts in SVG text.
- CSV created from 43 PR #32 measurements and 16 PR #30 floor metadata / PR #32 circulation audit records.
- No SVG visual raster QA, plan-section comparison, structural calculation, clearance proof, or original GLB readback completed; keep these open.
