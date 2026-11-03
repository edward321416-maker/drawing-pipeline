# 도면 엔진 코어 (Drawing Engine Core) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 태그된 Blender 3D 모델을 높이별로 절단해 벡터 평면도를 파생하고, 독립 검사기를 통과한 결과물만 `01_과정`에 내보내는 엔진 코어를 만든다.

**Architecture:** Blender 헤드리스 실행으로 객체(태그·월드 좌표 메시)를 JSON으로 추출 → 순수 Python(shapely)이 높이별로 절단해 `Sections`를 만든다 → 기하 검사(G)가 `Sections`를 검증 → 라벨 배치 솔버가 빈 공간에 라벨을 계산 배치 → matplotlib 렌더러가 선 두께·텍스트 위계 표를 유일한 출처로 벡터 평면을 그림 → 텍스트·스타일 검사(T)가 렌더된 결과(실제 글자 경계 상자, 아티스트에서 읽은 선 두께)를 검증. `build.py`가 한 번에 실행하고 위반이 있으면 `_rejected`로 보낸다.

**Tech Stack:** Python 3.14, shapely 2.2, numpy, matplotlib 3.10(Agg), PyYAML, pytest 9, Blender 4.2(헤드리스, 추출 전용).

**Spec:** `D:\Users\admin\Desktop\2학기 논문\docs\superpowers\specs\2026-11-01-drawing-errorfree-generation-design.md`

## Scope (이 계획의 범위)

기획안 §9의 **P0 감사 도구 + P1 엔진 골격**에 해당한다. 아래는 승인 1(3D 모델) 이후 **별도 계획**으로 작성한다. 심볼 규격이 사용자가 정할 불일치 항목(화장실 개수, Blender 승강로 등)에 의존하기 때문이다.

| 이 계획에 없는 것 | 이유 |
|---|---|
| 심볼 라이브러리(코어, 튜브, 화장실, 보이드) — P2 | 불일치 항목 확정 후 |
| 문 스윙 검사 G3, 법규·인체치수 검사 R1 — P3 | 심볼이 문·치수를 만든 뒤에 검사 가능 |
| 3단계 인필, 픽셀 게이트 P1, 일관성 검사 C1 — P4 | 상세도 승인 후 |
| 마스터 3D 모델(`1F_master.blend`) 작성 — P0 후반 | 사용자와 함께 정답을 정하는 단계 |
| DXF 내보내기 — P5 | 후순위 |

## Global Constraints

- 선 두께 5단계(Matplotlib lw, `AGENTS.md` §3.1): Cut Heavy `1.6~1.8` `#000000` / Cut Medium `1.0~1.2` `#222222` / Projection Light `0.5~0.6` `#444444` / Detail `0.35~0.4` `#aaaaaa` 점선 `--` / Structural Grid `0.4` `#dcdcdc` 1점 쇄선 `(0, (6, 3, 1, 3))`.
- 텍스트 위계 4단계: Title `11~13 pt` Bold `#111111` / Room Name `7.5~8.5 pt` Bold `#222222` / Sub-label·Area `6.0~6.5 pt` Regular `#555555` / Micro `5.0~5.5 pt` Bold `#333333`.
- 텍스트는 선 위에 얹히면 안 된다. 부득이한 경우만 순백색 배경 박스 `bbox=dict(boxstyle='square,pad=0.2', facecolor='white', edgecolor='none')`.
- 평면 절단 높이 `1.5 m`, 검사 높이 `0.3 m, 1.5 m, 3.0 m`(층고 확정 후 천장 아래 0.3 m를 추가). 구조 격자 `9 m`, 기둥 Ø`0.9 m`.
- 한글 폰트 맑은 고딕, 영문 Arial, 해상도 `300 DPI`, 축척 `1:300 @ A3`.
- 검사 위반 0건이면 `D:\Users\admin\Desktop\2학기 논문\도면\01_과정\01_기획_구획_베이스`에, 1건 이상이면 `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\_rejected`에 저장한다. `D:\Users\admin\Desktop\2학기 논문\도면\02_최종결과물`에는 사용자가 "최종 승인"한 파일만 둔다. 이 계획의 어떤 코드도 그 폴더에 쓰지 않는다.
- 콘솔·로그·보고서에 출력하는 파일 경로는 `os.path.abspath()`로 전체 절대 경로를 쓴다.
- 기존 `D:\Users\admin\Desktop\2학기 논문\scratch` 스크립트와 기존 `.blend`는 수정·삭제하지 않는다.
- 커밋은 사용자가 요청할 때만 한다. 각 태스크 마지막의 Commit 스텝은 그때 실행한다.
- 엔진 루트는 `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진`이다. 코드 블록 첫 줄의 `# FILE: <경로>`는 엔진 루트 기준 상대 경로이며, 각 태스크의 Files 목록에 전체 절대 경로를 적는다.
- 테스트 실행은 엔진 루트에서 `python -m pytest tests -v`. Blender 통합 테스트는 Blender가 없으면 skip된다(현재 `C:\Program Files\Blender Foundation\Blender 4.2\blender.exe`).

---

## File Structure

| 파일 (엔진 루트 기준) | 책임 |
|---|---|
| `conftest.py` | pytest import 경로 설정 |
| `engine_params.py`, `model/params.yaml` | 법규·치수·허용오차 파라미터 로더 (유일한 수치 출처) |
| `render/style.py` | 선 두께 5단계, 텍스트 4단계, kind → 선종·채움 매핑 (유일한 스타일 출처) |
| `extract/schema.py` | `KINDS`, `ModelObject`, `Model` |
| `extract/loader.py` | 모델 JSON 로더 |
| `extract/slicer.py` | 메시 절단 → shapely, `slice_model`, `Sections`, `filled_shell` |
| `extract/blender_export.py` | Blender 안에서 실행되는 JSON 내보내기 |
| `extract/run_blender.py` | Blender 헤드리스 실행 래퍼 |
| `extract/blender_inventory.py`, `extract/inventory_report.py` | 기존 `.blend` 감사(P0) |
| `checks/base.py` | `Violation`, `dedupe` |
| `checks/tags.py` | TAG 게이트 |
| `checks/geometry.py` | G1, G2, G4, G5 |
| `checks/text.py` | T1, T2, T3, T4 |
| `checks/registry.py` | 검사 ID 등록부와 일괄 실행 |
| `layout/labels.py` | 라벨 배치 솔버 |
| `render/plan_renderer.py` | 벡터 평면 렌더러와 `RenderResult` |
| `ledger/ledger.yaml`, `ledger/ledger.py` | 결함 장부와 감사 |
| `build.py` | 단일 진입점 |
| `tests/model_fixtures.py` | 테스트용 합성 모델(Blender 불필요) |
| `tests/test_*.py` | 각 모듈 테스트 |

---

### Task 1: 스캐폴딩, 파라미터, 스타일 표

**Files:**
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\conftest.py`
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\engine_params.py`
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\model\params.yaml`
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\render\style.py`
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\_rejected\.gitignore`
- Test: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_params.py`
- Test: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_style.py`

**Interfaces:**
- Produces: `engine_params.load_params(path: Path | None = None) -> Params` (`Params`는 frozen dataclass, 필드: `plan_cut_height_m, check_heights_m, grid_spacing_m, grid_tolerance_m, furniture_to_column_m, zone_overlap_tolerance_m2, zone_coverage_tolerance_ratio, scale_denominator, margin_m, dpi, label_gap_m, label_pad_m, text_collision_tolerance_m2`)
- Produces: `render.style.LINE_CLASSES: dict[str, LineClass]`, `TEXT_ROLES: dict[str, TextRole]`, `KIND_STYLE: dict[str, tuple[str, str | None]]`, `FONT_FAMILY: list[str]`

- [ ] **Step 1: 폴더와 패키지 파일 만들기**

```powershell
$e = 'D:\Users\admin\Desktop\2학기 논문\도면\00_엔진'
foreach ($d in 'model','extract','checks','render','layout','ledger','tests','reports','_rejected') {
  New-Item -ItemType Directory -Force -LiteralPath (Join-Path $e $d) | Out-Null
}
foreach ($d in 'extract','checks','render','layout','ledger') {
  $f = Join-Path $e "$d\__init__.py"
  if (-not (Test-Path -LiteralPath $f)) { New-Item -ItemType File -LiteralPath $f | Out-Null }
}
Get-ChildItem -LiteralPath $e | Select-Object Name
```

Expected: `model, extract, checks, render, layout, ledger, tests, reports, _rejected` 폴더가 보인다.

- [ ] **Step 2: 실패하는 테스트 작성**

```python
# FILE: tests/test_params.py
from pathlib import Path

import pytest

from engine_params import DEFAULT_PATH, load_params


def test_default_params_load():
    p = load_params()
    assert p.plan_cut_height_m == 1.5
    assert p.plan_cut_height_m in p.check_heights_m
    assert p.grid_spacing_m == 9.0
    assert p.scale_denominator == 300


def test_cut_height_must_be_among_check_heights(tmp_path: Path):
    text = DEFAULT_PATH.read_text(encoding="utf-8")
    bad = tmp_path / "params.yaml"
    bad.write_text(text.replace("[0.3, 1.5, 3.0]", "[0.3, 3.0]"), encoding="utf-8")
    with pytest.raises(ValueError):
        load_params(bad)
```

```python
# FILE: tests/test_style.py
from extract.schema import KINDS
from render.style import FONT_FAMILY, KIND_STYLE, LINE_CLASSES, TEXT_ROLES


def test_line_classes_follow_agents_md_table():
    assert set(LINE_CLASSES) == {"cut_heavy", "cut_medium", "projection_light", "detail", "grid"}
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
    assert set(KIND_STYLE) | {"slab"} == set(KINDS)
    for klass, _fill in KIND_STYLE.values():
        assert klass in LINE_CLASSES
```

- [ ] **Step 3: 테스트가 실패하는지 확인**

Run: `Set-Location -LiteralPath 'D:\Users\admin\Desktop\2학기 논문\도면\00_엔진'; python -m pytest tests\test_params.py tests\test_style.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'engine_params'`)

- [ ] **Step 4: 구현 (conftest, 파라미터, 스타일)**

```python
# FILE: conftest.py
import sys
from pathlib import Path

ROOT = Path(__file__).parent
for p in (ROOT, ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
```

```yaml
# FILE: model/params.yaml
# 엔진의 유일한 수치 출처. 코드에 같은 숫자를 다시 쓰지 않는다.
slice:
  plan_cut_height_m: 1.5            # 평면 절단 높이 (바닥 위)
  check_heights_m: [0.3, 1.5, 3.0]  # 3D 간섭 검사 높이. 층고 확정 시 천장 아래 0.3 m를 추가
grid:
  spacing_m: 9.0
  tolerance_m: 0.01
clearance:
  furniture_to_column_m: 1.2        # 기물-기둥 최소 이격 (통로 최소폭 1,200 mm와 같은 값)
zones:
  overlap_tolerance_m2: 0.01
  coverage_tolerance_ratio: 0.005   # 바닥 슬래브 중 구획존이 덮지 못해도 되는 비율
render:
  scale_denominator: 300            # 1:300 @ A3
  margin_m: 4.0
  dpi: 300
  label_gap_m: 0.3
  label_pad_m: 0.25
text:
  collision_tolerance_m2: 1.0e-6
```

```python
# FILE: engine_params.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).parent / "model" / "params.yaml"


@dataclass(frozen=True)
class Params:
    plan_cut_height_m: float
    check_heights_m: tuple[float, ...]
    grid_spacing_m: float
    grid_tolerance_m: float
    furniture_to_column_m: float
    zone_overlap_tolerance_m2: float
    zone_coverage_tolerance_ratio: float
    scale_denominator: float
    margin_m: float
    dpi: int
    label_gap_m: float
    label_pad_m: float
    text_collision_tolerance_m2: float


def load_params(path: Path | None = None) -> Params:
    raw = yaml.safe_load(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"))
    params = Params(
        plan_cut_height_m=float(raw["slice"]["plan_cut_height_m"]),
        check_heights_m=tuple(float(h) for h in raw["slice"]["check_heights_m"]),
        grid_spacing_m=float(raw["grid"]["spacing_m"]),
        grid_tolerance_m=float(raw["grid"]["tolerance_m"]),
        furniture_to_column_m=float(raw["clearance"]["furniture_to_column_m"]),
        zone_overlap_tolerance_m2=float(raw["zones"]["overlap_tolerance_m2"]),
        zone_coverage_tolerance_ratio=float(raw["zones"]["coverage_tolerance_ratio"]),
        scale_denominator=float(raw["render"]["scale_denominator"]),
        margin_m=float(raw["render"]["margin_m"]),
        dpi=int(raw["render"]["dpi"]),
        label_gap_m=float(raw["render"]["label_gap_m"]),
        label_pad_m=float(raw["render"]["label_pad_m"]),
        text_collision_tolerance_m2=float(raw["text"]["collision_tolerance_m2"]),
    )
    if params.plan_cut_height_m not in params.check_heights_m:
        raise ValueError("plan_cut_height_m must be one of check_heights_m")
    return params
```

```python
# FILE: render/style.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LineClass:
    name: str
    lw: float
    lw_min: float
    lw_max: float
    color: str
    linestyle: object


@dataclass(frozen=True)
class TextRole:
    name: str
    size: float
    size_min: float
    size_max: float
    weight: str
    color: str


# AGENTS.md §3.1 선 두께 위계 (유일한 출처)
LINE_CLASSES = {
    "cut_heavy": LineClass("cut_heavy", 1.7, 1.6, 1.8, "#000000", "-"),
    "cut_medium": LineClass("cut_medium", 1.1, 1.0, 1.2, "#222222", "-"),
    "projection_light": LineClass("projection_light", 0.55, 0.5, 0.6, "#444444", "-"),
    "detail": LineClass("detail", 0.38, 0.35, 0.4, "#aaaaaa", "--"),
    "grid": LineClass("grid", 0.4, 0.4, 0.4, "#dcdcdc", (0, (6, 3, 1, 3))),
}

# AGENTS.md §3.1 텍스트 위계 (유일한 출처)
TEXT_ROLES = {
    "title": TextRole("title", 12.0, 11.0, 13.0, "bold", "#111111"),
    "room": TextRole("room", 8.0, 7.5, 8.5, "bold", "#222222"),
    "sub": TextRole("sub", 6.25, 6.0, 6.5, "normal", "#555555"),
    "micro": TextRole("micro", 5.25, 5.0, 5.5, "bold", "#333333"),
}

FONT_FAMILY = ["Malgun Gothic", "Arial", "DejaVu Sans"]

# kind -> (선종, 채움색). 채움이 None이면 윤곽선만 그린다.
KIND_STYLE = {
    "column": ("cut_heavy", "#000000"),
    "exterior_wall": ("cut_heavy", "#111111"),
    "core_wall": ("cut_heavy", "#1a1a1a"),
    "partition_wall": ("cut_medium", "#666666"),
    "tube_wall": ("cut_medium", None),
    "stair": ("projection_light", None),
    "shaft": ("projection_light", None),
    "fixture": ("projection_light", None),
    "void": ("detail", None),
    "zone": ("detail", None),
}
```

```text
# FILE: _rejected/.gitignore
*
!.gitignore
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests\test_params.py -v`
Expected: 2 passed. (`test_style.py`는 `extract.schema`가 Task 2에서 만들어지므로 아직 실패한다.)

- [ ] **Step 6: Commit (사용자가 커밋을 요청한 경우에만)**

```bash
git add "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\conftest.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\engine_params.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\model\params.yaml" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\render\style.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_params.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_style.py"
git commit -m "feat(engine): add params loader and single-source style tables"
```

---

### Task 2: 모델 스키마, 로더, 태그 게이트, 합성 테스트 모델

**Files:**
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\extract\schema.py`
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\extract\loader.py`
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\checks\base.py`
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\checks\tags.py`
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\model_fixtures.py`
- Test: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_model_load.py`

**Interfaces:**
- Produces: `extract.schema.KINDS: frozenset[str]`, `WALL_KINDS`, `REQUIRED_TAGS`, `ModelObject(name, props, verts, tris)` (속성 `kind, name_ko, zmin, zmax, zmid, center_xy`), `Model(objects)` (`by_kind(*kinds)`, `get(name)`)
- Produces: `extract.loader.load_model(path) -> Model`
- Produces: `checks.base.Violation(check, message, where=None, objects=())`, `dedupe(violations)`
- Produces: `checks.tags.check_tags(model) -> list[Violation]`
- Produces (tests): `model_fixtures.sample_model() -> Model`, `mk(name, kind, name_ko, mesh, **extra) -> ModelObject`, `box_mesh(x0,y0,x1,y1,z0,z1)`, `cylinder_mesh(cx,cy,r,z0,z1,n=48)`, `ring_mesh(cx,cy,r_out,r_in,z0,z1,n=48)`, `write_model_json(model, path) -> Path`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
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
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests\test_model_load.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'checks.tags'`)

- [ ] **Step 3: 구현**

```python
# FILE: extract/schema.py
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

KINDS = frozenset({
    "column", "exterior_wall", "core_wall", "partition_wall", "tube_wall",
    "stair", "shaft", "fixture", "void", "zone", "slab",
})
WALL_KINDS = frozenset({"exterior_wall", "core_wall", "partition_wall"})
REQUIRED_TAGS = ("kind", "name_ko")


@dataclass(frozen=True, eq=False)
class ModelObject:
    name: str
    props: dict
    verts: np.ndarray  # (n, 3) 월드 좌표, 미터
    tris: np.ndarray   # (m, 3) 정점 인덱스

    @property
    def kind(self):
        return self.props.get("kind")

    @property
    def name_ko(self):
        return self.props.get("name_ko")

    @property
    def zmin(self) -> float:
        return float(self.verts[:, 2].min())

    @property
    def zmax(self) -> float:
        return float(self.verts[:, 2].max())

    @property
    def zmid(self) -> float:
        return (self.zmin + self.zmax) / 2.0

    @property
    def center_xy(self) -> tuple[float, float]:
        lo = self.verts[:, :2].min(axis=0)
        hi = self.verts[:, :2].max(axis=0)
        return (round(float((lo[0] + hi[0]) / 2), 2), round(float((lo[1] + hi[1]) / 2), 2))


@dataclass
class Model:
    objects: list[ModelObject] = field(default_factory=list)

    def by_kind(self, *kinds: str) -> list[ModelObject]:
        return [o for o in self.objects if o.kind in kinds]

    def get(self, name: str) -> ModelObject:
        for o in self.objects:
            if o.name == name:
                return o
        raise KeyError(name)
```

```python
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
    return Model(objects)
```

```python
# FILE: checks/base.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Violation:
    check: str
    message: str
    where: tuple[float, float] | None = None
    objects: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "check": self.check,
            "message": self.message,
            "where": list(self.where) if self.where else None,
            "objects": list(self.objects),
        }


def dedupe(violations):
    """같은 (검사, 객체쌍)의 위반은 첫 건만 남긴다(여러 높이에서 중복 보고 방지)."""
    seen, out = set(), []
    for v in violations:
        key = (v.check, v.objects)
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out
```

```python
# FILE: checks/tags.py
from __future__ import annotations

from checks.base import Violation
from extract.schema import KINDS, REQUIRED_TAGS


def check_tags(model) -> list[Violation]:
    out = []
    for o in model.objects:
        where = o.center_xy if len(o.verts) else None
        for tag in REQUIRED_TAGS:
            value = o.props.get(tag)
            if value is None or str(value).strip() == "":
                out.append(Violation("TAG", f"객체 '{o.name}': 필수 태그 '{tag}' 없음", where, (o.name,)))
        if o.kind is not None and o.kind not in KINDS:
            out.append(Violation("TAG", f"객체 '{o.name}': 알 수 없는 kind '{o.kind}'", where, (o.name,)))
    return out
```

```python
# FILE: tests/model_fixtures.py
"""Blender 없이 쓰는 합성 1F 축소 모델 (18 m x 18 m, 9 m 격자 3x3)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from extract.schema import Model, ModelObject


def box_mesh(x0, y0, x1, y1, z0, z1):
    v = np.array(
        [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
         [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]],
        dtype=float,
    )
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    tris = [t for a, b, c, d in quads for t in ((a, b, c), (a, c, d))]
    return v, np.array(tris, dtype=int)


def cylinder_mesh(cx, cy, r, z0, z1, n=48):
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    bottom = np.c_[cx + r * np.cos(ang), cy + r * np.sin(ang), np.full(n, z0)]
    top = bottom.copy()
    top[:, 2] = z1
    verts = np.vstack([bottom, top, [[cx, cy, z0]], [[cx, cy, z1]]])
    cb, ct = 2 * n, 2 * n + 1
    tris = []
    for i in range(n):
        j = (i + 1) % n
        tris += [(i, j, n + j), (i, n + j, n + i), (cb, j, i), (ct, n + i, n + j)]
    return verts, np.array(tris, dtype=int)


def ring_mesh(cx, cy, r_out, r_in, z0, z1, n=48):
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)

    def ring(r, z):
        return np.c_[cx + r * np.cos(ang), cy + r * np.sin(ang), np.full(n, z)]

    verts = np.vstack([ring(r_out, z0), ring(r_out, z1), ring(r_in, z0), ring(r_in, z1)])
    ob, ot, ib, it = 0, n, 2 * n, 3 * n
    tris = []
    for i in range(n):
        j = (i + 1) % n
        tris += [(ob + i, ob + j, ot + j), (ob + i, ot + j, ot + i)]   # 외측면
        tris += [(ib + i, it + j, ib + j), (ib + i, it + i, it + j)]   # 내측면
        tris += [(ot + i, ot + j, it + j), (ot + i, it + j, it + i)]   # 상부 링
        tris += [(ob + i, ib + j, ob + j), (ob + i, ib + i, ib + j)]   # 하부 링
    return verts, np.array(tris, dtype=int)


def mk(name, kind, name_ko, mesh, **extra) -> ModelObject:
    verts, tris = mesh
    return ModelObject(name, {"kind": kind, "name_ko": name_ko, **extra}, verts, tris)


def sample_model() -> Model:
    t = 0.175
    objs = [mk("Slab_1F", "slab", "1층 바닥", box_mesh(0, 0, 18, 18, -0.3, 0.0))]
    objs += [
        mk("Wall_S", "exterior_wall", "남측 외벽", box_mesh(-t, -t, 18 + t, t, 0, 4.5)),
        mk("Wall_N", "exterior_wall", "북측 외벽", box_mesh(-t, 18 - t, 18 + t, 18 + t, 0, 4.5)),
        mk("Wall_W", "exterior_wall", "서측 외벽", box_mesh(-t, -t, t, 18 + t, 0, 4.5)),
        mk("Wall_E", "exterior_wall", "동측 외벽", box_mesh(18 - t, -t, 18 + t, 18 + t, 0, 4.5)),
    ]
    for gx in (0, 9, 18):
        for gy in (0, 9, 18):
            if (gx, gy) == (9, 9):  # 튜브가 차지하는 격자점은 기둥 생략
                continue
            objs.append(mk(f"Col_{gx}_{gy}", "column", f"기둥 {gx}-{gy}", cylinder_mesh(gx, gy, 0.45, 0, 4.5)))
    objs += [
        mk("Tube_T1", "tube_wall", "T1 튜브", ring_mesh(9, 9, 3.0, 2.85, 0, 4.5)),
        mk("Void_Esc", "void", "에스컬 보이드", box_mesh(13, 6, 16, 12, 0, 4.5)),
        mk("Bench_1", "fixture", "벤치", box_mesh(2, 13, 4.2, 13.5, 0, 0.45)),
        mk("Showcase_1", "fixture", "쇼케이스", box_mesh(14, 1.5, 15.4, 2.9, 0, 1.0)),
        mk("Zone_West", "zone", "공공보행통로", box_mesh(0, 0, 9, 18, 0, 0.05)),
        mk("Zone_East", "zone", "시장 홀", box_mesh(9, 0, 18, 18, 0, 0.05)),
    ]
    return Model(objs)


def write_model_json(model: Model, path) -> Path:
    data = {
        "schema": 1,
        "units": "m",
        "objects": [
            {"name": o.name, "props": o.props, "verts": o.verts.tolist(), "tris": o.tris.tolist()}
            for o in model.objects
        ],
    }
    path = Path(path)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests\test_model_load.py tests\test_style.py tests\test_params.py -v`
Expected: 모두 PASS (`test_style.py`의 `KINDS` 일치 테스트 포함)

- [ ] **Step 5: Commit (사용자가 커밋을 요청한 경우에만)**

```bash
git add "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\extract" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\checks\base.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\checks\tags.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\checks\__init__.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\model_fixtures.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_model_load.py"
git commit -m "feat(engine): add tagged model schema, loader and tag gate"
```

---

### Task 3: 메시 절단기 (Slicer)

**Files:**
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\extract\slicer.py`
- Test: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_slicer.py`

**Interfaces:**
- Consumes: `ModelObject`, `Model` from Task 2
- Produces: `extract.slicer.section(obj: ModelObject, z: float) -> BaseGeometry` (빈 도형 가능)
- Produces: `extract.slicer.filled_shell(geom) -> BaseGeometry` (링의 구멍을 메운 영역)
- Produces: `extract.slicer.slice_model(model, heights) -> Sections`; `Sections.at(h) -> dict[str, geom]`, `.footprint(name) -> geom`(객체 z 중간 높이 단면), `.obj(name)`, `.kind(name)`, `.heights`, `.model`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# FILE: tests/test_slicer.py
import math

import pytest
from shapely.geometry import Point

from extract.slicer import filled_shell, section, slice_model
from model_fixtures import box_mesh, cylinder_mesh, mk, ring_mesh, sample_model


def _obj(mesh):
    return mk("T", "column", "시험", mesh)


def test_box_section_area_and_bounds():
    g = section(_obj(box_mesh(1, 2, 4, 6, 0, 3)), 1.5)
    assert g.area == pytest.approx(12.0)
    assert g.bounds == pytest.approx((1, 2, 4, 6))


def test_section_outside_height_range_is_empty():
    assert section(_obj(box_mesh(0, 0, 1, 1, 0, 1)), 5.0).is_empty


def test_section_on_top_face_does_not_crash_and_keeps_area():
    g = section(_obj(box_mesh(0, 0, 2, 2, 0, 2)), 2.0)
    assert g.area == pytest.approx(4.0, rel=1e-3)


def test_cylinder_section_matches_polygon_area():
    n, r = 48, 0.45
    expected = 0.5 * n * r * r * math.sin(2 * math.pi / n)
    g = section(_obj(cylinder_mesh(5, 5, r, 0, 4, n)), 1.5)
    assert g.area == pytest.approx(expected, rel=1e-3)


def test_ring_section_keeps_hole_and_filled_shell_fills_it():
    n, ro, ri = 48, 3.0, 2.85
    k = 0.5 * n * math.sin(2 * math.pi / n)
    g = section(_obj(ring_mesh(9, 9, ro, ri, 0, 4.5, n)), 1.5)
    assert g.area == pytest.approx(k * (ro**2 - ri**2), rel=1e-3)
    assert not g.contains(Point(9, 9))
    assert filled_shell(g).contains(Point(9, 9))
    assert filled_shell(g).area == pytest.approx(k * ro**2, rel=1e-3)


def test_slice_model_exposes_heights_footprints_and_kinds():
    model = sample_model()
    sections = slice_model(model, (0.3, 1.5, 3.0))
    assert "Col_0_0" in sections.at(1.5)
    assert "Bench_1" in sections.at(0.3) and "Bench_1" not in sections.at(1.5)
    assert sections.footprint("Zone_West").area == pytest.approx(162.0)
    assert sections.footprint("Slab_1F").area == pytest.approx(324.0)
    assert sections.kind("Tube_T1") == "tube_wall"
    assert sections.obj("Tube_T1").name == "Tube_T1"
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests\test_slicer.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'extract.slicer'`)

- [ ] **Step 3: 구현**

```python
# FILE: extract/slicer.py
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize, unary_union

from extract.schema import Model, ModelObject

_EPS = 1e-9


def _segments_at(verts: np.ndarray, tris: np.ndarray, z: float) -> list[LineString]:
    corners = verts[tris]                       # (m, 3, 3)
    dist = corners[:, :, 2] - z                 # 절단면까지의 부호 거리
    dist = np.where(np.abs(dist) < _EPS, _EPS, dist)  # 정점이 평면 위에 있으면 위쪽으로 취급
    segments = []
    for tri, d in zip(corners, dist):
        above = d > 0
        if above.all() or (~above).all():
            continue
        pts = []
        for a, b in ((0, 1), (1, 2), (2, 0)):
            if above[a] != above[b]:
                s = d[a] / (d[a] - d[b])
                p = tri[a] + s * (tri[b] - tri[a])
                pts.append((round(float(p[0]), 6), round(float(p[1]), 6)))
        if len(pts) == 2 and pts[0] != pts[1]:
            segments.append(LineString(pts))
    return segments


def section(obj: ModelObject, z: float) -> BaseGeometry:
    """메시를 수평면 z에서 자른 단면(내부 영역). 닫힌 메시의 짝수-홀수 규칙으로 구멍을 처리한다."""
    segments = _segments_at(obj.verts, obj.tris, z)
    if not segments:
        return Polygon()
    faces = list(polygonize(unary_union(segments)))
    if not faces:
        return Polygon()
    shells = [Polygon(f.exterior) for f in faces]
    inside = []
    for f in faces:
        p = f.representative_point()
        if sum(1 for s in shells if s.contains(p)) % 2 == 1:
            inside.append(f)
    return unary_union(inside) if inside else Polygon()


def filled_shell(geom: BaseGeometry) -> BaseGeometry:
    """링(튜브벽 등)의 내부 구멍을 메운 영역."""
    if geom.is_empty:
        return geom
    polys = [geom] if geom.geom_type == "Polygon" else [g for g in geom.geoms if g.geom_type == "Polygon"]
    return unary_union([Polygon(p.exterior) for p in polys])


@dataclass
class Sections:
    model: Model
    heights: tuple[float, ...]
    _at: dict
    _footprints: dict
    _objects: dict

    def at(self, h: float) -> dict:
        return self._at[h]

    def footprint(self, name: str) -> BaseGeometry:
        return self._footprints[name]

    def obj(self, name: str) -> ModelObject:
        return self._objects[name]

    def kind(self, name: str):
        return self._objects[name].kind


def slice_model(model: Model, heights) -> Sections:
    heights = tuple(heights)
    at = {h: {} for h in heights}
    footprints = {}
    objects = {}
    for o in model.objects:
        if len(o.verts) == 0:
            continue
        objects[o.name] = o
        footprints[o.name] = section(o, o.zmid)
        for h in heights:
            if o.zmin - _EPS <= h <= o.zmax + _EPS:
                g = section(o, h)
                if not g.is_empty:
                    at[h][o.name] = g
    return Sections(model, heights, at, footprints, objects)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests\test_slicer.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit (사용자가 커밋을 요청한 경우에만)**

```bash
git add "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\extract\slicer.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_slicer.py"
git commit -m "feat(engine): add mesh slicer with hole-aware sections"
```

---

### Task 4: Blender 내보내기와 헤드리스 실행기

**Files:**
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\extract\blender_export.py`
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\extract\run_blender.py`
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\blender_make_cube.py`
- Test: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_blender_export.py`

**Interfaces:**
- Consumes: `extract.loader.load_model` (Task 2)
- Produces: `extract.run_blender.find_blender() -> Path | None`, `run_blender_script(blend, script, *args, timeout=300)`(`blend`가 `None`이면 파일 없이 실행), `export_model(blend, out_json) -> Path`
- 모델 JSON 스키마(Task 2의 `load_model`이 읽는 형식): `{"schema":1, "units":"m", "objects":[{"name","props","verts","tris"}]}`. 정점은 **월드 좌표(미터)** 이다. 기존 `.blend`는 객체 위치가 0이고 형상이 정점에 구워져 있어 `matrix_world` 적용이 필수다.

- [ ] **Step 1: 실패하는 테스트 작성 (Blender가 없으면 skip)**

```python
# FILE: tests/blender_make_cube.py
"""Blender 안에서 실행: blender -b --python blender_make_cube.py -- <out.blend>"""
import sys

import bpy

out_path = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(5.0, 5.0, 0.5))
obj = bpy.context.active_object
obj.name = "Col_test"
obj.scale = (0.9, 0.9, 1.0)
obj["kind"] = "column"
obj["name_ko"] = "기둥 시험"
bpy.ops.wm.save_as_mainfile(filepath=out_path)
```

```python
# FILE: tests/test_blender_export.py
from pathlib import Path

import numpy as np
import pytest

from extract.loader import load_model
from extract.run_blender import export_model, find_blender, run_blender_script

pytestmark = pytest.mark.skipif(find_blender() is None, reason="Blender 실행 파일을 찾을 수 없음")

MAKE_CUBE = Path(__file__).with_name("blender_make_cube.py")


def test_export_applies_world_matrix_and_keeps_tags(tmp_path):
    blend = tmp_path / "cube.blend"
    run_blender_script(None, MAKE_CUBE, blend)
    assert blend.exists()

    out = export_model(blend, tmp_path / "model.json")
    model = load_model(out)
    assert len(model.objects) == 1
    cube = model.objects[0]
    assert cube.name == "Col_test"
    assert cube.kind == "column"
    assert cube.name_ko == "기둥 시험"
    lo, hi = cube.verts.min(axis=0), cube.verts.max(axis=0)
    # location(5,5,0.5) + scale(0.9,0.9,1) 가 월드 좌표에 반영돼야 한다
    assert np.allclose(lo, [4.55, 4.55, 0.0], atol=1e-4)
    assert np.allclose(hi, [5.45, 5.45, 1.0], atol=1e-4)
    assert len(cube.tris) == 12


def test_run_blender_script_raises_on_python_error(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        run_blender_script(None, bad)
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests\test_blender_export.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'extract.run_blender'`)

- [ ] **Step 3: 구현**

```python
# FILE: extract/blender_export.py
"""Blender 안에서 실행: blender -b <file.blend> --python blender_export.py -- <out.json>

모든 MESH 객체를 월드 좌표(미터)로 내보낸다. 커스텀 속성(kind, name_ko 등)을 그대로 보존한다.
"""
import json
import sys

import bpy


def _simple_props(obj):
    out = {}
    for key in obj.keys():
        if key.startswith("_"):
            continue
        value = obj[key]
        if isinstance(value, (str, int, float, bool)):
            out[key] = value
    return out


def export(out_path):
    scale = bpy.context.scene.unit_settings.scale_length
    deps = bpy.context.evaluated_depsgraph_get()
    objects = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(deps)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            world = obj.matrix_world
            verts = [[c * scale for c in (world @ v.co)] for v in mesh.vertices]
            tris = [list(t.vertices) for t in mesh.loop_triangles]
        finally:
            evaluated.to_mesh_clear()
        objects.append({"name": obj.name, "props": _simple_props(obj), "verts": verts, "tris": tris})
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"schema": 1, "units": "m", "objects": objects}, fh, ensure_ascii=False)


if __name__ == "__main__":
    export(sys.argv[sys.argv.index("--") + 1])
```

```python
# FILE: extract/run_blender.py
from __future__ import annotations

import glob
import os
import subprocess
from pathlib import Path
from shutil import which

EXPORT_SCRIPT = Path(__file__).with_name("blender_export.py")


def find_blender() -> Path | None:
    candidates = []
    env = os.environ.get("BLENDER_EXE")
    if env:
        candidates.append(env)
    candidates += sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender *\blender.exe"), reverse=True)
    for c in candidates:
        if Path(c).exists():
            return Path(c)
    found = which("blender")
    return Path(found) if found else None


def run_blender_script(blend, script, *args, timeout: int = 300) -> subprocess.CompletedProcess:
    exe = find_blender()
    if exe is None:
        raise RuntimeError("Blender 실행 파일을 찾을 수 없습니다 (환경변수 BLENDER_EXE 설정)")
    cmd = [str(exe), "-b"]
    if blend is not None:
        cmd.append(str(blend))
    cmd += ["--python-exit-code", "1", "--python", str(script), "--", *map(str, args)]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Blender 실패({proc.returncode}):\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
    return proc


def export_model(blend, out_json) -> Path:
    out_json = Path(out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    if out_json.exists():
        out_json.unlink()
    run_blender_script(blend, EXPORT_SCRIPT, out_json)
    if not out_json.exists():
        raise RuntimeError("Blender가 모델 JSON을 만들지 못했습니다")
    return out_json
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests\test_blender_export.py -v`
Expected: 2 passed (Blender 헤드리스 2회 실행, 약 10~30초)

- [ ] **Step 5: Commit (사용자가 커밋을 요청한 경우에만)**

```bash
git add "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\extract\blender_export.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\extract\run_blender.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\blender_make_cube.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_blender_export.py"
git commit -m "feat(engine): add headless Blender exporter with world-matrix coordinates"
```

---

### Task 5: 기하 검사 G1·G2·G4·G5

**Files:**
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\checks\geometry.py`
- Test: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_geometry_checks.py`

**Interfaces:**
- Consumes: `Sections`, `filled_shell` (Task 3), `Violation`, `dedupe` (Task 2), `Params` (Task 1), `WALL_KINDS` (Task 2)
- Produces: `check_g1_columns(sections, params)`, `check_g2_fixtures(sections, params)`, `check_g4_zones(sections, params)`, `check_g5_walls(sections, params)` — 모두 `list[Violation]` 반환

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# FILE: tests/test_geometry_checks.py
from checks.geometry import check_g1_columns, check_g2_fixtures, check_g4_zones, check_g5_walls
from engine_params import load_params
from extract.slicer import slice_model
from model_fixtures import box_mesh, cylinder_mesh, mk, sample_model

P = load_params()


def _sections(model):
    return slice_model(model, P.check_heights_m)


def _all(model):
    s = _sections(model)
    return (
        check_g1_columns(s, P) + check_g2_fixtures(s, P) + check_g4_zones(s, P) + check_g5_walls(s, P)
    )


def test_clean_model_has_no_geometry_violations():
    assert _all(sample_model()) == []


def test_g1_column_inside_void():
    m = sample_model()
    m.objects.append(mk("Col_bad", "column", "기둥 오류", cylinder_mesh(14.5, 9.0, 0.45, 0, 4.5)))
    v = check_g1_columns(_sections(m), P)
    assert len(v) == 1 and v[0].check == "G1"
    assert set(v[0].objects) == {"Col_bad", "Void_Esc"}


def test_g1_column_inside_tube_interior():
    m = sample_model()
    m.objects.append(mk("Col_bad", "column", "기둥 오류", cylinder_mesh(9.0, 9.0, 0.45, 0, 4.5)))
    v = check_g1_columns(_sections(m), P)
    assert len(v) == 1 and "Tube_T1" in v[0].objects


def test_g1_catches_column_that_only_crosses_void_above_floor():
    # 바닥(0.3 m)에서는 닿지 않고 1.5 m 이상에서만 보이드를 지나가는 기둥도 잡아야 한다 (복수 높이 절단)
    m = sample_model()
    m.objects.append(mk("Col_high", "column", "높은 기둥", cylinder_mesh(14.5, 9.0, 0.45, 1.0, 4.5)))
    v = check_g1_columns(_sections(m), P)
    assert len(v) == 1 and "Col_high" in v[0].objects


def test_g2_fixture_too_close_to_column():
    m = sample_model()
    m.objects.append(mk("Bench_near", "fixture", "가까운 벤치", box_mesh(1.0, 1.0, 2.0, 1.5, 0, 0.45)))
    v = check_g2_fixtures(_sections(m), P)
    assert len(v) == 1 and v[0].check == "G2"
    assert "Bench_near" in v[0].objects and "Col_0_0" in v[0].objects


def test_g2_fixture_overlaps_tube_interior():
    m = sample_model()
    m.objects.append(mk("Tree_in_tube", "fixture", "수목 벤치", box_mesh(8.0, 7.0, 10.0, 8.5, 0, 0.5)))
    v = check_g2_fixtures(_sections(m), P)
    assert any("Tube_T1" in x.objects for x in v)


def test_g4_overlapping_zones():
    m = sample_model()
    m.objects.append(mk("Zone_Mid", "zone", "겹친 존", box_mesh(8, 0, 10, 18, 0, 0.05)))
    v = check_g4_zones(_sections(m), P)
    assert v and all(x.check == "G4" for x in v)
    assert any("겹침" in x.message for x in v)


def test_g4_uncovered_floor():
    m = sample_model()
    m.objects = [o for o in m.objects if o.name != "Zone_East"]
    v = check_g4_zones(_sections(m), P)
    assert any("덮지 못한" in x.message for x in v)


def test_g4_zone_outside_slab():
    m = sample_model()
    m.objects.append(mk("Zone_Out", "zone", "슬래브 밖", box_mesh(18, 0, 20, 4, 0, 0.05)))
    v = check_g4_zones(_sections(m), P)
    assert any("벗어남" in x.message for x in v)


def test_g4_zones_without_slab_is_a_violation():
    m = sample_model()
    m.objects = [o for o in m.objects if o.kind != "slab"]
    v = check_g4_zones(_sections(m), P)
    assert len(v) == 1 and "슬래브" in v[0].message


def test_g5_wall_off_grid_and_exemption():
    m = sample_model()
    m.objects.append(mk("Wall_off", "partition_wall", "어긋난 벽", box_mesh(1, 3.0, 8, 3.2, 0, 3)))
    v = check_g5_walls(_sections(m), P)
    assert len(v) == 1 and v[0].check == "G5" and "Wall_off" in v[0].objects

    m2 = sample_model()
    m2.objects.append(
        mk("Wall_ok", "partition_wall", "예외 벽", box_mesh(1, 3.0, 8, 3.2, 0, 3), grid_exempt=1)
    )
    assert check_g5_walls(_sections(m2), P) == []
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests\test_geometry_checks.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'checks.geometry'`)

- [ ] **Step 3: 구현**

```python
# FILE: checks/geometry.py
from __future__ import annotations

from shapely.ops import unary_union

from checks.base import Violation, dedupe
from extract.schema import WALL_KINDS
from extract.slicer import filled_shell

AREA_EPS = 1e-6
G1_BLOCKERS = ("void", "tube_wall", "shaft", "stair")
G2_BLOCKERS = ("void", "tube_wall", "shaft")


def _where(geom):
    c = geom.centroid
    return (round(c.x, 2), round(c.y, 2))


def _blocker(kind, geom):
    # 튜브벽은 링이지만 튜브 내부 전체가 기둥·기물 금지 영역이다
    return filled_shell(geom) if kind == "tube_wall" else geom


def check_g1_columns(sections, params) -> list[Violation]:
    """기둥이 보이드·튜브·승강로·계단을 어느 검사 높이에서든 관통하면 위반."""
    out = []
    for h in sections.heights:
        at = sections.at(h)
        columns = {n: g for n, g in at.items() if sections.kind(n) == "column"}
        for n_b, g_b in at.items():
            kind_b = sections.kind(n_b)
            if kind_b not in G1_BLOCKERS:
                continue
            blocker = _blocker(kind_b, g_b)
            for n_c, g_c in columns.items():
                inter = g_c.intersection(blocker)
                if inter.area > AREA_EPS:
                    out.append(Violation(
                        "G1",
                        f"기둥 '{n_c}'이(가) {kind_b} '{n_b}'을(를) 관통 (높이 {h} m, 겹침 {inter.area:.3f} ㎡)",
                        _where(inter), (n_c, n_b)))
    return dedupe(out)


def check_g2_fixtures(sections, params) -> list[Violation]:
    """기물은 기둥과 최소 이격을 지키고 보이드·튜브 내부·승강로에 들어가지 않아야 한다."""
    out = []
    for h in sections.heights:
        at = sections.at(h)
        for n_f, g_f in at.items():
            if sections.kind(n_f) != "fixture":
                continue
            for n_o, g_o in at.items():
                kind_o = sections.kind(n_o)
                if kind_o == "column":
                    d = g_f.distance(g_o)
                    if d < params.furniture_to_column_m:
                        out.append(Violation(
                            "G2",
                            f"기물 '{n_f}'과(와) 기둥 '{n_o}' 이격 {d:.2f} m < {params.furniture_to_column_m} m",
                            _where(g_f), (n_f, n_o)))
                elif kind_o in G2_BLOCKERS:
                    inter = g_f.intersection(_blocker(kind_o, g_o))
                    if inter.area > AREA_EPS:
                        out.append(Violation(
                            "G2",
                            f"기물 '{n_f}'이(가) {kind_o} '{n_o}'에 침범 (겹침 {inter.area:.3f} ㎡)",
                            _where(inter), (n_f, n_o)))
    return dedupe(out)


def check_g4_zones(sections, params) -> list[Violation]:
    out = []
    zones = {o.name: sections.footprint(o.name) for o in sections.model.by_kind("zone")}
    if not zones:
        return out
    names = list(zones)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            inter = zones[a].intersection(zones[b])
            if inter.area > params.zone_overlap_tolerance_m2:
                out.append(Violation("G4", f"구획존 '{a}'와 '{b}' 겹침 {inter.area:.2f} ㎡", _where(inter), (a, b)))
    slabs = [sections.footprint(o.name) for o in sections.model.by_kind("slab")]
    if not slabs:
        out.append(Violation("G4", "구획존이 있으나 바닥 슬래브(kind=slab)가 없음"))
        return out
    slab = unary_union(slabs)
    zone_union = unary_union(list(zones.values()))
    outside = zone_union.difference(slab)
    if outside.area > params.zone_overlap_tolerance_m2:
        out.append(Violation("G4", f"구획존이 바닥 슬래브 밖으로 {outside.area:.2f} ㎡ 벗어남", _where(outside)))
    uncovered = slab.difference(zone_union)
    if uncovered.area > params.zone_coverage_tolerance_ratio * slab.area:
        out.append(Violation(
            "G4",
            f"구획존이 덮지 못한 바닥 {uncovered.area:.2f} ㎡ ({uncovered.area / slab.area:.1%})",
            _where(uncovered)))
    return out


def check_g5_walls(sections, params) -> list[Violation]:
    """외벽·코어벽·구획벽의 중심선은 기둥 격자선 위에 있어야 한다(grid_exempt 태그로 예외 지정)."""
    out = []
    spacing = params.grid_spacing_m
    for name, geom in sections.at(params.plan_cut_height_m).items():
        obj = sections.obj(name)
        if obj.kind not in WALL_KINDS or obj.props.get("grid_exempt"):
            continue
        minx, miny, maxx, maxy = geom.bounds
        dx, dy = maxx - minx, maxy - miny
        if min(dx, dy) > 1.0:  # 두꺼운 매스형 벽은 중심선 개념이 아니므로 제외
            continue
        axis, center = ("y", (miny + maxy) / 2) if dy < dx else ("x", (minx + maxx) / 2)
        rem = center % spacing
        off = min(rem, spacing - rem)
        if off > params.grid_tolerance_m:
            out.append(Violation(
                "G5",
                f"벽 '{name}' 중심선 {axis}={center:.3f} m가 기둥 격자({spacing} m)에서 {off:.3f} m 벗어남",
                _where(geom), (name,)))
    return out
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests\test_geometry_checks.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit (사용자가 커밋을 요청한 경우에만)**

```bash
git add "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\checks\geometry.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_geometry_checks.py"
git commit -m "feat(engine): add geometry checks G1 G2 G4 G5 across multiple cut heights"
```

---

### Task 6: 라벨 배치 솔버

**Files:**
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\layout\labels.py`
- Test: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_labels.py`

**Interfaces:**
- Consumes: `render.style.TEXT_ROLES`, `FONT_FAMILY` (Task 1), `Params` (Task 1)
- Produces: `layout.labels.LabelPlacementError`, `Placement(lines, line_centers, box, leader)`, `LabelSolver(params, canvas: Polygon)` with `.place(region, lines, obstacles) -> Placement` (`lines`는 `[(text, role), ...]`)

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# FILE: tests/test_labels.py
import pytest
from shapely.geometry import Polygon, box

from engine_params import load_params
from layout.labels import LabelPlacementError, LabelSolver

P = load_params()
CANVAS = box(-10, -10, 40, 40)
EMPTY = Polygon()
LINES = [("시장 홀", "room"), ("162㎡", "sub")]


def test_label_goes_to_open_center_of_region():
    placement = LabelSolver(P, CANVAS).place(box(0, 0, 20, 20), LINES, EMPTY)
    cx, cy = placement.box.centroid.x, placement.box.centroid.y
    assert (cx, cy) == pytest.approx((10, 10), abs=0.6)
    assert placement.leader is None
    assert len(placement.line_centers) == 2
    assert placement.line_centers[0][1] > placement.line_centers[1][1]  # 첫 줄이 위


def test_label_avoids_obstacles():
    obstacle = box(8, 8, 12, 12)
    placement = LabelSolver(P, CANVAS).place(box(0, 0, 20, 20), LINES, obstacle)
    assert not placement.box.intersects(obstacle)
    assert box(0, 0, 20, 20).contains(placement.box)


def test_label_uses_leader_when_region_is_too_small():
    region = box(0, 0, 1.0, 1.0)
    placement = LabelSolver(P, CANVAS).place(region, LINES, EMPTY)
    assert placement.leader is not None
    assert not placement.box.intersects(region)


def test_labels_never_overlap_each_other():
    solver = LabelSolver(P, CANVAS)
    region = box(0, 0, 20, 20)
    first = solver.place(region, LINES, EMPTY)
    second = solver.place(region, [("공공보행통로", "room"), ("420㎡", "sub")], EMPTY)
    assert not first.box.intersects(second.box)


def test_no_space_raises():
    tiny = box(0, 0, 1, 1)
    with pytest.raises(LabelPlacementError):
        LabelSolver(P, tiny).place(tiny, LINES, EMPTY)
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests\test_labels.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'layout.labels'`)

- [ ] **Step 3: 구현**

```python
# FILE: layout/labels.py
from __future__ import annotations

from dataclasses import dataclass

from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from shapely.geometry import LineString, Polygon, box
from shapely.ops import nearest_points, polylabel, unary_union

from render.style import FONT_FAMILY, TEXT_ROLES

WIDTH_FACTOR = 1.1     # 글리프 잉크 폭 -> 실제 진행 폭 여유
HEIGHT_FACTOR = 1.4    # 글자 크기 -> 한 줄 높이(상·하 여백 포함)
LINE_GAP_PT = 1.0
LEADER_STEPS_M = (0.5, 1.5, 3.0, 5.0, 8.0)
SCAN_STEP_M = 0.5


def _scan(lo: float, hi: float, step: float = SCAN_STEP_M) -> list[float]:
    out, v = [], lo
    while v <= hi + 1e-9:
        out.append(v)
        v += step
    return out


class LabelPlacementError(RuntimeError):
    pass


@dataclass(frozen=True)
class Placement:
    lines: tuple
    line_centers: tuple
    box: Polygon
    leader: LineString | None


class LabelSolver:
    """영역 안의 빈 공간에 라벨을 계산 배치한다. 들어가지 않으면 지시선으로 밖에 낸다."""

    def __init__(self, params, canvas: Polygon):
        self.params = params
        self.canvas = canvas
        self.taken: list[Polygon] = []
        self.m_per_pt = 0.0254 / 72.0 * params.scale_denominator

    def _line_size(self, text: str, role: str):
        spec = TEXT_ROLES[role]
        prop = FontProperties(family=FONT_FAMILY, weight=spec.weight)
        ink = TextPath((0, 0), text, size=spec.size, prop=prop).get_extents()
        return ink.width * WIDTH_FACTOR * self.m_per_pt, spec.size * HEIGHT_FACTOR * self.m_per_pt

    def _block_size(self, lines):
        sizes = [self._line_size(t, r) for t, r in lines]
        gap = LINE_GAP_PT * self.m_per_pt
        width = max(s[0] for s in sizes)
        height = sum(s[1] for s in sizes) + gap * (len(sizes) - 1)
        return width, height, [s[1] for s in sizes], gap

    def _commit(self, lines, heights, gap, hit, leader):
        y_top = hit.centroid.y + (hit.bounds[3] - hit.bounds[1]) / 2 - self.params.label_pad_m
        cx = hit.centroid.x
        centers = []
        for lh in heights:
            centers.append((cx, y_top - lh / 2))
            y_top -= lh + gap
        self.taken.append(hit)
        return Placement(tuple(lines), tuple(centers), hit, leader)

    def place(self, region, lines, obstacles) -> Placement:
        width, height, heights, gap = self._block_size(lines)
        pad = self.params.label_pad_m
        half_w, half_h = width / 2 + pad, height / 2 + pad
        parts = [g for g in (obstacles, *self.taken) if g is not None and not g.is_empty]
        blocked = unary_union(parts) if parts else Polygon()
        inner = region.buffer(-0.1)

        def fits(cx, cy, need_inside):
            b = box(cx - half_w, cy - half_h, cx + half_w, cy + half_h)
            if not self.canvas.contains(b) or b.intersects(blocked):
                return None
            if need_inside and not inner.contains(b):
                return None
            return b

        if not inner.is_empty:
            poly = inner if inner.geom_type == "Polygon" else max(inner.geoms, key=lambda g: g.area)
            center = polylabel(poly, tolerance=0.05)
            hit = fits(center.x, center.y, True)
            if hit is None:
                minx, miny, maxx, maxy = inner.bounds
                step = 0.5 if inner.area < 400 else 1.0
                cands = []
                x = minx + half_w
                while x <= maxx - half_w:
                    y = miny + half_h
                    while y <= maxy - half_h:
                        cands.append((x, y))
                        y += step
                    x += step
                cands.sort(key=lambda p: (p[0] - center.x) ** 2 + (p[1] - center.y) ** 2)
                for cx, cy in cands:
                    hit = fits(cx, cy, True)
                    if hit is not None:
                        break
            if hit is not None:
                return self._commit(lines, heights, gap, hit, None)

        rep = region.representative_point()
        minx, miny, maxx, maxy = region.bounds
        mx, my = (minx + maxx) / 2, (miny + maxy) / 2
        cx_lo, cy_lo, cx_hi, cy_hi = self.canvas.bounds
        xs = _scan(cx_lo + half_w, cx_hi - half_w)
        ys = _scan(cy_lo + half_h, cy_hi - half_h)
        for step in LEADER_STEPS_M:
            # 영역 바깥 네 변을 따라 후보를 훑고, 영역 중심에 가까운 순서로 시도한다
            ring = (
                [(x, maxy + half_h + step) for x in xs] + [(x, miny - half_h - step) for x in xs]
                + [(maxx + half_w + step, y) for y in ys] + [(minx - half_w - step, y) for y in ys]
            )
            ring.sort(key=lambda p: (p[0] - mx) ** 2 + (p[1] - my) ** 2)
            for cx, cy in ring:
                hit = fits(cx, cy, False)
                if hit is not None:
                    leader = LineString([(rep.x, rep.y), nearest_points(hit, rep)[0].coords[0]])
                    return self._commit(lines, heights, gap, hit, leader)
        raise LabelPlacementError(f"라벨 '{lines[0][0]}'를 배치할 빈 공간이 없습니다")
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests\test_labels.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit (사용자가 커밋을 요청한 경우에만)**

```bash
git add "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\layout" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_labels.py"
git commit -m "feat(engine): add label placement solver with leader fallback"
```

---

### Task 7: 벡터 평면 렌더러

**Files:**
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\render\plan_renderer.py`
- Test: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_render.py`

**Interfaces:**
- Consumes: `Sections`, `filled_shell` (Task 3), `LabelSolver`, `LabelPlacementError` (Task 6), `LINE_CLASSES`, `TEXT_ROLES`, `KIND_STYLE`, `FONT_FAMILY` (Task 1), `Params`
- Produces: `render.plan_renderer.render_plan(sections, params, out_png) -> RenderResult`
- Produces: `TextRecord(owner, text, role, size, bbox)`, `LineRecord(owner, klass, lw, geom, filled=False, leader=False)`, `RenderResult(png_path, texts, lines, canvas)` — `bbox`·`canvas`는 모델 좌표(m)의 `(minx, miny, maxx, maxy)`. `size`와 `lw`는 **그려진 아티스트에서 읽어 온 값**이다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# FILE: tests/test_render.py
from engine_params import load_params
from extract.slicer import slice_model
from model_fixtures import sample_model
from render.plan_renderer import render_plan

P = load_params()


def _render(tmp_path):
    sections = slice_model(sample_model(), P.check_heights_m)
    return render_plan(sections, P, tmp_path / "plan.png")


def test_render_writes_png_and_records(tmp_path):
    res = _render(tmp_path)
    assert res.png_path.exists() and res.png_path.stat().st_size > 5000
    assert res.canvas[2] > res.canvas[0] and res.canvas[3] > res.canvas[1]
    assert any(l.klass == "cut_heavy" for l in res.lines)
    assert any(l.klass == "grid" for l in res.lines)


def test_zone_labels_carry_computed_areas(tmp_path):
    res = _render(tmp_path)
    texts = [t.text for t in res.texts]
    assert "공공보행통로" in texts and "시장 홀" in texts
    assert texts.count("162㎡") >= 2  # 두 구획존 모두 폴리곤 면적(9 x 18)에서 계산된 값


def test_void_label_too_big_for_void_uses_leader(tmp_path):
    res = _render(tmp_path)
    assert any(l.leader and l.owner == "Void_Esc" for l in res.lines)
    assert any(t.text == "에스컬 보이드" for t in res.texts)


def test_no_label_straddles_the_zone_boundary_line(tmp_path):
    """튜브가 구획존 경계(x=9)에 걸쳐 있어도 어떤 라벨도 그 선을 가로지르지 않는다 (솔버가 존 윤곽을 장애물로 취급)."""
    res = _render(tmp_path)
    for t in res.texts:
        x0, _y0, x1, _y1 = t.bbox
        assert not (x0 < 9.0 < x1), f"'{t.text}' 가 x=9 경계선을 가로지름"


def test_recorded_styles_come_from_the_drawn_artists(tmp_path):
    res = _render(tmp_path)
    by_role = {t.role: t.size for t in res.texts}
    assert by_role["room"] == 8.0 and by_role["sub"] == 6.25
    heavy = [l.lw for l in res.lines if l.klass == "cut_heavy"]
    assert heavy and all(abs(w - 1.7) < 1e-6 for w in heavy)
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests\test_render.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'render.plan_renderer'`)

- [ ] **Step 3: 구현**

```python
# FILE: render/plan_renderer.py
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import PathPatch  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402
from shapely.geometry import LineString, box  # noqa: E402
from shapely.geometry.base import BaseGeometry  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from extract.slicer import filled_shell  # noqa: E402
from layout.labels import LabelSolver  # noqa: E402
from render.style import FONT_FAMILY, KIND_STYLE, LINE_CLASSES, TEXT_ROLES  # noqa: E402

LABELED_KINDS = ("zone", "tube_wall", "void", "shaft")
INTERIOR_OBSTACLE_KINDS = ("tube_wall", "void", "shaft")
Z_ORDER = {"zone": 1.0, "void": 1.5, "shaft": 2.0, "stair": 2.0, "tube_wall": 3.0, "partition_wall": 3.0,
           "exterior_wall": 3.0, "core_wall": 3.0, "fixture": 4.0, "column": 5.0}


@dataclass
class TextRecord:
    owner: str
    text: str
    role: str
    size: float
    bbox: tuple


@dataclass
class LineRecord:
    owner: str
    klass: str
    lw: float
    geom: BaseGeometry
    filled: bool = False
    leader: bool = False


@dataclass
class RenderResult:
    png_path: Path
    texts: list
    lines: list
    canvas: tuple


def _polys(geom):
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    return [g for g in geom.geoms if g.geom_type == "Polygon"]


def _path_for(poly):
    verts, codes = [], []
    for ring in [poly.exterior, *poly.interiors]:
        pts = list(ring.coords)
        verts += pts
        codes += [MplPath.MOVETO] + [MplPath.LINETO] * (len(pts) - 2) + [MplPath.CLOSEPOLY]
    return MplPath(verts, codes)


def render_plan(sections, params, out_png) -> RenderResult:
    model = sections.model
    cut = params.plan_cut_height_m

    drawn = []
    for o in model.objects:
        style = KIND_STYLE.get(o.kind)
        if style is None or len(o.verts) == 0:
            continue
        geom = sections.at(cut).get(o.name) if o.zmin <= cut <= o.zmax else None
        if geom is None or geom.is_empty:
            geom = sections.footprint(o.name)  # 절단면 위/아래 요소는 투영(바닥 윤곽)으로 그린다
        if geom.is_empty:
            continue
        drawn.append((o, geom, style[0], style[1]))
    if not drawn:
        raise ValueError("그릴 객체가 없습니다")

    content = unary_union([g for _, g, _, _ in drawn])
    m = params.margin_m
    x0, y0, x1, y1 = content.bounds
    canvas = (x0 - m, y0 - m, x1 + m, y1 + m)

    inch_per_m = 1.0 / (params.scale_denominator * 0.0254)
    fig = plt.figure(
        figsize=((canvas[2] - canvas[0]) * inch_per_m, (canvas[3] - canvas[1]) * inch_per_m),
        dpi=params.dpi, facecolor="white",
    )
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(canvas[0], canvas[2])
    ax.set_ylim(canvas[1], canvas[3])
    ax.set_aspect("equal")
    ax.axis("off")

    artists = []  # (artist, LineRecord)

    def add_polygon(owner, geom, klass, fill, zorder):
        spec = LINE_CLASSES[klass]
        for poly in _polys(geom):
            patch = PathPatch(
                _path_for(poly), facecolor=fill or "none", edgecolor=spec.color,
                linewidth=spec.lw, linestyle=spec.linestyle, zorder=zorder,
            )
            ax.add_patch(patch)
            artists.append((patch, LineRecord(owner, klass, spec.lw, poly, filled=fill is not None)))

    def add_line(owner, geom, klass, zorder, leader=False):
        spec = LINE_CLASSES[klass]
        xs, ys = geom.xy
        (line,) = ax.plot(list(xs), list(ys), color=spec.color, linewidth=spec.lw,
                          linestyle=spec.linestyle, zorder=zorder, solid_capstyle="butt")
        artists.append((line, LineRecord(owner, klass, spec.lw, geom, leader=leader)))

    # 구조 격자
    sp = params.grid_spacing_m
    for k in range(math.ceil((x0 - 1e-6) / sp), math.floor((x1 + 1e-6) / sp) + 1):
        add_line("grid", LineString([(k * sp, y0 - 1), (k * sp, y1 + 1)]), "grid", 0.5)
    for k in range(math.ceil((y0 - 1e-6) / sp), math.floor((y1 + 1e-6) / sp) + 1):
        add_line("grid", LineString([(x0 - 1, k * sp), (x1 + 1, k * sp)]), "grid", 0.5)

    for o, geom, klass, fill in drawn:
        add_polygon(o.name, geom, klass, fill, Z_ORDER.get(o.kind, 2.0))

    # 라벨: 장애물 = 그려진 선(채움은 면, 윤곽은 가는 띠)
    line_obs, interior_obs = [], []
    for o, geom, klass, fill in drawn:
        if o.kind == "zone":
            continue
        line_obs.append(geom if fill is not None else geom.boundary.buffer(0.05))
        if o.kind in INTERIOR_OBSTACLE_KINDS:
            interior_obs.append(filled_shell(geom))
    # 구획존 윤곽선도 장애물이다. 튜브·보이드 라벨이 존 경계선을 가로지르면 T2 위반이 된다.
    zone_outlines = [geom.boundary.buffer(0.05) for o, geom, _k, _f in drawn if o.kind == "zone"]
    line_obstacle = unary_union(line_obs + zone_outlines)
    zone_obstacle = unary_union(line_obs + zone_outlines + interior_obs)

    solver = LabelSolver(params, box(*canvas))
    label_items = []  # (owner, placement)
    ordered = [d for d in drawn if d[0].kind == "zone"] + [d for d in drawn if d[0].kind != "zone"]
    for o, geom, klass, fill in ordered:
        if o.kind not in LABELED_KINDS:
            continue
        if o.kind == "zone":
            region, obstacles, area = geom, zone_obstacle, geom.area
        else:
            shell = filled_shell(geom)
            region = shell.buffer(-params.label_gap_m)
            region = region if not region.is_empty else shell
            obstacles, area = line_obstacle, shell.area
        role = o.props.get("label_role", "room")
        lines = [(str(o.name_ko), role), (f"{area:,.0f}㎡", "sub")]
        label_items.append((o.name, solver.place(region, lines, obstacles)))

    text_artists = []
    for owner, placement in label_items:
        if placement.leader is not None:
            add_line(owner, placement.leader, "detail", 9.0, leader=True)
        for (text, role), (cx, cy) in zip(placement.lines, placement.line_centers):
            spec = TEXT_ROLES[role]
            artist = ax.text(
                cx, cy, text, ha="center", va="center", fontsize=spec.size, fontweight=spec.weight,
                color=spec.color, fontfamily=FONT_FAMILY, zorder=10,
                bbox=dict(boxstyle="square,pad=0.2", facecolor="white", edgecolor="none"),
            )
            text_artists.append((artist, owner, text, role))

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    texts = []
    for artist, owner, text, role in text_artists:
        bb = artist.get_window_extent(renderer)
        (bx0, by0), (bx1, by1) = inv.transform([[bb.x0, bb.y0], [bb.x1, bb.y1]])
        texts.append(TextRecord(owner, text, role, float(artist.get_fontsize()), (bx0, by0, bx1, by1)))
    lines = []
    for artist, rec in artists:
        rec.lw = float(artist.get_linewidth())  # 의도한 값이 아니라 실제 아티스트에서 읽는다
        lines.append(rec)

    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=params.dpi, facecolor="white")
    plt.close(fig)
    return RenderResult(out_png, texts, lines, canvas)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests\test_render.py -v`
Expected: 5 passed. 생성된 PNG가 보고 싶으면 테스트의 `tmp_path` 대신 임시 경로를 지정해 직접 열어 본다.

- [ ] **Step 5: Commit (사용자가 커밋을 요청한 경우에만)**

```bash
git add "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\render\plan_renderer.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_render.py"
git commit -m "feat(engine): add vector plan renderer reading styles back from artists"
```

---

### Task 8: 텍스트·스타일 검사 T1~T4

**Files:**
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\checks\text.py`
- Test: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_text_checks.py`

**Interfaces:**
- Consumes: `RenderResult`, `TextRecord`, `LineRecord` (Task 7), `LINE_CLASSES`, `TEXT_ROLES` (Task 1), `Violation`, `dedupe` (Task 2)
- Produces: `check_t1_text_overlap(render, params)`, `check_t2_text_on_line(render, params)`, `check_t3_canvas(render, params)`, `check_t4_style(render, params)` — `list[Violation]`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# FILE: tests/test_text_checks.py
from pathlib import Path

from shapely.geometry import box

from checks.text import check_t1_text_overlap, check_t2_text_on_line, check_t3_canvas, check_t4_style
from engine_params import load_params
from extract.slicer import slice_model
from model_fixtures import sample_model
from render.plan_renderer import LineRecord, RenderResult, TextRecord, render_plan

P = load_params()


def _text(owner, text, bbox, role="room", size=8.0):
    return TextRecord(owner, text, role, size, bbox)


def _render(texts=(), lines=(), canvas=(0, 0, 20, 20)):
    return RenderResult(Path("x.png"), list(texts), list(lines), canvas)


def test_real_render_of_clean_model_passes_all_text_checks(tmp_path):
    """솔버가 만든 배치를 독립 검사기가 다시 검증한다 (구성 시 검증 + 사후 검증)."""
    res = render_plan(slice_model(sample_model(), P.check_heights_m), P, tmp_path / "plan.png")
    assert check_t1_text_overlap(res, P) == []
    assert check_t2_text_on_line(res, P) == []
    assert check_t3_canvas(res, P) == []
    assert check_t4_style(res, P) == []


def test_t1_detects_overlapping_texts():
    r = _render(texts=[_text("a", "남성", (2, 2, 6, 4)), _text("b", "장애인", (5, 3, 9, 5))])
    v = check_t1_text_overlap(r, P)
    assert len(v) == 1 and v[0].check == "T1"


def test_t1_allows_touching_but_not_overlapping_texts():
    r = _render(texts=[_text("a", "가", (2, 2, 6, 4)), _text("b", "나", (6, 2, 9, 4))])
    assert check_t1_text_overlap(r, P) == []


def test_t2_detects_text_on_wall_but_not_on_grid_or_own_leader():
    wall = LineRecord("Wall", "cut_heavy", 1.7, box(0, 0, 10, 0.35), filled=True)
    grid = LineRecord("grid", "grid", 0.4, box(0, 0, 0, 0).union(box(4, 0, 4.01, 10)), filled=True)
    own_leader = LineRecord("lab", "detail", 0.38, box(2, 1, 2.1, 8), filled=True, leader=True)
    text = _text("lab", "라벨", (2, 0.1, 5, 1.0))
    v = check_t2_text_on_line(_render(texts=[text], lines=[wall]), P)
    assert len(v) == 1 and v[0].check == "T2"
    assert check_t2_text_on_line(_render(texts=[text], lines=[grid, own_leader]), P) == []


def test_t2_unfilled_polygon_is_checked_by_its_outline_only():
    outline = LineRecord("Zone", "detail", 0.38, box(0, 0, 10, 10), filled=False)
    inside = _text("lab", "안쪽", (3, 3, 6, 5))
    on_edge = _text("lab", "경계", (-1, 4, 2, 6))
    assert check_t2_text_on_line(_render(texts=[inside], lines=[outline]), P) == []
    assert len(check_t2_text_on_line(_render(texts=[on_edge], lines=[outline]), P)) == 1


def test_t3_detects_text_outside_canvas():
    r = _render(texts=[_text("legend", "범례", (18, 5, 22, 6))])
    v = check_t3_canvas(r, P)
    assert len(v) == 1 and v[0].check == "T3"


def test_t4_detects_off_table_sizes_and_widths():
    bad_text = _text("a", "큰글씨", (1, 1, 2, 2), role="room", size=10.0)
    bad_line = LineRecord("Wall", "cut_heavy", 2.5, box(0, 0, 1, 1), filled=True)
    v = check_t4_style(_render(texts=[bad_text], lines=[bad_line]), P)
    assert {x.check for x in v} == {"T4"} and len(v) == 2
    ok_text = _text("a", "정상", (1, 1, 2, 2), role="room", size=8.0)
    ok_line = LineRecord("Wall", "cut_heavy", 1.7, box(0, 0, 1, 1), filled=True)
    assert check_t4_style(_render(texts=[ok_text], lines=[ok_line]), P) == []
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests\test_text_checks.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'checks.text'`)

- [ ] **Step 3: 구현**

```python
# FILE: checks/text.py
from __future__ import annotations

from shapely.geometry import box

from checks.base import Violation, dedupe
from render.style import LINE_CLASSES, TEXT_ROLES

EPS = 1e-6


def _text_box(t):
    return box(*t.bbox)


def _drawn_geometry(rec):
    # 채움 도형은 면 전체, 윤곽만 그린 도형은 경계선, 선은 그대로
    if rec.filled or rec.geom.geom_type in ("LineString", "MultiLineString"):
        return rec.geom
    return rec.geom.boundary


def _where(geom):
    c = geom.centroid
    return (round(c.x, 2), round(c.y, 2))


def check_t1_text_overlap(render, params) -> list[Violation]:
    out = []
    texts = render.texts
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            a, b = texts[i], texts[j]
            inter = _text_box(a).intersection(_text_box(b))
            if inter.area > params.text_collision_tolerance_m2:
                out.append(Violation(
                    "T1", f"텍스트 '{a.text}'와 '{b.text}' 겹침 ({inter.area:.2f} ㎡)",
                    _where(inter), (f"{a.owner}:{a.text}", f"{b.owner}:{b.text}")))
    return dedupe(out)


def check_t2_text_on_line(render, params) -> list[Violation]:
    """텍스트가 선(벽·기둥·계단·호·윤곽·치수선) 위에 얹히면 위반. 구조 격자는 흰 배경 박스로 가려지므로 제외."""
    out = []
    for t in render.texts:
        tb = _text_box(t)
        for rec in render.lines:
            if rec.klass == "grid":
                continue
            if rec.leader and rec.owner == t.owner:
                continue
            geom = _drawn_geometry(rec)
            if tb.intersects(geom):
                out.append(Violation(
                    "T2", f"텍스트 '{t.text}'가 {rec.klass} 선('{rec.owner}')과 겹침",
                    _where(tb.intersection(geom)), (f"{t.owner}:{t.text}", rec.owner)))
    return dedupe(out)


def check_t3_canvas(render, params) -> list[Violation]:
    out = []
    cx0, cy0, cx1, cy1 = render.canvas
    for t in render.texts:
        x0, y0, x1, y1 = t.bbox
        if x0 < cx0 - EPS or y0 < cy0 - EPS or x1 > cx1 + EPS or y1 > cy1 + EPS:
            out.append(Violation(
                "T3", f"텍스트 '{t.text}'가 캔버스 밖으로 잘림", (round((x0 + x1) / 2, 2), round((y0 + y1) / 2, 2)),
                (f"{t.owner}:{t.text}",)))
    return out


def check_t4_style(render, params) -> list[Violation]:
    out = []
    for t in render.texts:
        spec = TEXT_ROLES.get(t.role)
        if spec is None:
            out.append(Violation("T4", f"알 수 없는 텍스트 위계 '{t.role}'", None, (f"{t.owner}:{t.text}",)))
        elif not (spec.size_min - EPS <= t.size <= spec.size_max + EPS):
            out.append(Violation(
                "T4", f"텍스트 '{t.text}' 크기 {t.size} pt가 {t.role} 범위 {spec.size_min}~{spec.size_max} pt를 벗어남",
                None, (f"{t.owner}:{t.text}",)))
    for rec in render.lines:
        spec = LINE_CLASSES.get(rec.klass)
        if spec is None:
            out.append(Violation("T4", f"알 수 없는 선종 '{rec.klass}'", None, (rec.owner,)))
        elif not (spec.lw_min - EPS <= rec.lw <= spec.lw_max + EPS):
            out.append(Violation(
                "T4", f"'{rec.owner}' 선 두께 {rec.lw}가 {rec.klass} 범위 {spec.lw_min}~{spec.lw_max}를 벗어남",
                None, (rec.owner, rec.klass)))
    return dedupe(out)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests\test_text_checks.py -v`
Expected: 7 passed. 첫 테스트가 솔버·렌더러·검사기의 일치를 보증한다.

- [ ] **Step 5: Commit (사용자가 커밋을 요청한 경우에만)**

```bash
git add "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\checks\text.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_text_checks.py"
git commit -m "feat(engine): add independent text and style checks T1-T4"
```

---

### Task 9: 검사 등록부와 결함 장부

**Files:**
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\checks\registry.py`
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\ledger\ledger.yaml`
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\ledger\ledger.py`
- Test: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_regression.py`
- Test: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_ledger.py`

**Interfaces:**
- Consumes: Task 5·8의 모든 검사 함수
- Produces: `checks.registry.CHECK_IDS: frozenset[str]` (= `TAG, LAYOUT, G1, G2, G4, G5, T1, T2, T3, T4`), `MODEL_CHECKS`, `RENDER_CHECKS` (id → 함수), `run_model_checks(sections, params)`, `run_render_checks(render, params)`
- Produces: `ledger.ledger.load_ledger(path=None) -> list[dict]`, `audit_ledger(defects, registered_ids) -> list[str]` (문제 목록, 빈 리스트면 정상)
- 장부 규칙: `checks`에 적힌 검사는 모두 등록돼 있어야 하고, `planned_checks`에 적힌 검사는 **아직 등록되지 않아야** 한다(구현되면 `checks`로 옮겨야 하므로 장부가 낡지 않는다). `checks`가 있으면 `regression_test`가 `test_regression.py`에 실제로 존재해야 한다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# FILE: tests/test_regression.py
"""사용자가 지적한 결함(결함 장부)의 회귀 검사. 각 함수 이름은 ledger.yaml의 regression_test와 일치해야 한다."""
from pathlib import Path

from shapely.geometry import box

from checks.geometry import check_g1_columns, check_g2_fixtures
from checks.text import check_t1_text_overlap, check_t2_text_on_line, check_t3_canvas
from engine_params import load_params
from extract.slicer import slice_model
from model_fixtures import box_mesh, cylinder_mesh, mk, sample_model
from render.plan_renderer import LineRecord, RenderResult, TextRecord

P = load_params()


def _ids(violations):
    return {v.check for v in violations}


def _sections(model):
    return slice_model(model, P.check_heights_m)


def _render(texts=(), lines=(), canvas=(0, 0, 20, 20)):
    return RenderResult(Path("x.png"), list(texts), list(lines), canvas)


def _text(owner, text, bbox):
    return TextRecord(owner, text, "room", 8.0, bbox)


def test_d001_tree_bench_encroaches_on_elevator_tube():
    m = sample_model()
    m.objects.append(mk("Tree_T4", "fixture", "수목 벤치", box_mesh(8.0, 7.0, 10.0, 8.5, 0, 0.5)))
    assert "G2" in _ids(check_g2_fixtures(_sections(m), P))


def test_d002_column_passes_through_void_escalator():
    m = sample_model()
    m.objects.append(mk("Col_bad", "column", "기둥 오류", cylinder_mesh(14.5, 9.0, 0.45, 0, 4.5)))
    assert "G1" in _ids(check_g1_columns(_sections(m), P))


def test_d003_furniture_overlaps_column():
    m = sample_model()
    m.objects.append(mk("Stand_bad", "fixture", "가판대", box_mesh(-0.2, -0.2, 0.9, 0.9, 0, 0.9)))
    assert "G2" in _ids(check_g2_fixtures(_sections(m), P))


def test_d004_title_box_covers_furniture():
    fixture = LineRecord("Showcase", "projection_light", 0.55, box(5, 3, 7, 6), filled=False)
    title = _text("title", "시장 홀 (마켓 플라자)", (4, 4, 8, 5))
    assert "T2" in _ids(check_t2_text_on_line(_render(texts=[title], lines=[fixture]), P))


def test_d005_restroom_labels_overlap_each_other():
    r = _render(texts=[_text("m", "남성 화장실", (2, 2, 7, 3.5)), _text("u", "장애인 다목적", (4, 3, 9, 4.5))])
    assert "T1" in _ids(check_t1_text_overlap(r, P))


def test_d006_legend_text_is_clipped_by_canvas():
    r = _render(texts=[_text("legend", "구조 기둥 Ø0.9m (RC Column)", (14, 18, 24, 19))])
    assert "T3" in _ids(check_t3_canvas(r, P))


def test_d007_overall_dimension_hidden_by_caption():
    r = _render(texts=[_text("dim", "54,000", (8, 2, 12, 3)), _text("caption", "남측 썬큰 광장", (7, 2.5, 13, 3.8))])
    assert "T1" in _ids(check_t1_text_overlap(r, P))


def test_d009_text_collides_with_line_in_approved_single_line_plan():
    wall = LineRecord("Wall", "cut_heavy", 1.7, box(0, 0, 10, 0.35), filled=True)
    r = _render(texts=[_text("atrium", "필로티 보이드 아트리움", (2, 0.1, 8, 1.0))], lines=[wall])
    assert "T2" in _ids(check_t2_text_on_line(r, P))
```

```python
# FILE: tests/test_ledger.py
import test_regression
from checks.registry import CHECK_IDS, MODEL_CHECKS, RENDER_CHECKS
from ledger.ledger import audit_ledger, load_ledger


def test_registry_ids_are_complete():
    assert CHECK_IDS == {"TAG", "LAYOUT", "G1", "G2", "G4", "G5", "T1", "T2", "T3", "T4"}
    assert set(MODEL_CHECKS) == {"G1", "G2", "G4", "G5"}
    assert set(RENDER_CHECKS) == {"T1", "T2", "T3", "T4"}


def test_project_ledger_is_consistent_with_registry():
    assert audit_ledger(load_ledger(), CHECK_IDS) == []


def test_every_active_defect_has_an_existing_regression_test():
    for d in load_ledger():
        if d.get("checks"):
            assert d.get("regression_test"), f"{d['id']}: regression_test 없음"
            assert hasattr(test_regression, d["regression_test"]), f"{d['id']}: {d['regression_test']} 없음"


def test_audit_detects_stale_and_missing_entries():
    defects = [
        {"id": "X-1", "title": "a", "checks": ["G9"], "planned_checks": []},
        {"id": "X-2", "title": "b", "checks": [], "planned_checks": ["G1"]},
        {"id": "X-3", "title": "c", "checks": [], "planned_checks": []},
        {"id": "X-3", "title": "dup", "checks": ["G1"], "planned_checks": []},
    ]
    problems = " | ".join(audit_ledger(defects, CHECK_IDS))
    assert "G9" in problems and "이미 구현" in problems and "연결된 검사가 없음" in problems and "중복" in problems
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests\test_ledger.py tests\test_regression.py -v`
Expected: `test_regression.py`는 PASS(이미 있는 검사 사용), `test_ledger.py`는 FAIL (`ModuleNotFoundError: No module named 'checks.registry'`)

- [ ] **Step 3: 구현**

```python
# FILE: checks/registry.py
from __future__ import annotations

from checks.geometry import check_g1_columns, check_g2_fixtures, check_g4_zones, check_g5_walls
from checks.text import check_t1_text_overlap, check_t2_text_on_line, check_t3_canvas, check_t4_style

MODEL_CHECKS = {
    "G1": check_g1_columns,
    "G2": check_g2_fixtures,
    "G4": check_g4_zones,
    "G5": check_g5_walls,
}
RENDER_CHECKS = {
    "T1": check_t1_text_overlap,
    "T2": check_t2_text_on_line,
    "T3": check_t3_canvas,
    "T4": check_t4_style,
}
# TAG(태그 게이트)와 LAYOUT(라벨 배치 실패)은 build.py가 직접 생성한다
CHECK_IDS = frozenset({"TAG", "LAYOUT", *MODEL_CHECKS, *RENDER_CHECKS})


def run_model_checks(sections, params):
    out = []
    for fn in MODEL_CHECKS.values():
        out += fn(sections, params)
    return out


def run_render_checks(render, params):
    out = []
    for fn in RENDER_CHECKS.values():
        out += fn(render, params)
    return out
```

```yaml
# FILE: ledger/ledger.yaml
# 결함 장부. 사용자가 새 오류를 지적하면 (1) 여기에 등록 (2) 전용 검사 추가 (3) AGENTS.md·GEMINI.md 갱신.
# checks: 구현·등록된 검사 / planned_checks: 아직 구현되지 않은 검사(구현되면 checks로 옮긴다)
defects:
  - id: D-001
    title: "T4 승강기 튜브에 수목·벤치가 침범"
    checks: [G2]
    planned_checks: []
    regression_test: test_d001_tree_bench_encroaches_on_elevator_tube
  - id: D-002
    title: "보이드 에스컬레이터를 구조 기둥이 관통"
    checks: [G1]
    planned_checks: []
    regression_test: test_d002_column_passes_through_void_escalator
  - id: D-003
    title: "시장 홀 가구가 기둥과 겹침"
    checks: [G2]
    planned_checks: []
    regression_test: test_d003_furniture_overlaps_column
  - id: D-004
    title: "대형 표제 상자가 가구를 덮음"
    checks: [T2]
    planned_checks: []
    regression_test: test_d004_title_box_covers_furniture
  - id: D-005
    title: "화장실 진입구 차폐, 글자 중첩"
    checks: [T1]
    planned_checks: [G3, R1]
    regression_test: test_d005_restroom_labels_overlap_each_other
  - id: D-006
    title: "범례 문구 잘림"
    checks: [T3]
    planned_checks: []
    regression_test: test_d006_legend_text_is_clipped_by_canvas
  - id: D-007
    title: "하단 전체 치수가 다른 문구에 가림"
    checks: [T1]
    planned_checks: []
    regression_test: test_d007_overall_dimension_hidden_by_caption
  - id: D-008
    title: "AI 인필에서 T2 샤프트 소실(구조 변조)"
    checks: []
    planned_checks: [P1, C1]
    regression_test: null
  - id: D-009
    title: "승인본 단선도의 텍스트-선 충돌"
    checks: [T2]
    planned_checks: []
    regression_test: test_d009_text_collides_with_line_in_approved_single_line_plan
```

```python
# FILE: ledger/ledger.py
from __future__ import annotations

from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).with_name("ledger.yaml")


def load_ledger(path=None) -> list[dict]:
    raw = yaml.safe_load(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"))
    return list(raw["defects"])


def audit_ledger(defects, registered_ids) -> list[str]:
    problems, seen = [], set()
    for d in defects:
        did = d.get("id", "?")
        if did in seen:
            problems.append(f"{did}: 장부 번호 중복")
        seen.add(did)
        checks, planned = d.get("checks") or [], d.get("planned_checks") or []
        if not checks and not planned:
            problems.append(f"{did}: 연결된 검사가 없음")
        for c in checks:
            if c not in registered_ids:
                problems.append(f"{did}: 검사 {c}가 등록되지 않음")
        for c in planned:
            if c in registered_ids:
                problems.append(f"{did}: 검사 {c}는 이미 구현됨 — planned_checks에서 checks로 옮길 것")
    return problems
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests\test_ledger.py tests\test_regression.py -v`
Expected: 12 passed (회귀 8 + 장부 4)

- [ ] **Step 5: Commit (사용자가 커밋을 요청한 경우에만)**

```bash
git add "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\checks\registry.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\ledger" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_regression.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_ledger.py"
git commit -m "feat(engine): add check registry and defect ledger with regression tests"
```

---

### Task 10: 단일 진입점 `build.py` (통과본만 내보내기)

**Files:**
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\build.py`
- Test: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_build.py`

**Interfaces:**
- Consumes: `load_model`, `check_tags`, `slice_model`, `run_model_checks`, `run_render_checks`, `render_plan`, `LabelPlacementError`, `export_model`, `load_params`
- Produces: `build.build(model_json, out_dir, rejected_dir, name, params=None) -> BuildReport(ok, violations, png_path, report_path, checks_run)`; CLI `python build.py (--blend FILE | --model-json FILE) [--out DIR] [--rejected DIR] [--name NAME]`, 종료 코드 0=통과, 1=거부
- 동작: TAG 위반이 있으면 **렌더하지 않고** 보고서만 `rejected_dir`에 쓴다. 그 외에는 임시 폴더에 렌더한 뒤 위반 0건이면 `out_dir`, 1건 이상이면 `rejected_dir`로 PNG와 `<name>.report.json`을 옮긴다. `02_최종결과물`에는 절대 쓰지 않는다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# FILE: tests/test_build.py
import json

from build import build
from extract.schema import ModelObject
from model_fixtures import box_mesh, cylinder_mesh, mk, sample_model, write_model_json


def _report(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_clean_model_is_exported_to_out_dir_only(tmp_path):
    model_json = write_model_json(sample_model(), tmp_path / "model.json")
    out, rej = tmp_path / "out", tmp_path / "rej"
    r = build(model_json, out, rej, "plan")
    assert r.ok and r.violations == []
    assert (out / "plan.png").exists() and (out / "plan.report.json").exists()
    assert not rej.exists() or not any(rej.iterdir())
    data = _report(out / "plan.report.json")
    assert data["ok"] is True
    assert {"TAG", "G1", "G2", "G4", "G5", "T1", "T2", "T3", "T4"} <= set(data["checks_run"])


def test_model_with_violation_goes_to_rejected_with_report(tmp_path):
    m = sample_model()
    m.objects.append(mk("Col_bad", "column", "기둥 오류", cylinder_mesh(14.5, 9.0, 0.45, 0, 4.5)))
    model_json = write_model_json(m, tmp_path / "model.json")
    out, rej = tmp_path / "out", tmp_path / "rej"
    r = build(model_json, out, rej, "plan")
    assert not r.ok
    assert not (out / "plan.png").exists()
    assert (rej / "plan.png").exists() and (rej / "plan.report.json").exists()
    data = _report(rej / "plan.report.json")
    assert data["ok"] is False
    assert any(v["check"] == "G1" for v in data["violations"])


def test_untagged_object_is_rejected_without_rendering(tmp_path):
    m = sample_model()
    verts, tris = box_mesh(0, 0, 1, 1, 0, 1)
    m.objects.append(ModelObject("Untagged", {}, verts, tris))
    model_json = write_model_json(m, tmp_path / "model.json")
    out, rej = tmp_path / "out", tmp_path / "rej"
    r = build(model_json, out, rej, "plan")
    assert not r.ok and r.png_path is None
    assert not (rej / "plan.png").exists()
    data = _report(rej / "plan.report.json")
    assert data["checks_run"] == ["TAG"]
    assert {v["check"] for v in data["violations"]} == {"TAG"}


def test_unplaceable_label_becomes_layout_violation(tmp_path):
    m = sample_model()
    m.objects.append(
        mk("Void_tiny", "void", "아주 긴 이름의 보이드 라벨은 어디에도 들어가지 않는다" * 3,
           box_mesh(0.3, 0.3, 0.5, 0.5, 0, 4.5)))
    model_json = write_model_json(m, tmp_path / "model.json")
    r = build(model_json, tmp_path / "out", tmp_path / "rej", "plan")
    assert not r.ok
    assert any(v.check in {"LAYOUT", "T1", "T2", "T3"} for v in r.violations)
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests\test_build.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'build'`)

- [ ] **Step 3: 구현**

```python
# FILE: build.py
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from checks.base import Violation
from checks.registry import MODEL_CHECKS, RENDER_CHECKS, run_model_checks, run_render_checks
from checks.tags import check_tags
from engine_params import load_params
from extract.loader import load_model
from extract.slicer import slice_model
from layout.labels import LabelPlacementError
from render.plan_renderer import render_plan

ENGINE_ROOT = Path(__file__).parent
DEFAULT_OUT = ENGINE_ROOT.parent / "01_과정" / "01_기획_구획_베이스"
DEFAULT_REJECTED = ENGINE_ROOT / "_rejected"


@dataclass
class BuildReport:
    ok: bool
    violations: list
    png_path: Path | None
    report_path: Path
    checks_run: list


def build(model_json, out_dir, rejected_dir, name, params=None) -> BuildReport:
    params = params or load_params()
    model = load_model(model_json)
    violations = list(check_tags(model))
    checks_run = ["TAG"]
    rendered = None

    with tempfile.TemporaryDirectory() as tmp:
        if not violations:
            sections = slice_model(model, params.check_heights_m)
            violations += run_model_checks(sections, params)
            checks_run += list(MODEL_CHECKS)
            try:
                render = render_plan(sections, params, Path(tmp) / f"{name}.png")
                violations += run_render_checks(render, params)
                checks_run += list(RENDER_CHECKS)
                rendered = render.png_path
            except LabelPlacementError as exc:
                violations.append(Violation("LAYOUT", str(exc)))

        ok = not violations
        target = Path(out_dir if ok else rejected_dir)
        target.mkdir(parents=True, exist_ok=True)
        png_path = None
        if rendered is not None:
            png_path = target / f"{name}.png"
            shutil.copyfile(rendered, png_path)
        report_path = target / f"{name}.report.json"
        report_path.write_text(
            json.dumps(
                {
                    "name": name,
                    "ok": ok,
                    "source": os.path.abspath(model_json),
                    "checks_run": checks_run,
                    "violations": [v.to_dict() for v in violations],
                },
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
    return BuildReport(ok, violations, png_path, report_path, checks_run)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="태그된 Blender 모델에서 검증된 평면도를 생성한다")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--blend", help="마스터 .blend 파일")
    src.add_argument("--model-json", help="이미 추출한 모델 JSON")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="통과본 저장 폴더")
    ap.add_argument("--rejected", default=str(DEFAULT_REJECTED), help="거부본 저장 폴더")
    ap.add_argument("--name", default="1F_plan")
    args = ap.parse_args(argv)

    with tempfile.TemporaryDirectory() as tmp:
        if args.blend:
            from extract.run_blender import export_model

            model_json = export_model(args.blend, Path(tmp) / "model.json")
        else:
            model_json = Path(args.model_json)
        report = build(model_json, args.out, args.rejected, args.name)

    print(f"결과: {'통과' if report.ok else '거부'}")
    if report.png_path:
        print(f"도면: {os.path.abspath(report.png_path)}")
    print(f"보고서: {os.path.abspath(report.report_path)}")
    for v in report.violations:
        where = f" @ {v.where}" if v.where else ""
        print(f"  [{v.check}] {v.message}{where}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests\test_build.py -v`
Expected: 4 passed

- [ ] **Step 5: 전체 테스트 스위트 실행**

Run: `python -m pytest tests -v`
Expected: 모든 테스트 PASS (Blender 테스트 포함)

- [ ] **Step 6: Commit (사용자가 커밋을 요청한 경우에만)**

```bash
git add "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\build.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_build.py"
git commit -m "feat(engine): add build entrypoint that exports only passing drawings"
```

---

### Task 11: 기존 `.blend` 감사 도구 (P0)

**Files:**
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\extract\blender_inventory.py`
- Create: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\extract\inventory_report.py`
- Test: `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_inventory.py`

**Interfaces:**
- Consumes: `extract.run_blender.run_blender_script` (Task 4)
- Produces: `inventory_report.group_prefix(name) -> str`, `group_inventory(items) -> list[dict]`(키: `prefix, count, types, tagged, kinds, bbox_min, bbox_max`), `render_markdown(groups, blend_path) -> str`, CLI `python extract\inventory_report.py --blend FILE --out-md FILE`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
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
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests\test_inventory.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'extract.inventory_report'`)

- [ ] **Step 3: 구현**

```python
# FILE: extract/blender_inventory.py
"""Blender 안에서 실행: blender -b <file.blend> --python blender_inventory.py -- <out.json>"""
import json
import sys

import bpy


def main(out_path):
    items = []
    for obj in bpy.data.objects:
        props = {
            k: obj[k] for k in obj.keys()
            if not k.startswith("_") and isinstance(obj[k], (str, int, float, bool))
        }
        item = {"name": obj.name, "type": obj.type, "props": props}
        if obj.type == "MESH" and len(obj.data.vertices):
            pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
            item["bbox_min"] = [min(p[i] for p in pts) for i in range(3)]
            item["bbox_max"] = [max(p[i] for p in pts) for i in range(3)]
        items.append(item)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"objects": items}, fh, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1])
```

```python
# FILE: extract/inventory_report.py
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path

INVENTORY_SCRIPT = Path(__file__).with_name("blender_inventory.py")


def group_prefix(name: str) -> str:
    """이름에서 숫자 성분을 지워 같은 종류의 객체끼리 묶는다 (CafeSet_2_Chair_3 -> CafeSet_Chair)."""
    return re.sub(r"[_.]\d+(?=[_.]|$)", "", name)


def group_inventory(items) -> list[dict]:
    groups: dict[str, dict] = {}
    for it in items:
        g = groups.setdefault(group_prefix(it["name"]), {
            "prefix": group_prefix(it["name"]), "count": 0, "types": set(), "tagged": 0,
            "kinds": set(), "bbox_min": None, "bbox_max": None,
        })
        g["count"] += 1
        g["types"].add(it["type"])
        kind = (it.get("props") or {}).get("kind")
        if kind:
            g["tagged"] += 1
            g["kinds"].add(str(kind))
        if "bbox_min" in it:
            if g["bbox_min"] is None:
                g["bbox_min"], g["bbox_max"] = list(it["bbox_min"]), list(it["bbox_max"])
            else:
                g["bbox_min"] = [min(a, b) for a, b in zip(g["bbox_min"], it["bbox_min"])]
                g["bbox_max"] = [max(a, b) for a, b in zip(g["bbox_max"], it["bbox_max"])]
    out = []
    for g in groups.values():
        g["types"] = sorted(g["types"])
        g["kinds"] = sorted(g["kinds"])
        out.append(g)
    return sorted(out, key=lambda g: (-g["count"], g["prefix"]))


def _range(lo, hi, axis):
    return "-" if lo is None else f"{lo[axis]:.1f} ~ {hi[axis]:.1f}"


def render_markdown(groups, blend_path) -> str:
    total = sum(g["count"] for g in groups)
    tagged = sum(g["tagged"] for g in groups)
    lines = [
        "# Blender 모델 감사 보고서",
        "",
        f"- 대상 파일: `{blend_path}`",
        f"- 총 객체: {total} / 태그됨: {tagged} / 태그 없음: {total - tagged}",
        "",
        "| 이름 묶음 | 개수 | 타입 | 태그됨 | kind | X 범위(m) | Y 범위(m) | Z 범위(m) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for g in groups:
        lines.append(
            f"| {g['prefix']} | {g['count']} | {','.join(g['types'])} | {g['tagged']} | "
            f"{','.join(g['kinds']) or '-'} | {_range(g['bbox_min'], g['bbox_max'], 0)} | "
            f"{_range(g['bbox_min'], g['bbox_max'], 1)} | {_range(g['bbox_min'], g['bbox_max'], 2)} |"
        )
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    from extract.run_blender import run_blender_script

    ap = argparse.ArgumentParser(description="기존 .blend의 객체 목록과 태그 현황을 감사한다")
    ap.add_argument("--blend", required=True)
    ap.add_argument("--out-md", required=True)
    args = ap.parse_args(argv)

    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "inventory.json"
        run_blender_script(args.blend, INVENTORY_SCRIPT, raw)
        items = json.loads(raw.read_text(encoding="utf-8"))["objects"]
    groups = group_inventory(items)
    out = Path(args.out_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(groups, os.path.abspath(args.blend)), encoding="utf-8")
    print(f"감사 보고서: {os.path.abspath(out)}")
    return 0


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    raise SystemExit(main())
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests\test_inventory.py -v`
Expected: 3 passed

- [ ] **Step 5: 기존 모델 감사 실행 (실제 파일, 읽기 전용)**

```powershell
Set-Location -LiteralPath 'D:\Users\admin\Desktop\2학기 논문\도면\00_엔진'
python extract\inventory_report.py --blend 'D:\Users\admin\Desktop\2학기 논문\도면\01_과정\01_기획_구획_베이스\1F_시장홀_모델.blend' --out-md 'D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\reports\inventory_1F_시장홀_모델.md'
```

Expected: `감사 보고서: D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\reports\inventory_1F_시장홀_모델.md` 출력. 보고서 머리에 `총 객체: 358 / 태그됨: 0 / 태그 없음: 358`이 나온다(계획 작성 시 임시 폴더에서 같은 명령으로 확인한 값). 같은 보고서에서 다음 두 가지도 확인됐으며, 기존 모델을 마스터로 그대로 쓰지 않는 근거다.

- **좌표 원점이 격자와 어긋나 있다.** 기둥 X 범위가 -8.9~44.8 m, Y 범위가 -17.9~35.8 m라서 9 m 격자(원점 = X1·Y1 교점)에 맞지 않는다. 마스터 모델은 원점을 X1·Y1 교점에 두어야 G5(벽 중심선-격자 정렬)가 의미를 가진다.
- **기둥이 1.5 m 높이의 짧은 막대다.** `Col` 39개의 Z 범위가 0.0~1.5 m라서 평면 절단 높이(1.5 m)와 경계에서 겨우 만나고, 복수 높이 간섭 검사(3.0 m)에서는 사라진다.

같은 방식으로 `1F_나노바나나_시맨틱_모델.blend`도 감사한다. 이 보고서와 `D:\Users\admin\Desktop\2학기 논문\도면\02_최종결과물\1F_단선_공간기획도_승인본.png`, `D:\Users\admin\Desktop\2학기 논문\도면\01_과정\02_나노바나나_스타일링\1F_건축도면_선두께_해치_치수_정밀평면도.png`를 대조해 **불일치 목록**을 만들고, 사용자에게 정답을 지정받는 것이 기획안 승인 1의 입력이다.

- [ ] **Step 6: Commit (사용자가 커밋을 요청한 경우에만)**

```bash
git add "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\extract\blender_inventory.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\extract\inventory_report.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_inventory.py" "D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\reports"
git commit -m "feat(engine): add existing-blend inventory audit tool"
```

---

## Self-Review

**1. 기획안 커버리지**

| 기획안 항목 | 담당 태스크 |
|---|---|
| §3 P1 단일 원천 = 태그된 Blender 모델, 그림 코드에 좌표 없음 | Task 2(스키마·로더), 3(절단), 4(Blender 추출), 7(렌더러는 `Sections`만 읽음) |
| §3 P2 구성 시 검증(라벨·면적 계산) | Task 6(라벨 솔버), 7(면적은 폴리곤에서 계산) — 가구 패커·문 스윙은 P2·P3 범위 밖 |
| §3 P4 검사는 산출물을 본다 | Task 7(렌더된 경계 상자·아티스트 선 두께 기록), 8(독립 검사기) |
| §3 P5 실패하면 사용자에게 보이지 않는다 | Task 10(`_rejected` 라우팅) |
| §5.1 폴더 구조 | Task 1 Step 1, 각 Files |
| §5.2 파이프라인 | Task 10 |
| §5.3 Blender 모델 규약(태그 의무, 절단 높이 1.5 m, 월드 좌표, 복수 높이) | Task 2(TAG), 3, 4, 5(G1 복수 높이 테스트) |
| §6 Stage 0 불일치 감사 | Task 11 |
| §7.1 검사 G1·G2·G4·G5·T1~T4 | Task 5, 8 |
| §7.1 G3·R1·P1·C1 | **범위 밖**(Scope 표 참조). 장부의 `planned_checks`가 구현 시점을 추적한다 |
| §7.2 결함 장부 D-001~D-009 | Task 9 |
| §8 결정 5(승인본 보호) | Global Constraints, Task 10 |

**2. 플레이스홀더 점검:** 모든 스텝에 실제 코드와 명령이 있고 "TBD/TODO/나중에"는 없다. 범위 밖 항목은 Scope 표에 이유와 함께 명시했다.

**3. 사전 검증(2026-11-01):** 이 문서의 `# FILE:` 코드 블록 37개를 임시 폴더로 추출해 `python -m pytest tests`를 실행했고 **66개 전부 통과**했다(Blender 헤드리스 테스트 포함). 이 과정에서 독립 검사기가 솔버의 결함 1건을 실제로 잡았다. 라벨 솔버가 구획존 윤곽선을 장애물로 보지 않아 튜브·보이드 라벨이 존 경계선(x=9)을 가로질렀고(T2 위반 6건), 렌더러의 장애물에 존 윤곽을 추가하고 지시선 후보 탐색을 넓혀 해결했다. 같은 문제는 `test_no_label_straddles_the_zone_boundary_line`이 막는다.

**4. 타입·이름 일관성:** `Sections.at/footprint/obj/kind`는 Task 3에서 정의하고 Task 5·7에서 같은 이름으로 쓴다. `TextRecord/LineRecord/RenderResult` 필드는 Task 7에서 정의하고 Task 8·9 테스트가 같은 필드로 생성한다. `Violation(check, message, where, objects)`는 Task 2 정의와 Task 5·8·10 사용이 일치한다. `CHECK_IDS`는 Task 9에서 정의하고 Task 10의 `checks_run`이 같은 ID를 쓴다.

---

## Addendum (2026-11-01, 계획 실행 후 추가된 변경)

계획의 11개 태스크를 실행한 뒤 마스터 모델을 만들면서 엔진에 다음이 추가됐다. 상세와 근거는 `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\reports\stage0_마스터모델_검토.md`에 있다.

| 변경 | 파일 |
|---|---|
| 검사 높이 `5.7` 추가(1층 층고 6.0 m의 천장 아래 0.3 m), 해당 테스트 수정 | `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\model\params.yaml`, `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_params.py` |
| 검사 G6(점유 영역 겹침) 신설, 결함 장부 D-010, 회귀 테스트 | `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\checks\overlaps.py`, `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\checks\registry.py`, `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\ledger\ledger.yaml`, `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_overlap_checks.py`, `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_regression.py`, `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_ledger.py` |
| 렌더러: `label_text`·`label=False/0` 태그, 코어·화장실 안쪽 라벨 금지 | `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\render\plan_renderer.py` |
| 마스터 모델 패키지(데이터 고정, 빌더, `.blend` 생성, 3D 렌더, 파이프라인) | `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\master` |
| 마스터 모델 테스트 | `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_master_model.py` |

이후 승인 1(3D 모델)을 받아 단선 평면(Stage 1)까지 엔진에 다음이 더해졌다.

| 변경 | 파일 |
|---|---|
| 표기 계층(격자 기호, 칸별·전체 치수, 표제, 진북 방위표, 축척 막대)과 `Annotation`, 표기 파라미터 | `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\render\annotations.py`, `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\engine_params.py`, `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\model\params.yaml` |
| 렌더러 개편: `Pen` 도구, 건물 윤곽(필로티 쪽은 얇게), `room` 라벨, 표기 모드 | `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\render\plan_renderer.py` |
| 새 kind `room`(라벨 전용), 모델 `meta`(진북 각도) | `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\extract\schema.py`, `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\extract\loader.py`, `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\extract\blender_export.py` |
| 사용자 승인 설계 조정(개구부 축소)을 원본과 분리해 기록 | `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\model\design_adjustments.json` |
| 지시선을 대상 영역 경계에서 긋도록 수정 | `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\layout\labels.py` |
| 표기·윤곽·room 테스트 | `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_annotations.py`, `D:\Users\admin\Desktop\2학기 논문\도면\00_엔진\tests\test_outline_and_rooms.py` |

테스트는 66개에서 91개로 늘었고 모두 통과한다.
