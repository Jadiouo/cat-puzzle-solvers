#!/usr/bin/env node
// Verifies docs/js/solver.js against the C++ solver (native/cat_native.cpp).
// Input : JSON file produced by tests/test_demo_js.py: [{suite,id,n,regions,exp:{bitmask:{status,count,nodes},match:{...}}}]
// For each puzzle and each algo (bitmask, match) in classify mode (stop at 2 solutions) it checks
//   solution-count class (0 / 1 / >=2)  and  the exact node count.
// Items where C++ timed out are skipped (reported), never counted as agreement.
// Exit code 0 iff no mismatch. Prints a summary line and the first mismatches.
'use strict';
const fs = require('fs');
const path = require('path');
const { solve } = require(path.join(__dirname, '..', '..', 'docs', 'js', 'solver.js'));

const items = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const stats = {};
let bad = 0, skipped = 0, same = 0, total = 0;
const diffs = [];
const t0 = Date.now();
for (const it of items) {
  for (const algo of ['bitmask', 'match']) {
    const e = it.exp[algo];
    const key = it.suite + '/' + algo;
    const s = stats[key] || (stats[key] = { total: 0, same: 0, skipped: 0, classBad: 0, nodeBad: 0 });
    if (e.status === 'TIMEOUT' || e.status === 'ERROR') { s.skipped++; skipped++; continue; }
    s.total++; total++;
    const r = solve(it.regions, it.n, { algo, limit: 2, maxNodes: e.nodes + 1000 });
    const cls = Math.min(r.count, 2);
    const okClass = r.status !== 'CAPPED' && cls === e.count;
    const okNodes = r.nodes === e.nodes;
    if (!okClass) s.classBad++;
    if (!okNodes) s.nodeBad++;
    if (okClass && okNodes) { s.same++; same++; }
    else { bad++; if (diffs.length < 15) diffs.push(`${it.id} ${algo}: js class=${cls} nodes=${r.nodes} (${r.status}) vs cpp class=${e.count} nodes=${e.nodes}`); }
  }
}
for (const k of Object.keys(stats).sort()) {
  const s = stats[k];
  console.log(`${k.padEnd(14)} total=${s.total} identical=${s.same} classMismatch=${s.classBad} nodeMismatch=${s.nodeBad} skipped(cpp timeout)=${s.skipped}`);
}
diffs.forEach(d => console.log('DIFF ' + d));
console.log(`SUMMARY identical=${same} total=${total} skipped=${skipped} mismatches=${bad} seconds=${((Date.now() - t0) / 1000).toFixed(1)}`);
process.exit(bad ? 1 : 0);
