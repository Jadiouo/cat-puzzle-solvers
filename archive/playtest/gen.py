import random, time
D4=((1,0),(-1,0),(0,1),(0,-1))

def rand_solution(n, rng):
    while True:
        cols=[]
        def rec(r):
            if r==n: return True
            cs=list(range(n)); rng.shuffle(cs)
            for c in cs:
                if c in cols or (cols and abs(cols[-1]-c)<=1): continue
                cols.append(c)
                if rec(r+1): return True
                cols.pop()
            return False
        if rec(0): return list(cols)

def count_solutions(reg, n, cap):
    """reg: flat list n*n region idx. Row-by-row DFS with bitmasks; stops at cap."""
    cnt=0
    def rec(r, cm, rm, prev):
        nonlocal cnt
        if r==n:
            cnt+=1; return cnt>=cap
        base=r*n
        for c in range(n):
            if cm>>c&1 or (prev>=0 and -2<c-prev<2): continue
            g=reg[base+c]
            if rm>>g&1: continue
            if rec(r+1, cm|1<<c, rm|1<<g, c): return True
        return False
    rec(0,0,0,-99)
    return cnt

def grow(n, sol, rng):
    reg=[-1]*(n*n)
    fr=[]
    for r,c in enumerate(sol):
        reg[r*n+c]=r
    cells=n*n-n
    # random growth: pick random region (weighted by randomness), expand to random free neighbour
    frontier=[[ (r*n+sol[r]) ] for r in range(n)]
    free=cells
    while free:
        g=min(rng.randrange(n),rng.randrange(n),key=lambda q:len(frontier[q]))
        cand=[]
        for x in frontier[g]:
            r,c=divmod(x,n)
            for dr,dc in D4:
                a,b=r+dr,c+dc
                if 0<=a<n and 0<=b<n and reg[a*n+b]<0: cand.append(a*n+b)
        if not cand: continue
        y=rng.choice(cand); reg[y]=g; frontier[g].append(y); free-=1
    return reg

def connected_without(reg, n, g, drop):
    cells=[i for i in range(n*n) if reg[i]==g and i!=drop]
    if not cells: return False
    seen={cells[0]}; st=[cells[0]]; S=set(cells)
    while st:
        x=st.pop(); r,c=divmod(x,n)
        for dr,dc in D4:
            a,b=r+dr,c+dc
            if 0<=a<n and 0<=b<n:
                y=a*n+b
                if y in S and y not in seen: seen.add(y); st.append(y)
    return len(seen)==len(S)

def viol(reg,n,lo,hi):
    sz=[0]*n
    for g in reg: sz[g]+=1
    return sum(max(0,lo-z)+max(0,z-hi) for z in sz)

def generate(n, rng, tlimit=15.0, objcap=40, lo=3, hi=None):
    if hi is None: hi=2*n+(2 if n==6 else 0)
    """returns (reg, sol, stats) or None on timeout."""
    t0=time.time(); restarts=0; iters=0
    while time.time()-t0<tlimit:
        restarts+=1
        sol=rand_solution(n,rng); reg=grow(n,sol,rng)
        catset={r*n+sol[r] for r in range(n)}
        cur=(viol(reg,n,lo,hi),count_solutions(reg,n,objcap))
        stall=0
        while cur!=(0,1) and time.time()-t0<tlimit and stall<1500:
            iters+=1
            x=rng.randrange(n*n)
            if x in catset: stall+=1; continue
            r,c=divmod(x,n); old=reg[x]
            nb={reg[(r+dr)*n+c+dc] for dr,dc in D4 if 0<=r+dr<n and 0<=c+dc<n}-{old}
            if not nb: stall+=1; continue
            new=rng.choice(sorted(nb))
            if not connected_without(reg,n,old,x): stall+=1; continue
            reg[x]=new
            v=viol(reg,n,lo,hi)
            k=(v,count_solutions(reg,n,objcap) if v<=cur[0] else 10**9)
            if k<=cur:
                stall = 0 if k<cur else stall+1
                cur=k
            else:
                reg[x]=old; stall+=1
        if cur==(0,1):
            return reg,sol,dict(restarts=restarts,iters=iters,time=time.time()-t0)
    return None


def steer(reg, sol, n, rng, scorefn, direction, tlimit, lo=3, hi=None):
    """from a unique puzzle, random single-cell moves keeping uniqueness+shape; accept if score moves in direction (+1 hard, -1 easy)."""
    if hi is None: hi=2*n+(2 if n==6 else 0)
    catset={r*n+sol[r] for r in range(n)}
    cur=scorefn(reg); t0=time.time()
    while time.time()-t0<tlimit:
        x=rng.randrange(n*n)
        if x in catset: continue
        r,c=divmod(x,n); old=reg[x]
        nb={reg[(r+dr)*n+c+dc] for dr,dc in D4 if 0<=r+dr<n and 0<=c+dc<n}-{old}
        if not nb: continue
        new=rng.choice(sorted(nb))
        if not connected_without(reg,n,old,x): continue
        reg[x]=new
        if viol(reg,n,lo,hi)==0 and count_solutions(reg,n,2)==1:
            sc=scorefn(reg)
            if sc is not None and (sc-cur)*direction>=0: cur=sc; continue
        reg[x]=old
    return cur
