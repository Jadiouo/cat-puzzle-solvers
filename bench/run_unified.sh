#!/bin/bash
# Unified comparison (same round, same load): unique-solution and adversarial suites, main methods.
PY=.venv/bin/python
OUT=bench/results
LOG=$OUT/unified_load.txt
stamp() { echo "$1 $(date +%H:%M:%S) $(cut -d' ' -f1-3 /proc/loadavg)" | tee -a $LOG; }
SOLVERS="native_bitmask native_hybrid native_dlx native_match native_match_rr \
 sat_cadical153_seq sat_cadical195_seq sat_glucose4_seq cpsat_w1"
: > $LOG
stamp start
for s in S5 S5b S6 S6x S6m; do
  stamp "begin $s"
  $PY -B -m bench run --solvers $SOLVERS --suite $s --mode classify --timeout 10 --repeat 3 \
      --out $OUT --tag unified_$s > $OUT/unified_$s.log 2>&1
  stamp "end $s rc=$?"
done
stamp done
