// Unit tests for docs/js/drag.js (pure helpers). Exit code 0 = all passed.
const assert = require('assert');
const D = require('../../docs/js/drag.js');
const n = 6;
// mode decision
assert.strictEqual(D.modeFor(0), 'fill'); assert.strictEqual(D.modeFor(1), 'clear'); assert.strictEqual(D.modeFor(2), null);
// applyMode: cats never change, fill only touches empties, clear only touches X
assert.strictEqual(D.applyMode('fill', 0), 1); assert.strictEqual(D.applyMode('fill', 1), -1); assert.strictEqual(D.applyMode('fill', 2), -1);
assert.strictEqual(D.applyMode('clear', 1), 0); assert.strictEqual(D.applyMode('clear', 0), -1); assert.strictEqual(D.applyMode('clear', 2), -1);
for (const m of [0, 1, 2]) assert.strictEqual(D.applyMode(null, m), -1);
// cellAt
assert.strictEqual(D.cellAt(0, 0, 0, 0, 60, 60, n), 0);
assert.strictEqual(D.cellAt(59.9, 59.9, 0, 0, 60, 60, n), 35);
assert.strictEqual(D.cellAt(60, 10, 0, 0, 60, 60, n), null);
assert.strictEqual(D.cellAt(-1, 10, 0, 0, 60, 60, n), null);
assert.strictEqual(D.cellAt(25, 15, 10, 5, 60, 60, n), 1 * 0 + 1 + 1 * n); // x=(25-10)/10=1, y=(15-5)/10=1
// line: endpoints, no gaps, 8-connected, both directions, every size
for (const N of [6, 9, 16]) {
  for (let a = 0; a < N * N; a += 3) for (let b = 0; b < N * N; b += 5) {
    const p = D.line(a, b, N);
    assert.strictEqual(p[0], a); assert.strictEqual(p[p.length - 1], b);
    const need = Math.max(Math.abs((a % N) - (b % N)), Math.abs(((a / N) | 0) - ((b / N) | 0))) + 1;
    assert.strictEqual(p.length, need, 'length ' + a + '->' + b);
    for (let k = 1; k < p.length; k++) {
      assert.ok(Math.abs((p[k] % N) - (p[k - 1] % N)) <= 1 && Math.abs(((p[k] / N) | 0) - ((p[k - 1] / N) | 0)) <= 1);
    }
  }
}
assert.deepStrictEqual(D.line(0, 5, 6), [0, 1, 2, 3, 4, 5]);          // whole first row, jumping straight to the far end
assert.deepStrictEqual(D.line(5, 0, 6), [5, 4, 3, 2, 1, 0]);
assert.deepStrictEqual(D.line(0, 30, 6), [0, 6, 12, 18, 24, 30]);      // column
assert.deepStrictEqual(D.line(7, 7, 6), [7]);
// simulated drag over a row that contains a cat: fill skips the cat, clear skips the cat
{
  const marks = [0, 0, 2, 0, 1, 0]; const mode = D.modeFor(marks[0]);
  D.line(0, 5, 6).forEach(k => { const to = D.applyMode(mode, marks[k]); if (to >= 0) marks[k] = to; });
  assert.deepStrictEqual(marks, [1, 1, 2, 1, 1, 1]);
  const m2 = [1, 1, 2, 1, 0, 1]; const md = D.modeFor(m2[0]);
  D.line(0, 5, 6).forEach(k => { const to = D.applyMode(md, m2[k]); if (to >= 0) m2[k] = to; });
  assert.deepStrictEqual(m2, [0, 0, 2, 0, 0, 0]);
  const m3 = [2, 0, 1, 0, 0, 0]; const m0 = D.modeFor(m3[0]); // start on a cat: nothing changes
  D.line(0, 5, 6).forEach(k => { const to = D.applyMode(m0, m3[k]); if (to >= 0) m3[k] = to; });
  assert.deepStrictEqual(m3, [2, 0, 1, 0, 0, 0]);
}
// history: one entry per action, LIFO
{
  const h = new D.History(); h.push([]); assert.strictEqual(h.size(), 0);
  h.push([{ i: 0, from: 0, to: 1 }, { i: 1, from: 0, to: 1 }]); h.push([{ i: 2, from: 1, to: 0 }]);
  assert.strictEqual(h.size(), 2); assert.strictEqual(h.pop()[0].i, 2); assert.strictEqual(h.pop().length, 2); assert.strictEqual(h.pop(), null);
}
console.log('drag.js: all checks passed');
