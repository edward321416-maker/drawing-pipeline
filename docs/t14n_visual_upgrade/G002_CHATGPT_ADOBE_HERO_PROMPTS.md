# C-T14N | ChatGPT/Adobe G-002 image-edit request — award-level architectural visualization

## Required actual image inputs (no filename-only handoff)
1. **Image 1: actual G-002 source JPG** — `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14L\docs\t14m_v43\retouch\G-002\input\G002_source.jpg`
2. **Image 2: structural mask, reference only** — `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14L\docs\t14m_v43\retouch\G-002\input\G002_structure_lock_reference.png` (must not appear in output)
3. **Image 3: silhouette/void reference** — `D:\Users\admin\Desktop\중간마감\drawing-pipeline-T14L\docs\t14m_v43\retouch\G-002\input\G002_building_silhouette.png`
4. Optional: verified, copyright-permitted actual site photos and own architecture 3D passes.
5. Optional: official 2026 Architizer awards references cited in the Art Direction doc for **craft only**, never replicate the architecture.

**Critical precondition:** if the model lacks real source image pixels, report inability and stop. Input 1 is the target image; input 2/3 are instructions, not compositing assets.

## Prompt — A: Editorial daytime architectural competition HERO (first choice)

Edit the **supplied architecture itself** as a serious professional architectural-visualization commission. This is not a simple color grade, watercolor sketch, generic AI skyscraper, fantasy city or a different design.

Retain the camera, 16:9 frame, projection, building outline and spatial identity of Image 1. The actual design is a 3D fractal commercial architecture that turns the street into vertical public space. Its distinct architectural logic is the multiple visible vertical circulation tubes, upper-floor accessibility, porosity and voids. Present *these existing elements* with exceptional clarity, rather than disguising the building as an anonymous generic glass tower.

Create the photographic experience of a highly crafted international architecture competition HERO render:
- believable natural daylight and one consistent sun direction; soft but tangible contact shadows on architecture and ground
- physically plausible material response where source material assignments are clear, fine tonal separation at all facade depths and slab edges
- subtle reflections and transparency only at documented glazing; clearly legible foreground/midground/background with atmospheric perspective
- human occupation and pedestrian scale only in existing confirmed accessible ground/public areas
- urban context that looks lived-in and geographically plausible. If actual Sindang/Dongdaemun site evidence is unavailable, use restrained non-identifiable conceptual context, not a fabricated claim of exact geography
- visual hierarchy: architecture 70%, public street/people 20%, surrounding city and atmosphere 10%; these are communication priorities, not pixel/area requirements
- restrained editorial palette with deep but readable shadows, natural highlights, no excessive bloom, fog, saturated sunset, fake detail, plastic surfaces, or artificial over-sharpening

**IMMUTABLE:** exactly preserve 17 levels B2–15F, source-visible floorplate edges, facade rhythm, four corner cores, T1–T4 tubes, existing voids, middle garden, roof openings, setbacks, base and the camera. No added doors/windows/stairs/skybridges/balconies/slabs/structural members/roof detail. No change in the number, location, or geometry of any documented architectural element. Do not invent hidden components or claims about the real construction material.

Deliver a genuinely transformed architectural environment (not merely stronger contrast), with the building still geometrically identical. If precise preservation is impossible, return a clearly marked **style study only**, not a geometrically approved architectural render. Output PNG, no labels or fake logos. Record any apparent risk areas and provide a change list.

## Prompt — B: Blue-hour public life HERO (second option)

Using the **same original architectural target**, produce a blue-hour competition visualization in which the actual existing public ground floor and vertical circulation reveal the idea of a city street rising into a building. Preserve every geometry constraint from Prompt A. Use deep blue ambient dusk and warm human-scale light only within verified open/occupied zones; subtle people and city life with photographic scale. Credible reflective materials, warm/cool balance, contact shadow and ambient occlusion. No imaginary mezzanines, bridges, glazing, stairs, new terraces, moving tubes or moving the camera. Treat background-only creativity separately from architectural design authority. Output an original PNG and a source-versus-output caveat list.

## Review and handoff instructions

- For both options deliver: actual `A_raw.png`/`B_raw.png`, prompts, export receipt, dimensions, SHA256.
- Show full-size source, both options, and 100% zoom crops of base / tubes / upper floors / voids / garden / roof.
- Never claim success from a small color difference. Actual artistic depth, material, light, scale and urban scene must be recognizably stronger.
- If model cannot render the same camera/material without geometry drift, keep AI output as **conceptual art direction reference** only and composite only safe background/atmosphere layers behind the source-authoritative architecture. The native source geometry (not the AI image) always wins technical disagreements.
- Source JPG 2400×1350. At 396mm print width, effective ~154dpi; a native verified 4700+ px Blender rerender or smaller placement is needed for 300dpi. AI upscaling is not verified architecture detail.
