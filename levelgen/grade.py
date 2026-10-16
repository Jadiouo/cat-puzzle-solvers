"""Human-style technique grader.

T2  single candidate in a unit (row/col/region)
T3  1 unit confined to 1 unit of another type (pointing / claiming)
T3b cover elimination: X cannot hold a cat if row+col+region+8-neighbours of X
    cover all candidates of some other unit
T4  k=2..4 units confined to k units of another type (subset)
T5a one-layer lookahead: placing X + forced singles reaches a contradiction
    after exactly 1 placement (X itself counted as depth 0)
T5b deeper lookahead (contradiction after >=2 forced placements)
"""
from collections import Counter
from itertools import combinations

from .board import normalize

# --- All scoring weights live here. Edit and call rescore(). -----------------
WEIGHTS = {
    "T2": 1,
    "T3": 3,
    "T3b": 4,
    "T4": 6,
    "T5a": 9,
    "T5b": 12,        # per T5b step
    "T5b_depth": 2,   # per unit of lookahead depth in T5b steps
}
LEVELS = ("T2", "T3", "T3b", "T4", "T5a", "T5b")
LEVEL_RANK = {l: i for i, l in enumerate(LEVELS)}
TECHNIQUES = ("T2", "T3", "T3b", "T4", "T5a", "T5b")


class SolutionEliminated(AssertionError):
    pass


def make_units(reg, n):
    rows = [frozenset(r * n + c for c in range(n)) for r in range(n)]
    cols = [frozenset(r * n + c for r in range(n)) for c in range(n)]
    rg = [frozenset(i for i in range(n * n) if reg[i] == g) for g in range(n)]
    return {"row": rows, "col": cols, "reg": rg}


def neigh8(x, n):
    r, c = divmod(x, n)
    return [a * n + b for a in range(r - 1, r + 2) for b in range(c - 1, c + 2)
            if 0 <= a < n and 0 <= b < n]


class State:
    def __init__(s, n, U):
        s.n = n
        s.U = U
        s.cand = set(range(n * n))
        s.cats = set()
        s.N8 = [neigh8(x, n) for x in range(n * n)]
        s.ulist = [(t, i, u) for t, L in U.items() for i, u in enumerate(L)]
        s.of = {x: [(t, i) for t, L in U.items() for i, u in enumerate(L) if x in u]
                for x in range(n * n)}

    def copy(s):
        t = State.__new__(State)
        t.n, t.U, t.N8, t.ulist, t.of = s.n, s.U, s.N8, s.ulist, s.of
        t.cand = set(s.cand)
        t.cats = set(s.cats)
        return t

    def place(s, x):
        s.cats.add(x)
        rm = set(s.N8[x])
        for t, i in s.of[x]:
            rm |= s.U[t][i]
        s.cand -= rm

    def dead(s):
        return any(not (u & s.cand) and not (u & s.cats) for _, _, u in s.ulist)


def t2(s):
    for _, _, u in s.ulist:
        if u & s.cats:
            continue
        c = u & s.cand
        if len(c) == 1:
            return next(iter(c))
    return None


def subset_elim(s, kmin, kmax):
    types = ("reg", "row", "col")
    for k in range(kmin, kmax + 1):
        for A in types:
            for B in types:
                if A == B:
                    continue
                un = [i for i, u in enumerate(s.U[A]) if not (u & s.cats)]
                if len(un) <= k:
                    continue
                for combo in combinations(un, k):
                    cells = set()
                    for i in combo:
                        cells |= s.U[A][i] & s.cand
                    bs = {j for j, u in enumerate(s.U[B]) if u & cells}
                    if len(bs) == k:
                        rm = set()
                        for j in bs:
                            rm |= s.U[B][j] & s.cand
                        rm -= cells
                        if rm:
                            s.cand -= rm
                            return True
    return False


def t3b(s):
    for x in sorted(s.cand):
        cover = set(s.N8[x])
        for t, i in s.of[x]:
            cover |= s.U[t][i]
        for t, i, u in s.ulist:
            if x in u or (u & s.cats):
                continue
            c = u & s.cand
            if c and c <= cover:
                s.cand.discard(x)
                return True
    return False


def propagate_simple(s):
    d = 0
    while True:
        if s.dead():
            return False, d
        x = t2(s)
        if x is None:
            return True, d
        s.place(x)
        d += 1


def lookahead(s):
    """Shallowest contradiction depth over all candidate cells, eliminating that
    cell. Returns depth (0 = immediate dead end after placing, equivalent to T3b)
    or None when no contradiction exists."""
    best = None
    for x in sorted(s.cand):
        t = s.copy()
        t.place(x)
        ok, d = propagate_simple(t)
        if not ok and (best is None or d < best[0]):
            best = (d, x)
            if d == 0:
                break
    if best is None:
        return None
    s.cand.discard(best[1])
    return best[0]


def _solve(reg, n, sol=None, max_tech="T5b"):
    s = State(n, make_units(reg, n))
    use = Counter()
    top = LEVEL_RANK[max_tech]
    solset = set(sol) if sol is not None else None

    def chk(step):
        if solset is not None and not solset <= (s.cand | s.cats):
            raise SolutionEliminated(f"{step} eliminated a solution cell")

    while len(s.cats) < n:
        if s.dead():
            return s, use, "dead"
        x = t2(s)
        if x is not None:
            use["T2"] += 1
            s.place(x)
            chk("T2")
            continue
        if top >= 1 and subset_elim(s, 1, 1):
            use["T3"] += 1
            chk("T3")
            continue
        if top >= 2 and t3b(s):
            use["T3b"] += 1
            chk("T3b")
            continue
        if top >= 3 and subset_elim(s, 2, 4):
            use["T4"] += 1
            chk("T4")
            continue
        if top >= 4:
            d = lookahead(s)
            if d is not None:
                chk("T5")
                if d == 0:          # defensive; unreachable after t3b
                    use["T3b"] += 1
                elif d == 1:
                    use["T5a"] += 1
                else:
                    use["T5b"] += 1
                    use["T5b_depth"] += d
                continue
        return s, use, "stuck"
    return s, use, "ok"


def score(use, weights=None):
    w = weights or WEIGHTS
    return (w["T2"] * use["T2"] + w["T3"] * use["T3"] + w["T3b"] * use["T3b"]
            + w["T4"] * use["T4"] + w["T5a"] * use["T5a"]
            + w["T5b"] * use["T5b"] + w["T5b_depth"] * use["T5b_depth"])


def highest(use):
    for l in reversed(LEVELS):
        if use[l]:
            return l
    return "T2"


def grade(regions, solution=None, weights=None):
    """Grade a puzzle. `solution` (list of column per row) enables the check that
    no step ever removes an answer cell (raises SolutionEliminated).
    Returns dict: counts, level, score, steps, T5b_depth, solved (False if the
    techniques get stuck -> would need guessing)."""
    reg, n = normalize(regions)
    sol = None if solution is None else [r * n + c for r, c in enumerate(solution)]
    s, use, status = _solve(reg, n, sol)
    counts = {t: use[t] for t in TECHNIQUES}
    out = {
        "counts": counts,
        "T5b_depth": use["T5b_depth"],
        "level": highest(use),
        "steps": sum(counts.values()),
        "solved": status == "ok",
        "score": score(use, weights),
    }
    if status == "ok":
        out["solution"] = [x % n for x in sorted(s.cats)]
    return out


def rescore(pool_item, weights):
    """Recompute score of a stored pool entry with other weights."""
    u = Counter(pool_item["counts"])
    u["T5b_depth"] = pool_item["T5b_depth"]
    return score(u, weights)
