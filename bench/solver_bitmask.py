"""(A) Bitmask DFS with forward checking. Pure stdlib.

Board = one Python int, bit r*n+c = cell (r,c) still possible. Placing a cat at x clears KILL[x]
(its row, column, colour region and 8-neighbourhood) and marks its row/col/region "done".
After every placement each undone unit (row/col/region) must still have a candidate (forward
check). Branch unit: "mrv" = undone unit (row/col/region) with fewest candidates, "row" = lowest
undone row. Branching on the cells of one unit partitions the solution space, so counts are exact.

Adapter interface = bench.solvers.Adapter.solve(regions, mode, timeout_s). Extra result keys:
"branches" (= nodes - 1).
"""
import time

MODES = ("first", "classify", "count")


class _Timeout(Exception):
    pass


def build_tables(regions):
    """Return dict of bit tables, or None if the colour count != n (then no solution exists)."""
    n = len(regions)
    ids = sorted({x for row in regions for x in row})
    if len(ids) != n:
        return None
    gi = {g: i for i, g in enumerate(ids)}
    ROW = [0] * n
    COL = [0] * n
    REG = [0] * n
    for r in range(n):
        for c in range(n):
            b = 1 << (r * n + c)
            ROW[r] |= b
            COL[c] |= b
            REG[gi[regions[r][c]]] |= b
    KILL = [0] * (n * n)
    UBIT = [0] * (n * n)
    for r in range(n):
        for c in range(n):
            g = gi[regions[r][c]]
            k = ROW[r] | COL[c] | REG[g]
            for a in range(max(0, r - 1), min(n, r + 2)):
                for b in range(max(0, c - 1), min(n, c + 2)):
                    k |= 1 << (a * n + b)
            KILL[r * n + c] = k
            UBIT[r * n + c] = (1 << r) | (1 << (n + c)) | (1 << (2 * n + g))
    return {"n": n, "ROW": ROW, "COL": COL, "REG": REG, "UN": ROW + COL + REG,
            "KILL": KILL, "UBIT": UBIT, "FULL": (1 << (3 * n)) - 1, "ALL": (1 << (n * n)) - 1}


def cats_to_solution(cats, n):
    sol = [0] * n
    while cats:
        low = cats & -cats
        x = low.bit_length() - 1
        sol[x // n] = x % n
        cats ^= low
    return sol


def finish(mode, limit, sols, nodes, t0, timed_out, extra=None):
    """Common result packaging (same conventions as CatSolverAdapter)."""
    elapsed = time.perf_counter() - t0
    out = {"solutions": sols, "nodes": nodes, "elapsed": elapsed}
    if extra:
        out.update(extra)
    if not timed_out:
        cnt = len(sols) if mode == "count" else min(len(sols), limit if limit else len(sols))
        if mode == "first":
            cnt = 1 if sols else 0
        out.update(status="SOLVED" if sols else "UNSAT", count=cnt, complete=True)
    elif mode in ("first", "classify") and len(sols) >= (1 if mode == "first" else 2):
        out.update(status="SOLVED", count=1 if mode == "first" else 2, complete=True)
    else:
        out.update(status="TIMEOUT", count=None, complete=False)
    return out


class BitmaskAdapter:
    """Bitmask DFS + forward checking, MRV over rows/cols/regions."""
    name = "bitmask"
    modes = MODES
    exhaustive = True
    order = "mrv"

    def solve(self, regions, mode, timeout_s):
        t0 = time.perf_counter()
        n = len(regions)
        T = build_tables(regions)
        if T is None:
            return {"status": "UNSAT", "solutions": [], "count": 0, "complete": True,
                    "nodes": 0, "elapsed": time.perf_counter() - t0}
        UN, KILL, UBIT, FULL = T["UN"], T["KILL"], T["UBIT"], T["FULL"]
        units = range(3 * n)
        rows_only = self.order == "row"
        limit = {"first": 1, "classify": 2, "count": None}[mode]
        deadline = t0 + timeout_s
        sols = []
        nodes = 0
        BIG = 1 << 30

        def rec(alive, done, cats):
            nonlocal nodes
            nodes += 1
            if not nodes & 255 and time.perf_counter() > deadline:
                raise _Timeout
            if done == FULL:
                sols.append(cats_to_solution(cats, n))
                return limit is not None and len(sols) >= limit
            bc, bm = BIG, 0
            for u in units:
                if done >> u & 1:
                    continue
                m = alive & UN[u]
                if not m:
                    return False                      # forward check failed
                if rows_only:
                    if bc == BIG and u < n:
                        bc, bm = 0, m                 # first undone row
                    continue
                c = m.bit_count()
                if c < bc:
                    bc, bm = c, m
            while bm:
                low = bm & -bm
                bm ^= low
                x = low.bit_length() - 1
                if rec(alive & ~KILL[x], done | UBIT[x], cats | low):
                    return True
            return False

        timed_out = False
        try:
            rec(T["ALL"], 0, 0)
        except _Timeout:
            timed_out = True
        return finish(mode, limit, sols, nodes, t0, timed_out, {"branches": max(nodes - 1, 0)})


class BitmaskRowAdapter(BitmaskAdapter):
    """Same, but plain row-by-row order (no MRV); still forward-checks all units."""
    name = "bitmask_row"
    order = "row"
