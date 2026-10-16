"""(B) Propagation + branching hybrid on bitboards. Pure stdlib.

Each node runs cheap propagation to a fixed point, then branches on the undone unit
(row/col/region) with the fewest candidates. Propagation rules (every one is a sound
elimination or forced placement, so exact counts are preserved):
  S   single: an undone unit with one candidate -> place; with zero -> contradiction
  T3  a unit whose candidates all lie in one unit of another type (region<->row/col):
      clear the rest of that unit
  T3b cover exclusion: x is removed if placing x clears every candidate of some undone unit
      not containing x (computed as: x in intersection of KILL[y] over that unit's candidates y)
  K2  pairs: two units of one type whose candidates touch only two units of another type
      -> clear everything else in those two units (pigeonhole); touching < 2 -> contradiction
Adapters (propagation set): hybrid_s = S, hybrid_t3 = S+T3, hybrid_t3b = S+T3+T3b (default
class `HybridAdapter` name "hybrid"), hybrid_k2 = S+T3+T3b+K2.
Extra result keys: "branches", "forced" (cats placed by propagation), "elims" (T3/T3b/K2 rounds).
"""
import time

from .solver_bitmask import MODES, _Timeout, build_tables, cats_to_solution, finish


def _bits(m):
    while m:
        low = m & -m
        yield low.bit_length() - 1
        m ^= low


class HybridAdapter:
    name = "hybrid"
    modes = MODES
    exhaustive = True
    use_t3 = True
    use_t3b = True
    use_k2 = False

    def solve(self, regions, mode, timeout_s):
        t0 = time.perf_counter()
        n = len(regions)
        T = build_tables(regions)
        if T is None:
            return {"status": "UNSAT", "solutions": [], "count": 0, "complete": True,
                    "nodes": 0, "elapsed": time.perf_counter() - t0}
        ROW, COL, REG, UN = T["ROW"], T["COL"], T["REG"], T["UN"]
        KILL, UBIT, FULL = T["KILL"], T["UBIT"], T["FULL"]
        units = range(3 * n)
        use_t3, use_t3b, use_k2 = self.use_t3, self.use_t3b, self.use_k2
        limit = {"first": 1, "classify": 2, "count": None}[mode]
        deadline = t0 + timeout_s
        sols = []
        st = {"nodes": 0, "forced": 0, "elims": 0}
        BIG = 1 << 30
        types = (ROW, COL, REG)

        def prop(alive, done, cats):
            """Returns (alive, done, cats) at fixed point, or None on contradiction."""
            while True:
                changed = False
                for u in units:                                   # S
                    if done >> u & 1:
                        continue
                    m = alive & UN[u]
                    if not m:
                        return None
                    if not m & (m - 1):
                        x = m.bit_length() - 1
                        alive &= ~KILL[x]
                        done |= UBIT[x]
                        cats |= m
                        st["forced"] += 1
                        changed = True
                if changed:
                    continue
                if done == FULL:
                    return alive, done, cats
                if use_t3:                                        # T3
                    rm = 0
                    for g in range(n):
                        if done >> (2 * n + g) & 1:
                            continue
                        m = alive & REG[g]
                        x = (m & -m).bit_length() - 1
                        r, c = divmod(x, n)
                        if not m & ~ROW[r]:
                            rm |= ROW[r] & ~REG[g]
                        if not m & ~COL[c]:
                            rm |= COL[c] & ~REG[g]
                    for u in range(2 * n):
                        if done >> u & 1:
                            continue
                        m = alive & UN[u]
                        x = (m & -m).bit_length() - 1
                        # region of x: find via UBIT (bits 2n..3n-1)
                        g = (UBIT[x] >> (2 * n)).bit_length() - 1
                        if not m & ~REG[g]:
                            rm |= REG[g] & ~UN[u]
                    rm &= alive
                    if rm:
                        alive &= ~rm
                        st["elims"] += 1
                        continue
                if use_t3b:                                       # T3b
                    rm = 0
                    for u in units:
                        if done >> u & 1:
                            continue
                        m = alive & UN[u]
                        acc = alive & ~m & ~rm
                        mm = m
                        while mm and acc:
                            low = mm & -mm
                            acc &= KILL[low.bit_length() - 1]
                            mm ^= low
                        rm |= acc
                    if rm:
                        alive &= ~rm
                        st["elims"] += 1
                        continue
                if use_k2:                                        # K2
                    rm = 0
                    for ta in range(3):
                        A = types[ta]
                        for tb in range(3):
                            if ta == tb:
                                continue
                            B = types[tb]
                            cand = []
                            for i in range(n):
                                if done >> (ta * n + i) & 1:
                                    continue
                                m = alive & A[i]
                                t = 0
                                cnt = 0
                                for j in range(n):
                                    if m & B[j]:
                                        t |= 1 << j
                                        cnt += 1
                                        if cnt > 2:
                                            break
                                if cnt <= 2:
                                    cand.append((t, m))
                            for a in range(len(cand)):
                                ta_, ma = cand[a]
                                for b in range(a + 1, len(cand)):
                                    tb_, mb = cand[b]
                                    u2 = ta_ | tb_
                                    k = u2.bit_count()
                                    if k < 2:
                                        return None
                                    if k == 2:
                                        cells = ma | mb
                                        for j in _bits(u2):
                                            rm |= B[j] & alive & ~cells
                    if rm:
                        alive &= ~rm
                        st["elims"] += 1
                        continue
                return alive, done, cats

        def rec(alive, done, cats):
            st["nodes"] += 1
            if not st["nodes"] & 63 and time.perf_counter() > deadline:
                raise _Timeout
            r = prop(alive, done, cats)
            if r is None:
                return False
            alive, done, cats = r
            if done == FULL:
                sols.append(cats_to_solution(cats, n))
                return limit is not None and len(sols) >= limit
            bc, bm = BIG, 0
            for u in units:
                if done >> u & 1:
                    continue
                m = alive & UN[u]
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
        nodes = st["nodes"]
        return finish(mode, limit, sols, nodes, t0, timed_out,
                      {"branches": max(nodes - 1, 0), "forced": st["forced"],
                       "elims": st["elims"]})


class HybridSAdapter(HybridAdapter):
    name = "hybrid_s"
    use_t3 = False
    use_t3b = False


class HybridT3Adapter(HybridAdapter):
    name = "hybrid_t3"
    use_t3b = False


class HybridK2Adapter(HybridAdapter):
    name = "hybrid_k2"
    use_k2 = True
