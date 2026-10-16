#!/bin/bash
# Extra experiment: S3 N=25 (20 puzzles), classify, timeout 60s, repeat 1, all base + variant solvers.
PY=.venv/bin/python
OUT=bench/results
LOG=$OUT/extra_load.txt
stamp() { echo "$1 $(date +%H:%M:%S) $(cut -d' ' -f1-3 /proc/loadavg)" | tee -a $LOG; }
SOLVERS="native_bitmask native_hybrid native_dlx native_match native_rr native_match_rr \
 sat_cadical153_seq sat_cadical153_pairwise sat_cadical153_ladder sat_cadical153_totalizer sat_cadical153_bitwise \
 sat_cadical195_seq sat_glucose4_seq sat_minisat22_seq cpsat_w1"
stamp "begin S3n25 t60"
$PY -B -m bench run --solvers $SOLVERS --suite S3 --n 25 --mode classify --timeout 60 --repeat 1 \
    --out $OUT --tag extra_S3n25_t60 > $OUT/extra_S3n25_t60.log 2>&1
stamp "end S3n25 rc=$?"
