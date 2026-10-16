"""S6x: larger adversarial unique-solution puzzles.  Run: .venv/bin/python -B -m bench.build_s6x [secs_per_climb]

Same hill climb as bench.build_s6 (recolour one non-cat boundary cell, every candidate must be unique by SAT),
but objectives are evaluated faster and sizes are larger:
  bm  : native C++ bitmask classify nodes        hy : native C++ hybrid classify nodes
  sat : CaDiCaL153 classify conflicts (identity variable order)
  sat2: MAX over K fixed random variable relabelings + clause shuffles of CaDiCaL classify conflicts
        (robust objective: a puzzle cannot be hard only for one lucky variable order).
        Chosen over propagations because propagations scale with conflicts (same blunt signal), while max-over-orders
        directly measures "hard whatever the order"; propagations are still recorded for every puzzle.
Groups: S6x-{bm,hy,sat} at N=16,18 ; S6x-sat2 at N=14,16,18.  Starts for N=14 are the S6 starts (same seeds).
"""
import json
import os
import random
import statistics
import sys
import time

from levelgen.board import (D4, MIN_REGION, connected_without, max_region_size, region_sizes,
                            size_violation, to_grid)
from . import check
from . import solvers  # noqa: F401  (must precede solver_sat)
from .build_s5b import SAT, CPSAT, make_unique
from .solver_native import run_batch

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "suites", "S6x.json")
PER = int(os.environ.get("S6X_PER", "5"))
MAIN_SIZES = tuple(int(x) for x in os.environ.get("S6X_SIZES", "16,18").split(","))
SAT2_SIZES = tuple(int(x) for x in os.environ.get("S6X_SAT2_SIZES", "14,16,18").split(","))
K_ORDERS = 3
EVAL_T = 3.0
MEAS_T = 10.0
TOTAL_BUDGET = float(os.environ.get("S6X_TOTAL_S", str(70 * 60)))


def native(solver, grid, t=EVAL_T):
    r = run_batch(solver, "classify", t, [("p", grid)])[0]
    return r


def sat_run(grid, perm=None, seed=0):
    """CaDiCaL classify with optional variable relabeling. Returns (count, conflicts, propagations, sols)."""
    from pysat.solvers import Solver
    n = len(grid)
    cl = SAT._clauses(grid)
    nv = n * n
    if perm is not None:
        cl = [[(perm[abs(l) - 1] + 1) * (1 if l > 0 else -1) if abs(l) <= nv else l for l in c] for c in cl]
        rr = random.Random(seed)
        rr.shuffle(cl)
    inv = None if perm is None else {p: i for i, p in enumerate(perm)}
    s = Solver(name="cadical153", bootstrap_with=cl)
    sols = []
    try:
        while len(sols) < 2:
            if not s.solve():
                break
            m = s.get_model()
            cells = [k for k in range(nv) if m[(perm[k] if perm else k)] > 0]
            col = {k // n: k % n for k in cells}
            sols.append([col.get(r, -1) for r in range(n)])
            s.add_clause([-((perm[k] if perm else k) + 1) for k in cells])
        st = s.accum_stats()
    finally:
        s.delete()
    return len(sols), st.get("conflicts", 0), st.get("propagations", 0), sols


def make_perms(n, tag):
    out = []
    for k in range(K_ORDERS):
        rr = random.Random(f"s6x-perm:{tag}:{k}")
        p = list(range(n * n))
        rr.shuffle(p)
        out.append((p, k + 1))
    return out


def score(obj, grid, perms):
    cnt, conf, _, _ = sat_run(grid)
    if cnt != 1:
        return False, 0
    if obj == "sat":
        return True, conf
    if obj == "sat2":
        return True, max([conf] + [sat_run(grid, p, sd)[1] for p, sd in perms])
    r = native("bitmask" if obj == "bm" else "hybrid", grid)
    return True, r["nodes"] or 0


def climb(n, reg, sol, obj, rng, budget, perms):
    lo, hi = MIN_REGION, max_region_size(n)
    cats = {r * n + sol[r] for r in range(n)}
    reg = list(reg)
    ok, cur = score(obj, to_grid(reg, n), perms)
    assert ok
    start = best = cur
    best_reg, steps, acc = list(reg), 0, 0
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
        ok, v = score(obj, to_grid(reg, n), perms)
        if ok and v >= cur:
            cur = v
            acc += 1
            if v > best:
                best, best_reg = v, list(reg)
        else:
            reg[x] = old
    return best_reg, {"start_score": start, "best": best, "steps": steps, "accepted": acc}


def measure(grid, sol, perms):
    b = native("bitmask", grid, MEAS_T)
    h = native("hybrid", grid, MEAS_T)
    t0 = time.perf_counter()
    cnt, conf, prop, ss = sat_run(grid)
    st = time.perf_counter() - t0
    c = CPSAT.solve(grid, "classify", MEAS_T)
    c2 = c if c["count"] is not None else CPSAT.solve(grid, "classify", 120)
    mx = max([conf] + [sat_run(grid, p, sd)[1] for p, sd in perms])
    rec = {"bm_status": b["status"], "bm_seconds": round(b["elapsed"], 4), "bm_count": b["count"],
           "hy_status": h["status"], "hy_seconds": round(h["elapsed"], 4), "hy_count": h["count"],
           "sat_seconds": round(st, 4), "sat_count": cnt, "cpsat_status": c["status"],
           "cpsat_seconds": round(c["elapsed"], 4), "cpsat_count": c["count"],
           "bm_nodes": b["nodes"], "hy_nodes": h["nodes"], "sat_conflicts": conf, "sat_propagations": prop,
           "sat_conflicts_max_orders": mx}
    rec["unique"] = (cnt == 1 and ss[0] == sol and c2["count"] == 1 and c2["solutions"][0] == sol
                     and check.is_valid(grid, sol))
    return rec


def main(budget=55.0):
    t_all = time.perf_counter()
    sizes = sorted(set(MAIN_SIZES) | set(SAT2_SIZES))
    starts, gen_s = {}, {}
    for n in sizes:
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
    jobs = [(n, o) for n in MAIN_SIZES for o in ("bm", "hy", "sat")] + [(n, "sat2") for n in SAT2_SIZES]
    total_climbs = len(jobs) * PER
    done = 0
    puzzles, rep = [], {}
    for n, obj in jobs:
        t0 = time.perf_counter()
        perms = make_perms(n, n)
        for k, (seed, reg0, sol) in enumerate(starts[n]):
            remain = TOTAL_BUDGET - (time.perf_counter() - t_all)
            left = total_climbs - done
            b = max(5.0, min(budget, remain / left - 12.0))   # 12 s reserved per puzzle for measure()
            done += 1
            rng = random.Random(f"s6x:{n}:{obj}:{k}")
            reg, info = climb(n, reg0, sol, obj, rng, b, perms)
            grid = to_grid(reg, n)
            sz = region_sizes(reg, n)
            rec = measure(grid, sol, perms)
            info["budget_s"] = round(b, 1)
            print(n, obj, k, info, {x: rec[x] for x in ("bm_nodes", "hy_nodes", "sat_conflicts",
                                                         "sat_conflicts_max_orders", "unique")}, flush=True)
            if not rec["unique"]:
                rep.setdefault(f"{n}-{obj}", {}).setdefault("rejected", []).append(k)
                continue
            puzzles.append({"id": f"S6x-{obj}-n{n}-{k}", "group": f"S6x-{obj}", "n": n, "regions": grid,
                            "planted": list(sol), "start_seed": seed, "climb": info,
                            "ref": {"count": 1, "source": "SAT(cadical153) + CP-SAT classify, identical "
                                    "solution, bench.check valid"},
                            "region_min": min(sz), "region_max": max(sz), "measure": rec})
        rep.setdefault(f"{n}-{obj}", {})["secs"] = round(time.perf_counter() - t0, 1)
        rep[f"{n}-{obj}"]["kept"] = sum(p["n"] == n and p["group"] == f"S6x-{obj}" for p in puzzles)
    total = round(time.perf_counter() - t_all, 1)
    suite = {"suite": "S6x",
             "description": "larger adversarial unique-solution puzzles: S6x-bm/hy/sat at N=16,18 (native C++ bitmask nodes, "
                            "native hybrid nodes, CaDiCaL conflicts) and S6x-sat2 at N=14,16,18 (max CaDiCaL conflicts over "
                            f"{K_ORDERS}+1 variable orders); SAT uniqueness check at every step; SAT+CP-SAT double check; "
                            "fixed seeds (bench.build_s6x)",
             "params": {"per": PER, "main_sizes": MAIN_SIZES, "sat2_sizes": SAT2_SIZES, "k_orders": K_ORDERS,
                        "climb_budget_s": budget, "eval_timeout_s": EVAL_T, "total_budget_s": TOTAL_BUDGET},
             "start_gen_s": gen_s, "generation_report": rep, "total_s": total, "puzzles": puzzles}
    with open(OUT, "w") as f:
        json.dump(suite, f, separators=(",", ":"))
    write_md(puzzles, total)
    print("done", total, flush=True)


def write_md(puzzles, total):
    def key(obj):
        return {"bm": "bm_nodes", "hy": "hy_nodes", "sat": "sat_conflicts", "sat2": "sat_conflicts_max_orders"}[obj]
    lines = ["# S6x climb results", "", f"generation total {total} s. Ratio = final / start objective (own objective).", "",
             "| objective | N | puzzles | start median | final median | ratio median | ratio max |", "|---|---|---|---|---|---|---|"]
    groups = {}
    for p in puzzles:
        groups.setdefault((p["group"][4:], p["n"]), []).append(p)
    for (obj, n), ps in sorted(groups.items(), key=lambda t: (["bm", "hy", "sat", "sat2"].index(t[0][0]), t[0][1])):
        st = [max(p["climb"]["start_score"], 1) for p in ps]
        fi = [p["climb"]["best"] for p in ps]
        ra = [f / s for f, s in zip(fi, st)]
        lines.append(f"| {obj} | {n} | {len(ps)} | {statistics.median(st):.0f} | {statistics.median(fi):.0f} | "
                     f"{statistics.median(ra):.1f}x | {max(ra):.1f}x |")
    lines += ["", "Cross-measure medians (final puzzles): bitmask nodes / hybrid nodes / CaDiCaL conflicts / "
              "max-over-orders conflicts / CaDiCaL propagations / CP-SAT s", "",
              "| group | N | bm nodes | hy nodes | sat conf | sat conf max-orders | sat props | cpsat s |", "|---|---|---|---|---|---|---|---|"]
    for (obj, n), ps in sorted(groups.items(), key=lambda t: (["bm", "hy", "sat", "sat2"].index(t[0][0]), t[0][1])):
        m = [p["measure"] for p in ps]
        md = lambda k: statistics.median([x[k] for x in m])
        lines.append(f"| {obj} | {n} | {md('bm_nodes'):.0f} | {md('hy_nodes'):.0f} | {md('sat_conflicts'):.0f} | "
                     f"{md('sat_conflicts_max_orders'):.0f} | {md('sat_propagations'):.0f} | {md('cpsat_seconds'):.3f} |")
    lines += ["", "Old S6 reference (see build_s6): DFS (bm/hy) climbs 16-417x median vs S5b-like baseline, SAT about 3.5-4.6x."]
    with open(os.path.join(os.path.dirname(HERE), "bench", "results", "s6x_climb.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 55.0)
