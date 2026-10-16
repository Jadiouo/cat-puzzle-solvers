"""C++ ports of the bitmask / hybrid / DLX solvers (native/cat_native.cpp) as bench adapters.

Why subprocess (not ctypes): the runner already isolates every solve in its own process, a
subprocess gives a hard kill with no shared state, and the binary needs no Python ABI glue.
Cost: ~1 ms process start, which is excluded because `elapsed` is the internal C++ timer
(steady_clock around table build + search; file parsing and process start excluded).

Registration (done later by the owner of solvers.py): add NATIVE_ADAPTERS to ADAPTERS.
Same result contract as bench.solvers.Adapter; extra keys "forced"/"elims" (hybrid).
"""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = os.environ.get("CAT_NATIVE_EXE", os.path.join(os.path.dirname(HERE), "native", "build", "cat_native"))
MODES = ("first", "classify", "count")


def available(exe=None):
    return os.path.isfile(exe or EXE) and os.access(exe or EXE, os.X_OK)


def line_for(pid, regions):
    n = len(regions)
    return f"{pid} {n} " + " ".join(str(v) for row in regions for v in row) + "\n"


def run_batch(solver, mode, timeout_s, puzzles, repeats=1, exe=None):
    """puzzles: iterable of (id, regions). Returns list of result dicts (one per puzzle)."""
    inp = "".join(line_for(i, g) for i, g in puzzles)
    p = subprocess.run([exe or EXE, "-s", solver, "-m", mode, "-t", str(timeout_s), "-r", str(repeats)],
                       input=inp, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"cat_native failed ({p.returncode}): {p.stderr[-200:]}")
    return [json.loads(l) for l in p.stdout.splitlines() if l.strip()]


class NativeAdapter:
    modes = MODES
    exhaustive = True
    solver = None

    def solve(self, regions, mode, timeout_s):
        if not available():
            return {"status": "ERROR", "solutions": [], "count": None, "complete": False,
                    "nodes": None, "elapsed": 0.0, "error": f"binary missing: {EXE} (run make -C native)"}
        r = run_batch(self.solver, mode, timeout_s, [("p", regions)])[0]
        out = {"status": r["status"], "solutions": r["solutions"], "count": r["count"],
               "complete": r["complete"], "nodes": r["nodes"], "elapsed": r["elapsed"]}
        if mode == "count":
            out["count_only"] = True   # count mode never stores solutions: judge must not expect a list
        if self.solver == "hybrid":
            out.update(forced=r["forced"], elims=r["elims"])
        if "error" in r:
            out["error"] = r["error"]
        return out


class NativeBitmask(NativeAdapter):
    name, solver = "native_bitmask", "bitmask"


class NativeHybrid(NativeAdapter):
    name, solver = "native_hybrid", "hybrid"


class NativeDLX(NativeAdapter):
    name, solver = "native_dlx", "dlx"


class NativeMatch(NativeAdapter):
    """bitmask DFS + per-node Hall/bipartite-matching check (regions->rows, regions->cols)."""
    name, solver = "native_match", "match"


class NativeRR(NativeAdapter):
    """bitmask DFS + random tie-break/value order + Luby restarts (seed 1). Complete; no count mode."""
    name, solver = "native_rr", "rr"
    modes = ("first", "classify")


class NativeMatchRR(NativeAdapter):
    name, solver = "native_match_rr", "match_rr"
    modes = ("first", "classify")


NATIVE_ADAPTERS = {a.name: a for a in (NativeBitmask(), NativeHybrid(), NativeDLX(),
                                       NativeMatch(), NativeRR(), NativeMatchRR())}
