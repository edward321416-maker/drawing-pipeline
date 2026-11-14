# G-002 / Chrome ChatGPT Images — 실제 이미지 편집 프롬프트
기준: PR #25 Cycles **원본 이미지를 실제로 첨부**. 프롬프트만 입력하거나 텍스트 설명만 받으면 실행한 것으로 기록하지 않음.

### Prompt A / Urban Daylight
**Image 1 is an actual Blender Cycles render of the user's verified architectural design. EDIT this uploaded image, do not redesign/recreate another building.** Make this scene read as a **convincing professionally photographed built commercial building** in a real city, not a 3D model screenshot, illustration, low-poly game environment, or palette filter.

Architectural identity must remain the same as the image: exact view/camera and silhouette; the same visible floors, slab edges, dark vertical facade fins and horizontal bands, four tall corner cores, existing cylindrical circulation tubes, distinctive middle open garden, roof garden and existing circular rooftop openings; unchanged entrance and footprint. No new or removed floor, window row, slab, gap, tube, roof edge, bridge or stair. Treat these as immutable geometry.

**Actively improve the physical appearance of the BUILDING, not only the background:**
- deep but plausible glass reflection/transparency at actual facade glazing, subtle varied reflectance by viewing angle, convincing real construction-scale mullion depth without changing facade pattern
- physically credible concrete/metal visual finish with small surface variation and highlights, realistic ambient occlusion and contact shadows at existing geometry joins
- believable human-scale foreground paving, curb/road and daylight shadows; a few naturally scaled pedestrians only on plausible accessible ground; no crowd blocking the building
- replace toy-like round-sphere trees with realistic, detailed tree canopies while preserving their positions/volumes and actual roof/intermediate garden boundaries
- surrounding existing simple block context may become believable generic urban building surfaces and streetscape without claiming exact surveyed Dongdaemun/Sindang facades; preserve main spatial relationships and lens perspective
- natural editorial architectural photography: soft midday/afternoon sunlight, balanced whites, realistic subtle atmospheric depth, no over-sharpening or game-art light

Do NOT output an edit explanation, prompt or checklist as the main answer. Produce a **new edited image**. No titles, watermarks, labels or text inside. Keep 16:9 framing. If you cannot maintain the architectural form, say so and produce a **style study only** rather than silently change geometry. Report meaningful building-surface vs context changes separately after the image.

### Prompt B / Blue Hour
**Image 1 is the verified mesh-based Blender Cycles G-002 blue-hour render. Perform genuine image editing on this exact uploaded image.** It is currently far too dark and flat. Transform it into an **architectural photography-quality evening visualization**, not merely a brighter version of a CGI draft.

**Preserve identical geometric construction and original camera, slab/facade grid, four corner cores, T1–T4 tubes, midlevel garden, rooftop circles and base.** Only the lighting/material look and *non-architectural* surrounding details can change.

- blue dusk sky with balanced exposure; upper slabs, voids, tubes and rooftop must remain clearly legible even at 100% crop
- realistic warm but localized indoor light **only behind already existing real openings**; no invented lit-up window rows or uniform LED facade
- credible facade glass response and metal/concrete texture; restrained long shadows and reflected warm light
- photoreal street, street-level pedestrians, realistic foliage for present trees; no fake sports-car glamour, giant signage, neon overload, fog flood or sci-fi appearance
- background secondary to building; consistent perspective, believable natural scale, cinematic without darkness crushing black details

Produce the **actual edited image**, 16:9, no text/watermark. Do not edit the roof circles or floor divisions.

### Targeted correction prompts after observing any structural drift
**Facade**: "Edit only the surface realism/lighting of the existing facade. Use the uploaded Blender source as immutable registration reference. Restore the exact count and positions of horizontal orange facade bands, vertical glass divisions and floor edges. No other changes."
**Rooftop and void**: "Using source reference, correct only roof circular apertures, rooftop landscaping outline, middle garden slab boundaries and core silhouettes to be geometrically identical; preserve all improved materials, sky and human-scale context elsewhere."
**Trees and urban context**: "Select only vegetation and surrounding city/ground areas, not the tower. Replace spherical proxy foliage and gray untextured context volumes with photoreal natural vegetation, real-scale facades, paving and people. Maintain all existing positions, footprints and camera."
**Blue-hour exposure**: "Edit only exposure, sky color and localized interior lighting behind existing windows; maintain actual structural geometry and facade openings; reveal readable levels and garden without introducing lighting strips or new floors."

### Critical handoff constraints
1. Upload **actual image** (each under 20MB) via Chrome authenticated user session; optionally upload geometry lock reference separately.
2. First request both actual outputs A/B in separate conversations, download with Save. Do not accept text-only analysis as an edited PNG.
3. If editor selection is inaccurate, use before/after geometry verification; do not mark success from prompt compliance alone.
4. Output may be lower resolution than 4800×2700. Do not claim the 4800px original dpi for a smaller ChatGPT image.
5. Final quality is based on **the building itself** looking more like built architecture, with preserved geometry; rejecting raw GPT pixel drift is safer than passing fake design. Do NOT restore the original entire unedited building over the GPT result, because that defeats the user's requested retouch.
