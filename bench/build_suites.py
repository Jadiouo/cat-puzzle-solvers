"""Build the benchmark suites (fixed seeds). Not run by the test-suite; outputs are committed
under bench/suites/. Usage: python3 -B -m bench.build_suites s1|s2|s3|s4|refs [--workers 14]

Reference counts come from methods independent of the solvers under test:
  levelgen.board.count_solutions  (plain row DFS, N<=9)   and/or
  bench.reference.count_solutions (bitmask DFS, any N)    -- counts must agree where both ran.
Last resort: cat_solver 'all' mode, labelled as non-independent. Not finished => count=null (unknown).
"""
import argparse
import json
import multiprocessing as mp
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUITES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "suites")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SUITE_META = {
    "S1": "levelgen pool.json: 300 unique-solution puzzles, N=6..9",
    "S2": "larger unique-solution puzzles from levelgen.generate (N=10,12,14), fixed seeds",
    "S3": "random connected regions, not planted: 0, 1 or many solutions; N=8,10,12,15,20,25 x20",
    "S4": "hard: planted solution, near-uniform region sizes (~N each) so propagation is weak; N=10..20",
}


def path(s):
    return os.path.join(SUITES, f"{s}.json")


def save(suite, puzzles, extra=None):
    os.makedirs(SUITES, exist_ok=True)
    doc = {"suite": suite, "description": SUITE_META[suite], **(extra or {}), "puzzles": puzzles}
    with open(path(suite), "w") as f:
        json.dump(doc, f, separators=(",", ":"))
        f.write("\n")


def load(suite):
    with open(path(suite)) as f:
        return json.load(f)


# ---------------------------------------------------------------- random generators
def _neighbors(n, r, c):
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        a, b = r + dr, c + dc
        if 0 <= a < n and 0 <= b < n:
            yield a, b


def random_connected(n, rng):
    """N connected regions from N random seed cells, random frontier growth."""
    grid = [[-1] * n for _ in range(n)]
    cells = [(r, c) for r in range(n) for c in range(n)]
    for g, (r, c) in enumerate(rng.sample(cells, n)):
        grid[r][c] = g
    frontier = [(r, c) for r in range(n) for c in range(n) if grid[r][c] < 0
                and any(grid[a][b] >= 0 for a, b in _neighbors(n, r, c))]
    left = n * n - n
    while left:
        r, c = frontier.pop(rng.randrange(len(frontier)))
        if grid[r][c] >= 0:
            continue
        grid[r][c] = rng.choice([grid[a][b] for a, b in _neighbors(n, r, c) if grid[a][b] >= 0])
        left -= 1
        for a, b in _neighbors(n, r, c):
            if grid[a][b] < 0:
                frontier.append((a, b))
    return grid


def random_solution(n, rng):
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

    rec(0)
    return cols


def balanced_planted(n, rng):
    """Regions seeded at the cells of a planted solution; always grow the smallest region
    that still has a free neighbour, so every region ends up with about N cells."""
    sol = random_solution(n, rng)
    grid = [[-1] * n for _ in range(n)]
    for r, c in enumerate(sol):
        grid[r][c] = r
    size = [1] * n
    left = n * n - n
    while left:
        order = sorted(range(n), key=lambda g: (size[g], rng.random()))
        for g in order:
            cand = [(a, b) for r in range(n) for c in range(n) if grid[r][c] == g
                    for a, b in _neighbors(n, r, c) if grid[a][b] < 0]
            if cand:
                a, b = rng.choice(cand)
                grid[a][b] = g
                size[g] += 1
                left -= 1
                break
    return grid, sol


# ---------------------------------------------------------------- suites
def build_s1():
    with open(os.path.join(ROOT, "levelgen", "pool", "pool.json")) as f:
        pool = json.load(f)
    ps = [{"id": p["id"], "n": p["size"], "regions": p["regions"], "planted": p["solution"],
           "level": p["level"]} for p in pool["puzzles"]]
    save("S1", ps, {"seed": pool["meta"]["seed"]})


def _gen_one(args):
    n, seed = args
    from levelgen import generate
    t = time.time()
    p = generate(n, seed)
    return n, seed, p, time.time() - t


def build_s2(workers, per_task, seeds_per_n, ns=(10, 12, 14)):
    """Run generate() for every (n, seed) in parallel; give up on tasks over `per_task` s."""
    tasks = [(n, s) for n in ns for s in range(1, seeds_per_n + 1)]
    done, report = [], {}
    pending = list(tasks)
    running = {}
    q = mp.Queue()

    def worker(a):
        q.put(_gen_one(a))

    while pending or running:
        while pending and len(running) < workers:
            a = pending.pop(0)
            pr = mp.Process(target=worker, args=(a,))
            pr.start()
            running[a] = (pr, time.time())
        try:
            n, s, p, dt = q.get(timeout=1)
            pr, _ = running.pop((n, s))
            pr.join()
            rep = report.setdefault(n, {"ok": 0, "fail": 0, "timeout": 0, "secs": []})
            if p is None:
                rep["fail"] += 1
            else:
                rep["ok"] += 1
                rep["secs"].append(round(dt, 1))
                done.append({"id": f"S2-n{n}-s{s}", "n": n, "regions": p["regions"],
                             "planted": p["solution"], "seed": s})
            print("gen", n, s, "ok" if p else "FAIL", round(dt, 1), flush=True)
        except Exception:
            pass
        for a, (pr, t0) in list(running.items()):
            if time.time() - t0 > per_task:
                pr.kill()
                pr.join()
                del running[a]
                report.setdefault(a[0], {"ok": 0, "fail": 0, "timeout": 0, "secs": []})["timeout"] += 1
                print("gen", *a, "TIMEOUT", per_task, flush=True)
    rep = {str(k): {**v, "seeds_tried": seeds_per_n, "per_task_limit_s": per_task}
           for k, v in report.items()}
    if os.path.exists(path("S2")):      # keep results for N values not re-run now
        old = load("S2")
        done += [p for p in old["puzzles"] if p["n"] not in ns]
        rep = {**{k: v for k, v in old.get("generation_report", {}).items() if int(k) not in ns}, **rep}
    done.sort(key=lambda p: (p["n"], p["seed"]))
    save("S2", done, {"generation_report": dict(sorted(rep.items(), key=lambda kv: int(kv[0])))})


def build_s3():
    ps = []
    for n in (8, 10, 12, 15, 20, 25):
        for i in range(20):
            rng = random.Random(f"bench:S3:{n}:{i}")
            ps.append({"id": f"S3-n{n}-{i:02d}", "n": n, "regions": random_connected(n, rng)})
    save("S3", ps, {"seed": "bench:S3:<n>:<i>"})


def build_s4():
    ps = []
    for n in (10, 12, 14, 16, 18, 20):
        for i in range(5):
            rng = random.Random(f"bench:S4:{n}:{i}")
            grid, sol = balanced_planted(n, rng)
            ps.append({"id": f"S4-n{n}-{i:02d}", "n": n, "regions": grid, "planted": sol})
    save("S4", ps, {"seed": "bench:S4:<n>:<i>"})


# ---------------------------------------------------------------- reference counts
def _ref_one(args):
    suite, pid, grid, tl = args
    from bench import reference
    from levelgen import board
    n = len(grid)
    t = time.time()
    c = reference.count_solutions(grid, time_limit=tl)
    out = {"count": c, "source": "bench.reference bitmask DFS", "seconds": round(time.time() - t, 2)}
    if n <= 9:
        flat = [x for row in grid for x in row]
        b = board.count_solutions(flat, n, 10 ** 9)
        out["cross_check"] = {"levelgen.board.count_solutions": b}
        if c is None or b != c:
            out["count"] = b if c is None else None
            out["source"] = "levelgen.board.count_solutions brute force"
            if c is not None:
                out["conflict"] = [c, b]
    if out["count"] is None:
        # last resort, NOT independent of the solver under test
        from cat_solver import SolveOptions, parse_puzzle, solve
        p = parse_puzzle({"schema_version": "1.0", "size": n,
                          "regions": [[f"R{x}" for x in row] for row in grid]})
        r = solve(p, SolveOptions(mode="all", timeout_ms=tl * 1000))
        if r.status in ("SOLVED", "UNSAT"):
            out["count"] = len(r.solutions)
            out["source"] = "cat_solver all-mode (NOT independent)"
    if out["count"] is None:
        out["source"] = "unknown (bench.reference and cat_solver both exceeded the time limit)"
    return pid, out


def build_refs(suites, workers, tl):
    for s in suites:
        doc = load(s)
        jobs = [(s, p["id"], p["regions"], tl) for p in doc["puzzles"]]
        with mp.Pool(workers) as pool:
            res = dict(pool.imap_unordered(_ref_one, jobs, chunksize=1))
        for p in doc["puzzles"]:
            p["ref"] = res[p["id"]]
        doc["ref_time_limit_s"] = tl
        with open(path(s), "w") as f:
            json.dump(doc, f, separators=(",", ":"))
            f.write("\n")
        unk = sum(1 for p in doc["puzzles"] if p["ref"]["count"] is None)
        bad = sum(1 for p in doc["puzzles"] if "conflict" in p["ref"])
        print(f"{s}: {len(doc['puzzles'])} puzzles, unknown={unk}, conflicts={bad}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["s1", "s2", "s3", "s4", "refs"])
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--suites", nargs="+", default=["S1", "S2", "S3", "S4"])
    ap.add_argument("--per-task", type=int, default=300)
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--ns", type=int, nargs="+", default=[10, 12, 14])
    ap.add_argument("--ref-limit", type=int, default=120)
    a = ap.parse_args()
    if a.what == "s1":
        build_s1()
    elif a.what == "s2":
        build_s2(a.workers, a.per_task, a.seeds, tuple(a.ns))
    elif a.what == "s3":
        build_s3()
    elif a.what == "s4":
        build_s4()
    else:
        build_refs(a.suites, a.workers, a.ref_limit)


if __name__ == "__main__":
    main()
