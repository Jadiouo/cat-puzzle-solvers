// Faithful C++ ports of bench/solver_bitmask.py, bench/solver_hybrid.py (default: S+T3+T3b)
// and bench/solver_dlx.py.  Same branching order, same propagation rules, same node counting,
// so node counts must equal the Python ones puzzle by puzzle.
//
// Input  (stdin or -i file): one puzzle per line:  id n v00 v01 ... v(n-1)(n-1)
// Output (stdout): one JSON object per line.
// Usage: cat_native -s bitmask|hybrid|dlx|match|rr|match_rr -m first|classify|count -t timeout_s [-r repeats] [-i file]
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <map>
#include <random>
#include <stdexcept>
#include <sstream>
#include <string>
#include <vector>

typedef unsigned __int128 u128;
typedef uint64_t u64;
using Clock = std::chrono::steady_clock;
struct TimeoutEx {};
struct RestartEx {};

static inline double secs(Clock::time_point a, Clock::time_point b) {
    return std::chrono::duration<double>(b - a).count();
}

// ---------- fixed-width bitset over n*n cells ----------
template <int W> struct B {
    u64 w[W];
    B() { for (int i = 0; i < W; i++) w[i] = 0; }
    inline bool any() const { u64 a = 0; for (int i = 0; i < W; i++) a |= w[i]; return a != 0; }
    inline B operator&(const B& o) const { B r; for (int i = 0; i < W; i++) r.w[i] = w[i] & o.w[i]; return r; }
    inline B operator|(const B& o) const { B r; for (int i = 0; i < W; i++) r.w[i] = w[i] | o.w[i]; return r; }
    inline B andnot(const B& o) const { B r; for (int i = 0; i < W; i++) r.w[i] = w[i] & ~o.w[i]; return r; }  // this & ~o
    inline B& operator&=(const B& o) { for (int i = 0; i < W; i++) w[i] &= o.w[i]; return *this; }
    inline B& operator|=(const B& o) { for (int i = 0; i < W; i++) w[i] |= o.w[i]; return *this; }
    inline B& clear(const B& o) { for (int i = 0; i < W; i++) w[i] &= ~o.w[i]; return *this; }
    inline int count() const { int c = 0; for (int i = 0; i < W; i++) c += __builtin_popcountll(w[i]); return c; }
    inline int lowest() const { for (int i = 0; i < W; i++) if (w[i]) return i * 64 + __builtin_ctzll(w[i]); return -1; }
    inline bool single() const {   // exactly one bit
        int c = 0; for (int i = 0; i < W; i++) { if (w[i]) { if (c || (w[i] & (w[i] - 1))) return false; c = 1; } }
        return c == 1;
    }
    inline void set(int x) { w[x >> 6] |= (u64)1 << (x & 63); }
    inline void reset(int x) { w[x >> 6] &= ~((u64)1 << (x & 63)); }
};

struct Result {
    bool timed_out = false;
    long long count = 0, nodes = 0, forced = 0, elims = 0;
    std::vector<std::vector<int>> sols;   // stored for first/classify only
};

struct Params { int limit; bool store; double deadline_s; Clock::time_point t0; };

static inline bool expired(const Params& P) { return secs(P.t0, Clock::now()) > P.deadline_s; }

// ---------- tables shared by bitmask & hybrid (build_tables) ----------
template <int W> struct Tables {
    int n = 0;
    std::vector<B<W>> ROW, COL, REG, UN, KILL;
    std::vector<u128> UBIT;
    std::vector<int> REGOF;
    u128 FULL = 0;
    B<W> ALL;
    bool ok = false;
    explicit Tables(const std::vector<int>& g, int n_) : n(n_) {
        std::vector<int> ids(g); std::sort(ids.begin(), ids.end()); ids.erase(std::unique(ids.begin(), ids.end()), ids.end());
        if ((int)ids.size() != n) return;
        ok = true;
        ROW.assign(n, B<W>()); COL.assign(n, B<W>()); REG.assign(n, B<W>());
        REGOF.assign(n * n, 0);
        for (int r = 0; r < n; r++) for (int c = 0; c < n; c++) {
            int gi = std::lower_bound(ids.begin(), ids.end(), g[r * n + c]) - ids.begin();
            int x = r * n + c;
            ROW[r].set(x); COL[c].set(x); REG[gi].set(x); REGOF[x] = gi; ALL.set(x);
        }
        KILL.assign(n * n, B<W>()); UBIT.assign(n * n, 0);
        for (int r = 0; r < n; r++) for (int c = 0; c < n; c++) {
            int x = r * n + c, gi = REGOF[x];
            B<W> k = ROW[r] | COL[c] | REG[gi];
            for (int a = std::max(0, r - 1); a < std::min(n, r + 2); a++)
                for (int b = std::max(0, c - 1); b < std::min(n, c + 2); b++) k.set(a * n + b);
            KILL[x] = k;
            UBIT[x] = ((u128)1 << r) | ((u128)1 << (n + c)) | ((u128)1 << (2 * n + gi));
        }
        UN.reserve(3 * n);
        for (auto& v : ROW) UN.push_back(v);
        for (auto& v : COL) UN.push_back(v);
        for (auto& v : REG) UN.push_back(v);
        FULL = (((u128)1) << (3 * n)) - 1;
    }
};

// ---------- (A) bitmask DFS, MRV over units + forward check ----------
template <int W> struct Bitmask {
    const Tables<W>& T; const Params& P; Result& R; int n;
    Bitmask(const Tables<W>& t, const Params& p, Result& r) : T(t), P(p), R(r), n(t.n) {}
    bool rec(const B<W>& alive, u128 done, const B<W>& cats) {
        R.nodes++;
        if (!(R.nodes & 255) && expired(P)) throw TimeoutEx();
        if (done == T.FULL) { record(cats); return P.limit && R.count >= P.limit; }
        int bc = 1 << 30; B<W> bm;
        for (int u = 0; u < 3 * n; u++) {
            if ((done >> u) & 1) continue;
            B<W> m = alive & T.UN[u];
            if (!m.any()) return false;
            int c = m.count();
            if (c < bc) { bc = c; bm = m; }
        }
        while (bm.any()) {
            int x = bm.lowest(); bm.reset(x);
            B<W> na = alive; na.clear(T.KILL[x]);
            B<W> nc = cats; nc.set(x);
            if (rec(na, done | T.UBIT[x], nc)) return true;
        }
        return false;
    }
    void record(const B<W>& cats) {
        R.count++;
        if (P.store) {
            std::vector<int> s(n, 0);
            for (int x = 0; x < n * n; x++) if ((cats.w[x >> 6] >> (x & 63)) & 1) s[x / n] = x % n;
            R.sols.push_back(s);
        }
    }
};

// ---------- (B) hybrid: S + T3 + T3b to fixed point, then MRV branch ----------
template <int W> struct Hybrid {
    const Tables<W>& T; const Params& P; Result& R; int n;
    Hybrid(const Tables<W>& t, const Params& p, Result& r) : T(t), P(p), R(r), n(t.n) {}
    bool prop(B<W>& alive, u128& done, B<W>& cats) {
        const int NU = 3 * n;
        for (;;) {
            bool changed = false;
            for (int u = 0; u < NU; u++) {
                if ((done >> u) & 1) continue;
                B<W> m = alive & T.UN[u];
                if (!m.any()) return false;
                if (m.single()) {
                    int x = m.lowest();
                    alive.clear(T.KILL[x]);
                    done |= T.UBIT[x];
                    cats |= m;
                    R.forced++;
                    changed = true;
                }
            }
            if (changed) continue;
            if (done == T.FULL) return true;
            {   // T3
                B<W> rm;
                for (int g = 0; g < n; g++) {
                    if ((done >> (2 * n + g)) & 1) continue;
                    B<W> m = alive & T.REG[g];
                    int x = m.lowest(); int r = x / n, c = x % n;
                    if (!m.andnot(T.ROW[r]).any()) rm |= T.ROW[r].andnot(T.REG[g]);
                    if (!m.andnot(T.COL[c]).any()) rm |= T.COL[c].andnot(T.REG[g]);
                }
                for (int u = 0; u < 2 * n; u++) {
                    if ((done >> u) & 1) continue;
                    B<W> m = alive & T.UN[u];
                    int x = m.lowest(); int g = T.REGOF[x];
                    if (!m.andnot(T.REG[g]).any()) rm |= T.REG[g].andnot(T.UN[u]);
                }
                rm &= alive;
                if (rm.any()) { alive.clear(rm); R.elims++; continue; }
            }
            {   // T3b
                B<W> rm;
                for (int u = 0; u < NU; u++) {
                    if ((done >> u) & 1) continue;
                    B<W> m = alive & T.UN[u];
                    B<W> acc = alive.andnot(m).andnot(rm);
                    B<W> mm = m;
                    while (mm.any() && acc.any()) {
                        int y = mm.lowest(); mm.reset(y);
                        acc &= T.KILL[y];
                    }
                    rm |= acc;
                }
                if (rm.any()) { alive.clear(rm); R.elims++; continue; }
            }
            return true;
        }
    }
    bool rec(B<W> alive, u128 done, B<W> cats) {
        R.nodes++;
        if (!(R.nodes & 63) && expired(P)) throw TimeoutEx();
        if (!prop(alive, done, cats)) return false;
        if (done == T.FULL) {
            R.count++;
            if (P.store) {
                std::vector<int> s(n, 0);
                for (int x = 0; x < n * n; x++) if ((cats.w[x >> 6] >> (x & 63)) & 1) s[x / n] = x % n;
                R.sols.push_back(s);
            }
            return P.limit && R.count >= P.limit;
        }
        int bc = 1 << 30; B<W> bm;
        for (int u = 0; u < 3 * n; u++) {
            if ((done >> u) & 1) continue;
            B<W> m = alive & T.UN[u];
            int c = m.count();
            if (c < bc) { bc = c; bm = m; }
        }
        while (bm.any()) {
            int x = bm.lowest(); bm.reset(x);
            B<W> na = alive; na.clear(T.KILL[x]);
            B<W> nc = cats; nc.set(x);
            if (rec(na, done | T.UBIT[x], nc)) return true;
        }
        return false;
    }
};

template <int W> static void run_bitmask_hybrid(bool hybrid, const std::vector<int>& g, int n, const Params& P, Result& R) {
    Tables<W> T(g, n);
    if (!T.ok) return;   // colour count != n: UNSAT, 0 nodes
    try {
        if (hybrid) { Hybrid<W> H(T, P, R); H.rec(T.ALL, 0, B<W>()); }
        else { Bitmask<W> M(T, P, R); M.rec(T.ALL, 0, B<W>()); }
    } catch (TimeoutEx&) { R.timed_out = true; }
}


// ---------- (D) bitmask DFS + Hall/matching pruning and/or randomised Luby restarts ----------
// match: at every node, the unplaced colour regions must have a perfect matching into the unused rows
//        and into the unused columns (edge = region still has an alive cell in that row/column).
//        Same branching order as Bitmask, only extra pruning => node count <= Bitmask.
// rr:    MRV ties broken uniformly at random, value order shuffled, Luby restarts (node budget =
//        base * luby(i)).  Complete: the budget grows without bound, so some restart finishes.
static inline bool kuhn_try(int a, const uint32_t* adj, uint32_t& seen, int* matchR) {
    uint32_t cand = adj[a] & ~seen;
    while (cand) {
        int b = __builtin_ctz(cand); cand &= cand - 1;
        seen |= 1u << b;
        if (matchR[b] < 0 || kuhn_try(matchR[b], adj, seen, matchR)) { matchR[b] = a; return true; }
    }
    return false;
}
static inline bool perfect_matching(int k, const uint32_t* adj) {
    int matchR[32];
    for (int i = 0; i < 32; i++) matchR[i] = -1;
    for (int a = 0; a < k; a++) {
        if (!adj[a]) return false;
        uint32_t seen = 0;
        if (!kuhn_try(a, adj, seen, matchR)) return false;
    }
    return true;
}
static long long luby(long long i) {   // 1-based: 1 1 2 1 1 2 4 ...
    for (;;) {
        long long k = 1;
        while (((1LL << k) - 1) < i) k++;
        if (((1LL << k) - 1) == i) return 1LL << (k - 1);
        i -= (1LL << (k - 1)) - 1;
    }
}

template <int W> struct Search {
    const Tables<W>& T; const Params& P; Result& R; int n;
    bool match, rr; long long budget = 0, used = 0;
    std::mt19937_64 rng;
    Search(const Tables<W>& t, const Params& p, Result& r, bool m, bool rr_, unsigned long long seed)
        : T(t), P(p), R(r), n(t.n), match(m), rr(rr_), rng(seed) {}
    bool hall(const B<W>& alive, u128 done) {
        uint32_t ra[32], ca[32]; int k = 0;
        for (int g = 0; g < n; g++) {
            if ((done >> (2 * n + g)) & 1) continue;
            B<W> m = alive & T.REG[g];
            uint32_t rm = 0, cm = 0;
            while (m.any()) { int x = m.lowest(); m.reset(x); rm |= 1u << (x / n); cm |= 1u << (x % n); }
            ra[k] = rm; ca[k] = cm; k++;
        }
        return perfect_matching(k, ra) && perfect_matching(k, ca);
    }
    bool rec(const B<W>& alive, u128 done, const B<W>& cats) {
        R.nodes++;
        if (rr && ++used > budget) throw RestartEx();
        if (!(R.nodes & 255) && expired(P)) throw TimeoutEx();
        if (done == T.FULL) {
            R.count++;
            if (P.store) {
                std::vector<int> s(n, 0);
                for (int x = 0; x < n * n; x++) if ((cats.w[x >> 6] >> (x & 63)) & 1) s[x / n] = x % n;
                R.sols.push_back(s);
            }
            return P.limit && R.count >= P.limit;
        }
        int bc = 1 << 30, ties = 0; B<W> bm;
        for (int u = 0; u < 3 * n; u++) {
            if ((done >> u) & 1) continue;
            B<W> m = alive & T.UN[u];
            if (!m.any()) return false;
            int c = m.count();
            if (c < bc) { bc = c; bm = m; ties = 1; }
            else if (rr && c == bc && rng() % (++ties) == 0) bm = m;   // reservoir sampling over ties
        }
        if (match && !hall(alive, done)) return false;
        int xs[640], k = 0;
        while (bm.any()) { int x = bm.lowest(); bm.reset(x); xs[k++] = x; }
        if (rr) for (int i = k - 1; i > 0; i--) std::swap(xs[i], xs[rng() % (i + 1)]);
        for (int i = 0; i < k; i++) {
            int x = xs[i];
            B<W> na = alive; na.clear(T.KILL[x]);
            B<W> nc = cats; nc.set(x);
            if (rec(na, done | T.UBIT[x], nc)) return true;
        }
        return false;
    }
};

template <int W> static void run_search(bool match, bool rr, const std::vector<int>& g, int n, const Params& P, Result& R) {
    Tables<W> T(g, n);
    if (!T.ok) return;
    Search<W> S(T, P, R, match, rr, 1);
    try {
        if (!rr) { S.rec(T.ALL, 0, B<W>()); return; }
        const long long BASE = 100;
        for (long long i = 1;; i++) {
            S.budget = BASE * luby(i); S.used = 0;
            R.count = 0; R.sols.clear();   // a restart abandons partial results; nodes stay cumulative
            try { S.rec(T.ALL, 0, B<W>()); return; } catch (RestartEx&) {}
        }
    } catch (TimeoutEx&) { R.timed_out = true; }
}

// ---------- (C) DLX ----------
struct DLX {
    std::vector<int> L, R_, U, D, C, S, ROW;
    int n; const Params& P; Result& R; std::vector<int> chosen;
    DLX(const std::vector<int>& g, int n_, const Params& p, Result& r) : n(n_), P(p), R(r) {
        int nprim = 3 * n, nsec = std::max(n - 1, 0) * std::max(n - 1, 0), ncols = nprim + nsec;
        L.resize(ncols + 1); R_.resize(ncols + 1);
        for (int i = 0; i <= ncols; i++) { L[i] = i - 1; R_[i] = i + 1; }
        L[0] = nprim; R_[nprim] = 0;
        for (int k = nprim + 1; k <= ncols; k++) L[k] = R_[k] = k;
        U.resize(ncols + 1); D.resize(ncols + 1); C.resize(ncols + 1);
        for (int i = 0; i <= ncols; i++) U[i] = D[i] = C[i] = i;
        S.assign(ncols + 1, 0); ROW.assign(ncols + 1, -1);
        for (int r_ = 0; r_ < n; r_++) for (int c = 0; c < n; c++) {
            std::vector<int> cols = {1 + r_, 1 + n + c, 1 + 2 * n + g[r_ * n + c]};
            for (int i = r_ - 1; i <= r_; i++) for (int j = c - 1; j <= c; j++)
                if (0 <= i && i <= n - 2 && 0 <= j && j <= n - 2) cols.push_back(1 + nprim + i * (n - 1) + j);
            int first = -1;
            for (int col : cols) {
                int x = U.size();
                U.push_back(U[col]); D.push_back(col); C.push_back(col); ROW.push_back(r_ * n + c);
                L.push_back(0); R_.push_back(0);
                D[U[col]] = x; U[col] = x; S[col]++;
                if (first < 0) { first = x; L[x] = R_[x] = x; }
                else { int last = L[first]; L[x] = last; R_[x] = first; R_[last] = x; L[first] = x; }
            }
        }
    }
    void cover(int c) {
        R_[L[c]] = R_[c]; L[R_[c]] = L[c];
        for (int i = D[c]; i != c; i = D[i])
            for (int j = R_[i]; j != i; j = R_[j]) { int u = U[j], d = D[j]; D[u] = d; U[d] = u; S[C[j]]--; }
    }
    void uncover(int c) {
        for (int i = U[c]; i != c; i = U[i])
            for (int j = L[i]; j != i; j = L[j]) { S[C[j]]++; D[U[j]] = j; U[D[j]] = j; }
        R_[L[c]] = c; L[R_[c]] = c;
    }
    bool search() {
        R.nodes++;
        if (!(R.nodes & 255) && expired(P)) throw TimeoutEx();
        if (R_[0] == 0) {
            R.count++;
            if (P.store) { std::vector<int> s(n, 0); for (int o : chosen) s[o / n] = o % n; R.sols.push_back(s); }
            return P.limit && R.count >= P.limit;
        }
        int c = R_[0], best = S[c];
        for (int k = R_[c]; k != 0; k = R_[k]) if (S[k] < best) { best = S[k]; c = k; }
        if (best == 0) return false;
        cover(c);
        bool stop = false;
        for (int r = D[c]; r != c; r = D[r]) {
            chosen.push_back(ROW[r]);
            for (int j = R_[r]; j != r; j = R_[j]) cover(C[j]);
            stop = search();
            for (int j = L[r]; j != r; j = L[j]) uncover(C[j]);
            chosen.pop_back();
            if (stop) break;
        }
        uncover(c);
        return stop;
    }
};

static void run_dlx(const std::vector<int>& g, int n, const Params& P, Result& R) {
    if (n == 0) return;
    DLX d(g, n, P, R);
    try { d.search(); } catch (TimeoutEx&) { R.timed_out = true; }
}

template <int W> static void dispatch_w(int solver, const std::vector<int>& g, int n, const Params& P, Result& R) {
    if (solver >= 3) { run_search<W>(solver == 3 || solver == 5, solver == 4 || solver == 5, g, n, P, R); return; }
    run_bitmask_hybrid<W>(solver == 1, g, n, P, R);
}

static void run_one(int solver, const std::vector<int>& g, int n, const Params& P, Result& R) {
    if (solver == 2) { run_dlx(g, n, P, R); return; }
    int W = (n * n + 63) / 64;
    switch (W) {
        case 1: dispatch_w<1>(solver, g, n, P, R); break;
        case 2: dispatch_w<2>(solver, g, n, P, R); break;
        case 3: dispatch_w<3>(solver, g, n, P, R); break;
        case 4: dispatch_w<4>(solver, g, n, P, R); break;
        case 5: dispatch_w<5>(solver, g, n, P, R); break;
        case 6: dispatch_w<6>(solver, g, n, P, R); break;
        case 7: dispatch_w<7>(solver, g, n, P, R); break;
        case 8: dispatch_w<8>(solver, g, n, P, R); break;
        case 9: dispatch_w<9>(solver, g, n, P, R); break;
        case 10: dispatch_w<10>(solver, g, n, P, R); break;
        default: throw std::runtime_error("n too large (max 25)");
    }
}

int main(int argc, char** argv) {
    std::string sname = "hybrid", mode = "classify", infile;
    double timeout = 10; int repeats = 1;
    for (int i = 1; i < argc; i++) {
        std::string a = argv[i];
        auto nx = [&]() -> std::string { if (i + 1 >= argc) { fprintf(stderr, "missing value for %s\n", a.c_str()); exit(2); } return argv[++i]; };
        if (a == "-s") sname = nx(); else if (a == "-m") mode = nx(); else if (a == "-t") timeout = atof(nx().c_str());
        else if (a == "-r") repeats = atoi(nx().c_str()); else if (a == "-i") infile = nx();
        else { fprintf(stderr, "usage: cat_native -s bitmask|hybrid|dlx|match|rr|match_rr -m first|classify|count -t sec [-r reps] [-i file]\n"); return 2; }
    }
    int solver = sname == "bitmask" ? 0 : sname == "hybrid" ? 1 : sname == "dlx" ? 2 : sname == "match" ? 3 : sname == "rr" ? 4 : sname == "match_rr" ? 5 : -1;
    int limit = mode == "first" ? 1 : mode == "classify" ? 2 : mode == "count" ? 0 : -1;
    if (solver < 0 || limit < 0) { fprintf(stderr, "bad solver or mode\n"); return 2; }
    std::ifstream fin; if (!infile.empty()) fin.open(infile);
    std::istream& in = infile.empty() ? std::cin : fin;
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty()) continue;
        std::istringstream ss(line);
        std::string id; int n; ss >> id >> n;
        std::vector<int> g(n * n);
        for (auto& v : g) ss >> v;
        std::vector<double> times; Result R;
        std::string err;
        for (int rep = 0; rep < repeats; rep++) {
            Result cur;
            Params P{limit, limit != 0, timeout, Clock::now()};
            try {
                if (solver >= 4 && mode == "count") throw std::runtime_error("count mode unsupported for randomised-restart solvers");
                run_one(solver, g, n, P, cur);
            } catch (std::exception& e) { err = e.what(); }
            double el = secs(P.t0, Clock::now());
            times.push_back(el); R = cur;
            if (cur.timed_out || !err.empty()) break;
        }
        std::vector<double> st(times); std::sort(st.begin(), st.end());
        double med = st[st.size() / 2];
        bool enough = limit && R.count >= limit;
        const char* status; std::string cnt; bool complete;
        if (!err.empty()) { status = "ERROR"; cnt = "null"; complete = false; }
        else if (R.timed_out && !enough) { status = "TIMEOUT"; cnt = "null"; complete = false; }
        else {
            complete = true; status = R.count ? "SOLVED" : "UNSAT";
            long long c = R.count;
            if (mode == "first") c = c ? 1 : 0; else if (mode == "classify") c = std::min<long long>(c, 2);
            cnt = std::to_string(c);
        }
        printf("{\"id\":\"%s\",\"status\":\"%s\",\"count\":%s,\"complete\":%s,\"nodes\":%lld,\"forced\":%lld,\"elims\":%lld,\"elapsed\":%.9f,\"elapsed_all\":[",
               id.c_str(), status, cnt.c_str(), complete ? "true" : "false", R.nodes, R.forced, R.elims, med);
        for (size_t i = 0; i < times.size(); i++) printf("%s%.9f", i ? "," : "", times[i]);
        printf("],\"solutions\":[");
        for (size_t i = 0; i < R.sols.size(); i++) {
            printf("%s[", i ? "," : "");
            for (size_t j = 0; j < R.sols[i].size(); j++) printf("%s%d", j ? "," : "", R.sols[i][j]);
            printf("]");
        }
        printf("]%s%s}\n", err.empty() ? "" : ",\"error\":\"", err.empty() ? "" : (err + "\"").c_str());
        fflush(stdout);
    }
    return 0;
}
