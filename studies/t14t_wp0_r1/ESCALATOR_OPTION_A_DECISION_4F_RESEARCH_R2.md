# WP0 / Selected concept A: functional escalators, protected original geometry

**Decision received:** Escalators MUST remain functioning primary vertical circulation. Study option A (connected arrival/boarding platforms) first. The user did NOT approve editing source slabs, openings, cores, stairs, shafts, landing hardware, or the V4.2 drawing book.

**State:** `OPTION_A_DESIGN_DIRECTION_SELECTED / 4_FLOOR_PLAN_SECTION_PROXY_STUDY_COMPLETED_LOCALLY / SOURCE_GEOMETRY_UNCHANGED / ACTUAL_SECTIONS_PENDING / NOT_APPROVED`.

## New locally generated review artifacts (not uploaded to GitHub)

- Local PDF: `/mnt/data/WP0_A_Study_20261123/WP0_A_ESCALATOR_ACTIVE_PLAN_SECTION_STUDY_A3_10P.pdf` — 10 A3-landscape pages, 4 priority-floor plan diagrams, 4 model-axis projected schematic sections, decision gates. Exact local artifact path only; **not a repo file**.
- Local ZIP: `/mnt/data/WP0_A_Study_20261123/WP0_A_4F_PLAN_SECTION_PRELIMINARY_PACKAGE.zip` — PDF, 8 editable vector SVGs (4 source-projection plans + 4 model-axis schematic sections), report README and SHA manifest.
- Local PDF QA: 10/10 pages text present, page dimensions A3 landscape and zero out-of-page text spans; all pages rendered and visually reviewed as a contact sheet; SVG XML 8/8 parsed; ZIP integrity verified.

The plan polygons were traced/simplified from the **verified PR #30 projection source slices at approximately 0.18m simplification tolerance**. They are presentation diagrams, **NOT authoritative 1:200 final CAD plans**. Tube circles are diagrammatic. Sections show **model-axis X-Z or Y-Z projections**, not original-GLB mesh cuts. They must NOT be mistaken for validated slab-support/egress/buildability details.

## Geometry / model-axis measurements independently re-read from PR #30/PR #32

| Floor | FFL (m) | D-01 coordinates (m) and axis z | Existing gap | Audited net new deck area | Exceptional issue |
|---|---:|---|---|---|---|
| B1 | -5.4996 | (-4.5,-15), boarding z_low=-6.1 | no direct route; inside core | 9.4m² is a *rectangle arithmetic result*, **not a feasible option A deck** | Core D occupied, A cannot solve by adding local deck alone |
| 2F | +6.0004 | (5,13.89), arrival z_high=6.0; (1,13.89), board z_low=5.4 | 5.6m each along +Y | 18.6m² per landing (PR32 audited) | Core D has 0m² on slab; nearest slab 17.0m |
| 7F | +31.0010 | (33,14.16), arrival z_high=31.0; (29,14.16), board z_low=30.4 | 4.8m each along +Y | 15.8m² per landing (PR32 audited) | Core C and D each 0m² on slab; each 17.0m from slab |
| 12F | +57.0004 | (29,3.5), arrival z_high=57.0; (33,3.5), board z_low=56.4 | 4.5m each along -Y | 14.6m² per landing (PR32 audited) | Existing central void 342m²; T4 turn -75° gives 100% model apron on slab, but door clear opening not inspected |

**Axis elevations are not proven walkable finished tread/landing elevations.** Approximate 0.6m differences from FFL at some boarding axes cannot be erased by simply drawing the deck to FFL: verify cut mesh/truss/pit/real door thresholds.

Original slice SHA:
- B1 `c4b82d37e4c04b722dfccc0bbbb22546c69b90ecce07c29883e9408fb96e2525`
- 2F `a80696fe8ff486103cc1192641dbe68eed2d7b7ddcb4458d53ebc8bbe50c523e`
- 7F `db8d579e5916509f9fc0f798a8054bf7e5f6ffa0e5163059ff020291288efbeb`
- 12F `cfe535648a272d609b46727d7a937f7ec77eca66364c5bd5d7e54dcd09cdca83`.

## Unresolved prerequisite before actual design correction

- **First user architecture decision:** Must 2F core D and 7F core C/D be floor-accessible? Option C1: plan physical access to all three (around 17m new deck/bridge connections, *study only*) vs C2: keep cores as non-enterable pass-through at those levels until independent egress/capacity validation. Neither is structurally nor legally approved.
- **No change to escalator functional role:** The active-escalator intent is fixed; the core access choice does not cancel that intent.
- Await full actual section/GLB mesh availability or independent evidence before claiming 1:100 or 1:50 dimensioned buildable sections.
- Don't alter original model/PR30/PR31/PR32/1F/V4.2 or merge/freeze. Distinct 47-ID source audit and existing preliminary crosswalk remain `OPEN_REQUIRES_REVIEW`.
- WP1 actual continuous clearance, door sweeps and independent egress/structural/accessibility validation remain pending.

**Provenance note:** The PDF + SVG zip exists in this ChatGPT session's sandbox only, not in the user's Windows path or GitHub. The decision record is on this isolated GitHub study branch.
