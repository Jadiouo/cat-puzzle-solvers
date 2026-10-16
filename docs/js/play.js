/* Play tab: choose a puzzle, place cats / X marks (each cat is judged at once: gold = correct and locked, red = wrong: the cat vanishes, the empty cell stays red), hint, timer. */
(function () {
  var C = window.Cat, t = C.t;
  var $ = function (id) { return document.getElementById(id); };
  var pool = [], big = [], cur = null, board = null, t0 = 0, timerId = 0, solved = false;
  var G = C.game, st = null, hist = new C.drag.History(), drag = null, hl = -1;
  var LEVELS = ['T3', 'T3b', 'T4', 'T5a', 'T5b'];

  function levelName(p) { return t('lv' + p.level); }
  function fmtTime(ms) { var s = Math.floor(ms / 1000); return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2); }
  // The message is kept as i18n keys (not text) so a language switch can re-render it.
  var lastMsg = null;
  function say(parts, cls) {
    lastMsg = { parts: parts, cls: cls };
    var m = $('playMsg');
    m.textContent = parts.map(function (p) { return t(p[0], p[1]); }).join(' ');
    m.className = 'msg' + (cls ? ' ' + cls : '');
  }

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
    cur = p; hist.clear(); drag = null; hl = -1; st = G.create(p.n); solved = false; cur._sol = p.solution || null;
    board = C.board.create($('playBoard'), p.regions, p.n, { interactive: true });
    $('playTitle').textContent = t('playTitle', { n: p.n, level: levelName(p), id: p.id });
    clearInterval(timerId); t0 = Date.now(); $('playTimer').textContent = '0:00';
    timerId = setInterval(function () { if (!solved) $('playTimer').textContent = fmtTime(Date.now() - t0); }, 500);
    say([['msgStart', { n: p.n }]]); render(null);
  }

  function newPuzzle() {
    var list = candidates();
    if (!list.length) { say([['msgNoPuzzle']]); return; }
    var p; do { p = list[Math.floor(Math.random() * list.length)]; } while (list.length > 1 && cur && p.id === cur.id);
    load(p);
  }

  // The state (marks / gold / red / counters) lives in `st`, a pure Cat.game state; the DOM only mirrors it.
  function render(prev) {
    for (var i = 0; i < st.marks.length; i++) {
      var cl = board.cells[i].classList, gold = !!st.locked[i], red = !!st.wrong[i];
      C.board.setMark(board, i, st.marks[i]);
      cl.toggle('gold', gold); cl.toggle('wrong', red);
      if (prev) {                                   // one-shot animation only on the placing moment
        if (gold && !prev.locked[i]) { cl.remove('fresh'); void board.cells[i].offsetWidth; cl.add('fresh'); }
        if (red && !prev.wrong[i]) { cl.remove('shake'); void board.cells[i].offsetWidth; cl.add('shake'); }
      } else { cl.remove('fresh'); cl.remove('shake'); }
    }
    $('playMistakes').textContent = t('mistakes', { n: st.mistakes });
    $('playHints').textContent = t('hintsUsed', { n: st.hints });
    $('playBoard').classList.toggle('won', st.done);
    $('btnUndo').disabled = st.done || !hist.size();
    $('btnHint').disabled = st.done;
  }

  function finishIfDone() {
    if (!st.done || solved) return;
    solved = true;
    var el = Date.now() - t0;
    $('playTimer').textContent = fmtTime(el);
    say([['solvedTitle'], ['msgSolved', { time: fmtTime(el), mistakes: st.mistakes, hints: st.hints }]], 'good');
  }

  // Apply one game transition result: update state, push undo entry, redraw, narrate.
  function apply(r, kind) {
    if (!r.changed) return false;
    var prev = st; st = r.s; hist.push(r.hist);
    render(prev); finishIfDone();
    if (!solved) {
      if (st.mistakes > prev.mistakes) say([['msgBad']], 'warn');
      else if (st.locked.join() !== prev.locked.join()) say([['msgGood', { left: cur.n - G.lockedCount(st) }]], 'good');
    }
    return true;
  }

  function undo() {
    if (solved || !cur) return;
    var ch = hist.pop(); if (!ch) return;
    var prev = st; st = G.undo(st, ch); render(prev);
  }

  function onHint() {
    if (solved || !cur || !cur._sol) return;
    var h = G.hint(st, cur._sol); if (h.i < 0) return;
    var prev = st; st = h.s; render(prev); finishIfDone();
    if (!solved) say([['msgHint', { r: ((h.i / cur.n) | 0) + 1, c: h.i % cur.n + 1 }]], 'good');
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
      drag = { id: e.pointerId, start: i, last: i, mode: D.modeFor(st.marks[i]), moved: false, seen: {}, list: [] };
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
        var r = G.dragStep(st, drag.mode, k);       // skips gold cats and finished boards
        if (r.changed) { st = r.s; C.board.setMark(board, k, st.marks[k]); drag.list = drag.list.concat(r.hist); }
      });
    });
    function finish(e, cancel) {
      if (!drag || drag.id !== e.pointerId) return;
      var d = drag; drag = null;
      try { el.releasePointerCapture(e.pointerId); } catch (x) {}
      if (d.moved) {
        if (d.list.length) { hist.push(d.list); render(st); }
      } else if (!cancel) apply(G.click(st, cur._sol, d.start));
    }
    el.addEventListener('pointerup', function (e) { finish(e, false); });
    el.addEventListener('pointercancel', function (e) { finish(e, true); });
    el.addEventListener('pointerleave', function (e) { if (!drag) hover(-1); });
    el.addEventListener('contextmenu', function (e) {
      e.preventDefault();
      var c = e.target.closest('.cell'); if (!c || !cur || e.pointerType === 'touch' || drag) return;
      apply(G.toggleX(st, +c.dataset.i));
    });
    el.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      var c = e.target.closest('.cell'); if (!c) return;
      e.preventDefault(); apply(G.click(st, cur._sol, +c.dataset.i));
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
    $('btnHint').onclick = onHint;
    $('btnReset').onclick = function () { if (cur) load(cur); };
    $('btnRaceThis').onclick = function () { document.dispatchEvent(new CustomEvent('racethis')); };
    document.addEventListener('langchange', function () {
      fillSelects();
      if (cur) { $('playTitle').textContent = t('playTitle', { n: cur.n, level: levelName(cur), id: cur.id }); render(st); }
      if (lastMsg) say(lastMsg.parts, lastMsg.cls);
    });
  }

  function init() {
    return Promise.all([fetch('data/pool.json').then(function (r) { return r.json(); }), fetch('data/s5.json').then(function (r) { return r.json(); })])
      .then(function (a) { pool = a[0]; big = a[1]; fillSelects(); bind(); newPuzzle(); });
  }
  C.play = { init: init, current: function () { return cur; } };
})();
