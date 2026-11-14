# C-T14M — AI retouch execution and accuracy gate

## Outcome

Actual ChatGPT image edits were downloaded for G-002, G-103, G-106, and G-111. They were not used as architectural spatial authority. The pipeline extracts only a low-frequency tone field, applies it to the verified source, restores every protected structure-edge pixel from the source, and re-composites the authoritative vector layer for technical pages.

All four pilots remain `REJECTED_NOT_FOR_BOOK` because an independent architectural reviewer has not completed the required checklist. Candidate V4.3 was therefore **not generated**. The primary deliverable is an execution/blocker report, not a finished drawing book.

## Deliverables

- Korean execution report: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14L\docs\t14m_v43\C_T14M_AI_Retouch_Execution_Report.pdf`
- Contact sheet: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14L\docs\t14m_v43\C_T14M_AI_Retouch_Execution_Report_Contact_Sheet.png`
- Four source/retouch packets: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14L\docs\t14m_v43\retouch`
- 65-page inventory: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14L\docs\t14m_v43\asset_inventory.json`
- PDF QA: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14L\docs\t14m_v43\qa\report_pdf_qa.json`
- Tests: `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14L\docs\t14m_v43\tests_report.json`

## Verified facts

- G-002 source hash: `9acd9ab3f5848f51ac1f2cc678ae988bf4f17197f238a5905eac9d8460e75a75`.
- G-002 source is 2400×1350 and approximately 154 dpi at the V4.2 396 mm placement.
- A same-camera full-tower Blender source was not found, so native 4700 px rerendering is blocked.
- Protected-pixel changes are zero for all four pilot candidates.
- G-106 and G-111 preserve the original SVG/PDF and use a final vector recomposite.
- The report is 8 A3-landscape pages, embeds Malgun Gothic, has a 7.4 pt minimum searchable text size, and has no out-of-bounds text.
- Retouch-scoped tests: 14/14 pass. Full suite: 323 pass, 18 skip, 10 environment-blocked because `output\C_T14I_run` is absent from the isolated worktree.

## Required next decision

An independent reviewer must compare the source, candidate, and high-resolution crops for the four pilot assets. A passing automated similarity or lock test is not sufficient. Only after the checklists are completed may the manifest status move to `APPROVED_FOR_LAYOUT_NOT_DESIGN_APPROVED`; 300 dpi page inspection is still required for print status.
