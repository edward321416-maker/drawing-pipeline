"""C-T14T decision packet: items that need a user decision because resolving them would change verified geometry
(or the approved 1F symbol). Built from the floor metadata; nothing here is approved.

    python -I tools/t14s/decision_packet.py   ->  docs/t14t_corrections/decision_packet.md / .json
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
from t14s import source as SRC  # noqa: E402

OUT = os.path.join(ROOT, "outputs", "T14T")
DOC = os.path.join(ROOT, "docs", "t14t_corrections")


def meta(f):
    return json.load(open(os.path.join(OUT, f, "T14T_%s_plan_metadata.json" % f), encoding="utf-8"))


def collect():
    dec = {}
    for f in SRC.TARGET_FLOORS:
        for k, v in meta(f)["design_proposed"]["decision_refs"].items():
            dec.setdefault(k, []).extend(v)
    return dec


def build():
    dec = collect()
    P = {}
    d1 = sorted(dec.get("D-01", []), key=lambda x: (SRC.FLOORS.index(x["floor"]), x["escalator"], x["role"]))
    P["D-01"] = {
        "title": "에스컬레이터 승·하차 랜딩이 검증된 바닥판 위에 없음 (캡슐 개구 안 / 코어 안)",
        "fact": "모델의 에스컬레이터 축(검증)은 캡슐 개구 안에서 끝나거나(%d건) 코어 외곽 안에서 시작한다. 그 지점에 닿는 검증된 슬래브가 없어 방문객 동선을 이을 수 없다. "
                "도면은 검증 슬래브 가장자리까지만 경로를 그리고(파란 점선·빈 마름모), 개구 위로는 잇지 않았다." % len(d1),
        "rows": d1,
        "alternatives": [
            "A. 캡슐 개구 안 턴어라운드 지점에 제안 랜딩 슬래브를 추가한다 (검증 슬래브·개구 수정 → 사용자 승인 필요, 도면에는 미반영).",
            "B. 캡슐·에스컬레이터를 시각용 보이드로 두고 방문객 수직 이동은 T3/T4 승강기와 코어 계단으로만 한다 (경로 변경 없음, 프로그램 영향 검토 필요).",
            "C. 에스컬레이터 승·하차 끝을 개구 가장자리로 옮긴다 (에스컬레이터 개구 수정 → 승인 필요).",
        ],
    }
    d2 = dec.get("D-02", [])
    P["D-02"] = {
        "title": "해당 층에 바닥판이 없는 코어 (2F 코어 D, 7F 코어 C·D)",
        "fact": "코어 벽은 모델에 있으나 코어 앞에 슬래브가 없다. 코어를 계단이 통과만 하는 닫힌 샤프트로 그리고 '출입 불가'로 표시했다(제안). 피난층·피난 동선 적합성은 검토하지 않았다.",
        "rows": d2,
        "alternatives": ["A. 코어 앞에 국부 슬래브를 연장한다 (검증 슬래브 수정 → 승인 필요).",
                         "B. 현행 유지: 해당 층에서 출입하지 않는 통과 전용 계단 (법규 검토 필요).",
                         "C. 2F 노치·7F 후퇴부에 브리지/데크를 제안한다 (모델 수정 → 승인 필요)."],
    }
    d3 = dec.get("D-03", [])
    P["D-03"] = {
        "title": "T3·T4 승강기 출입구 방향을 캡슐 개구에서 돌려 놓음 (1F 승인 심볼과 다름)",
        "fact": "1F 승인 심볼의 출입구는 남향이다. T3(2F–6F)·T4(6F–15F)에서는 남쪽 출입구가 서·동측 캡슐 개구와 접해 설 자리가 없다. 유리 원통(검증)은 그대로 두고 로비 출입구만 홀 쪽으로 45° 돌렸다(제안).",
        "rows": d3,
        "alternatives": ["A. 출입구 회전을 승인한다 (승강로·원통 변경 없음).",
                         "B. 남향을 유지하고 캡슐 개구를 줄인다 (검증 개구 수정 → 승인 필요).",
                         "C. 승강기 로비를 다시 설계한다 (1F 승인 심볼 변경 → 승인 필요)."],
    }
    d5 = dec.get("D-05", [])
    P["D-05"] = {
        "title": "FR(화물 승강기) 반입 접점",
        "fact": "모델에 FR 개구가 있으나 문·전실이 없다. 홀 쪽 45° 단위 방향 중 바닥판 위에서 비어 있는 면에 반입 문과 2.6 m 랜딩을 제안했다. 화물 전용 동선·하역장은 모델에 없다.",
        "rows": d5,
        "alternatives": ["A. 제안한 FR 반입 접점을 승인한다.", "B. 반입 방향을 지정한다.", "C. 반입을 코어 계단으로 한정한다 (화물 승강기 사용 안 함)."],
    }
    P["D-06"] = {
        "title": "후방(BOH) 동선은 공용 홀을 시간대 분리로 공유",
        "fact": "점포별 창고·주방 서비스 문에서 FR 반입 접점까지 서비스 경로(갈색 점선)를 공용 홀 위에 그렸다. 별도 후방 복도는 모델에 없어 만들지 않았다. 일부 점포는 서비스 문 앞 설 자리가 없어 서비스 문 없이 판매 공간을 통해서만 접근한다(SERVICE_DOOR_DROPPED 메모).",
        "rows": [], "alternatives": ["A. 시간대 분리 공유를 승인한다.", "B. 별도 후방 복도를 위해 점포 일부를 줄이는 안을 요청한다."],
    }
    P["D-07"] = {
        "title": "자유 개구부(12F 중앙 보이드 등)의 난간",
        "fact": "개구 가장자리에 제안 난간(붉은 점선)만 표시했다. 규격·높이·유리/금속 여부는 미정이며 검증된 난간은 모델에 없다.",
        "rows": [], "alternatives": ["A. 난간 개념(높이 1.1–1.2 m 등)을 지정한다.", "B. 보이드 용도(문화 프로그램 상부 개방)를 확정한다."],
    }
    P["D-08"] = {
        "title": "T1 나선 램프(B1–6F)의 승·하차 지점",
        "fact": "램프는 모델에 있으나 층별 출입 지점은 모델·1F 심볼에 정의가 없다. 연결 여부를 판정하지 않고 '미모델'로 기록했다.",
        "rows": dec.get("D-08", []), "alternatives": ["A. 층별 램프 출입 지점을 지정한다."],
    }
    P["D-09"] = {
        "title": "문화(11F–14F) 운영 개념과 정원(6F·15F)의 이용 규칙",
        "fact": "11F 공연·퍼포먼스, 12F 전시·미디어, 13F 창작·공방, 14F 교육·커뮤니티는 제안한 운영 개념이다(모델 값 아님). 정원은 산책로·식재·벤치·그늘 시설의 개념 배치이며 경사·포장·접근성 규격은 설계하지 않았다.",
        "rows": [], "alternatives": ["A. 운영 개념 승인/수정.", "B. 정원 접근성(경사·유효폭·포장) 기준 지정."],
    }
    return P


def write(P):
    os.makedirs(DOC, exist_ok=True)
    json.dump(P, open(os.path.join(DOC, "decision_packet.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    L = ["# C-T14T 결정 패킷 (승인 아님)", "",
         "검증 지오메트리(슬래브·기둥·코어·튜브·개구·에스컬레이터 개구)를 바꿔야만 풀리는 항목과 승인된 1F 심볼을 바꾸는 항목이다. "
         "기하를 임의로 고치지 않았고, 아래는 사용자 결정이 필요하다. 상태: `C_T14T_READY_FOR_CHATGPT_INDEPENDENT_REVIEW`.", ""]
    for k, v in P.items():
        L += ["## %s — %s" % (k, v["title"]), "", v["fact"], ""]
        if v["rows"]:
            if k == "D-01":
                L += ["| 층 | 에스컬레이터 | 구분 | 끝점 (m) | 가장 가까운 검증 보행면까지(직선) | 축 방향 슬래브까지 | 도면의 접근 지점 (m) |", "|---|---|---|---|---|---|---|"]
                for r in v["rows"]:
                    if "gap_to_slab_m" in r:
                        L.append("| %s | %s | %s | (%.1f, %.1f) | %.1f m | %s | (%.1f, %.1f) |" % (r["floor"], r["escalator"], {"board": "승차", "arrive": "하차"}[r["role"]], r["end_m"][0], r["end_m"][1],
                                                                                         r["gap_to_slab_m"], ("%.1f m" % r["axis_gap_m"]) if r.get("axis_gap_m") else "—", r["access_edge_m"][0], r["access_edge_m"][1]))
                    else:
                        L.append("| %s | %s | %s | (%.1f, %.1f) | 코어/화장실 외곽 안 | — | — |" % (r["floor"], r["escalator"], {"board": "승차", "arrive": "하차"}[r["role"]], r["end_m"][0], r["end_m"][1]))
            else:
                seen = []
                for r in v["rows"]:
                    s = ", ".join("%s=%s" % (a, b) for a, b in r.items())
                    if s not in seen:
                        seen.append(s)
                L += ["- " + s for s in seen]
            L.append("")
        L += ["선택지:"] + ["- " + a for a in v["alternatives"]] + [""]
    open(os.path.join(DOC, "decision_packet.md"), "w", encoding="utf-8", newline="\n").write("\n".join(L))
    return os.path.join(DOC, "decision_packet.md")


if __name__ == "__main__":
    print(os.path.abspath(write(build())))
