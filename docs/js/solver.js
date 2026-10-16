/* Cat-board solvers: a line-by-line port of native/cat_native.cpp
 *   algo "bitmask": bitmask DFS, MRV over the 3N units (rows, cols, regions) + forward checking
 *   algo "match"  : the same branching, plus at every node a Hall check: unplaced regions must have
 *                   a perfect matching into columns and into rows that still hold a live cell.
 * Branch order and tie-breaks are identical to C++ (first unit with the smallest live count wins;
 * cells tried in increasing index), so node counts are comparable one-to-one.
 * Works as a plain <script>, in a Web Worker (importScripts) and under Node (require).
 */
(function (root) {
  'use strict';

  var PLACE = 0, REMOVE = 1, PRUNE = 2, DEAD = 3, FOUND = 4;   // trace event types; event = type | (cell << 3)
  var CAP = { cap: true };

  function popcnt(v) {
    v = v - ((v >>> 1) & 0x55555555);
    v = (v & 0x33333333) + ((v >>> 2) & 0x33333333);
    return (((v + (v >>> 4)) & 0x0f0f0f0f) * 0x01010101) >>> 24;
  }

  function build(regions, n) {
    var ids = [], seen = {}, r, c, i;
    for (r = 0; r < n; r++) for (c = 0; c < n; c++) { var v = regions[r][c]; if (!seen[v]) { seen[v] = 1; ids.push(v); } }
    ids.sort(function (a, b) { return a - b; });
    if (ids.length !== n) return null;                       // colour count != N : unsatisfiable
    var idx = {}; ids.forEach(function (v, k) { idx[v] = k; });
    var NN = n * n, W = (NN + 31) >> 5, NU = 3 * n;
    var UN = [], k;
    for (k = 0; k < NU; k++) UN.push(new Uint32Array(W));
    var regOf = new Int32Array(NN), KILL = [];
    for (r = 0; r < n; r++) for (c = 0; c < n; c++) {
      var x = r * n + c, g = idx[regions[r][c]];
      regOf[x] = g;
      UN[r][x >> 5] |= 1 << (x & 31);
      UN[n + c][x >> 5] |= 1 << (x & 31);
      UN[2 * n + g][x >> 5] |= 1 << (x & 31);
    }
    var all = new Uint32Array(W);
    for (i = 0; i < NN; i++) all[i >> 5] |= 1 << (i & 31);
    for (r = 0; r < n; r++) for (c = 0; c < n; c++) {
      var xx = r * n + c, kb = new Uint32Array(W), g2 = regOf[xx];
      for (i = 0; i < W; i++) kb[i] = UN[r][i] | UN[n + c][i] | UN[2 * n + g2][i];
      for (var a = Math.max(0, r - 1); a < Math.min(n, r + 2); a++)
        for (var b = Math.max(0, c - 1); b < Math.min(n, c + 2); b++) { var y = a * n + b; kb[y >> 5] |= 1 << (y & 31); }
      KILL.push(kb);
    }
    var regCells = [];
    for (k = 0; k < n; k++) regCells.push([]);
    for (i = 0; i < NN; i++) regCells[regOf[i]].push(i);
    return { n: n, NN: NN, W: W, NU: NU, UN: UN, KILL: KILL, regOf: regOf, all: all, regCells: regCells };
  }

  /* opts: algo, limit (0 = all, 1, 2), maxNodes, onProgress(nodes, ms), progressMs, trace {events:[], cap:int}
   * returns {status: SOLVED|UNSAT|CAPPED, count, nodes, ms, solutions:[[col per row]], traceTruncated} */
  function solve(regions, n, opts) {
    opts = opts || {};
    var algo = opts.algo || 'bitmask', match = algo === 'match';
    var limit = opts.limit === undefined ? 2 : opts.limit;
    var maxNodes = opts.maxNodes || Infinity;
    var onProgress = opts.onProgress, progressMs = opts.progressMs || 100;
    var tr = opts.trace ? opts.trace.events : null, trCap = opts.trace ? opts.trace.cap : 0, trTrunc = false;
    var t0 = now();
    var T = build(regions, n);
    if (!T) return { status: 'UNSAT', count: 0, nodes: 0, ms: now() - t0, solutions: [] };
    var W = T.W, NU = T.NU, UN = T.UN, KILL = T.KILL, regOf = T.regOf, regCells = T.regCells;
    var A = new Uint32Array((n + 2) * W), BM = new Uint32Array((n + 2) * W), TMP = new Uint32Array(W);
    var done = new Uint8Array(NU), doneCount = 0, cats = new Int32Array(n + 1);
    var nodes = 0, count = 0, sols = [], lastTick = t0;
    var adjR = new Int32Array(n), adjC = new Int32Array(n), matchR = new Int32Array(n);
    A.set(T.all, 0);

    function ev(type, x) {
      if (!tr) return;
      if (tr.length >= trCap) { trTrunc = true; return; }
      tr.push(type | (x << 3));
    }

    function kuhn(a, adj, seen) {          // seen is an object {m}
      var cand = adj[a] & ~seen.m;
      while (cand) {
        var low = cand & -cand, b = 31 - Math.clz32(low);
        cand ^= low;
        seen.m |= low;
        if (matchR[b] < 0 || kuhn(matchR[b], adj, seen)) { matchR[b] = a; return true; }
      }
      return false;
    }
    var seenObj = { m: 0 };
    function perfect(k, adj) {
      for (var i = 0; i < n; i++) matchR[i] = -1;
      for (var a = 0; a < k; a++) {
        if (!adj[a]) return false;
        seenObj.m = 0;
        if (!kuhn(a, adj, seenObj)) return false;
      }
      return true;
    }
    function hall(base) {
      var k = 0;
      for (var g = 0; g < n; g++) {
        if (done[2 * n + g]) continue;
        var rm = 0, cm = 0, cl = regCells[g];
        for (var j = 0; j < cl.length; j++) {
          var x = cl[j];
          if ((A[base + (x >> 5)] >>> (x & 31)) & 1) { rm |= 1 << ((x / n) | 0); cm |= 1 << (x % n); }
        }
        adjR[k] = rm; adjC[k] = cm; k++;
      }
      return perfect(k, adjR) && perfect(k, adjC);
    }

    function record(d) {
      count++;
      var s = new Array(n);
      for (var i = 0; i < d; i++) s[(cats[i] / n) | 0] = cats[i] % n;
      sols.push(s);
    }

    function rec(d) {
      nodes++;
      if (nodes > maxNodes) { nodes = maxNodes; throw CAP; }
      if ((nodes & 4095) === 0) {
        var t = now();
        if (onProgress && t - lastTick >= progressMs) { lastTick = t; onProgress(nodes, t - t0); }
      }
      if (doneCount === NU) { record(d); ev(FOUND, 0); return limit !== 0 && count >= limit; }
      var base = d * W, bbase = base, bc = 1 << 30, u, i, c;
      for (u = 0; u < NU; u++) {
        if (done[u]) continue;
        var un = UN[u], cnt = 0;
        for (i = 0; i < W; i++) { var m = A[base + i] & un[i]; TMP[i] = m; if (m) cnt += popcnt(m); }
        if (cnt === 0) { ev(DEAD, 0); return false; }
        if (cnt < bc) { bc = cnt; for (i = 0; i < W; i++) BM[bbase + i] = TMP[i]; }
      }
      if (match && !hall(base)) { ev(PRUNE, 0); return false; }
      var nb = base + W;
      for (i = 0; i < W; i++) {
        var word = BM[bbase + i];
        while (word) {
          var low = word & -word, x = (i << 5) + 31 - Math.clz32(low);
          word ^= low;
          BM[bbase + i] = word;           // keep remaining candidates (C++ resets the bit as it goes)
          var kb = KILL[x];
          for (c = 0; c < W; c++) A[nb + c] = A[base + c] & ~kb[c];
          var r = (x / n) | 0, cc = x % n, g = regOf[x];
          done[r] = done[n + cc] = done[2 * n + g] = 1; doneCount += 3; cats[d] = x;
          ev(PLACE, x);
          if (rec(d + 1)) return true;
          ev(REMOVE, x);
          done[r] = done[n + cc] = done[2 * n + g] = 0; doneCount -= 3;
          word = BM[bbase + i];
        }
      }
      return false;
    }

    var capped = false;
    try { rec(0); } catch (e) { if (e === CAP) capped = true; else throw e; }
    var enough = limit !== 0 && count >= limit;
    var status = capped && !enough ? 'CAPPED' : (count ? 'SOLVED' : 'UNSAT');
    if (onProgress) onProgress(nodes, now() - t0);
    return { status: status, count: count, nodes: nodes, ms: now() - t0, solutions: sols, traceTruncated: trTrunc };
  }

  function now() { return (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now(); }

  var api = { solve: solve, PLACE: PLACE, REMOVE: REMOVE, PRUNE: PRUNE, DEAD: DEAD, FOUND: FOUND };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.CatSolver = api;
})(typeof self !== 'undefined' ? self : this);
