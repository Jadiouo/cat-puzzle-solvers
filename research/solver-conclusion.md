# 貓咪棋盤題：哪個求解演算法最好？（在本批題組與實作下）

日期：2026-10-16。資料：`bench/results/`（final_native_*、extra_*、unified_*）。
這是同語言（原生碼）實作之間的實測比較，不是演算法複雜度的證明。

## 結論

沒有單一演算法在所有題型都最好。實測支持兩條結論：

1. **一般題：回溯法＋Hall 匹配剪枝（native_match）最快。**
   - 做法：bitmask DFS（MRV＋forward check），每個節點再檢查兩件事：還沒放貓的色區能不能分到互不相同的空列，以及能不能分到互不相同的空欄（二分圖完美匹配）。只要有一邊做不到，就剪掉這個分支。
   - 隨機唯一解題（S5、S5b，N=11–16）：PAR2 0.3ms，SAT 1.2–1.6ms。
   - 隨機色區大盤（S3 N=25，20 題，其中 13 題無解，timeout 60s）：20 題全部解完，最慢 0.01s。沒有剪枝的三種 DFS 各有 4–5 題超時。
2. **本批找到的最壞題上，CDCL SAT（CaDiCaL／Glucose）最穩。**
   - 針對各方法爬山產生的刁難題（S6、S6x、S6m，N=10–18，全部是唯一解題），單題最大值：SAT 76–91ms，match 454ms，沒有剪枝的 DFS 0.8–1.1s。
   - 爬山能把 DFS 的節點數推高幾十倍到上千倍，SAT 的 conflicts 中位只推高 3–5 倍（個別題最高到 14–58 倍）。
   - 這不是最壞情況保證。刁難題全部是唯一解題，沒有做針對 UNSAT 的對抗，也沒有測鴿籠式的無解題。

**選擇規則：**
- 平常用 match，它在一般題上快 4–5 倍。
- 如果 N≥14 且題目可能被刻意刁難，或你想要一個不用自己設計剪枝就很穩的解法，用 CDCL（CaDiCaL）。
- 在本批資料裡，兩者最慢的一題都不到 0.5 秒。

## 最關鍵的一個發現

先前的結論「大盤 SAT 最好、DFS 會超時」，原因已經找到：**DFS 缺少計數（Hall）推理**，不是 DFS 這個框架不行。
- 加入 Hall 匹配剪枝後，S1–S4 classify 的超時從 8–9 題降到 0。
- S3 上，節點數的中位減少 3 倍，最多減少 3.4×10⁶ 倍。
- 推論：CDCL 靠子句學習，自己就能學到類似的推理，所以不需要人工設計剪枝也很穩。這一點沒有直接驗證。

## 證據摘要

| 題型 | match | 最好的無剪枝 DFS | CaDiCaL | CP-SAT |
|---|---|---|---|---|
| S5 隨機唯一解（PAR2） | **0.3ms** | 0.5ms（hybrid） | 1.6ms | 6.1ms |
| S6x 刁難 bitmask（N=16/18） | 33ms | 200ms（hybrid） | **14ms** | 42ms |
| S6x 刁難 hybrid | 16ms | 242ms（dlx） | 12ms（與 match 持平） | 47ms |
| S6x 刁難 SAT（sat／sat2） | **1.2／0.9ms** | 10／2.8ms | 5.9／3.4ms | 17／12ms |
| S6m 刁難 match（N=18） | 284ms | 394ms（dlx） | **43ms** | 145ms |
| 全部對抗題的最壞單題 | 454ms | 811ms | **91ms** | 353ms |
| S3 N=25 超時（60s） | **0/20** | 4/20 | **0/20** | **0/20** |

PAR2：超時的題以 2 倍 timeout 計。粗體代表該列差距 ≥1.5 倍的最好者。
時間是原生求解時間（core）：native 用 C++ 內部計時；SAT 用求解器呼叫的時間，不含 Python 建模。
表中前六列來自同一輪的統一比較（`unified_*.csv`，load 2–9），可以互相比較。

**S6m 上 match 對 CaDiCaL 的時間比**：

| N | 12 | 14 | 16 | 18 |
|---|---|---|---|---|
| match / CaDiCaL | 0.7 倍（match 較快） | 5.9 倍 | 2.5 倍 | 6.6 倍 |

SAT 的優勢在 N≥14 才出現，倍數不單調。每格只有 5 題，無法判斷差距是否隨 N 擴大。

**數全部解（count）：不比較。**
- 大 N 時所有方法都列舉不完。例如 S4-n14-00 有 15,620,263 個解，兩種 DFS 數出的結果一致。
- match 的 count 和其他方法是在不同輪、不同負載下跑的。PAR2 的名次主要反映超時數：match 26 題、dlx 34 題、CaDiCaL 41 題、CP-SAT 43 題。

## 正確性

- 獨立題目：正式評比 S1–S6 共 587 題，統一比較共 188 題（S5、S5b、S6、S6x、S6m）。另外 S6x 與 S6m 是新生成的 65 題，所以全部獨立題目共 652 題。
- 各批未超時的結果，對參考答案都是 0 MISMATCH、0 ERROR。各批的超時數：
  - 正式評比 5255 筆中 215 筆超時。
  - S3 N=25（60s）300 筆中 19 筆超時。
  - match 全題組 1761 筆中 26 筆超時。
  - 統一比較 1692 筆中 0 筆超時。
- 參考答案的來源：
  - 有獨立的 bench.reference 時，用它。
  - S3/S4 中沒有獨立參考的題，用 SAT＋CP-SAT 雙確認的類別（0／1／≥2）。
  - S5、S5b、S6、S6x、S6m：用 SAT＋CP-SAT 雙確認唯一解。
  - 因此參考答案有一部分來自受測的 SAT 求解器，不是完全獨立。

## 限制

- **盤面範圍**：唯一解題只做到 N=18，隨機色區做到 N=25。
- **樣本小**：每個（題組、N）格子只有 5 題，極值不穩。差距不到 1.5 倍的不排名。
- **沒有 UNSAT 對抗**：所有刁難題都是唯一解題。Hall 違反本質上是鴿籠式的無解推理，而 resolution 對鴿籠問題在理論上是指數級的。針對 SAT 的最壞情況，可能落在本批沒測到的無解題上。
- **對抗方法有限**：
  - 刁難題都用同一種局部爬山產生（一次改一格的顏色，每題 55–60 秒）。
  - SAT 的爬山目標是 cadical153 的 conflicts（sat2 是 4 種變數順序下的最大值），可能比 DFS 的節點數更難爬。
  - 所以「SAT 只能被推高 3–5 倍」不等於 SAT 本身難以刁難。
- **實作依賴**：
  - hybrid 每個節點約 1.5µs，這是這份實作每個節點都重算傳播的成本；改成增量版可能更快。
  - 隨機重啟版（native_rr、match_rr）在這類題上反而變差，例如 S6m 上 match_rr 約 2.9s。
  - SAT 只測了一種主要建模方式（列／欄／區 exactly-one，加上相鄰禁止）。5 種 AMO 編碼只在 S3 N=25 上比過：都沒有超時，但最大值差到 50 倍（pairwise 0.55s，ladder 0.011s）。
- **雜訊**：正式評比時 load 10–44，統一比較時 load 2–9。不同輪的時間不可直接比；節點數和 conflicts 不受負載影響。

## 檔案

- 求解器：`native/cat_native.cpp`（bitmask／hybrid／dlx／match／rr／match_rr），`bench/solver_sat.py`（SAT 編碼與求解器變體、CP-SAT）
- 題組：`bench/suites/S1–S6.json`、`S6x.json`、`S6m.json`；生成器 `bench/build_*.py`
- 結果：`bench/results/final_native_tables.md`（正式評比）、`extra_S3n25_t60.csv`、`extra_match_*.csv`、`unified_*.csv`、`s6x_climb.md`
- 腳本：`bench/run_final_native.sh`、`run_final_native_resume.sh`、`run_extra_s3n25.sh`、`run_extra_match.sh`、`run_unified.sh`
