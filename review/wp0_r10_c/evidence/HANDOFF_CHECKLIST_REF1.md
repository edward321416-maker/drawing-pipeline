# R10-C REF1 — check against the independent reference handoff

Specification: `references/academic_drawing_books/CHATGPT_REFERENCE_HANDOFF.md` at commit `8d5e5d1e21caa2dda80d60d86e6534653d4bf90d` (branch `review/wp0-chatgpt-reference-handoff`).
Everything below is the executor's own measurement or record unless it says otherwise; **nothing here is an independent verification and no submission readiness is claimed.**
No design revision was made for this check.

## 1. Reference identities and frame coordinates (direct re-measurement of the local files)
| ref | pages | SHA-256 equals handoff | measured at | max deviation from handoff frame / divider / title-band values |
|---|---:|---|---|---:|
| A | 21 (handoff 21) | yes | p6 | 0.05 mm |
| B | 18 (handoff 18) | yes | p15 | 0.04 mm |
| C | 15 (handoff 15) | NO (local 28c4e37b4fc0… vs handoff 574607af0b73…) | p6 | 0.05 mm |
| D | 6 (handoff 6) | yes | p3 | 0.05 mm |

- Reference C (2024 architecture): the local copy's hash differs, as the handoff expected. Page count 15, A2 landscape except portrait pp11-13 and the frame geometry all agree with the handoff. Local copy metadata: producer `iLovePDF`, modDate `D:20240617062239Z`. Per-page text and 36-dpi render hashes of the local copy are in `evidence/handoff_crosscheck_references.json` (`C.fingerprint_of_local_copy.page_fingerprints`); compute the same on the other copy to localise any content difference. Not a visual mismatch finding.
- Title-band width: REF1 pages report it from the OUTER frame edge (A 46.8, B 33.1, C 41.1, D 29.0 mm); the handoff measures from the INNER frame edge (45.3 / 32.1 / 39.4 / 27.9 mm). Same geometry, different definition (difference = frame band).
- R10-C template (`evidence/handoff_crosscheck_references.json` → `r10c_template`): A2 inner-edge title band 45.22 mm vs reference A 45.3; A3 31.97 mm vs reference B 32.1.

## 2. Acceptance checklist
| item (handoff) | status | evidence / note |
|---|---|---|
| Preserve approved design and original 1F | PASS (executor tests) | preservation tests T01-T18 pass 18/18 against the R10-B1 commit; A-103 is built from the approved 1F master (HD-08); master-vs-slice area difference is disclosed (FRONT-02) |
| No speculative structural members, roof features, finishes, ceiling heights, legal compliance | PASS as designed; needs independent review | structural member list = MISSING_SOURCE; roof plan from GLB geometry only (HD-09); ceiling heights 미확인 in every room; legal/usable floor area = UNRESOLVED |
| A2 architectural and A3 structural books, appropriate portrait views | PARTIAL | A2 elevations A-401..404 are portrait; structural grid elevations S-301..S-305 are A3 LANDSCAPE whereas reference D p5 and B p17 are portrait: open finding |
| Do not shrink a 1:200 drawing and retain the same scale label | OPEN (disclosed) | R9/R10 A2 research pages S-401..S-407 are reduced 1:1.414 onto A3; the scale labels INSIDE those pages still show the original scale; the SCALE column and a stamped note give the reduction. Actual printed scale is stated x 1.414 (measured, see below) |
| Independently verify all actual drawing scales incl. reduced structural research sheets | DONE by executor (not independent) | `evidence/scale_verification_REF1.json`: 69 pages by scale bar, 7 reduced sheets (all print at stated x 1.414: 1:50 -> 1:70.7, 1:100 -> 1:141.4, 1:25 -> 1:35.4), 3 by grid labels / column markers / panel size (A-103 1:200, APX-01 1:300, APX-02 1:50); 0 mismatches; S-001 (non-scaled axon) not verifiable; 19 pages carry no scale |
| Coherent title block; resolve legacy R9 drawing IDs without altering source evidence; keep provenance | OPEN | 22 of 99 pages keep the R9 frame and R9 drawing numbers (e.g. A-521 prints D-2F); not resolved because that is a revision; provenance is kept in `page_map.csv` / source register |
| Separate geometry-only structural planning from engineering proposals | PARTIAL | structural sheets carry an evidence-class legend (verified geometry / research proposal / unverified); research pages S-401..S-408 are marked PARTIAL; no member sizes anywhere |
| Review actual content, not page count | n/a | 99 previews, 54 crops, page_map.csv per page |

## 3. Executor-reported issues in the handoff, with what was directly checked here
| reported issue | check |
|---|---|
| 99 pages (34 / 47 / 18) | confirmed by page counts of the published PDFs |
| 22 legacy R9 frames | confirmed: 22 pages contain the R9 title block text (`page_map.csv`, crop KD-12) |
| 6 producible omitted details A-511-516 | confirmed in `WP0_Missing_Drawings_Register_REF1.md`: source exists, sheets not produced |
| absent standalone A-002 / A-902 / A-903 | confirmed (no such pages) |
| 176.07 mm core D mismatch not printed | confirmed: no '176.07', 'HD-01' or mismatch text on A-501 (only 176.47 mm risers are printed); crop KD-01 |
| E2 structure evidence absent | executor record only (BLOCKED_STRUCTURAL_EVIDENCE); no structural evidence exists in the sources |
| routes 5 / 11 / 13 unresolved | confirmed from the HD-10 re-measurement: route 5 unchanged, routes 11/13 still cross existing furniture |
| all ceiling heights unverified | confirmed: CH column reads 미확인 for every room (crop KD-10) |
| Route 5 widths 1.03 m vs 1.26 m | **reconciled** (`evidence/route5_width_reconciliation.json`): same sample (d = 5.6 m, x = 40.604, y = 23.15) and the same two bounding obstacles; 1.257 m = clearance along the sampling axis (0.395 wall + 0.862 tube); 1.026 m = shortest diagonal gap between the obstacles. Use 1.03 m as the narrowest clear gap; both are below the 3.0 m trunk need; the furniture revision changes neither |

## 4. Package contract
Project-owned artifacts only; separate review branch; originals of the project PDFs, one JPEG per page, detail crops, `page_map.csv` (scale, scale verdict, status, source revision per sheet), source register, QA, manifest with SHA-256 and git blob SHA-1. Raw reference PDFs are **not** published: public redistribution rights are not verified and the user's authorisation of a public repository does not establish them. Local original R10-C and REF1 packages are preserved unchanged.
