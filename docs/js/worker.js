/* Web Worker: runs one solve and streams progress. Cancellation = the page terminates this worker. */
importScripts('solver.js');
self.onmessage = function (e) {
  var m = e.data;
  var opts = { algo: m.algo, limit: m.limit, maxNodes: m.maxNodes, progressMs: 80,
               onProgress: function (nodes, ms) { self.postMessage({ type: 'progress', nodes: nodes, ms: ms }); } };
  if (m.traceCap) opts.trace = { events: [], cap: m.traceCap };
  var r = self.CatSolver.solve(m.regions, m.n, opts);
  var trace = opts.trace ? Int32Array.from(opts.trace.events) : null;
  self.postMessage({ type: 'done', result: r, trace: trace }, trace ? [trace.buffer] : []);
};
