import argparse
import json
import os
import sys

from .pool import build_pool, summarize


def main(argv=None):
    ap = argparse.ArgumentParser(prog="levelgen")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pool", help="build a verified puzzle pool")
    p.add_argument("--sizes", type=int, nargs="+", default=[6, 7, 8, 9])
    p.add_argument("--count", type=int, default=60, help="normal puzzles per size")
    p.add_argument("--probe-count", type=int, default=15, help="lookahead-required puzzles per size")
    p.add_argument("--probe-target", default="T5a", choices=["T5a", "T5b"])
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--max-seconds", type=float, default=1e9, help="time cap per size and kind")
    p.add_argument("--out", default="levelgen/pool/pool.json")
    a = ap.parse_args(argv)
    log = lambda s: print(s, file=sys.stderr, flush=True)
    pool = build_pool(a.sizes, a.count, a.probe_count, a.probe_target, a.seed, a.max_seconds, log)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(pool, f, separators=(",", ":"))
    for r in summarize(pool):
        print(r)
    return 0


raise SystemExit(main())
