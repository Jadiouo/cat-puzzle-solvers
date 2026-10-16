// Unit tests for docs/js/game.js (pure state transitions). Exit code 0 = all passed.
const assert = require('assert');
const G = require('../../docs/js/game.js');
const D = require('../../docs/js/drag.js');
const n = 4, sol = [1, 3, 0, 2];               // cats at 1, 7, 8, 14
const at = (r) => r * n + sol[r];
const cat = (s, i) => G.click(G.click(s, sol, i).s, sol, i);   // empty -> X -> cat

// correct cat -> gold + locked, no mistake; not on undo stack
let r = cat(G.create(n), at(0));
assert.strictEqual(r.s.marks[at(0)], 2); assert.strictEqual(r.s.locked[at(0)], 1); assert.strictEqual(r.s.mistakes, 0);
assert.deepStrictEqual(r.hist, []);
let s = r.s;
// click / right-click / drag on gold: no effect
assert.strictEqual(G.click(s, sol, at(0)).changed, false);
assert.strictEqual(G.toggleX(s, at(0)).changed, false);
assert.strictEqual(G.dragStep(s, 'fill', at(0)).changed, false);
assert.strictEqual(G.dragStep(s, 'clear', at(0)).changed, false);
assert.strictEqual(G.click(s, sol, at(0)).s.marks[at(0)], 2);
// drag fill over a row skips gold, fills the rest
let t = s; for (let c = 0; c < n; c++) t = G.dragStep(t, 'fill', c).s;
assert.deepStrictEqual(t.marks.slice(0, 4), [1, 2, 1, 1]); assert.strictEqual(t.locked[1], 1);
// wrong cat -> red, mistakes+1, stays on the board
let w = cat(G.create(n), 0);
assert.strictEqual(w.s.marks[0], 2); assert.strictEqual(w.s.wrong[0], 1); assert.strictEqual(w.s.locked[0], 0); assert.strictEqual(w.s.mistakes, 1);
// click red -> empty (not X); mistakes unchanged; a second wrong placement counts again
let w2 = G.click(w.s, sol, 0).s;
assert.strictEqual(w2.marks[0], 0); assert.strictEqual(w2.wrong[0], 0); assert.strictEqual(w2.mistakes, 1);
assert.strictEqual(cat(w2, 0).s.mistakes, 2);
// right-click on red also removes it
assert.strictEqual(G.toggleX(w.s, 0).s.marks[0], 0);
// undo: X placed before gold stays gold; undo of a plain X works; undo of a red cat goes back to X
let u = G.click(G.create(n), sol, 5); const hx = u.hist;      // 0 -> X
assert.strictEqual(G.undo(u.s, hx).marks[5], 0);
let g1 = G.click(G.create(n), sol, at(1)); const hxx = g1.hist; // X (undoable)
let g2 = G.click(g1.s, sol, at(1));                              // gold (not recorded)
assert.deepStrictEqual(g2.hist, []);
assert.strictEqual(G.undo(g2.s, hxx).marks[at(1)], 2); assert.strictEqual(G.undo(g2.s, hxx).locked[at(1)], 1);
let rx = G.click(G.create(n), sol, 0); let rc = G.click(rx.s, sol, 0);   // X then red cat
assert.deepStrictEqual(rc.hist, [{ i: 0, from: 1, to: 2 }]);
let ru = G.undo(rc.s, rc.hist); assert.strictEqual(ru.marks[0], 1); assert.strictEqual(ru.wrong[0], 0); assert.strictEqual(ru.mistakes, 1);
// stale entry (red already removed) is ignored
assert.strictEqual(G.undo(G.click(rc.s, sol, 0).s, rc.hist).marks[0], 0);
// hint: gold cat on first unconfirmed solution cell, hint count +1, mistakes unchanged
let h = G.hint(G.create(n), sol);
assert.strictEqual(h.i, at(0)); assert.strictEqual(h.s.marks[at(0)], 2); assert.strictEqual(h.s.locked[at(0)], 1);
assert.strictEqual(h.s.hints, 1); assert.strictEqual(h.s.mistakes, 0);
let h2 = G.hint(h.s, sol); assert.strictEqual(h2.i, at(1)); assert.strictEqual(h2.s.hints, 2);
// complete: all gold -> done, then everything is frozen (including undo and hint), red strays removed
let f = G.create(n); f = cat(f, 0).s;                    // one stray red cat
for (let k = 0; k < n; k++) f = cat(f, at(k)).s;
assert.strictEqual(f.done, true); assert.strictEqual(G.lockedCount(f), n); assert.strictEqual(f.mistakes, 1);
assert.strictEqual(f.marks[0], 0); assert.strictEqual(f.wrong.reduce((a, b) => a + b, 0), 0);
for (const i of [0, 2, at(2)]) {
  assert.strictEqual(G.click(f, sol, i).changed, false); assert.strictEqual(G.toggleX(f, i).changed, false);
  assert.strictEqual(G.dragStep(f, 'fill', i).changed, false);
}
assert.strictEqual(G.undo(f, [{ i: 0, from: 0, to: 0 }]), f); assert.strictEqual(G.hint(f, sol).i, -1);
// hint can complete the board too
let hh = G.create(n); for (let k = 0; k < n; k++) hh = G.hint(hh, sol).s;
assert.strictEqual(hh.done, true); assert.strictEqual(hh.hints, n);
// input state is never mutated
const s0 = G.create(n), snap = JSON.stringify(s0); G.click(s0, sol, 0); G.hint(s0, sol); G.toggleX(s0, 1); G.dragStep(s0, 'fill', 2);
assert.strictEqual(JSON.stringify(s0), snap);
console.log('verify_game: ok');
