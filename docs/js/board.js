/* Cat.board: renders an N×N region board into a container and exposes per-cell state setters. */
(function () {
  function hue(i) { return (i * 137.508 + 20) % 360; }

  function create(container, regions, n, opts) {
    opts = opts || {};
    container.innerHTML = '';
    container.style.setProperty('--n', n);
    container.classList.toggle('dense', n >= 14);
    var cells = [], frag = document.createDocumentFragment();
    // region ids -> compact indices (palette follows index)
    var ids = [], map = {};
    regions.forEach(function (row) { row.forEach(function (v) { if (map[v] === undefined) { map[v] = ids.length; ids.push(v); } }); });
    for (var r = 0; r < n; r++) for (var c = 0; c < n; c++) {
      var d = document.createElement('div');
      var g = regions[r][c];
      d.className = 'cell';
      d.style.setProperty('--h', hue(map[g]).toFixed(1));
      if (r === 0 || regions[r - 1][c] !== g) d.classList.add('bt');
      if (r === n - 1 || regions[r + 1][c] !== g) d.classList.add('bb');
      if (c === 0 || regions[r][c - 1] !== g) d.classList.add('bl');
      if (c === n - 1 || regions[r][c + 1] !== g) d.classList.add('br');
      d.dataset.i = r * n + c;
      d.innerHTML = '<svg class="ic"><use href="#cat"/></svg>';
      if (opts.interactive) { d.setAttribute('role', 'gridcell'); d.tabIndex = 0; }
      frag.appendChild(d); cells.push(d);
    }
    container.appendChild(frag);
    return { el: container, cells: cells, n: n };
  }

  // mark: 0 empty, 1 X, 2 cat
  function setMark(b, i, mark) {
    var cl = b.cells[i].classList;
    cl.toggle('x', mark === 1); cl.toggle('cat', mark === 2);
  }
  function clearFlags(b, names) {
    b.cells.forEach(function (c) { names.forEach(function (nm) { c.classList.remove(nm); }); });
  }
  window.Cat = window.Cat || {};
  window.Cat.board = { create: create, setMark: setMark, clearFlags: clearFlags };
})();
