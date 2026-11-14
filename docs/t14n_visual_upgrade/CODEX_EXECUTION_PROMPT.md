# Codex execution | C-T14N: actually improve G-002 architectural hero render

**Read the full PR #21 current HEAD and PR #22 art-direction documents first.** This task exists because the user visually rejected the C-T14M result: a near-original, tone-only G-002 image is **not** an architectural competition hero render. Do not repeat the old pipeline under a new name.

Repo: `edward321416-maker/drawing-pipeline`.
Existing Draft PR #21 head at review: `f8a031046494e382dea3c9cd74adbbed05afe6b7`.
PR #21 base: `chatgpt/t14l-ai-retouch-protocol-20261114`.
Use your own isolated T14N branch/worktree and preserve main, PR #19/#20/#21, V4.2, model caches and authoritative geometry. No merge, FREEZE, purchases, or unauthorized design changes.

## 1 — Diagnose and reject the weak prior result
Read actual `tools/t14m/retouch_assets.py` `ingest_g002` and G-002 manifests. Record the real observed facts: `GaussianBlur(64)`, AI/source color difference clipped ±32, factor 0.35, protected pixels replaced, MAE 2.1483/255. This is color correction rather than immersive architectural visualization. Do not submit `G002_ai_grade_structure_locked.png` as award-caliber.

## 2 — Find a **faithful production source**
Inventory *actual files* (not presumed paths): original high-resolution Blender/GLB/FBX/OBJ source, any mesh-generating Python scripts, `model_world.npz` and a 3D camera transform/projection; also verify a ground plane, true facade material references and site photos.

- If a faithful 3D model/camera can be reconstructed from **source-authoritative artifacts**, compare model floor counts, cores A–D, tubes T1–T4, slab/void topology, roof and pixel projection to the source, and document proof. Treat unverifiable mesh geometry as a hard block; no arbitrary regeneration.
- If authoritative 3D reconstruction is impossible, use a **2.5D compositing** path: retain source building silhouette and exact architecture; add context/sky/street/people only through separately reviewed and geometrically safe masks. State its visual limitations and never describe it as native PBR or an architectural design approval.

## 3 — Compose competition-quality visuals, not a generic filter
Reference criteria: Brick Visual's *Kengo Kuma Shanghai Industrial Museum* (2026 Architizer Vision Awards Rendering–Atmosphere Jury Winner), and Digital Bunch's *Public Life in the Financial District* (Rendering–People Editor's Choice). Use their craft standards, never copy their buildings or imagery.

Create **A**: daylight editorial hero, warm-neutral plausible lighting, architectural facade depth, realistic ground shadow, environmental layers, human-scale activity, and a coherent city/public-space story.

Create **B**: blue-hour occupied commercial street, warm interiors only where source verifies openings, authentic surrounding life, restrained atmosphere and visual contrast. Either variation must emphasize the user's actual vertical public commercial circulation and spatial porosity. Use geographically specific Sindang/Dongdaemun cues only with source-proven site data; otherwise label conceptual context.

The actual building must be at least as legible as the source. Never add floors, cores, tubes, skybridges, windows, doors, balconies, stairs or roof shapes. Document any appearance-only material assumptions.

## 4 — Execute the edit and handoff
Give real `G002_source.jpg`, geometry reference, building silhouette/lock and **both actual prompts** in `G002_CHATGPT_ADOBE_HERO_PROMPTS.md` to ChatGPT image editing or Adobe Photoshop. If the connected tool does not accept the actual bytes, supply the complete upload packet and mark it blocked; do not fabricate returned PNGs.

Acquire the real edited PNGs `G002_A_daylight_raw.png`, `G002_B_bluehour_raw.png`; record export tool receipt, SHA and dimensions. Use any generated architecture-changing pixels **only as inspiration**, not a verified output. Build genuine corrected composites using authoritative geometry and layer masks. Do not reuse `ingest_g002` low-frequency-only output as the final image.

## 5 — Two independent review gates
- **Architectural accuracy:** source-to-candidate alignment and full crop inspection for floor slabs, silhouette, four cores, tubes, voids, midgarden, roof, base, camera; human reviewer required.
- **Visual craft:** human reviewer sees source and A/B full-screen (plus enlarged crops), rates compelling composition/architecture narrative, light/shadows, material/depth, human/public-life scale, context coherence, and print/display quality 1–5. Every criterion must be >=4 and summary `ACCEPT` to label **visual quality approved**. A pixel-change metric never substitutes for judgment.
- If either gate is pending, report status `VISUAL_QUALITY_NOT_APPROVED` or `GEOMETRY_NOT_APPROVED`. Never publish Candidate V4.3 merely because a PNG was downloaded.

## 6 — Output to the user, not just GitHub
Deliver:
1. Full-size A/B PNG + original image side-by-side, with 100% detail crops and aesthetic quality/accuracy notes.
2. 2–4-page visual review PDF at A3 landscape, showing actual source and A/B if obtained; if not, a clearly titled **blocked/report** PDF without fake render images.
3. File hashes, masks, scene/source provenance, pass/fail review JSON and actual tests.
4. Separate Draft PR for candidate assets and code changes (not merged).
5. Actual final Candidate V4.3 only if approved print and architecture criteria are met, otherwise no V4.3 claim.
6. User-facing full absolute Windows paths. Update `AI_Execution_Log` with transport and readback.

Don't ask again about a decision already approved. If the 3D source really does not exist, document the specific missing link and maximize safe improvement from 2.5D. Work **one G-002 hero image to visual quality first**, then expand diagrams and plans. The user should actually **see** the increased quality before proceeding.

**No invented visually compelling results; the only acceptable success is a real edited architectural scene visibly better than C-T14M while structurally faithful.**
