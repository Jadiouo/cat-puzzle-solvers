(function () {
  var C = window.Cat;
  function showTab(name) {
    document.querySelectorAll('.tabs button').forEach(function (b) { b.setAttribute('aria-selected', String(b.dataset.tab === name)); });
    ['play', 'race', 'findings'].forEach(function (n) { document.getElementById('tab-' + n).hidden = n !== name; });
    document.querySelector('.hero').hidden = name !== 'play';
    try { history.replaceState(null, '', '#' + name); } catch (e) {}
  }
  C.showTab = showTab;

  function theme(mode) {
    document.documentElement.setAttribute('data-theme', mode);
    try { localStorage.setItem('cat-theme', mode); } catch (e) {}
  }
  function isDark() {
    var m = document.documentElement.getAttribute('data-theme');
    return m === 'dark' || (m === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  }

  document.querySelectorAll('.tabs button').forEach(function (b) { b.onclick = function () { showTab(b.dataset.tab); }; });
  document.getElementById('btnTheme').onclick = function () { theme(isDark() ? 'light' : 'dark'); };
  document.getElementById('btnLang').onclick = function () { C.setLang(C.getLang() === 'en' ? 'zh' : 'en'); };
  document.getElementById('readmeLink').href = (window.CAT_CONFIG || {}).README_URL || '#';
  try { var saved = localStorage.getItem('cat-theme'); if (saved) theme(saved); } catch (e) {}

  C.applyI18n();
  document.addEventListener('langchange', C.applyI18n);
  C.play.init().then(C.race.init).then(function () {
    C.applyI18n();
    var h = (location.hash || '').slice(1);
    if (h === 'race' || h === 'findings' || h === 'play') showTab(h);
  }).catch(function (e) { document.getElementById('playMsg').textContent = 'Failed to load data: ' + e.message; });
})();
