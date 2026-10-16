"""Solver adapters. To add a method: subclass Adapter, implement solve(), register it.

solve(regions, mode, timeout_s) -> dict with keys
  status    SOLVED | UNSAT | TIMEOUT | STUCK | ERROR
  solutions list of solutions found (each = column index per row, 0-based)
  count     int or None. first: 0/1 (found or not). classify: 0, 1, or 2 (2 = at least 2).
            count: exact number of solutions. None = no claim.
  complete  True if the answer for the requested mode is determined
  nodes     search nodes / inference steps (None if not applicable)
  elapsed   seconds of pure solve time (perf_counter, parsing/imports excluded)
mode in {first, classify, count}. `regions` is an N x N grid of ints (0..N-1).
"""
import time

MODES = ("first", "classify", "count")


class Adapter:
    name = "?"
    modes = MODES
    exhaustive = True   # False: a negative answer (STUCK) is not a claim about the puzzle

    def solve(self, regions, mode, timeout_s):
        raise NotImplementedError


class CatSolverAdapter(Adapter):
    """MRV + forward checking backtracking (cat_solver). count -> its 'all' mode."""
    name = "cat_solver"
    _MODE = {"first": "first", "classify": "classify", "count": "all"}

    def solve(self, regions, mode, timeout_s):
        from cat_solver import SolveOptions, parse_puzzle, solve
        n = len(regions)
        puzzle = parse_puzzle({"schema_version": "1.0", "size": n,
                               "regions": [[f"R{x}" for x in row] for row in regions]})
        opts = SolveOptions(mode=self._MODE[mode], timeout_ms=max(1, int(timeout_s * 1000)))
        t0 = time.perf_counter()
        res = solve(puzzle, opts)
        elapsed = time.perf_counter() - t0
        sols = res.solutions
        if res.status == "SOLVED" or res.status == "UNSAT":
            ok = True
            if mode == "first":
                cnt = 1 if sols else 0
            elif mode == "classify":
                cnt = min(len(sols), 2)
            else:
                cnt = len(sols)
            status = res.status
        elif res.status == "TIMEOUT" or res.status == "NODE_LIMIT" or res.status == "CANCELLED":
            ok, cnt, status = False, None, "TIMEOUT"
            if mode == "classify" and len(sols) >= 2:   # found 2nd solution right before the limit
                ok, cnt, status = True, 2, "SOLVED"
        else:
            return {"status": "ERROR", "solutions": [], "count": None, "complete": False,
                    "nodes": res.nodes, "elapsed": elapsed, "error": "; ".join(res.errors)}
        return {"status": status, "solutions": sols, "count": cnt, "complete": ok,
                "nodes": res.nodes, "elapsed": elapsed}


class LevelgenGradeAdapter(Adapter):
    """levelgen.grade: human-technique inference only. SOLVED = completed by pure deduction
    (which implies a unique answer, so classify/count report count=1); STUCK = would need
    guessing, which is not a claim about the puzzle. No internal time limit (parent kills)."""
    name = "levelgen"
    exhaustive = False

    def solve(self, regions, mode, timeout_s):
        from levelgen import grade
        t0 = time.perf_counter()
        g = grade(regions)
        elapsed = time.perf_counter() - t0
        steps = g["steps"]
        if g["solved"]:
            return {"status": "SOLVED", "solutions": [g["solution"]], "count": 1,
                    "complete": True, "nodes": steps, "elapsed": elapsed}
        return {"status": "STUCK", "solutions": [], "count": None, "complete": False,
                "nodes": steps, "elapsed": elapsed}


ADAPTERS = {a.name: a for a in (CatSolverAdapter(), LevelgenGradeAdapter())}


SKIPPED = {}   # name -> reason, for optional adapters whose packages are missing


def _register_all():
    import importlib.util
    from . import solver_bitmask, solver_dlx, solver_hybrid
    for a in (solver_bitmask.BitmaskAdapter(), solver_bitmask.BitmaskRowAdapter(),
              solver_hybrid.HybridAdapter(), solver_hybrid.HybridSAdapter(),
              solver_hybrid.HybridT3Adapter(), solver_hybrid.HybridK2Adapter(),
              solver_dlx.DLXAdapter()):
        ADAPTERS[a.name] = a
    # SAT adapters need pysat / ortools; probe with find_spec only (nothing imported here)
    have = {m: importlib.util.find_spec(m) is not None for m in ("pysat", "ortools")}
    from . import solver_sat
    for name, a in solver_sat.ADAPTERS.items():
        need = "ortools" if name.startswith("cpsat") else "pysat"
        if have[need]:
            ADAPTERS[name] = a
        else:
            SKIPPED[name] = f"python package '{need}' not installed (use .venv/bin/python)"
    # native C++ ports (subprocess to native/build/cat_native); skipped with a hint if not built
    from . import solver_native
    if solver_native.available():
        ADAPTERS.update(solver_native.NATIVE_ADAPTERS)
    else:
        for name in solver_native.NATIVE_ADAPTERS:
            SKIPPED[name] = f"binary missing: {solver_native.EXE} (run: make -C native)"


_register_all()


def get(name):
    if name not in ADAPTERS:
        why = SKIPPED.get(name)
        if why:
            raise SystemExit(f"solver {name!r} skipped: {why}")
        raise SystemExit(f"unknown solver {name!r}; available: {', '.join(ADAPTERS)}")
    return ADAPTERS[name]
