# S6x climb results

generation total 2760.8 s. Ratio = final / start objective (own objective).

| objective | N | puzzles | start median | final median | ratio median | ratio max |
|---|---|---|---|---|---|---|
| bm | 16 | 5 | 1669 | 314826 | 283.0x | 9349.8x |
| bm | 18 | 5 | 22720 | 1726657 | 51.4x | 25658.3x |
| hy | 16 | 5 | 250 | 81376 | 580.9x | 11076.3x |
| hy | 18 | 5 | 3019 | 419782 | 124.1x | 228077.7x |
| sat | 16 | 5 | 155 | 1817 | 4.7x | 11.7x |
| sat | 18 | 5 | 1361 | 4196 | 5.5x | 14.2x |
| sat2 | 14 | 5 | 462 | 1632 | 2.7x | 9.0x |
| sat2 | 16 | 5 | 290 | 1376 | 3.8x | 6.5x |
| sat2 | 18 | 5 | 1406 | 5000 | 3.3x | 57.7x |

Cross-measure medians (final puzzles): bitmask nodes / hybrid nodes / CaDiCaL conflicts / max-over-orders conflicts / CaDiCaL propagations / CP-SAT s

| group | N | bm nodes | hy nodes | sat conf | sat conf max-orders | sat props | cpsat s |
|---|---|---|---|---|---|---|---|
| bm | 16 | 314826 | 35700 | 2856 | 3878 | 82208 | 0.025 |
| bm | 18 | 1726657 | 289833 | 5161 | 5366 | 244904 | 0.040 |
| hy | 16 | 283488 | 81376 | 6937 | 7149 | 257236 | 0.034 |
| hy | 18 | 2132443 | 419782 | 12144 | 15844 | 830418 | 0.064 |
| sat | 16 | 1716 | 330 | 1817 | 1817 | 56185 | 0.009 |
| sat | 18 | 65992 | 18405 | 4196 | 4196 | 142507 | 0.021 |
| sat2 | 14 | 3310 | 692 | 477 | 1632 | 13046 | 0.008 |
| sat2 | 16 | 1811 | 295 | 231 | 1376 | 11558 | 0.005 |
| sat2 | 18 | 16326 | 3044 | 1698 | 5000 | 72491 | 0.020 |

Old S6 reference (see build_s6): DFS (bm/hy) climbs 16-417x median vs S5b-like baseline, SAT about 3.5-4.6x.

## S6m (objective: native match nodes)

generation total 1465.4 s.

| objective | N | puzzles | start median | final median | ratio median | ratio max | bitmask nodes median |
|---|---|---|---|---|---|---|---|
| mt | 12 | 5 | 39 | 2899 | 42.8x | 78.4x | 5397 |
| mt | 14 | 5 | 161 | 91293 | 353.8x | 1730.4x | 163197 |
| mt | 16 | 5 | 450 | 133533 | 263.9x | 2014.3x | 295710 |
| mt | 18 | 5 | 354 | 311570 | 1552.4x | 8918.0x | 1559702 |
