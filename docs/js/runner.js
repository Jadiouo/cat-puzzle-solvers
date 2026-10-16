/* Cat.Runner: owns one Web Worker; run() resolves with the solver result, cancel() kills the worker. */
(function () {
  function Runner() { this.w = null; this.cancelled = false; }
  Runner.prototype.run = function (params, onProgress) {
    var self = this;
    this.cancel();
    this.cancelled = false;
    return new Promise(function (resolve, reject) {
      var w = new Worker('js/worker.js');
      self.w = w;
      self._resolve = resolve;
      w.onmessage = function (e) {
        var m = e.data;
        if (m.type === 'progress') { if (onProgress) onProgress(m.nodes, m.ms); }
        else if (m.type === 'done') { w.terminate(); if (self.w === w) self.w = null; resolve({ result: m.result, trace: m.trace }); }
      };
      w.onerror = function (err) { w.terminate(); reject(new Error(err.message || 'worker error')); };
      w.postMessage(params);
    });
  };
  Runner.prototype.cancel = function () {
    if (this.w) { this.w.terminate(); this.w = null; this.cancelled = true; if (this._resolve) this._resolve(null); }
  };
  window.Cat = window.Cat || {};
  window.Cat.Runner = Runner;
})();
