#!/bin/bash
# Extra experiment: the Hall-matching DFS variants on every suite (same settings as run_final_native.sh).
PY=.venv/bin/python
OUT=bench/results
LOG=$OUT/extra_load.txt
stamp() { echo "$1 $(date +%H:%M:%S) $(cut -d' ' -f1-3 /proc/loadavg)" | tee -a $LOG; }
run() {  # suite repeat solvers modes...
  local s=$1 r=$2 sv=$3; shift 3
  stamp "begin match $s"
  $PY -B -m bench run --solvers $sv --suite $s --mode "$@" --timeout 10 --repeat $r \
      --out $OUT --tag extra_match_$s > $OUT/extra_match_$s.log 2>&1
  stamp "end match $s rc=$?"
}
for s in S2 S3 S4 S5 S5b S6; do run $s 3 "native_match native_match_rr" classify count; done
run S1 1 "native_match native_match_rr" classify count
stamp "done match"
