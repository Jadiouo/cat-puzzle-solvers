"""Replace rows of a finished run with rows from a (partial) re-run, keyed by (suite, id, solver, mode).
  python3 -B -m bench.merge_results results/final_S3 results/rerun_S3_count_n15plus
Rewrites <base>.csv/.json (summary recomputed) and records the re-run in meta['reruns']."""
import csv
import json
import sys

from . import runner


def merge(base, rerun):
    d = json.load(open(base + ".json"))
    r = json.load(open(rerun + ".json"))
    key = lambda x: (x["suite"], x["id"], x["solver"], x["mode"])
    new = {key(x): x for x in r["rows"]}
    old_keys = {key(x) for x in d["rows"]}
    assert set(new) <= old_keys, "rerun contains rows that are not in the base run"
    changed = []
    out = []
    for x in d["rows"]:
        y = new.get(key(x))
        if y is not None and (y["verdict"], y["status"]) != (x["verdict"], x["status"]):
            changed.append({"key": list(key(x)), "old": [x["status"], x["verdict"], x["elapsed_s"]],
                            "new": [y["status"], y["verdict"], y["elapsed_s"]]})
        out.append(y if y is not None else x)
    d["rows"] = out
    d["summary"] = runner.summarize(out)
    d["meta"].setdefault("reruns", []).append({"file": rerun.split("/")[-1], "rows_replaced": len(new),
                                               "argv": r["meta"]["argv"], "load_start": r["meta"]["load_start"],
                                               "load_end": r["meta"]["load_end"], "wall_s": r["meta"]["wall_s"],
                                               "status_or_verdict_changed": changed})
    json.dump(d, open(base + ".json", "w"), indent=1)
    with open(base + ".csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=runner.FIELDS)
        w.writeheader()
        w.writerows(out)
    return len(new), changed


if __name__ == "__main__":
    n, ch = merge(sys.argv[1], sys.argv[2])
    print(n, "rows replaced;", len(ch), "with a different status/verdict")
    for c in ch:
        print(c)
