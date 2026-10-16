"""Subprocess entry: reads one JSON task on stdin, writes one JSON result on stdout."""
import json
import sys
import traceback


SAMPLE = 20


def main():
    task = json.loads(sys.stdin.read())
    from . import solvers
    try:
        res = solvers.get(task["solver"]).solve(task["regions"], task["mode"], task["timeout"])
    except Exception:
        res = {"status": "ERROR", "solutions": [], "count": None, "complete": False,
               "nodes": None, "elapsed": 0.0, "error": traceback.format_exc()[-400:]}
    # count mode can produce huge solution lists: keep the true count, return only a sample
    # (the sampling happens after the adapter's clock stopped, so it is not timed)
    sols = res.get("solutions") or []
    if len(sols) > SAMPLE:
        res["n_solutions"] = len(sols)
        step = len(sols) / SAMPLE
        res["solutions"] = [sols[int(i * step)] for i in range(SAMPLE)]
    else:
        res["n_solutions"] = len(sols)
    sys.stdout.write(json.dumps(res))


main()
