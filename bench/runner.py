"""Benchmark runner.

  python3 -B -m bench run --solvers cat_solver levelgen --suite S1 --mode classify --timeout 10
  python3 -B -m bench list                      # solvers and suites
  python3 -B -m bench report results/x.json     # re-print the summary of a finished run

Each (puzzle, solver, mode) runs in a fresh subprocess, one at a time, so a hang is killed at the
time limit and nothing leaks between runs. Timing = perf_counter around solve() inside the worker
(interpreter start-up, imports and parsing excluded). Hard kill at timeout + 3 s; any result slower
than 1.05 x timeout counts as TIMEOUT whichever way it ended.
"""
import argparse
import csv
import json
import os
import platform
import statistics
import subprocess
import sys
import time

from . import check, solvers

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SUITE_DIR = os.path.join(HERE, "suites")
RESULT_DIR = os.path.join(HERE, "results")
GRACE = 3.0
FIELDS = ["suite", "id", "n", "solver", "mode", "status", "elapsed_s", "elapsed_all", "nodes", "count",
          "build_s", "solve_s", "import_s", "core_s", "conflicts", "decisions", "propagations", "branches",
          "ref_count", "ref_source", "verdict", "note"]


def load_suite(name):
    p = os.path.join(SUITE_DIR, f"{name}.json")
    if not os.path.exists(p):
        raise SystemExit(f"suite {name} not found: {p}")
    with open(p) as f:
        return json.load(f)


def apply_satref(doc):
    """Puzzles whose reference is not independent (unknown, or cat_solver only) get the class from the
    SAT double confirmation (bench/suites/S3_S4_satref.json: CaDiCaL and CP-SAT agree, solutions valid).
    The reference then only knows the class 0 / 1 / >=2 ('class_only'); count mode compares min(count, 2).
    Returns the number of puzzles patched."""
    p = os.path.join(SUITE_DIR, "S3_S4_satref.json")
    if not os.path.exists(p):
        return 0
    with open(p) as f:
        sat = json.load(f)["puzzles"]
    k = 0
    for pz in doc["puzzles"]:
        src = str((pz.get("ref") or {}).get("source", ""))
        s = sat.get(pz["id"])
        if s and s.get("confirmed") and not src.startswith("bench.reference"):
            pz["ref"] = {"count": s["class"], "class_only": True,
                         "source": "SAT double confirmation (CaDiCaL + CP-SAT agree, solutions valid)"}
            k += 1
    return k


def judge(puzzle, mode, res, timeout):
    """Compare one solver result to the reference. Returns (verdict, note).
    Verdicts: OK, MISMATCH, TIMEOUT, ERROR, INCOMPLETE (inference stuck), NOREF (valid, no reference)."""
    st = res.get("status")
    if st == "ERROR":
        return "ERROR", (res.get("error") or "")[-120:].replace("\n", " | ")
    if st == "TIMEOUT" or (res.get("elapsed") or 0) > timeout * 1.05:
        return "TIMEOUT", ""
    grid = puzzle["regions"]
    sols = res.get("solutions") or []
    for s in sols:
        v = check.violations(grid, s)
        if v:
            return "MISMATCH", f"invalid solution {s}: {','.join(v)}"
    if len({tuple(s) for s in sols}) != len(sols):
        return "MISMATCH", "duplicate solutions"
    ref = (puzzle.get("ref") or {}).get("count")
    if ref is not None and sols and ref == 0:
        return "MISMATCH", "solution reported but reference count is 0"
    if st == "STUCK":
        return "INCOMPLETE", ""
    if ref is None and puzzle.get("planted") and (st == "UNSAT" or res.get("count") == 0):
        return "MISMATCH", "reported 0 solutions but a planted solution exists"
    cnt = res.get("count")
    nl = res.get("n_solutions", len(sols))   # worker returns only a sample of long lists
    if mode == "count" and cnt is not None and nl != cnt and st != "UNSAT" and not res.get("count_only"):
        return "MISMATCH", f"count {cnt} but {nl} solutions listed"
    if ref is None:
        return "NOREF", "reference unknown"
    class_only = bool((puzzle.get("ref") or {}).get("class_only"))   # ref = SAT-confirmed class 0/1/2
    if mode == "first":
        want = 1 if ref > 0 else 0
        got = 1 if sols else 0
    elif mode == "classify":
        want, got = min(ref, 2), cnt
    elif class_only:
        want, got = min(ref, 2), (None if cnt is None else min(cnt, 2))
    else:
        want, got = ref, cnt
    if got != want:
        return "MISMATCH", f"got {got} expected {want} (ref count {ref})"
    return "OK", ""


def run_task(solver, puzzle, mode, timeout):
    task = json.dumps({"solver": solver, "regions": puzzle["regions"], "mode": mode,
                       "timeout": timeout})
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    try:
        cp = subprocess.run([sys.executable, "-B", "-m", "bench._worker"], input=task, text=True,
                            capture_output=True, cwd=ROOT, env=env, timeout=timeout + GRACE)
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "solutions": [], "count": None, "complete": False,
                "nodes": None, "elapsed": float(timeout), "killed": True}
    try:
        return json.loads(cp.stdout)
    except ValueError:
        return {"status": "ERROR", "solutions": [], "count": None, "complete": False, "nodes": None,
                "elapsed": 0.0, "error": f"worker rc={cp.returncode}: {cp.stderr[-200:]}"}


def run_repeats(solver, puzzle, mode, timeout, repeat, runner=None):
    """Run one (solver, puzzle, mode) up to `repeat` times and fold them into one row.
    Rule (applied uniformly): if ANY repeat times out, the whole row is TIMEOUT (status and verdict
    both, elapsed = the time limit) - a solver that is only sometimes within the limit is not
    counted as having solved it. MISMATCH from any repeat still outranks TIMEOUT (a wrong answer
    is never hidden). Otherwise the first non-OK verdict is kept, elapsed = median of repeats.
    Returns (res, times, verdict, note); res["status"] never contradicts verdict == TIMEOUT."""
    runner = runner or run_task
    times, res, verdict, note, counts = [], None, "OK", "", set()
    cores, builds = [], []
    timed_out = False
    mism = None
    for k in range(repeat):
        res = runner(solver, puzzle, mode, timeout)
        times.append(res.get("elapsed") or 0.0)
        cores.append(res["solve_s"] if res.get("solve_s") is not None else (res.get("elapsed") or 0.0))
        if res.get("build_s") is not None:
            builds.append(res["build_s"])
        v, nt = judge(puzzle, mode, res, timeout)   # every repeat is checked
        counts.add(res.get("count"))
        if v == "MISMATCH" and mism is None:
            mism = (v, nt)
        if v == "TIMEOUT":
            timed_out = True
        elif verdict == "OK" and not timed_out:
            verdict, note = v, nt
        if v in ("TIMEOUT", "ERROR") or res.get("status") in ("TIMEOUT", "ERROR"):
            break
    res = dict(res)
    if timed_out:
        verdict, note = "TIMEOUT", ""
        res["status"] = "TIMEOUT"
        res["count"] = None
        res["elapsed"] = float(timeout) if len(times) > 1 else max(times[-1], 0.0)
        if len(times) > 1:
            note = f"timed out in repeat {len(times)} of {repeat}"
    elif len(counts) > 1 and mism is None:
        mism = ("MISMATCH", f"count differs between repeats: {sorted(map(str, counts))}")
    if mism:
        verdict, note = mism
    if not timed_out and len(times) > 1:
        res["elapsed"] = statistics.median(times)
        if res.get("solve_s") is not None:
            res["solve_s"] = statistics.median(cores)
        if builds:
            res["build_s"] = statistics.median(builds)
    # core_s = native solve time: C++ internal timer (native) or solver-only time (SAT: no Python model build)
    res["core_s"] = float(timeout) if timed_out else statistics.median(cores)
    return res, times, verdict, note


def select(doc, per_n, ns):
    ps = doc["puzzles"]
    if ns:
        ps = [p for p in ps if p["n"] in ns]
    if per_n:
        seen, out = {}, []
        for p in ps:
            if seen.get(p["n"], 0) < per_n:
                seen[p["n"]] = seen.get(p["n"], 0) + 1
                out.append(p)
        ps = out
    return ps


def summarize(rows):
    """Rows -> list of dict per (suite, solver, mode, n)."""
    groups = {}
    for r in rows:
        groups.setdefault((r["suite"], r["solver"], r["mode"], r["n"]), []).append(r)
    out = []
    for (suite, solver, mode, n), g in sorted(groups.items()):
        done = [r["elapsed_s"] for r in g if r["verdict"] in ("OK", "NOREF", "MISMATCH", "INCOMPLETE")]
        out.append({"suite": suite, "solver": solver, "mode": mode, "n": n, "puzzles": len(g),
                    "median_s": statistics.median(done) if done else None,
                    "max_s": max(done) if done else None,
                    "timeouts": sum(r["verdict"] == "TIMEOUT" for r in g),
                    "errors": sum(r["verdict"] == "ERROR" for r in g),
                    "mismatches": sum(r["verdict"] == "MISMATCH" for r in g),
                    "incomplete": sum(r["verdict"] == "INCOMPLETE" for r in g),
                    "noref": sum(r["verdict"] == "NOREF" for r in g)})
    return out


def fmt_table(summ):
    f = lambda x: "-" if x is None else f"{x:.4f}" if x < 10 else f"{x:.1f}"
    lines = [f"{'suite':<6}{'solver':<11}{'mode':<9}{'N':>3}{'#':>5}{'median_s':>10}{'max_s':>9}"
             f"{'timeout':>8}{'error':>6}{'MISMATCH':>9}{'stuck':>6}{'noref':>6}"]
    for s in summ:
        flag = "  <<< !!! MISMATCH" if s["mismatches"] else ""
        lines.append(f"{s['suite']:<6}{s['solver']:<11}{s['mode']:<9}{s['n']:>3}{s['puzzles']:>5}"
                     f"{f(s['median_s']):>10}{f(s['max_s']):>9}{s['timeouts']:>8}{s['errors']:>6}"
                     f"{s['mismatches']:>9}{s['incomplete']:>6}{s['noref']:>6}{flag}")
    return "\n".join(lines)


def print_report(rows):
    print(fmt_table(summarize(rows)))
    bad = [r for r in rows if r["verdict"] == "MISMATCH"]
    if bad:
        print("\n" + "!" * 70 + f"\n!!! {len(bad)} RESULT(S) DISAGREE WITH THE REFERENCE\n" + "!" * 70)
        for r in bad:
            print(f"!!! {r['suite']} {r['id']} n={r['n']} {r['solver']}/{r['mode']}: {r['note']}")
    errs = [r for r in rows if r["verdict"] == "ERROR"]
    for r in errs[:10]:
        print(f"ERROR {r['id']} {r['solver']}/{r['mode']}: {r['note']}")
    return len(bad)


def cmd_run(a):
    rows = []
    t_start = time.time()
    load_start = os.getloadavg()
    plan = []
    for sname in a.suite:
        doc = load_suite(sname)
        apply_satref(doc)
        for p in select(doc, a.per_n, a.n):
            for sv in a.solvers:
                for mode in a.mode:
                    ad = solvers.ADAPTERS.get(sv)
                    if ad is not None and mode not in ad.modes:
                        print(f"skip {sv}/{mode}: mode unsupported", flush=True)
                        continue
                    plan.append((sname, p, sv, mode))
    for sv in a.solvers:
        solvers.get(sv)
    if solvers.SKIPPED:
        print("note: optional solvers unavailable on this python:", ", ".join(solvers.SKIPPED), flush=True)
    for i, (sname, p, sv, mode) in enumerate(plan, 1):
        res, times, verdict, note = run_repeats(sv, p, mode, a.timeout, a.repeat)
        ref = p.get("ref") or {}
        rows.append({"suite": sname, "id": p["id"], "n": p["n"], "solver": sv, "mode": mode,
                     "status": res.get("status"), "elapsed_s": round(res.get("elapsed") or 0.0, 8),
                     "elapsed_all": ";".join(f"{t:.5f}" for t in times),
                     "build_s": res.get("build_s"), "solve_s": res.get("solve_s"),
                     "import_s": res.get("import_s"), "core_s": round(res.get("core_s") or 0.0, 8),
                     "conflicts": res.get("conflicts"), "decisions": res.get("decisions"),
                     "propagations": res.get("propagations"), "branches": res.get("branches"),
                     "nodes": res.get("nodes"), "count": res.get("count"),
                     "ref_count": ref.get("count"), "ref_source": ref.get("source"),
                     "verdict": verdict, "note": note})
        if verdict == "MISMATCH":
            print(f"!!! MISMATCH {sname} {p['id']} {sv}/{mode}: {note}", flush=True)
        if a.verbose or i % 50 == 0:
            print(f"[{i}/{len(plan)}] {time.time() - t_start:.0f}s", flush=True)
    tag = a.tag or time.strftime("%Y%m%d-%H%M%S")
    os.makedirs(a.out, exist_ok=True)
    base = os.path.join(a.out, tag)
    meta = {"load_start": load_start, "load_end": os.getloadavg(), "argv": sys.argv[1:], "timeout_s": a.timeout, "repeat": a.repeat,
            "python": platform.python_version(), "machine": platform.machine(),
            "platform": platform.platform(), "cpu_count": os.cpu_count(),
            "wall_s": round(time.time() - t_start, 1), "grace_s": GRACE}
    with open(base + ".csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    with open(base + ".json", "w") as f:
        json.dump({"meta": meta, "summary": summarize(rows), "rows": rows}, f, indent=1)
    print(f"\nwrote {base}.csv / .json  (wall {meta['wall_s']}s)\n")
    return 1 if print_report(rows) else 0


def cmd_report(a):
    with open(a.file) as f:
        doc = json.load(f)
    return 1 if print_report(doc["rows"]) else 0


def cmd_list(a):
    print("solvers:", ", ".join(solvers.ADAPTERS))
    for k, v in solvers.SKIPPED.items():
        print(f"  (skipped {k}: {v})")
    for fn in sorted(os.listdir(SUITE_DIR)):
        if fn.endswith(".json"):
            d = load_suite(fn[:-5])
            if not isinstance(d.get("puzzles"), list):
                print(f"{fn[:-5]}: (reference table, {len(d.get('puzzles', []))} entries) - {d.get('description', '')}")
                continue
            ref = [p for p in d["puzzles"] if (p.get("ref") or {}).get("count") is not None]
            print(f"{d['suite']}: {len(d['puzzles'])} puzzles, ref known {len(ref)} - {d['description']}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bench")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--solvers", nargs="+", required=True)
    r.add_argument("--suite", nargs="+", required=True)
    r.add_argument("--mode", nargs="+", default=["classify"], choices=solvers.MODES)
    r.add_argument("--timeout", type=float, default=10.0)
    r.add_argument("--per-n", type=int, default=0, help="at most K puzzles per N")
    r.add_argument("--n", type=int, nargs="+", help="only these N")
    r.add_argument("--repeat", type=int, default=1, help="median of K runs (not for timeouts)")
    r.add_argument("--out", default=RESULT_DIR)
    r.add_argument("--tag")
    r.add_argument("--verbose", action="store_true")
    r.set_defaults(fn=cmd_run)
    p = sub.add_parser("report")
    p.add_argument("file")
    p.set_defaults(fn=cmd_report)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    a = ap.parse_args(argv)
    return a.fn(a)
