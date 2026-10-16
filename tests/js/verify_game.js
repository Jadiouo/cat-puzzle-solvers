// Unit tests for docs/js/game.js (pure state transitions). Exit code 0 = all passed.
const assert = require('assert');
const G = require('../../docs/js/game.js');
const D = require('../../docs/js/drag.js');
const n = 4, sol = [1, 3, 0, 2];               // cats at 1, 7, 8, 14
const at = (r) => r * n + sol[r];
const cat = (s, i) => G.placeCat(s, sol, i);                  // double tap

// correct cat -> gold + locked, no mistake; not on undo stack
let r = cat(G.create(n), at(0));
assert.strictEqual(r.s.marks[at(0)], 2); assert.strictEqual(r.s.locked[at(0)], 1); assert.strictEqual(r.s.mistakes, 0);
assert.deepStrictEqual(r.hist, []);
let s = r.s;
// tap / double tap / drag on gold: no effect
assert.strictEqual(G.placeCat(s, sol, at(0)).changed, false);
assert.strictEqual(G.toggleX(s, at(0)).changed, false);
assert.strictEqual(G.dragStep(s, 'fill', at(0)).changed, false);
assert.strictEqual(G.dragStep(s, 'clear', at(0)).changed, false);
assert.strictEqual(G.placeCat(s, sol, at(0)).s.marks[at(0)], 2);
// drag fill over a row skips gold, fills the rest
let t = s; for (let c = 0; c < n; c++) t = G.dragStep(t, 'fill', c).s;
assert.deepStrictEqual(t.marks.slice(0, 4), [1, 2, 1, 1]); assert.strictEqual(t.locked[1], 1);
// wrong cat -> the cat vanishes at once, the empty cell keeps a red frame, mistakes+1
let w = cat(G.create(n), 0);
assert.strictEqual(w.s.marks[0], 0); assert.strictEqual(w.s.wrong[0], 1); assert.strictEqual(w.s.locked[0], 0); assert.strictEqual(w.s.mistakes, 1);
// single tap toggles only empty <-> X, never a cat
let x1 = G.toggleX(G.create(n), at(0)).s; assert.strictEqual(x1.marks[at(0)], 1);
let x2 = G.toggleX(x1, at(0)).s; assert.strictEqual(x2.marks[at(0)], 0); assert.strictEqual(x2.locked[at(0)], 0);
// a wrong cat straight from an empty cell: undo entry only clears the red frame
assert.deepStrictEqual(w.hist, [{ i: 0, from: 0, to: 0 }]);
let wu = G.undo(w.s, w.hist); assert.strictEqual(wu.wrong[0], 0); assert.strictEqual(wu.mistakes, 1);
// tap on the red empty cell -> X, red cleared; mistakes unchanged; another wrong cat there counts again
let w2 = G.toggleX(w.s, 0).s;
assert.strictEqual(w2.marks[0], 1); assert.strictEqual(w2.wrong[0], 0); assert.strictEqual(w2.mistakes, 1);
assert.strictEqual(G.placeCat(w2, sol, 0).s.mistakes, 2);
// drag fill over red -> X, red cleared
let wd = G.dragStep(w.s, 'fill', 0).s; assert.strictEqual(wd.marks[0], 1); assert.strictEqual(wd.wrong[0], 0);
// undo: X placed before gold stays gold; undo of a plain X works; undo of a red cat goes back to X
let u = G.toggleX(G.create(n), 5); const hx = u.hist;         // 0 -> X
assert.strictEqual(G.undo(u.s, hx).marks[5], 0);
let g1 = G.toggleX(G.create(n), at(1)); const hxx = g1.hist;    // X (undoable)
let g2 = G.placeCat(g1.s, sol, at(1));                           // gold (not recorded)
assert.deepStrictEqual(g2.hist, []);
assert.strictEqual(G.undo(g2.s, hxx).marks[at(1)], 2); assert.strictEqual(G.undo(g2.s, hxx).locked[at(1)], 1);
let rx = G.toggleX(G.create(n), 0); let rc = G.placeCat(rx.s, sol, 0);   // X then wrong cat (vanishes -> empty)
assert.deepStrictEqual(rc.hist, [{ i: 0, from: 1, to: 0 }]);
let ru = G.undo(rc.s, rc.hist); assert.strictEqual(ru.marks[0], 1); assert.strictEqual(ru.wrong[0], 0); assert.strictEqual(ru.mistakes, 1);
// stale entry (cell changed since) is ignored
assert.strictEqual(G.undo(G.toggleX(rc.s, 0).s, rc.hist).marks[0], 1);
// hint: gold cat on first unconfirmed solution cell, hint count +1, mistakes unchanged
let h = G.hint(G.create(n), sol);
assert.strictEqual(h.i, at(0)); assert.strictEqual(h.s.marks[at(0)], 2); assert.strictEqual(h.s.locked[at(0)], 1);
assert.strictEqual(h.s.hints, 1); assert.strictEqual(h.s.mistakes, 0);
let h2 = G.hint(h.s, sol); assert.strictEqual(h2.i, at(1)); assert.strictEqual(h2.s.hints, 2);
// complete: all gold -> done, then everything is frozen (including undo and hint), red frames cleared
let f = G.create(n); f = cat(f, 0).s;                    // one red (wrong) cell
for (let k = 0; k < n; k++) f = cat(f, at(k)).s;
assert.strictEqual(f.done, true); assert.strictEqual(G.lockedCount(f), n); assert.strictEqual(f.mistakes, 1);
assert.strictEqual(f.marks[0], 0); assert.strictEqual(f.wrong.reduce((a, b) => a + b, 0), 0);
for (const i of [0, 2, at(2)]) {
  assert.strictEqual(G.placeCat(f, sol, i).changed, false); assert.strictEqual(G.toggleX(f, i).changed, false);
  assert.strictEqual(G.dragStep(f, 'fill', i).changed, false);
}
assert.strictEqual(G.undo(f, [{ i: 0, from: 0, to: 0 }]), f); assert.strictEqual(G.hint(f, sol).i, -1);
// hint can complete the board too
let hh = G.create(n); for (let k = 0; k < n; k++) hh = G.hint(hh, sol).s;
assert.strictEqual(hh.done, true); assert.strictEqual(hh.hints, n);
// input state is never mutated
const s0 = G.create(n), snap = JSON.stringify(s0); G.placeCat(s0, sol, 0); G.hint(s0, sol); G.toggleX(s0, 1); G.dragStep(s0, 'fill', 2);
assert.strictEqual(JSON.stringify(s0), snap);
console.log('verify_game: ok');
