# FILE: extract/loader.py
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from extract.schema import Model, ModelObject

SCHEMA_VERSION = 1


def load_model(path) -> Model:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA_VERSION:
        raise ValueError(f"지원하지 않는 모델 JSON 스키마: {data.get('schema')!r}")
    objects = [
        ModelObject(
            name=item["name"],
            props=dict(item.get("props", {})),
            verts=np.asarray(item["verts"], dtype=float).reshape(-1, 3),
            tris=np.asarray(item["tris"], dtype=int).reshape(-1, 3),
        )
        for item in data["objects"]
    ]
    return Model(objects, meta=dict(data.get("meta", {})))
