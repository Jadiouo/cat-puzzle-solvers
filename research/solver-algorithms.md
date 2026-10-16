# Queens / Star Battle 求解演算法調查筆記（存取日 2026-10-15）

## 複雜度
- Parks（1 樹、色區連通、不可八方向相鄰）= Queens 規則。Minevich et al., arXiv:2411.02251（2024-11）證 (c,r)-tree Parks 判定問題 NP-complete，reduction 自 3SAT，且證明限制於連通色區仍成立；gadget 刻意讓可滿足時解唯一。https://arxiv.org/abs/2411.02251
  - 該文只給實驗計數（4x4 連通色區唯一解題數 11760），未見 #P / ASP 定理（本人只讀了 pdftotext 片段）。
- Star Battle 專屬 NP-complete 證明：查不到。Queens 專屬論文：查不到。
- 相關：queen graph 獨立集於 polyomino NP-complete 且 parsimonious（#P-complete），但無色區規則。https://arxiv.org/abs/2607.24668
- 綜述 Kendall/Parkes/Spoerer, ICGA J. 31(1), 2008（付費，未讀）。

## 實作
- ILP/PuLP+CBC，2x2 視窗 AMO 處理不相鄰；6x6~12x12 中位數 4~7 ms；唯一性=排除已知解再解；有生成器；MIT。https://github.com/aryanbpatel/queens-solver
- 純回溯（首色區逐格、刪衝突）無計時。https://mathspp.com/blog/beating-linkedin-queens-with-python
- Star Battle 傳播+MRV 分支+計數解 (sen-ltd)：https://dev.to/sendotltd/solving-star-battle-with-constraint-propagation-and-a-uniqueness-proof-2kbb （WebFetch 404，內容僅來自搜尋摘要）
- Knuth Dancing Links arXiv:cs/0011047（N-queens N<=18，含 secondary 概念）。
- AMO 編碼比較：arXiv:2005.06274；arXiv:1810.12975。
- 未確認：Norvig StarBattle.ipynb（429，未讀到內容）。

## 人類式
- Krazydad 進階教學（有命名規則）https://derp.krazydad.com/twonottouch/adv_tutorial/ ；puzzles.wiki 技巧 https://www.puzzles.wiki/wiki/Star_Battle ；qsolve（Rust 人類式）https://docs.rs/crate/qsolve/1.1.0/source/src/lib.rs
- 難度評分文獻：查不到。

## 題庫
- Krazydad 版權所有，「個人/教會/學校/醫院/機構免費複製」，商用需書面許可 https://krazydad.com/faq
- playqueensgame.com（非 LinkedIn 關聯，7~12 各 250 題，授權未查）https://www.playqueensgame.com/linkedin-queens
- LinkedIn 存檔/公開資料集：查不到。
