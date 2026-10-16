#!/bin/bash
# Final native-level comparison. Run from the repo root:  bench/run_final_native.sh
# Single process, one solve at a time. Logs load average at start/end and after every suite.
# S1 uses --repeat 1 (estimated total > 2 h with repeat 3); the other suites use --repeat 3.
PY=.venv/bin/python
OUT=bench/results
SOLVERS="native_bitmask native_hybrid native_dlx sat_cadical153_seq cpsat_w1"
LOG=$OUT/final_native_load.txt
stamp() { echo "$1 $(date +%H:%M:%S) $(cut -d' ' -f1-3 /proc/loadavg)" | tee -a $LOG; }
: > $LOG
stamp start
run() {  # suite repeat modes...
  local s=$1 r=$2; shift 2
  stamp "begin $s repeat=$r"
  $PY -B -m bench run --solvers $SOLVERS --suite $s --mode "$@" --timeout 10 --repeat $r \
      --out $OUT --tag final_native_$s > $OUT/final_native_$s.log 2>&1
  stamp "end $s rc=$?"
}
run S2 3 classify count
run S3 3 classify count
run S4 3 classify count
run S5 3 classify
run S5b 3 classify
run S6 3 classify
run S1 1 classify count
stamp done
