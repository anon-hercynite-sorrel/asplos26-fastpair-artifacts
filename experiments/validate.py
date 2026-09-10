# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Check declared numeric claims against the committed measurements.

    uv run experiments/validate.py

Uses the same common.py and suite.py reductions as the figures. Exits nonzero
if a value is outside its declared range or fewer than EXPECTED_CHECKS run.
See METHODOLOGY.md for conventions and MANIFEST.md for capture provenance.
"""
import csv
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "figures"))
import common as C  # noqa: E402
import suite as S  # noqa: E402

FAILS = []
ROWS = []
# The full green set re-derives exactly this many checks. Several blocks are guarded and
# silently contribute nothing if their results file is missing or unreadable -- so a count below
# this means the reproduction is INCOMPLETE, not passing. main() fails loud on a shortfall rather
# than printing a false "all green".
#
# 77 supporting checks, including five token-length checks. The 18 historical pipeline checks
# were replaced by experiments/check_pipes.py, which validates the current
# selected boost captures and five-bin figure. make analyze runs both checkers.
EXPECTED_CHECKS = 77


def check(name, got, lo, hi, unit="", note=""):
    """Record a check: pass iff lo <= got <= hi."""
    ok = got is not None and lo <= got <= hi
    ROWS.append((name, got, f"[{lo:g}, {hi:g}]", unit, ok, note))
    if not ok:
        FAILS.append(name)
    return ok


# Legacy-corpus join keys: (summary file, column, DE dataset_id).
COLS = [
    ("tpch-sf10", "l_comment", "tpch-sf10"),
    ("tpch-sf10", "ps_comment", "tpch-sf10"),
    ("lship", "l_shipinstruct", "tpch-sf10"),
    ("synthetic", "url", "synthetic"),
    ("clickbench", "URL", "clickbench"),
    ("fineweb", "text", "fineweb"),
    ("wikipedia", "text", "wikipedia"),
    ("book-reviews", "text", "book-reviews"),
    ("amazon-movies", "text", "amazon-movies"),
    ("amazon-electronics", "text", "amazon-electronics"),
]



def main():
    print("Re-deriving headline numbers from results/ (via figures/common.py)\n")

    # Check the table/figure length reducer against the independently recorded
    # occurrence-weighted dictionary statistic across the declared B300 corpus.
    root = S.chip_root("b300")
    stores = {codec: S.cells(root, "b300", "boost", codec)
              for codec in ("onpair", "fsst12")}
    length_cells = []
    for _, ds, col in S.REAL + S.GEN:
        for codec, bits in (("onpair", 16), ("onpair", 12), ("fsst12", 12)):
            c = stores[codec].get((ds, col, bits))
            if c is not None:
                length_cells.append(c)
    check("token length: B300 corpus coverage", len(length_cells), 45, 45, "cells")
    errors = []
    payload_matches = 0
    for c in length_cells:
        g = c.get("gpu") or {}
        mean, recorded = S.mean_len(c), g.get("dict_mean_len")
        errors.append(abs(mean / recorded - 1) if mean and recorded else float("inf"))
        payload_matches += c.get("sample_bytes") is not None and c["sample_bytes"] == g.get("decoded_bytes")
    check("token length: matches recorded weighted mean", max(errors, default=float("inf")),
          0, 1e-6, "relative")
    check("token length: sample bytes match decoded payload", payload_matches, 45, 45, "cells")
    # Every o_clerk value has 15 bytes: one OnPair-16 code or four FSST-12 codes.
    for codec, bits, expected in (("onpair", 16, 15.0), ("fsst12", 12, 3.75)):
        c = stores[codec].get(("tpch-sf45", "o_clerk", bits))
        check(f"token length: o_clerk {codec}-{bits}", S.mean_len(c), expected, expected, "B/code")

    # Current fig:pipes uses the best-configuration boost recapture. Its raw-counter
    # accounting and selection checks live in check_pipes.py (run by make analyze).
    # The historical ncu-costsurface-v2.csv is retained only as archived evidence.

    # 11. FSST-12 generality (§6.4, §1, §7). Until 2026-08-14 NOTHING here was checked, and
    #     three published numbers had silently drifted: the rate range was still B300+H100-only
    #     after the other two chips landed, the compression-ratio range read 0.72-0.81x where
    #     the data gives 0.74-0.84x, and the OnPair-16 margin read 1.06-1.23x (B300) where four
    #     chips give 1.12-1.61x. These checks exist so that cannot recur silently.
    #
    #     The OnPair comparator is same_run_onpair(), NOT cell(..., ONPAIR): the former is the
    #     OnPair cell measured on the same box in the same session, the latter is the canonical
    #     matrix entry from an earlier send. Using the wrong one shifts every ratio.
    TEXT5 = [("fineweb", "text"), ("wikipedia", "text"), ("book-reviews", "text"),
             ("amazon-movies", "text"), ("amazon-electronics", "text")]
    GPUS4 = ("b300", "h100", "l40s", "a100")

    def fsst_rate_ratios(bits):
        """FSST-12 / OnPair-<bits> decode rate, over the five text columns x four GPUs."""
        out = {}
        for g in GPUS4:
            rs = []
            for ds, col in TEXT5:
                f = C.best_shipped(C.cell(g, ds, col, 12, C.FSST12))
                o = C.best_shipped(C.same_run_onpair(g, ds, col, bits))
                if f and o:
                    rs.append(f / o)
            if rs:
                out[g] = rs
        return out

    r12 = fsst_rate_ratios(12)
    if len(r12) == len(GPUS4) and all(len(v) == len(TEXT5) for v in r12.values()):
        flat = [x for v in r12.values() for x in v]
        check("FSST-12: cells present (5 columns x 4 GPUs)", float(len(flat)), 20, 20, "cells")
        check("FSST-12 / OnPair-12: min over 4 GPUs", min(flat), 0.90, 0.93, "x", "§6: 0.91 to 1.11x")
        check("FSST-12 / OnPair-12: max over 4 GPUs", max(flat), 1.09, 1.13, "x", "§6: 0.91 to 1.11x")
        # The A100 inversion is the load-bearing claim: it is the ONE chip where FSST-12 beats
        # OnPair-12 on every one of the five columns, which §6 reads as the access-width account.
        check("FSST-12: A100 beats OnPair-12 on all five",
              1.0 if all(x > 1.0 for x in r12["a100"]) else 0.0, 1, 1, "bool",
              "§6 attributes this to the split's common path plus the narrowest L1 headroom")
        check("FSST-12: A100 min", min(r12["a100"]), 1.00, 1.04, "x", "§6: 1.02 to 1.11x on the A100")
        check("FSST-12: A100 max", max(r12["a100"]), 1.09, 1.13, "x")
        # ... and the other three chips must NOT invert, or the A100 sentence is not a contrast.
        check("FSST-12: B300/H100/L40S do not invert",
              1.0 if all(x <= 1.02 for g in ("b300", "h100", "l40s") for x in r12[g]) else 0.0,
              1, 1, "bool")

    r16 = fsst_rate_ratios(16)
    if len(r16) == len(GPUS4) and all(len(v) == len(TEXT5) for v in r16.values()):
        flat16 = [x for v in r16.values() for x in v]
        check("FSST-12 / OnPair-16: min over 4 GPUs", min(flat16), 1.10, 1.14, "x", "§6: 1.12 to 1.61x")
        check("FSST-12 / OnPair-16: max over 4 GPUs", max(flat16), 1.59, 1.63, "x", "§6: 1.12 to 1.61x")
        check("FSST-12 exceeds OnPair-16 on every cell",
              1.0 if all(x > 1.0 for x in flat16) else 0.0, 1, 1, "bool")

    # Compression ratio, container-matched: the basis §6 and tab:datasets now state explicitly.
    cr = []
    for ds, col in TEXT5:
        f = C.cell("b300", ds, col, 12, C.FSST12)
        o = C.same_run_onpair("b300", ds, col, 12)
        if f and o and f.get("mem_ratio_container_matched") and o.get("mem_ratio"):
            cr.append(f["mem_ratio_container_matched"] / o["mem_ratio"])
    if len(cr) == len(TEXT5):
        check("FSST-12 ratio / OnPair-12 ratio: min", min(cr), 0.72, 0.76, "x", "§6: 0.74 to 0.84x")
        check("FSST-12 ratio / OnPair-12 ratio: max", max(cr), 0.82, 0.86, "x", "§6: 0.74 to 0.84x")

    # The two ratio bases (FSST-12's own fixed 12-bit packing vs the container OnPair's codes
    # pass through) agree on the five REAL TEXT columns the paper evaluates, which is why the
    # basis choice moves no reported number.
    #
    # The scope is exactly those five, NOT "high-cardinality columns": TPC-H p_name has 2.0M
    # distinct values and still diverges 1.34x, because BtrBlocks compresses a structured code
    # stream further than a fixed 12-bit packing regardless of cardinality. An earlier version
    # of this check asserted the agreement over everything above 100k distinct and failed on
    # exactly that column. Cardinality is one driver of the divergence, not the only one.
    agree = []
    for ds, col in TEXT5:
        c = C.cell("b300", ds, col, 12, C.FSST12)
        if c and c.get("mem_ratio") and c.get("mem_ratio_container_matched"):
            agree.append(c["mem_ratio_container_matched"] / c["mem_ratio"])
    diverge = []
    for f in sorted((C.RESULTS / "b300-fsst12").glob("*.json")):
        for c in json.load(open(f)):
            if c.get("codec") != C.FSST12:
                continue
            n, m = c.get("mem_ratio"), c.get("mem_ratio_container_matched")
            if n and m and (c["dataset_id"], c["column"]) not in TEXT5:
                diverge.append(m / n)
    if agree and diverge:
        check("ratio bases agree on the five evaluated text columns", max(agree), 0.99, 1.01, "x",
              "the basis choice moves no number the paper reports")
        check("ratio bases diverge elsewhere", max(diverge), 100, 2000, "x",
              "READMEs said 3.3x; fineweb/language (1 distinct) is 906x")

    # Every FSST-12 cell is byte-exact against the CPU reference -- the generality claim is
    # "decodes byte for byte through the shipped kernels", so a single false here voids it.
    ver = []
    for g in GPUS4:
        d = C.RESULTS / ("%s-fsst12" % g)
        if not d.is_dir():
            continue
        for f in sorted(d.glob("fsst12_summary_*.json")):
            ver += [bool(c.get("verified")) for c in json.load(open(f))
                    if c.get("codec") == C.FSST12]
    if ver:
        check("FSST-12: every cell byte-exact", 1.0 if all(ver) else 0.0, 1, 1, "bool",
              f"{sum(ver)}/{len(ver)} verified")

    # 12. Fused output positioning (results/b300-fusedstall/). §3.2 justifies the stored
    #     sidecar against regeneration as a SEPARATE pass; the reviewer's reply is to fuse
    #     regeneration into the decode. Measured here, and slow -- but only meaningful
    #     because the kernel is byte-exact AND because the obvious objection (our block-wide
    #     stall) was removed and changed nothing.
    fs_dir = C.RESULTS / "b300-fusedstall"
    if fs_dir.is_dir():
        SHIPPED = "onpair_shmem_4tpt_split8read"
        rel = {}
        for f in sorted(fs_dir.glob("fusedstall_summary_*.json")):
            for c in json.load(open(f)):
                g = c.get("gpu") or {}
                km = {k.get("kernel"): k for k in g.get("kernels", []) if k.get("applicable")}
                base = (km.get(SHIPPED) or {}).get("decode_gib_s")
                if not base:
                    continue
                for name in (SHIPPED + "_lookback", SHIPPED + "_lookback_noshift",
                             SHIPPED + "_lookback_w1", SHIPPED + "_stcsedge"):
                    k = km.get(name)
                    if k and k.get("decode_gib_s"):
                        # An unverified rate must never reach a check: that is the whole
                        # reason the experimental kernels are excluded from best_kernel.
                        if not k.get("verified"):
                            continue
                        rel.setdefault(name, []).append(k["decode_gib_s"] / base)
        gm = lambda v: statistics.geometric_mean(v)
        b = rel.get(SHIPPED + "_lookback")
        n = rel.get(SHIPPED + "_lookback_noshift")
        w1 = rel.get(SHIPPED + "_lookback_w1")
        e = rel.get(SHIPPED + "_stcsedge")
        if b and n:
            check("fused positioning: base vs shipped", gm(b), 0.30, 0.40, "x",
                  "about 2.9x slower; §3.2's third option")
            check("fused positioning: stall removed", gm(n), 0.30, 0.40, "x")
            # The load-bearing one: removing the stall must change ~nothing, or the
            # paper's claim that the stall is not the cost is wrong.
            check("fused positioning: removing the stall changes nothing", gm(n) / gm(b),
                  0.97, 1.03, "x", "hypothesis was that this would be >1")
        if b and w1:
            # Second, independent refutation: no-stall-at-all is the WORST configuration.
            check("fused positioning: 1 warp/block is worse, not better", gm(w1) / gm(b),
                  0.35, 0.50, "x", "narrowing removes the idle and loses 2.3x")
        if e:
            check("streaming drain edges: no effect", gm(e), 0.98, 1.02, "x",
                  "head+tail policy change is inside dispersion")
        # Disjoint dictionary halves: §4 discloses that the shipped kernel holds each
        # entry's low eight bytes twice, and now states what that costs in RATE, not only
        # in footprint. Small, and the paper says so; the check keeps "small" honest.
        hi = []
        for f in sorted(fs_dir.glob("fusedstall_summary_*.json")):
            for c in json.load(open(f)):
                km = {k.get("kernel"): k for k in ((c.get("gpu") or {}).get("kernels") or [])
                      if k.get("applicable")}
                base = (km.get(SHIPPED) or {}).get("decode_gib_s")
                k = km.get(SHIPPED + "_hilo")
                if base and k and k.get("decode_gib_s") and k.get("verified"):
                    hi.append(k["decode_gib_s"] / base)
        if hi:
            check("disjoint dict halves: small gain", gm(hi), 1.01, 1.05, "x",
                  "§4: 1.02 to 1.03x; the duplicate costs rate as well as footprint")

    # 13. Access-width isolation on the EVALUATED columns (§5.3). The claim is that
    #     split8read narrows each access rather than making the table more cache-resident,
    #     and it rests on two counters moving in OPPOSITE ways: wavefronts down about a
    #     quarter while sector count stays flat. A hit-rate move of a couple of points
    #     cannot produce a wavefront reduction of 23%, which is the whole argument.
    #
    #     The A100 leg needed an explicit --metrics pass: `--set full` omits both counters
    #     on sm_80, which is why this was a three-chip result until 2026-08-15.
    def width_ratio(chip, col, metric):
        import csv as _csv, io as _io
        d = C.RESULTS / ("%s-widthncu-eval" % chip)
        if not d.is_dir():
            return None
        vals = {}
        for variant, tag in (("split8read", "s"), ("onpair_shmem_4tpt", "t")):
            f = d / ("shdict_ncu_%s_text_b12_%s_width.csv" % (col, variant))
            if not f.exists():
                f = d / ("shdict_ncu_%s_text_b12_%s_raw.csv" % (col, variant))
            if not f.exists():
                return None
            txt = f.read_text(errors="replace")
            i = txt.find('"ID","Process ID"')
            if i < 0:
                return None
            got = []
            for r in _csv.DictReader(_io.StringIO(txt[i:])):
                if r.get("Metric Name") == metric:
                    try:
                        got.append(float((r.get("Metric Value") or "").replace(",", "")))
                    except ValueError:
                        pass
                elif metric in (r.keys() if hasattr(r, "keys") else []):
                    pass
            if not got:
                # raw-page CSVs carry metrics as COLUMNS, not rows
                rows = list(_csv.reader(_io.StringIO(txt[i:])))
                hdr = [h.split(".TriageCompute.")[-1] for h in rows[0]]
                if metric not in hdr:
                    return None
                j = hdr.index(metric)
                for rr in rows[2:]:
                    try:
                        got.append(float(rr[j].replace(",", "")))
                    except (ValueError, IndexError):
                        pass
            if not got:
                return None
            vals[tag] = statistics.median(got)
        return (vals["s"] / vals["t"]) if vals.get("t") else None

    def width_delta_pts(chip, col, metric):
        """split8read minus stride-16, in percentage points (not a ratio)."""
        import csv as _csv, io as _io
        d = C.RESULTS / ("%s-widthncu-eval" % chip)
        vals = {}
        for variant, tag in (("split8read", "s"), ("onpair_shmem_4tpt", "t")):
            f = d / ("shdict_ncu_%s_text_b12_%s_width.csv" % (col, variant))
            if not f.exists():
                return None
            txt = f.read_text(errors="replace")
            i = txt.find('"ID","Process ID"')
            if i < 0:
                return None
            got = []
            for r in _csv.DictReader(_io.StringIO(txt[i:])):
                if r.get("Metric Name") == metric:
                    try:
                        got.append(float((r.get("Metric Value") or "").replace(",", "")))
                    except ValueError:
                        pass
            if not got:
                return None
            vals[tag] = statistics.median(got)
        return vals["s"] - vals["t"]

    WAVE = "l1tex__data_pipe_lsu_wavefronts.sum"
    SECT = "l1tex__t_sectors.sum"
    for chip in ("b300", "a100", "h100", "l40s"):
        for col in ("fineweb", "wikipedia"):
            wv = width_ratio(chip, col, WAVE) or width_ratio(chip, col,
                                                             "l1tex__data_pipe_lsu_wavefronts.avg")
            sc = width_ratio(chip, col, SECT)
            if wv:
                # The L40S reduction is real but SMALLER (0.84) than the HBM parts' 0.77,
                # and its hit rate moves ~8 points rather than under 3, so that chip
                # corroborates the direction without isolating width from residency.
                # Asserting one band for all four would either fail or be too loose to mean
                # anything, so the bands differ and §5.3 says why.
                lo, hi = (0.81, 0.88) if chip == "l40s" else (0.74, 0.81)
                check("width %s/%s: wavefronts fall" % (chip, col), wv, lo, hi, "x",
                      "split8read / stride-16; the narrowing")
            if sc:
                # The control. If sectors moved with wavefronts, the gain would be bytes,
                # not access width, and the mechanism claim would not hold.
                check("width %s/%s: sectors flat" % (chip, col), sc, 0.99, 1.02, "x",
                      "same bytes, fewer accesses")
            # The OTHER control, and the one §5.3's isolation actually rests on: on the
            # L1-bound parts the hit rate must move too little to explain a ~23% wavefront
            # drop. On the L40S it moves ~8 points and the paper says the two terms are not
            # separated there, so that chip is asserted to be the exception rather than
            # quietly averaged in with the rest.
            hr = width_delta_pts(chip, col, "l1tex__t_sector_hit_rate.pct")
            if hr is not None:
                lo, hi = (5.0, 12.0) if chip == "l40s" else (0.0, 3.0)
                check("width %s/%s: hit-rate move (pts)" % (chip, col), hr, lo, hi, "pts",
                      "residency cannot explain the drop where this is small")

    # 10. Token access distribution (Appendix A). Every number the appendix quotes in prose,
    # re-derived through common.freq_* -- the same reduction fig_freqbars draws, so the figure,
    # the prose and the JSON cannot drift apart. This appendix had NO coverage until
    # 2026-08-20, the same exposure that let three FSST-12 numbers in §6 drift unnoticed.
    try:
        fd = C.freqdist()

        # "the 256 most-read entries serve 81% of FSST-12's decoded codes, 35% of OnPair-12's
        # and 13% of OnPair-16's; a thousand entries serve all of FSST-12's, 72% ... and 24%"
        for codec, at256, at1k in (("fsst-12", (80, 82), (99.5, 100)),
                                   ("onpair-12", (34.5, 36), (71, 73)),
                                   ("onpair-16", (13, 14), (24, 25))):
            r = C.freq_record(fd, "l_comment", codec)
            check("freq l_comment/%s: top-256 coverage" % codec, C.freq_at(r, 256),
                  at256[0], at256[1], "%", "appendix A prose")
            check("freq l_comment/%s: top-1024 coverage" % codec, C.freq_at(r, 1024),
                  at1k[0], at1k[1], "%", "appendix A prose")

        # "1026 entries against OnPair-12's 3862 on l_comment, and 870 against 2214 on naics_name"
        for col, codec, want in (("l_comment", "fsst-12", 1026), ("l_comment", "onpair-12", 3862),
                                 ("cg_naics_name", "fsst-12", 870),
                                 ("cg_naics_name", "onpair-12", 2214)):
            got = C.freq_record(fd, col, codec)["entries_referenced"]
            check("freq %s/%s: entries referenced" % (col, codec), float(got),
                  want, want, "", "appendix A prose")

        # "376 entries, 2165 and 26866" to cover 90%, i.e. "37% of FSST-12's table, 56% of
        # OnPair-12's and 48% of OnPair-16's". Interpolated, not nearest-sample: see
        # common.freq_entries_for, which inverts the curve the way the figure reads it forward.
        for codec, ent, frac in (("fsst-12", (374, 378), (36, 38)),
                                 ("onpair-12", (2160, 2172), (55, 57)),
                                 ("onpair-16", (26800, 26930), (47, 49))):
            r = C.freq_record(fd, "l_comment", codec)
            e90 = C.freq_entries_for(r, 90)
            check("freq l_comment/%s: entries for 90%%" % codec, e90, ent[0], ent[1],
                  "entries", "appendix A prose")
            check("freq l_comment/%s: 90%% as share of table" % codec,
                  100.0 * e90 / r["entries_referenced"], frac[0], frac[1], "%",
                  "appendix A prose")

        # "covering 90% of the reads takes between 15 and 59% of the entries" -- the LOW end
        # does not re-derive: the minimum over all (column, codec) is 13.8%, on
        # cg_naics_name/OnPair-16. Asserted against the DATA rather than against the prose, so
        # the discrepancy stays visible. Fix the sentence to "14 to 59%", or recompute it if the
        # appendix is rescoped to the locked corpus, which drops that column entirely.
        shares = [100.0 * C.freq_entries_for(r, 90) / r["entries_referenced"] for r in fd]
        check("freq: min 90% share of table", min(shares), 13.5, 14.2, "%",
              "prose says 15%; data says 13.8% on cg_naics_name/OnPair-16")
        check("freq: max 90% share of table", max(shares), 58, 59.5, "%", "prose: 59%")

        # "that hot set stays under 19 KB on every column at OnPair-12 and FSST-12 alike",
        # charging each entry the eight bytes of a dense plane. OnPair-16 "does not: on the five
        # columns whose dictionaries fill, its hot set is 191 to 299 KB".
        for codec in ("fsst-12", "onpair-12"):
            worst = max(8.0 * C.freq_entries_for(r, 90) / 1024.0
                        for r in fd if r["codec"] == codec)
            check("freq %s: worst 90%% hot set" % codec, worst, 0, 19, "KiB",
                  "appendix A: under 19 KB on every column")
        big = sorted((8.0 * C.freq_entries_for(r, 90) / 1024.0
                      for r in fd if r["codec"] == "onpair-16"), reverse=True)[:5]
        check("freq onpair-16: 5th largest hot set", big[-1], 190, 195, "KiB", "appendix A: 191 KB")
        check("freq onpair-16: largest hot set", big[0], 295, 302, "KiB", "appendix A: 299 KB")

        # "On Wikipedia only 2% of accesses reach the high plane and 90% of those come from
        # 1.1 KB. On l_comment 42% ... from 8.8 KB. On naics_name 79% ... 1.9 KB against the
        # low plane's 3.1 KB." Checked in BYTES: the appendix's KB are binary (9048 B reads as
        # 8.8), so asserting on the raw counter keeps a unit slip out of the check itself.
        for col, frac, hib, lob in (("wikipedia", (1.5, 2.5), (1150, 1200), None),
                                    ("l_comment", (41, 43), (9000, 9100), None),
                                    ("cg_naics_name", (78, 80), (1950, 2000), (3150, 3200))):
            r = C.freq_record(fd, col, "onpair-12")
            check("freq %s: high-plane access share" % col, 100.0 * r["hi_access_frac"],
                  frac[0], frac[1], "%", "appendix A prose")
            check("freq %s: high-plane 90%% bytes" % col, float(r["hi_bytes_90"]),
                  hib[0], hib[1], "B", "appendix A prose")
            if lob:
                check("freq %s: low-plane 90%% bytes" % col, float(r["lo_bytes_90"]),
                      lob[0], lob[1], "B", "appendix A prose")
    except FileNotFoundError:
        pass

    # ── report ──
    w = max(len(r[0]) for r in ROWS)
    print(f"{'check':<{w}}  {'derived':>11}  {'expected':>14}  result")
    print("-" * (w + 40))
    for name, got, exp, unit, ok, note in ROWS:
        gs = f"{got:.3f} {unit}".strip() if isinstance(got, float) else str(got)
        print(f"{name:<{w}}  {gs:>11}  {exp:>14}  {'PASS' if ok else 'FAIL'}"
              + (f"   ({note})" if note and not ok else ""))
    print("-" * (w + 40))
    print(f"{len(ROWS)} checks, {len(FAILS)} failed")
    if len(ROWS) < EXPECTED_CHECKS:
        print(f"INCOMPLETE: only {len(ROWS)}/{EXPECTED_CHECKS} checks ran -- a results file is "
              "missing or unreadable, so guarded checks were silently skipped. This is a "
              "failure, not a pass.")
        sys.exit(1)
    if FAILS:
        print("FAILED:", ", ".join(FAILS))
        sys.exit(1)
    print(f"all {len(ROWS)} headline numbers re-derive from committed data ✓")



if __name__ == "__main__":
    main()
