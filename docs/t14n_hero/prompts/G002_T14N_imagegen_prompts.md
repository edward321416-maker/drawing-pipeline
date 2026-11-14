# G-002 C-T14N image-edit prompts actually executed

All prompts used `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14N\assets\t14k\architectural_exterior_render.jpg` as the authoritative architectural edit target. The structure mask and silhouette were reference-only inputs.

## Scheme A — Urban Daylight

Produce a polished international architecture-competition hero visualization under clear soft daylight. Keep the exact camera, crop, tower height, floor/slab rhythm, cores, tubes, middle void and sky garden, roof opening/garden, façade openings, footprint, and silhouette. Do not invent or move architectural elements. Improve natural global illumination, contact shadows, restrained concrete/metal/glass depth, existing-glazing reflection/transparency, atmospheric perspective, generic urban context, planting, and naturally scaled pedestrians. Output the same 16:9 composition with no text or masks.

## Scheme B — Blue Hour

Produce a polished blue-hour visualization while preserving the same locked architectural features. Use natural cobalt ambient light and restrained warm light only behind existing openings/glazing. Emphasize the inhabited vertical market, open gardens, voids, tubes, and slab layering without neon spectacle or invented architecture. Output the same 16:9 composition with no text or masks.

## Background plates

For each A/B raw study, remove the AI-reinterpreted central tower inside `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14N\docs\t14n_hero\qa\G002_tower_composite_mask.png` and reconstruct a continuous subordinate urban backplate. The cleared zone contains no hero building, façade grid, text, or dominant object. These plates have no architectural authority and are used only outside the source-tower matte.

## Enforcement

The raw A/B results changed architecture and were marked `REJECTED_NOT_FOR_BOOK`. Only the urban backplates were retained. The corrected candidates use source-derived building pixels and are still `VISUAL_QUALITY_NOT_APPROVED` pending user review.
