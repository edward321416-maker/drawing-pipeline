"""C-T14D 2단계: 기준층 평면(A3 1:200) 제작·검사 드라이버.

기준층 목록의 각 층에 대해
  1) 감사 증거(floor_equivalence_evidence.json, floor_coverage_audit.json)에서 시트 표기 문구를 생성한다(손으로 쓰지 않는다),
  2) 렌더러를 실행하고, 3) 독립 QA(t14_floor_qa.py --no-tiles)를 실행하고, 4) plan_registry.json에 기록한다.

    python -I tools/t14d_make_plans.py --run <도면집 후보 폴더> --glb <전층.glb> --floors 3F,8F,13F
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
import pipeline_common as pc  # noqa: E402


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def wrap(t, w=38):
    return textwrap.wrap(t, width=w, break_long_words=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--glb", required=True)
    ap.add_argument("--floors", required=True)
    ap.add_argument("--first-sheet-no", type=int, default=101)
    a = ap.parse_args()
    run = os.path.abspath(a.run)
    ev = pc.load_json(os.path.join(run, "00_index", "floor_equivalence_evidence.json"))
    cov = pc.load_json(os.path.join(run, "00_index", "floor_coverage_audit.json"))
    bb = pc.load_json(os.path.join(run, "raw_slices", "camera_bounds.json"))["building"]
    rel = lambda p: (round(p[0] - bb["xmin"], 1), round(p[1] - bb["ymin"], 1))
    floors = [f.strip() for f in a.floors.split(",") if f.strip()]
    plans = []
    for i, f in enumerate(floors):
        grp = next(g for g in cov["plan_sheet_groups"] if f in g["members"])
        sid = "P-%d" % (a.first_sheet_no + i)
        members = grp["members"]
        notes = []
        if grp["kind"] == "INDEPENDENT":
            notes.append("%s · 적용 층: %s (단독)" % (sid, f))
            nonequal = sorted({(p["pair"].replace("~", " ").replace(f, "").strip()) for h in ev["hypothesis_groups"] for p in h["pairs"] if f in p["pair"].split("~") and p["relation"] == "DIFFERENT"})
            if nonequal:
                notes += wrap("%s와 동등하지 않음(검증): 프로그램·외피·슬래브 차이" % "·".join(nonequal))
            else:
                notes += wrap("다른 층과 동등 검증된 층 없음")
        else:
            notes.append("%s · 적용 층: %s" % (sid, "·".join(members)))
            notes += wrap("수직동선 개구만 다름(검증됨)") + wrap("※ EQUIVALENCE VERIFIED 표기 아님")
            other = [m for m in members if m != f]
            pair = next(p for h in ev["hypothesis_groups"] for p in h["pairs"] if set(p["pair"].split("~")) == set(members[:2]) and len(members) == 2) if len(members) == 2 else None
            if pair:
                ve = pair["vertical_elements"]
                for kind, label in (("stair", "에스컬레이터"), ("shaft", "승강기 샤프트")):
                    for ff in members:
                        pts = ve[kind][ff]
                        other_pts = ve[kind][other[0]] if ff == f else ve[kind][f]
                        only = [p for p in pts if all(abs(p[0] - q[0]) > 0.5 or abs(p[1] - q[1]) > 0.5 for q in other_pts)]
                        if only:
                            notes += wrap("%s %s 고유: %s" % (ff, label, " ".join("(%.1f,%.1f)" % rel(p) for p in only)))
        floor_notes = notes
        base = "plan_%s_A3_1to200" % f
        cmd = [sys.executable, "-I", os.path.join(ROOT, "src", "architectural_plan_renderer.py"), "--out", run, "--floor", f, "--scale", "200", "--png-width", "4961",
               "--cleanline", "--final-dir", os.path.join(run, "01_plans"), "--name", base]
        for n in floor_notes:
            cmd += ["--note", n]
        env = dict(os.environ, PYTHONUTF8="1")
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
        print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-400:])
        if r.returncode:
            raise SystemExit("렌더 실패 %s\n%s" % (f, r.stderr[-800:]))
        qa_report = os.path.join(run, "06_QA", "floor_%s_geometry_qa.json" % f)
        q = subprocess.run([sys.executable, "-I", os.path.join(HERE, "t14_floor_qa.py"), "--run", run, "--floor", f, "--glb", a.glb, "--sheet-dir", "01_plans", "--suffix", "",
                            "--no-tiles", "--ref-dir", os.path.join(run, "reference_1F"), "--report", qa_report], capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
        qa = pc.load_json(qa_report)
        plans.append({"sheet": sid, "floor": f, "applies_to": members, "kind": grp["kind"], "scale": "A3 1:200", "notes_on_sheet": floor_notes,
                      "level": "S_SCHEMATIC (상층 구획벽·문 미검증, 가구 PROPOSED_ONLY)", "status": "CANDIDATE — NOT FROZEN",
                      "files": {e: {"path": os.path.join(run, "01_plans", base + "." + e), "sha256": sha(os.path.join(run, "01_plans", base + "." + e))} for e in ("svg", "pdf", "png")},
                      "qa": {"pass": qa["pass"], "fail": qa["fail"], "total": qa["total"], "report": qa_report}})
        print("QA", f, "%d/%d" % (qa["pass"], qa["total"]), "FAIL" if qa["fail"] else "")
    json.dump({"book": "C_T14D", "plans": plans, "model_sha256": sha(a.glb)}, open(os.path.join(run, "01_plans", "plan_registry.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("REGISTRY", os.path.join(run, "01_plans", "plan_registry.json"))


if __name__ == "__main__":
    main()
