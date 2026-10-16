"""Tables for the native-level final comparison (bench/run_final_native.sh -> bench/results/final_native_*.json).
  .venv/bin/python -B -m bench.make_table_native > bench/results/final_native_tables.md

Methods (core is C++ for all): native_bitmask / native_hybrid / native_dlx (native/cat_native), sat_cadical153_seq
(CaDiCaL 1.5.3 via pysat), cpsat_w1 (OR-tools CP-SAT, 1 worker).

Timing definitions
  core  = native solve time. native: the C++ internal clock (table build + search, no file parsing, no process start).
          SAT / CP-SAT: solve_s (the solver call only; Python model building excluded).
  e2e   = end to end = core + model building. native: identical to core (tables are built inside the timer).
          SAT / CP-SAT: build_s + solve_s (Python clause/model construction + solver creation + solve).
  Neither includes interpreter start-up or library import. Each row is the median of --repeat runs; if ANY repeat
  timed out the row is a TIMEOUT (counted as 2 x timeout in PAR2).
Cell = median / max / timeouts / PAR2; median and max are over the puzzles the method finished.
"""
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "results")
SUITES = ("S1", "S2", "S3", "S4", "S5", "S5b", "S6")
SOLVERS = ["native_bitmask", "native_hybrid", "native_dlx", "sat_cadical153_seq", "cpsat_w1"]
SHORT = {"native_bitmask": "bitmask", "native_hybrid": "hybrid", "native_dlx": "dlx",
         "sat_cadical153_seq": "CaDiCaL", "cpsat_w1": "CP-SAT"}
CLASS_NAME = {0: "0 解", 1: "唯一解", 2: ">=2 解"}
WORK = {  # solver -> [(column, label)]
    "native_bitmask": [("nodes", "nodes")], "native_hybrid": [("nodes", "nodes")], "native_dlx": [("nodes", "nodes")],
    "sat_cadical153_seq": [("conflicts", "conflicts"), ("decisions", "decisions"), ("propagations", "propagations")],
    "cpsat_w1": [("branches", "branches"), ("conflicts", "conflicts")]}


def fnum(x):
    """compact number: 12, 3.4k, 5.6M"""
    if x is None:
        return "-"
    x = float(x)
    for lim, u in ((1e9, "G"), (1e6, "M"), (1e3, "k")):
        if x >= lim:
            return f"{x / lim:.3g}{u}"
    return f"{x:.0f}"


def ft(t):
    if t is None:
        return "-"
    if t < 1e-3:
        return f"{t * 1e6:.0f}us"
    if t < 1:
        return f"{t * 1e3:.1f}ms"
    return f"{t:.2f}s"


def load():
    rows, metas = [], {}
    for s in SUITES:
        p = os.path.join(R, f"final_native_{s}.json")
        if not os.path.exists(p):
            continue
        d = json.load(open(p))
        rows += d["rows"]
        metas[s] = d["meta"]
    return rows, metas


def group_of():
    out = {}
    for s in ("S5", "S5b", "S6"):
        d = json.load(open(os.path.join(HERE, "suites", f"{s}.json")))
        for p in d["puzzles"]:
            out[p["id"]] = p.get("group") or s
    return out


def num(x):
    return None if x in (None, "") else float(x)


def enrich(rows, timeout, groups):
    for r in rows:
        r["n"] = int(r["n"])
        r["to"] = r["verdict"] == "TIMEOUT"
        r["core"] = num(r["core_s"])
        r["e2e"] = num(r["elapsed_s"])
        if r["to"]:
            r["core"] = r["e2e"] = float(timeout)
        r["cls"] = min(int(float(r["ref_count"])), 2) if r["ref_count"] not in ("", None) else None
        r["group"] = groups.get(r["id"])
        for c in ("nodes", "conflicts", "decisions", "propagations", "branches"):
            r[c] = num(r[c])
    return rows


def par2(g, key, timeout):
    return sum(2 * timeout if r["to"] else r[key] for r in g) / len(g)


def cell(g, key, timeout):
    if not g:
        return "n/a", None
    fin = [r[key] for r in g if not r["to"]]
    to = len(g) - len(fin)
    p = par2(g, key, timeout)
    med = statistics.median(fin) if fin else None
    mx = max(fin) if fin else None
    return f"{ft(med)} / {ft(mx)} / {to}/{len(g)} / {ft(p)}", (p, med if med is not None else 1e9)


def time_table(rows, keyfn, keys, label, timeout, key="core", pred=None):
    out = ["| " + label + " | " + " | ".join(SHORT[s] for s in SOLVERS) + " |", "|---|" + "---|" * len(SOLVERS)]
    for k in keys:
        base = [r for r in rows if keyfn(r) == k and (pred is None or pred(r))]
        if not base:
            continue
        cells, ranks = {}, {}
        for sv in SOLVERS:
            g = [r for r in base if r["solver"] == sv]
            cells[sv], ranks[sv] = cell(g, key, timeout)
        valid = {s: v for s, v in ranks.items() if v}
        if valid and len({v for v in valid.values()}) > 1:
            b = min(valid, key=valid.get)
            cells[b] = f"**{cells[b]}**"
        n = len([r for r in base if r["solver"] == SOLVERS[0]])
        name = " ".join(map(str, k)) if isinstance(k, tuple) else str(k)
        out.append(f"| {name} ({n}) | " + " | ".join(cells[s] for s in SOLVERS) + " |")
    return out


def work_table(rows, keyfn, keys, label, pred=None):
    """median / max of the language-independent work counters, over puzzles the method finished"""
    cols = []
    for sv in SOLVERS:
        for c, lab in WORK[sv]:
            cols.append((sv, c, f"{SHORT[sv]} {lab}"))
    out = ["| " + label + " | " + " | ".join(c[2] for c in cols) + " |", "|---|" + "---|" * len(cols)]
    for k in keys:
        base = [r for r in rows if keyfn(r) == k and not r["to"] and (pred is None or pred(r))]
        cs = []
        for sv, c, _ in cols:
            v = [r[c] for r in base if r["solver"] == sv and r[c] is not None]
            cs.append(f"{fnum(statistics.median(v))} / {fnum(max(v))}" if v else "-")
        name = " ".join(map(str, k)) if isinstance(k, tuple) else str(k)
        out.append(f"| {name} | " + " | ".join(cs) + " |")
    return out


def keys_of(rows, keyfn, pred=None):
    return sorted({keyfn(r) for r in rows if pred is None or pred(r)})


def main():
    rows, metas = load()
    timeout = next(iter(metas.values()))["timeout_s"]
    groups = group_of()
    enrich(rows, timeout, groups)
    out = []
    P = out.append

    # ---- 0 setup ---------------------------------------------------------------------------------
    P("# 原生層級最終總評比（所有求解器核心皆為 C++）\n")
    P("方法：native_bitmask、native_hybrid、native_dlx（native/cat_native，-O2）、sat_cadical153_seq（pysat 的 CaDiCaL 1.5.3，"
      "AMO 用 Sinz sequential counter）、cpsat_w1（ortools CP-SAT，1 worker）。單程序依序執行，一次一題。\n")
    P("## 0. 設定、計時口徑、正確性\n")
    P("| 題組 | repeat | timeout | 牆鐘 | load average 起 -> 迄 (1/5/15 分) | row 數 |")
    P("|---|---|---|---|---|---|")
    for s in SUITES:
        if s in metas:
            m = metas[s]
            P(f"| {s} | {m['repeat']} | {m['timeout_s']:g}s | {m['wall_s'] / 60:.1f} 分 | "
              f"{'/'.join(f'{x:.1f}' for x in m['load_start'])} -> {'/'.join(f'{x:.1f}' for x in m['load_end'])} | "
              f"{sum(r['suite'] == s for r in rows)} |")
    lp = os.path.join(R, "final_native_load.txt")
    if os.path.exists(lp):
        P("\n逐階段 load average（`/proc/loadavg` 前三欄；機器上另有其他使用者的工作，無法獨佔）：\n")
        P("```\n" + open(lp).read().rstrip() + "\n```")
    P("")
    P("**計時口徑**")
    P("- 主比較 = core（原生求解時間）：native 用 C++ 內部 steady_clock（含建表、搜尋，不含讀檔、行程啟動）；"
      "SAT / CP-SAT 用 solve_s（只含求解器呼叫，不含 Python 建模）。")
    P("- 端到端 = e2e：native 與 core 相同（建表在計時內）；SAT / CP-SAT = build_s + solve_s（含 Python 建 CNF／模型、建立求解器物件）。"
      "兩者都不含直譯器啟動與 import。")
    P(f"- 逾時 {timeout:g}s；PAR2 把逾時算 {2 * timeout:g}s；任一次 repeat 逾時即整筆 TIMEOUT。"
      "格式：中位／最大／超時／PAR2，中位與最大只算有完成的題，粗體 = 該列 PAR2 最小。")
    P("- 單位：us = 微秒，ms = 毫秒。native 的 count 模式不儲存解，只回報解數，所以 count 的正確性檢查是「解數 = 參考解數」。")
    P("- 工作量（與語言無關）：native = 搜尋節點數；CaDiCaL = conflicts / decisions / propagations（pysat accum_stats）；"
      "CP-SAT = branches / conflicts（solver.num_branches / num_conflicts）。工作量只統計有完成的題。")
    bad = [r for r in rows if r["verdict"] in ("MISMATCH", "ERROR", "NOREF", "INCOMPLETE")]
    P(f"\n**正確性**：共 {len(rows)} 筆 row，每一筆都與參考比對（獨立參考 bench.reference；無獨立參考的 S3/S4 題用 SAT 雙確認的類別；"
      f"S5/S5b/S6 為唯一解、參考由 SAT+CP-SAT+bitmask 確認）。")
    P(f"- MISMATCH {sum(r['verdict'] == 'MISMATCH' for r in rows)}、ERROR {sum(r['verdict'] == 'ERROR' for r in rows)}、"
      f"無參考/卡住 {sum(r['verdict'] in ('NOREF', 'INCOMPLETE') for r in rows)}、"
      f"逾時 {sum(r['to'] for r in rows)}、OK {sum(r['verdict'] == 'OK' for r in rows)}。")
    if bad:
        P("- **有問題的 row（不隱藏）**：")
        for r in bad:
            P(f"  - {r['suite']} {r['id']} {r['solver']}/{r['mode']}: {r['verdict']} {r['note']}")
    else:
        P("- 沒有任何 MISMATCH / ERROR 題 id 需要列出。")
    P("- 只確認到類別（0/唯一/>=2）的題（S3/S4 中無獨立參考者）在 count 模式只比較 min(解數,2)；其餘 count 與獨立參考的精確解數一致。")
    P("")

    # ---- 1/2 classify & count by class (S1-S4) ----------------------------------------------------
    s14 = lambda r: r["suite"] in ("S1", "S2", "S3", "S4")
    sec = 1
    for mode in ("classify", "count"):
        for key, kname in (("core", "原生求解時間 core"), ("e2e", "端到端 e2e")):
            if key == "e2e" and mode == "count":
                pass
            P(f"## {sec}. {mode}，依解數類別，{kname}（S1–S4）\n")
            sec += 1
            for cls in (0, 1, 2):
                pred = lambda r, c=cls, m=mode: s14(r) and r["mode"] == m and r["cls"] == c
                ks = keys_of(rows, lambda r: (r["suite"], r["n"]), pred)
                if not ks:
                    continue
                P(f"### {CLASS_NAME[cls]}\n")
                out += time_table(rows, lambda r: (r["suite"], r["n"]), ks, "題組 N (#題)", timeout, key, pred)
                P("")

    # ---- unique-solution section ---------------------------------------------------------------------
    P(f"## {sec}. 唯一解題：S5 / S5b / S6（只做 classify）\n")
    sec += 1
    u = lambda r: r["suite"] in ("S5", "S5b", "S6") and r["mode"] == "classify"
    P("題組規模與最壞情況：S5 = N 11–16 隨機唯一解；S5b = N 12/14/16 較難的唯一解；S6 = 對抗性（爬山法針對 bitmask / hybrid / SAT 各自最壞化）。\n")
    P("### 原生求解時間 core\n")
    ks = keys_of(rows, lambda r: (r["suite"], r["n"]), u)
    out += time_table(rows, lambda r: (r["suite"], r["n"]), ks, "題組 N (#題)", timeout, "core", u)
    P("\n### 端到端 e2e（含 SAT / CP-SAT 的 Python 建模）\n")
    out += time_table(rows, lambda r: (r["suite"], r["n"]), ks, "題組 N (#題)", timeout, "e2e", u)
    P("\n### 各題組最壞情況（單題最大 core，括號 = 該題 id）\n")
    P("| 題組 | " + " | ".join(SHORT[s] for s in SOLVERS) + " |")
    P("|---|" + "---|" * len(SOLVERS))
    for s in ("S5", "S5b", "S6"):
        cs = []
        for sv in SOLVERS:
            g = [r for r in rows if r["suite"] == s and r["solver"] == sv and r["mode"] == "classify"]
            if not g:
                cs.append("-")
                continue
            w = max(g, key=lambda r: r["core"])
            cs.append(f"{'>=' if w['to'] else ''}{ft(w['core'])} ({w['id']})")
        P(f"| {s} | " + " | ".join(cs) + " |")
    P("\n### 工作量隨 N 成長（中位 / 最大；有完成的題）\n")
    out += work_table(rows, lambda r: (r["suite"], r["n"]), ks, "題組 N", u)
    P("\n### S6 子組（針對誰最壞化）x 方法：core 中位／最大／超時／PAR2\n")
    gk = keys_of(rows, lambda r: r["group"], lambda r: r["suite"] == "S6")
    out += time_table(rows, lambda r: r["group"], gk, "子組 (#題)", timeout, "core", lambda r: r["suite"] == "S6")
    P("\n### S6 子組 x N：core\n")
    gk2 = keys_of(rows, lambda r: (r["group"], r["n"]), lambda r: r["suite"] == "S6")
    out += time_table(rows, lambda r: (r["group"], r["n"]), gk2, "子組 N (#題)", timeout, "core", lambda r: r["suite"] == "S6")
    P("\n### S6 子組：工作量（中位 / 最大）\n")
    out += work_table(rows, lambda r: r["group"], gk, "子組", lambda r: r["suite"] == "S6")
    P("\n### S6 子組 x N：工作量（中位 / 最大）\n")
    out += work_table(rows, lambda r: (r["group"], r["n"]), gk2, "子組 N", lambda r: r["suite"] == "S6")
    P("")

    # ---- work metrics on hard S3 / S4 --------------------------------------------------------------------
    P(f"## {sec}. 困難題的工作量（classify；S3 N>=15、S4 N>=12，依類別）\n")
    sec += 1
    for cls in (0, 2):
        pred = lambda r, c=cls: r["mode"] == "classify" and r["cls"] == c and ((r["suite"] == "S3" and r["n"] >= 15) or (r["suite"] == "S4" and r["n"] >= 12))
        ks = keys_of(rows, lambda r: (r["suite"], r["n"]), pred)
        if ks:
            P(f"### {CLASS_NAME[cls]}（中位 / 最大）\n")
            out += work_table(rows, lambda r: (r["suite"], r["n"]), ks, "題組 N", pred)
            P("")

    # ---- per-node cost ---------------------------------------------------------------------------------------
    P(f"## {sec}. 每節點成本（native；core / nodes，中位數；只算完成的題）\n")
    sec += 1
    P("| 題組 / mode / N | " + " | ".join(f"{SHORT[s]} ns/節點" for s in SOLVERS[:3]) + " |")
    P("|---|---|---|---|")
    ks = sorted({(r["suite"], r["mode"], r["n"]) for r in rows if r["solver"] == "native_bitmask"})
    for k in ks:
        cs = []
        for sv in SOLVERS[:3]:
            v = [r["core"] / r["nodes"] * 1e9 for r in rows if (r["suite"], r["mode"], r["n"]) == k and r["solver"] == sv
                 and not r["to"] and r["nodes"]]
            cs.append(f"{statistics.median(v):.0f}" if v else "-")
        P(f"| {k[0]} {k[1]} N={k[2]} | " + " | ".join(cs) + " |")
    P("")

    # ---- overall ranking --------------------------------------------------------------------------------------
    P(f"## {sec}. PAR2 總排名（core；全部題目等權）\n")
    sec += 1
    P("| 範圍 | mode | " + " | ".join(SHORT[s] for s in SOLVERS) + " |")
    P("|---|---|" + "---|" * len(SOLVERS))
    for name, f in (("S1–S4 全部", s14), ("S3 N>=15 + S4 N>=12", lambda r: (r["suite"] == "S3" and r["n"] >= 15) or (r["suite"] == "S4" and r["n"] >= 12)),
                    ("S5+S5b+S6（唯一解）", lambda r: r["suite"] in ("S5", "S5b", "S6"))):
        for mode in ("classify", "count"):
            g = {sv: [r for r in rows if r["solver"] == sv and r["mode"] == mode and f(r)] for sv in SOLVERS}
            if not g[SOLVERS[0]]:
                continue
            v = {sv: par2(g[sv], "core", timeout) for sv in SOLVERS}
            order = sorted(SOLVERS, key=v.get)
            P(f"| {name} | {mode} | " + " | ".join(f"{ft(v[s])} (#{order.index(s) + 1}, 逾時 {sum(r['to'] for r in g[s])}/{len(g[s])})" for s in SOLVERS) + " |")
    P("")

    ip = os.path.join(R, "final_native_investigation.md")
    if os.path.exists(ip):
        P(open(ip).read())
    print("\n".join(out))


if __name__ == "__main__":
    main()
