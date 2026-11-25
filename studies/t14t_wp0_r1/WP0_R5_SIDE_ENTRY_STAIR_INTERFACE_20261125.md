# WP0 R5 — Keep existing stair vestibule orientation; test side-entry bridges

Status: `E2_SIDE_ENTRY_GEOMETRY_CANDIDATE / USER_DIRECTION_DECISION_PENDING / STRUCTURAL_AND_EGRESS_HOLD / PROTECTED_SOURCE_UNCHANGED`.
User has previously approved functioning escalators, all 3 floor-accessible cores, open-space-preserving column-free bridge priority, and research only (no verified geometry changes).

## New direct source findings

- `docs/pipeline_discovery.md` lines 22–36,50: the full-building GLB is an architectural representation model; `A-VERT-STRS_A~D` are solid boxes, not detailed stairs. Walls/doors/room subdivision are not detailed in that GLB. The separate tagged 1F master is the detailed reference. The local full building GLB documented at `D:\Users\admin\Desktop\5-2\설계스튜디오\중간발표\07_representation\render\out\GMC-ZZ-ZZ-M3-0701.glb` has not been directly opened in this runtime. Drive searches for exact GLB/extracted model_world.npz/model_objects.json/m_1f_source.json names found no results. Do not conflate unavailable raw mesh and actual missing architectural/structural details. Existing 1F master JSON IS accessible in GitHub.
- PR30 pinned `1164fc0f58d943598d8e48146a02fcb3214c852e`: `engine/model/m_1f_source.json` stairs C=[39,-18,45,-12], D=[-9,-18,-3,-12], same XY bounding extents as upper-floor core slice boxes. `engine/symbols/stair_core.py` lines 78–199,203: C vestibule W, D vestibule E, outer door centered unless offset. Source `engine/model/design_adjustments.json`: only core B has an approved outer-door offset (-2.3m); no C/D offsets. Therefore original design convention implies C candidate door (39,-15) and D (-3,-15), NOT north centered. This is a proposed transfer of the approved 1F orientation, not existing upper-floor doors.
- `AGENTS.md` §3: 4-flight square stair and vestibule, inner door directly facing main landing. `engine/model/params.yaml` stair_core: 0.25m nominal wall, 1.6m vestibule, 0.15m partition, 1.2m flight and nominal door, 0.28m tread, 0.18m riser parameter, originally 6m FTF. `engine/reports/stage2_코어심볼_검토.md`: C/D nominal 36-step capacity and 8.4m2 vestibule. These are historic design parameters, not newly verified legal requirements.
- Local nominal candidate stair capacity per existing generator arithmetic for a 6m square: [6,12,6,12] possible counts. 6.0m FTF needs ceil(6/.18)=34 risers; 5.0m FTF needs 28. For 5.0006m also 28, and 4.9994m 28. Illustrative four-flight counts [6,11,6,11] at 6m and [6,8,6,8] at 5m satisfy nominal count limits, not exact stair fit, uniform landing geometry, inter-flight headroom, usable tread, fire/egress compliance or actual constructed stair. Do not treat maximum capacity as actual step count; detailed stairs must be independently generated for each FTF.

## Measured reversible floorplan alternatives
All coordinates in model metres; deck width 2.4m gross. Bridge straight run remains 17m with no intermediate column assumed, NOT structurally established.
D variants (C mirrored around x=18):
- N0 prior north entry: [-7.2,-12,-4.8,5], 40.80m2/core, 122.40m2 total. Would need different internal vestibule/stair entry arrangement or north access redesign; not default.
- E1 central wrap: [-7.2,-12,-4.8,5], [-4.8,-12,-0.6,-9.6], [-3,-16.2,-0.6,-12], 60.96m2/core, 182.88m2/3.
- E2 shifted wrap: [-5.4,-12,-3,5], [-3,-12,-0.6,-9.6], [-3,-16.2,-0.6,-12], 56.64m2/core, 169.92m2/3. Additional 47.52m2 vs N0; saves 12.96m2 vs E1. For C mirror X = 36-X: [39,-12,41.4,5], [36.6,-12,39,-9.6], [36.6,-16.2,39,-12].
- E2 side door nominal aperture at y=-15.6..-14.4 on x=-3 (D) or x=39 (C), using old 1F 1.2m nominal parameter; actual wall opening, fire door and clear opening not approved. Door swing and net usable route width remain unknown; potential local widening needed.

Independent exact (not R3 simplified) projection ring assembly, 1cm endpoint key tolerance; no simplification, polygon clipping of source rings against candidate rectangles; source net areas 2002.452110m2 2F and 1415.618122m2 7F; match published 2002.5/1415.6 rounding.
| Floor/core | N0 nearest column bbox (m) | E1 nearest column bbox (m) | E2 nearest column bbox (m) | E2 source slab overlap (m2) | E2 Y=5 edge contact (m) |
|---|---:|---:|---:|---:|---:|
|2F D|0.752|0.752|0.761|0.00246|2.400|
|7F D|0.752|0.752|0.761|0.00141|2.400|
|7F C|0.749|0.210|0.210|0.00404|2.400|

Tiny nonzero overlaps are source coordinate boundary tolerances, not validated bearing. 0 interior cut-line hits (each candidate rectangle tested inset 5mm, clipped segment length >5mm) for all 9 option/floor-core cases. This is not solid-geometry intersection analysis or full 3D clearance; linework screening alone misses containment, near-boundary collisions, unsliced objects, guards, etc. 7F C turning corner near A-STRC_column_27 is critical (0.210m). The extra local wrap may require torsional support/end frame or new support, so it does NOT validate OS1 structural priority; compare stiffness, reactions, and both end attachments with actual engineering data. No structural member sizing because load/cross-section/reinforcement/support details unavailable.

## Decision needed (not approval of geometry)
Recommend E2 direction as it retains C west/D east vestibule layout and avoids arbitrary 90-degree stair-core rotation. Compare more area and corner complexity vs N0 smaller footprint and redesigned internal core continuity. User chooses whether to preserve side entry or consider north-entry redesign; no original wall opening/slab construction/structure change approved. Before any exact change, produce real 3D stair stack with FTF-specific risers, candidate door geometry, circulation width and OS1 structural/egress verification. Do not close D02/X-02/2F-01/7F-01/R-02, or any of the 25 D01 escalator landing failures.

## Deliverable
`R5_SIDE_ENTRY_FOCUS_PLAN_SOURCE_OVERLAY.svg` on study branch: 3 focus plans assembled from all raw projection loop segments plus local source element linework, N0 dashed, E2 shaded, side door proposal dashed without removing original wall. Editable presentation study, not final CAD; exact text connector readback passed. No local PDF or render QA was performed for R5. Previous R4 local artifacts unchanged.
