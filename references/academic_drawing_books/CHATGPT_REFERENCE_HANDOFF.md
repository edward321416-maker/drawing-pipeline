# WP0 — Independent academic drawing-book reference handoff
Status: reference-only; not submission approval. 2026-11-27.
Source inspection: four user-supplied PDFs opened in ChatGPT; file bytes hashed, page dimensions read and representative vector frame coordinates measured. No third-party PDF or rendered image is included in this public branch. The local executor already has two Jangsan originals; the architectural hash differs from the ChatGPT copy. Do not treat the copies as byte-identical.

## Reference identities
| ID | Pages | SHA-256 (ChatGPT attachment) | Physical page layout |
|---|---:|---|---|
| A — 2023 architecture | 21 | 2dda59ba40a22300cb8240709d2847b84743cb15223e44b011b041c65df5c5a1 | A2 landscape except pp17–19 portrait |
| B — 2023 structure | 18 | edf6b736ca9a60743c025690913f7364cb00a2e5a9eb32f9cefbe641a59deb15 | A3 landscape pp1–16; portrait p17; p18 677.2×381.0 mm |
| C — 2024 architecture (copy) | 15 | 574607af0b730ce11f649eda54c7d736c50f10c21fd4f3854e652a900e80bb1e | A2 landscape except pp11–13 portrait |
| D — 2024 structure | 6 | c6d483919bb76a2661cb01a1ef9fb0f693b20d0836e445017ad593dbdabb1e58 | A3 landscape except p5 portrait |

Executor-reported C SHA-256: 28c4e37b4fc02de12ae9c24646bce88e567b26273722cdd6bd4577e922b57a9f (different; investigate metadata or page-content differences; not a visual mismatch finding). D matches exactly. Source PDFs remain local; public redistribution rights not verified.

## Measured template coordinates (mm)
Displayed page origin top-left. Bounding boxes are x0,y0,x1,y1. Values rounded to 0.1 mm. Measured from straight vector frame lines, not image estimates. Divider is the narrow double line; title-band width from its right line to inner right frame. Use the same coherent family rather than mixing the margins.
| Reference / page | Paper | Outer frame | Inner frame | Divider x | Title-band width |
|---|---|---|---|---|---:|
| A p6 | 594.1×420.2 | 12.8,9.9,581.2,410.5 | 14.3,11.3,579.7,409.1 | 533.7–534.4 | 45.3 |
| B p15 | 420.2×297.0 | 9.1,7.0,410.9,290.2 | 10.0,7.9,409.9,289.2 | 377.3–377.8 | 32.1 |
| C p6 | 594.1×420.2 | 20.4,13.3,573.8,406.9 | 22.1,14.9,572.1,405.2 | 531.9–532.7 | 39.4 |
| D p3 | 420.2×297.0 | 14.4,9.3,405.7,287.6 | 15.6,10.5,404.5,286.5 | 376.0–376.6 | 27.9 |

These are representative landscape measurements, not a claim that every page has identical geometry. A3/A2 title-band ratio approximately 0.707 within each family. Portrait arrangement must be measured separately from original pages.

## Page-level reference map
- A pp1–3: framed perspective cover, design overview/area schedule/location, site plan. pp4–16: floor and roof plans. pp17–18: elevations, p19: sections, p20: coordinated facade detail, p21: core.
- B pp1–14: overview, site and supporting architecture. pp15–16: structural plans, member marks/schedules, local sections. p17: grid elevation. p18: structural model.
- C pp1–3: cover, overview, site. pp4–10: basement, ground, selected upper and roof plans; room name/number/ceiling-height tags, dimension chains, FL/SL, OPEN, section markers. pp11–12: elevations; p13: sections; p14: exterior-wall details; p15: core.
- D pp1–2: cover and overview. pp3–4: structural plan, member schedules by category, slab-level legend. p5: structural grid elevation. p6: assembled/exploded model.

## R10-C independent-review acceptance checklist
Preserve approved design and original 1F; no speculative structural members, roof features, finishes, ceiling heights, or legal compliance. Do not infer verified values from reference buildings. A2 architectural and A3 structural books, appropriate portrait views. Do not shrink a 1:200 drawing and retain the same scale label. Independently verify all actual drawing scales including reduced structural research sheets. Apply coherent title block and resolve legacy R9 drawing IDs without altering source evidence; retain provenance. Separate geometry-only structural planning from engineering proposals. Review actual content, not page count.

Executor-reported REF1 issues (not independently verified): 99 pages (34 architecture, 47 structure, 18 appendix); 22 legacy R9 frames; 6 producible omitted details A-511–516; absent standalone A-002/A-902/A-903; 176.07 mm core D mismatch not printed; E2 structure evidence absent; routes 5/11/13 unresolved; all ceiling heights unverified. Resolve discrepancy between reported route 5 widths 1.03 m and 1.26 m by checking endpoints and methods. Preserve original local R10-C and REF1 packages. User authorization of public repository does not establish third-party redistribution rights.

## Review package contract
Publish project-owned review artifacts only after screening for credentials, personal information, third-party material, and sensitive paths. Use a separate review branch, not main. Include originals of project PDFs, one JPEG per page, detail crops, page_map.csv, source register, QA, manifest with hashes, scale and status per sheet. Record exact commit. Review each sheet against the four references and distinguish direct observations from executor reports. Raw reference PDFs are not delivered by this handoff; keep local unless redistribution is authorized and an actual binary-transfer method is available.
