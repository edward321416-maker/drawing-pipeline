# FILE: tests/test_inventory.py
from extract.inventory_report import group_inventory, group_prefix, render_markdown


def _item(name, kind=None, lo=(0, 0, 0), hi=(1, 1, 1), typ="MESH"):
    props = {"kind": kind} if kind else {}
    return {"name": name, "type": typ, "props": props, "bbox_min": list(lo), "bbox_max": list(hi)}


def test_group_prefix_strips_numeric_components():
    assert group_prefix("Bench_0") == "Bench"
    assert group_prefix("CafeSet_2_Chair_3") == "CafeSet_Chair"
    assert group_prefix("Col.001") == "Col"
    assert group_prefix("Wall_N") == "Wall_N"


def test_group_inventory_counts_tags_and_bounds():
    items = [
        _item("Bench_0", lo=(0, 0, 0), hi=(2, 1, 1)),
        _item("Bench_1", lo=(5, 5, 0), hi=(7, 6, 1)),
        _item("CafeSet_0_Chair_0", kind="fixture"),
        _item("CafeSet_1_Chair_0"),
        {"name": "Camera", "type": "CAMERA", "props": {}},
    ]
    groups = {g["prefix"]: g for g in group_inventory(items)}
    assert groups["Bench"]["count"] == 2
    assert groups["Bench"]["bbox_min"] == [0, 0, 0] and groups["Bench"]["bbox_max"] == [7, 6, 1]
    assert groups["CafeSet_Chair"]["count"] == 2 and groups["CafeSet_Chair"]["tagged"] == 1
    assert groups["CafeSet_Chair"]["kinds"] == ["fixture"]
    assert groups["Camera"]["bbox_min"] is None


def test_markdown_reports_totals_and_absolute_source_path():
    groups = group_inventory([_item("Bench_0"), _item("Bench_1", kind="fixture")])
    md = render_markdown(groups, r"D:\Users\admin\Desktop\2학기 논문\도면\01_과정\01_기획_구획_베이스\1F_시장홀_모델.blend")
    assert "총 객체: 2" in md and "태그됨: 1" in md and "태그 없음: 1" in md
    assert r"D:\Users\admin\Desktop\2학기 논문\도면\01_과정\01_기획_구획_베이스\1F_시장홀_모델.blend" in md
    assert "| Bench |" in md
