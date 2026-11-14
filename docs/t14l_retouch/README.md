# C-T14L / 실제 AI 리터치 다운로드·정확성 검수 필수화

**Scope:** V4.2 PR #19 `codex/t14k-editorial-v42` commit `aa8217a34c18e45075df5fd344de2d5d8a4baac9`. This branch is a **protocol-only Draft PR**. It does not falsely claim that image editing has been executed.

## Gate and responsibilities

- All new graduation-book graphics (exterior renders, massing/program/walking diagrams, technical plan/elevation/section/detail graphics) get a ChatGPT/Adobe Photoshop retouch/review pass with a **real uploaded source and a downloaded PNG** before any edited graphic is adopted into a new V4.3 candidate. Text-only pages are exempt.
- This pass is *not* permission to modify the building. Ground truth stays in Blender/source model, source PDFs, SVG, model cache and documented architecture decisions. For technical drawings the AI output is a background/style layer only. Re-composite the original validated vector linework/annotations/scale bar on top.
- Every figure requires a handoff packet: source/geometry SHA, pixel bounds, original PDF/vector reference, print-scale dimensions, protected mask/vector overlay, per-asset negative prompt, retouch PNG, before/after image, independent structural review, approved-assets SHA manifest.
- Missing source edit or absent real download => `AWAITING_EXTERNAL_AI_RETOUCH`. Missing geometry mask or degraded CAD linework => `REJECTED_NOT_FOR_BOOK`. Human verified stylistic candidate => `APPROVED_FOR_LAYOUT_NOT_DESIGN_APPROVED`. No automatic FREEZE.

## Known real G-002 pilot source

- JPG in repo `assets/t14k/architectural_exterior_render.jpg`.
- SHA256 `9acd9ab3f5848f51ac1f2cc678ae988bf4f17197f238a5905eac9d8460e75a75`.
- 2400×1350px / 16:9. Printed at 396×222.75mm = ~154 original source dpi.
- Preserve exact full tower, 17 levels B2–15F, four corner cores, facade rhythm, tubes and voids, midlevel garden, roof openings and perspective. No made-up window, stair, door, balcony, roof, material spec or additional building.
- Real source render is from earlier presentation workflow; original full GLB is missing. Material/color, plants and surrounding context are visual staging only.

## Pilot order and workflow

1. G-002: authentic exterior Blender render; only photographic relight/color grading/background tidying with structural lock.
2. G-103: sequence of actual model massing/stack/floor/tube; retouch aesthetic layer only.
3. G-106: main floor plan, all sectioned geometry/dims/grid/text protected vector.
4. G-111: technical details, keep model vs concept vs unresolved status.

For each: **export source → submit source + prompt to ChatGPT/Adobe → actually save PNG → geometry/hash/print QA → signed review → input to source renderer → rebuilt PDF**. Then expand to remaining Part I & II image inventory. A screenshot of an AI suggestion or a generated architecture lookalike is not a valid substitute for the actual retouched source.

## Actual implementation handoff

The **actual fail-closed gate and regression tests are now committed to this Draft PR**, with verified blob hashes:
- `tools/t14l/retouch_gate.py` (Git blob `e6075fec6f3b8655b5b1f7a55e136bb9ce94d6ef`)
- `tests/test_t14l_retouch_gate.py` (Git blob `e5152e6e6c105aee661078064df416cb81560cc0`)
- `docs/t14l_retouch/HANDOFF_PROMPTS.md`, `CODEX_EXECUTION.md`, `G002_manifest.template.json`.

Local **synthetic-only** regression run: `python -m unittest discover -s tests -p test_t14l_retouch_gate.py -v` => **11/11 pass**. These results check only the gate logic; no real G-002 AI image was produced and no print gate passed. A separate downloadable ChatGPT-session PDF/package is supplementary, not a substitute for an actual edited PNG.

For actual local handoff, copy the template to `G002_manifest.json` in the same directory; fill the real retouch image SHA, export record, comparison and independent review, then run `python tools/t14l/retouch_gate.py docs/t14l_retouch/G002_manifest.json --report docs/t14l_retouch/G002_audit.json`. Use `--print-gate` only after the real PDF page has been inspected and actual print DPI is adequate.

Working directory to be created/verified:
`D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14L`.
Source image in new worktree:
`D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14L\assets\t14k\architectural_exterior_render.jpg`.

**No new paid API, connection, structural modification, PR merge, or final FREEZE is authorized.**
