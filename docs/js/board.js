/* Cat.board: renders an N×N region board into a container and exposes per-cell state setters.
   Layout rules (so cells can never change size): the grid is repeat(N, 1fr) x repeat(N, 1fr) inside a square
   container; cells have no borders; the cat / X glyphs are absolutely positioned; grid lines and region
   boundaries are drawn by one SVG overlay (vector-effect: non-scaling-stroke), not by per-cell borders. */
(function () {
  var NS = 'http://www.w3.org/2000/svg';
  function hue(i) { return (i * 137.508 + 20) % 360; }

  function overlay(regions, n) {
    var thin = '', thick = '', r, c;
    for (var k = 1; k < n; k++) thin += 'M' + k + ' 0V' + n + 'M0 ' + k + 'H' + n;
    for (r = 0; r < n; r++) for (c = 0; c < n; c++) {
      var g = regions[r][c];
      if (c + 1 < n && regions[r][c + 1] !== g) thick += 'M' + (c + 1) + ' ' + r + 'v1';
      if (r + 1 < n && regions[r + 1][c] !== g) thick += 'M' + c + ' ' + (r + 1) + 'h1';
    }
    var svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('class', 'lines'); svg.setAttribute('viewBox', '0 0 ' + n + ' ' + n);
    svg.setAttribute('preserveAspectRatio', 'none'); svg.setAttribute('aria-hidden', 'true');
    [['thin', thin], ['thick', thick]].forEach(function (p) {
      var el = document.createElementNS(NS, 'path');
      el.setAttribute('class', p[0]); el.setAttribute('d', p[1]); svg.appendChild(el);
    });
    return svg;
  }

  function create(container, regions, n, opts) {
    opts = opts || {};
    container.innerHTML = '';
    container.style.setProperty('--n', n);
    container.classList.toggle('dense', n >= 14);
    container.classList.toggle('play', !!opts.interactive);
    var cells = [], frag = document.createDocumentFragment();
    var ids = [], map = {};
    regions.forEach(function (row) { row.forEach(function (v) { if (map[v] === undefined) { map[v] = ids.length; ids.push(v); } }); });
    var glyphs = '<svg class="ic" viewBox="0 0 24 24"><use href="#cat"/></svg>' +
      (opts.interactive ? '<svg class="xm" viewBox="0 0 24 24"><path d="M7 7l10 10M17 7L7 17"/></svg>' : '');
    for (var r = 0; r < n; r++) for (var c = 0; c < n; c++) {
      var d = document.createElement('div');
      d.className = 'cell';
      d.style.setProperty('--h', hue(map[regions[r][c]]).toFixed(1));
      d.dataset.i = r * n + c;
      d.innerHTML = glyphs;
      if (opts.interactive) {
        d.setAttribute('role', 'gridcell'); d.tabIndex = 0;
        d.setAttribute('aria-label', (r + 1) + ',' + (c + 1));
      }
      frag.appendChild(d); cells.push(d);
    }
    container.appendChild(frag);
    container.appendChild(overlay(regions, n));
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
