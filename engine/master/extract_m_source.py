"""중간발표 설계(07_representation/s7.py)의 1층 데이터를 읽어 논문 작업공간의 JSON으로 고정(freeze)한다.

읽기 전용이다. 중간발표 폴더에는 아무것도 쓰지 않는다(바이트코드도 만들지 않는다).
사용: python master\\extract_m_source.py
출력: model\\m_1f_source.json  (대지 좌표 u, v — 건물 54 m x 54 m, 범위 u -9~45, v -18~36)
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

import shapely

MIDTERM_07 = r"D:\Users\admin\Desktop\5-2\설계스튜디오\중간발표\07_representation"
OUT = Path(__file__).resolve().parent.parent / "model" / "m_1f_source.json"


def _wkt(geom) -> str:
    return shapely.to_wkt(geom, rounding_precision=6)


def main() -> int:
    sys.dont_write_bytecode = True
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, MIDTERM_07)
    os.chdir(MIDTERM_07)
    import s7  # noqa: E402  (중간발표 작업공간 모듈)

    z1f = s7.ZF["1F"]
    columns = [
        [round(u, 4), round(v, 4), z0, z1]
        for (u, v, z0, z1) in s7.columns()
        if z0 <= z1f + 0.6 and z1 > z1f
    ]
    small = [n for n in s7.SMALL if s7.TUBE[n]["z0"] <= z1f + 0.1 < s7.TUBE[n]["z1"]]
    data = {
        "provenance": {
            "source": os.path.join(MIDTERM_07, "s7.py"),
            "extracted": datetime.date.today().isoformat(),
            "frame": "대지 좌표 (u, v) m. 마스터 모델은 X1·A 교점이 원점이 되도록 u+9, v+18로 환산한다",
        },
        "floor_z": {"1F": s7.ZF["1F"], "2F": s7.ZF["2F"]},
        "col_r": s7.COL_R,
        "north_vec": [round(float(v), 6) for v in s7.north_vec()],  # 대지 축(u 오른쪽, v 위)에서의 진북 방향
        "columns": columns,
        "tubes": {
            k: {"c": list(t["c"]), "r": t["r"], "kind": t["kind"], "role": t["role"]}
            for k, t in s7.TUBE.items()
        },
        "small": small,
        "stairs": {k: list(p.bounds) for k, p in s7.STAIRS.items()},
        "wc": {k: list(g.bounds) for k, g in s7.WC.items()},
        "wkt": {
            "plate_1f": _wkt(s7.PLATE["1F"]),
            "piloti": _wkt(s7.PILOTI),
            "service": _wkt(s7.SERVICE),
            "cap_w": _wkt(s7.CAP_W),
        },
        "reference_areas": {
            "enclosed_1f": round(s7.ENCLOSED["1F"].area, 1),
            "market_hall_typed": 1640,
            "service_typed": 250,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"고정 완료: {os.path.abspath(OUT)}")
    print(f"기둥 {len(columns)}개, 튜브 {len(data['tubes'])}개, 1층을 지나는 소형 샤프트 {small}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
