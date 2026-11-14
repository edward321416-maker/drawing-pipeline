# C-T14N | Award-caliber architectural hero visualization — art direction (2026-11-14)

## User acceptance gap / source facts
- User reports the C-T14M result does not read as a competition-quality architectural rendering.
- PR #21 G-002 image processor performs GaussianBlur(radius=64) on source and AI images, clips their low-frequency channel difference to ±32, applies only 35% of that field, enhances contrast 1.035 and color 1.02, then restores every locked pixel. This is a conservative **color grade**, not architectural material/lighting/context visualization.
- `G002_automated_accuracy.json`: average absolute RGB channel delta **2.1483/255**; `G002_ai_export_record.json`: raw PNG **1672×941**, source/candidate **2400×1350**. The final candidate contains **no raw AI spatial pixels**.
- Do not pass a subtle grade as a successful "award-quality hero retouch". Existing four C-T14M images remain `REJECTED_NOT_FOR_BOOK` pending independent review.
- Source-model constraint: original same-camera full-tower Blender source was not found per PR #21; so a full 3D photoreal rerender is **blocked until a verified source mesh and camera can be established**. Never invent architectural geometry to unblock it.

## Verified contemporary visual references (mood/quality, not images to copy)
1. Architizer **2026 Vision Awards**: Brick Visual, *Kengo Kuma Shanghai Industrial Museum*, Jury Winner, Rendering — Atmosphere. https://architizer.com/blog/inside-architizer/updates/2026-vision-awards-winners/
2. Architizer **2026 Vision Awards**: Digital Bunch, *Public Life in the Financial District*, Editor's Choice Winner, Rendering — People. Same official page.
3. Architizer **2026 Vision Awards** winners gallery: https://winners.architizer.com/2026/Vision/
4. 2025 environment-oriented architectural visualization: *Te Ahi Kā* by TT Architects, Editor's Choice Winner, Rendering — Architecture + Environment. https://architizer.com/blog/inspiration/collections/rooted-in-place-the-art-of-context-in-architectural-visualization/

These establish craft criteria, not a guarantee of a prize. Do not reproduce another architect's project, composition, signature palette, or site.

## Proposed C-T14N visual intent
Primary subject: the *user's* actual 3D fractal commercial architecture, with faithful vertical circulation and ground-to-upper-floor public access. The story is **'the street becomes three-dimensional'** rather than a generic photoreal glass tower.

### Two visual alternatives for a first comparison
**A — Urban daylight / competition main hero (default)**:
- legible 3/4 exterior perspective, real source camera until verified 3D allows another; avoid arbitrary camera change
- coherent natural sky, credible sun direction and contact shadows, warm-neutral materials, restrained contrast
- urban fabric around the tower should read as Sindang/Dongdaemun **only with verified photo/map/model context**; otherwise use visibly conceptual context rather than claim it is the site
- one visual hierarchy: tower primary, pedestrian/public-space use secondary, surrounding city third
- physically plausible translucency, depth, scale, glass reflection, vegetation in allowed regions; no false additions to core/tube/slab/void/facade
- show base-to-upper-level accessibility by revealing real tubes and public space *without inventing connection geometry*

**B — Blue-hour active street (alternative)**:
- dusk sky with consistent cool ambient light, warm occupied commercial interiors only when original glazing/openings support them
- human-scale street foreground, plausible activity, subtle wet/dry surface detail, realistic exposure without bloom/glow excess
- make the vertical voids and movement cues legible from confirmed source structure, not invented stairs or skybridges

### Composition requirements
- No bare object floating in empty gray background; a credible ground plane, horizon and foreground/background layering are required.
- A focal point, leading eye line, stable value hierarchy, correct human scale, intentional cropping, atmosphere and plausible material response.
- Preserve the actual source footprint, 17-level B2–15F definition, four corner cores A–D, tubes T1–T4, slabs, garden, voids, roof and aperture rhythm.
- For any unverified material, choose neutral conceptual shading explicitly flagged **visualization assumption**, never claim as built/constructible fact.
- Quality cannot be inferred from "AI edited" metadata, number of modified pixels, photoreal buzzwords or 300dpi alone.

## Technically honest production pathways
**Path 1 (preferred)**: Confirm/build traceable source 3D mesh + camera from existing verified model. Set up actual physically based material, HDRI/sun lighting, world/city backdrop and controlled entourage. Render native 16:9 4800×2700 or wider; save raw render passes (beauty, depth, object-ID/cryptomatte, normal, shadows) and unmodified-source geometry evidence. Use ChatGPT/Photoshop only for postproduction of nonstructural layers. All camera and model changes require provenance and geometric consistency checks.

**Path 2 (fallback if reliable 3D/camera absent)**: Architectural **2.5D photo-compositing** of source JPG with scene lighting, verified site photo/background, ground contact, atmosphere and scale references. Keep building silhouette, apertures, floor lines, cores/tubes strictly tied to original. Use masks (structure / building interiors / glazing / ground / sky / city / people). Add only photographic/atmospheric pixels outside structural authority; no claiming true PBR or new 3D views. The result may be visually better but **must be labelled 2.5D**.

**Not acceptable**: Current `ingest_g002` low-frequency tone-only output presented as award-level render; arbitrary image-to-image generative redraw that changes the user’s architecture; fabricated full-tower model; added stairs, floorplates, roof objects or unverified bridges.

## Deliverables before moving to G-103/G-106/G-111
1. User-facing **full-size** side-by-side A/B scene options, not merely a PDF plan and not microscopic thumbnails.
2. Reference-to-output art-direction notes (light/material/depth/urban setting/human scale/storytelling).
3. Geometry overlays and critical crops, original/render/edited SHA256, independent architecture geometry review.
4. Dedicated visual craft panel rated by a human reviewer at 100% and presentation scale. Both quantitative and qualitative gate evidence.
5. Candidate full-sheet PDF (if architecture passes) or a clearly labelled review-sheet PDF (if blocked).
6. Select A or B based on actual result. Only then expand to additional sheets. `main`, PR #19/20/21, final V4.2 and structural source remain unchanged.

## Approval rule
G-002 must pass **two separate independent gates**:
- Geometry/provenance: hard gate; zero altered protected CAD/3D geometry, source-to-final traceability; status as in existing C-T14M.
- Visual craft: image must show material realism, credible illumination/shadows, depth/context, appropriate human scale, compelling architectural narrative and 100% crop quality. Every criterion >= 4/5, independent reviewer decision `ACCEPT`, and before/after evidence showing **substantive visual improvement**. These scores are human assessments, not algorithmically forged or inferred.
Either failed/pending => `VISUAL_QUALITY_NOT_APPROVED` / `GEOMETRY_NOT_APPROVED`, not a new V4.3 PDF or final approval.
