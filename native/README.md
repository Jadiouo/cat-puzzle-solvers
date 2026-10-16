# native/ — C++ ports of the Python bitmask, hybrid and DLX solvers

Goal: compare algorithms, not languages. The three ports walk exactly the same search tree as the
Python originals (`bench/solver_bitmask.py`, `solver_hybrid.py`, `solver_dlx.py`): same branching
order (lowest bit first), same MRV tie-breaking (first strictly smaller), same propagation
(hybrid = S + T3 + T3b, run to a fixed point, same in-loop update order), same DLX link layout.
Per-puzzle equality of node counts is the proof of faithfulness (`native/compare.py`,
`tests/test_native.py`).

## Build
    make -C native            # build/cat_native      (-O2, headline numbers)
    make -C native native     # build/cat_native_o3   (-O3 -march=native, comparison only)
`native/build/` is git-excluded (`.git/info/exclude`). Needs only g++ (C++17).

## Use
    printf 'p1 6 0 0 ... \n' | native/build/cat_native -s hybrid -m classify -t 10 [-r 3]
Input line: `id n v...` (n*n region ids, row-major). Output: one JSON line per puzzle with status,
count, complete, nodes, forced/elims (hybrid), elapsed (median of -r runs, internal steady_clock,
build tables + search, no parsing), elapsed_all, solutions (first/classify only; count mode never
stores solutions). Timeout is checked inside the search (bitmask/DLX every 256 nodes, hybrid every 64,
as in Python). Single thread.

Python side: `bench/solver_native.py` (adapters `native_bitmask`, `native_hybrid`, `native_dlx`,
dict `NATIVE_ADAPTERS`; not yet registered in bench/solvers.py). It uses subprocess rather than
ctypes: process isolation and hard kill like the runner, no ABI glue; ~1 ms start-up is outside the
internal timer.

Boards are `ceil(n*n/64)`-word bitsets (template width, n<=25 -> 10 words), unit masks are 128-bit,
so N up to 25 is supported (a 32-bit mask cannot hold a 625-cell board).

## Benchmark
    python3 -B native/compare.py --suites S1 S2 S3 S4 --timeout 10 --repeat 3 --tag o2
    python3 -B native/compare.py --exe native/build/cat_native_o3 --tag o3 --skip-python
Writes `bench/results/native_<tag>.csv`.
