"""S5: unique-solution puzzles for N=11..16.  Run: .venv/bin/python -B -m bench.build_s5

Generator = levelgen-style hill climb (planted solution -> grown connected regions -> single-cell
boundary moves until unique) with two changes:
 1. uniqueness test = BitmaskAdapter.classify (fast, capped at 2 solutions, short timeout; a
    timeout counts as "not better" and the move is undone). No slow solver in the loop.
 2. guided moves: the second solution found by classify is kept; with prob 0.8 the move is a
    boundary cell where that second solution has a cat that the planted one does not (re-colouring
    exactly such a cell is the only single-cell move that can invalidate it), else a random cell.
Acceptance: size violation (3..2N) must not rise; solution count (1 or 2+) must not rise.
Confirmation (independent families): BitmaskAdapter classify == 1 solution, SAT (CaDiCaL)
classify == 1 solution, identical to planted; bench.check rule check; bench.reference
(row DFS) as a third check for N<=12 or whatever fits in its 20 s budget.
"""
import json
import os
import random
import statistics
import sys
import time

from levelgen.board import (D4, MIN_REGION, connected_without, max_region_size,
                            region_sizes, size_violation, to_grid)
from levelgen.generate import grow, rand_solution
from . import check, reference
from .solver_bitmask import BitmaskAdapter
from . import solvers  # noqa: F401  (must precede solver_sat: circular registration)
from .solver_sat import SatAdapter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "suites", "S5.json")
SIZES = (11, 12, 13, 14, 15, 16)
PER_N = 10
BM = BitmaskAdapter()
SAT = SatAdapter("pairwise", "cadical153")


def classify(grid, timeout=2.0):
    r = BM.solve(grid, "classify", timeout)
    return r["count"], r["solutions"]


def make_unique(n, rng, deadline, max_restarts=40, stall_limit=4000):
    lo, hi = MIN_REGION, max_region_size(n)
    for _ in range(max_restarts):
        sol = rand_solution(n, rng)
        reg = grow(n, sol, rng)
        cats = {r * n + sol[r] for r in range(n)}
        sv = size_violation(reg, n, lo, hi)
        cnt, sols = classify(to_grid(reg, n))
        cnt = 99 if cnt is None else cnt
        stall = 0
        while (sv, cnt) != (0, 1) and stall < stall_limit:
            if time.perf_counter() > deadline:
                return None
            if sv == 0 and cnt >= 2 and sols and rng.random() < 0.8:
                other = next((s for s in sols if list(s) != sol), None)
                pool = [r * n + other[r] for r in range(n) if other[r] != sol[r]] if other else []
                x = rng.choice(pool) if pool else rng.randrange(n * n)
            else:
                x = rng.randrange(n * n)
            if x in cats:
                stall += 1
                continue
            r, c = divmod(x, n)
            old = reg[x]
            nb = {reg[(r + dr) * n + c + dc] for dr, dc in D4
                  if 0 <= r + dr < n and 0 <= c + dc < n} - {old}
            if not nb or not connected_without(reg, n, old, x):
                stall += 1
                continue
            reg[x] = rng.choice(sorted(nb))
            v = size_violation(reg, n, lo, hi)
            if v > sv:
                reg[x] = old
                stall += 1
                continue
            if v > 0:
                nc, ns = 99, []
            else:
                nc, ns = classify(to_grid(reg, n))
                nc = 99 if nc is None else nc
            if (v, nc) <= (sv, cnt):
                stall = 0 if (v, nc) < (sv, cnt) else stall + 1
                sv, cnt = v, nc
                if v == 0:
                    sols = ns or sols
                    if nc == 1:
                        sols = ns
            else:
                reg[x] = old
                stall += 1
        if (sv, cnt) == (0, 1):
            return reg, sol
    return None


def confirm(n, grid, sol):
    a = BM.solve(grid, "classify", 120)
    b = SAT.solve(grid, "classify", 120)
    ok = (a["count"] == 1 and b["count"] == 1 and a["solutions"][0] == sol
          and b["solutions"][0] == sol and check.is_valid(grid, sol))
    src = "bitmask classify + SAT(cadical153) classify, identical solution, bench.check valid"
    cnt = 1 if ok else None
    if ok and n <= 13:
        rc = reference.count_solutions(grid, time_limit=20)
        if rc is not None:
            ok = ok and rc == 1
            src += " + bench.reference row DFS"
    return ok, {"count": 1, "source": src,
                "seconds": round(a["elapsed"] + b["elapsed"], 3)}


def main(budget_total=2100, sizes=SIZES, attempt_s=90):
    t_start = time.perf_counter()
    puzzles, report = [], {}
    per_n_budget = budget_total / len(sizes)
    prev = {}
    if len(sizes) < len(SIZES) and os.path.exists(OUT):   # partial rerun: keep other sizes
        prev = json.load(open(OUT))
        puzzles = [p for p in prev['puzzles'] if p['n'] not in sizes]
        report = {k: v for k, v in prev['generation_report'].items() if int(k) not in sizes}
    for n in sizes:
        secs, ok, fail, sizes_lo, sizes_hi = [], 0, 0, [], []
        t_n = time.perf_counter()
        seed = 0
        while ok < PER_N and time.perf_counter() - t_n < per_n_budget:
            seed += 1
            rng = random.Random(f"s5:{n}:{seed}")
            t0 = time.perf_counter()
            res = make_unique(n, rng, deadline=t0 + attempt_s)
            dt = time.perf_counter() - t0
            if res is None:
                fail += 1
                print(n, seed, "fail", round(dt, 1), flush=True)
                continue
            reg, sol = res
            grid = to_grid(reg, n)
            good, ref = confirm(n, grid, sol)
            if not good:
                fail += 1
                print(n, seed, "confirm-fail", flush=True)
                continue
            ok += 1
            secs.append(round(dt, 1))
            sz = region_sizes(reg, n)
            sizes_lo.append(min(sz)); sizes_hi.append(max(sz))
            puzzles.append({"id": f"S5-n{n}-s{seed}", "n": n, "regions": grid,
                            "planted": list(sol), "seed": seed, "ref": ref,
                            "region_min": min(sz), "region_max": max(sz)})
            print(n, seed, "ok", round(dt, 1), min(sz), max(sz), flush=True)
        report[str(n)] = {"ok": ok, "fail": fail, "seeds_tried": seed,
                          "success_rate": round(ok / seed, 3) if seed else 0,
                          "secs_mean": round(statistics.mean(secs), 1) if secs else None,
                          "secs_max": max(secs) if secs else None, "secs": secs,
                          "region_size_min": min(sizes_lo) if sizes_lo else None,
                          "region_size_max": max(sizes_hi) if sizes_hi else None}
    puzzles.sort(key=lambda p: (p["n"], p["seed"]))
    report = dict(sorted(report.items(), key=lambda kv: int(kv[0])))
    suite = {"suite": "S5",
             "description": "unique-solution puzzles N=11..16 from bench.build_s5 (guided hill climb, "
                            "bitmask uniqueness test, SAT+bitmask confirmed), fixed seeds",
             "generation_report": report, "puzzles": puzzles}
    with open(OUT, "w") as f:
        json.dump(suite, f, separators=(",", ":"))
    print(json.dumps(report, indent=1), "total", round(time.perf_counter() - t_start))


if __name__ == "__main__":
    # usage: build_s5 [total_budget_s] [sizes comma list] [attempt_deadline_s]
    a = sys.argv
    main(float(a[1]) if len(a) > 1 else 2100,
         tuple(int(x) for x in a[2].split(",")) if len(a) > 2 else SIZES,
         float(a[3]) if len(a) > 3 else 90)
