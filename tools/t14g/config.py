"""Edition, project code and issue date for the title block. One place; nothing is typed into sheet text.

Override with environment variables when rebuilding an older edition:
    T14_EDITION=V3  T14_PROJECT=C-T14G  T14_REVISION="R3"  T14_ISSUE_DATE=2026-11-11
"""
import datetime
import os

EDITION = os.environ.get("T14_EDITION", "V3")
PROJECT_CODE = os.environ.get("T14_PROJECT", "C-T14G")
REVISION = os.environ.get("T14_REVISION", "R3")
ISSUE_DATE = os.environ.get("T14_ISSUE_DATE", datetime.date.today().isoformat())
PAPER_A3 = (420.0, 297.0)
PAPER_A1 = (841.0, 594.0)


def apply(sheet_module):
    """Push the config into tools/t14d_sheet.py (module level settings used by Sheet.title_block)."""
    sheet_module.EDITION = EDITION
    sheet_module.PROJECT_CODE = PROJECT_CODE
    sheet_module.REVISION = REVISION
    sheet_module.ISSUE_DATE = ISSUE_DATE
