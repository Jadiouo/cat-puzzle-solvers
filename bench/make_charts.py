"""Build the README result charts (SVG) from bench/results/*.csv and s6x_climb.md.

    python3 bench/make_charts.py        # system python3 with matplotlib; no .venv needed

Every number drawn is printed, so it can be cross-checked against research/solver-conclusion.md.
Time = core_s (native solve time; SAT/CP-SAT = solver call only), median over the repeats of a puzzle.
PAR2 = mean over all puzzles of that time (a timeout counts as 2 x timeout).
"""
import csv, os, re, statistics, collections
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "results")
OUT = os.path.join(HERE, "..", "docs", "assets")
os.makedirs(OUT, exist_ok=True)

DFS = ["native_bitmask", "native_hybrid", "native_dlx"]
SHORT = {"native_bitmask": "bitmask", "native_hybrid": "hybrid", "native_dlx": "dlx"}
# categorical slots 1-4 of the reference palette (validated adjacent, light mode); same hex works on white card
COL = {"match": "#2a78d6", "dfs": "#eb6834", "cadical": "#1baf7a", "cpsat": "#6250d6"}
LAB = {"match": "Hall-matching DFS", "dfs": "best plain DFS", "cadical": "CaDiCaL (CDCL SAT)", "cpsat": "CP-SAT"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e3e2de"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "svg.fonttype": "path"})


def load(name):
    with open(os.path.join(R, name)) as f:
        return list(csv.DictReader(f))


def per_puzzle(rows, timeout):
    """-> {(solver, puzzle_id): time}; median of repeats; any TIMEOUT -> 2*timeout."""
    g = collections.defaultdict(list)
    for r in rows:
        g[(r["solver"], r["id"])].append(r)
    out = {}
    for k, rs in g.items():
        if any(r["status"] == "TIMEOUT" for r in rs):
            out[k] = 2 * timeout
        else:
            out[k] = statistics.median(float(r["core_s"]) for r in rs)
    return out


def fmt(t):
    return f"{t*1e6:.0f}us" if t < 1e-3 else f"{t*1e3:.3g}ms" if t < 1 else f"{t:.3g}s"


# ---------- unified data ----------
SUITES = {s: per_puzzle(load(f"unified_{s}.csv"), 10) for s in ["S5", "S5b", "S6", "S6x", "S6m"]}


def par2(table, solver, pred):
    v = [t for (s, i), t in table.items() if s == solver and pred(i)]
    return sum(v) / len(v), len(v)


GROUPS = [("S5\nrandom unique", "S5", lambda i: i.startswith("S5-")),
          ("S6x-bm", "S6x", lambda i: i.startswith("S6x-bm")),
          ("S6x-hy", "S6x", lambda i: i.startswith("S6x-hy")),
          ("S6x-sat", "S6x", lambda i: i.startswith("S6x-sat-")),
          ("S6x-sat2", "S6x", lambda i: i.startswith("S6x-sat2")),
          ("S6m\nN=18", "S6m", lambda i: i.startswith("S6m-mt-n18"))]

# ---------- (a) PAR2 by suite ----------
print("== (a) PAR2 (core), unified round ==")
res = {}
for label, suite, pred in GROUPS:
    t = SUITES[suite]
    row = {"match": par2(t, "native_match", pred)[0],
           "cadical": par2(t, "sat_cadical153_seq", pred)[0],
           "cpsat": par2(t, "cpsat_w1", pred)[0]}
    d = {s: par2(t, s, pred)[0] for s in DFS}
    best = min(d, key=d.get)
    row["dfs"] = d[best]
    res[label] = (row, best, par2(t, "native_match", pred)[1])
    print(label.replace("\n", " "), f"n={res[label][2]}", f"bestDFS={SHORT[best]}",
          {k: fmt(v) for k, v in row.items()})

fig, ax = plt.subplots(figsize=(9, 4.4))
keys = ["match", "dfs", "cadical", "cpsat"]
w = 0.19
for j, k in enumerate(keys):
    xs = [i + (j - 1.5) * w for i in range(len(GROUPS))]
    ys = [res[g[0]][0][k] * 1e3 for g in GROUPS]
    ax.bar(xs, ys, w * 0.92, color=COL[k], label=LAB[k], zorder=3)
ax.set_yscale("log")
ax.set_xticks(range(len(GROUPS)))
ax.set_xticklabels([g[0] for g in GROUPS])
ax.set_ylabel("PAR2, core time (ms, log scale)")
ax.set_title("Mean solve time by puzzle family (lower is better)", loc="left", color=INK, fontsize=11)
ax.yaxis.grid(True, color=GRID, zorder=0); ax.set_axisbelow(True)
for s in ("top", "right"): ax.spines[s].set_visible(False)
ax.legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.17), fontsize=9)
fig.text(0.01, 0.01, "Unified round, 3 repeats/puzzle, 5 puzzles per (family, N) cell, no timeouts. S6m shown at N=18.", fontsize=7.5, color=INK2)
fig.patch.set_facecolor("white"); fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(os.path.join(OUT, "par2_by_suite.svg"), facecolor="white"); plt.close(fig)

# ---------- (b) worst single puzzle on adversarial suites ----------
print("== (b) worst single puzzle, adversarial (S6, S6x, S6m) ==")
adv = {}
for s in ("S6", "S6x", "S6m"):
    adv.update({(sv, s + "|" + i): t for (sv, i), t in SUITES[s].items()})
worst = {}
for name, sv in [("bitmask", "native_bitmask"), ("hybrid", "native_hybrid"), ("dlx", "native_dlx"),
                 ("match", "native_match"), ("CaDiCaL", "sat_cadical153_seq"), ("CP-SAT", "cpsat_w1")]:
    v = {i: t for (s, i), t in adv.items() if s == sv}
    k = max(v, key=v.get)
    worst[name] = (v[k], k)
    print(name, fmt(v[k]), k, f"(n={len(v)})")
plain = max(worst[k][0] for k in ("bitmask", "hybrid", "dlx"))
print("worst plain DFS:", fmt(plain))
order = [("bitmask", "bitmask"), ("hybrid", "hybrid"), ("dlx", "dlx"), ("match", "Hall-matching DFS"),
         ("CaDiCaL", "CaDiCaL"), ("CP-SAT", "CP-SAT")]
cmap = {"bitmask": COL["dfs"], "hybrid": COL["dfs"], "dlx": COL["dfs"], "match": COL["match"],
        "CaDiCaL": COL["cadical"], "CP-SAT": COL["cpsat"]}
fig, ax = plt.subplots(figsize=(7.5, 3.6))
ys = list(range(len(order)))[::-1]
for y, (k, lab) in zip(ys, order):
    ax.barh(y, worst[k][0] * 1e3, 0.62, color=cmap[k], zorder=3)
    ax.text(worst[k][0] * 1e3 * 1.04, y, fmt(worst[k][0]), va="center", fontsize=9, color=INK)
ax.set_yticks(ys); ax.set_yticklabels([o[1] for o in order])
ax.set_xlabel("slowest single puzzle, core time (ms)")
ax.set_title("Worst case on the hill-climbed hard puzzles (lower is better)", loc="left", color=INK, fontsize=11)
ax.xaxis.grid(True, color=GRID, zorder=0); ax.set_axisbelow(True)
for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
ax.tick_params(axis="y", length=0); ax.set_xlim(0, max(w_[0] for w_ in worst.values()) * 1e3 * 1.18)
fig.text(0.01, 0.01, "S6 + S6x + S6m, N=10-18, all unique-solution. Not a worst-case guarantee.", fontsize=7.5, color=INK2)
fig.patch.set_facecolor("white"); fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(os.path.join(OUT, "worst_case.svg"), facecolor="white"); plt.close(fig)

# ---------- (c) S3 N=25 timeouts ----------
print("== (c) S3 N=25, 60 s timeout ==")
rows = load("extra_S3n25_t60.csv")
by = collections.defaultdict(lambda: collections.defaultdict(list))
for r in rows:
    by[r["solver"]][r["id"]].append(r["status"])
print("solvers in file:", sorted(by))
S3 = {}
for sv, d in by.items():
    S3[sv] = (sum(any(x == "TIMEOUT" for x in v) for v in d.values()), len(d))
    print(sv, f"timeouts {S3[sv][0]}/{S3[sv][1]}")
CH = [("bitmask", "native_bitmask", COL["dfs"]), ("hybrid", "native_hybrid", COL["dfs"]),
      ("dlx", "native_dlx", COL["dfs"]), ("Hall-matching DFS", "native_match", COL["match"]),
      ("CaDiCaL", "sat_cadical153_seq", COL["cadical"]), ("CP-SAT", "cpsat_w1", COL["cpsat"])]
CH = [c for c in CH if c[1] in S3]
fig, ax = plt.subplots(figsize=(7.5, 3.4))
ys = list(range(len(CH)))[::-1]
for y, (lab, sv, c) in zip(ys, CH):
    to, tot = S3[sv]
    ax.barh(y, to, 0.62, color=c, zorder=3)
    ax.text(to + 0.1, y, f"{to}/{tot}", va="center", fontsize=9, color=INK)
ax.set_yticks(ys); ax.set_yticklabels([c[0] for c in CH])
ax.set_xlabel("puzzles timed out (60 s limit)")
ax.set_title("Random color regions, N=25, 20 puzzles (lower is better)", loc="left", color=INK, fontsize=11)
ax.xaxis.grid(True, color=GRID, zorder=0); ax.set_axisbelow(True)
for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
ax.tick_params(axis="y", length=0); ax.set_xlim(0, 6.5)
fig.patch.set_facecolor("white"); fig.tight_layout()
fig.savefig(os.path.join(OUT, "s3_n25_timeouts.svg"), facecolor="white"); plt.close(fig)

# ---------- (d) climb ratio ----------
print("== (d) hill-climb push-up (own objective, median final/start) ==")
txt = open(os.path.join(R, "s6x_climb.md")).read()
climb = {}
for m in re.finditer(r"^\| (bm|hy|sat|sat2|mt) \| (\d+) \| 5 \| (\d+) \| (\d+) \| ([\d.]+)x \| ([\d.]+)x \|", txt, re.M):
    climb[(m[1], int(m[2]))] = (float(m[5]), float(m[6]))
for k, v in climb.items():
    print(k, f"median {v[0]}x max {v[1]}x")
bars = [("bitmask nodes", [climb[("bm", 16)][0], climb[("bm", 18)][0]], COL["dfs"]),
        ("hybrid nodes", [climb[("hy", 16)][0], climb[("hy", 18)][0]], COL["dfs"]),
        ("match nodes", [climb[("mt", 16)][0], climb[("mt", 18)][0]], COL["match"]),
        ("CaDiCaL conflicts", [climb[("sat", 16)][0], climb[("sat", 18)][0]], COL["cadical"]),
        ("CaDiCaL, max of 4 var. orders", [climb[("sat2", 16)][0], climb[("sat2", 18)][0]], COL["cadical"])]
fig, ax = plt.subplots(figsize=(9, 3.8))
ys = list(range(len(bars)))[::-1]
for y, (lab, vals, c) in zip(ys, bars):
    for dy, v, n in ((0.17, vals[0], 16), (-0.17, vals[1], 18)):
        ax.barh(y + dy, v, 0.3, color=c, alpha=1.0 if n == 18 else 0.55, zorder=3)
        ax.text(v * 1.08, y + dy, f"{v:g}x  (N={n})", va="center", fontsize=8, color=INK)
ax.set_xscale("log"); ax.set_xlim(1, 30000)
ax.set_yticks(ys); ax.set_yticklabels([b[0] for b in bars])
ax.set_xlabel("median final / start difficulty (log scale)")
ax.set_title("How far search can push difficulty up (the solver's own metric)", loc="left", color=INK, fontsize=11)
ax.xaxis.grid(True, color=GRID, zorder=0); ax.set_axisbelow(True)
for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
ax.tick_params(axis="y", length=0)
fig.patch.set_facecolor("white"); fig.tight_layout()
fig.savefig(os.path.join(OUT, "climb_ratio.svg"), facecolor="white"); plt.close(fig)
print("charts ->", os.path.abspath(OUT))
