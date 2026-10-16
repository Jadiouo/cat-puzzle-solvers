"""S5b: unbiased unique-solution puzzles (N=12,14,16).  Run: .venv/bin/python -B -m bench.build_s5b

Same hill climb / guided moves as bench.build_s5, but the uniqueness test inside the generator is
SAT only (CaDiCaL153 classify, 10 s limit; timeout = "not better"). No bitmask/hybrid/dlx/native
solver is called during generation, so puzzles are not filtered by bitmask speed (S5's selection bias).
Phase 2 (after generation): bitmask classify (10 s) and CP-SAT classify as post-hoc checks, timings
recorded per puzzle; phase 3: same bitmask timing on S5 puzzles with equal N for comparison.
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
from . import check
from . import solvers  # noqa: F401  (must precede solver_sat: circular registration)
from .solver_sat import SatAdapter, CpSatAdapter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "suites", "S5b.json")
S5 = os.path.join(HERE, "suites", "S5.json")
SIZES = (12, 14, 16)
PER_N = 8
SAT = SatAdapter("pairwise", "cadical153")
CPSAT = CpSatAdapter(1)
GEN_TIMEOUT = 10.0
POST_TIMEOUT = 10.0


def classify(grid, timeout=GEN_TIMEOUT):
    r = SAT.solve(grid, "classify", timeout)
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


def post_check(n, grid, sol):
    """Run AFTER generation. Returns (ok, ref dict, bitmask record)."""
    from .solver_bitmask import BitmaskAdapter
    bm = BitmaskAdapter().solve(grid, "classify", POST_TIMEOUT)
    sat = SAT.solve(grid, "classify", 120)
    cp = CPSAT.solve(grid, "classify", 120)
    rec = {"bm_timeout": bm["status"] == "TIMEOUT" or bm["count"] is None,
           "bm_seconds": round(bm["elapsed"], 4), "bm_nodes": bm.get("nodes"),
           "bm_count": bm["count"]}
    sat_ok = sat["count"] == 1 and sat["solutions"][0] == sol
    cp_ok = cp["count"] == 1 and cp["solutions"][0] == sol
    rec["cpsat_seconds"] = round(cp["elapsed"], 4)
    ok = sat_ok and cp_ok and check.is_valid(grid, sol)
    if rec["bm_timeout"]:
        src = "SAT(cadical153) classify + CP-SAT classify, identical solution, bench.check valid; bitmask timed out (10 s), kept"
    else:
        ok = ok and bm["count"] == 1 and bm["solutions"][0] == sol
        src = "SAT(cadical153) classify + CP-SAT classify, identical solution, bench.check valid; bitmask classify agrees"
    return ok, {"count": 1, "source": src, "seconds": round(sat["elapsed"] + cp["elapsed"], 3)}, rec


def stats(xs, to):
    if not xs:
        return None
    return {"count": len(xs), "median": round(statistics.median(xs), 4), "max": round(max(xs), 4),
            "timeouts": sum(to)}


def main(per_n_budget=480, sizes=SIZES, attempt_s=120):
    t_start = time.perf_counter()
    cands, report = [], {}
    for n in sizes:                      # phase 1: SAT-only generation
        secs, ok, fail, lo_, hi_ = [], 0, 0, [], []
        t_n = time.perf_counter()
        seed = 0
        while ok < PER_N and time.perf_counter() - t_n < per_n_budget:
            seed += 1
            rng = random.Random(f"s5b:{n}:{seed}")
            t0 = time.perf_counter()
            res = make_unique(n, rng, deadline=t0 + attempt_s)
            dt = time.perf_counter() - t0
            if res is None:
                fail += 1
                print(n, seed, "fail", round(dt, 1), flush=True)
                continue
            reg, sol = res
            ok += 1
            secs.append(round(dt, 1))
            sz = region_sizes(reg, n)
            lo_.append(min(sz)); hi_.append(max(sz))
            cands.append((n, seed, reg, sol, sz))
            print(n, seed, "gen-ok", round(dt, 1), flush=True)
        report[str(n)] = {"generated": ok, "fail": fail, "seeds_tried": seed,
                          "gen_secs_total": round(time.perf_counter() - t_n, 1), "secs": secs}
    gen_total = round(time.perf_counter() - t_start, 1)
    puzzles = []
    for n, seed, reg, sol, sz in cands:   # phase 2: post-hoc checks
        grid = to_grid(reg, n)
        good, ref, rec = post_check(n, grid, sol)
        print(n, seed, "post", good, rec, flush=True)
        if not good:
            report[str(n)].setdefault("post_fail", []).append(seed)
            continue
        puzzles.append({"id": f"S5b-n{n}-s{seed}", "n": n, "regions": grid, "planted": list(sol),
                        "seed": seed, "ref": ref, "region_min": min(sz), "region_max": max(sz),
                        "posthoc": rec})
    puzzles.sort(key=lambda p: (p["n"], p["seed"]))
    # phase 3: S5 vs S5b bitmask timing, same N
    from .solver_bitmask import BitmaskAdapter
    bm = BitmaskAdapter()
    s5 = json.load(open(S5))["puzzles"]
    cmp = {}
    for n in sizes:
        a, ato = [], []
        for p in s5:
            if p["n"] == n:
                r = bm.solve(p["regions"], "classify", POST_TIMEOUT)
                a.append(r["elapsed"]); ato.append(r["status"] == "TIMEOUT" or r["count"] is None)
        b = [p["posthoc"]["bm_seconds"] for p in puzzles if p["n"] == n]
        bto = [p["posthoc"]["bm_timeout"] for p in puzzles if p["n"] == n]
        cmp[str(n)] = {"S5": stats(a, ato), "S5b": stats(b, bto)}
        print("cmp", n, cmp[str(n)], flush=True)
    for n in sizes:
        report[str(n)]["kept"] = sum(p["n"] == n for p in puzzles)
    suite = {"suite": "S5b",
             "description": "unique-solution puzzles N=12,14,16 from bench.build_s5b (guided hill climb, "
                            "SAT-only (cadical153) uniqueness test in the loop; bitmask/CP-SAT only post hoc), fixed seeds",
             "generation_report": report, "generation_total_s": gen_total,
             "bitmask_vs_S5": cmp, "puzzles": puzzles}
    with open(OUT, "w") as f:
        json.dump(suite, f, separators=(",", ":"))
    print(json.dumps(report), "gen_total", gen_total, "total", round(time.perf_counter() - t_start))


if __name__ == "__main__":
    a = sys.argv
    main(float(a[1]) if len(a) > 1 else 480)
