"""Independent rule checker (does not import any solver). Grid regions are N x N ints."""


def violations(regions, sol):
    """sol = column index per row. Returns list of rule violations (empty = valid)."""
    n = len(regions)
    out = []
    if not isinstance(sol, (list, tuple)) or len(sol) != n:
        return ["length"]
    if any((not isinstance(c, int)) or not 0 <= c < n for c in sol):
        return ["range"]
    if len(set(sol)) != n:
        out.append("column")
    if len({regions[r][c] for r, c in enumerate(sol)}) != n:
        out.append("region")
    for r in range(n - 1):
        if abs(sol[r] - sol[r + 1]) <= 1:
            out.append(f"adjacent@{r}")
    return out


def is_valid(regions, sol):
    return not violations(regions, sol)
