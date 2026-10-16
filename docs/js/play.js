/* Play tab: choose a puzzle, place cats / X marks, check, hint (computed by the solver in a worker), timer. */
(function () {
  var C = window.Cat, t = C.t;
  var $ = function (id) { return document.getElementById(id); };
  var pool = [], big = [], cur = null, marks = null, board = null, t0 = 0, timerId = 0, solved = false, hints = 0;
  var runner = new C.Runner(), hinting = false, hist = new C.drag.History(), drag = null, hl = -1;
  var LEVELS = ['T3', 'T3b', 'T4', 'T5a', 'T5b'];

  function levelName(p) { return t('lv' + p.level); }
  function fmtTime(ms) { var s = Math.floor(ms / 1000); return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2); }
  function say(text, cls) { var m = $('playMsg'); m.textContent = text; m.className = 'msg' + (cls ? ' ' + cls : ''); }

  function fillSelects() {
    var ss = $('selSize'), sl = $('selLevel'), vs = ss.value, vl = sl.value;
    ss.innerHTML = ''; sl.innerHTML = '';
    [6, 7, 8, 9].forEach(function (n) { ss.add(new Option(n + '×' + n, String(n))); });
    ss.add(new Option(t('big'), 'big'));
    sl.add(new Option(t('any'), 'any'));
    LEVELS.forEach(function (l) { sl.add(new Option(t('lv' + l), l)); });
    ss.value = vs || '6'; sl.value = vl || 'any';
    sl.disabled = ss.value === 'big';
  }

  function candidates() {
    var s = $('selSize').value, l = $('selLevel').value;
    if (s === 'big') return big;
    return pool.filter(function (p) { return p.n === +s && (l === 'any' || p.level === l); });
  }

  function load(p) {
    cur = p; hist.clear(); drag = null; hl = -1; marks = new Int8Array(p.n * p.n); solved = false; hints = 0; cur._sol = p.solution || null;
    board = C.board.create($('playBoard'), p.regions, p.n, { interactive: true });
    $('playTitle').textContent = t('playTitle', { n: p.n, level: levelName(p), id: p.id });
    clearInterval(timerId); t0 = Date.now(); $('playTimer').textContent = '0:00';
    timerId = setInterval(function () { if (!solved) $('playTimer').textContent = fmtTime(Date.now() - t0); }, 500);
    $('playBoard').classList.remove('won');
    say(t('msgStart', { n: p.n })); syncUndo();
  }

  function newPuzzle() {
    var list = candidates();
    if (!list.length) { say('No puzzle for this filter.'); return; }
    var p; do { p = list[Math.floor(Math.random() * list.length)]; } while (list.length > 1 && cur && p.id === cur.id);
    load(p);
  }

  function cats() { var o = []; for (var i = 0; i < marks.length; i++) if (marks[i] === 2) o.push(i); return o; }

  function conflicts() {
    var n = cur.n, bad = {}, rows = {}, cols = {}, regs = {}, cs = cats(), i, j;
    cs.forEach(function (x) {
      var r = (x / n) | 0, c = x % n, g = cur.regions[r][c];
      (rows[r] = rows[r] || []).push(x); (cols[c] = cols[c] || []).push(x); (regs[g] = regs[g] || []).push(x);
    });
    [rows, cols, regs].forEach(function (m) { Object.keys(m).forEach(function (k) { if (m[k].length > 1) m[k].forEach(function (x) { bad[x] = 1; }); }); });
    for (i = 0; i < cs.length; i++) for (j = i + 1; j < cs.length; j++) {
      var a = cs[i], b = cs[j];
      if (Math.abs(((a / n) | 0) - ((b / n) | 0)) <= 1 && Math.abs(a % n - b % n) <= 1) { bad[a] = 1; bad[b] = 1; }
    }
    return Object.keys(bad).map(Number);
  }

  function wrongCats() {
    if (!cur._sol) return [];
    var n = cur.n;
    return cats().filter(function (x) { return cur._sol[(x / n) | 0] !== x % n; });
  }

  function flag(list, cls) { list.forEach(function (x) { board.cells[x].classList.add(cls); }); }

  function checkSolved() {
    if (solved || cats().length !== cur.n || conflicts().length) return false;
    solved = true;
    var el = Date.now() - t0;
    $('playTimer').textContent = fmtTime(el);
    $('playBoard').classList.add('won');
    say(t('solvedTitle') + ' ' + t('msgSolved', { time: fmtTime(el), hints: hints }), 'good');
    return true;
  }

  function syncUndo() { $('btnUndo').disabled = solved || !hist.size(); }

  function refreshConflicts() {
    for (var i = 0; i < board.cells.length; i++) board.cells[i].classList.remove('conf');
    flag(conflicts(), 'conf');
  }

  // Apply a list of {i, to} as ONE undoable action. Returns true when something changed.
  function commit(list) {
    if (solved) return false;
    var ch = [];
    list.forEach(function (c) { if (marks[c.i] !== c.to) ch.push({ i: c.i, from: marks[c.i], to: c.to }); });
    if (!ch.length) return false;
    ch.forEach(function (c) { marks[c.i] = c.to; C.board.setMark(board, c.i, c.to); });
    hist.push(ch);
    C.board.clearFlags(board, ['bad', 'hintcell']);
    refreshConflicts(); checkSolved(); syncUndo();
    return true;
  }

  function undo() {
    if (solved || !cur) return;
    var ch = hist.pop(); if (!ch) return;
    ch.forEach(function (c) { marks[c.i] = c.from; C.board.setMark(board, c.i, c.from); });
    C.board.clearFlags(board, ['bad', 'hintcell']);
    refreshConflicts(); syncUndo();
  }

  function setMark(i, v) { commit([{ i: i, to: v }]); }

  function onCheck() {
    if (solved) return;
    C.board.clearFlags(board, ['bad', 'hintcell']);
    var cf = conflicts();
    if (cf.length) { flag(cf, 'bad'); say(t('msgConf'), 'warn'); return; }
    var w = wrongCats();
    if (w.length) { flag(w, 'bad'); say(t('msgWrong'), 'warn'); return; }
    say(t('msgOk', { left: cur.n - cats().length }), 'good');
  }

  function onHint() {
    if (solved || hinting) return;
    C.board.clearFlags(board, ['bad', 'hintcell']);
    hinting = true; say(t('msgHintThinking'));
    var p = cur;
    // The hint cell always comes from the solver (match DFS, first solution).
    runner.run({ regions: p.regions, n: p.n, algo: 'match', limit: 1 }).then(function (o) {
      hinting = false;
      if (!o || p !== cur) return;
      var sol = o.result.solutions[0]; p._sol = sol;
      var wr = wrongCats();
      if (wr.length) { flag(wr, 'bad'); say(t('msgHintWrong'), 'warn'); return; }
      for (var r = 0; r < p.n; r++) {
        var x = r * p.n + sol[r];
        if (marks[x] !== 2) {
          hints++; commit([{ i: x, to: 2 }]); board.cells[x].classList.add('hintcell');
          say(t('msgHint', { r: r + 1, c: sol[r] + 1 }), 'good'); return;
        }
      }
      say(t('msgHintDone'));
    });
  }

  function bind() {
    var el = $('playBoard'), D = C.drag;
    function cellFromEvent(e) {
      var r = el.getBoundingClientRect();
      return D.cellAt(e.clientX, e.clientY, r.left, r.top, r.width, r.height, cur.n);
    }
    function hover(i) {
      if (i === hl) return;
      if (hl >= 0 && board.cells[hl]) board.cells[hl].classList.remove('hl');
      hl = i; if (i >= 0) board.cells[i].classList.add('hl');
    }
    // Pointer Events: one code path for mouse, touch and pen. Nothing changes until the pointer leaves the start
    // cell (drag) or is released on it (click = cycle empty -> X -> cat -> empty).
    el.addEventListener('pointerdown', function (e) {
      if (!cur || solved || e.button !== 0 || !e.isPrimary) return;
      var i = cellFromEvent(e); if (i === null) return;
      drag = { id: e.pointerId, start: i, last: i, mode: D.modeFor(marks[i]), moved: false, seen: {}, list: [] };
      try { el.setPointerCapture(e.pointerId); } catch (x) {}
      e.preventDefault();
    });
    el.addEventListener('pointermove', function (e) {
      if (!cur) return;
      var i = cellFromEvent(e);
      if (e.pointerType === 'mouse' || drag) hover(i === null ? -1 : i);
      if (!drag || drag.id !== e.pointerId || i === null || i === drag.last) return;
      var path = D.line(drag.last, i, cur.n);
      if (!drag.moved) { drag.moved = true; path.unshift(drag.start); }
      drag.last = i;
      path.forEach(function (k) {
        if (drag.seen[k]) return; drag.seen[k] = 1;
        var to = D.applyMode(drag.mode, marks[k]);
        if (to >= 0) { marks[k] = to; C.board.setMark(board, k, to); drag.list.push({ i: k, from: to === 1 ? 0 : 1, to: to }); }
      });
    });
    function finish(e, cancel) {
      if (!drag || drag.id !== e.pointerId) return;
      var d = drag; drag = null;
      try { el.releasePointerCapture(e.pointerId); } catch (x) {}
      if (d.moved) {
        if (d.list.length) { hist.push(d.list); C.board.clearFlags(board, ['bad', 'hintcell']); refreshConflicts(); checkSolved(); syncUndo(); }
      } else if (!cancel) setMark(d.start, (marks[d.start] + 1) % 3);
    }
    el.addEventListener('pointerup', function (e) { finish(e, false); });
    el.addEventListener('pointercancel', function (e) { finish(e, true); });
    el.addEventListener('pointerleave', function (e) { if (!drag) hover(-1); });
    el.addEventListener('contextmenu', function (e) {
      e.preventDefault();
      var c = e.target.closest('.cell'); if (!c || !cur || e.pointerType === 'touch' || drag) return;
      var i = +c.dataset.i; setMark(i, marks[i] === 1 ? 0 : 1);
    });
    el.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      var c = e.target.closest('.cell'); if (!c) return;
      e.preventDefault(); var i = +c.dataset.i; setMark(i, (marks[i] + 1) % 3);
    });
    document.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && (e.key === 'z' || e.key === 'Z') && !$('tab-play').hidden) {
        var tg = e.target && e.target.tagName;
        if (tg === 'SELECT' || tg === 'INPUT' || tg === 'TEXTAREA') return;
        e.preventDefault(); undo();
      }
    });
    $('btnUndo').onclick = undo;
    $('btnNew').onclick = newPuzzle;
    $('selSize').onchange = function () { $('selLevel').disabled = $('selSize').value === 'big'; newPuzzle(); };
    $('selLevel').onchange = newPuzzle;
    $('btnCheck').onclick = onCheck;
    $('btnHint').onclick = onHint;
    $('btnReset').onclick = function () { if (cur) load(cur); };
    $('btnRaceThis').onclick = function () { document.dispatchEvent(new CustomEvent('racethis')); };
    document.addEventListener('langchange', function () {
      fillSelects();
      if (cur) $('playTitle').textContent = t('playTitle', { n: cur.n, level: levelName(cur), id: cur.id });
    });
  }

  function init() {
    return Promise.all([fetch('data/pool.json').then(function (r) { return r.json(); }), fetch('data/s5.json').then(function (r) { return r.json(); })])
      .then(function (a) { pool = a[0]; big = a[1]; fillSelects(); bind(); newPuzzle(); });
  }
  C.play = { init: init, current: function () { return cur; } };
})();
