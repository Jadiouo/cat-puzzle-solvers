"""Deterministic puzzle generator: iteration-bounded (no wall-clock dependence),
so the same (size, seed, target) always yields the same output."""
import random

from .board import (D4, MIN_REGION, connected_without, count_solutions,
                    max_region_size, region_sizes, size_violation, to_grid)
from .grade import LEVEL_RANK, grade

TARGETS = (None, "T3b", "T4", "T5a", "T5b")


def rand_solution(n, rng):
    while True:
        cols = []

        def rec(r):
            if r == n:
                return True
            cs = list(range(n))
            rng.shuffle(cs)
            for c in cs:
                if c in cols or (cols and abs(cols[-1] - c) <= 1):
                    continue
                cols.append(c)
                if rec(r + 1):
                    return True
                cols.pop()
            return False

        if rec(0):
            return list(cols)


def grow(n, sol, rng):
    reg = [-1] * (n * n)
    for r, c in enumerate(sol):
        reg[r * n + c] = r
    frontier = [[r * n + sol[r]] for r in range(n)]
    free = n * n - n
    while free:
        g = min(rng.randrange(n), rng.randrange(n), key=lambda q: len(frontier[q]))
        cand = []
        for x in frontier[g]:
            r, c = divmod(x, n)
            for dr, dc in D4:
                a, b = r + dr, c + dc
                if 0 <= a < n and 0 <= b < n and reg[a * n + b] < 0:
                    cand.append(a * n + b)
        if not cand:
            continue
        y = rng.choice(cand)
        reg[y] = g
        frontier[g].append(y)
        free -= 1
    return reg


def _neighbour_move(reg, n, x, rng):
    r, c = divmod(x, n)
    old = reg[x]
    nb = {reg[(r + dr) * n + c + dc] for dr, dc in D4
          if 0 <= r + dr < n and 0 <= c + dc < n} - {old}
    if not nb:
        return None
    new = rng.choice(sorted(nb))
    if not connected_without(reg, n, old, x):
        return None
    return old, new


def make_unique(n, rng, max_restarts=60, stall_limit=1500, objcap=40):
    """Local search to a connected, size-legal, uniquely solvable layout.
    Returns (reg, sol) or None."""
    lo, hi = MIN_REGION, max_region_size(n)
    for _ in range(max_restarts):
        sol = rand_solution(n, rng)
        reg = grow(n, sol, rng)
        catset = {r * n + sol[r] for r in range(n)}
        cur = (size_violation(reg, n, lo, hi), count_solutions(reg, n, objcap))
        stall = 0
        while cur != (0, 1) and stall < stall_limit:
            x = rng.randrange(n * n)
            if x in catset:
                stall += 1
                continue
            mv = _neighbour_move(reg, n, x, rng)
            if mv is None:
                stall += 1
                continue
            old, new = mv
            reg[x] = new
            v = size_violation(reg, n, lo, hi)
            k = (v, count_solutions(reg, n, objcap) if v <= cur[0] else 10 ** 9)
            if k <= cur:
                stall = 0 if k < cur else stall + 1
                cur = k
            else:
                reg[x] = old
                stall += 1
        if cur == (0, 1):
            return reg, sol
    return None


def steer(reg, sol, n, rng, target, iters):
    """Random single-cell moves preserving connectivity, size limits and
    uniqueness; accept when (level rank, score) does not decrease.
    Stops when level >= target. Mutates reg; returns True on success."""
    lo, hi = MIN_REGION, max_region_size(n)
    catset = {r * n + sol[r] for r in range(n)}
    want = LEVEL_RANK[target]

    def key(rg):
        g = grade(to_grid(rg, n))
        if not g["solved"]:
            return None
        return (LEVEL_RANK[g["level"]], g["score"])

    cur = key(reg)
    if cur is None:
        return False
    if cur[0] >= want:
        return True
    for _ in range(iters):
        x = rng.randrange(n * n)
        if x in catset:
            continue
        mv = _neighbour_move(reg, n, x, rng)
        if mv is None:
            continue
        old, new = mv
        reg[x] = new
        if size_violation(reg, n, lo, hi) == 0 and count_solutions(reg, n, 2) == 1:
            k = key(reg)
            if k is not None and k >= cur:
                cur = k
                if cur[0] >= want:
                    return True
                continue
        reg[x] = old
    return False


def generate(size, seed, target=None, max_bases=4, steer_iters=1500):
    """Return a puzzle dict or None (failure within the fixed iteration budget).
    target: None, or 'T3b'/'T4'/'T5a'/'T5b' = highest technique must be >= target.
    Output is a pure function of (size, seed, target, budgets)."""
    if target not in TARGETS:
        raise ValueError(f"target must be one of {TARGETS}")
    rng = random.Random(f"levelgen:{size}:{seed}:{target}")
    n = size
    for _ in range(max_bases if target else 1):
        base = make_unique(n, rng)
        if base is None:
            continue
        reg, sol = base
        if target is not None:
            if not steer(reg, sol, n, rng, target, steer_iters):
                continue
        g = grade(to_grid(reg, n), solution=sol)
        if not g["solved"]:
            continue    # needs guessing beyond T5b; reject
        sz = region_sizes(reg, n)
        return {"size": n, "regions": to_grid(reg, n), "solution": list(sol),
                "seed": seed, "target": target,
                "region_min": min(sz), "region_max": max(sz)}
    return None
