"""Build the final comparison tables (markdown) from bench/results/final_S*.json + the SAT double
confirmation in bench/suites/S3_S4_satref.json.
  .venv/bin/python -B -m bench.make_table  > bench/results/final_tables.md
Import costs are measured once and cached in bench/results/import_cost.json (--remeasure to redo).

Metrics
  PAR2    mean over ALL puzzles of the cell; a timeout counts 2 x timeout. Unlike the median of finished
          puzzles it cannot be flattered by timing out on the hard ones.
  median  median over the puzzles the method FINISHED, shown with (finished/total).
"""
import json
import math
import os
import statistics
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "results")
SOLVERS = ["cat_solver", "bitmask", "hybrid", "dlx", "sat_cadical153_seq", "cpsat_w1"]
ANSWERED = ("OK", "NOREF", "MISMATCH", "INCOMPLETE")
CLASS_NAME = {0: "0 解", 1: "唯一解", 2: ">=2 解"}
IMPORT_STMT = {
    "cat_solver": "import bench.solvers; from cat_solver import SolveOptions, parse_puzzle, solve",
    "bitmask": "import bench.solvers",
    "hybrid": "import bench.solvers",
    "dlx": "import bench.solvers",
    "sat_cadical153_seq": "import bench.solvers; import pysat.solvers, pysat.card",
    "cpsat_w1": "import bench.solvers; from ortools.sat.python import cp_model",
}


def load():
    rows, metas = [], {}
    for s in ("S1", "S2", "S3", "S4"):
        d = json.load(open(os.path.join(R, f"final_{s}.json")))
        rows += d["rows"]
        metas[s] = d["meta"]
    sat = json.load(open(os.path.join(HERE, "suites", "S3_S4_satref.json")))["puzzles"]
    return rows, metas, sat


def enrich(rows, sat, timeout):
    """add: cls (0/1/2), kind (indep | sat2), t (PAR2 time), basis (X/Y/Z/T/-), conflict"""
    for r in rows:
        r["elapsed_s"] = float(r["elapsed_s"])
        indep = str(r["ref_source"]).startswith("bench.reference") and r["ref_count"] not in (None, "")
        if indep:
            r["cls"], r["kind"] = min(int(r["ref_count"]), 2), "indep"
        else:
            s = sat[r["id"]]
            assert s["confirmed"], r["id"]
            r["cls"], r["kind"] = s["class"], "sat2"
        r["timed_out"] = r["verdict"] == "TIMEOUT"
        r["t"] = 2 * timeout if r["timed_out"] else r["elapsed_s"]
        r["conflict"] = False
        if r["timed_out"]:
            r["basis"] = "T"
            continue
        got = None if r["count"] in (None, "") else int(r["count"])
        if r["verdict"] == "MISMATCH" or got is None:
            r["conflict"] = True
            r["basis"] = "!"
            continue
        if min(got, 2) != r["cls"]:
            r["conflict"] = True
            r["basis"] = "!"
        elif r["kind"] == "indep":
            r["basis"] = "X"
        elif r["mode"] == "count" and r["cls"] == 2:
            r["basis"] = "Z"      # SAT confirms ">= 2"; the exact count is only method-vs-method
        else:
            r["basis"] = "Y"
    return rows


def sel(rows, **kw):
    return [r for r in rows if all(r[k] == v for k, v in kw.items())]


def cell(g):
    """PAR2 / median (finished/total)"""
    if not g:
        return "n/a"
    par2 = sum(r["t"] for r in g) / len(g)
    done = [r["elapsed_s"] for r in g if not r["timed_out"]]
    med = f"{statistics.median(done):.4f}" if done else "-"
    return f"{par2:.4f} / {med} ({len(done)}/{len(g)})"


def par2(g):
    return sum(r["t"] for r in g) / len(g) if g else None


def best_cells(groups):
    """groups: solver -> rows. returns dict solver -> rendered cell with the best PAR2 in bold"""
    vals = {sv: par2(g) for sv, g in groups.items() if g}
    cells = {sv: cell(g) for sv, g in groups.items()}
    if vals and len(set(vals.values())) > 1:
        b = min(vals, key=lambda s: vals[s])
        cells[b] = f"**{cells[b]}**"
    return cells


def table(rows, mode, keyfn, keys, label, extra=None):
    out = ["| " + label + " | " + " | ".join(SOLVERS) + " |", "|---|" + "---|" * len(SOLVERS)]
    winners = {}
    for k in keys:
        base = [r for r in rows if r["mode"] == mode and keyfn(r) == k]
        if extra:
            base = [r for r in base if extra(r)]
        if not base:
            continue
        groups = {sv: [r for r in base if r["solver"] == sv] for sv in SOLVERS}
        cells = best_cells(groups)
        n = len(groups[SOLVERS[0]])
        vv = {s_: par2(groups[s_]) for s_ in SOLVERS}
        winners[k] = min(SOLVERS, key=vv.get) if len(set(vv.values())) > 1 else "無(全部逾時)"
        out.append(f"| {k[0] if isinstance(k, tuple) else k}{'' if not isinstance(k, tuple) else ' ' + ' '.join(map(str, k[1:]))} ({n}) | "
                   + " | ".join(cells[s] for s in SOLVERS) + " |")
    return out, winners


def measure_import(remeasure):
    p = os.path.join(R, "import_cost.json")
    if os.path.exists(p) and not remeasure:
        return json.load(open(p))
    res = {}
    root = os.path.dirname(HERE)
    for sv in ["(interpreter only)"] + SOLVERS:
        stmt = "pass" if sv.startswith("(") else IMPORT_STMT[sv]
        ts = []
        for _ in range(7):
            cp = subprocess.run([sys.executable, "-B", "-c",
                                 f"import time;t=time.perf_counter();{stmt};print(time.perf_counter()-t)"],
                                capture_output=True, text=True, cwd=root)
            ts.append(float(cp.stdout.strip()))
        res[sv] = statistics.median(ts)
    json.dump(res, open(p, "w"), indent=1)
    return res


def main():
    remeasure = "--remeasure" in sys.argv
    rows, metas, sat = load()
    timeout = metas["S3"]["timeout_s"]
    enrich(rows, sat, timeout)
    imp = measure_import(remeasure)
    out = []
    P = out.append

    # ---- 0. answer provenance --------------------------------------------------------------
    ans = [r for r in rows if not r["timed_out"]]
    basis = {b: sum(r["basis"] == b for r in ans) for b in "XYZ!"}
    confl = [r for r in rows if r["conflict"]]
    P(f"total rows {len(rows)}; MISMATCH {sum(r['verdict'] == 'MISMATCH' for r in rows)}; "
      f"ERROR {sum(r['verdict'] == 'ERROR' for r in rows)}; TIMEOUT {sum(r['timed_out'] for r in rows)}; "
      f"verdict NOREF in raw csv {sum(r['verdict'] == 'NOREF' for r in rows)}\n")
    P("## 0. 答案依據（每一筆「有答案」的 row 只歸一類）\n")
    P(f"- X = {basis['X']} 筆：與獨立參考（bench.reference，不共用任何求解器程式碼）一致")
    P(f"- Y = {basis['Y']} 筆：原本無獨立參考，改以 SAT 雙確認（CaDiCaL 1.5.3 與 CP-SAT 兩個獨立實作"
      f"皆同意，且解經 bench/check.py 驗證）的 0 / 唯一 / >=2 類別為準，答案的類別一致")
    P(f"- Z = {basis['Z']} 筆：count 模式、題目為 >=2 解——SAT 只確認「>=2」，"
      f"精確解數僅「方法間一致」（見表 5）")
    P(f"- 與參考矛盾 / 無答案 = {basis['!']} 筆" + ("：" + ", ".join(f"{r['id']}/{r['solver']}/{r['mode']}" for r in confl) if confl else ""))
    P(f"- 逾時（不算答案）= {sum(r['timed_out'] for r in rows)} 筆；以上四類加總 "
      f"{sum(basis.values())} + 逾時 {sum(r['timed_out'] for r in rows)} = {len(rows)}\n")
    P("計時口徑：除非特別標示，時間 =「不含 import」（worker 內 perf_counter 包住 solve()，"
      "含 build，不含直譯器啟動與函式庫 import）；表 3 另列「含 import」口徑（每題獨立程序的情境）。"
      f"逾時測量上限 {timeout:g}s，PAR2 把逾時記為 {2 * timeout:g}s。"
      "bench/results/final_*.csv 的 elapsed 為三次重複的中位數；任一次逾時即整筆記為 TIMEOUT。\n")

    suiteN = sorted({(r["suite"], r["n"]) for r in rows})
    suiteN = sorted(suiteN, key=lambda k: (k[0], int(k[1])))
    for r in rows:
        r["n"] = int(r["n"])
    suiteN = sorted({(r["suite"], r["n"]) for r in rows})

    # ---- 1. per suite/N ------------------------------------------------------------------
    P("## 1. 各題組 / N（格式：PAR2 / 完成題中位數 (完成題數/總題數)；粗體 = 該列 PAR2 最小）\n")
    winners1 = {}
    for mode in ("classify", "count"):
        P(f"### 1.{1 if mode == 'classify' else 2} {mode}（不含 import，秒）\n")
        t, w = table(rows, mode, lambda r: (r["suite"], r["n"]), suiteN, "suite N (#)")
        winners1[mode] = w
        out += t
        P("")

    # ---- 2. by class -----------------------------------------------------------------------
    P("## 2. 依參考／SAT 雙確認解數分三類（0 解 / 唯一解 / >=2 解）\n")
    P("類別來源：獨立參考（bench.reference）；無獨立參考的題以 SAT 雙確認。"
      "同一格內是同 suite、同 N、同類別的題目。\n")
    winners2 = {}
    for mode in ("classify", "count"):
        for cls in (0, 1, 2):
            sub = [r for r in rows if r["cls"] == cls and r["mode"] == mode]
            keys = sorted({(r["suite"], r["n"]) for r in sub})
            P(f"### 2.{cls + 1}{'a' if mode == 'classify' else 'b'} {CLASS_NAME[cls]} - {mode}\n")
            t, w = table(rows, mode, lambda r: (r["suite"], r["n"]), keys, "suite N (#)",
                         extra=lambda r, c=cls: r["cls"] == c)
            winners2[(mode, cls)] = w
            out += t
            P("")

    # ---- 3. import --------------------------------------------------------------------------
    P("## 3. 兩種計時口徑：不含 import vs 含 import（每題獨立程序）\n")
    P(f"含 import = 不含 import 的時間 + 該方法的一次性 import 成本（下列中位數，7 次新直譯器；"
      f"測的是本評比框架實際載入的內容：`import bench.solvers` 加上方法自己的函式庫；直譯器本身啟動不含，空程式約 {imp['(interpreter only)']:.3f}s）。"
      "逾時仍記 2x 上限。\n")
    P("| 項目 | " + " | ".join(SOLVERS) + " |")
    P("|---|" + "---|" * len(SOLVERS))
    P("| import 成本 (s) | " + " | ".join(f"{imp[s]:.3f}" for s in SOLVERS) + " |")
    P("")
    for mode in ("classify", "count"):
        P(f"### 3.{1 if mode == 'classify' else 2} {mode} 的 PAR2（秒）：不含 import / 含 import；粗體 = 該口徑最小\n")
        P("| suite N (#) | " + " | ".join(SOLVERS) + " |")
        P("|---|" + "---|" * len(SOLVERS))
        for k in suiteN:
            base = [r for r in rows if r["mode"] == mode and (r["suite"], r["n"]) == k]
            g = {sv: [r for r in base if r["solver"] == sv] for sv in SOLVERS}
            ex = {sv: par2(g[sv]) for sv in SOLVERS}
            inc = {sv: sum(r["t"] if r["timed_out"] else r["t"] + imp[sv] for r in g[sv]) / len(g[sv]) for sv in SOLVERS}
            bx, bi = min(ex, key=ex.get), min(inc, key=inc.get)
            if len(set(ex.values())) == 1:
                bx = bi = None
            cs = []
            for sv in SOLVERS:
                a, b = f"{ex[sv]:.4f}", f"{inc[sv]:.4f}"
                cs.append(f"{'**' + a + '**' if sv == bx else a} / {'**' + b + '**' if sv == bi else b}")
            P(f"| {k[0]} N={k[1]} ({len(g[SOLVERS[0]])}) | " + " | ".join(cs) + " |")
        P("")

    # ---- 4. PAR2 ranking ------------------------------------------------------------------------
    P("## 4. PAR2 排名（所有題目等權平均；越小越好）\n")
    hard = lambda r: (r["suite"] == "S3" and r["n"] >= 15) or (r["suite"] == "S4" and r["n"] >= 12)
    P("| 範圍 | mode | " + " | ".join(SOLVERS) + " |")
    P("|---|---|" + "---|" * len(SOLVERS))
    rank = {}
    for name, f in (("全部題目", lambda r: True), ("困難子集 (S3 N>=15, S4 N>=12)", hard)):
        for mode in ("classify", "count"):
            g = {sv: [r for r in rows if r["solver"] == sv and r["mode"] == mode and f(r)] for sv in SOLVERS}
            v = {sv: par2(g[sv]) for sv in SOLVERS}
            order = sorted(SOLVERS, key=v.get)
            rank[(name, mode)] = order
            P(f"| {name} | {mode} | " + " | ".join(f"{v[s]:.3f} (#{order.index(s) + 1}, 逾時 {sum(r['timed_out'] for r in g[s])}/{len(g[s])})" for s in SOLVERS) + " |")
    P("\n含 import 口徑（每題獨立程序）的困難子集 PAR2：")
    for mode in ("classify", "count"):
        g = {sv: [r for r in rows if r["solver"] == sv and r["mode"] == mode and hard(r)] for sv in SOLVERS}
        v = {sv: sum(r["t"] if r["timed_out"] else r["t"] + imp[sv] for r in g[sv]) / len(g[sv]) for sv in SOLVERS}
        P(f"- {mode}: " + ", ".join(f"{s} {v[s]:.3f}" for s in sorted(SOLVERS, key=v.get)))
    P("")

    # ---- 5. NOREF double confirmation ------------------------------------------------------------
    P("## 5. 無獨立參考的題：SAT 雙確認（bench/suites/S3_S4_satref.json）\n")
    ids = sorted(sat, key=lambda i: (sat[i]["suite"], sat[i]["n"], i))
    why = {"no_reference": "參考未知（bench.reference 與 cat_solver 皆逾時）", "cat_solver_only": "參考僅來自 cat_solver（NOT independent）"}
    P(f"- 共 {len(ids)} 題；雙確認成功 {sum(sat[i]['confirmed'] for i in ids)} 題（CaDiCaL 與 CP-SAT 類別相同、解經 check.py 驗證合法）")
    for w in why:
        for c in (0, 1, 2):
            n_ = [i for i in ids if sat[i]["why"] == w and sat[i]["class"] == c]
            if n_:
                P(f"  - {why[w]}，確認為 {CLASS_NAME[c]}：{len(n_)} 題")
    cs_old = [i for i in ids if sat[i]["why"] == "cat_solver_only"]
    agree_old = [i for i in cs_old if min(sat[i]["old_ref_count"], 2) == sat[i]["class"]]
    P(f"- 原 ref 來自 cat_solver 的 {len(cs_old)} 題，與 SAT 雙確認類別一致 {len(agree_old)} 題"
      + ("" if len(agree_old) == len(cs_old) else "，**不一致：" + ", ".join(sorted(set(cs_old) - set(agree_old))) + "**"))
    nr_rows = [r for r in rows if r["id"] in sat]
    nr_ans = [r for r in nr_rows if not r["timed_out"]]
    bad = [r for r in nr_ans if r["conflict"]]
    P(f"- 這些題上共 {len(nr_rows)} 筆 row，其中 {len(nr_ans)} 筆有答案：與 SAT 類別一致 {len(nr_ans) - len(bad)}，"
      f"**矛盾 {len(bad)}**" + ("：" + ", ".join(f"{r['id']}/{r['solver']}/{r['mode']}" for r in bad) if bad else "（沒有任何方法的答案被推翻）"))
    zr = [r for r in rows if r["basis"] == "Z"]
    P(f"- count 模式下「SAT 只能確認 >=2、精確解數沒有獨立來源」的 row（Z 類）共 {len(zr)} 筆："
      "這些題（S3 N=20/25、S4 N>=14 中無獨立參考者）在 count 模式下所有方法都逾時，沒有任何方法回報精確解數，"
      "所以也沒有精確解數可以被誤信；它們只在 classify 模式有答案（0 解 / >=2 解，已 SAT 雙確認）")
    P("")
    P("| id | 為何無獨立參考 | CaDiCaL | CP-SAT | 類別 | 驗證合法 |")
    P("|---|---|---|---|---|---|")
    for i in ids:
        s = sat[i]
        P(f"| {i} | {'參考未知' if s['why'] == 'no_reference' else 'ref=cat_solver'} | {s['cadical153']['class']} "
          f"| {s['cpsat']['class']} | {s['class']} | {'是' if s['confirmed'] else '否'} |")
    P("")

    # ---- 6. dlx vs bitmask nodes -----------------------------------------------------------------
    P("## 6. DLX vs bitmask：同題 nodes 逐題比對\n")
    idx = {(r["suite"], r["id"], r["mode"], r["solver"]): r for r in rows}
    for other in ("dlx", "hybrid", "cat_solver"):
        for mode in ("classify", "count"):
            eq, ne, ex, skipped = 0, 0, [], 0
            for (s, i, m, sv), r in idx.items():
                if sv != "bitmask" or m != mode:
                    continue
                o = idx[(s, i, m, other)]
                if r["timed_out"] or o["timed_out"]:
                    skipped += 1
                    continue
                if str(r["nodes"]) == str(o["nodes"]):
                    eq += 1
                else:
                    ne += 1
                    ex.append((i, r["nodes"], o["nodes"]))
            tot = eq + ne
            P(f"- bitmask vs {other} / {mode}: 兩者皆完成的 {tot} 題中 nodes 逐題相等 {eq} ({100 * eq / tot:.1f}%)，"
              f"不相等 {ne}；因任一方逾時而略過 {skipped}"
              + ("；不相等例子：" + "; ".join(f"{i} bitmask={a} {other}={b}" for i, a, b in ex[:3]) if ex else ""))
    P("")
    P("解讀：bitmask 與 dlx 在所有共同完成的題上 nodes 完全相等，代表兩者走的是同一棵搜尋樹"
      "（同樣的 MRV 選擇與同樣的分支順序），差別只在每個節點的實作成本。"
      "因此它們的「正確性一致」不是兩個獨立證據，且 dlx 比 bitmask 慢純粹是常數因子。\n")

    # ---- 7. S4 enumeration infeasible -----------------------------------------------------------------
    P("## 7. S4 count：N>=14 列舉不可行\n")
    bm = {n_: [int(r["count"]) for r in rows if r["suite"] == "S4" and r["solver"] == "bitmask"
               and r["mode"] == "count" and r["n"] == n_ and not r["timed_out"]] for n_ in (10, 12)}
    tt = {n_: [r["elapsed_s"] for r in rows if r["suite"] == "S4" and r["solver"] == "bitmask"
               and r["mode"] == "count" and r["n"] == n_ and not r["timed_out"]] for n_ in (10, 12)}
    gm = {n_: math.exp(statistics.mean(math.log(c) for c in bm[n_])) for n_ in bm}
    ratio = gm[12] / gm[10]
    per_sol = sum(tt[12]) / sum(bm[12])
    P(f"實測（bitmask 完成的題）：N=10 解數 {sorted(bm[10])}，幾何平均 {gm[10]:,.0f}；"
      f"N=12 解數 {sorted(bm[12])}，幾何平均 {gm[12]:,.0f}。N=14,16,18,20 各 5 題、6 種方法全部在 {timeout:g}s 內未完成。")
    P(f"\n**推論**（只用 N=10、12 兩點的對數線性外推，每 +2 的 N 解數約乘 {ratio:.0f} 倍；"
      f"N=12 實測每個解約 {per_sol * 1e6:.1f} 微秒；這是粗估，只有兩個 N 點，數量級可信度有限）：\n")
    P("| N | 估計解數（推論） | 以 bitmask 逐解成本估計的列舉時間（推論） | 相對 10s 上限 |")
    P("|---|---|---|---|")
    for n_ in (14, 16, 18, 20):
        c = gm[12] * ratio ** ((n_ - 12) / 2)
        sec = c * per_sol

        def human(s):
            for lim, u in ((86400 * 365, "年"), (86400, "天"), (3600, "小時"), (60, "分鐘")):
                if s >= lim:
                    return f"{s / lim:,.1f} {u}"
            return f"{s:.0f} 秒"
        P(f"| {n_} | ~{c:.1e} | ~{human(sec)} | {sec / timeout:,.0f}x |")
    P("\n因此 S4 N>=14 的 count 沒有任何方法的實測結果；classify（是否唯一）則全部方法都在毫秒級完成，不受影響。\n")

    # ---- 7b. rerun stability ----------------------------------------------------------------------------
    P("## 7b. 重跑記錄與邊界穩定性\n")
    P("final_S3 的 count 模式 N>=15（6 方法 x 60 題）依修正後的 repeat 規則重跑一次（任一次重複逾時即整筆 TIMEOUT）。"
      "重跑時機器負載偏高（其他工作同時在跑，load average 25-45），所以 6-10 秒附近的邊界題結果會變動，"
      "下列是重跑前後 status/verdict 有變的 row（原始值 -> 新值）：\n")
    for rr in metas["S3"].get("reruns", []):
        for c in rr["status_or_verdict_changed"]:
            P(f"- {'/'.join(c['key'][1:])}: {c['old'][0]}/{c['old'][1]} ({c['old'][2]:.2f}s) -> {c['new'][0]}/{c['new'][1]} ({c['new'][2]:.2f}s)")
    P("\n含意：在 10s 上限附近，兩次實測有 7 筆互相翻轉（另 1 筆 S3-n20-04/hybrid 是 repeat bug 的修正），方向有好有壞；所以 count 模式 S3 N=15 上 bitmask / hybrid / dlx / cat_solver 之間的 "
      "PAR2 差距，不應被讀成穩定的排名（推論：差距小於這個邊界噪音）。\n")

    # ---- 8. conclusions -----------------------------------------------------------------------------------
    P("## 8. 結論（依上列新表）\n")
    P(f"**答案可信度。** 共 {len(ans)} 筆有答案的 row：{basis['X']} 筆與獨立參考一致、{basis['Y']} 筆經 SAT 雙確認"
      f"（CaDiCaL + CP-SAT，解已用 check.py 驗證）、{basis['Z']} 筆僅「方法間一致」（count 模式、無獨立參考的 >=2 解題；這類題 count 全部逾時，所以是 0）、"
      f"矛盾 {basis['!']} 筆；另 {sum(r['timed_out'] for r in rows)} 筆逾時不算答案。"
      "不宣稱「全部正確」：>=2 解題在 classify 模式只被確認為「>=2」，而且 bitmask 與 dlx 是同一棵搜尋樹（表 6），不能算兩個獨立證據。\n")
    for mode in ("classify", "count"):
        order = rank[("困難子集 (S3 N>=15, S4 N>=12)", mode)]
        P(f"- {mode}，困難子集 PAR2 排名：" + " < ".join(order) + "。")
    P("")
    P("各 N 最快者（以 PAR2 最小；三類拆分見表 2）：")
    for mode in ("classify", "count"):
        s = "; ".join(f"{k[0]}-N{k[1]}:{v}" for k, v in sorted(winners1[mode].items()))
        P(f"- {mode}: {s}")
    P("")
    P("**怎麼讀（推論標示）**：")
    P("- 小 N（S3 N<=12、S4、S1/S2）上 bitmask 最快、其餘都在毫秒級，差異沒有實務意義；"
      "區分演算法的是 S3 N>=15 的「0 解 / >=2 解」兩類（隨機分區，搜尋樹大）。")
    P("- classify：SAT（CaDiCaL）在 S3 N>=15 全部完成、PAR2 是這類題的最佳選擇（PAR2 比回溯類低 1-3 個數量級）；"
      "回溯／DLX／hybrid 在 S3 N=20/25 約三到五成逾時。CP-SAT 次之，N=25 的 >=2 解類兩者幾乎打平（0.031 vs 0.037）。")
    P("- count：S3 N<=12 與 S4 N=10/12，bitmask 最快（每個解 ~6 微秒）；S3 N>=20 只有 SAT/CP-SAT 能完成一部分（0 解題），"
      ">=2 解題全部逾時；S4 N>=14 列舉不可行（表 7）。count 的 N=15 排名受邊界噪音影響（7b）。")
    P("- 含 import（每題獨立程序）：CP-SAT 多 ~0.21s，在 N<=12 的小題上由 bitmask / hybrid / dlx 勝出幅度變成約 50 倍，"
      "但對 S3 N>=15 的困難題 SAT 仍最佳。")
    P("- 局限：S4 為 5 題 / N、S3 為 20 題 / N；timeout 10s；機器負載偏高；SAT 的 N>=15 優勢是 3 次重複中位數下的結果。\n")
    P("三類拆分後各 N 的最快者（PAR2，連續相同者合併為最後一個 N）：")
    for mode in ("classify", "count"):
        for cls in (0, 1, 2):
            w = winners2.get((mode, cls))
            if w:
                P(f"- {mode} / {CLASS_NAME[cls]}: " + "; ".join(f"{k[0]} N={k[1]}:{v}" for k, v in sorted(w.items())))
    P("")
    print("\n".join(out))


main()
