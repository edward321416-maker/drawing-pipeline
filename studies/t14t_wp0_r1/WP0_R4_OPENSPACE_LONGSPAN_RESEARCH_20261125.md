# WP0 R4 — Preserve south open space; functional escalators & three accessible cores
Date: 2026-11-25 KST
State: `OS1_OPENSPAN_PRIORITIZED / OS2_UPPER_SUSPENSION_CONTINGENCY / OS3_PARTIAL_SUPPORT_IF_NEEDED / MODEL_UNMODIFIED / DESIGN_NOT_APPROVED`

## Explicit user decisions (reaffirm, do not re-ask)
- Operating escalators are mandatory primary vertical circulation; never represent them as decorative/inactive.
- 2F core D and 7F cores C & D must be physically accessible from those floors *in the eventual design*.
- Maintain southern architectural void/open-space expression as the highest spatial preference.
- Research a **no-new-intermediate-column long-span bridge** first; only consider local/new support if structural evidence rejects column-free options.
- **No modification of the verified model slabs, cores, structural walls, landing hardware, voids or the 1F and V4.2 drawings is approved.**

## Direct source checks — PR #30 and PR #32
- Pinned PR30 `1164fc0f58d943598d8e48146a02fcb3214c852e`, PR32 `f364a642675b08788750ca9646dd7dddb02c64`.
- Core centerlines (model XY): 2F D (-6,-12), 7F D (-6,-12), 7F C (42,-12). Existing verified slab starts at model Y=+5 along those locations; **17.0m planar geometric separation** to the core north wall. Model orientation +Y is not the geographic north arrow.
- Actual cut north-wall linework remains continuous: 2F D X[-8.999,-4.291,-3.001]; 7F D X[-8.999,-6.035,-3.001]; 7F C X[39.001,41.965,44.999] at Y≈-12. No confirmed door opening in the required north wall.
- Levels, model slice floor Z (m): 1F 0.0004, 2F 6.0004, 3F 11.0004; 6F 26.0004, 7F 31.0010, 8F 36.0004. Floor-to-floor differences at bridge: 2F below 6.0000m / above 5.0000m; 7F below 5.0006m / above 4.9994m. These are NOT finished clear headroom or true sections.
- Source `floor_3F_slice.json` has **two separate slab projections**: `A-FLOR_glassfloor` and `A-FLOR_s7_3F`. Comparing only `projection[0]` misleadingly suggests no main upper slab; the original `A-FLOR_s7_3F` exists above the proposed 2F link. 8F likewise has verified main slab at the corresponding model XY. **This does not prove any suspended anchor, capacity or connection.**
- Source columns near D: centroid approximately X=-8.4 at Y=-9/0; near C: X=44.4 at Y=-9/0; typical source bbox 0.9 × 0.9m. The source bbox gap for the illustrated deck *outer envelope* width `W`, centered on the core, is roughly `1.95m - W/2` (this is geometry-only). W2.4 =>0.75m, W2.7=>0.60m, W2.9=>0.50m, W3.2=>0.35m. This is **not** a regulatory clearance or measured unobstructed passage.

## Option structure (all PROPOSED_ONLY)
- **OS-1, first:** 17m gross deck run × 2.4m gross width, double-end-bearing structure at core and existing slab ends, NO intermediate column. 40.8m² per core × 3 = **122.4m²** gross *study footprint*. Both bearing points, their reinforcement, load path, deflection and pedestrian-induced vibration must be assessed by structural design. Core structural/fire wall cutting is not authorized; doorway shown only dashed.
- **OS-2, second:** retain open space with upper-floor hanging/suspended structural concept. Potential 3F/8F overhead floor plate is verified as *spatially present*; anchor construction, force path, loading, seismic compatibility, equipment and fire compartmentation **not verified**. Do not promote to supported design without original GLB/structure details and engineer check.
- **OS-3, conditional:** partial intermediate support only after OS-1 and OS-2 are rejected on actual structure calculations. This study does **not** place new columns or redesign the protected void.

## Important unresolved blockers and action gates
1. **Door/stair connection:** 0 of 3 confirmed north-facing openings; actual core stair landing and wall/fire-rating must be verified before 1:50 doorway placement. The base wall must NOT be shown as already opened.
2. **End support and main-slab interface:** bearing/attachment, force path, existing slab reinforcement, permanent and construction loads, serviceability and vibration are NOT_ASSESSED.
3. **Gross 2.4m does NOT equal net usable width.** Need guardrails, beam outer width, door swing, usable egress, accessible routes, maintenance and smoke/fire zoning.
4. **The 2F/7F escalator D-01 landing failures remain independent and open** (four local landing cases); 25 D-01 issues building-wide remain open. Fixing cores alone does not validate escalator movement.
5. **No verified original GLB sections.** R4 diagrams use local source coordinates + FFL, not raw mesh cuts, verified loading, or finished 1:100/1:50 CAD.
6. Record original audit IDs `X-02`, `2F-01`, `7F-01`, reviewer `R-02` OPEN; do not automatically close any of the 47 original audit IDs.
7. Structural code study must consider current KDS 41 12 00 building loads, KDS 41 10 05 structural general criteria, and human-induced vibration as a serviceability issue (see AISC Design Guide 11). Standards cited to identify engineer's checks, **NOT a certified legal compliance review**.

## Local outputs created and internally QA-checked (not uploaded to repo)
- `/mnt/data/WP0_R4_OpenSpan_20261125/WP0_R4_OPEN_SPAN_BRIDGE_STUDY_A3_8P.pdf` (A3 landscape vector, 8 pages; SHA-256 `307efcaf50a88026d3d81371de287cf5e5882f62c90ae8cc739a25bbc3be63bf`).
- `/mnt/data/WP0_R4_OpenSpan_20261125/WP0_R4_OPEN_SPACE_PRIORITIZED_STUDY_EDITABLE_PACKAGE.zip` (PDF, 3 editable model-coordinate focus plan SVGs, 2 editable model-level proxy section SVGs, evidence JSON, README, SHA manifest; SHA-256 `fb632c41cb84bc78056f266cce965974d14481ac899c43aa42d648fd4fd609fb`).
- Validations: PDF pages 8/8 A3 with text all inside page; visual render/contact sheet reviewed, selected pages full-resolution inspected; 5/5 SVG XML parsed; ZIP CRC and internal manifest SHA 8/8 verified.
- Reconstructed only the **focus model geometry** shown and level-only proxy sections; these are editable presentation diagrams, NOT CAD-derived architectural working drawings or structural engineering details. Original R3 artifacts and their SHA erratum remain unchanged.

## Next engineering verification before architectural approval
- Obtain raw original GLB/section and core stair geometry, actual structural/slab/framing source, column/shear wall load path; trace actual door and slab seating.
- Size/check OS1 reactions and bridge strength/deflection/vibration, then OS2 upper anchors if OS1 fails. Compare free/occupied space under bridge and actual clear width.
- Coordinate 2F/7F D01 escalator landing connections with bridge and visitor path.
- Return a specific proposed change set (core north wall opening location/width, bridge foundation & end seats and floor corrections) to the user for explicit approval. Do not modify verified geometry or merge/freeze.

**All source/prod paths remain unchanged; the user approved research priorities, NOT geometry changes.**
