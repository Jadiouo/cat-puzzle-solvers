"""Batch pool builder with independent uniqueness verification (cat_solver)."""
import json
import statistics as stt
import sys
import time
from collections import Counter

from cat_solver import SolveOptions, parse_puzzle, solve

from .generate import generate
from .grade import LEVELS, WEIGHTS, grade
from .ugliness import ugliness_parts


def verify_unique(puzzle):
    """Independent check via cat_solver (different search code). Raises on failure."""
    n = puzzle["size"]
    payload = {"schema_version": "1.0", "size": n,
               "regions": [[f"R{g}" for g in row] for row in puzzle["regions"]]}
    res = solve(parse_puzzle(payload), SolveOptions(mode="classify", timeout_ms=60000))
    if not (res.status == "SOLVED" and res.uniqueness == "UNIQUE" and res.search_complete):
        raise ValueError(f"not unique: {res.status}/{res.uniqueness}")
    if res.solutions != [puzzle["solution"]]:
        raise ValueError("solution mismatch with cat_solver")


def finalize(puzzle, pid, kind):
    g = grade(puzzle["regions"], solution=puzzle["solution"])   # asserts no answer cell removed
    if not g["solved"] or g["solution"] != puzzle["solution"]:
        raise ValueError("grader did not reach the solution")
    verify_unique(puzzle)
    ug, parts = ugliness_parts(puzzle["regions"])
    return {
        "id": pid, "kind": kind, "size": puzzle["size"],
        "regions": puzzle["regions"], "solution": puzzle["solution"],
        "counts": g["counts"], "T5b_depth": g["T5b_depth"],
        "level": g["level"], "score": g["score"], "steps": g["steps"],
        "ugliness": round(ug, 4), "ugliness_regions": [round(x, 4) for x in parts],
        "region_min": puzzle["region_min"], "region_max": puzzle["region_max"],
        "seed": puzzle["seed"], "target": puzzle["target"],
    }


def build_kind(size, count, base_seed, target, kind, max_seconds, log):
    items, seen = [], set()
    attempts = fails = 0
    t0 = time.time()
    while len(items) < count and time.time() - t0 < max_seconds:
        seed = base_seed + attempts
        attempts += 1
        p = generate(size, seed, target)
        if p is None:
            fails += 1
            continue
        key = json.dumps(p["regions"])
        if key in seen:
            continue
        seen.add(key)
        items.append(finalize(p, f"L{size}-{kind}-{len(items):03d}", kind))
        log(f"  N={size} {kind} {len(items)}/{count} level={items[-1]['level']} "
            f"score={items[-1]['score']} t={time.time() - t0:.0f}s")
    return items, {"size": size, "kind": kind, "target": target, "wanted": count,
                   "got": len(items), "attempts": attempts, "gen_failures": fails,
                   "success_rate": round(len(items) / attempts, 3) if attempts else 0,
                   "seconds": round(time.time() - t0, 1),
                   "sec_per_puzzle": round((time.time() - t0) / max(1, len(items)), 2)}


def build_pool(sizes, count, probe_count, probe_target, seed, max_seconds, log=lambda s: None):
    puzzles, stats = [], []
    for n in sizes:
        for kind, cnt, tg, off in (("normal", count, None, 0),
                                   ("probe", probe_count, probe_target, 500_000)):
            if cnt <= 0:
                continue
            base = seed * 1_000_003 + n * 10_000_000 + off
            it, st = build_kind(n, cnt, base, tg, kind, max_seconds, log)
            puzzles += it
            stats.append(st)
            log(json.dumps(st))
    return {"meta": {"seed": seed, "sizes": list(sizes), "weights": WEIGHTS,
                     "levels": list(LEVELS), "solution_format": "column index per row, 0-based",
                     "regions_format": "N x N region index grid"},
            "stats": stats, "puzzles": puzzles}


def summarize(pool):
    rows = []
    for n in pool["meta"]["sizes"]:
        P = [p for p in pool["puzzles"] if p["size"] == n]
        if not P:
            continue
        sc = [p["score"] for p in P]
        lv = Counter(p["level"] for p in P)
        rows.append((n, len(P), dict(lv), stt.median(sc), min(sc), max(sc),
                     stt.median(p["ugliness"] for p in P)))
    return rows
