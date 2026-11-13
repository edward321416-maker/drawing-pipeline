"""C-T14I graduation drawing book / technical appendix tooling.

`import t14i` first in every C-T14I script: it fixes the edition env defaults (read by tools/t14g/config.py), puts tools/ and src/ on
sys.path and switches on the minimum-text-size policy of tools/t14d_sheet.py.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(_HERE)
ROOT = os.path.dirname(TOOLS)
for _p in (os.path.join(ROOT, "src"), TOOLS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("T14_EDITION", "V4")
os.environ.setdefault("T14_PROJECT", "C-T14I")
os.environ.setdefault("T14_REVISION", "R4")
os.environ.setdefault("T14_ISSUE_DATE", "2026-11-13")

import t14d_sheet as _sheet  # noqa: E402
from t14i import config as _config  # noqa: E402

_config.apply(_sheet)
