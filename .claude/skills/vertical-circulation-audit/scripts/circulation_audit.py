"""vertical-circulation-audit: what is connected and assessed, and what is not (stdlib only).

    circulation_audit.py [--root .] [--meta-glob 'outputs/T14T/*/*_plan_metadata.json'] [--floors 2F 7F]
                         [--technical-report docs/t14t_corrections/build_test_report.json] [--require-complete] [--json out.json]

Reads the per-floor metadata written by the C-T14T builder. For every floor it separates
  connected            graph nodes on verified slab (assessed visitor circulation)
  provisional/excluded escalator ends at an opening, blocked, cores without slab, missing required nodes, unreachable unit doors, disconnected graph
  passenger_transport_not_assessed   lifts and ramps (by their source label) that have no graph node
  service_only         freight lifts and services shafts (by their source label); listed, not required
  not_assessed         items the model cannot assess (T1 ramp access, D-08)
  proposed_decisions   proposed design decisions awaiting approval (D-03 lift-entry rotations, ...)
Classes come from references/element_classes.json (source labels) and references/decision_ids.json; nothing is inferred.
Verdicts: COMPLETE (nothing open), CONNECTED_WITH_OPEN_ITEMS (assessed nodes connected, but passenger transport / not-assessed /
proposed items remain), INCOMPLETE (a connection failed or a required node is excluded). A technical PASS is none of these.
Exit status: 0 = report written (and every floor COMPLETE when --require-complete), 1 = not complete under --require-complete, 2 = input error.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

REFS = Path(__file__).resolve().parent.parent / "references"
PLACED = ("ON_SLAB", "AT_OPENING_EDGE")
ESC_ID = re.compile(r"^esc\s+(\w+?)\W+(\w+)\s+(board|arrive|through)$")
DISCLAIMER = "Technical PASS is not circulation proof. No egress, fire, accessibility or architectural approval is assessed here."
LEGEND = ("COMPLETE = nothing open. CONNECTED_WITH_OPEN_ITEMS = assessed nodes connected, but passenger transport / not-assessed / proposed items remain. "
          "Service-only shafts (freight lift, services shafts) are listed, not required.")


def destination_problem(root: Path, path: str) -> str | None:
    """Same protected-path rule as every other write in these skills (drawing-source-guard owns the list). Fail closed if it is missing."""
    p = Path(__file__).resolve().parents[2] / "drawing-source-guard" / "scripts" / "guard_check.py"
    if not p.exists():
        return "drawing-source-guard skill not found: refusing to write"
    spec = importlib.util.spec_from_file_location("guard_check_for_audit", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.destination_problem(root, path)


def load_refs() -> tuple[list, dict]:
    rules = json.loads((REFS / "element_classes.json").read_text(encoding="utf-8"))["rules"]
    decisions = json.loads((REFS / "decision_ids.json").read_text(encoding="utf-8"))["ids"]
    return rules, decisions


def classify(name: str | None, rules: list) -> dict | None:
    """First rule whose label text occurs in the source name; None if there is no name or no rule."""
    if not name:
        return None
    return next((r for r in rules if r["match"] in name), None)


def _components(nodes: dict, edges: list) -> int:
    parent = {k: k for k in nodes if nodes[k].get("status") in PLACED}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for e in edges:
        if e["a"] in parent and e["b"] in parent:
            parent[find(e["a"])] = find(e["b"])
    return len({find(k) for k in parent})


def _decision_detail(did: str, items: list) -> str:
    turns = ["%s %+d°" % (i["tube"], round(i["turn_deg"])) for i in items if "tube" in i and "turn_deg" in i]
    return ", ".join(turns) if turns else "%d item(s)" % len(items)


def audit_floor(meta: dict) -> dict:
    rules, decision_ids = load_refs()
    dp, gv = meta["design_proposed"], meta["geometry_verified"]
    G, refs = dp["circulation_graph"], dp.get("decision_refs", {})
    nodes = {n["id"]: n for n in G["nodes"]}
    connected = sorted(k for k, n in nodes.items() if n["status"] == "ON_SLAB")
    provisional, excluded, undecided = [], [], []

    def item(i, kind, decision=None, reason=""):
        d = {"id": i, "kind": kind, "decision": decision, "reason": reason}
        if not decision:
            undecided.append(i)
        return d

    for u in G.get("unresolved", []):
        d = item(u["id"], u["status"], u.get("decision"), u.get("reason", ""))
        (provisional if u["status"] == "AT_OPENING_EDGE" else excluded).append(d)
    listed = {x["id"] for x in provisional + excluded}
    for k, n in nodes.items():                                   # graph nodes that are neither connected nor listed as unresolved
        if n["status"] not in PLACED and k not in listed:
            excluded.append(item(k, n["status"], n.get("decision"), "node not placed on verified slab"))
        elif n["status"] == "AT_OPENING_EDGE" and k not in listed:
            provisional.append(item(k, "AT_OPENING_EDGE", n.get("decision"), "route stops at the verified slab edge"))
    # required nodes that the graph silently left out
    no_slab = {c.get("core"): c for c in refs.get("D-02", [])}
    for core in gv.get("cores", []):
        if "core " + core in nodes:
            continue
        if core in no_slab:
            excluded.append(item("core " + core, "CORE_WITHOUT_SLAB", "D-02", "verified core footprint has no floor slab on this level"))
        else:
            excluded.append(item("core " + core, "REQUIRED_NODE_MISSING_FROM_GRAPH"))
    lobby_missing = set()
    for t in ("T3", "T4"):                                       # panoramic lift tubes: the lobby is a required node where the tube exists
        if t in gv.get("tubes", []) and "tube " + t not in nodes:
            excluded.append(item("tube " + t, "REQUIRED_NODE_MISSING_FROM_GRAPH"))
            lobby_missing.add(t)
    have = {m.groups() for k in nodes for m in [ESC_ID.match(k)] if m}
    for ax in gv.get("escalator_axes", []):
        if ax.get("role_here") in ("board", "arrive") and (ax["from"], ax["to"], ax["role_here"]) not in have:
            excluded.append(item("esc %s-%s %s" % (ax["from"], ax["to"], ax["role_here"]), "REQUIRED_NODE_MISSING_FROM_GRAPH"))
    for u in G.get("unit_doors", []):
        if not u.get("reachable"):
            excluded.append(item("unit door %s" % u.get("room"), "UNIT_DOOR_UNREACHABLE"))
    not_assessed = [{"id": x["id"], "reason": x.get("reason", ""), "decision": x.get("decision")} for x in G.get("not_modeled", [])]
    # verified tubes, shafts and lifts, classified by their source label
    names = {v["id"]: v.get("name") for v in dp.get("vertical_elements", [])}
    for e in list(gv.get("tubes", [])) + [x if isinstance(x, str) else x.get("name", "") for x in gv.get("shafts", [])]:
        if e:
            names.setdefault(e, None)
    routed = {k.split(" ", 1)[1] for k in nodes if k.startswith("tube ")}
    passenger, service, non_transport, unclassified = [], [], [], []
    for eid in sorted(names):
        if eid in routed or eid in lobby_missing or eid in ("capW", "capE") or eid.startswith("ESC "):
            continue
        rule = classify(names[eid], rules)
        rec = {"id": eid, "name": names[eid]}
        if rule is None:
            unclassified.append(rec)
        elif rule["class"] == "SERVICE_ONLY":
            service.append({**rec, "kind": rule["kind"]})
        elif rule["class"] == "NON_TRANSPORT":
            non_transport.append({**rec, "kind": rule["kind"]})
        elif rule["class"] == "PASSENGER_TRANSPORT":
            if rule["kind"] == "RAMP" and any(eid in x["id"] for x in not_assessed):
                continue                                           # reported once, as not_assessed (T1 ramp, D-08)
            passenger.append({**rec, "kind": rule["kind"], "note": rule.get("note", "")})
    proposed = []
    for did in sorted(refs):
        info = decision_ids.get(did)
        if info is None or info["category"] == "PROPOSED_DESIGN_AWAITING_APPROVAL":
            proposed.append({"id": did, "status": info["category"] if info else "UNCLASSIFIED_DECISION",
                             "meaning": info["meaning"] if info else "id not in references/decision_ids.json", "detail": _decision_detail(did, refs[did])})
    comps = _components(nodes, G.get("edges", []))
    if comps > 1:
        excluded.append(item("route graph", "GRAPH_DISCONNECTED", None, "%d separate components" % comps))
    kinds = []
    for cond, label in ((provisional, "PROVISIONAL_CONNECTION"), (excluded, "EXCLUDED_NODE"), (passenger, "PASSENGER_TRANSPORT_NOT_ASSESSED"),
                        (unclassified, "UNCLASSIFIED_ELEMENT"), (not_assessed, "NOT_ASSESSED"),
                        ([p for p in proposed if p["status"] == "PROPOSED_DESIGN_AWAITING_APPROVAL"], "PROPOSED_DESIGN_AWAITING_APPROVAL"),
                        ([p for p in proposed if p["status"] == "UNCLASSIFIED_DECISION"], "UNCLASSIFIED_DECISION")):
        if cond:
            kinds.append(label)
    verdict = "INCOMPLETE" if (provisional or excluded) else "CONNECTED_WITH_OPEN_ITEMS" if kinds else "COMPLETE"
    return {"floor": meta["floor"], "verdict": verdict, "open_item_kinds": kinds, "connected": connected, "provisional": provisional, "excluded": excluded,
            "passenger_transport_not_assessed": passenger, "service_only": service, "non_transport": non_transport, "unclassified_elements": unclassified,
            "not_assessed": not_assessed, "proposed_decisions": proposed, "components": comps, "undecided_items": undecided, "decision_refs": sorted(refs)}


def cross_check(rows: list, report: dict) -> list[str]:
    notes = []
    by = {f["floor"]: f for f in report.get("floors", [])}
    for r in rows:
        t = by.get(r["floor"])
        if not t:
            continue
        if t.get("pass") and r["verdict"] != "COMPLETE":
            notes.append("%s: TECHNICAL_PASS_NOT_CIRCULATION_PROOF (technical pass, circulation %s)" % (r["floor"], r["verdict"]))
        if t.get("circulation_complete") and r["verdict"] != "COMPLETE":
            notes.append("%s: VALIDATOR_FLAG_OVERSTATES (circulation_complete=true but audit=%s: %s)" % (r["floor"], r["verdict"], ", ".join(r["open_item_kinds"])))
    return notes


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")           # a cp949 console must not crash on arrows or check marks
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--meta-glob", default="outputs/T14T/*/*_plan_metadata.json")
    ap.add_argument("--floors", nargs="*")
    ap.add_argument("--technical-report")
    ap.add_argument("--require-complete", action="store_true", help="exit 1 unless every floor is COMPLETE (there is no switch that relaxes this)")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    if a.json and (why := destination_problem(root, a.json)):
        print("ERROR: --json destination refused: %s" % why)
        return 2
    try:
        files = sorted(root.glob(a.meta_glob))
        if not files:
            raise FileNotFoundError("no metadata matches %s under %s" % (a.meta_glob, root))
        rows = [audit_floor(json.loads(p.read_text(encoding="utf-8"))) for p in files]
        if a.floors:
            rows = [r for r in rows if r["floor"] in a.floors]
        notes = cross_check(rows, json.loads(Path(a.technical_report).read_text(encoding="utf-8"))) if a.technical_report else []
    except (OSError, KeyError, json.JSONDecodeError) as e:
        print("ERROR: %r" % e)
        return 2
    for r in rows:
        print("%-4s %-26s connected=%d provisional=%d excluded=%d passenger_transport_not_assessed=%d service_only=%d not_assessed=%d proposed_decisions=%d%s" % (
            r["floor"], r["verdict"], len(r["connected"]), len(r["provisional"]), len(r["excluded"]), len(r["passenger_transport_not_assessed"]),
            len(r["service_only"]), len(r["not_assessed"]), len(r["proposed_decisions"]),
            "  UNCLASSIFIED=%s" % [x["id"] for x in r["unclassified_elements"]] if r["unclassified_elements"] else ""))
        for x in r["excluded"]:
            print("       excluded     %-30s %-28s %s" % (x["id"], x["kind"], x["decision"] or "NO_DECISION_ID"))
        for x in r["passenger_transport_not_assessed"]:
            print("       not assessed %-30s %s" % (x["id"], x["kind"]))
    tally = {k: sum(1 for r in rows if r["verdict"] == k) for k in ("COMPLETE", "CONNECTED_WITH_OPEN_ITEMS", "INCOMPLETE")}
    print("floors=%d %s | provisional nodes=%d excluded nodes=%d passenger transport not assessed=%d" % (
        len(rows), " ".join("%s=%d" % kv for kv in tally.items()), sum(len(r["provisional"]) for r in rows), sum(len(r["excluded"]) for r in rows),
        sum(len(r["passenger_transport_not_assessed"]) for r in rows)))
    for n in notes:
        print("NOTE", n)
    print(LEGEND)
    print(DISCLAIMER)
    if a.json:
        (root / a.json).parent.mkdir(parents=True, exist_ok=True)
        (root / a.json).write_text(json.dumps({"schema": "C-T14-CIRCULATION-AUDIT-2.0", "floors": rows, "cross_check_notes": notes, "legend": LEGEND, "disclaimer": DISCLAIMER}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if a.require_complete and any(r["verdict"] != "COMPLETE" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
