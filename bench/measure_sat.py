"""Timing/correctness harness for the SAT / CP-SAT adapters (does not touch bench.runner).

  .venv/bin/python -B -m bench.measure_sat --suite S1 --mode classify count --adapters ALL \
      --repeat 2 --timeout 10 --jobs 3 --out /path/res.json

Each (puzzle, adapter, mode, repeat) is a fresh subprocess with a hard kill at timeout+3 s.
Per cell we keep the median of build_s / solve_s / elapsed over the repeats, plus import_s.
Verdict comes from bench.runner.judge (reference comparison + independent rule checker).
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from . import runner, solver_sat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def worker():
    task = json.loads(sys.stdin.read())
    try:
        res = solver_sat.ADAPTERS[task["adapter"]].solve(task["regions"], task["mode"], task["timeout"])
    except Exception:
        import traceback
        res = {"status": "ERROR", "solutions": [], "count": None, "complete": False,
               "nodes": None, "elapsed": 0.0, "error": traceback.format_exc()[-400:]}
    sys.stdout.write(json.dumps(res))


def run_one(adapter, puzzle, mode, timeout):
    task = json.dumps({"adapter": adapter, "regions": puzzle["regions"], "mode": mode,
                       "timeout": timeout})
    try:
        cp = subprocess.run([sys.executable, "-B", "-m", "bench.measure_sat", "--worker"],
                            input=task, text=True, capture_output=True, cwd=ROOT,
                            timeout=timeout + runner.GRACE)
        return json.loads(cp.stdout)
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "solutions": [], "count": None, "complete": False,
                "nodes": None, "elapsed": float(timeout), "build_s": None, "solve_s": None,
                "killed": True}
    except ValueError:
        return {"status": "ERROR", "solutions": [], "count": None, "complete": False,
                "nodes": None, "elapsed": 0.0, "error": cp.stderr[-200:]}


def cell(job):
    adapter, sname, p, mode, timeout, repeat = job
    rs = []
    for _ in range(repeat):
        r = run_one(adapter, p, mode, timeout)
        rs.append(r)
        if r["status"] in ("TIMEOUT", "ERROR"):
            break
    r = rs[-1]
    med = lambda k: (statistics.median(x[k] for x in rs if x.get(k) is not None)
                     if any(x.get(k) is not None for x in rs) else None)
    out = dict(r)
    out["elapsed"] = med("elapsed") if r["status"] not in ("TIMEOUT", "ERROR") else r["elapsed"]
    for k in ("build_s", "solve_s", "import_s"):
        out[k] = med(k)
    verdict, note = runner.judge(p, mode, out, timeout)
    ref = (p.get("ref") or {}).get("count")
    return {"suite": sname, "id": p["id"], "n": p["n"], "adapter": adapter, "mode": mode,
            "status": out["status"], "verdict": verdict, "note": note, "count": out.get("count"),
            "ref_count": ref, "elapsed": out["elapsed"], "build_s": out["build_s"],
            "solve_s": out["solve_s"], "import_s": out["import_s"], "reps": len(rs)}


def main():
    if "--worker" in sys.argv:
        return worker()
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", nargs="+", required=True)
    ap.add_argument("--mode", nargs="+", default=["classify"])
    ap.add_argument("--adapters", nargs="+", default=["ALL"])
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--per-n", type=int, default=0)
    ap.add_argument("--n", type=int, nargs="+")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    names = list(solver_sat.ADAPTERS) if a.adapters == ["ALL"] else a.adapters
    jobs = []
    for sname in a.suite:
        for p in runner.select(runner.load_suite(sname), a.per_n, a.n):
            for ad in names:
                for mode in a.mode:
                    jobs.append((ad, sname, p, mode, a.timeout, a.repeat))
    t0 = time.time()
    with ThreadPoolExecutor(a.jobs) as ex:
        rows = list(ex.map(cell, jobs))
    json.dump({"argv": sys.argv[1:], "wall_s": time.time() - t0, "load": os.getloadavg(),
               "rows": rows}, open(a.out, "w"))
    bad = [r for r in rows if r["verdict"] in ("MISMATCH", "ERROR")]
    print(f"{len(rows)} cells, wall {time.time()-t0:.0f}s, mismatch/error {len(bad)}")
    for r in bad[:10]:
        print(r)


if __name__ == "__main__":
    main()
