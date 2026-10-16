"""Region-shape ugliness metric (ported from exp3.py)."""
from .board import normalize


def ugliness_parts(regions):
    """Returns (ugliness, per-region list)."""
    reg, n = normalize(regions)
    us = []
    for g in range(n):
        cs = {i for i in range(n * n) if reg[i] == g}
        A = len(cs)

        def nb(i):
            r, c = divmod(i, n)
            return [(r + a) * n + c + b for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))
                    if 0 <= r + a < n and 0 <= c + b < n and (r + a) * n + c + b in cs]

        P = sum(4 - len(nb(i)) for i in cs)
        comp = P * P / (16 * A) - 1

        def inblock(i):
            r, c = divmod(i, n)
            for a in (0, -1):
                for b in (0, -1):
                    if not (0 <= r + a and r + a + 1 < n and 0 <= c + b and c + b + 1 < n):
                        continue
                    q = [(r + a) * n + c + b, (r + a + 1) * n + c + b,
                         (r + a) * n + c + b + 1, (r + a + 1) * n + c + b + 1]
                    if all(x in cs for x in q):
                        return True
            return False

        cor = {i for i in cs if len(nb(i)) <= 2 and not inblock(i)}
        seen = set()
        best = 0
        for i in cor:
            if i in seen:
                continue
            st = [i]
            seen.add(i)
            k = 0
            while st:
                y = st.pop()
                k += 1
                for z in nb(y):
                    if z in cor and z not in seen:
                        seen.add(z)
                        st.append(z)
            best = max(best, k)
        br = sum(1 for i in cs if len(nb(i)) >= 3 and not inblock(i)) if A > 1 else 0
        gaps = 0
        for r in range(n):
            cc = sorted(c for c in range(n) if r * n + c in cs)
            gaps += sum(1 for a, b in zip(cc, cc[1:]) if b > a + 1)
        for c in range(n):
            rr = sorted(r for r in range(n) if r * n + c in cs)
            gaps += sum(1 for a, b in zip(rr, rr[1:]) if b > a + 1)
        us.append(comp + 0.5 * max(0, best - 2) + 0.7 * br + 1.0 * gaps)
    return sum(us) / n + 0.5 * max(us), us


def ugliness(regions):
    return ugliness_parts(regions)[0]
