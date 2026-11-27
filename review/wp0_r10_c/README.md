# WP0 R10-C reference-integrated review package (REF1)

Review branch `review/wp0-r10-c-reference-integrated` — not merged into `main`. Generated 2026-11-27. Not a submission-ready claim: nothing here is independently verified. The next stage is an independent full-book visual and technical review.
Specification used for checking: `references/academic_drawing_books/CHATGPT_REFERENCE_HANDOFF.md` (commit `8d5e5d1e21ca`).

| folder | content |
|---|---|
| `pdf/` | architectural A2 (34p), structural A3 (47p), technical appendix (18p), combined (99p) |
| `previews/ARCH|STRUCT|APPX/` | one 180 dpi JPEG per page, `<BOOK>_p<page-in-book>_<drawing-id>.jpg` (99 files) |
| `crops/<category>/` | 54 enlarged crops: title blocks, room tags, dimension chains, core details, section details, circulation bottlenecks, bridge connections, structural member schedules, known defects |
| `contact_sheets/` | 9 sheets, 12 pages each, with page numbers and drawing ids |
| `evidence/` | `page_map.csv|json`, drawing index, source register, missing-drawings register, QA report, `HANDOFF_CHECKLIST_REF1.md`, `scale_verification_REF1.json`, dimension QA, preservation tests, circulation re-measurement, `route5_width_reconciliation.json`, reference template specification and cross-check, execution log, redaction log, publication audit |
| `manifest.json` | SHA-256 and git blob SHA-1 of every file in this folder |
| `PUBLICATION_STATUS.md` | authorisation, repository identity, what was withheld and why |

Start with `evidence/WP0_Drawing_Book_QA_Report_REF1.md` and `evidence/HANDOFF_CHECKLIST_REF1.md`, then `contact_sheets/`, `previews/`, `crops/known_defects/`, and trace any page through `evidence/page_map.csv`.

Key open items: 22 of 99 pages keep the R9 frame and R9 drawing numbers; structural book is PARTIAL (no member sizes, beams, foundations); structural grid elevations are landscape; reduced research sheets keep their original scale labels (actual print scale = stated x 1.414); HD-01 core D landing (176.07 mm) and HD-02 E2 bridge evidence unresolved; HD-10 furniture candidate does not clear routes 11/13 and route 5 is a 1.03 m gap (1.26 m along the sampling axis); ceiling heights unverified; A-511..A-516 details not produced; cover render AI-retouched and unapproved; no physical print test.
Local paths in the text evidence are replaced by `<USER_HOME>` / `<TEMP>`; the unredacted originals stay local (`evidence/redaction_log.json` lists the changed files and hashes).
