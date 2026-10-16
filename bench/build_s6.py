"""S6: adversarial unique-solution puzzles.  Run: .venv/bin/python -B -m bench.build_s6 [secs_per_climb]

Start = SAT-only unique puzzle (bench.build_s5b.make_unique; the same 5 starts per N are used for all three
objectives).  Local search: recolour one non-cat boundary cell (keeps connectivity + size 3..2N); EVERY candidate
is checked unique by SAT (cadical153 classify, 10 s, timeout = reject) regardless of objective.  Accept if
objective >= current (plateau moves allowed); keep best.
  S6-bm : bitmask classify nodes     S6-hy : hybrid classify nodes     S6-sat : CaDiCaL classify conflicts
Phase 2: cross-measure bitmask / hybrid / SAT / CP-SAT (10 s each; SAT+CP-SAT uniqueness double check).
Phase 3: S5b-style baseline at the same N (N=10 generated here, N=12/14 taken from S5b.json, all re-measured).
"""
import json
import math
import os
import random
import statistics
import sys
import time

from levelgen.board import (D4, MIN_REGION, connected_without, max_region_size, region_sizes,
                            size_violation, to_grid)
from . import check
from .build_s5b import SAT, CPSAT, make_unique
from .solver_bitmask import BitmaskAdapter
from .solver_hybrid import HybridAdapter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "suites", "S6.json")
S5B = os.path.join(HERE, "suites", "S5b.json")
SIZES = tuple(int(x) for x in os.environ.get("S6_SIZES", "10,12,14").split(","))
PER = int(os.environ.get("S6_PER", "5"))
OBJS = ("bm", "hy", "sat")
BM, HY = BitmaskAdapter(), HybridAdapter()
EVAL_T = 3.0     # objective eval time cap (nodes at timeout still count as a score)
MEAS_T = 10.0


def score(obj, grid):
    """Returns (unique_by_SAT, objective value)."""
    r = SAT.solve(grid, "classify", 10.0)
    if r["count"] != 1:
        return False, 0
    if obj == "sat":
        return True, r["nodes"] or 0
    a = BM if obj == "bm" else HY
    q = a.solve(grid, "classify", EVAL_T)
    return True, q["nodes"] or 0


def climb(n, reg, sol, obj, rng, budget):
    lo, hi = MIN_REGION, max_region_size(n)
    cats = {r * n + sol[r] for r in range(n)}
    reg = list(reg)
    ok, cur = score(obj, to_grid(reg, n))
    assert ok
    best, best_reg, steps, acc = cur, list(reg), 0, 0
    t_end = time.perf_counter() + budget
    while time.perf_counter() < t_end:
        steps += 1
        x = rng.randrange(n * n)
        if x in cats:
            continue
        r, c = divmod(x, n)
        old = reg[x]
        nb = {reg[(r + dr) * n + c + dc] for dr, dc in D4
              if 0 <= r + dr < n and 0 <= c + dc < n} - {old}
        if not nb or not connected_without(reg, n, old, x):
            continue
        reg[x] = rng.choice(sorted(nb))
        if size_violation(reg, n, lo, hi) > 0:
            reg[x] = old
            continue
        ok, v = score(obj, to_grid(reg, n))
        if ok and v >= cur:
            cur = v
            acc += 1
            if v > best:
                best, best_reg = v, list(reg)
        else:
            reg[x] = old
    return best_reg, {"start_score": None, "best": best, "steps": steps, "accepted": acc}


def measure(grid, sol):
    n = len(grid)
    b = BM.solve(grid, "classify", MEAS_T)
    h = HY.solve(grid, "classify", MEAS_T)
    s = SAT.solve(grid, "classify", MEAS_T)
    c = CPSAT.solve(grid, "classify", MEAS_T)
    rec = {}
    for k, r in (("bm", b), ("hy", h), ("sat", s), ("cpsat", c)):
        rec[k + "_status"] = r["status"]
        rec[k + "_seconds"] = round(r["elapsed"], 4)
        rec[k + "_count"] = r["count"]
    rec["bm_nodes"], rec["hy_nodes"], rec["sat_conflicts"] = b["nodes"], h["nodes"], s["nodes"]
    # uniqueness double check (SAT + CP-SAT, long limit if the 10 s one did not finish)
    s2 = s if s["count"] is not None else SAT.solve(grid, "classify", 120)
    c2 = c if c["count"] is not None else CPSAT.solve(grid, "classify", 120)
    rec["unique"] = (s2["count"] == 1 and c2["count"] == 1 and s2["solutions"][0] == sol
                     and c2["solutions"][0] == sol and check.is_valid(grid, sol))
    return rec


def med(xs):
    return round(statistics.median(xs), 4) if xs else None


def spearman(a, b):
    def rk(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2
            i = j + 1
        return r
    ra, rb = rk(a), rk(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return round(num / den, 3) if den else None


def main(budget=40.0):
    t_all = time.perf_counter()
    starts, gen_s = {}, {}
    for n in SIZES:
        t0 = time.perf_counter()
        lst, seed = [], 0
        while len(lst) < PER:
            seed += 1
            rng = random.Random(f"s6start:{n}:{seed}")
            res = make_unique(n, rng, deadline=time.perf_counter() + 90)
            if res:
                lst.append((seed, res[0], res[1]))
        starts[n] = lst
        gen_s[n] = round(time.perf_counter() - t0, 1)
        print("starts", n, gen_s[n], flush=True)
    puzzles, rep = [], {}
    for n in SIZES:
        for obj in OBJS:
            t0 = time.perf_counter()
            for k, (seed, reg0, sol) in enumerate(starts[n]):
                rng = random.Random(f"s6:{n}:{obj}:{k}")
                reg, info = climb(n, reg0, sol, obj, rng, budget)
                grid = to_grid(reg, n)
                sz = region_sizes(reg, n)
                rec = measure(grid, sol)
                print(n, obj, k, info, {x: rec[x] for x in ("bm_nodes", "hy_nodes", "sat_conflicts", "unique")},
                      flush=True)
                if not rec["unique"]:
                    rep.setdefault(f"{n}-{obj}", {}).setdefault("rejected", []).append(k)
                    continue
                puzzles.append({"id": f"S6-{obj}-n{n}-{k}", "group": f"S6-{obj}", "n": n, "regions": grid,
                                "planted": list(sol), "start_seed": seed, "climb": info,
                                "ref": {"count": 1, "source": "SAT(cadical153) + CP-SAT classify, identical "
                                        "solution, bench.check valid"},
                                "region_min": min(sz), "region_max": max(sz), "measure": rec})
            rep.setdefault(f"{n}-{obj}", {})["secs"] = round(time.perf_counter() - t0, 1)
            rep[f"{n}-{obj}"]["kept"] = sum(p["n"] == n and p["group"] == f"S6-{obj}" for p in puzzles)
    # baseline
    base = []
    s5b = [p for p in json.load(open(S5B))["puzzles"]]
    for n in SIZES:
        if n == 10:
            for seed in range(1, 9):
                res = make_unique(n, random.Random(f"s6base:{n}:{seed}"), deadline=time.perf_counter() + 60)
                if res:
                    g = to_grid(res[0], n)
                    base.append({"n": n, "measure": measure(g, res[1])})
        else:
            for p in [q for q in s5b if q["n"] == n]:
                base.append({"n": n, "measure": measure(p["regions"], p["planted"])})
    print("baseline done", flush=True)
    # analysis
    ana = {}
    keys = (("bm", "bm_nodes"), ("hy", "hy_nodes"), ("sat", "sat_conflicts"))
    for n in SIZES:
        b = [x["measure"] for x in base if x["n"] == n]
        row = {"S5b-like": {"count": len(b)}}
        for m, nk in keys:
            row["S5b-like"][m + "_med_nodes"] = med([r[nk] for r in b])
            row["S5b-like"][m + "_med_s"] = med([r[m + "_seconds"] for r in b])
        row["S5b-like"]["cpsat_med_s"] = med([r["cpsat_seconds"] for r in b])
        for obj in OBJS:
            ps = [p["measure"] for p in puzzles if p["n"] == n and p["group"] == f"S6-{obj}"]
            d = {"count": len(ps)}
            for m, nk in keys:
                d[m + "_med_nodes"] = med([r[nk] for r in ps])
                d[m + "_med_s"] = med([r[m + "_seconds"] for r in ps])
                d[m + "_timeouts"] = sum(r[m + "_status"] == "TIMEOUT" for r in ps)
            d["cpsat_med_s"] = med([r["cpsat_seconds"] for r in ps])
            d["cpsat_timeouts"] = sum(r["cpsat_status"] == "TIMEOUT" for r in ps)
            base_nodes = row["S5b-like"][obj + "_med_nodes"]
            d["target_ratio_vs_base"] = round(d[obj + "_med_nodes"] / base_nodes, 1) if base_nodes and d[obj + "_med_nodes"] else None
            row["S6-" + obj] = d
        ana[str(n)] = row
    allm = [p["measure"] for p in puzzles] + [x["measure"] for x in base]
    ana["spearman_all"] = {"bm_vs_hy": spearman([r["bm_nodes"] for r in allm], [r["hy_nodes"] for r in allm]),
                           "bm_vs_sat": spearman([r["bm_nodes"] for r in allm], [r["sat_conflicts"] for r in allm]),
                           "hy_vs_sat": spearman([r["hy_nodes"] for r in allm], [r["sat_conflicts"] for r in allm]),
                           "sat_vs_cpsat_s": spearman([r["sat_conflicts"] for r in allm], [r["cpsat_seconds"] for r in allm])}
    suite = {"suite": "S6",
             "description": "adversarial unique-solution puzzles N=10,12,14: local search maximising bitmask nodes (S6-bm), "
                            "hybrid nodes (S6-hy) or CaDiCaL conflicts (S6-sat); SAT uniqueness check at every step; "
                            "SAT+CP-SAT double check; fixed seeds (bench.build_s6)",
             "budget_per_climb_s": budget, "start_gen_s": gen_s, "generation_report": rep,
             "baseline": base, "analysis": ana, "puzzles": puzzles,
             "total_s": round(time.perf_counter() - t_all, 1)}
    with open(OUT, "w") as f:
        json.dump(suite, f, separators=(",", ":"))
    print(json.dumps(ana, indent=1), "total", suite["total_s"])


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 40.0)
