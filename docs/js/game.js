/* Pure game-state transitions for Play mode (no DOM). Works in browsers (window.Cat.game) and node (module.exports).
   Marks: 0 empty, 1 X, 2 cat. A single tap toggles X, a double tap places a cat. A cat is judged against the unique solution the moment it is placed:
     correct -> locked[i]=1 ("gold": can never change again)
     wrong   -> the cat is removed at once, the cell is left empty with wrong[i]=1 ("red" frame), mistakes+1.
                The red frame stays as a reminder until the cell is changed again (tap, cat, drag).
   Every function returns a NEW state; functions that change cells also return `hist`, the changes ({i,from,to}) that
   belong on the undo stack. Gold placements and hints are never on it, so Undo cannot touch them.
   sol[r] = column of the cat in row r. */
(function (root) {
  var D = (typeof module !== 'undefined' && module.exports) ? require('./drag.js') : root.Cat.drag;

  function create(n) {
    var z = function () { var a = []; for (var i = 0; i < n * n; i++) a.push(0); return a; };
    return { n: n, marks: z(), locked: z(), wrong: z(), mistakes: 0, hints: 0, done: false };
  }
  function copy(s) {
    return { n: s.n, marks: s.marks.slice(), locked: s.locked.slice(), wrong: s.wrong.slice(), mistakes: s.mistakes, hints: s.hints, done: s.done };
  }
  function isCorrect(sol, n, i) { return sol[(i / n) | 0] === i % n; }
  function lockedCount(s) { var k = 0; for (var i = 0; i < s.locked.length; i++) k += s.locked[i] ? 1 : 0; return k; }

  // After a lock: all N cats gold -> done; stray red cats are removed from the finished board.
  function finish(s) {
    if (lockedCount(s) !== s.n) return;
    s.done = true;
    for (var i = 0; i < s.marks.length; i++) s.wrong[i] = 0;
  }

  // Put a cat on cell i of the (already copied) state s and judge it.
  function putCat(s, sol, i) {
    if (isCorrect(sol, s.n, i)) { s.marks[i] = 2; s.locked[i] = 1; s.wrong[i] = 0; finish(s); }
    else { s.marks[i] = 0; s.wrong[i] = 1; s.mistakes++; }
  }
  // Undo-stack entry for a wrong placement (X -> removed cat = empty); gold is never recorded.
  function entry(s, i, from) { return s.locked[i] ? [] : [{ i: i, from: from, to: s.marks[i] }]; }

  function frozen(s, i) { return s.done || s.locked[i]; }
  function same(s) { return { s: s, hist: [], changed: false }; }

  // Double tap / Enter: put a cat on cell i (from empty or X) and judge it at once. Clears a red frame.
  function placeCat(s, sol, i) {
    if (frozen(s, i)) return same(s);
    var t = copy(s), from = s.marks[i];
    t.wrong[i] = 0;
    putCat(t, sol, i);
    return { s: t, hist: entry(t, i, from), changed: true };
  }

  // Single tap / right click / Space: toggle X on empty/X (clears a red frame); gold never changes.
  function toggleX(s, i) {
    if (frozen(s, i)) return same(s);
    var t = copy(s), from = s.marks[i];
    t.wrong[i] = 0;
    t.marks[i] = from === 1 ? 0 : 1;
    return { s: t, hist: [{ i: i, from: from, to: t.marks[i] }], changed: true };
  }

  // One cell passed over during a drag. Same rules as drag.applyMode (only 0<->1) plus: locked/finished cells are skipped.
  function dragStep(s, mode, i) {
    if (frozen(s, i)) return same(s);
    var to = D.applyMode(mode, s.marks[i]);
    if (to < 0) return same(s);
    var t = copy(s), from = s.marks[i];
    t.marks[i] = to; t.wrong[i] = 0;
    return { s: t, hist: [{ i: i, from: from, to: to }], changed: true };
  }

  // Revert one undo-stack entry. Cells that are locked or no longer in the recorded state are left alone.
  function undo(s, changes) {
    if (s.done) return s;
    var t = copy(s);
    changes.forEach(function (c) {
      if (t.locked[c.i] || t.marks[c.i] !== c.to) return;
      t.marks[c.i] = c.from; t.wrong[c.i] = 0;
    });
    return t;
  }

  // Hint: put a gold cat on the first row whose solution cell is not yet confirmed. Counts as a hint, not a mistake.
  function hint(s, sol) {
    if (s.done) return { s: s, i: -1 };
    for (var r = 0; r < s.n; r++) {
      var i = r * s.n + sol[r];
      if (!s.locked[i]) {
        var t = copy(s);
        t.hints++; t.marks[i] = 2; t.locked[i] = 1; t.wrong[i] = 0; finish(t);
        return { s: t, i: i };
      }
    }
    return { s: s, i: -1 };
  }

  var api = { create: create, isCorrect: isCorrect, lockedCount: lockedCount, placeCat: placeCat, toggleX: toggleX, dragStep: dragStep, undo: undo, hint: hint };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else { root.Cat = root.Cat || {}; root.Cat.game = api; }
})(typeof window !== 'undefined' ? window : this);
