# 貓咪棋盤求解器（cat_solver）

> **English summary:** the original pure-Python (standard library only) CLI solver and unique-puzzle generator. `python3 -m cat_solver solve <puzzle.json>` classifies a puzzle as UNSAT / unique / multiple; `python3 -m cat_solver generate --size 10 --seed 1` makes a reproducible unique-solution puzzle. The benchmarked native solvers live in `native/` and `bench/`; this package is the readable reference implementation.

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

範例 `tests/fixtures/sample10.json`（由 `tests/fixtures/make_sample10.py` 生成）的預期結果：`base`、`trust-cats` 均為唯一解 `[6,1,5,0,3,7,2,8,4,9]`；`trust-all` 因為 observed crosses 擋住答案而為 UNSAT。

## 生成關卡

指定棋盤大小、難度和整數 seed。相同參數可重現完全相同的 JSON；輸出只含題目，可以直接交給 `solve`：

```bash
python3 -m cat_solver generate --size 10 --difficulty medium --seed 1 > level.json
python3 -m cat_solver solve level.json --mode classify
```

`easy` 會提供約半數答案位置作為 `fixed_cats`，`medium` 提供約四分之一，`hard` 不提供固定貓。生成器以隨機合法答案建立 region 鏈式分配，確保題目本身唯一，再以同一 solver 的 `classify` 和獨立 validator 驗證後才輸出。尺寸 2、3 在此規則下沒有任何合法答案，因此不會生成；可生成尺寸為 1、4..25。生成的區域是程式化棋盤，形狀不追求美觀；較好看的分級題目見 `levelgen/`。

## 測試

```bash
python3 -m unittest discover -v
```

測試包含輸入與規則驗證、F1/F2、sample10 三政策、資源限制、CLI、生成後再解，以及固定 seed 的隨機小棋盤與獨立排列 oracle 比對。

## 早期遊戲原型

專案初期做過兩個瀏覽器遊戲原型，與求解器研究無關，已移到 [`archive/`](../archive/README.md)。目前的互動 demo 在 `docs/`。
