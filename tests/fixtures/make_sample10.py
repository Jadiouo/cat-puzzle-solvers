"""Regenerate tests/fixtures/sample10.json (self-generated 10x10 fixture).

Run from the repo root:  python3 -B tests/fixtures/make_sample10.py
Board: levelgen.generate.generate(10, SEED, None) (deterministic).
Annotations are added programmatically:
  observed_cats    = one correct cat in the last row
  observed_crosses = a few cells that are NOT cats in the unique solution,
                     plus one WRONG cross on the solution cat of row 1
                     (so trust-all becomes UNSAT, base/trust-cats stay UNIQUE).
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from levelgen.generate import generate  # noqa: E402

SEED = 1
N = 10


def build():
    g = generate(N, SEED, None)
    sol = g["solution"]
    letters = "ABCDEFGHIJ"
    rng = random.Random(f"sample10-marks:{SEED}")
    wrong = [1, sol[1]]
    pool = [[r, c] for r in range(N) for c in range(N) if sol[r] != c and [r, c] != wrong]
    crosses = sorted(rng.sample(pool, 30) + [wrong])
    return {
        "schema_version": "1.0",
        "id": "sample10_generated",
        "size": N,
        "regions": [[letters[x] for x in row] for row in g["regions"]],
        "fixed_cats": [],
        "blocked_cells": [],
        "annotations": {"observed_cats": [[N - 1, sol[N - 1]]], "observed_crosses": crosses},
        "source": {"kind": "generated", "generator": "levelgen.generate.generate(size=10, seed=1, target=None)",
                   "seed": SEED, "annotations": "synthetic; one deliberately wrong cross on the solution cat of row 1"},
        "notes": ["Coordinates are zero-based.", "Base constraints ignore observed marks.",
                  "observed_crosses contains one deliberately wrong cross, so trust-all is UNSAT."],
    }


if __name__ == "__main__":
    out = Path(__file__).with_name("sample10.json")
    out.write_text(json.dumps(build(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(out)
