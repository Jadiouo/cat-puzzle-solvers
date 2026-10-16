/* Pure helpers for drag-painting on the board (no DOM). Works in browsers (window.Cat.drag) and node (module.exports).
   Marks: 0 empty, 1 X, 2 cat. */
(function (root) {
  // Mode is decided by the mark of the cell where the drag starts.
  //   empty -> 'fill'  (dragged-over empty cells become X)
  //   X     -> 'clear' (dragged-over X cells become empty)
  //   cat   -> null    (dragging changes nothing)
  function modeFor(startMark) { return startMark === 0 ? 'fill' : startMark === 1 ? 'clear' : null; }

  // New mark for a cell under the given mode, or -1 when the cell must stay as it is (cats never change).
  function applyMode(mode, mark) {
    if (mode === 'fill') return mark === 0 ? 1 : -1;
    if (mode === 'clear') return mark === 1 ? 0 : -1;
    return -1;
  }

  // Cell index under a point, from the board's bounding box; null outside it. (x,y in the same space as the rect.)
  function cellAt(x, y, left, top, width, height, n) {
    var fx = (x - left) / width, fy = (y - top) / height;
    if (!(fx >= 0 && fx < 1 && fy >= 0 && fy < 1)) return null;
    return Math.floor(fy * n) * n + Math.floor(fx * n);
  }

  // Every cell on the straight line from cell a to cell b (inclusive, Bresenham), so a fast pointer never skips a cell.
  function line(a, b, n) {
    var x0 = a % n, y0 = (a / n) | 0, x1 = b % n, y1 = (b / n) | 0, out = [];
    var dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1, err = dx + dy;
    for (;;) {
      out.push(y0 * n + x0);
      if (x0 === x1 && y0 === y1) break;
      var e2 = 2 * err;
      if (e2 >= dy) { err += dy; x0 += sx; }
      if (e2 <= dx) { err += dx; y0 += sy; }
    }
    return out;
  }

  // Undo history: each entry is one user action = list of {i, from, to}. Pure stack operations.
  function History() { this.stack = []; }
  History.prototype.push = function (changes) { if (changes && changes.length) this.stack.push(changes); };
  History.prototype.pop = function () { return this.stack.pop() || null; };
  History.prototype.clear = function () { this.stack.length = 0; };
  History.prototype.size = function () { return this.stack.length; };

  var api = { modeFor: modeFor, applyMode: applyMode, cellAt: cellAt, line: line, History: History };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else { root.Cat = root.Cat || {}; root.Cat.drag = api; }
})(typeof window !== 'undefined' ? window : this);
