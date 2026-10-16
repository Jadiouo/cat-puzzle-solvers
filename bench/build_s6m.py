"""S6m: puzzles adversarial to the Hall-matching-pruned DFS (native `match`).  Run: .venv/bin/python -B -m bench.build_s6m [secs]

Same climb as bench.build_s6x with objective mt = native match classify nodes (3 s cap); SAT uniqueness at every step;
SAT + CP-SAT double check at the end.  N=12,14,16,18 x 5.  Extra per-puzzle record: native bitmask nodes.
"""
import json
import os
import random
import statistics
import sys
import time

from levelgen.board import region_sizes, to_grid
from . import build_s6x as X
from .build_s5b import make_unique

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "suites", "S6m.json")
SIZES = (12, 14, 16, 18)
PER = 5
TOTAL = 38 * 60


def mt_score(grid):
    cnt, _, _, _ = X.sat_run(grid)
    if cnt != 1:
        return False, 0
    return True, X.native("match", grid)["nodes"] or 0


def main(budget=60.0):
    X.score = lambda obj, grid, perms: mt_score(grid)
    t_all = time.perf_counter()
    starts = {}
    for n in SIZES:
        lst, seed = [], 0
        while len(lst) < PER:
            seed += 1
            res = make_unique(n, random.Random(f"s6start:{n}:{seed}"), deadline=time.perf_counter() + 90)
            if res:
                lst.append((seed, res[0], res[1]))
        starts[n] = lst
        print("starts", n, round(time.perf_counter() - t_all, 1), flush=True)
    puzzles, done = [], 0
    for n in SIZES:
        for k, (seed, reg0, sol) in enumerate(starts[n]):
            remain = TOTAL - (time.perf_counter() - t_all)
            b = max(5.0, min(budget, remain / (len(SIZES) * PER - done) - 12.0))
            done += 1
            reg, info = X.climb(n, reg0, sol, "mt", random.Random(f"s6m:{n}:{k}"), b, None)
            grid = to_grid(reg, n)
            sz = region_sizes(reg, n)
            rec = X.measure(grid, sol, X.make_perms(n, n))
            m = X.native("match", grid, X.MEAS_T)
            rec["mt_nodes"], rec["mt_status"], rec["mt_seconds"] = m["nodes"], m["status"], round(m["elapsed"], 4)
            info["budget_s"] = round(b, 1)
            print(n, k, info, {x: rec[x] for x in ("mt_nodes", "bm_nodes", "hy_nodes", "sat_conflicts", "unique")}, flush=True)
            if not rec["unique"]:
                continue
            puzzles.append({"id": f"S6m-mt-n{n}-{k}", "group": "S6m-mt", "n": n, "regions": grid,
                            "planted": list(sol), "start_seed": seed, "climb": info,
                            "ref": {"count": 1, "source": "SAT(cadical153) + CP-SAT classify, identical "
                                    "solution, bench.check valid"},
                            "region_min": min(sz), "region_max": max(sz), "measure": rec})
    total = round(time.perf_counter() - t_all, 1)
    suite = {"suite": "S6m",
             "description": "adversarial unique-solution puzzles N=12,14,16,18 for the Hall-matching-pruned bitmask DFS "
                            "(native match nodes, 3 s eval cap); SAT uniqueness check at every step; SAT+CP-SAT double check; "
                            "fixed seeds (bench.build_s6m); measure also holds native bitmask/hybrid nodes",
             "params": {"per": PER, "sizes": SIZES, "climb_budget_s": budget, "eval_timeout_s": X.EVAL_T,
                        "total_budget_s": TOTAL},
             "total_s": total, "puzzles": puzzles}
    json.dump(suite, open(OUT, "w"), separators=(",", ":"))
    lines = ["", "## S6m (objective: native match nodes)", "", f"generation total {total} s.", "",
             "| objective | N | puzzles | start median | final median | ratio median | ratio max | bitmask nodes median |",
             "|---|---|---|---|---|---|---|---|"]
    for n in SIZES:
        ps = [p for p in puzzles if p["n"] == n]
        if not ps:
            continue
        st = [max(p["climb"]["start_score"], 1) for p in ps]
        fi = [p["climb"]["best"] for p in ps]
        ra = [f / s for f, s in zip(fi, st)]
        bm = statistics.median(p["measure"]["bm_nodes"] for p in ps)
        lines.append(f"| mt | {n} | {len(ps)} | {statistics.median(st):.0f} | {statistics.median(fi):.0f} | "
                     f"{statistics.median(ra):.1f}x | {max(ra):.1f}x | {bm:.0f} |")
    with open(os.path.join(os.path.dirname(HERE), "bench", "results", "s6x_climb.md"), "a") as f:
        f.write("\n".join(lines) + "\n")
    print("done", total, flush=True)


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 60.0)
