# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. tokendist: the rank-frequency curve of every column's dictionary reads.

WHY A DISTRIBUTION AND NOT A STATISTIC. An earlier version of this material summarised each
column to one number, the entropy of its code-reference distribution over the maximum. That
number does not separate the groups: at OnPair-12 the generated columns span 0.79 to 1.00 and the
real ones 0.55 to 0.93, and Loghub Windows, a real column, reads lower than either of the two
generated columns the codec inverts. A summary that overlaps cannot carry the claim, so this
draws the shape it was computed from and lets the reader see whether the groups differ.

WHAT ONE PANEL IS. Every distinct code the column uses, sorted by how often it is referenced,
descending, on a log frequency axis. A uniform distribution is a flat line; a Zipfian one falls
away. Panels are independent: each autoscales to its own column, because the columns differ by
four orders of magnitude in both code count and reference count, and a shared axis would flatten
every panel but the largest into a line.

NO SHARED SCALE MEANS NO CROSS-PANEL MAGNITUDE CLAIM. The comparison this figure supports is of
SHAPE. A reader cannot read "more references" off it, and nothing in the paper asks them to.

Source: results/token-freqdist-corpus/<column>.op12.txt, one count per line, sorted descending,
emitted by encodings/onpair-sys/examples/onpair_skew.rs under FREQ_OUT. OnPair-12 only: at twenty
panels this size three overlaid curves are not legible, and the codec changes how far the tail
runs rather than the shape of its head.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import suite as S  # noqa: E402

FLOOR = 1e-7

SRC = Path(__file__).resolve().parent.parent / "results" / "token-freqdist-corpus"

# AXIS FLOOR, and the fill baseline shares it. Normalised counts, so this is a frequency relative
# to the column's hottest code. At 1e-6 the rarest codes fell off the bottom -- 47 of Windows'
# 3569, 12 each of CodeParrot and ghgit_author -- and because the dense panels are filled
# silhouettes rather than bars, a curve that meets the floor reads as a tail that ENDS instead of
# one that continues below the frame. On a figure whose whole claim is the shape of these curves,
# that is the one artifact worth spending an axis decade on. ONE decade is the right price: the
# smallest normalised frequency anywhere in the corpus is 2.45e-07 (Windows), so 1e-7 draws every
# code in every column. 1e-8 also works and is worse -- two spare decades flatten every
# silhouette toward the top of its panel and cost the shape contrast the figure exists for.

# (file stem, display label, group). A leading * on the label means the paper sets that name in
# \texttt, so the panel label is drawn monospace to match; the star is stripped before drawing.
# Order is the reading order of the grid.
PANELS = [
    ("FineWeb2", "FineWeb2", "real"), ("Wikipedia", "Wikipedia", "real"),
    ("CodeParrot", "CodeParrot", "real"), ("Android", "*Android", "real"),
    ("URL", "*URL", "real"), ("Title", "*Title", "real"),
    ("HDFS", "*HDFS", "real"), ("Thunderbird", "*Thunderbird", "real"),
    ("Spark", "*Spark", "real"), ("Windows", "*Windows", "real"),
    ("hn_by", "*hn_by", "real-short"), ("amz_product_id", "*amz_product_id", "real-short"),
    ("cb_PageCharset", "*PageCharset", "real-short"),
    ("ghgit_author", "*ghgit_author", "real-short"),
    ("amz_review_id", "*amz_review_id", "real-short"),
    ("c_address", "*c_address", "generated"), ("l_comment", "*l_comment", "generated"),
    ("o_clerk", "*o_clerk", "generated"), ("l_shipinstruct", "*l_shipinstruct", "generated"),
    ("ps_comment", "*ps_comment", "generated"),
]
NCOL, NROW = 4, 5
# COLUMN-MAJOR fill: panels go down a column before moving right. That is what makes a 4x5 grid
# hold these three groups, since 10 + 5 + 5 lands as two whole columns, one, and one. Filling
# row-major instead splits every group across a row boundary.


def stats():
    """{file stem: (mean value bytes, codes per value at OnPair-12)}.

    THE FIFTEEN CORPUS COLUMNS COME FROM suite.py, like every other figure in this directory,
    so these labels carry the same numbers as tab:datasets and the rest of the paper rather than
    a second derivation of them. Value bytes is sample_bytes/rows and codes per value is that
    over suite.mean_len.

    The five short real columns are not in the campaign suite -- they were never benchmarked,
    only encoded -- so those five alone read from summary.txt, the encode probe's own stdout.
    That split is the reason this returns a dict instead of asking suite for everything.
    """
    out = {}
    root = S.latest_root(None)
    cells = S.cells(root, "b300", "boost", "onpair")
    corpus = [(p[0], r) for p, r in
              zip(PANELS[:10], S.REAL)] + [(p[0], r) for p, r in zip(PANELS[15:], S.GEN)]
    for stem, (_, ds, col) in corpus:
        c = cells.get((ds, col, 12))
        if not c:
            continue
        vb = c["sample_bytes"] / c["rows"]
        out[stem] = (vb, vb / S.mean_len(c))
    for line in (SRC / "summary.txt").read_text().splitlines():
        f = line.split()
        if len(f) < 5 or f[0] == "column" or f[0] in out:
            continue
        try:
            out[f[0]] = (float(f[2]), float(f[4]))
        except ValueError:
            continue
    return out


def _fmt(x):
    """Integer above 100, one decimal below: a tenth of a byte or of a code is noise at 3,716."""
    return ("%d" % round(x)) if x >= 100 else ("%.1f" % x)


def counts(stem):
    f = SRC / ("%s.op12.txt" % stem)
    if not f.exists():
        return None
    return [int(x) for x in f.read_text().split()]


def main():
    meta = stats()
    plt = C.apply_theme()
    fig, axes = plt.subplots(NROW, NCOL, figsize=(7.0, 4.0))
    missing = []
    order = axes.T.ravel()   # column-major
    for ax, (stem, label, group) in zip(order, PANELS):
        v = counts(stem)
        if not v:
            missing.append(stem)
            ax.set_axis_off()
            continue
        colour = C.colour("corpus", group)
        # NORMALISED BY THE PANEL'S OWN MAXIMUM, on a fixed decade range. Autoscaling each panel
        # to its own counts inverts the figure's meaning on exactly the column it exists to
        # show: l_shipinstruct's five codes are referenced 20.84 million times each, differing by
        # 0.06%, and a log axis fitted to that span magnifies the difference into a full-height
        # staircase -- the one perfectly uniform column drawn as the most skewed one. Dividing by
        # the maximum puts a uniform column flat along the top and lets a Zipfian one fall away,
        # which is the comparison, and a fixed range keeps that reading the same in every panel.
        top = v[0]
        y = [c / top for c in v]
        if len(v) > 64:
            # A FILLED POLYGON, not bars. Twenty panels of a few thousand vector rectangles was
            # seventy thousand paths and a page slow to render, so these are rasterized -- but
            # rasterizing BARS aliased badly: at 0.85 width their sub-pixel gaps beat against
            # the pixel grid and drew moire stripes, so FineWeb2's four thousand codes came out
            # looking like six. A polygon has no gaps to alias, rasterizes cleanly, and is the
            # right primitive for a silhouette nobody reads bar by bar.
            ax.fill_between(range(len(v)), FLOOR, y, color=colour, linewidth=0, rasterized=True)
        else:
            # Few enough codes to read individually, which is the point on these columns: five
            # equal bars against five falling ones. Vector, and the gaps are deliberate.
            ax.bar(range(len(v)), y, width=0.85, linewidth=0, color=colour)
        ax.set_yscale("log")
        ax.set_ylim(FLOOR, 2.0)
        ax.set_xlim(-0.5, len(v) - 0.5)
        # No ticks, no numbers, no grid: twenty panels of shape, identified by name alone.
        # Minor ticks have to go explicitly -- a log axis re-adds them after set_yticks([]),
        # which is what leaked a column of numbers into the l_shipinstruct panel.
        ax.set_xticks([])
        ax.set_yticks([])
        ax.tick_params(which="both", left=False, right=False, top=False, bottom=False,
                       labelleft=False, labelbottom=False)
        ax.yaxis.set_minor_locator(plt.NullLocator())
        ax.grid(False)
        for side in ("top", "right", "left", "bottom"):
            ax.spines[side].set_visible(True)
            ax.spines[side].set_linewidth(0.4)
            ax.spines[side].set_color("#bbbbbb")
        mono = label.startswith("*")
        # Name, then the two numbers the dropped table carried: mean value length and codes per
        # value. Both belong with the curve rather than in a separate table, since the curve is
        # only interesting once you know how long a value is and how many codes it costs.
        vb, cdv = meta.get(stem, (None, None))
        text = label.lstrip("*")
        if vb is not None:
            text += "\nB:%s|C:%s" % (_fmt(vb), _fmt(cdv))
        ax.set_xlabel(text, fontsize=C.FS["tick"], labelpad=2,
                      fontfamily="monospace" if mono else None)
    for ax in order[len(PANELS):]:
        ax.set_axis_off()
    if missing:
        sys.stderr.write("fig_tokendist: no dump for %s\n" % ", ".join(missing))
    fig.tight_layout(pad=0.3, h_pad=0.9, w_pad=0.7)
    C.save(fig, "fig_tokendist", width="text")

    for stem, label, group in PANELS:
        label = label.lstrip("*")
        v = counts(stem)
        if v:
            top = v[0] / sum(v)
            sys.stderr.write("%-16s %-11s codes %6d  top-1 %5.1f%%  top-10 %5.1f%%\n"
                             % (label, group, len(v), 100 * top,
                                100 * sum(v[:10]) / sum(v)))


if __name__ == "__main__":
    main()
