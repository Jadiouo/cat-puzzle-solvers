# Archive: early game prototypes

Not part of the solver study. Kept for history only.

- `prototype/` — a single-file browser game with a 100-level campaign (`cat-game-prototype.html`, open it directly). `build_campaign.py` rebuilds the campaign with the `cat_solver` package; run it from the repository root: `python3 archive/prototype/build_campaign.py`.
- `playtest/` — a page of 12 generated puzzles with difficulty scores, used for informal playtesting (`python3 -B build_playtest.py` inside the folder rebuilds it).

The current interactive demo is in [`docs/`](../docs/) and live at https://jadiouo.github.io/cat-puzzle-solvers/.
