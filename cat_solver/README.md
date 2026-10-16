# 貓咪棋盤求解器

Python 3.11+、標準函式庫實作的 JSON 貓咪棋盤求解器與唯一關卡生成器。

## 規則與輸入

棋盤大小為 1..25；`regions` 是 N×N 字串矩陣，恰有 N 個不同 ID。每列、每欄、每個 region 各有一隻貓；貓不得八方向相鄰。只禁止相鄰格，遠距離斜線合法。Region ID 相同即屬同一區，即使格子不連通。

JSON 中座標為 0-based。`fixed_cats`、`blocked_cells` 是硬限制。`annotations.observed_cats` 和 `observed_crosses` 依政策選擇是否信任：

* `base`（預設）：忽略 observed 標記。
* `trust-cats`：另將 observed cats 固定。
* `trust-all`：另將 observed cats 固定、observed crosses 禁止。

合法但矛盾的限制會回報 `UNSAT`。`first` 不代表唯一；預設 `classify` 找到第二解即回報 `MULTIPLE`；`all` 列舉全部解。資源中止會回報 `TIMEOUT`、`NODE_LIMIT` 或 `CANCELLED`，不會將未完成搜尋冒報為無解或唯一解。

## 求解

```bash
python3 -m cat_solver solve tests/fixtures/sample10.json --mode classify --mark-policy base
python3 -m cat_solver solve tests/fixtures/sample10.json --mode classify --mark-policy trust-all
python3 -m cat_solver tests/fixtures/sample10.json --mode all --timeout-ms 5000
python3 -m cat_solver solve tests/fixtures/sample10.json --human
```

JSON 是預設輸出格式，結果明示 `"coordinate_base": 0`。`--human` 會以 1-based `(row,column)` 顯示。輸入 `-` 可從標準輸入讀取。退出碼：0 為正常判定（包括 UNSAT）、2 為輸入錯誤、3 為資源中止。

Level 46 轉錄資料的預期結果：`base`、`trust-cats` 均為唯一解 `[2,7,9,6,3,5,8,0,4,1]`；`trust-all` 為 UNSAT。此 fixture 是人工轉錄，尚未在遊戲內確認。

## 生成關卡

指定棋盤大小、難度和整數 seed。相同參數可重現完全相同的 JSON；輸出只含題目，可以直接交給 `solve`：

```bash
python3 -m cat_solver generate --size 10 --difficulty medium --seed 46 > level.json
python3 -m cat_solver solve level.json --mode classify
```

`easy` 會提供約半數答案位置作為 `fixed_cats`，`medium` 提供約四分之一，`hard` 不提供固定貓。生成器以隨機合法答案建立 region 鏈式分配，確保題目本身唯一，再以同一 solver 的 `classify` 和獨立 validator 驗證後才輸出。尺寸 2、3 在此規則下沒有任何合法答案，因此不會生成；可生成尺寸為 1、4..25。生成的區域是程式化棋盤，不代表遊戲實際關卡版型。

## 測試

```bash
python3 -m unittest discover -v
```

測試包含輸入與規則驗證、F1/F2、Level 46 三政策、資源限制、CLI、生成後再解，以及固定 seed 的隨機小棋盤與獨立排列 oracle 比對。

## 可玩視覺原型

直接用瀏覽器開啟 [`prototype/cat-game-prototype.html`](prototype/cat-game-prototype.html)，主線固定包含 100 關，並可重玩已開放關卡或另玩隨機唯一解題。每關開場都沒有預放貓；題目提供的禁用格以灰色斜紋顯示，玩家自己的排除叉以醒目紅底顯示。桌面可按住左鍵拖過空格標叉；觸控可點格放貓，或先選「點格排除」再點格標叉。

主線關卡以 4×4、5×5 為主；每個顏色區域恰有 N 格且四方向連通，答案經唯一解搜尋及獨立 validator 驗證。第 1–34 關提供 3 次提示，第 35–67 關提供 1 次，第 68–100 關不提供提示；遊戲仍保留答案檢查。關卡依 `10×完整 solver 節點數 + 2×N − 題目禁用格數 + 平均分支寬度` 遞增排列，分支寬度由同一搜尋樹逐節點量測；這是可驗證的搜尋成本代理，不等同人類體感。三種版面「星夜街機」、「探險手帳」、「旅程地圖」可用左右按鈕或方向鍵切換。

資料與生成器：

* [`prototype/campaign-100.json`](prototype/campaign-100.json)：固定種子建立的 100 個不同 puzzle fingerprint 關卡、目標解及唯一解證明。
* [`prototype/campaign-100-manifest.json`](prototype/campaign-100-manifest.json)：每關 fingerprint、求解狀態、節點數、難度分數與題目叉統計，並記錄候選去重數。
* `python3 prototype/build_campaign.py`：重建候選池；只有完整窮盡並證明唯一解、答案通過 validator、每色恰有 N 格且四方向連通、題目叉數不超過棋盤尺寸的關卡才會入選。生成器會更新以上兩份 JSON，並把同一 campaign inline 到 HTML，保持 double-click 自包含。

原型只在記憶體保存遊玩進度；刷新頁面會重新開始。它不呼叫網路服務，也不修改 Python production solver/generator。
