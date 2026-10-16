#!/bin/bash
# Resume of run_final_native.sh after S6 was interrupted (2026-10-15 23:27). Appends to the same load log.
PY=.venv/bin/python
OUT=bench/results
SOLVERS="native_bitmask native_hybrid native_dlx sat_cadical153_seq cpsat_w1"
LOG=$OUT/final_native_load.txt
stamp() { echo "$1 $(date +%H:%M:%S) $(cut -d' ' -f1-3 /proc/loadavg)" | tee -a $LOG; }
stamp resume
run() {  # suite repeat modes...
  local s=$1 r=$2; shift 2
  stamp "begin $s repeat=$r"
  $PY -B -m bench run --solvers $SOLVERS --suite $s --mode "$@" --timeout 10 --repeat $r \
      --out $OUT --tag final_native_$s > $OUT/final_native_$s.log 2>&1
  stamp "end $s rc=$?"
}
run S6 3 classify
run S1 1 classify count
stamp done
