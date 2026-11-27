# Reference measurements (R10-C)

Measured from the vector data of the reference drawing books (read-only). Layout space = landscape sheet, mm, y down. Measurements and our own pages only; no third-party pixels are stored here.

## References

| book | file | sha256 (prefix) | pages |
|---|---|---|---|
| arch | `<TEMP>\재열지원_건축 도면집 제출자료.pdf` | 2dda59ba40a22300 (expected 2dda59ba40a22300: match) | 21 |
| struct | `<TEMP>\재열지원_구조 도면집 제출자료.pdf` | edf6b736ca9a6074 (expected edf6b736ca9a6074: match) | 18 |
| MISSING | `Jangsan_Architecture_A2.pdf` | - | MISSING_REFERENCE |
| MISSING | `Jangsan_Structure_A3.pdf` | - | MISSING_REFERENCE |

Searched for the two `3조_...` books: <TEMP>, Downloads, Desktop (depth 3) and recursively D:\ and <USER_HOME> (`*장산*.pdf`, `*[name withheld]*.pdf`). Four non-drawing-book PDFs matched (A4 design report, A4 presentation, 600x1800 panel, 482x271 study presentation) and were not used.

## Sheet types

| book | orientation | size mm | pages |
|---|---|---|---|
| arch | landscape | 594.1 x 420.2 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 20, 21 |
| arch | portrait | 420.2 x 594.1 | 17, 18, 19 |
| struct | landscape | 420.2 x 297.0 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16 |
| struct | portrait | 297.0 x 420.2 | 17 |
| struct | landscape | 677.2 x 381.0 | 18 |

## Frame and title block (layout space)

| item | A2 (arch book, landscape p4) | A3 (structure book, landscape p3) |
|---|---|---|
| outer outline rect | (12.83, 9.91, 581.15, 410.46) | (9.06, 6.97, 410.89, 290.18) |
| inner outline rect | (14.27, 11.3, 579.71, 409.07) | (10.03, 7.94, 409.91, 289.21) |
| band (solid black) | 1.44 mm | 0.97 mm |
| margins to sheet edge L/T/R/B | {'left': 12.83, 'top': 9.91, 'right': 12.93, 'bottom': 9.7} | {'left': 9.06, 'top': 6.97, 'right': 9.27, 'bottom': 6.86} |
| outline stroke | 0.254 mm (0.127 on cover and portrait sheets) | 0.254 mm (0.127 on portrait sheet) |
| heavy divider x (fill edges) | [533.65, 534.37] | [377.32, 377.82] |
| label size | 6.97 pt (KIND row 5.58 pt) | 4.93 pt (3.94 pt) |
| value / title sizes | [8.37, 13.22, 13.94] pt | [5.92, 9.35, 9.86] pt |
| row rule y (block) | [34.76, 35.48, 62.65, 90.17, 96.73, 229.19, 235.75, 242.32, 248.88, 255.44, 262.0, 268.56, 275.12, 281.69, 288.25, 294.81, 301.37, 307.93, 314.54, 321.14, 327.74, 340.83, 347.43, 354.03, 371.26, 371.98] | [24.54, 25.05, 44.27, 63.7, 68.35, 162.04, 166.65, 171.31, 175.92, 180.58, 185.24, 189.85, 194.51, 199.12, 203.78, 208.39, 213.05, 217.71, 222.36, 227.02, 231.72, 240.95, 245.6, 250.26, 262.49, 262.96] |

A3/A2 block-width ratio = 0.7072 (1/sqrt2 = 0.7071): the A3 book is the A2 layout scaled by 0.7071 with text scaled alike.

Cell sequence from the top (A2, mm from inner top y=11.30): PROJECT NO 0-23.5 | heavy rule | PROJECT TITLE to 51.4 | DRAWING TITLE to 78.9 | FILE NAME row 6.56 + NOTE area to 217.9 | REV table 12 rows x 6.56 (header row at the bottom; columns at 5.89 / 32.69 / 40.01 from the block edge) | DRAWING BY, CHECKED BY, SUBMITTED BY, APPROVED BY (4 x 6.6) | blank row 6.5 | DATE 6.6 | SCALE 6.6 | KIND / DRAWING NO / SHEET NO 17.2 (dividers 15.4 / 30.1 from the divider) | heavy rule | footer 37.1 (3 centred lines 13.94 pt).

Orientation: landscape sheets carry the block on the RIGHT edge. Portrait sheets (arch p17-19, struct p17) are the same layout rotated 90 deg clockwise: block on the BOTTOM edge, text direction top-to-bottom (PROJECT NO at the right end). Frame margins in layout space are the same.

## Elements

- grid_bubble_A2_plan_p6: `[{"label": "X1", "font": "MalgunGothic", "pt": 13.94, "diameter_mm": 9.86, "stroke_mm": 0.127}, {"label": "Y1", "font": "MalgunGothic", "pt": 13.94, "diameter_mm": 9.86, "stroke_mm": 0.127}]`
- grid_bubble_A3_struct_p15: `[{"label": "X1", "font": "MalgunGothic", "pt": 9.86, "diameter_mm": 6.98, "stroke_mm": 0.127}, {"label": "Y1", "font": "MalgunGothic", "pt": 9.86, "diameter_mm": 6.98, "stroke_mm": 0.127}]`
- dimension_style_A2_plan_p6: `{"text_pt": 11.15, "font": "MalgunGothic", "text_height_above_line_note": "text sits above the dimension line", "ticks_45deg": [[2.99, 135.0, 0.254], [3.02, 136.0, 0.254]], "other_lines": [[46.65, 0.0, 0.254]]}`
- north_arrow_A2_site_p3: `{"circle_diameter_mm": 26.54, "stroke_mm": 0.127, "N_pt": 22.77, "N_font": "Gulim"}`

## Type sizes by role (pt; mm = pt x 0.3528)

| role | A2 book | A3 book |
|---|---|---|
| block label | MalgunGothic 6.97 (KIND/DRAWING NO/SHEET NO 5.58) | 4.93 (3.94) |
| block values (date, scale, kind, names) | MalgunGothic 8.37 | 5.92 |
| block project/drawing title | MalgunGothic 13.22 | 9.35 |
| block footer | MalgunGothic 13.94 | 9.86 |
| view title under the drawing | MalgunGothic 22.31 (+ scale caption 11.15) | 15.77 (7.89) |
| grid label / dimension text / room names | MalgunGothic 13.94 / 11.15 / 11.15 | 9.86 / 7.89 / 7.89 |
| elevation level names, notes (CAD export) | Dotum 11.14, Gulim 8.2 / 7.29 / 6.56, ArialMT 14.0 | Gulim 4.64, Dotum 7.88 |
| overview tables (p2) | MalgunGothic 13.01 (headings 13.01, spaced letters) | scaled |

## Pen widths (mm; dominant by total length)

Pen set measured on plans/sections/details: 0.042, 0.085, 0.127, 0.169, 0.254, 0.339 mm. Plan p4 by length: 0.254 black (walls/openings outlines, 20.1 m) > 0.339 black (heaviest cut lines) > 0.042 black/grey hairlines (hatch, ground, chain lines; dashed lines are drawn as separate short segments, no PDF dash attribute) > 0.127 > 0.085 > 0.169. Section p19: 0.339 black 13.0 m (cut slabs/walls), 0.127 (5.8 m), 0.254. Detail p21: 0.042 / 0.339 / 0.127. Poche and floor tints are fills without outline (yellow cut concrete, pink/blue symbols).

## Page sequences

### arch book

| p | size mm | title (DRAWING TITLE cell) | scale in block | scale strings | block | images |
|---|---|---|---|---|---|---|
| 1 | 594.1x420.2 l | 투시도 | NONE |  | yes | 1 |
| 2 | 594.1x420.2 l | 설계개요 및 층별개요 | NONE | 1/1000 | yes | 0 |
| 3 | 594.1x420.2 l | 배치도 | 1 / 170 | 1 / 170; 축 척 : 1 / 170 | yes | 0 |
| 4 | 594.1x420.2 l | 지하5층 평면도 | 1 / 140 | 1 / 140; 축 척 : 1 / 140 | yes | 0 |
| 5 | 594.1x420.2 l | 지하1층 평면도 | 1 / 140 | 1 / 140; 축 척 : 1 / 140 | yes | 0 |
| 6 | 594.1x420.2 l | 지상1층 평면도 | 1 / 140 | 1 / 140; 축 척 : 1 / 140 | yes | 0 |
| 7 | 594.1x420.2 l | 지상2층 평면도 | 1 / 140 | 1 / 140; 축 척 : 1 / 140 | yes | 0 |
| 8 | 594.1x420.2 l | 지상3층 평면도 | 1 / 140 | 1 / 140; 축 척 : 1 / 140 | yes | 0 |
| 9 | 594.1x420.2 l | 지상4층 평면도 | 1 / 140 | 1 / 140; 축 척 : 1 / 140 | yes | 0 |
| 10 | 594.1x420.2 l | 오피스 평면도 | 1 / 140 | 1 / 140; 축 척 : 1 / 140 | yes | 0 |
| 11 | 594.1x420.2 l | 지상8층 평면도 | 1 / 140 | 1 / 140; 축 척 : 1 / 140 | yes | 0 |
| 12 | 594.1x420.2 l | 지상9층 평면도 | 1 / 140 | 1 / 140; 축 척 : 1 / 140 | yes | 0 |
| 13 | 594.1x420.2 l | 지상12층 평면도 | 1 / 140 | 1 / 140; 축 척 : 1 / 140 | yes | 0 |
| 14 | 594.1x420.2 l | 지상13층 평면도 | 1 / 140 | 1 / 140; 축 척 : 1 / 140 | yes | 0 |
| 15 | 594.1x420.2 l | 지상17층 평면도 | 1 / 140 | 1 / 140; 축 척 : 1 / 140 | yes | 0 |
| 16 | 594.1x420.2 l | 옥상층 평면도 | 1 / 140 | 1 / 140; 축 척 : 1 / 140 | yes | 0 |
| 17 | 420.2x594.1 p | 남, 동측면도 | 1 / 200 | 1 / 200; 축 척 : 1 / 200 | yes | 0 |
| 18 | 420.2x594.1 p | 북, 서측면도 | 1 / 200 | 1 / 200; 축 척 : 1 / 300 | yes | 0 |
| 19 | 420.2x594.1 p | 종, 횡단면도 | 1/200 | 1/200; 축 척 : 1 / 200 | yes | 0 |
| 20 | 594.1x420.2 l | 외벽 평 ,  입 ,  단면도 |  | : 1 / 70; 축 척  | yes | 0 |
| 21 | 594.1x420.2 l | 코어 상세 평, 단면도 | 1 / 80 | 1 / 80; 축 척 : 1 / 80 | yes | 0 |

### struct book

| p | size mm | title (DRAWING TITLE cell) | scale in block | scale strings | block | images |
|---|---|---|---|---|---|---|
| 1 | 420.2x297.0 l | 설계개요 및 층별개요 | NONE | 1/1000 | yes | 0 |
| 2 | 420.2x297.0 l | 배치도 | 1 / 300 1 / 200 | 1 / 200; 1 / 300; 축 척 : 1 / 240 | yes | 0 |
| 3 | 420.2x297.0 l | 지하5층 평면도 | 1 / 200 | 1 / 200; 축 척 : 1 / 200 | yes | 0 |
| 4 | 420.2x297.0 l | 지하1층 평면도 | 1 / 200 | 1 / 200; 축 척 : 1 / 200 | yes | 0 |
| 5 | 420.2x297.0 l | 지상1층 평면도 | 1 / 200 | 1 / 200; 축 척 : 1 / 200 | yes | 0 |
| 6 | 420.2x297.0 l | 지상2층 평면도 | 1 / 200 | 1 / 200; 축 척 : 1 / 200 | yes | 0 |
| 7 | 420.2x297.0 l | 지상3층 평면도 | 1 / 200 | 1 / 200; 축 척 : 1 / 200 | yes | 0 |
| 8 | 420.2x297.0 l | 지상4층 평면도 | 1 / 200 | 1 / 200; 축 척 : 1 / 200 | yes | 0 |
| 9 | 420.2x297.0 l | 오피스 평면도 | 1 / 200 | 1 / 200; 축 척 : 1 / 200 | yes | 0 |
| 10 | 420.2x297.0 l | 지상8층 평면도 | 1 / 200 | 1 / 200; 축 척 : 1 / 200 | yes | 0 |
| 11 | 420.2x297.0 l | 지상9층 평면도 | 1 / 200 | 1 / 200; 축 척 : 1 / 200 | yes | 0 |
| 12 | 420.2x297.0 l | 지상12층 평면도 | 1 / 200 | 1 / 200; 축 척 : 1 / 200 | yes | 0 |
| 13 | 420.2x297.0 l | 지상13층 평면도 | 1 / 200 | 1 / 200; 축 척 : 1 / 200 | yes | 0 |
| 14 | 420.2x297.0 l | 지상17층 평면도 | 1 / 200 | 1 / 200; 축 척 : 1 / 200 | yes | 0 |
| 15 | 420.2x297.0 l | 지상1층 평면도 | 1 / 200 | 1 / 200; 축 척 : 1 / 200 | yes | 0 |
| 16 | 420.2x297.0 l | 지상9층 평면도 | 1 / 200 1 / 200 | 1 / 200; 축 척 : 1 / 200 | yes | 0 |
| 17 | 297.0x420.2 p | 골조입면도 | 1 / 200 | 1 / 200; 축 척 : 1 / 300 | yes | 0 |
| 18 | 677.2x381.0 l | None | None |  | NO | 1 |

Composition notes: arch p1 is the cover = one full-bleed perspective picture (3842 x 2942 px, 96 dpi tag, 188 dpi effective) filling the whole content area (14.22..533.65 x 11.26..409.07 mm) with the standard block (DRAWING TITLE 투시도, SCALE NONE); there is no separate cover sheet. p2 (both books) is the design-overview sheet: 4 ruled tables/regions (설계 개요, 층별 면적표, 위치도 with N arrow and 1/1000, 용도별 분류) in 13 pt. Neither book has a drawing-index sheet. The structure book has no cover; its last page (677.2 x 381 mm, 16:9) is an image-only axonometric with no frame or block.

Section/view naming: floor plans '지하5층 평면도', '지상N층 평면도', typical floors grouped '지상5, 6, 7, 10, 11, 14, 15, 16층 오피스 평면도'; elevations '남, 동측면도' and '북, 서측면도'; sections '종, 횡단면도'; details '외벽 평, 입, 단면도', '코어 상세 평, 단면도'; structure '골조입면도', '지상N층 구조평면도'. Scale caption '축 척 : 1 / N' (spaced). View bubble = circle with view number over a rule over the sheet letter.

## Deltas: R10 template vs reference

| item | R10 template | reference (measured) | delta |
|---|---|---|---|
| Frame | single rect (14,13)-(580,407), stroke 0.9 mm | solid black band 1.44 mm between outline rects (12.83,9.91)-(581.15,410.46) and (14.27,11.30)-(579.71,409.07), outlines 0.254 mm (0.127 on cover/portrait) => visible 1.70 mm | margins L12.8 T9.9 R12.9 B9.7 (R10: 14/13/14/13); band 1.70 vs 0.90 mm |
| Title divider | x=532, 0.64 mm | heavy x=534.01 (0.72 fill + 2x0.254), visible 0.97 mm | +2.0 mm; heavier |
| Block width | 48 mm (532..580) | 45.70 mm centre-to-inner-edge (45.34 content) | -2.3 mm |
| Fields | PROJECT NO, PROJECT TITLE, DRAWING TITLE, REFERENCES, GEOMETRY, NOTES, REVISION, ISSUE, PRINT SCALE, DATE, DRAWING NO (11 cells) | PROJECT NO, PROJECT TITLE, DRAWING TITLE, FILE NAME, NOTE, REV table (11 rows + header), DRAWING BY, CHECKED BY, SUBMITTED BY, APPROVED BY, (blank row), DATE, SCALE, KIND / DRAWING NO / SHEET NO, footer (3 centred lines) | R10 lacks REV table, KIND, SHEET NO, sign rows; has REFERENCES/GEOMETRY/ISSUE not in reference |
| Label type | 6.0 pt, grey | MalgunGothic 6.97 pt (5.58 pt for KIND/DRAWING NO/SHEET NO), pure black | +0.97 pt, black |
| Value type | 9.4 pt bold titles, 17 pt bold drawing no. | 13.22 pt regular titles, 8.37 pt values, 13.94 pt footer | titles larger, no bold, drawing no. small in a 15 mm cell |
| Cell rules | 0.18 mm | 0.254 mm black (top 3 cells), 0.042 mm hairlines (grey 0.596) | hairline table style |
| Orientation | landscape only | portrait = landscape layout rotated 90 deg clockwise, block on the bottom edge, text reads top-to-bottom | new in R10-C |
| A3 | none | A2 layout x 0.7071 (frame margins L9.06 T6.97 R9.3 B6.9, band 0.97, block 32.1 mm, text x0.707) | new in R10-C |
| Pens | 0.09 / 0.10 / 0.12 / 0.18 / 0.4 mm ad hoc | set {0.042, 0.085, 0.127, 0.169, 0.254, 0.339} mm (0.12/0.24/0.36/0.48/0.72/0.96 pt) | CAD pen table; heaviest drawing pen 0.339 |
| Grid bubble | r 4.4 mm (D 8.8), 7.3 pt bold, 0.23 mm | D 9.86 mm (A3 6.98), 0.127 mm, label 13.94 pt (A3 9.86) regular | +1.1 mm, much larger label |
| Dimension | 45 deg tick 1.2 mm, text 6.7 pt, 0.105-0.13 mm | 45 deg tick 3.02 mm @0.254, dim line 0.254, text 11.15 pt above the line | ticks 2.5x longer, text 1.7x larger |
| North symbol | none in template | circle D 26.54 mm 0.127, 'N' 22.8 pt Gulim, needle rotated to true north | added helper |
| View caption | title 10.8 pt bold + '1:N' 7.5 pt | title 22.31 pt (A2) + '축 척 : 1 / N' 11.15 pt under it, view-number bubble '1 over A' | caption 2x larger |
| Colour | BLACK (.09,.105,.11) | pure black 0x000000 text and lines | block uses pure black in R10-C |
| Cover / overview | no cover; no overview | p1 = full-bleed render + the block (DRAWING TITLE 투시도); p2 = 설계개요 and 층별 면적표 (4 tables + location map) | R10-C produces both |
| Drawing index | none | none in either reference book (the sequence is the index) | R10-C adds index_pages() |
