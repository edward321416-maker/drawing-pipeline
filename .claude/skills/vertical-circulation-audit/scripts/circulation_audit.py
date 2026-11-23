"""vertical-circulation-audit: report which required nodes are connected, provisional, excluded or not assessed (stdlib only).

    circulation_audit.py [--root .] [--meta-glob 'outputs/T14T/*/*_plan_metadata.json'] [--floors 2F 7F]
                         [--technical-report docs/t14t_corrections/build_test_report.json]
                         [--require-complete] [--allow-not-assessed] [--json out.json]

Reads the per-floor metadata written by the C-T14T builder (design_proposed.circulation_graph, decision_refs,
geometry_verified.cores / escalator_axes). A floor is COMPLETE only when every required node (cores, T3/T4 lobbies, escalator board/arrive ends, unit doors) is connected on verified slab.
Verified tubes and shafts that the graph does not route are listed as unrouted_elements; they are reported, not required.
A technical PASS says nothing about circulation; this script never converts one into the other.
Exit status: 0 = report written (and complete when --require-complete), 1 = incomplete under --require-complete, 2 = input error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PLACED = ("ON_SLAB", "AT_OPENING_EDGE")
ESC_ID = re.compile(r"^esc\s+(\w+?)\W+(\w+)\s+(board|arrive|through)$")
DISCLAIMER = "Technical PASS is not circulation proof. No egress, fire, accessibility or architectural approval is assessed here."


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


def audit_floor(meta: dict) -> dict:
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
    for t in ("T3", "T4"):                                       # public lift tubes: the lobby is a required node where the tube exists
        if t in gv.get("tubes", []) and "tube " + t not in nodes:
            excluded.append(item("tube " + t, "REQUIRED_NODE_MISSING_FROM_GRAPH"))
    routed = {k.split(" ", 1)[1] for k in nodes if k.startswith("tube ")}
    shafts = [x if isinstance(x, str) else x.get("name", "") for x in gv.get("shafts", [])]
    unrouted = sorted(e for e in set(gv.get("tubes", [])) | set(shafts) if e and e not in routed and e not in ("capW", "capE"))
    have = {m.groups() for k in nodes for m in [ESC_ID.match(k)] if m}
    for ax in gv.get("escalator_axes", []):
        if ax.get("role_here") in ("board", "arrive") and (ax["from"], ax["to"], ax["role_here"]) not in have:
            excluded.append(item("esc %s-%s %s" % (ax["from"], ax["to"], ax["role_here"]), "REQUIRED_NODE_MISSING_FROM_GRAPH"))
    for u in G.get("unit_doors", []):
        if not u.get("reachable"):
            excluded.append(item("unit door %s" % u.get("room"), "UNIT_DOOR_UNREACHABLE"))
    not_assessed = [{"id": x["id"], "reason": x.get("reason", ""), "decision": x.get("decision")} for x in G.get("not_modeled", [])]
    comps = _components(nodes, G.get("edges", []))
    if comps > 1:
        excluded.append(item("route graph", "GRAPH_DISCONNECTED", None, "%d separate components" % comps))
    if provisional or excluded:
        verdict = "INCOMPLETE"
    elif not_assessed:
        verdict = "COMPLETE_EXCEPT_NOT_ASSESSED"
    else:
        verdict = "COMPLETE"
    return {"floor": meta["floor"], "verdict": verdict, "connected": connected, "provisional": provisional, "excluded": excluded,
            "not_assessed": not_assessed, "unrouted_elements": unrouted, "components": comps, "undecided_items": undecided, "decision_refs": sorted(refs)}


def cross_check(rows: list, report: dict) -> list[str]:
    notes = []
    by = {f["floor"]: f for f in report.get("floors", [])}
    for r in rows:
        t = by.get(r["floor"])
        if not t:
            continue
        if t.get("pass") and r["verdict"] != "COMPLETE":
            notes.append("%s: TECHNICAL_PASS_NOT_CIRCULATION_PROOF (technical pass, circulation %s)" % (r["floor"], r["verdict"]))
        if t.get("circulation_complete") and r["verdict"] == "INCOMPLETE":
            notes.append("%s: VALIDATOR_FLAG_OVERSTATES (circulation_complete=true but audit=INCOMPLETE: %s)" % (
                r["floor"], ", ".join(sorted({x["kind"] for x in r["excluded"] + r["provisional"]}))))
        elif t.get("circulation_complete") and r["verdict"] == "COMPLETE_EXCEPT_NOT_ASSESSED":
            notes.append("%s: VALIDATOR_FLAG_IGNORES_NOT_ASSESSED (circulation_complete=true; %d item(s) not assessed: %s)" % (
                r["floor"], len(r["not_assessed"]), ", ".join(x["id"] for x in r["not_assessed"])))
    return notes


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")           # a cp949 console must not crash on arrows or check marks
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--meta-glob", default="outputs/T14T/*/*_plan_metadata.json")
    ap.add_argument("--floors", nargs="*")
    ap.add_argument("--technical-report")
    ap.add_argument("--require-complete", action="store_true")
    ap.add_argument("--allow-not-assessed", action="store_true", help="count COMPLETE_EXCEPT_NOT_ASSESSED as complete under --require-complete")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
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
    order = {"COMPLETE": 0, "COMPLETE_EXCEPT_NOT_ASSESSED": 1, "INCOMPLETE": 2}
    for r in rows:
        print("%-4s %-30s connected=%d provisional=%d excluded=%d not_assessed=%d unrouted=%d%s" % (
            r["floor"], r["verdict"], len(r["connected"]), len(r["provisional"]), len(r["excluded"]), len(r["not_assessed"]), len(r["unrouted_elements"]),
            "  UNDECIDED=%s" % r["undecided_items"] if r["undecided_items"] else ""))
        for x in r["excluded"]:
            print("       excluded     %-30s %-28s %s" % (x["id"], x["kind"], x["decision"] or "NO_DECISION_ID"))
    tally = {k: sum(1 for r in rows if r["verdict"] == k) for k in order}
    print("floors=%d %s | provisional nodes=%d excluded nodes=%d not-assessed items=%d" % (
        len(rows), " ".join("%s=%d" % kv for kv in tally.items()), sum(len(r["provisional"]) for r in rows), sum(len(r["excluded"]) for r in rows), sum(len(r["not_assessed"]) for r in rows)))
    for n in notes:
        print("NOTE", n)
    print("COMPLETE means: cores, T3/T4 lobbies, escalator ends and unit doors are connected. Verified shafts and tubes under 'unrouted' (e.g. FR, M1, M2, EV1, EV2, PL, T1, T2) have no graph node and were not tested.")
    print(DISCLAIMER)
    if a.json:
        Path(a.json).write_text(json.dumps({"schema": "C-T14-CIRCULATION-AUDIT-1.0", "floors": rows, "cross_check_notes": notes, "disclaimer": DISCLAIMER}, ensure_ascii=False, indent=1), encoding="utf-8")
    limit = 1 if a.allow_not_assessed else 0
    return 1 if a.require_complete and any(order[r["verdict"]] > limit for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
