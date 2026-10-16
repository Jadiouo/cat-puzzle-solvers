"""Dancing Links (Knuth Algorithm X) adapter for the cat puzzle.

Model: one option per cell (r, c).
  primary columns   : row r, column c, region g          (each covered exactly once)
  secondary columns : one per 2x2 window (i, j), 0 <= i, j <= N-2  (covered at most once)
Two distinct cells share a 2x2 window iff max(|dr|, |dc|) <= 1, i.e. they are 8-neighbours:
  (=>) both lie in a 2x2 block, so |dr| <= 1 and |dc| <= 1;
  (<=) for |dr|, |dc| <= 1 the pair fits in the block with top-left (min r, min c), clamped
       into the grid (a block of side 2 always exists for N >= 2 and contains any such pair).
Same row/column pairs are already excluded by the primary columns; this only forbids diagonal and
orthogonal touching. MRV: choose the primary column with the fewest remaining options.
nodes = number of Algorithm X recursive calls.
"""
import sys
import time

from .solvers import Adapter


class _Timeout(Exception):
    pass


def _build(regions):
    n = len(regions)
    nprim = 3 * n
    nsec = max(n - 1, 0) ** 2
    ncols = nprim + nsec
    # node arrays; index 0 = root, 1..ncols = column headers
    L = list(range(-1, ncols))
    R = list(range(1, ncols + 2))
    L[0] = nprim
    R[nprim] = 0
    # secondary headers self-linked
    for k in range(nprim + 1, ncols + 1):
        L[k] = R[k] = k
    U = list(range(ncols + 1))
    D = list(range(ncols + 1))
    C = list(range(ncols + 1))
    S = [0] * (ncols + 1)
    ROW = [-1] * (ncols + 1)
    for r in range(n):
        for c in range(n):
            cols = [1 + r, 1 + n + c, 1 + 2 * n + regions[r][c]]
            for i in (r - 1, r):
                for j in (c - 1, c):
                    if 0 <= i <= n - 2 and 0 <= j <= n - 2:
                        cols.append(1 + nprim + i * (n - 1) + j)
            first = -1
            for col in cols:
                x = len(U)
                U.append(U[col]); D.append(col); C.append(col); ROW.append(r * n + c)
                L.append(0); R.append(0)
                D[U[col]] = x
                U[col] = x
                S[col] += 1
                if first < 0:
                    first = x
                    L[x] = R[x] = x
                else:
                    last = L[first]
                    L[x] = last; R[x] = first
                    R[last] = x; L[first] = x
    return L, R, U, D, C, S, ROW


def dlx_search(regions, limit, deadline=None):
    """Enumerate up to `limit` solutions (None = all). Returns (solutions, nodes, timed_out)."""
    n = len(regions)
    if n == 0:
        return [], 0, False
    L, R, U, D, C, S, ROW = _build(regions)
    sols = []
    nodes = 0
    chosen = []

    def cover(c):
        R[L[c]] = R[c]; L[R[c]] = L[c]
        i = D[c]
        while i != c:
            j = R[i]
            while j != i:
                u, d, cc = U[j], D[j], C[j]
                D[u] = d; U[d] = u
                S[cc] -= 1
                j = R[j]
            i = D[i]

    def uncover(c):
        i = U[c]
        while i != c:
            j = L[i]
            while j != i:
                cc = C[j]
                S[cc] += 1
                D[U[j]] = j; U[D[j]] = j
                j = L[j]
            i = U[i]
        R[L[c]] = c; L[R[c]] = c

    def search():
        nonlocal nodes
        nodes += 1
        if deadline is not None and not nodes & 255 and time.perf_counter() > deadline:
            raise _Timeout
        if R[0] == 0:
            sol = [0] * n
            for o in chosen:
                sol[o // n] = o % n
            sols.append(sol)
            return limit is not None and len(sols) >= limit
        c = R[0]
        best = S[c]
        k = R[c]
        while k != 0:
            if S[k] < best:
                best, c = S[k], k
            k = R[k]
        if best == 0:
            return False
        cover(c)
        r = D[c]
        stop = False
        while r != c:
            chosen.append(ROW[r])
            j = R[r]
            while j != r:
                cover(C[j]); j = R[j]
            stop = search()
            j = L[r]
            while j != r:
                uncover(C[j]); j = L[j]
            chosen.pop()
            if stop:
                break
            r = D[r]
        uncover(c)
        return stop

    old = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old, 10 * n + 1000))
    try:
        search()
        return sols, nodes, False
    except _Timeout:
        return sols, nodes, True
    finally:
        sys.setrecursionlimit(old)


class DLXAdapter(Adapter):
    """Algorithm X with dancing links, MRV over primary columns, 2x2-window secondary columns."""
    name = "dlx"
    _LIMIT = {"first": 1, "classify": 2, "count": None}

    def solve(self, regions, mode, timeout_s):
        t0 = time.perf_counter()
        sols, nodes, timed_out = dlx_search(regions, self._LIMIT[mode], t0 + timeout_s)
        elapsed = time.perf_counter() - t0
        lim = self._LIMIT[mode]
        if timed_out and not (lim is not None and len(sols) >= lim):
            return {"status": "TIMEOUT", "solutions": sols, "count": None, "complete": False,
                    "nodes": nodes, "elapsed": elapsed}
        cnt = len(sols)
        return {"status": "SOLVED" if sols else "UNSAT", "solutions": sols, "count": cnt,
                "complete": True, "nodes": nodes, "elapsed": elapsed}
