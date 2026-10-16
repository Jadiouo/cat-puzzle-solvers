"""Independent re-judging of puzzles that lack an independent reference, by two unrelated SAT/CP
engines (pysat CaDiCaL 1.5.3 and OR-tools CP-SAT). Needs the venv:
  .venv/bin/python -B -m bench.satref        # writes bench/suites/S3_S4_satref.json

Per puzzle: class 0 / 1 / 2 (2 = at least two solutions, found by blocking the first one).
Any solution an engine returns is validated with bench.check (rule checker, no solver code).
confirmed = both engines agree on the class AND every returned solution is valid.
(a 0-solution verdict therefore needs both engines UNSAT; a 1/2 verdict comes with checked solutions)."""
import json
import os
import sys
import time

from . import check

HERE = os.path.dirname(os.path.abspath(__file__))
SUITES = os.path.join(HERE, "suites")
OUT = os.path.join(SUITES, "S3_S4_satref.json")


def _cells(n):
    return [(r, c) for r in range(n) for c in range(n)]


def _groups(regions):
    n = len(regions)
    g = [[r * n + c for c in range(n)] for r in range(n)] + [[r * n + c for r in range(n)] for c in range(n)]
    reg = {}
    for r in range(n):
        for c in range(n):
            reg.setdefault(regions[r][c], []).append(r * n + c)
    return g + list(reg.values())


def _forbidden(n):
    """all unordered pairs of 8-neighbour cells (full list, independent of the bench adapters)"""
    out = []
    for r in range(n):
        for c in range(n):
            for dr, dc in ((0, 1), (1, -1), (1, 0), (1, 1)):
                r2, c2 = r + dr, c + dc
                if 0 <= r2 < n and 0 <= c2 < n:
                    out.append((r * n + c, r2 * n + c2))
    return out


def _decode(true_cells, n):
    sol = [None] * n
    for k in true_cells:
        sol[k // n] = k % n
    return sol


def cadical(regions, limit=2):
    from pysat.solvers import Solver
    n = len(regions)
    s = Solver(name="cadical153")
    for g in _groups(regions):
        s.add_clause([k + 1 for k in g])
        for i, a in enumerate(g):
            for b in g[i + 1:]:
                s.add_clause([-(a + 1), -(b + 1)])
    for a, b in _forbidden(n):
        s.add_clause([-(a + 1), -(b + 1)])
    sols = []
    while len(sols) < limit and s.solve():
        m = s.get_model()
        cells = [k for k in range(n * n) if m[k] > 0]
        sols.append(_decode(cells, n))
        s.add_clause([-(k + 1) for k in cells])
    s.delete()
    return sols


def cpsat(regions, limit=2):
    from ortools.sat.python import cp_model
    n = len(regions)
    m = cp_model.CpModel()
    x = [m.NewBoolVar(f"x{k}") for k in range(n * n)]
    for g in _groups(regions):
        m.AddExactlyOne([x[k] for k in g])
    for a, b in _forbidden(n):
        m.AddBoolOr([x[a].Not(), x[b].Not()])
    sols = []
    while len(sols) < limit:
        sv = cp_model.CpSolver()
        sv.parameters.num_workers = 1
        st = sv.Solve(m)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            if st != cp_model.INFEASIBLE:
                return None   # UNKNOWN: refuse to guess
            break
        cells = [k for k in range(n * n) if sv.Value(x[k])]
        sols.append(_decode(cells, n))
        m.AddBoolOr([x[k].Not() for k in cells])
    return sols


def judge_one(regions):
    rec = {}
    ok = True
    for name, fn in (("cadical153", cadical), ("cpsat", cpsat)):
        t = time.perf_counter()
        sols = fn(regions)
        dt = time.perf_counter() - t
        if sols is None:
            rec[name] = {"class": None, "seconds": round(dt, 3)}
            ok = False
            continue
        valid = all(check.is_valid(regions, s) for s in sols) and len({tuple(s) for s in sols}) == len(sols)
        rec[name] = {"class": len(sols), "solutions": sols, "valid": valid, "seconds": round(dt, 3)}
        ok = ok and valid
    a, b = rec["cadical153"]["class"], rec["cpsat"]["class"]
    rec["agree"] = a is not None and a == b
    rec["confirmed"] = bool(ok and rec["agree"])
    rec["class"] = a if rec["agree"] else None
    return rec


def targets():
    out = []
    for s in ("S1", "S2", "S3", "S4"):
        d = json.load(open(os.path.join(SUITES, f"{s}.json")))
        for p in d["puzzles"]:
            ref = p.get("ref") or {}
            if ref.get("count") is None or "NOT independent" in (ref.get("source") or ""):
                out.append((s, p, "no_reference" if ref.get("count") is None else "cat_solver_only"))
    return out


def main():
    res = {}
    for s, p, why in targets():
        rec = judge_one(p["regions"])
        rec.update({"suite": s, "n": p["n"], "why": why,
                    "old_ref_count": (p.get("ref") or {}).get("count")})
        res[p["id"]] = rec
        print(p["id"], why, rec["class"], "confirmed" if rec["confirmed"] else "!!! NOT CONFIRMED", flush=True)
    doc = {"description": "SAT double confirmation (pysat cadical153 + OR-tools CP-SAT) for puzzles without an "
                          "independent reference. class: 0, 1, 2 (= at least 2).",
           "puzzles": res}
    json.dump(doc, open(OUT, "w"))
    print(len(res), "puzzles;", sum(r["confirmed"] for r in res.values()), "confirmed")


if __name__ == "__main__":
    main()
