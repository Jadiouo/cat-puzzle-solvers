#!/usr/bin/env python3
"""Regenerates docs/data/{pool,s5,race}.json from the research data. Run from anywhere:  python3 docs/data/build_data.py

Only reads: levelgen/pool/pool.json, bench/suites/{S5,S3,S6m}.json, bench/results/{extra_S3n25_t60,unified_S6m}.csv
(only self-generated puzzles are used).
Race selection criteria are described in docs/data/README.md.
"""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.dirname(os.path.abspath(__file__))


def rd(*p):
    with open(os.path.join(ROOT, *p)) as f:
        return json.load(f)


def csvrows(name, solver):
    with open(os.path.join(ROOT, "bench", "results", name)) as f:
        return {r["id"]: r for r in csv.DictReader(f) if r["solver"] == solver}


def dump(name, obj):
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(obj, f, separators=(",", ":"))


# ---- Play: pool (N=6-9, graded) ----
pool = rd("levelgen", "pool", "pool.json")["puzzles"]
dump("pool.json", [{"id": p["id"], "n": p["size"], "level": p["level"], "score": p["score"],
                    "regions": p["regions"], "solution": p["solution"]} for p in pool])

# ---- Play: a few big boards from S5 (unique solution, N=11-16): the first puzzle of each N ----
s5 = rd("bench", "suites", "S5.json")["puzzles"]
seen, big = set(), []
for p in s5:
    if p["n"] not in seen:
        seen.add(p["n"])
        big.append({"id": p["id"], "n": p["n"], "level": "big", "regions": p["regions"], "solution": p["planted"]})
dump("s5.json", big)

# ---- Race: curated ----
s3 = {p["id"]: p for p in rd("bench", "suites", "S3.json")["puzzles"]}
s6m = {p["id"]: p for p in rd("bench", "suites", "S6m.json")["puzzles"]}
pl = {p["id"]: p for p in pool}
e_bit, e_mat = csvrows("extra_S3n25_t60.csv", "native_bitmask"), csvrows("extra_S3n25_t60.csv", "native_match")
u_bit, u_mat = csvrows("unified_S6m.csv", "native_bitmask"), csvrows("unified_S6m.csv", "native_match")


def ref(b, m):
    return {"bitmask": {"status": b["status"], "nodes": int(b["nodes"]), "ms": round(float(b["elapsed_s"]) * 1000, 3)},
            "match": {"status": m["status"], "nodes": int(m["nodes"]), "ms": round(float(m["elapsed_s"]) * 1000, 3)}}


race = []
for i in ("17", "11", "01", "09", "06"):      # group "hall": S3 N=25 random regions
    pid = "S3-n25-" + i
    race.append({"id": pid, "group": "hall", "n": 25, "regions": s3[pid]["regions"], "ref": ref(e_bit[pid], e_mat[pid])})
for pid in ("S6m-mt-n18-4", "S6m-mt-n18-1", "S6m-mt-n16-0", "S6m-mt-n14-1"):   # group "hard": S6m
    race.append({"id": pid, "group": "hard", "n": s6m[pid]["n"], "regions": s6m[pid]["regions"], "ref": ref(u_bit[pid], u_mat[pid])})
for pid in ("S3-n10-05", "S3-n8-05"):            # group "anim": small boards, unsatisfiable (pure Hall pruning)
    race.append({"id": pid, "group": "anim", "n": s3[pid]["n"], "regions": s3[pid]["regions"], "ref": None})
for pid in ("L9-normal-007", "L9-normal-013"):   # group "anim": small boards from the playable pool
    race.append({"id": pid, "group": "anim", "n": pl[pid]["size"], "regions": pl[pid]["regions"], "ref": None})
dump("race.json", race)
print("pool", len(pool), "s5", len(big), "race", len(race))
