"""Build 12 playtest puzzles (deterministic). Run: python -B build_playtest.py"""
import math, random, json, itertools, os, sys
from collections import Counter
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gen import generate
from solver import solve, score

POOL = {6: 120, 7: 100, 8: 40, 9: 14}

def brute_count(reg, n):
    """Independent check: permutations, no import of generator/solver logic."""
    cnt = 0
    for p in itertools.permutations(range(n)):
        if any(abs(p[i] - p[i + 1]) <= 1 for i in range(n - 1)):
            continue
        if len({reg[i * n + p[i]] for i in range(n)}) == n:
            cnt += 1
            if cnt > 1:
                break
    return cnt

def connected(reg, n):
    for g in range(n):
        cs = [i for i in range(n * n) if reg[i] == g]
        seen = {cs[0]}; st = [cs[0]]
        while st:
            r, c = divmod(st.pop(), n)
            for a, b in ((r+1,c),(r-1,c),(r,c+1),(r,c-1)):
                if 0 <= a < n and 0 <= b < n:
                    y = a * n + b
                    if reg[y] == g and y not in seen:
                        seen.add(y); st.append(y)
        if len(seen) != len(cs):
            return False
    return True

def pool_for(n):
    rng = random.Random(4242 + n)
    out = []
    for _ in range(POOL[n]):
        g = generate(n, rng, tlimit=600)
        reg, sol, _ = g
        got, use, st = solve(reg, n)
        assert st == 'ok' and got == [r*n+sol[r] for r in range(n)]
        _, _, st0 = solve(reg, n, t5=False)
        out.append(dict(reg=list(reg), sol=sol, use=use, score=score(use), needT5=(st0 != 'ok')))
    return out

def pick(pool, mid_no_t5):
    """low = easiest no-T5; high = hardest T5; mid = closest (log scale) to the geometric mean."""
    no = sorted([p for p in pool if not p['needT5']], key=lambda p: p['score'])
    yes = sorted([p for p in pool if p['needT5']], key=lambda p: p['score'])
    low, high = no[0], yes[-1]
    target = (low['score'] * high['score']) ** 0.5
    rest = [p for p in pool if p is not low and p is not high]
    if mid_no_t5:  # hardest no-T5 puzzle (T3/T4-heavy), keeps >=5 puzzles solvable without T5
        mid = max([p for p in rest if not p['needT5']], key=lambda p: p['score'])
    else:
      mid = min(rest, key=lambda p: (abs(math.log(p['score'] / target)), p['score']))
    return [low, mid, high]

puzzles = []
for n in (6, 7, 8, 9):
    for tier, p in zip(('low', 'mid', 'high'), pick(pool_for(n), n in (6, 7))):
        reg = p['reg']; sizes = Counter(reg)
        assert connected(reg, n) and len(sizes) == n
        hi = 2 * n + (2 if n == 6 else 0)
        assert 3 <= min(sizes.values()) and max(sizes.values()) <= hi
        assert brute_count(reg, n) == 1, 'not unique'
        u = p['use']
        puzzles.append(dict(
            id=f"p{n}{tier[0]}", size=n, tier=tier,
            regions=[''.join(chr(65 + reg[r*n+c]) for c in range(n)) for r in range(n)],
            solution=[[r, p['sol'][r]] for r in range(n)],
            score=p['score'],
            techniques={k: u[k] for k in ('T2', 'T3', 'T4', 'T5', 'T5depth')},
            needs_T5=p['needT5'],
            max_region=max(sizes.values()), min_region=min(sizes.values())))
print([(q['id'],q['score'],q['needs_T5']) for q in puzzles])
assert sum(not q['needs_T5'] for q in puzzles) >= 5 and sum(q['needs_T5'] for q in puzzles) >= 4
with open(os.path.join(HERE, 'playtest-puzzles.json'), 'w') as f:
    json.dump(puzzles, f, ensure_ascii=False, indent=1, sort_keys=True)
for q in puzzles:
    print(q['id'], q['size'], q['score'], q['needs_T5'], q['min_region'], q['max_region'])

# embed (score/techniques deliberately omitted: blind test)
order = [q['id'] for q in puzzles]
random.Random(20261015).shuffle(order)
data = dict(order=order, puzzles=[dict(id=q['id'], size=q['size'], regions=q['regions'], solution=q['solution']) for q in puzzles])
hp = os.path.join(HERE, 'playtest.html')
html = open(hp, encoding='utf-8').read()
import re
html = re.sub(r'/\*DATA\*/.*?/\*END\*/', lambda m: '/*DATA*/' + json.dumps(data, separators=(',', ':')) + '/*END*/', html, flags=re.S)
open(hp, 'w', encoding='utf-8').write(html)
print('order', order)
