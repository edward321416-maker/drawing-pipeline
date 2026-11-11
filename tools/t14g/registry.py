"""Single detail-sheet registry (sheet number -> scale).

Every place that prints a detail number with a scale reads it from here: the detail generator
(spec scale), plan and elevation callout symbols, the sheet-index text, A-002 and A-900. Nothing
types "D-407 . 1:50" by hand any more (audit finding F-01).

  * detail_scale("D-410")        -> 100
  * callout_label("D-410")       -> "D-410 . 1:100"
  * detail_scale("D-499")        -> raises UnknownSheetError (a callout to a sheet that does not exist)
  * verify_against_registry(...) -> compares the detail registry the generator actually wrote
                                    with this table; any difference is a build failure.
"""
import json
import os

# scale denominator of each detail sheet. The generator reads it, the callouts read it.
DETAIL_SCALE = {
    "D-401": 50, "D-402": 50, "D-403": 50, "D-404": 50, "D-405": 50, "D-406": 50,
    "D-407": 100, "D-408": 100, "D-409": 50, "D-410": 100,
}
# graphic scale bar ticks (m): 5 m = 100 mm at 1:50, 10 m = 100 mm at 1:100, 20 m = 100/80/50 mm at 1:200/1:250/1:400 (as in V2)
SUPPORTED_BAR = {50: (0, 1, 2, 5), 100: (0, 2, 5, 10), 200: (0, 5, 10, 20), 250: (0, 5, 10, 20), 400: (0, 5, 10, 20), 1000: (0, 10, 20, 50)}


class UnknownSheetError(KeyError):
    pass


class ScaleMismatchError(ValueError):
    pass


def detail_scale(sid):
    try:
        return DETAIL_SCALE[sid]
    except KeyError:
        raise UnknownSheetError("callout refers to detail sheet %r which is not in the registry" % sid) from None


def callout_label(sid, scale=None):
    """'D-410 · 1:100'. If a caller passes its own scale it must equal the registry scale."""
    reg = detail_scale(sid)
    if scale is not None and int(scale) != reg:
        raise ScaleMismatchError("callout %s printed with 1:%s but the sheet is 1:%d" % (sid, scale, reg))
    return "%s · 1:%d" % (sid, reg)


def bar_meters(den):
    """Tick distances (m) for a graphic scale bar that is 100 mm of paper at 1:50/1:100 and 80-125 mm otherwise."""
    return SUPPORTED_BAR[den]


def verify_against_registry(detail_registry_path):
    """Return a list of problems (empty = ok) between the generated detail_registry.json and DETAIL_SCALE."""
    problems = []
    reg = json.load(open(detail_registry_path, encoding="utf-8"))["details"]
    seen = {}
    for d in reg:
        seen[d["sheet"]] = d["scale"]
    for sid, den in DETAIL_SCALE.items():
        if sid not in seen:
            problems.append("%s missing in generated detail registry" % sid)
        elif seen[sid] != "1:%d" % den:
            problems.append("%s generated at %s but registry says 1:%d" % (sid, seen[sid], den))
    for sid in seen:
        if sid not in DETAIL_SCALE:
            problems.append("%s generated but not in registry" % sid)
    return problems


def load_json(path):
    return json.load(open(os.fspath(path), encoding="utf-8"))
