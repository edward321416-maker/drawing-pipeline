# WP0 R3 / 2F + 7F functional core entry bridge research — decision + evidence

**User decision 2026-11-23:** Keep escalators operating as primary vertical circulation; make **2F core D and 7F cores C/D all floor-accessible by design**. The user **did not authorize** changing validated slab/core/wall/opening/escalator geometry.

State: `S1_PRELIMINARY_STUDY_FAVORED / 3_CORE_LINKS_PROPOSED_ONLY / STRUCTURAL_EGRESS_ACCESSIBILITY_NOT_VERIFIED / ORIGINALS_UNCHANGED`.

## Source evidence actually re-read
- PR #30 pinned `1164fc0f58d943598d8e48146a02fcb3214c852e`: 2F floor Z `+6.0004`, 7F `+31.001`; 1F Z `+0.0004`, 3F `+11.0004`, 6F `+26.0004`, 8F `+36.0004`.
- PR #32 pinned `f364a642675b08788750ca9646dd7dddbdb02c64`: three cores each 36m² bounding area, exactly 0m² on their floor's verified slab, nearest verified slab 17m, all four 2.6m peripheral apron directions 0% on slab. Existing slab remains at model Y=+5, core north wall at Y=-12.
- Core D model X range [-9,-3], center X=-6; 7F core C range [39,45], center X=42. Bridge model Y=-12..+5 (17m), branch choice only, not a modified BIM structure.
- Column grid near D: source column centroid x=-8.4 at y=-9,0; near C x=44.4 at y=-9,0. Screened against source column segment bounding rectangles about 0.9 x 0.9m.
- Original source-trace plan SVGs from the preceding study are visually simplified with epsilon ~0.18m, **not authoritative CAD or full original GLB**. No source geometry/hash mutation was performed.

## Quantified reversible schemes (model-coordinate calculations, not structural sizing)

| Study | Width/profile | New deck/core | Three cores total | Minimum nearest source-column-edge gap | Assessment |
|---|---|---:|---:|---:|---|
| S1 | 2.4m straight 17m | 40.80m² | 122.40m² | 0.75m | **Study first**: lower added slab footprint and greater column clearance |
| S2 | 3.0m straight 17m | 51.00m² | 153.00m² | 0.45m | Keep as an alternative only; confirm railing and unimpeded real clear-width |
| S3 | 2.4m straight + 3.6m-wide, 2.6m-deep core-side local apron | 43.92m² | 131.76m² | 0.15m | Core entry shape comes very close to existing columns; **not recommended unchanged** |

- 2F S1 new proposed area: 40.8m²; 7F S1 two decks: 81.6m².
- All scheme footprints do not geometrically overlap the **approximately traced** original slab area or existing column bounding rectangles, but this proves neither structural bearing, true walkway clear-width nor valid egress.
- Diagrammatic 0.5m lap onto existing source slab at Y=5..5.5 is a **study interface marker**, not a new slab-area or proof of attachment.
- Core north wall opening at Y=-12 is **NOT model-verified as a real door**; graphic gate is a *placeholder*, not permission to cut the structural/fire-rated wall.
- Full 17m structural load path is **NOT verified**. Neither single long-span member nor side-column-dependent support hypothesis has engineering design; source columns may exist beside the path but using them as supports requires separate design and approval.
- Source-level Y-Z sections are **model-coordinate schematic** only. They are NOT original GLB cut, do not size beam/truss, guards, risers, pit, anchorage, fire stopping or true headroom.
- **Escalator arrival/boarding gap remains an independent D-01 open issue.** Fixing core access does not close any of the 25 landing issues.
- No 47-item register issue status is automatically marked resolved. D02 links to `X-02`, `2F-01`, `7F-01`, and PR32 `R-02`.

## Created and checked in this ChatGPT runtime, not in this GitHub branch
- Local A3 PDF: `/mnt/data/WP0_Core_Access_R3/WP0_R3_2F_7F_CORE_BRIDGE_17M_ALTERNATIVES_A3_10P.pdf` (10 pages, final SHA-256 `9999ca8bdb73540dc40409c77ffde31ef45ae7ef0bd0b14321d0bf62d8c304b3`).
- Local ZIP: `/mnt/data/WP0_Core_Access_R3/WP0_R3_2F_7F_17M_BRIDGE_RESEARCH_SOURCE_AND_PDF.zip` (8 editable SVG, PDF, geometry JSON, README, checksums; final SHA-256 `e0793244ebece67c034e0a39068889837c27f96c2be002e7f3749a667a341134`).
- Checks run: 8/8 SVG XML parses; 10/10 PDF A3 landscape pages have text and all bounded text inside page; all 10 pages rasterized and contact-sheet visual QA; ZIP CRC/integrity pass; 3/3 proposed bridges screened by Shapely against source-trace exterior and selected nearby source columns. These are not independent engineering or CAD/GLB validations.
- Both are **local generated artifacts only**: no GitHub PDF or SVG commit claim.

## Next work / explicit approval gates
1. **Before changing the core wall:** inspect source-GLB/actual sections, wall construction, existing door/swing, fire compartmentation and core's intended stair usage, then ask the user for **specific north-wall doorway geometry approval**.
2. Verify load path / bearing at core and main slab, and compare feasible 17m long-span vs lateral beam/support from existing columns. Column locations alone are not approval to attach loads.
3. Compute continuous usable walking width including railings, core door swing, slab-side transition and nearby column; code, egress and accessible routes must be separately reviewed.
4. Coordinate actual D-01 escalator landings (2F and 7F) with the proposed accessible-core plan. Do not disable escalators.
5. Provide new PROPOSED_ONLY 1:100/1:50 *dimensioned* details only after authoritative geometry/GLB support. Keep original 1F, protected PR30/PR31/PR32 and V4.2 candidate untouched.

**This document is a study record only, not architectural approval, an instruction to modify protected geometry, or confirmation of legal compliance.**
