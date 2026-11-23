# 02 P0 alternatives with geometry provenance

All numbers are MEASURED_FROM_VERIFIED_SLICE: geometry arithmetic only; no design validity, egress or code compliance is implied. Source: hash-pinned slices (`data/t14s/source_slices`, unchanged, verified True). Parameters: landing depth 2.6 m and entry apron 2.6 x 2.6 m are the C-T14T builder values, not code requirements; deck width = escalator width (3.6 m) from the model.

## D-01 escalator landings (25)

End position: core 1, opening 20, outside_slab_outline 4.

| Option | What changes | Measured | Needs approval | Not measured |
|---|---|---|---|---|
| A local landing decks / bridges (study) | proposed new deck in the capsule opening or notch, verified slab and opening untouched in the model | new deck per landing 9.6-19.0 m2, 6.1-12.2 % of the 156 m2 opening, no column within any deck footprint, per-floor combined 18.6-37.9 m2 | yes (structure, opening, egress) | deck thickness against sections, truss/pit interplay, continuous clear width, fire/egress |
| B no-escalator operation | escalators stay as void and visual; vertical use by cores and lifts | verified cores connected on every floor except D-02 floors; lift lobbies T3/T4 connected; EV1/EV2/PL not assessed | yes (programme and thesis) | lift and stair capacity, evacuation |
| C relocate escalator geometry | move the escalator end onto verified slab | outward translation needed 12.1-14.7 m, the same order as the escalator length (9.8-12.4 m) | yes (verified model change) | structural and programme consequences |

The 24 capsule landings (opening or notch) are measured above; B1 to 1F starts inside core D, so A and C do not apply to it (a core would have to move). Per landing rows: `measurements/d01_escalator_landings.csv`. Section evidence for these options is UNVERIFIED (the V4.2 section sheets were not compared; WP0).

## D-02 cores without slab (3)

| Core | Core area on slab | Nearest verified slab | Apron 2.6 m on slab (S/N/W/E) |
|---|---|---|---|
| D02-2F-core-D | 0.0 m2 | 17.0 m | 0 % / 0 % / 0 % / 0 % |
| D02-7F-core-C | 0.0 m2 | 17.0 m | 0 % / 0 % / 0 % / 0 % |
| D02-7F-core-D | 0.0 m2 | 17.0 m | 0 % / 0 % / 0 % / 0 % |

- Option 1 keep as pass-through shaft (current drawing, marked not enterable): no geometry change; needs an egress and exit-capacity assessment by the user's engineers.
- Option 2 connect the core to slab: the nearest verified slab is 17.0 m away, so this is not a local apron but a deck or bridge of about 17 m: a structural study, not a drawing edit.

## D-03 lift entry rotations (15)

| Floor | Tube | Proposed turn | Apron on slab unrotated -> proposed | Blocked unrotated by |
|---|---|---|---|---|
| 2F | T3 | +45 deg | 2.9 % -> 100.0 % | tube:capW |
| 3F | T3 | +45 deg | 2.9 % -> 100.0 % | tube:capW |
| 4F | T3 | +45 deg | 2.9 % -> 100.0 % | tube:capW |
| 5F | T3 | +45 deg | 2.9 % -> 100.0 % | tube:capW |
| 6F | T3 | +45 deg | 2.9 % -> 100.0 % | tube:capW |
| 6F | T4 | -45 deg | 100.0 % -> 100.0 % | tube:capE |
| 7F | T4 | -45 deg | 22.2 % -> 100.0 % | tube:capE |
| 8F | T4 | -45 deg | 22.2 % -> 100.0 % | tube:capE |
| 9F | T4 | -45 deg | 22.2 % -> 100.0 % | tube:capE |
| 10F | T4 | -45 deg | 22.2 % -> 100.0 % | tube:capE |
| 11F | T4 | -45 deg | 22.2 % -> 100.0 % | tube:capE |
| 12F | T4 | -75 deg | 22.2 % -> 100.0 % | tube:capE |
| 13F | T4 | -45 deg | 22.2 % -> 100.0 % | tube:capE |
| 14F | T4 | -45 deg | 22.2 % -> 100.0 % | tube:capE |
| 15F | T4 | -45 deg | 22.2 % -> 100.0 % | tube:capE |

- Every unrotated apron overlaps the capsule tube (capW for T3, capE for T4). 6F T4 is 100 %% on slab but still touches capE.
- 12F T4: -45 deg leaves the apron 94.9 % on slab (the 12F void edge), -75 deg 100.0 %; that is why 12F differs.
- Keeping the 1F orientation (0 deg) is not usable in any of the 15 cases. Door clear opening, lobby threshold and tube interior conflicts are NOT measured (WP0).

## Programme measurements behind R-10 to R-16

| Floor | Hall m2 | Units (n, largest m2) | Support rooms (n, m2) | Programme m2 |
|---|---|---|---|---|
| 10F | 1660.1 | 6, 81.9 | 14, 146.6 | 화장실 51.4 · F&B 2118.2 |
| 11F | 1773.8 | 5, 83.2 | 2, 41.5 | 문화 2133.0 · 화장실 51.4 |
| 12F | 1585.8 | 3, 59.4 | 2, 37.8 | 문화 1790.9 · 화장실 51.4 |
| 13F | 1779.2 | 5, 83.2 | 2, 41.5 | 문화 2122.1 · 화장실 51.4 |
| 14F | 1933.3 | 3, 59.4 | 1, 16.2 | 문화 2122.0 · 화장실 51.4 |
| 6F | 463.5, 82.8, 363.3 | 5, 55.9 | 4, 50.2 | 판매 659.5 · 화장실 51.4 · F&B 489.3 · 정원 1078.8 |
| 15F | 759.9 | 1, 43.7 | 2, 21.8 | F&B 825.4 · 화장실 51.4 · 정원 1296.6 |

3F-9F: 54 units, 22 distinct unit areas; areas present on 5 or more of the 7 floors: [31.0].

## Printed-area finding (PDF)

Support rooms and restrooms without a printed area: 161 (all of them). Floors where a unit, hall or garden area is not printed: 12 (B1, 2F, 4F, 5F, 6F, 7F, 9F, 10F, 11F, 12F, 13F, 14F).
