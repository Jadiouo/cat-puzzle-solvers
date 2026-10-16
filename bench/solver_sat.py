"""SAT (pysat) and CP-SAT (ortools) adapters, same interface as bench.solvers.Adapter.

Not registered in bench.solvers.ADAPTERS (that file is not modified). Use register() or
bench/measure_sat.py. Result dict = standard keys plus timing split:
  import_s  one-off library import in this process (NOT in elapsed)
  build_s   model construction incl. solver object creation (IS in elapsed)
  solve_s   search time only (IS in elapsed)
  elapsed = build_s + solve_s
Model: x[r][c] one per cell; exactly-one per row, column, region; no two cats 8-neighbour
adjacent (only the 2 diagonal pairs per 2x2 window are added; orthogonal pairs are implied by
the row/column exactly-one).
"""
import threading
import time

from .solvers import Adapter

_t0 = time.perf_counter()
_IMPORT_S = {}


def _timed_import(kind):
    if kind in _IMPORT_S:
        return 0.0
    t = time.perf_counter()
    if kind == "sat":
        import pysat.solvers, pysat.card  # noqa: F401
    else:
        from ortools.sat.python import cp_model  # noqa: F401
    _IMPORT_S[kind] = time.perf_counter() - t
    return _IMPORT_S[kind]


def _groups(regions):
    n = len(regions)
    rows = [[r * n + c for c in range(n)] for r in range(n)]
    cols = [[r * n + c for r in range(n)] for c in range(n)]
    reg = {}
    for r in range(n):
        for c in range(n):
            reg.setdefault(regions[r][c], []).append(r * n + c)
    return rows + cols + list(reg.values())


def _diag_pairs(n):
    for r in range(n - 1):
        for c in range(n - 1):
            yield r * n + c, (r + 1) * n + c + 1
            yield r * n + c + 1, (r + 1) * n + c


def _decode(cells, n):
    """cells = set of true cell indexes -> column per row, or None if malformed."""
    sol = [None] * n
    for k in cells:
        sol[k // n] = k % n
    return sol if None not in sol else None


_CARD_ENC = {"ladder": "ladder", "totalizer": "totalizer", "bitwise": "bitwise"}


class SatAdapter(Adapter):
    """pysat. amo in {pairwise, seq, card}; solver name is a pysat name (glucose4 is
    interruptible so the time limit is honoured inside a call; cadical153 is only checked
    between calls, the runner's hard kill covers the rest)."""

    def __init__(self, amo="pairwise", solver="glucose4"):
        self.amo, self.sname = amo, solver
        self.name = f"sat_{solver}_{amo}"

    def _clauses(self, regions):
        from pysat.card import CardEnc, EncType
        n = len(regions)
        top = n * n
        cl = []
        for g in _groups(regions):
            lits = [k + 1 for k in g]
            cl.append(lits)  # at least one
            if self.amo == "pairwise":
                cl += [[-a, -b] for i, a in enumerate(lits) for b in lits[i + 1:]]
            elif self.amo == "seq":  # Sinz sequential counter, k=1
                m = len(lits)
                s = [top + i + 1 for i in range(m - 1)]
                top += m - 1
                if m > 1:
                    cl.append([-lits[0], s[0]])
                    for i in range(1, m - 1):
                        cl.append([-lits[i], s[i]])
                        cl.append([-s[i - 1], s[i]])
                        cl.append([-lits[i], -s[i - 1]])
                    cl.append([-lits[m - 1], -s[m - 2]])
            elif self.amo == "card":  # pysat CardEnc, totalizer
                enc = CardEnc.atmost(lits=lits, bound=1, top_id=top, encoding=EncType.totalizer)
                top = max(top, enc.nv)
                cl += enc.clauses
            elif self.amo in _CARD_ENC:  # pysat CardEnc AMO (+ the ALO clause already added above)
                enc = CardEnc.atmost(lits=lits, bound=1, top_id=top, encoding=getattr(EncType, _CARD_ENC[self.amo]))
                top = max(top, enc.nv)
                cl += enc.clauses
            else:
                raise ValueError(self.amo)
        cl += [[-a - 1, -b - 1] for a, b in _diag_pairs(n)]
        return cl

    def solve(self, regions, mode, timeout_s):
        imp = _timed_import("sat")
        from pysat.solvers import Solver
        n = len(regions)
        deadline = time.perf_counter() + timeout_s
        tb = time.perf_counter()
        cl = self._clauses(regions)
        s = Solver(name=self.sname, bootstrap_with=cl,
                   use_timer=False)
        build = time.perf_counter() - tb
        sols, status, solve_t = [], "SOLVED", 0.0
        interruptible = self.sname in ("glucose4", "glucose3", "maplechrono", "maplecm")
        want = {"first": 1, "classify": 2, "count": None}[mode]
        try:
            while want is None or len(sols) < want:
                left = deadline - time.perf_counter()
                if left <= 0:
                    status = "TIMEOUT"
                    break
                ts = time.perf_counter()
                if interruptible:
                    tm = threading.Timer(left, s.interrupt)
                    tm.start()
                    try:
                        r = s.solve_limited(expect_interrupt=True)
                    finally:
                        tm.cancel()
                    s.clear_interrupt()
                else:
                    r = s.solve()
                solve_t += time.perf_counter() - ts
                if r is None:
                    status = "TIMEOUT"
                    break
                if not r:
                    break
                model = s.get_model()
                cells = [k for k in range(n * n) if model[k] > 0]
                sol = _decode(cells, n)
                if sol is None or len(cells) != n:
                    return {"status": "ERROR", "solutions": sols, "count": None, "complete": False,
                            "nodes": None, "elapsed": build + solve_t, "error": "bad model"}
                sols.append(sol)
                s.add_clause([-(k + 1) for k in cells])  # block this placement
            try:
                st_ = s.accum_stats()
                nodes = st_.get("conflicts")
                extra = {k: st_.get(k) for k in ("conflicts", "decisions", "propagations")}
            except Exception:
                nodes, extra = None, None
        finally:
            s.delete()
        return _finish(mode, status, sols, build, solve_t, imp, nodes, extra)


def _finish(mode, status, sols, build, solve_t, imp, nodes, extra=None):
    elapsed = build + solve_t
    base = {"nodes": nodes, "elapsed": elapsed, "build_s": build, "solve_s": solve_t,
            "import_s": imp}
    if extra:
        base.update(extra)   # language-independent work counters (conflicts/decisions/propagations/branches)
    if status == "TIMEOUT":
        if mode == "classify" and len(sols) >= 2:
            return dict(base, status="SOLVED", solutions=sols, count=2, complete=True)
        if mode == "first" and sols:
            return dict(base, status="SOLVED", solutions=sols, count=1, complete=True)
        return dict(base, status="TIMEOUT", solutions=sols, count=None, complete=False)
    cnt = len(sols)
    if mode == "classify":
        cnt = min(cnt, 2)
    elif mode == "first":
        cnt = 1 if sols else 0
    return dict(base, status="SOLVED" if sols else "UNSAT", solutions=sols, count=cnt,
                complete=True)


class CpSatAdapter(Adapter):
    """ortools CP-SAT. workers=1: enumerate_all_solutions with callback (stop after 2 for
    classify). workers>1: classify by blocking (solve, forbid the solution, solve), because
    CP-SAT enumeration is single-threaded; count still uses enumeration (single-threaded)."""

    def __init__(self, workers=1):
        self.workers = workers
        self.name = f"cpsat_w{workers}"

    def solve(self, regions, mode, timeout_s):
        imp = _timed_import("cpsat")
        from ortools.sat.python import cp_model
        n = len(regions)
        deadline = time.perf_counter() + timeout_s
        tb = time.perf_counter()
        m = cp_model.CpModel()
        x = [m.new_bool_var(f"x{k}") for k in range(n * n)]
        for g in _groups(regions):
            m.add_exactly_one([x[k] for k in g])
        for a, b in _diag_pairs(n):
            m.add_bool_or([x[a].negated(), x[b].negated()])
        build = time.perf_counter() - tb
        blocking = self.workers > 1 and mode == "classify"
        sols, status, solve_t = [], "SOLVED", 0.0
        limit = {"first": 1, "classify": 2, "count": None}[mode]

        class CB(cp_model.CpSolverSolutionCallback):
            def __init__(s):
                super().__init__()
                s.found = []

            def on_solution_callback(s):
                s.found.append(_decode([k for k in range(n * n) if s.boolean_value(x[k])], n))
                if limit is not None and len(s.found) >= limit:
                    s.stop_search()

        solver = cp_model.CpSolver()
        solver.parameters.num_workers = self.workers
        nodes = None
        if blocking:
            solver.parameters.num_workers = self.workers
            while len(sols) < 2:
                left = deadline - time.perf_counter()
                if left <= 0:
                    status = "TIMEOUT"
                    break
                solver.parameters.max_time_in_seconds = left
                ts = time.perf_counter()
                st = solver.solve(m)
                solve_t += time.perf_counter() - ts
                if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                    cells = [k for k in range(n * n) if solver.boolean_value(x[k])]
                    sols.append(_decode(cells, n))
                    m.add_bool_or([x[k].negated() for k in cells])
                elif st == cp_model.INFEASIBLE:
                    break
                else:
                    status = "TIMEOUT"
                    break
            nodes = solver.num_branches
            extra = {"branches": solver.num_branches, "conflicts": solver.num_conflicts}
        else:
            solver.parameters.enumerate_all_solutions = True
            solver.parameters.num_workers = 1
            solver.parameters.max_time_in_seconds = max(1e-3, deadline - time.perf_counter())
            cb = CB()
            ts = time.perf_counter()
            st = solver.solve(m, cb)
            solve_t = time.perf_counter() - ts
            sols = cb.found
            nodes = solver.num_branches
            extra = {"branches": nodes, "conflicts": solver.num_conflicts}
            stopped_early = limit is not None and len(sols) >= limit
            if st == cp_model.OPTIMAL or (st == cp_model.INFEASIBLE):
                pass  # search space exhausted
            elif not stopped_early:
                status = "TIMEOUT" if st in (cp_model.UNKNOWN, cp_model.FEASIBLE) else "ERROR"
            if status == "ERROR":
                return {"status": "ERROR", "solutions": sols, "count": None, "complete": False,
                        "nodes": nodes, "elapsed": build + solve_t, "error": solver.status_name(st)}
        return _finish(mode, status, sols, build, solve_t, imp, nodes, extra)


ADAPTERS = {a.name: a for a in (
    SatAdapter("pairwise", "glucose4"), SatAdapter("seq", "glucose4"),
    SatAdapter("card", "glucose4"), SatAdapter("pairwise", "cadical153"),
    SatAdapter("seq", "cadical153"), CpSatAdapter(1), CpSatAdapter(4),
    # encoding variants (same solver, cadical153) and solver variants (same encoding, seq)
    SatAdapter("ladder", "cadical153"), SatAdapter("totalizer", "cadical153"),
    SatAdapter("bitwise", "cadical153"),
    SatAdapter("seq", "cadical195"), SatAdapter("seq", "glucose4"), SatAdapter("seq", "minisat22"))}


def register():
    """Add these adapters to bench.solvers.ADAPTERS at runtime (no file is modified)."""
    from . import solvers
    solvers.ADAPTERS.update(ADAPTERS)
