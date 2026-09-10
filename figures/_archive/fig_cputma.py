# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. cputma: the dependency/ILP split on the CPU, as Top-Down slots.

Linux-perf Top-Down of the OnPair decode hot loop, fixed-stride (fat, one independent indexed load)
vs variable-stride (entries, OnPair's dependent offset->bytes chain), swept across
1/4/8 threads on the two ISAs that expose a native Top-Down tree (Intel Sapphire, Arm Graviton4).
The fixed-stride layout retires a higher fraction of issue slots and stalls the backend less; the
dependent gather serializes on load latency and is more backend-bound. The split holds and, on Arm,
widens with thread count. Column: fineweb_text (gather-dominated), dict-12.
Source: results/cpu-tma/{intel-sapphire,arm-graviton4}_raw.tar.gz (perf stat --topdown).
"""
import re
import tarfile
import numpy as np
import common as C

CSURF = C.RESULTS / "cpu-tma"
ISAS = [("intel-sapphire", "Intel Sapphire Rapids"), ("arm-graviton4", "Arm Graviton4")]
THREADS = [1, 4, 8]
COL, BITS = "fineweb_text", 12
# fat is the protagonist (the fixed-stride win); entries is the baseline it beats.
FAT, ENT = C.PRIMARY, C.WARM


def topdown(tar, member):
    """(retiring%, backend_bound%) from the first '-- topdown --' block of a perf file.
    Aligns header metric tokens to the values row, so Intel's and Arm's differing column
    orders both parse."""
    txt = tar.extractfile(member).read().decode("utf-8", "ignore")
    block = txt.split("-- topdown --", 1)[1].split("-- topdown L2", 1)[0]
    lines = block.splitlines()
    for i, ln in enumerate(lines):
        if "retiring" in ln and ("tma_" in ln or "percent of slots" in ln):
            names = [n.replace("tma_", "") for n in
                     re.findall(r"tma_\w+|bad_speculation|retiring|frontend_bound|backend_bound", ln)]
            for nxt in lines[i + 1:]:
                vals = [float(x) for x in re.findall(r"\d+\.\d+", nxt)]
                if len(vals) >= len(names):
                    d = dict(zip(names, vals))
                    return d.get("retiring"), d.get("backend_bound")
    raise KeyError("no topdown block in %s" % member)


def read_isa(isa):
    """{layout: {thread: (retiring, backend)}} for the chosen column/bits."""
    out = {"fat": {}, "entries": {}}
    with tarfile.open(CSURF / ("%s_raw.tar.gz" % isa)) as tar:
        names = tar.getnames()
        for layout in out:
            for t in THREADS:
                want = "perf-%s-b%d-%dt-%s.txt" % (COL, BITS, t, layout)
                m = next((n for n in names if n.endswith(want)), None)
                if m:
                    out[layout][t] = topdown(tar, m)
    return out


RET, BE, OTHER = "#4393c3", "#e08214", "#d9d9d9"  # retiring / back-end-bound / other slots


def main():
    plt = C.apply_theme()
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.15), sharey=True)
    # two bars (fixed-stride, variable-stride) per core-count, grouped in pairs.
    pos, ticks, labs = [], [], []
    for gi, t in enumerate(THREADS):
        base = gi * 2.4
        pos += [base, base + 0.9]
        ticks += [base, base + 0.9]
        labs += ["fixed\n%dc" % t, "var.\n%dc" % t]
    for ax, (isa, title) in zip(axes, ISAS):
        d = read_isa(isa)
        for gi, t in enumerate(THREADS):
            for k, layout in enumerate(("fat", "entries")):
                ret, be = d[layout][t]
                other = max(0.0, 100.0 - ret - be)
                x = pos[gi * 2 + k]
                ax.bar(x, ret, 0.8, color=RET, zorder=3)
                ax.bar(x, be, 0.8, bottom=ret, color=BE, zorder=3)
                ax.bar(x, other, 0.8, bottom=ret + be, color=OTHER, zorder=3)
                ax.text(x, ret / 2, "%d" % round(ret), ha="center", va="center", color="white", fontsize=6)
                ax.text(x, ret + be / 2, "%d" % round(be), ha="center", va="center", color="white", fontsize=6)
        ax.set_title(title, fontsize=8)
        ax.set_xticks(ticks); ax.set_xticklabels(labs, fontsize=6)
        ax.set_ylim(0, 100)
        ax.grid(axis="y", color="#e6e6e6", lw=0.7, zorder=0); ax.set_axisbelow(True)
    axes[0].set_ylabel("% of issue slots")
    from matplotlib.patches import Patch
    leg = [Patch(fc=RET, label="retiring (useful work)"), Patch(fc=BE, label="back-end-bound (stall)"),
           Patch(fc=OTHER, label="other")]
    fig.legend(handles=leg, frameon=False, fontsize=6.5, ncol=3, loc="lower center",
               handlelength=1.1, columnspacing=1.4, bbox_to_anchor=(0.5, -0.04))
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    C.save(fig, "fig_cputma")


if __name__ == "__main__":
    main()
