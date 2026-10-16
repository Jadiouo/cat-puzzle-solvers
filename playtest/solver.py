from itertools import combinations
from collections import Counter

def make_units(reg, n):
    rows=[frozenset(r*n+c for c in range(n)) for r in range(n)]
    cols=[frozenset(r*n+c for r in range(n)) for c in range(n)]
    rg=[frozenset(i for i in range(n*n) if reg[i]==g) for g in range(n)]
    return {'row':rows,'col':cols,'reg':rg}

def neigh8(x,n):
    r,c=divmod(x,n); out=[]
    for a in range(r-1,r+2):
        for b in range(c-1,c+2):
            if 0<=a<n and 0<=b<n: out.append(a*n+b)
    return out

class State:
    def __init__(s,n,U):
        s.n=n; s.U=U; s.cand=set(range(n*n)); s.cats=set()
        s.N8=[neigh8(x,n) for x in range(n*n)]
        s.ulist=[(t,i,u) for t,L in U.items() for i,u in enumerate(L)]
        s.of={x:[(t,i) for t,L in U.items() for i,u in enumerate(L) if x in u] for x in range(n*n)}
    def copy(s):
        t=State.__new__(State); t.n=s.n; t.U=s.U; t.N8=s.N8; t.ulist=s.ulist; t.of=s.of
        t.cand=set(s.cand); t.cats=set(s.cats); return t
    def place(s,x):  # T1
        s.cats.add(x)
        rm=set(s.N8[x])
        for t,i in s.of[x]: rm|=s.U[t][i]
        s.cand-=rm
    def dead(s):
        for t,i,u in s.ulist:
            if not (u&s.cand) and not (u&s.cats): return True
        return False

def t2(s):  # singles; returns cell or None
    for t,i,u in s.ulist:
        if u&s.cats: continue
        c=u&s.cand
        if len(c)==1: return next(iter(c))
    return None

def subset_elim(s, kmin, kmax):
    """k units of type A whose cand lie within k units of type B -> remove other cand from those B units."""
    n=s.n
    types=['reg','row','col']
    for k in range(kmin,kmax+1):
        for A in types:
            for B in types:
                if A==B: continue
                un=[i for i,u in enumerate(s.U[A]) if not (u&s.cats)]
                if len(un)<=k: continue
                for combo in combinations(un,k):
                    cells=set()
                    for i in combo: cells|=s.U[A][i]&s.cand
                    # B units touched
                    bs={j for j,u in enumerate(s.U[B]) if u&cells}
                    if len(bs)==k:
                        rm=set()
                        for j in bs: rm|=s.U[B][j]&s.cand
                        rm-=cells
                        if rm:
                            s.cand-=rm; return True
    return False

def propagate_simple(s):
    d=0
    while True:
        if s.dead(): return False,d
        x=t2(s)
        if x is None: return True,d
        s.place(x); d+=1

def lookahead(s):
    """returns depth (>=1) of shallowest contradiction found, 0 if none; eliminates that cell."""
    best=None
    for x in sorted(s.cand):
        t=s.copy(); t.place(x)
        ok,d=propagate_simple(t)
        if not ok:
            if best is None or d<best[0]: best=(d,x)
            if d==0: break
    if best is None: return 0
    s.cand.discard(best[1]); return best[0]+1

def solve(reg,n,t5=True):
    s=State(n,make_units(reg,n)); use=Counter()
    while len(s.cats)<n:
        if s.dead(): return None,use,'dead'
        x=t2(s)
        if x is not None: use['T2']+=1; s.place(x); use['T1']+=1; continue
        if subset_elim(s,1,1): use['T3']+=1; continue
        if subset_elim(s,2,4): use['T4']+=1; continue
        if t5:
            d=lookahead(s)
            if d: use['T5']+=1; use['T5depth']+=d; continue
        return None,use,'guess'
    return sorted(s.cats),use,'ok'

def level(use):
    for l in ('T5','T4','T3'):
        if use[l]: return l
    return 'T2'

def score(use):
    """difficulty = 1*T2 + 3*T3 + 6*T4 + sum over T5 steps (6 + 2*depth); depth = forced placements before contradiction +1"""
    return use['T2']+3*use['T3']+6*use['T4']+6*use['T5']+2*use['T5depth']
