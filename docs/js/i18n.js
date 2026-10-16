/* i18n string table. t(key, {vars}) ; elements with data-i18n are re-rendered on language change. */
(function () {
  var S = {
    en: {
      title: 'Cat Board Lab', tabPlay: 'Play', tabRace: 'Race', tabFindings: 'Findings',
      heroTitle: 'Place one cat per row, column and colour region.',
      heroText: 'An N×N board has N colour regions. Every row, column and region holds exactly one cat, and no two cats touch, not even diagonally. Play a puzzle, then watch two solvers fight over the same board.',
      size: 'Size', difficulty: 'Difficulty', newPuzzle: 'New puzzle', any: 'Any', big: 'Big boards (N=11–16)',
      lvT3: 'Easy', lvT3b: 'Medium', lvT4: 'Hard', lvT5a: 'Expert', lvT5b: 'Master', lvbig: 'Large',
      tapHelp: 'Tap a cell: empty, then X, then cat. Drag across empty cells to fill them with X (across X to clear). Gold frame = correct, locked for good; red frame = wrong guess (the cat is removed, the cell stays red as a reminder). Ctrl/Cmd+Z undoes.',
      undo: 'Undo',
      hint: 'Hint', reset: 'Reset', raceThis: 'Race this puzzle',
      rulesTitle: 'Rules', rule1: 'Exactly one cat in every row.', rule2: 'Exactly one cat in every column.',
      rule3: 'Exactly one cat in every colour region.', rule4: 'Cats never touch, diagonals included.',
      playTitle: '{n}×{n} · {level} · {id}',
      msgStart: 'Find all {n} cats.', msgGood: 'Correct, locked in gold. {left} cat(s) to go.', msgBad: 'Wrong: no cat here. The cell is marked red.',
      mistakes: 'Mistakes {n}', hintsUsed: 'Hints {n}',
      msgHint: 'Hint: a gold cat was placed at row {r}, column {c}.', msgNoPuzzle: 'No puzzle for this filter.',
      msgSolved: 'Time {time}, mistakes {mistakes}, hints {hints}.', solvedTitle: 'Solved!',
      raceIntro: 'Same board, same branching order, two solvers. Both are bitmask backtracking; the second one also asks, at every node, whether the unplaced colour regions can still be matched to distinct free rows and to distinct free columns (Hall\'s condition). If not, it prunes.',
      puzzle: 'Puzzle', nodeCap: 'Node cap', mode: 'Mode', modeLive: 'Live race', modeAnim: 'Step-by-step (N ≤ 10)',
      run: 'Run race', cancel: 'Cancel', algoBitmask: 'Bitmask DFS', algoMatch: 'DFS + Hall matching',
      nodes: 'Nodes', time: 'Time', play: 'Play', pause: 'Pause', step: 'Step', restart: 'Restart', speed: 'Speed',
      lgPlace: 'cat placed', lgPrune: 'pruned by Hall check', lgDead: 'dead end',
      grpHall: 'Plain DFS drowns, matching does not (random regions, N=25)', grpHard: 'Hard for both (adversarial, N=14–18)',
      grpAnim: 'Small boards for step-by-step (N ≤ 10)', grpPlay: 'Current Play puzzle',
      optPlay: 'The puzzle from the Play tab ({n}×{n})',
      puzName: '{id} · {n}×{n}',
      stIdle: 'ready', stRunning: 'running…', stCancelled: 'cancelled', stNone: 'no solution', stUnique: 'unique solution', stMulti: '2+ solutions',
      stCap: 'exceeded {cap} nodes, not finished',
      sumBoth: 'Bitmask DFS needed {a} nodes; Hall matching needed {b}: {ratio} fewer nodes ({ta} vs {tb}).',
      sumCapped: 'Bitmask DFS exceeded {cap} nodes without finishing. Hall matching finished in {b} nodes ({tb}): at least {ratio} fewer nodes.',
      sumBothCapped: 'Neither solver finished within {cap} nodes. Raise the node cap or pick another puzzle.',
      sumMatchOnlyCapped: 'Hall matching exceeded {cap} nodes; bitmask DFS finished in {a} nodes.',
      sumSame: 'Both needed {a} nodes.',
      animTruncated: ' (animation shows the first {n} steps only)',
      animInfo: 'step {i} / {n}', animDone: 'finished',
      noteNoAnim: 'Step-by-step needs N ≤ 10; running a live race instead.',
      noteCap: 'Browser speed is a few million nodes per second; the cap stops runaway searches.',
      refTitle: 'C++ reference (native build, benchmark run): ',
      refLine: '{status}, {nodes} nodes, {ms} ms', refSolved: 'solution found',
      refTimeout: 'timed out at 60 s after {nodes} nodes',
      ratioNA: 'n/a',
      findTitle: 'What the benchmark found',
      find1: 'On ordinary puzzles, backtracking with Hall-matching pruning was the fastest method tested: on random unique-solution boards (N=11–16) its PAR2 was 0.3 ms against 1.2–1.6 ms for SAT, and on random-region N=25 boards it solved all 20 puzzles (slowest 0.01 s) while the three plain DFS variants each timed out on 4–5 of 20 at 60 s.',
      find2: 'On the hardest puzzles found by hill-climbing (N=10–18, all unique-solution), CDCL SAT was the steadiest: worst single puzzle 76–91 ms, against 454 ms for Hall-matching DFS and 0.8–1.1 s for plain DFS. This is not a worst-case guarantee: no unsatisfiable adversarial puzzles were tried.',
      find3: 'SAT is not in this demo because the solvers behind those numbers (CaDiCaL, Glucose, CP-SAT) are native libraries driven from Python; this page is plain static JavaScript with no build step and no dependencies.',
      readmeLink: 'Read the full write-up in the README',
      footer: 'Solver code runs entirely in your browser, in a Web Worker. Node counts match the C++ implementation exactly.',
      langBtn: '中文'
    },
    zh: {
      title: '貓咪棋盤實驗室', tabPlay: '試玩', tabRace: '對決', tabFindings: '研究發現',
      heroTitle: '每列、每欄、每個色區各放一隻貓。',
      heroText: 'N×N 的盤面有 N 個色區。每列、每欄、每個色區都恰好一隻貓，而且貓不能相鄰，斜對角也不行。先自己玩一題，再看兩種求解器在同一題上較勁。',
      size: '大小', difficulty: '難度', newPuzzle: '換一題', any: '不限', big: '大盤面（N=11–16）',
      lvT3: '簡單', lvT3b: '中等', lvT4: '困難', lvT5a: '專家', lvT5b: '大師', lvbig: '大盤',
      tapHelp: '點格子：空白 → X → 貓。從空格拖曳可一路標 X（從 X 拖曳則清除）。金框＝正確，永久鎖定；紅框＝猜錯（貓會消失，格子留紅框提醒）。Ctrl/Cmd+Z 復原。',
      undo: '復原',
      hint: '提示', reset: '重來', raceThis: '用這題對決',
      rulesTitle: '規則', rule1: '每一列恰好一隻貓。', rule2: '每一欄恰好一隻貓。',
      rule3: '每個色區恰好一隻貓。', rule4: '貓不能相鄰，斜對角也不行。',
      playTitle: '{n}×{n} · {level} · {id}',
      msgStart: '找出全部 {n} 隻貓。', msgGood: '答對了，金框鎖定。還差 {left} 隻。', msgBad: '錯了，這格沒有貓，已標成紅框。',
      mistakes: '錯誤 {n}', hintsUsed: '提示 {n}',
      msgHint: '提示：已在第 {r} 列、第 {c} 欄放上金色的貓。', msgNoPuzzle: '這個條件下沒有題目。',
      msgSolved: '用時 {time}，錯誤 {mistakes} 次，提示 {hints} 次。', solvedTitle: '完成！',
      raceIntro: '同一個盤面、同樣的分支順序、兩種求解器。兩者都是位元遮罩回溯法；第二種在每個節點多問一件事：還沒放貓的色區，能不能分到互不相同的空列，也能分到互不相同的空欄（Hall 條件）。做不到就剪枝。',
      puzzle: '題目', nodeCap: '節點上限', mode: '模式', modeLive: '即時對決', modeAnim: '逐步動畫（N ≤ 10）',
      run: '開始對決', cancel: '取消', algoBitmask: '位元遮罩回溯法', algoMatch: '回溯法＋Hall 匹配',
      nodes: '節點數', time: '時間', play: '播放', pause: '暫停', step: '單步', restart: '重播', speed: '速度',
      lgPlace: '放貓', lgPrune: '被 Hall 檢查剪掉', lgDead: '死路',
      grpHall: '一般回溯法卡死，匹配剪枝不會（隨機色區，N=25）', grpHard: '兩者都吃力（對抗題，N=14–18）',
      grpAnim: '小盤面，適合逐步動畫（N ≤ 10）', grpPlay: '目前試玩的題',
      optPlay: '試玩頁的這一題（{n}×{n}）',
      puzName: '{id} · {n}×{n}',
      stIdle: '待命', stRunning: '執行中…', stCancelled: '已取消', stNone: '無解', stUnique: '唯一解', stMulti: '兩個以上的解',
      stCap: '超過 {cap} 步仍未完成',
      sumBoth: '位元遮罩回溯法用了 {a} 個節點；Hall 匹配只要 {b} 個：少了 {ratio}（{ta} 對 {tb}）。',
      sumCapped: '位元遮罩回溯法超過 {cap} 個節點仍未完成。Hall 匹配用 {b} 個節點完成（{tb}）：節點數至少少了 {ratio}。',
      sumBothCapped: '兩者都在 {cap} 個節點內沒有完成。請調高節點上限或換一題。',
      sumMatchOnlyCapped: 'Hall 匹配超過 {cap} 個節點；位元遮罩回溯法用 {a} 個節點完成。',
      sumSame: '兩者都用了 {a} 個節點。',
      animTruncated: '（動畫只顯示前 {n} 步）',
      animInfo: '第 {i} / {n} 步', animDone: '結束',
      noteNoAnim: '逐步動畫需要 N ≤ 10；改用即時對決。',
      noteCap: '瀏覽器每秒大約處理數百萬個節點；節點上限用來擋掉跑不完的搜尋。',
      refTitle: 'C++ 參考值（原生版，評比時的結果）：',
      refLine: '{status}，{nodes} 個節點，{ms} ms', refSolved: '找到解',
      refTimeout: '60 秒逾時，已跑 {nodes} 個節點',
      ratioNA: '無法計算',
      findTitle: '評比的發現',
      find1: '一般題上，回溯法加 Hall 匹配剪枝是測到最快的方法：隨機唯一解題（N=11–16）的 PAR2 是 0.3 ms，SAT 是 1.2–1.6 ms；隨機色區的 N=25 題 20 題全部解完（最慢 0.01 秒），沒有剪枝的三種 DFS 在 60 秒限制下各有 4–5 題超時。',
      find2: '用爬山法找出的最難題（N=10–18，全部是唯一解題）上，CDCL SAT 最穩：單題最慢 76–91 ms，Hall 匹配 DFS 是 454 ms，一般 DFS 是 0.8–1.1 秒。這不是最壞情況保證：我們沒有試過針對無解題的對抗。',
      find3: '這個頁面沒有 SAT，因為那些數字背後的求解器（CaDiCaL、Glucose、CP-SAT）是用 Python 呼叫的原生函式庫；這個頁面是純靜態 JavaScript，沒有建置步驟，也沒有依賴套件。',
      readmeLink: '到 README 看完整說明',
      footer: '求解程式完全在你的瀏覽器裡、在 Web Worker 中執行。節點數和 C++ 版逐題相同。',
      langBtn: 'English'
    }
  };
  var lang = 'en';
  try { var saved = localStorage.getItem('cat-lang'); if (saved && S[saved]) lang = saved; else if ((navigator.language || '').toLowerCase().indexOf('zh') === 0) lang = 'zh'; } catch (e) {}

  function t(key, vars) {
    var s = (S[lang] && S[lang][key]); if (s === undefined) s = S.en[key]; if (s === undefined) return key;
    if (vars) s = s.replace(/\{(\w+)\}/g, function (_, k) { return vars[k] === undefined ? '' : vars[k]; });
    if (lang === 'en') s = s.replace(/(^|[^\d,.])1 nodes\b/g, '$11 node');   // singular after filling in a count of 1
    return s;
  }
  function apply() {
    document.documentElement.lang = lang === 'zh' ? 'zh-Hant' : 'en';
    var els = document.querySelectorAll('[data-i18n]');
    for (var i = 0; i < els.length; i++) els[i].textContent = t(els[i].getAttribute('data-i18n'));
    document.getElementById('btnLang').textContent = t('langBtn');
  }
  function setLang(l) { lang = l; try { localStorage.setItem('cat-lang', l); } catch (e) {} apply(); document.dispatchEvent(new CustomEvent('langchange')); }
  window.Cat = window.Cat || {};
  window.Cat.t = t; window.Cat.applyI18n = apply; window.Cat.setLang = setLang; window.Cat.getLang = function () { return lang; };
})();
