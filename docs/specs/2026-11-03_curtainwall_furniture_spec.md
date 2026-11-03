[TARGET_FILES]:
- `src/01_headless_slicer.py` (Modify: Exclude 3D door/window wireframe projections, extract clean opening cutouts and urban context)
- `src/02_topology_to_cad.py` (Modify: Recalibrate glass curtain wall to ultra-thin double lines, implement opaque-white-filled architectural furniture library & spatial zoning, and keep Shapely collision/culling rules)
- `src/04_hybrid_compositor.py` (Modify: Enforce strict A3 420x297mm scale locks at 1:500 for 1F and 1:100 for upper floors)
- `tests/verify_pipeline.py` (Update: Add high-zoom 800x800px crop verification for curtain walls, market furniture, cores, and capsules)

[CORE_OBJECTIVE]:
Fix the overly thick window/curtain-wall lines so they read as delicate transparent double-line glazing rather than heavy concrete walls, replace the repetitive mechanical `Π`-shaped furniture boxes with a rich, opaque-masked (`#FFFFFF` fill) architectural furniture & layout system tailored to each zone, and maintain zero collisions across all cores, doors, and site landscape elements on A3 sheets (`1:500` for 1F, `1:100` for upper floors).

[GSTACK_INTEGRATION_STRATEGY]:
- Core geometry slicing and vector drafting run locally via headless Blender (`bpy`, `bmesh`), `Shapely`, and `ezdxf` for zero-latency execution.
- Write execution logs and visual QA crop summaries (`crop_curtainwall_furniture.png`, `crop_core_restroom.png`) to `.gemini_sync.md` in the project root so artifact versions are tracked seamlessly.

[DETAILED_LOGIC_&_LAYOUT]:

### 1. Fix Window & Glass Curtain Wall Thickness (`A-GLAZ` Ultra-Thin Calibration)
In our latest `1:500` output, the exterior glass curtain wall and indoor/outdoor glazing line look almost as thick and black as the structural RC core walls because the two parallel lines merge together and the mullions are drawn as heavy black blocks. Fix this immediately:
- **True Double-Line Separation on Paper:**
  - At `1:500` scale, set the distance between the inner and outer glazing lines to `220mm` in world units (`0.44mm` on A3 paper) so the two parallel lines NEVER merge into a single thick black bar. (At `1:100`, use `150mm` world gap = `1.5mm` on paper).
  - Fill the strip between the two parallel glazing lines with **pure opaque white (`#FFFFFF`)** first so floor tile grids and column lines underneath are cleanly masked out.
- **Delicate Glazing Stroke & Subtle Mullions:**
  - **Outer & Inner Glass Frame Lines:** Paper stroke width **`0.09mm`** (at `1:500`) / **`0.12mm`** (at `1:100`), color **`#4A4A4A` (Medium-Dark Gray)**—less than 1/4 the thickness of cut structural walls (`0.45mm` `#000000`)!
  - **Center Glass Line (Optional at 1:100):** Hairline `0.05mm`, `#888888`.
  - **Mullion Ticks:** DO NOT draw heavy solid black squares! Draw only a crisp hairline perpendicular tick (`0.08mm` stroke, `#555555`) bridging strictly across the `220mm` gap between the two glazing lines every `2.5m ~ 3.0m`.

---

### 2. Architectural Furniture Typology & Spatial Layout Engine (Replace `Π`-Boxes)
Look at the current market hall furniture: they are all identical mechanical `Π`-shaped rectangles, and the background floor tile grid (`#CCCCCC`) passes straight through them! Implement the following two rules across all furniture:

#### Rule A: Mandatory Opaque White Background Mask (`fill="#FFFFFF"`)
- Every single furniture symbol (tables, counters, chairs, stalls, benches, beds, display plinths) MUST be rendered as closed SVG/CAD polygons with **`fill="#FFFFFF"` (100% opaque white fill)** and **`stroke="#666666"` (`0.08mm` paper stroke width)** so the floor tile grid or stipple dots NEVER bleed through the inside of furniture!

#### Rule B: Multi-Zone Architectural Furniture Planning & Clustering
Instead of stamping one repetitive block across `1 시장 홀`, divide each program zone into functional sub-zones and populate them with authentic architectural 2D symbols:

1. **`1 시장 홀` (Market Hall) — 3 Functional Sub-Zones:**
   - **Sub-Zone 1A: Central Island Market Booths (중앙 아일랜드형 마켓 매대, ~50% of hall):**
     - Place `3.2m x 2.2m` rectangular island counters (`600mm` deep perimeter counter table with rounded outer corners `r=150mm`, subtle internal counter tray dividers, open center standing zone for vendors, and 2 small circular vendor stools `r=180mm` inside).
     - Arrange in clean back-to-back or bay-aligned pairs centered between the structural column grid, keeping at least `1.8m` main pedestrian aisles.
   - **Sub-Zone 1B: F&B Café & Communal Dining Zone (푸드코트 및 식음 테이블 존 — near Curtain Wall & Light Tube `7`, ~30% of hall):**
     - Place clusters of **4-Person Square Café Tables** (`850mm x 850mm` square table + 4 tucked chairs `420mm x 420mm` with curved backrests on all 4 sides) and **8-Person Communal Long Tables** (`2400mm x 900mm` table + 4 chairs on each long side).
   - **Sub-Zone 1C: Pop-Up Kiosks & Information Bar (전면 안내 및 팝업 바 — near Main Entrance, ~20% of hall):**
     - Curved or linear reception/tasting bar (`3.0m x 0.8m`) with a row of 4~5 circular bar stools (`r=180mm`) along the front edge.

2. **`2 필로티 광장` (Piloti Plaza — Covered Outdoor Public Space):**
   - Place 3~4 **Circular Planter Benches (원형 수목 벤치)** in the open bays of the Piloti Plaza: concentric circles consisting of an outer wooden bench ring (`R_out = 1.6m`, `R_in = 1.15m`, with radial slat tick lines) wrapping around an inner planted shrub/tree circle (`R = 1.15m` with botanical foliage linework).

3. **`5 서측 캡슐` (West Capsule — Exhibition & Lounge Zone):**
   - Remove the awkward `| |` brick shapes and parentheses arcs.
   - Along the central axis of the capsule, place **3 Curated Exhibition Plinth Islands** (clean `2.4m x 1.2m` rectangular/oval display tables showing subtle artifact contours on top) alternating with **Double-Sided Gallery Benches** (`1.8m x 0.6m` minimalist museum benches with seat division lines) and a curved **Reception / Audio-Guide Desk** near the entrance door.

4. **`4 선큰 마당` (Sunken Courtyard) & Outdoor Plazas:**
   - At the bottom landing of the sunken courtyard and along the southern terrace, place small clusters of **Circular Outdoor Bistro Tables** (`r = 450mm` round table surrounded radially by 3 or 4 small café chairs).

5. **Upper Floors (`1:100` Scale Plans — 2F, 3F, etc.):**
   - Automatically match Korean room names on upper floors to rich `1:100` architectural layouts (all with `#FFFFFF` opaque fill):
     - **오피스 / 업무 / 코워킹:** Double-sided workstation desk clusters (`1600mm x 1600mm` per 2-person module) with task chairs (seat + curved backrest) and thin desk divider screens.
     - **회의실 / 세미나:** Large oval or boat-shaped conference table surrounded by 8~12 chairs.
     - **전시 / 갤러리 / 홀:** Free-standing exhibition partition walls + museum benches + sculptural plinths.
     - **공방 / 스튜디오 / 실험실:** Heavy worktables (`2400mm x 1200mm`) with stools and perimeter wall shelving (`450mm` deep with diagonal shelf symbol lines).
     - **휴게 / 라운지 / 카페:** L-shaped lounge sofas (with seat cushion seams and backrest lines), low round coffee tables, and lounge armchairs.

---

### 3. Maintain Core Column Culling, Door Collision Solver & 6-Tier Lineweight Hierarchy
Keep all structural and geometric rules strictly enforced:
1. **Zero Columns Near Cores/Tubes:** Maintain `core_exclusion_zone = unary_union(all_cores_and_tubes).buffer(1.8)` to cull any black point columns inside or within `1.8m` of stair cores, restrooms, capsules, or circular tubes.
2. **Zero Door/Wall/Fixture Collisions:** Punch clean boolean cutouts in both `A-WALL-CUT` and `A-GLAZ` at all door locations, enforce `>= 250mm` corner jamb clearance, auto-flip door swing sectors (`swing_poly`) to avoid hitting walls/other doors, and subtract door swing zones before placing fixtures.
3. **Updated 6-Tier Paper-Space `mm` Lineweight Table (A3 `420mm x 297mm`):**
   - **Tier 1 (`0.45mm` | `#000000` Solid Black Fill):** Cut Structural RC Walls, Core Walls, Point Columns, Mega-Tube Structural Rings (`A-WALL-CUT`, `A-COLS-CUT`).
   - **Tier 2 (`0.18mm` | `#222222` Dark Charcoal):** Door Leaves (`A-DOOR-LEAF`), Sunken Slab Perimeter Edge (`A-SLAB-EDGE`), Toilet Stall Partitions (`A-PART`).
   - **Tier 3 (`0.12mm` | `#444444` Medium Gray):** Stair Treads & Handrails, Spiral Ramp Treads, Elevator Car Boxes, Context Building Outlines (`A-STAIR`, `A-ELEV`, `A-CONTX`).
   - **Tier 4 (`0.09mm` | `#4A4A4A` Medium-Dark Gray on `#FFFFFF` Fill):** **Glass Curtain Walls & Window Frames (`A-GLAZ`)**—crisp double lines (`220mm` world gap at `1:500`) with hairline mullion ticks every `2.5m`.
   - **Tier 5 (`0.08mm` | `#666666 ~ #777777` Light-Medium Gray on `#FFFFFF` Fill):** **All Furniture Symbols (`A-FURN`)**, Sanitary Fixtures, Door Swing Arcs (`A-SWING`), and MEP Shaft `X` lines.
   - **Tier 6 (`0.04mm ~ 0.05mm` | `#CCCCCC` Very Light Gray):** Floor Tile Grids, Piloti Stipple Dots, Dashed Structural Grid Lines, and Site Botanical Foliage (`A-HATCH`, `A-GRID`).

[STRICT_CONSTRAINTS]:
- **Non-Destructive:** Never overwrite or corrupt the source `.blend` file.
- **Opaque Furniture Masking:** Floor grid lines (`#CCCCCC`) must NEVER be visible inside the boundary of any table, chair, counter, market stall, or bench (`fill="#FFFFFF"` is mandatory on all furniture elements).
- **Curtain Wall Contrast:** The glass curtain wall (`A-GLAZ`) must visually read as thin, delicate double lines—never merging into a thick black line like `A-WALL-CUT`.

[GEMINI_SYNC_REPORT]:
Upon completion, CLAUDECODE must print a markdown summary to the terminal and update `.gemini_sync.md` in the project root containing:
- **Executed Actions:** Confirmation of `A-GLAZ` double-line stroke reduction (`0.09mm` with `220mm` white-filled gap) and replacement of `Π`-boxes with multi-zone white-masked furniture symbols.
- **GSTACK & Skill Usage:** Status of local workspace outputs and high-zoom inspection crops (`crop_curtainwall_furniture.png`).
- **PR / Pipeline Status:** Validation results for 1F (`1:500`) and Upper Floor (`1:100`) A3 PDF/PNG/DXF sheets.
- **Unresolved Issues / Next Steps:** Any remaining edge-case geometry warnings or layout density adjustments.