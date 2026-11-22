"""C-T14S entry point: build the 16 missing floor plans (B2, B1, 2F-15F).

    python -I tools/t14s/build_all.py                      # all 16 floors -> outputs/T14S/<floor>/
    python -I tools/t14s/build_all.py --floors 3F 8F       # subset
    python -I tools/t14s/build_all.py --sync               # first run: copy + hash-pin the verified slices
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

if __name__ == "__main__":
    if "--sync" in sys.argv:
        sys.argv.remove("--sync")
        from t14s import source
        m = source.sync_sources()
        print("synced %d source files into %s" % (len(m["files"]), os.path.abspath(source.SRC_DIR)))
    from t14s import build
    build.main()
