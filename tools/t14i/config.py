"""Edition, text-size policy and status taxonomy for C-T14I (one place; nothing typed into sheet text)."""
import os

EDITION = os.environ.get("T14_EDITION", "V4")
PROJECT_CODE = os.environ.get("T14_PROJECT", "C-T14I")
REVISION = os.environ.get("T14_REVISION", "R4")
ISSUE_DATE = os.environ.get("T14_ISSUE_DATE", "2026-11-13")

# Internal quality targets (A3 print). They are our own targets, NOT statutory minimums.
MIN_PT = 6.0            # nothing smaller than this is drawn (symbols, bubbles, micro annotation)
MAIN_PT = 7.0           # main annotations (room names, key dimensions, notes) aim for >= 7 pt

PAPER_A3 = (420.0, 297.0)
PAPER_A1 = (841.0, 594.0)

# Truth classes used on EVERY drawing element that is not obviously a model cut.
MODEL_VERIFIED = "MODEL VERIFIED"          # derived from the model cache (mesh/slice/master); measured by code
CONCEPT_PROPOSED = "CONCEPT PROPOSED"      # our proposal; no model/decision behind it; never a construction fact
UNRESOLVED = "UNRESOLVED"                  # no source and no decision; deliberately not drawn
CLASS_COLOR = {MODEL_VERIFIED: "#0a6b3d", CONCEPT_PROPOSED: "#b5600a", UNRESOLVED: "#a32020"}

# Part / sheet-number conventions
PART_I = "PART I  Graduation Design Book"
PART_II = "PART II  Technical Drawing Appendix"
OUT_BOOK_I = "Graduation_Drawing_Book_Candidate_V4.pdf"
OUT_BOOK_II = "Technical_Drawing_Appendix_Candidate_V4.pdf"
OUT_CONTACT_I = "Graduation_Drawing_Book_Contact_Sheet.png"
OUT_CONTACT_II = "Technical_Appendix_Contact_Sheet.png"


def apply(sheet_module):
    sheet_module.EDITION = EDITION
    sheet_module.PROJECT_CODE = PROJECT_CODE
    sheet_module.REVISION = REVISION
    sheet_module.ISSUE_DATE = ISSUE_DATE
    sheet_module.MIN_PT = MIN_PT
