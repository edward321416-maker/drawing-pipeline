# C-T14Q — 위치 정합 Blender 기준 렌더용 ChatGPT 편집 프롬프트

기준 이미지는 `G002_A/B ... SITE_CONTEXT_BASE` 4800×2700 Blender Cycles 렌더의 업로드용 JPEG 복사본이다. PR #26의 프롬프트와 달리 **도로·보도·횡단보도·이웃 건물·가로수·태양 방향이 이미 Blender 기준본에 위치 정합으로 들어 있다.** ChatGPT는 새 요소를 만들지 말고 **재질·빛·질감·대기감·사람 스케일**만 보강한다. 편집 결과는 형상 드리프트를 먼저 검사하고, 통과 전에는 최종본이 아니다.

## 공통 사실 블록 (프롬프트에 그대로 쓰는 문장)
- 장소: 서울 중구 장충단로 247 일대(동대문역사문화공원역과 DDP 사이, 동대문 패션타운 남서 끝). **정확한 실제 입면 재현은 금지**, 일반적인 한국 도심 상업지구 질감.
- 카메라: 대지의 남남동 약 316 m, 지상 약 128 m 높이에서 북북서(방위 332°)를 보는 조감. 태양: 10월 중순 15:30(Daylight, 방위 234°·고도 25°) / 18:12(Blue Hour, 고도 -4°).
- **시각화 가정(사실 아님)**: 이웃 건물 높이의 약 86%, 도로 폭, 가로수 위치·수종, 가로등 위치는 추정이다.

## Prompt A — Urban Daylight (ChatGPT에 붙여넣기)
Image 1 is a Blender Cycles render of a verified architectural design placed at its real location in the Dongdaemun commercial district of Seoul, with a registered street grid, sidewalks, crosswalks, neighbouring blocks and the correct late-October 15:30 sun direction (sun low in the south-west, behind and left of the camera). EDIT this exact uploaded image into a convincing professional architectural photograph. Do not redesign or recreate the scene.

GEOMETRY LOCK (highest priority): keep the exact camera, framing and perspective. Keep every building volume, roofline and height, every street, lane marking, crosswalk, sidewalk edge and tree position exactly where they are. For the main tower keep the floor count, slab edges, four tall corner cores, cylindrical circulation tubes, mid-level open garden, roof garden, the circular roof openings, the entrance ramp and footprint unchanged. Do not add, remove, move or resize any building, floor, window row, core, tube, road, crosswalk, tree or vehicle lane. Do not change the ground shape in front of the tower.

IMPROVE (surfaces and light only): realistic glass reflections and transparency on the real glazing, concrete and metal surface texture with small variation, accurate soft contact shadows and sun-direction shadows, believable asphalt, granite paving and kerb detail, natural tree canopies with varied leaf colour (species not identifiable), generic Korean commercial-district facades on the neighbouring blocks (stone panel, glass curtain wall, tile, banner and LED signage bands WITHOUT legible text or brand names), subtle distance haze for the far buildings, a small number of correctly scaled pedestrians on sidewalks and a few cars on the roads. No crowd blocking the tower.

Natural editorial photography: balanced exposure, soft film-like contrast, no HDR halos, no over-sharpening, no game-engine look. Output a new edited image, 16:9, no text, no watermark, no title. If you cannot keep the architecture identical, say so and produce a style study only. Afterwards list separately what changed on the tower surface versus the surroundings.

## Prompt B — Blue Hour
Image 1 is a Blender Cycles blue-hour render of a verified architectural design placed at its real location in the Dongdaemun commercial district of Seoul (sun about 4 degrees below the horizon, deep blue twilight, street lamps and lit office windows already assumed). EDIT this exact uploaded image into an architectural-photography-quality evening photograph. Do not redesign or recreate the scene.

GEOMETRY LOCK (highest priority): same as above - identical camera, framing, perspective, tower volume, floors, cores, tubes, mid-level garden, roof openings, entrance ramp, neighbouring volumes, roads, crosswalks and tree positions. Do not add or remove buildings, floors, windows rows, roads or trees. The distribution of lit windows may be refined but do not invent glowing floors, LED facades or signboards on the tower.

IMPROVE: balanced blue-hour exposure with readable tower floors, voids, tubes and roof garden at 100%; credible warm light only behind real openings; realistic glass response and concrete texture; warm street lamps with believable light spill and slightly wet asphalt reflections; blue-grey ambient fill on shadows; natural foliage lit from below by lamps; a few small pedestrians and cars with light trails kept subtle; generic neighbouring facades with banner and LED signage bands without legible text or brands; no neon overload, no fog flood, no sci-fi.

Output a new edited image, 16:9, no text, no watermark. If you cannot keep the architecture identical, say so and produce a style study only. Afterwards list separately what changed on the tower versus the surroundings.

## 영역별 재편집 (드리프트가 관찰될 때만, 해당 영역을 선택해서)
- 입면: "Edit only the surface realism and lighting of the selected facade. Treat the uploaded Blender render as an immutable registration reference and restore the exact floor-band count, vertical fin rhythm and slab edges. Change nothing else."
- 지붕·보이드: "Correct only the roof openings, roof-garden outline, mid-level garden slab boundaries and core silhouettes so they are geometrically identical to the uploaded Blender render. Keep the improved materials elsewhere."
- 지상층·입구 램프: "Restore the entrance ramp, forecourt shape and ground-floor columns exactly as in the Blender render; only improve paving texture and shadows."
- 주변: "Select only roads, sidewalks and neighbouring blocks. Keep every block volume, height, lane and crosswalk as in the Blender render; improve only textures, signage bands without legible text, and lighting."

## 기록 원칙
- 실제 ChatGPT가 편집한 PNG를 다운로드한 경우에만 성공으로 기록한다. 업로드 JPEG의 SHA256, 대화 URL, 다운로드 PNG의 SHA256·크기·해상도를 남긴다.
- ChatGPT 출력 해상도는 보통 1672×941이다. 4800 px 원본 해상도를 가졌다고 주장하지 않는다.
