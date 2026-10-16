"""Fidelity check + benchmark: C++ vs Python, per puzzle.

  python3 -B native/compare.py --suites S1 S2 S3 S4 --timeout 10 --repeat 3 [--exe PATH] [--tag o2]

Python side runs in-process (one puzzle at a time, perf_counter solve time, median of --repeat;
a puzzle that times out is not repeated). Writes bench/results/native_<tag>.csv (long format) and
prints fidelity (node equality) and speed-up summaries.
"""
import argparse, csv, json, os, statistics, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from bench import solvers  # noqa: E402,F401  (import first: avoids a circular import)
from bench import solver_bitmask, solver_hybrid, solver_dlx, solver_native  # noqa: E402

PY = {"bitmask": solver_bitmask.BitmaskAdapter(), "hybrid": solver_hybrid.HybridAdapter(),
      "dlx": solver_dlx.DLXAdapter()}
FIELDS = ["suite", "id", "n", "solver", "mode", "impl", "status", "count", "nodes", "elapsed_s", "ns_per_node"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suites", nargs="+", default=["S1", "S2", "S3", "S4"])
    ap.add_argument("--solvers", nargs="+", default=list(PY))
    ap.add_argument("--modes", nargs="+", default=["classify", "count"])
    ap.add_argument("--timeout", type=float, default=10)
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--exe", default=None)
    ap.add_argument("--tag", default="o2")
    ap.add_argument("--skip-python", action="store_true", help="only run C++ (no equality check)")
    ap.add_argument("--py-csv", default=None, help="reuse python rows from this csv instead of rerunning")
    a = ap.parse_args()
    exe = a.exe or solver_native.EXE
    print("load", open("/proc/loadavg").read().strip(), "(start)", flush=True)
    rows = []
    cache = {}
    if a.py_csv:
        for r in csv.DictReader(open(a.py_csv)):
            if r["impl"] == "python":
                cache[(r["suite"], r["id"], r["solver"], r["mode"])] = r
    for sname in a.suites:
        d = json.load(open(os.path.join(ROOT, "bench", "suites", sname + ".json")))
        pz = [(p["id"], p["regions"], p["n"]) for p in d["puzzles"]]
        for sv in a.solvers:
            for mode in a.modes:
                nat = solver_native.run_batch(sv, mode, a.timeout, [(i, g) for i, g, _ in pz], a.repeat, exe)
                for (pid, g, n), c in zip(pz, nat):
                    rows.append(dict(suite=sname, id=pid, n=n, solver=sv, mode=mode, impl="cpp", status=c["status"],
                                     count=c["count"], nodes=c["nodes"], elapsed_s=c["elapsed"]))
                    if a.skip_python:
                        continue
                    key = (sname, pid, sv, mode)
                    if key in cache:
                        r = cache[key]
                        rows.append(dict(r, n=n)); continue
                    ts = []
                    for _ in range(a.repeat):
                        r = PY[sv].solve(g, mode, a.timeout)
                        ts.append(r["elapsed"])
                        if r["status"] == "TIMEOUT":
                            break
                    rows.append(dict(suite=sname, id=pid, n=n, solver=sv, mode=mode, impl="python", status=r["status"],
                                     count=r["count"], nodes=r["nodes"], elapsed_s=statistics.median(ts)))
                print(sname, sv, mode, "done", flush=True)
    for r in rows:
        nd = int(r["nodes"]) if r["nodes"] not in (None, "") else 0
        r["ns_per_node"] = f"{float(r['elapsed_s']) / nd * 1e9:.1f}" if nd else ""
    os.makedirs(os.path.join(ROOT, "bench", "results"), exist_ok=True)
    out = os.path.join(ROOT, "bench", "results", f"native_{a.tag}.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, FIELDS); w.writeheader(); w.writerows(rows)
    print("wrote", out)
    print("load", open("/proc/loadavg").read().strip(), "(end)")


if __name__ == "__main__":
    main()
