# WP0 R3 independent full audit (2026-11-25 KST)

**Status: `AUDIT_COMPLETED_35_CHECKS / DESIGN_APPROVAL_HOLD / ORIGINALS_UNCHANGED`.** The previously approved **research direction** stands: (a) escalators must remain functional primary vertical transport; (b) 2F core D and 7F cores C/D should be designed as floor-accessible. Approval to alter verified geometry, structural walls, doors, slabs, escalators, book V4.2, or prior PRs has **not** been given.

## Verifiable audit counts

35 checks: **PASS 12, PASS_LIMITED 5, BLOCK 6, OPEN 8, WARN 4**. Local review artifacts in this ChatGPT session:
- A3 9-page PDF: `/mnt/data/WP0_R3_FULL_AUDIT_20261125/WP0_R3_INDEPENDENT_FULL_AUDIT_A3_KO_9P.pdf`; SHA-256 `e250a2a4636f91c4872e10c283557f2c467e4b935ad5377cdb3f0d7aec09c120` (as verified 2026-11-25 KST).
- Machine checklist CSV: `/mnt/data/WP0_R3_FULL_AUDIT_20261125/AUDIT_CHECKLIST_35.csv`; 35 rows.
- Evidence JSON: `/mnt/data/WP0_R3_FULL_AUDIT_20261125/AUDIT_EVIDENCE.json`.
These local artifacts have **not** been uploaded to GitHub and must not be described as repo files.

## P0 findings reproduced from PR #30 actual source slice segments

| Floor, core | North wall at model Y=-12 | Wall line source segments | Core-entry status |
|---|---|---|---|
| 2F D | full approx 5.998m north wall | X -8.999..-4.291 and -4.291..-3.001 | NO CONFIRMED OPENING |
| 7F D | full approx 5.998m north wall | X -8.999..-6.035 and -6.035..-3.001 | NO CONFIRMED OPENING |
| 7F C | full approx 5.998m north wall | X 39.001..41.965 and 41.965..44.999 | NO CONFIRMED OPENING |

Original source PR30 `1164fc0f58d943598d8e48146a02fcb3214c852e`: floor FFL 2F +6.0004m and 7F +31.001m. PR32 `f364a642675b08788750ca9646dd7dddbdb02c64`: all 3 cores have 0m2 walkable slab and 17.0m to source slab. A 17m bridge reaching the slab at model Y=+5 **does not by itself open the north core wall**, guarantee safe slab connection, or create a valid exit.

P0 structural/traffic blockers: (1) no approved core wall penetration/fire door/stair interface; (2) 17m bridge support & bearing unresolved; (3) bridge-to-existing slab attachment only boundary contact; (4) railing/door clear-width NOT_MEASURED; (5) fire/egress/accessibility NOT_CHECKED; (6) no actual original 3D cuts, underbridge headroom and supporting details. No core is currently verified accessible by R3.

## Geometry recheck: correct but limited

- Proposed S1 gross bridge area 40.8m2/core, 122.4m2/3. S2 51.0m2/core, 153m2/3. S3 43.92m2/core, 131.76m2/3. Calculations reproduce.
- Source column BBox nearest-edge geometric gaps recalculated (approx): S1 0.749..0.752m, S2 0.449..0.452m, S3 0.149..0.152m. No proposed footprint overlaps sampled original column BBoxes. These gaps do **not** prove effective corridor width, egress/accessible passage, load path or constructability.
- R3 plan outlines are simplifications, not verified CAD: 2F source gross footprint ~2219.4m2 vs simplified trace 2222.17m2; 7F source ~1563.2m2 vs trace 1565.05m2. Source geometry/hash guard preserved in repo; original GLB versus slice not independently proved.
- R3 `WP0_R3_GEOMETRY_SCREENING.json` top-level `source_sha256` values `094c1e...` and `1dc7ba...` are **derived local trace hashes**, not pinned source-slice hashes. Pinned slice SHA values: 2F `a80696fe8ff486103cc1192641dbe68eed2d7b7ddcb4458d53ebc8bbe50c523e`, 7F `db8d579e5916509f9fc0f798a8054bf7e5f6ffa0e5163059ff020291288efbeb`. Preserve distinction.

## Audit of actual original R3 delivered files

- Original R3 local ZIP: `WP0_R3_2F_7F_17M_BRIDGE_RESEARCH_SOURCE_AND_PDF.zip` SHA256 `e0793244ebece67c034e0a39068889837c27f96c2be002e7f3749a667a341134`. ZIP CRC passes, internal manifest **11/11** SHA+length entries pass; editable SVG XML **8/8** valid.
- Original R3 standalone 10-page A3 PDF: `WP0_R3_2F_7F_CORE_BRIDGE_17M_ALTERNATIVES_A3_10P.pdf` observed SHA256 **`38e624a11871572401285a6998ff6c73006ae3edad9caa48e38b6e986856229f`**, 324518 bytes.
- The ZIP *internally embedded* 10-page PDF differs in bytes: SHA256 **`9999ca8bdb73540dc40409c77ffde31ef45ae7ef0bd0b14321d0bf62d8c304b3`**, 299565 bytes. It matches the internal manifest, **but not the separately distributed standalone PDF**. This corrects the earlier research MD and AI_Execution_Log that incorrectly associated `9999...` with the standalone PDF. 10/10 pages have matching extracted text and identical pixel rendering at 1.5x; this is a **version/byte-level documentation error, not a demonstrated visual change**. Do not overwrite files retroactively; issue a fixed canonical new version with verified hashes.
- 10/10 A3 PDF pages contain text and no out-of-page text. Korean fonts are embedded in PDF; SVG references non-embedded NanumGothic.

## Issue register and original safety

- Original audit 47 unique IDs: 15 common + 32 floor-specific; 25 P0, 19 P1, 3 P2. All 47 remain `OPEN_REQUIRES_REVIEW` in the prior **preliminary** crosswalk, not all physically re-inspected in this R3 audit. Core relevant: `X-02`, `2F-01`, `7F-01`, producer reviewer `R-02`.
- **D-01: 25 escalator landing connections remain unresolved.** R3 core bridge does not complete operational escalator connectivity. D-03 15 turning proposals and D-08 T1 ramps also remain open; WP1 independently COMPLETE floors = 0. WP3 full 32 sheet visual review and WP4 65-page V4.2 integration not done.
- PR30 PR31 PR32 were rechecked open Draft/unmerged at their pinned HEADs, respectively `1164fc0...`, `64f8114...`, `f364a64...`. Study branch versus PR32 prior to this note: 27 ahead commits, 25 changed files, **zero protected-path changes**; changed paths only under `studies/t14t_wp0_r1/` and `docs/t14t_audit_r1/independent_audit_47/`. No source or existing book changes were made by this review.

## Recommended correction order and approval gate

1. Read actual GLB sections and stair/core fire walls. Study **real** north-wall openings with exact doorway geometry and core stair connection, without modifying the source.
2. Compare at least two realistic support solutions for 17m link, verify actual upper/lower levels, slab bearing and headroom with a structural engineer.
3. Recompute continuous accessible clear width including railings, door clear swings, columns and model-verified slabs; separately assess fire/egress/accessibility.
4. Integrate each affected 2F/7F D-01 escalator landing with proposed core access and overall floor graph.
5. Only after dimensioned plans + actual sections + technical evidence exist, ask the user to approve **specific** structural wall/slab changes; do not interpret the selected research direction as approval.
6. Fix standalone vs ZIP SHA provenance and keep a single canonical new report build; do not silently rewrite previously delivered artifacts.

No code compliance, final architecture approval, publication, or model modification is authorized by this audit.
