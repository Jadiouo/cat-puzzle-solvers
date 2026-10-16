"""Board helpers shared by generator, grader and ugliness. Cells are flat indices r*n+c."""
D4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
MIN_REGION = 3


def max_region_size(n):
    """Upper bound of a region's size (spike rule: 2N, N=6 allowed up to 14)."""
    return 2 * n + (2 if n == 6 else 0)


def normalize(regions):
    """Accept 2D list (any hashable labels) or flat list/str with int n inferred.
    Returns (flat list of region indices 0..n-1, n)."""
    if regions and isinstance(regions[0], (list, tuple, str)) and len(regions[0]) == len(regions):
        rows = [list(r) for r in regions]
        n = len(rows)
        flat = [x for r in rows for x in r]
        if any(len(r) != n for r in rows):
            raise ValueError("regions must be N x N")
    else:
        flat = list(regions)
        n = int(round(len(flat) ** 0.5))
        if n * n != len(flat):
            raise ValueError("flat regions length must be a square")
    labels = sorted(set(flat), key=lambda v: (str(type(v)), v))
    if len(labels) != n:
        raise ValueError(f"need exactly {n} regions, got {len(labels)}")
    m = {v: i for i, v in enumerate(labels)}
    return [m[v] for v in flat], n


def to_grid(reg, n):
    return [[reg[r * n + c] for c in range(n)] for r in range(n)]


def region_sizes(reg, n):
    sz = [0] * n
    for g in reg:
        sz[g] += 1
    return sz


def count_solutions(reg, n, cap):
    """Row-by-row DFS with bitmasks; stops at cap. Counts valid placements."""
    cnt = 0

    def rec(r, cm, rm, prev):
        nonlocal cnt
        if r == n:
            cnt += 1
            return cnt >= cap
        base = r * n
        for c in range(n):
            if cm >> c & 1 or (prev >= 0 and -2 < c - prev < 2):
                continue
            g = reg[base + c]
            if rm >> g & 1:
                continue
            if rec(r + 1, cm | 1 << c, rm | 1 << g, c):
                return True
        return False

    rec(0, 0, 0, -99)
    return cnt


def connected_without(reg, n, g, drop):
    cells = [i for i in range(n * n) if reg[i] == g and i != drop]
    if not cells:
        return False
    seen = {cells[0]}
    st = [cells[0]]
    S = set(cells)
    while st:
        x = st.pop()
        r, c = divmod(x, n)
        for dr, dc in D4:
            a, b = r + dr, c + dc
            if 0 <= a < n and 0 <= b < n:
                y = a * n + b
                if y in S and y not in seen:
                    seen.add(y)
                    st.append(y)
    return len(seen) == len(S)


def is_connected(reg, n, g):
    return connected_without(reg, n, g, -1)


def size_violation(reg, n, lo=MIN_REGION, hi=None):
    if hi is None:
        hi = max_region_size(n)
    return sum(max(0, lo - z) + max(0, z - hi) for z in region_sizes(reg, n))
