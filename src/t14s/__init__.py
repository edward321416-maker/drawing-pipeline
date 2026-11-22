"""C-T14S: 16-floor architectural floor-plan candidates (B2, B1, 2F-15F).

Verified geometry comes only from the hash-pinned slice copy in data/t14s/source_slices.
Everything drawn on top of it (partitions, doors, core interiors, rooms, furniture) is PROPOSED_DESIGN.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "src", ROOT / "engine"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
