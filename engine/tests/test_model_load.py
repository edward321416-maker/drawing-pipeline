# FILE: tests/test_model_load.py
import json

import numpy as np
import pytest

from checks.tags import check_tags
from extract.loader import load_model
from extract.schema import ModelObject, Model
from model_fixtures import box_mesh, mk, sample_model, write_model_json


def test_roundtrip_keeps_objects_tags_and_coordinates(tmp_path):
    original = sample_model()
    path = write_model_json(original, tmp_path / "model.json")
    loaded = load_model(path)
    assert [o.name for o in loaded.objects] == [o.name for o in original.objects]
    first = loaded.get("Wall_S")
    assert first.kind == "exterior_wall"
    assert first.name_ko == "남측 외벽"
    assert np.allclose(first.verts, original.get("Wall_S").verts)


def test_load_rejects_unknown_schema_version(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema": 99, "objects": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_model(path)


def test_clean_sample_model_passes_tag_gate():
    assert check_tags(sample_model()) == []


def test_tag_gate_rejects_missing_and_unknown_tags():
    model = sample_model()
    verts, tris = box_mesh(0, 0, 1, 1, 0, 1)
    model.objects.append(ModelObject("Untagged", {}, verts, tris))
    model.objects.append(mk("WrongKind", "sofa", "소파", box_mesh(2, 2, 3, 3, 0, 1)))
    violations = check_tags(model)
    assert {v.check for v in violations} == {"TAG"}
    messages = " ".join(v.message for v in violations)
    assert "Untagged" in messages and "kind" in messages and "name_ko" in messages
    assert "WrongKind" in messages and "sofa" in messages
    assert len(violations) == 3


def test_by_kind_and_get():
    model = sample_model()
    assert len(model.by_kind("zone")) == 2
    with pytest.raises(KeyError):
        model.get("nope")
    assert isinstance(model, Model)
