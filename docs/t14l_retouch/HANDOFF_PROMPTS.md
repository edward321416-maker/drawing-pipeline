# C-T14L | Image-to-image AI retouch handoff prompts (2026-11-14)

**Ground truth:** C-T14K PR #19 V4.2; original Blender/model/CAD/SVG sources. AI image is never structural or design evidence. Never generate a lookalike building. The actual source image must be submitted to ChatGPT or Adobe Photoshop, and the edited PNG actually downloaded before adoption. Keep original source and PNG hashes.

## Universal instruction (prepend verbatim)

> You are editing the supplied **existing building image**, not designing or generating a new building. Preserve exactly the camera, cropping, perspective, building footprint, visible levels, cores, columns, floor slabs, lift tubes, facade geometry, voids and roof. Do not add a stair, door, window, railing, slab, mezzanine, roof hatch, structure, material specification, or circulation element not evidenced by the source. Only modify light, color grade, atmospheric contrast, background distractions and allowable graphic styling. Preserve the input pixel dimensions and ratio. Do not generate text, labels, dimensions, or scale bars. If accurate image preservation is impossible, stop and report this limitation rather than hallucinating structure. Deliver the actual PNG and state what changed.

## G-002 — exterior render (first pilot)

**Source:** D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14L\assets\t14k\architectural_exterior_render.jpg
**Known source hash from PR #20:** 9acd9ab3f5848f51ac1f2cc678ae988bf4f17197f238a5905eac9d8460e75a75. Rehash actual source bytes before editing.
**Format:** 2400×1350, 16:9. At 396 mm wide, effective source dpi is about 154; for 300 dpi use native same-camera rerender at least 4680 px wide or a smaller layout. Do not treat generative upscaling as proof of fabricated details.

> Retouch the attached genuine exterior JPEG conservatively: tidy sky/background, slightly raise shadow readability, balance white/color temperature, reduce compression noise and harmonize lighting. Keep the 17 levels (B2–15F), the four corner cores, T1–T4 tubes, middle garden, floor/void sequence, facade repetition, roof openings and camera position completely unchanged. No invented glazing, stair, new mass, door, railing, roof edge, material, or vegetation that changes access. Output an actual same-size PNG. Attach a concise change list and flag suspected geometric edits.

Inputs must include the real JPG plus structural silhouette/wireframe/anchor overlays where available; standalone image-only edits cannot certify built geometry. Human reviewer must verify top, core corners, tubes, middle garden and base at full and zoomed crops.

## G-103 — massing/program diagram

> Edit this **actual original** G-103 SVG/PDF-based visual only for color hierarchy, shading, contrast and clarity. Keep exactly the count and geometry of slabs/masses, positions of cores and tubes, stages and legend mappings. Do not change the sequence or introduce a building element. Do not re-create labels; recompose original labels and vectors above the retouched image. Return a real PNG and an edit list.

## G-106 — technical floor plan

> Use this **actual CAD/SVG plan** as immutable technical geometry. Only recolor non-technical background and agreed decorative zones. Do not alter walls, columns, grids, circulation, doors, stairs, tubes, dimensions, scale bars, annotation positions or text. Deliver a PNG background. The verified original CAD/SVG vectors, all lines and annotations must be placed on top in the final composite. Never create architectural technical detail via generative painting.

## G-111 — detail drawing

> Improve the readability of the real provided detail by limited shading/texture in approved blank areas. Treat any unresolved joint/fire/waterproofing/rebar information as unresolved, not a license to invent a constructible detail. Do not modify model geometry, attachment evidence, lineweights, dimension figures or labels. Final top-layer linework, dimensions, scale, text and verified/unverified status come from the authoritative source vector, not AI.

## Mandatory rejection / negative prompt

Do not redesign; no extra floors, moved cores, invented circulation, added glazing, fake construction details, changed camera, altered roof, shifted columns, missing voids, hallucinated text/dimensions, unsupported material claims or fabricated 300-dpi detail.

**Evidence for every candidate:** real original file/hash, AI export/download record, real candidate PNG/hash, before/after image, source vector/protected layers, signed geometry checklist, print-width/dpi and per-page inspected PDF render. If the editor cannot ingest the original image, status is AWAITING_EXTERNAL_AI_RETOUCH.
