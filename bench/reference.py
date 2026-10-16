"""Independent reference solution counter (row DFS over bitmasks + region-reachability
pruning). Shares no code with cat_solver or levelgen. Aborts with None past a node/time budget."""
import time


def count_solutions(regions, node_limit=None, time_limit=None, cap=None):
    """Return exact count, or None if the budget ran out (never a guess).
    cap: stop once count >= cap and return cap (exact only if < cap)."""
    n = len(regions)
    full = (1 << n) - 1
    ids = sorted({x for row in regions for x in row})
    ridx = {g: i for i, g in enumerate(ids)}
    cell_reg = [[ridx[regions[r][c]] for c in range(n)] for r in range(n)]
    # rowmask[g][r] = bitmask of columns in row r belonging to region g
    rowmask = [[0] * n for _ in range(n)]
    for r in range(n):
        for c in range(n):
            rowmask[cell_reg[r][c]][r] |= 1 << c
    # suffix union per region: union of rowmask[g][r..]
    suf = [[0] * (n + 1) for _ in range(n)]
    for g in range(n):
        for r in range(n - 1, -1, -1):
            suf[g][r] = suf[g][r + 1] | rowmask[g][r]
    nodes = 0
    count = 0
    deadline = None if time_limit is None else time.perf_counter() + time_limit
    aborted = False

    def rec(r, cols, regs, prev_bit):
        nonlocal nodes, count, aborted
        if r == n:
            count += 1
            return cap is not None and count >= cap
        nodes += 1
        if node_limit is not None and nodes > node_limit:
            aborted = True
            return True
        if deadline is not None and (nodes & 1023) == 0 and time.perf_counter() > deadline:
            aborted = True
            return True
        free = full & ~cols
        # every unused region must still reach a free column in rows >= r
        for g in range(n):
            if not (regs >> g) & 1 and not (suf[g][r] & free):
                return False
        banned = prev_bit | (prev_bit << 1) | (prev_bit >> 1)
        avail = free & ~banned
        while avail:
            low = avail & -avail
            avail ^= low
            c = low.bit_length() - 1
            g = cell_reg[r][c]
            if (regs >> g) & 1:
                continue
            if rec(r + 1, cols | low, regs | (1 << g), low):
                return True
        return False

    rec(0, 0, 0, 0)
    if aborted:
        return None
    return count
