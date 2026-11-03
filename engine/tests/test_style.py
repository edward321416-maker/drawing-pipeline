# FILE: tests/test_style.py
from extract.schema import KINDS
from render.style import FONT_FAMILY, KIND_STYLE, LINE_CLASSES, TEXT_ROLES


def test_line_classes_follow_agents_md_table():
    # boundary(대지경계선)는 AGENTS.md §3.1 표에 없던 선종으로 대지 도면을 위해 더했다
    assert set(LINE_CLASSES) == {"cut_heavy", "cut_medium", "projection_light", "detail", "grid", "boundary", "context"}
    ranges = {k: (v.lw_min, v.lw_max) for k, v in LINE_CLASSES.items()}
    assert ranges["cut_heavy"] == (1.6, 1.8)
    assert ranges["cut_medium"] == (1.0, 1.2)
    assert ranges["projection_light"] == (0.5, 0.6)
    assert ranges["detail"] == (0.35, 0.4)
    assert ranges["grid"] == (0.4, 0.4)
    assert LINE_CLASSES["cut_heavy"].color == "#000000"
    assert LINE_CLASSES["detail"].linestyle == "--"
    assert LINE_CLASSES["grid"].linestyle == (0, (6, 3, 1, 3))


def test_defaults_are_inside_their_ranges():
    for spec in LINE_CLASSES.values():
        assert spec.lw_min <= spec.lw <= spec.lw_max
    for spec in TEXT_ROLES.values():
        assert spec.size_min <= spec.size <= spec.size_max


def test_text_roles_follow_agents_md_table():
    assert set(TEXT_ROLES) == {"title", "room", "sub", "micro"}
    assert (TEXT_ROLES["title"].size_min, TEXT_ROLES["title"].size_max) == (11.0, 13.0)
    assert (TEXT_ROLES["room"].size_min, TEXT_ROLES["room"].size_max) == (7.5, 8.5)
    assert (TEXT_ROLES["sub"].size_min, TEXT_ROLES["sub"].size_max) == (6.0, 6.5)
    assert (TEXT_ROLES["micro"].size_min, TEXT_ROLES["micro"].size_max) == (5.0, 5.5)
    assert TEXT_ROLES["sub"].weight == "normal"
    assert FONT_FAMILY[0] == "Malgun Gothic"


def test_kind_style_covers_every_drawn_kind():
    # slab(윤곽으로만)·room(라벨 전용)·door(심볼이 호와 문짝으로 그림)는 KIND_STYLE로 그리지 않는다
    assert set(KIND_STYLE) | {"slab", "room", "door"} == set(KINDS)
    for klass, _fill in KIND_STYLE.values():
        assert klass in LINE_CLASSES
