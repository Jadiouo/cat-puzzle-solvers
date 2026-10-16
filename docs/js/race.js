/* Race tab: run bitmask DFS and Hall-match DFS on the same puzzle in two Web Workers, live counters,
 * optional step-by-step replay (N <= 10) built from the solver's trace events. */
(function () {
  var C = window.Cat, t = C.t;
  var $ = function (id) { return document.getElementById(id); };
  var puzzles = [], boards = {}, runners = { A: new C.Runner(), B: new C.Runner() };
  var running = false, anim = null, runId = 0;
  var TRACE_CAP = 60000;
  var ALGO = { A: 'bitmask', B: 'match' };

  function fmtN(v) { return v.toLocaleString('en-US'); }
  function fmtMs(ms) { return ms < 1 ? ms.toFixed(3) + ' ms' : ms < 1000 ? ms.toFixed(ms < 10 ? 2 : 0) + ' ms' : (ms / 1000).toFixed(2) + ' s'; }
  function fmtRatio(r) { return (r >= 100 ? Math.round(r).toLocaleString('en-US') : r.toFixed(1)) + '×'; }
  function capLabel(n) { return fmtN(n); }

  function selected() {
    var v = $('selRace').value;
    if (v === 'play') { var p = C.play.current(); return p ? { id: p.id, n: p.n, regions: p.regions, ref: null } : puzzles[0]; }
    return puzzles.filter(function (q) { return q.id === v; })[0];
  }

  function buildSelect() {
    var sel = $('selRace'), keep = sel.value;
    sel.innerHTML = '';
    var groups = [['hall', 'grpHall'], ['hard', 'grpHard'], ['anim', 'grpAnim']];
    groups.forEach(function (g) {
      var og = document.createElement('optgroup'); og.label = t(g[1]);
      puzzles.filter(function (q) { return q.group === g[0]; }).forEach(function (q) { og.appendChild(new Option(t('puzName', { id: q.id, n: q.n }), q.id)); });
      sel.appendChild(og);
    });
    var og = document.createElement('optgroup'); og.label = t('grpPlay');
    var cur = C.play.current();
    og.appendChild(new Option(t('optPlay', { n: cur ? cur.n : '?' }), 'play'));
    sel.appendChild(og);
    sel.value = keep && sel.querySelector('option[value="' + keep + '"]') ? keep : puzzles[0].id;
  }

  function resetCard(k) {
    $('nodes' + k).textContent = '–'; $('time' + k).textContent = '–'; $('bar' + k).style.width = '0';
    $('bar' + k).className = ''; setChip(k, '', '');
  }
  function setChip(k, text, cls) { var c = $('chip' + k); c.textContent = text; c.className = 'chip ' + (cls || ''); }

  function showPuzzle() {
    stopAnim();
    var q = selected();
    ['A', 'B'].forEach(function (k) { boards[k] = C.board.create($('board' + k), q.regions, q.n); resetCard(k); });
    shown = {}; $('raceSummary').textContent = ''; $('animBar').hidden = true;
    var canAnim = q.n <= 10;
    var mode = $('selMode');
    mode.querySelector('option[value="anim"]').disabled = !canAnim;
    mode.value = canAnim && (q.group === 'anim' || $('selRace').value === 'play') ? 'anim' : 'live';
    $('raceNote').textContent = t('noteCap');
    showRef(q);
  }

  function showRef(q) {
    var el = $('raceRef');
    if (!q.ref) { el.textContent = ''; return; }
    function line(name, r) {
      var body = r.status === 'TIMEOUT' ? t('refTimeout', { nodes: fmtN(r.nodes) }) :
        t('refLine', { status: r.status === 'UNSAT' ? t('stNone') : t('refSolved'), nodes: fmtN(r.nodes), ms: r.ms < 1 ? r.ms.toFixed(3) : r.ms.toFixed(1) });
      return name + ': ' + body;
    }
    el.textContent = t('refTitle') + line(t('algoBitmask'), q.ref.bitmask) + ' | ' + line(t('algoMatch'), q.ref.match);
  }

  var shown = {};   // last finished result per card (+ summary), re-rendered on language change
  function statusChip(k, r, cap) {
    shown[k] = [r, cap];
    if (r.status === 'CAPPED') setChip(k, t('stCap', { cap: capLabel(cap) }), 'bad');
    else if (r.status === 'UNSAT') setChip(k, t('stNone'), 'ok');
    else setChip(k, r.count >= 2 ? t('stMulti') : t('stUnique'), 'ok');
  }

  function finish(k, r, cap) {
    $('nodes' + k).textContent = (r.status === 'CAPPED' ? '> ' : '') + fmtN(r.nodes);
    $('time' + k).textContent = fmtMs(r.ms);
    $('bar' + k).style.width = r.status === 'CAPPED' ? '100%' : Math.min(100, (r.nodes / cap) * 100) + '%';
    $('bar' + k).className = r.status === 'CAPPED' ? 'capped' : 'ok';
    statusChip(k, r, cap);
    var b = boards[k], n = b.n;
    if (r.solutions[0]) r.solutions[0].forEach(function (c, row) { C.board.setMark(b, row * n + c, 2); });
  }

  function summarize(a, b, cap) {
    shown.sum = [a, b, cap];
    var el = $('raceSummary'), cls = 'summary';
    if (a.status === 'CAPPED' && b.status === 'CAPPED') el.textContent = t('sumBothCapped', { cap: capLabel(cap) });
    else if (a.status === 'CAPPED') { el.textContent = t('sumCapped', { cap: capLabel(cap), b: fmtN(b.nodes), tb: fmtMs(b.ms), ratio: fmtRatio(cap / Math.max(1, b.nodes)) }); cls += ' win'; }
    else if (b.status === 'CAPPED') el.textContent = t('sumMatchOnlyCapped', { cap: capLabel(cap), a: fmtN(a.nodes) });
    else if (a.nodes === b.nodes) el.textContent = t('sumSame', { a: fmtN(a.nodes) });
    else { el.textContent = t('sumBoth', { a: fmtN(a.nodes), b: fmtN(b.nodes), ratio: fmtRatio(a.nodes / Math.max(1, b.nodes)), ta: fmtMs(a.ms), tb: fmtMs(b.ms) }); cls += a.nodes > b.nodes ? ' win' : ''; }
    el.className = cls;
  }

  function setRunning(on) {
    running = on; $('btnRun').disabled = on; $('btnCancel').disabled = !on;
    ['selRace', 'selCap', 'selMode'].forEach(function (id) { $(id).disabled = on; });
  }

  function run() {
    if (running) return;
    var q = selected(), cap = +$('selCap').value, wantAnim = $('selMode').value === 'anim';
    if (wantAnim && q.n > 10) { wantAnim = false; $('raceNote').textContent = t('noteNoAnim'); }
    showPuzzle();
    var id = ++runId, res = {}, traces = {};
    setRunning(true);
    ['A', 'B'].forEach(function (k) { setChip(k, t('stRunning'), 'run'); });
    var jobs = ['A', 'B'].map(function (k) {
      return runners[k].run({ regions: q.regions, n: q.n, algo: ALGO[k], limit: 2, maxNodes: cap, traceCap: wantAnim ? TRACE_CAP : 0 }, function (nodes, ms) {
        if (id !== runId) return;
        $('nodes' + k).textContent = fmtN(nodes); $('time' + k).textContent = fmtMs(ms);
        $('bar' + k).style.width = Math.min(100, nodes / cap * 100) + '%';
      }).then(function (o) {
        if (id !== runId) return;
        if (!o) { setChip(k, t('stCancelled'), ''); return; }
        res[k] = o.result; traces[k] = o.trace; finish(k, o.result, cap);
      });
    });
    Promise.all(jobs).then(function () {
      if (id !== runId) return;
      setRunning(false);
      if (res.A && res.B) {
        summarize(res.A, res.B, cap);
        if (wantAnim) startAnim(q, res, traces);
      }
    }).catch(function (e) { setRunning(false); $('raceSummary').textContent = 'Error: ' + e.message; });
  }

  function cancel() {
    runId++; runners.A.cancel(); runners.B.cancel(); setRunning(false);
    ['A', 'B'].forEach(function (k) { setChip(k, t('stCancelled'), ''); });
  }

  /* ---------- step-by-step replay ---------- */
  function stopAnim() { if (anim) { cancelAnimationFrame(anim.raf); anim = null; } }

  function startAnim(q, res, traces) {
    var n = q.n;
    anim = { n: n, k: {}, pos: 0, playing: false, acc: 0, last: 0, raf: 0, max: 0, trunc: res.A.traceTruncated || res.B.traceTruncated };
    ['A', 'B'].forEach(function (k) {
      C.board.clearFlags(boards[k], ['cat', 'x']);
      anim.k[k] = { ev: traces[k], stack: [], visited: 1, total: res[k].nodes, flagged: -1 };
      anim.max = Math.max(anim.max, traces[k].length);
      $('nodes' + k).textContent = '1 / ' + fmtN(res[k].nodes);
    });
    $('animBar').hidden = false; $('aPlay').textContent = t('play');
    updateInfo();
  }

  function resetAnimState() {
    ['A', 'B'].forEach(function (k) {
      var s = anim.k[k]; s.stack = []; s.visited = 1; s.flagged = -1;
      var b = boards[k]; C.board.clearFlags(b, ['cat', 'prune', 'dead', 'found']); b.el.classList.remove('flash-prune', 'flash-dead');
      $('nodes' + k).textContent = '1 / ' + fmtN(s.total);
    });
    anim.pos = 0;
  }

  function applyEvent(k, e) {
    var s = anim.k[k], b = boards[k], type = e & 7, x = e >> 3;
    if (s.flagged >= 0) { b.cells[s.flagged].classList.remove('prune', 'dead'); s.flagged = -1; }
    b.el.classList.remove('flash-prune', 'flash-dead');
    if (type === 0) { s.stack.push(x); b.cells[x].classList.add('cat'); s.visited++; }
    else if (type === 1) { var y = s.stack.pop(); b.cells[y].classList.remove('cat'); }
    else if (type === 2 || type === 3) {
      var cl = type === 2 ? 'prune' : 'dead';
      if (s.stack.length) { s.flagged = s.stack[s.stack.length - 1]; b.cells[s.flagged].classList.add(cl); }
      else b.el.classList.add('flash-' + cl);
    } else if (type === 4) b.el.classList.add('found');
  }

  function stepTo(target) {
    for (; anim.pos < target; anim.pos++) {
      ['A', 'B'].forEach(function (k) { var ev = anim.k[k].ev; if (anim.pos < ev.length) applyEvent(k, ev[anim.pos]); });
    }
    ['A', 'B'].forEach(function (k) {
      var s = anim.k[k], done = anim.pos >= s.ev.length;
      $('nodes' + k).textContent = done && !anim.trunc ? fmtN(s.total) : fmtN(s.visited) + ' / ' + fmtN(s.total);
    });
    updateInfo();
  }

  function updateInfo() {
    var i = Math.min(anim.pos, anim.max);
    $('aInfo').textContent = (i >= anim.max ? t('animDone') : t('animInfo', { i: i, n: anim.max })) + (anim.trunc ? t('animTruncated', { n: fmtN(TRACE_CAP) }) : '');
  }

  function rate() { return 2 * Math.pow(10, +$('aSpeed').value / 100 * 3); }

  function tick(ts) {
    if (!anim || !anim.playing) return;
    if (!anim.last) anim.last = ts;
    anim.acc += (ts - anim.last) / 1000 * rate(); anim.last = ts;
    var whole = Math.floor(anim.acc);
    if (whole > 0) { anim.acc -= whole; stepTo(Math.min(anim.max, anim.pos + whole)); }
    if (anim.pos >= anim.max) { anim.playing = false; $('aPlay').textContent = t('play'); return; }
    anim.raf = requestAnimationFrame(tick);
  }

  function togglePlay() {
    if (!anim) return;
    if (anim.playing) { anim.playing = false; cancelAnimationFrame(anim.raf); $('aPlay').textContent = t('play'); return; }
    if (anim.pos >= anim.max) resetAnimState();
    anim.playing = true; anim.last = 0; $('aPlay').textContent = t('pause'); anim.raf = requestAnimationFrame(tick);
  }

  function init() {
    return fetch('data/race.json').then(function (r) { return r.json(); }).then(function (d) {
      puzzles = d; buildSelect(); showPuzzle();
      $('btnRun').onclick = run; $('btnCancel').onclick = cancel;
      $('selRace').onchange = showPuzzle;
      $('aPlay').onclick = togglePlay;
      $('aStep').onclick = function () { if (!anim) return; if (anim.playing) togglePlay(); if (anim.pos >= anim.max) resetAnimState(); stepTo(Math.min(anim.max, anim.pos + 1)); };
      $('aRestart').onclick = function () { if (!anim) return; if (anim.playing) togglePlay(); resetAnimState(); updateInfo(); };
      document.addEventListener('langchange', function () { buildSelect(); showRef(selected()); if (!running) $('raceNote').textContent = t('noteCap');
        ['A', 'B'].forEach(function (k) { if (shown[k]) statusChip(k, shown[k][0], shown[k][1]); });
        if (shown.sum) summarize(shown.sum[0], shown.sum[1], shown.sum[2]);
      });
      document.addEventListener('racethis', function () {
        buildSelect(); $('selRace').value = 'play'; showPuzzle(); C.showTab('race');
      });
    });
  }
  C.race = { init: init };
})();
