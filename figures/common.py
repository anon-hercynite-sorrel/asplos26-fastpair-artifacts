"""Shared helpers for OnPair-GPU figure generation.

Every figure script reads the committed `results/` JSON/CSV and writes a PDF (+PNG)
into `figures/out/`. Nothing here re-runs a GPU job; the figures are reproduced
purely from the archived measurement artifacts. See figures/README.md.
"""
import json
import re
from pathlib import Path


def _repo_root() -> Path:
    """The directory containing results/ (walk up from this file)."""
    here = Path(__file__).resolve()
    for d in [here.parent, *here.parents]:
        if (d / "results").is_dir():
            return d
    raise RuntimeError("could not locate results/ above %s" % here)


ROOT = _repo_root()
RESULTS = ROOT / "results"
OUTDIR = Path(__file__).resolve().parent / "out"

# Four architectures, one representative GPU each: A100 (Ampere), L40S (Ada Lovelace,
# GDDR6), H100 (Hopper), B300 (Blackwell) -- two memory technologies (HBM + GDDR6).
# GH200 dropped (a second Hopper, within noise of H100); B200 dropped for B300 (the
# newer Blackwell, complete locked sweep + full NCU). Raw for the dropped parts is in
# results/{gh200,b200}.
GPUS = ["a100", "l40s", "h100", "b300"]
GPU_LABEL = {"a100": "A100", "l40s": "L40S", "gh200": "GH200", "h100": "H100", "b200": "B200", "b300": "B300"}

# Vendor-rated HBM peak, GiB/s. Matches the Sec 2 architecture table (TB/s) and the
# GH200 "paper figure" of 3725 GiB/s used for the %-of-peak resolution.
HBM_PEAK_GIBS = {"a100": 1448, "l40s": 805, "gh200": 3725, "h100": 3120, "b200": 7451, "b300": 7451}

# Throughput is reported in GB/s (decimal, 10^9 B/s), reduced from the raw per-iteration
# timings at figure-generation: GB/s = decoded_bytes / min(decode_ns_iters) (bytes per
# nanosecond == GB/s exactly). Best-of-100-iterations (min) is the microbenchmark
# convention. This factor converts a stored GiB/s scalar (binary, 2^30) to GB/s for the
# DE and any older cell that lacks the raw samples.
GIB_TO_GB = (2 ** 30) / 1e9   # 1.073741824

# --------------------------------------------------------------------------
# Unified theme: one palette and one look across every results-bearing figure.
# --------------------------------------------------------------------------
INK = "#333333"
PRIMARY = "#2166ac"   # OnPair-GPU; the binding L1/TEX pipe (the protagonist)
WARM = "#e08214"      # hardware DE; the %-of-peak accent (the baseline to beat)
GRAY = "#9aa0a6"      # software nvCOMP-Zstd; idle pipes (muted)

# Decode techniques (Fig. field).
TECH = {"onpair": PRIMARY, "de": WARM, "software": GRAY}

# GPU generations, A100 -> B200, light -> dark (newest/fastest is darkest). Used
# wherever a bar or panel is keyed by GPU (Fig. breadth, Fig. scaling).
GPU_RAMP = {"a100": "#9ecae1", "l40s": "#74c476", "gh200": "#6baed6", "h100": "#3182bd", "b200": "#08519c", "b300": "#08519c"}

# GSST (CHEOPS'25), the prior GPU decoder for the FSST family: 191 GB/s on the A100,
# TPC-H l_comment. Its only reported point, drawn as a soft dashed reference line on
# the l_comment panel. Converted to GiB/s to match the figures' axes.
GSST_GIBS = 191.0 * 1e9 / (2 ** 30)   # ~177.9
GSST_GBS = 191.0   # GSST's reported rate is already GB/s (decimal); use directly on GB/s axes
GSST_COL = ("tpch-sf10", "l_comment")
GSST_RED = "#d6604d"

# Stage decomposition (Fig. stagecost): the two migrating stages echo the theme's
# blue/orange; gather and drain barely move, so they are muted.
STAGE = {"scan": PRIMARY, "emit": WARM, "gather": "#7fb3a6", "drain": GRAY}

# Cost surface (Fig. costsurface): foreground the cache path that binds, mute the
# idle pipes. L1/TEX is the bound; L2 is the same path one level down; DRAM/SM idle.
PIPE = {"L1/TEX": PRIMARY, "L2": "#a8c5e0", "DRAM": GRAY, "SM (compute)": GRAY}

# Launch-bound (1-6 MB) columns: reported for completeness, not as throughput.
LAUNCH_BOUND = {
    ("dbtext", "email"), ("dbtext", "hex"), ("dbtext", "l_comment"),
    ("dbtext", "ps_comment"), ("dbtext", "yago"), ("tpch-sf10", "s_comment"),
}

# Representative (dataset, column) for breadth/scaling, with a short label.
REPRESENTATIVE = [
    ("tpch-sf10", "ps_comment", "TPC-H ps_comment"),
    ("tpch-sf10", "l_comment", "TPC-H l_comment"),
    ("clickbench", "URL", "ClickBench URL"),
    ("fineweb", "text", "FineWeb"),
    ("wikipedia", "text", "Wikipedia"),
    ("book-reviews", "text", "book-reviews"),
    ("synthetic", "url", "synthetic"),
    ("lship", "l_shipinstruct", "l_shipinstruct"),
]


# Codec that produced a cell's stored representation. Every record written before
# FSST-12 existed is OnPair and carries no "codec" key, so absent means ONPAIR.
ONPAIR = "onpair"
FSST12 = "fsst12"


# Harness LABELS are not dataset ids. The sweep writes `onpair_summary_<label>.json`, and a
# label can differ from the `dataset_id` recorded inside it: `lship` holds cells whose
# dataset_id is `tpch-sf10`. Filenames are therefore not scopes for OnPair either.
#
# This bites silently rather than loudly. Asking for the cell by its real id --
# cell(gpu, "tpch-sf10", "l_shipinstruct") -- opened the tpch file, which holds only the
# three comment columns, and returned None. On 2026-08-17 that quietly dropped a whole
# column from a selector fit across all four GPUs: the fit reported 72 cells and 9 columns
# when the corpus has 10, and nothing failed. Individual figures had each papered over it
# with their own alias tables (fig_compressibility._OFFSET_DID_ALIAS,
# fig_crossarch.FSST12_ALIAS, inline conditionals elsewhere), so the mapping was repeated
# four times and absent everywhere else. Resolve it once, here.
LABEL_TO_DATASET = {"lship": "tpch-sf10"}


def resolve_dataset(dataset):
    """The real `dataset_id` for a harness label (identity for anything already an id)."""
    return LABEL_TO_DATASET.get(dataset, dataset)


def load(gpu, dataset, codec=ONPAIR):
    """Cells for one (gpu, dataset), from the directory that codec lives in.

    `dataset` may be either a dataset_id or a harness label; both resolve to the same
    cells. Filenames are not scopes in either directory, so every file is read and cells
    are filtered on their own `dataset_id`. Verified free of duplicates at import.
    """
    target = resolve_dataset(dataset)
    d = RESULTS / (("%s-fsst12" % gpu) if codec == FSST12 else gpu)
    if not d.is_dir():
        return []
    pattern = "*.json" if codec == FSST12 else "onpair_summary_*.json"
    out = []
    for f in sorted(d.glob(pattern)):
        try:
            out.extend(json.load(open(f)))
        except (json.JSONDecodeError, OSError):
            continue
    return [c for c in out if c.get("dataset_id") == target]


def same_run_onpair(gpu, dataset, column, bits):
    """The OnPair cell measured in the SAME session as that chip's FSST-12 cells.

    Distinct from `cell(..., ONPAIR)`, which returns the canonical matrix entry from
    a different (earlier) send. Use this one for FSST-12-vs-OnPair claims, so the
    comparison never crosses boxes or revisions; use `cell` for anything the paper
    already reports.
    """
    d = RESULTS / ("%s-fsst12" % gpu)
    if not d.is_dir():
        return None
    for f in sorted(d.glob("onpair_ref_*.json")):
        for c in json.load(open(f)):
            if (
                c.get("dataset_id") == dataset
                and c.get("column") == column
                and c.get("bits") == bits
                and c.get("codec", ONPAIR) == ONPAIR
            ):
                return c
    return None


def cell(gpu, dataset, column, bits=12, codec=ONPAIR):
    """One (gpu, dataset, column, bits, codec) record, or None.

    `codec` is not redundant with `bits`. FSST-12 is a 12-bit codec, so it writes
    bits=12 and is otherwise indistinguishable from OnPair-12 -- and because this
    returns the FIRST match, that collision would silently hand back the wrong
    codec's cell rather than raise. Callers get OnPair unless they ask otherwise.
    """
    for c in load(gpu, dataset, codec):
        if (
            c.get("column") == column
            and c.get("bits") == bits
            and c.get("codec", ONPAIR) == codec
        ):
            return c
    return None


def kernel_map(c):
    """{kernel_name: decode_gib_s} for one cell."""
    g = c.get("gpu") or {}
    return {k.get("kernel"): k.get("decode_gib_s") for k in g.get("kernels", [])}


def _gb_s(decoded_bytes, ns_iters, gib_s_scalar=None):
    """Reduce one kernel's raw per-iteration ns to GB/s = decoded_bytes / min(ns).
    Falls back to a stored GiB/s scalar (converted) when raw samples are absent."""
    if decoded_bytes and ns_iters:
        return decoded_bytes / min(ns_iters)   # bytes / ns == GB/s
    return gib_s_scalar * GIB_TO_GB if gib_s_scalar else None


def best_shipped(c):
    """Best decode GB/s over SHIPPED kernels, reduced from the raw per-iteration timings.

    GB/s = decoded_bytes / min(decode_ns_iters). Excludes the non-byte-exact `*ablate*`
    instrumentation builds and any kernel that failed byte-validation. Falls back to the
    stored best_decode_gib_s (converted) if no raw per-iteration samples are present.
    """
    if not c:
        return None
    g = c.get("gpu") or {}
    db = g.get("decoded_bytes")
    vals = [
        _gb_s(db, k.get("decode_ns_iters"), k.get("decode_gib_s"))
        for k in g.get("kernels", [])
        if k.get("decode_gib_s")
        and "ablate" not in str(k.get("kernel", ""))
        and k.get("verified") is not False
    ]
    vals = [v for v in vals if v]
    if vals:
        return max(vals)
    bd = g.get("best_decode_gib_s")
    return bd * GIB_TO_GB if bd else None


def software_best(c):
    """Best software nvCOMP-Zstd decode GB/s for one cell (or None), from raw min."""
    if not c:
        return None
    g = c.get("gpu") or {}
    best = None
    for e in (g.get("nvcomp_zstd") or []):
        if not isinstance(e, dict):
            continue
        rb, it = e.get("raw_bytes"), e.get("decode_ms_iters")
        v = (rb / min(it) / 1e6) if (rb and it) else (
            e["decode_gib_s"] * GIB_TO_GB if e.get("decode_gib_s") else None)
        if v and (best is None or v > best):
            best = v
    return best


def zstd_gb_s(entry):
    """One nvCOMP-Zstd entry's decode GB/s (min of raw samples, else converted scalar)."""
    rb, it = entry.get("raw_bytes"), entry.get("decode_ms_iters")
    if rb and it:
        return rb / min(it) / 1e6
    return entry["decode_gib_s"] * GIB_TO_GB if entry.get("decode_gib_s") else None


def distinct_codes(c):
    return ((c or {}).get("gpu") or {}).get("distinct_codes")


def de_map():
    """Blackwell hardware Decompression Engine best decode GB/s per (dataset, column).
    Sourced from B300; the DE is fixed-function silicon, byte-identical on B200/B300.
    The DE stores only a min-reduced scalar (no raw samples), so convert GiB/s -> GB/s."""
    f = RESULTS / "b300" / "onpair_nvcomp_hw.json"
    return {(e["dataset_id"], e["column"]):
            (e["best_decode_gib_s"] * GIB_TO_GB if e.get("best_decode_gib_s") else None)
            for e in json.load(open(f))}


# --------------------------------------------------------------------------
# Token access distribution (Appendix A)
# --------------------------------------------------------------------------
# Ranks the figure samples at. 4^6 and 4^8 land exactly on the two dictionary caps, and 256 /
# 1024 are the two ranks the appendix quotes in prose.
FREQ_EDGES = [1, 4, 16, 64, 256, 1024, 4096, 16384, 65536]


def freqdist(fname="token-freqdist/token_freqdist.json"):
    """Per (column, codec) token access distribution records."""
    return json.load(open(RESULTS / fname))


def freq_record(rows, column, codec):
    """The one record for a (column, codec), or None."""
    for r in rows:
        if r["column"] == column and r["codec"] == codec:
            return r
    return None


def freq_coverage(curve, ranks=None):
    """Share of all accesses (%) served by the N most-frequently-read entries, at each rank.

    Cumulative on purpose. An earlier version of the figure binned ranks into powers of four
    and drew the share falling in each bin, which is misleading: the bins hold 1, 3, 12, 48
    ... entries, so a bar can be tall merely because its bin is wide.

    Deliberately stdlib-only and living here rather than in the figure, so the validator
    re-derives the appendix's numbers through the SAME reduction the figure draws instead of a
    second implementation that could drift apart from it.
    """
    ranks = FREQ_EDGES if ranks is None else ranks
    xs = [0.0] + [float(r) for r, _ in curve]
    ys = [0.0] + [float(c) for _, c in curve]
    out = []
    for want in ranks:
        if want >= xs[-1]:
            out.append(ys[-1] * 100.0)
            continue
        for i in range(1, len(xs)):
            if xs[i] >= want:
                # Linear between the bracketing samples; equal x means a repeated rank, so
                # take the later (higher) coverage rather than dividing by zero.
                span = xs[i] - xs[i - 1]
                frac = 0.0 if span == 0 else (want - xs[i - 1]) / span
                out.append((ys[i - 1] + frac * (ys[i] - ys[i - 1])) * 100.0)
                break
    return out


def freq_at(record, rank):
    """Coverage (%) at one rank for one record."""
    return freq_coverage(record["curve"], [rank])[0]


def freq_entries_for(record, target_pct):
    """Entries needed to cover target_pct of accesses -- the hot-set size.

    Inverts the cumulative curve by linear interpolation, the same convention freq_coverage
    reads it forward with. Taking the smallest EMITTED rank at or above the target instead
    would be an upper bound and is visibly coarser: on `l_comment` at 90% it reads 2287
    against the interpolated 2165, because the curve is sampled at 64 log-spaced ranks and
    the gaps are wide out where the tail flattens.
    """
    curve = record["curve"]
    xs = [0.0] + [float(r) for r, _ in curve]
    ys = [0.0] + [float(c) * 100.0 for _, c in curve]
    for i in range(1, len(ys)):
        if ys[i] >= target_pct:
            span = ys[i] - ys[i - 1]
            frac = 0.0 if span == 0 else (target_pct - ys[i - 1]) / span
            return xs[i - 1] + frac * (xs[i] - xs[i - 1])
    return xs[-1]


def ncu_sol(metric, fname="b200-ncu/ncu_costsurface_synthetic_url_b12_sol.txt"):
    """Parse a Speed-of-Light %-of-peak value from an NSight Compute SOL dump."""
    txt = (RESULTS / fname).read_text(errors="ignore")
    for line in txt.splitlines():
        if line.strip().startswith(metric):
            m = re.findall(r"[-+]?\d*\.?\d+", line)
            if m:
                return float(m[-1])
    raise KeyError("metric %r not found in %s" % (metric, fname))


# ==========================================================================
# TYPOGRAPHY AND MARKS.  One contract; every figure asks for a size by what the
# thing IS, never by a literal.  Same motive as the palette below: changing the
# type scale is one edit here rather than a sweep of the generators.
#
# THESE ARE PRINTED POINTS, and they are only printed points because `save` draws
# each figure at the exact width LaTeX will show it at (see PRINT_PT). A figure
# drawn 7.1in wide and included at 7.0in scales every glyph by 0.986; one drawn
# 3.3in wide and included at 3.33in magnifies by 1.01. Those factors used to run
# from 0.93 to 1.15 across the seven paper figures, so an 8pt axis label printed
# anywhere between 7.5 and 9.2pt and no declared size meant anything. Normalising
# the width is what makes this table a contract instead of a suggestion.
FS = {
    "axis_label": 8.1,    # x/y axis names, and a colourbar's label
    "tick": 8.1,          # tick labels on every axis, including a colourbar's
    "panel_title": 8.1,   # the B=1 / B=8 / Real-world style panel heading
    "legend": 8.1,        # legend entries and legend titles
    "annot": 5.5,         # values printed inside the plot (bar tops, heatmap cells)
    # Dense keys use the same readable type size; adjust their layout to fit.
    "legend_dense": 8.1,
}

# Data marks. `ms` is a diameter in points; scatter's `s` is an AREA in points
# squared, hence MS ** 2. Stars read smaller than a disc of the same diameter.
MS = 4.4
MS_SCATTER = MS ** 2
MS_STAR = MS * 1.6
MS_LEGEND = MS * 1.2   # legend proxy, a little larger so a shape is identifiable
LW = 1.1               # a data line

# acmart[sigplan] widths are TeX points (1/72.27 inch); Matplotlib/PDF points
# are 1/72 inch. Convert so inclusion at column/text width preserves font sizes.
PRINT_PT = {key: value * 72.0 / 72.27
            for key, value in {"column": 240.945, "text": 505.89}.items()}
# Gap between the axes and a legend placed below them, in figure fractions, on top
# of whatever tight_layout already left under the x label -- which at these sizes is
# about ten points and is itself the gap you want. Zero, therefore, and kept as a
# named constant so the answer to "why is this key so far out" is one edit.
LEGEND_GAP = 0.0


def apply_theme():
    """One consistent look across all figures. Returns the pyplot module."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": FS["axis_label"], "axes.titlesize": FS["panel_title"],
        "axes.labelsize": FS["axis_label"],
        "xtick.labelsize": FS["tick"], "ytick.labelsize": FS["tick"],
        "legend.fontsize": FS["legend"], "legend.title_fontsize": FS["legend"],
        "lines.markersize": MS, "lines.linewidth": LW,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": "#888888", "axes.linewidth": 0.8, "axes.axisbelow": True,
        "axes.grid": True, "axes.grid.axis": "y",
        "grid.color": "#e6e6e6", "grid.linewidth": 0.7,
        "text.color": INK, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
        "figure.dpi": 200, "figure.facecolor": "white", "savefig.facecolor": "white",
        # Hatch weight is a global rcParam, not a per-artist one: setting linewidth on a bar
        # does nothing to its hatch. Default 1.0 draws a heavy screen that swamps the fill it
        # sits on at these bar widths, so every figure gets a light rule instead.
        "hatch.linewidth": 0.35,
    })
    return plt


def new_fig(w=3.3, h=2.2):
    return apply_theme().subplots(figsize=(w, h))


PAD_IN = 0.02   # savefig pad_inches; part of the width the normaliser has to hit


def fit_print_width(fig, width="column", tol=0.004, rounds=6):
    """Scale `fig` so its saved tight bbox is exactly the printed width of `width`.

    Fonts are absolute points, so growing the canvas does NOT grow the type -- the
    axes take the extra room and every declared size in FS lands on the page as
    that many points. That is the whole reason this exists. Aspect is preserved, so
    a figure keeps the shape it was authored with.

    Iterative because the tight bbox is not linear in the figure size: rotated tick
    labels and an overhanging legend occupy a fixed number of points, so the margin
    they add is a shrinking fraction as the canvas grows. Two or three rounds
    converge to well under a point.
    """
    target = PRINT_PT[width] / 72.0
    fig.canvas.draw()
    for _ in range(rounds):
        bb = fig.get_tightbbox(fig.canvas.get_renderer())
        cur = bb.width + 2 * PAD_IN
        if abs(cur - target) <= tol:
            break
        w, h = fig.get_size_inches()
        k = target / cur
        fig.set_size_inches(w * k, h * k)
        fig.canvas.draw()
    return fig


def save(fig, name, width=None):
    """Write out/<name>.{pdf,png}, drawn at the width LaTeX will print it at.

    `width` names the float shape the paper wraps it in: "column" for figure,
    "text" for figure*. Getting it wrong is not a crash, it is a figure whose type
    is off by the ratio of the two, so it matches the \\includegraphics line.

    Omitting it leaves the figure at whatever size the generator chose, which is
    what the many generators that are NOT in the paper still do. Normalising them
    would resize a seven-inch panel down to one column; the ones the paper prints
    pass their width explicitly instead.
    """
    OUTDIR.mkdir(exist_ok=True)
    if width is not None:
        fit_print_width(fig, width)
    for ext in ("pdf", "png"):
        # Rasterized artists, including dense hatch fills, use 600 dpi; other PDF elements
        # stay vector regardless.
        fig.savefig(OUTDIR / ("%s.%s" % (name, ext)), bbox_inches="tight", pad_inches=PAD_IN,
                    dpi=600)
    print("wrote", (OUTDIR / (name + ".pdf")).relative_to(ROOT))


def rasterize_dotted_legend(legend):
    """Rasterize dotted swatches while retaining vector text and correct placement."""
    from types import MethodType
    from matplotlib.patches import Patch
    from matplotlib.transforms import Affine2D

    def draw_swatch(swatch, renderer):
        # DrawingArea caches its transform before mixed-mode rendering changes the DPI
        # (Matplotlib #28549). Apply the live DPI ratio only during the patch draw.
        transform = swatch.get_data_transform()
        dpi = renderer.points_to_pixels(72)
        scale = swatch.get_figure().dpi_scale_trans + Affine2D().scale(1 / dpi)
        swatch.set_transform(transform + scale)
        try:
            Patch.draw(swatch, renderer)
        finally:
            swatch.set_transform(transform)

    for handle in legend.legend_handles:
        if isinstance(handle, Patch) and "." in (handle.get_hatch() or ""):
            handle.set_rasterized(True)
            handle.draw = MethodType(draw_swatch, handle)


def legend_below(fig, x=0.5, gap=None, expand=False, **kw):
    """A legend hung under the axes, the same distance out in every figure.

    Anchored by its TOP edge (loc="upper center") one LEGEND_GAP below the figure
    box, so the space between the x label and the key does not depend on how many
    rows the key happens to need. bbox_inches="tight" in `save` then grows the
    canvas to include it.

    borderaxespad is forced to zero. Its default is half a font size -- about three
    points of air above the key that nothing in the figure asked for, and it is
    applied even when bbox_to_anchor is given, which is easy to miss. Left at the
    default it put the gap at 7 to 10pt in four figures against fig_perf_real's
    4.6pt, which was the one figure that happened to set it.

    `expand` spreads the entries across the full canvas width instead of centring
    them as a block: right for a wide figure whose key needs every column, wrong
    for a narrow one, where it would stretch three entries across the page.
    `x` moves a centred key off centre, for a figure carrying two of them.
    """
    kw.setdefault("frameon", False)
    kw.setdefault("fontsize", FS["legend"])
    kw.setdefault("borderaxespad", 0.0)
    y = -(LEGEND_GAP if gap is None else gap)
    if expand:
        return fig.legend(loc="upper center", bbox_to_anchor=(0.0, y, 1.0, 0.001),
                          mode="expand", **kw)
    return fig.legend(loc="upper center", bbox_to_anchor=(x, y), **kw)


# ==========================================================================
# PALETTE BY ROLE.  One place; every figure asks for a colour by what the thing
# IS, never by hex.  Changing a scale is one edit here instead of a sweep of the
# generators, which is the whole point of this section existing.
#
# Two scales, chosen by what the figure is about:
#   "technique"  our codecs, and the devices they run on  -> viridis
#   "baseline"   the fixed-function Engine we measure against -> inferno
#   "analysis"   instrument readings and mechanism        -> plasma
# So a reader can tell at a glance whether a figure is showing WHAT SOMETHING IS or
# HOW IT BEHAVES, and the two never share a hue vocabulary.
#
# VIRIDIS IS CAPPED AT 0.90. Above that it runs into a saturated yellow-green: #d8e219 sits at
# luminance 0.691 with saturation 0.89 and only 1.42:1 contrast against the page, which is what
# reads as harsh. Plasma does not have the same problem at the same position, because it reaches
# its yellow only at the very top of its range, above anything sampled here. The cap is only
# affordable because the Engine moved to its own scale and freed viridis's middle.
#
# Both are perceptually uniform, which is necessary but NOT sufficient for a
# black-and-white printer: uniformity buys monotone luminance, so two members far
# apart in the scale survive greyscale and two members close together do not.
# greyscale_report() measures that instead of assuming it, and any family it flags
# has to carry identity in marker shape or hatch as well as hue.
# --------------------------------------------------------------------------
SCALE = {"technique": "viridis", "baseline": "inferno", "analysis": "plasma"}

# THE PAPER-WIDE DEVICE ORDER. Every figure that lays devices out side by side uses this, so a
# reader who learns the order once can carry it between figures. Before this existed there were
# four orders in the tree: suite.CHIPS_CORE, fig_pipes.ORDER, fig_crossarch.ORDER and the device
# palette family, all different.
#
# The rule is: memory technology first, newest first within each group.
#   - HBM before GDDR, because the boundary between them is what section 5.4 argues, so the
#     grouping has to survive being read left to right.
#   - Newest first inside a group puts the B300 -- the headline device -- at the left edge where
#     a reader starts, and walks backward to the A100, which is the direction the "reaches back
#     to Ampere" claim is made in.
DEVICE_ORDER = ["b300", "h100", "a100", "rtxpro", "l40s"]
DEVICE_LABEL = {"b300": "B300", "h100": "H100", "a100": "A100",
                "rtxpro": "RTX PRO", "l40s": "L40S"}


def devices(present=None):
    """The paper-wide device order, optionally filtered to those actually present."""
    return [d for d in DEVICE_ORDER if present is None or d in present]

# family -> (ordered members, scale, (lo, hi) span, mode). The span trims the ends of the
# colormap: plasma runs near-black at 0.0 and near-yellow at 1.0, and both lose
# contrast, one against ink and one against paper.
#
# mode picks how the members are placed inside the span:
#   "luminance"  equal steps in BRIGHTNESS, which maximises what a greyscale printer has
#                to resolve. Use for families whose members are categories.
#   "interior"   n evenly spaced positions with both ends dropped, i.e. member i sits at
#                (i+1)/(n+1) of the span. Predictable and symmetric; use for small ORDINAL
#                families where the reader reads the ramp as an order, not as identities.
#
# WHICH MODE A FAMILY TAKES IS NOT A STYLE CHOICE. The interior form reads better as a ramp
# and is right for an ORDER, but it cannot be forced onto a categorical family: measured on the
# four-member pipe family it lands at a worst greyscale gap of 0.082 and RAISING the spread makes
# it worse, not better (0.084 at 1.8, 0.078 at 2.0, 0.064 at 2.4), because clamping pins the
# outer two members at the span's ends while the inner two stay in viridis's flattest luminance
# region. Categories therefore take "luminance", which clears the same family at 0.149.
#
# An interior family may carry a fifth element, SPREAD, which pushes the members outward
# from the centre of the span by that factor: 1.0 leaves the ends-dropped positions alone,
# 1.5 moves them half a step further apart. Raise it when three colours sit too close to
# tell apart at line width; positions are clamped to the span, so it cannot run off the
# end of the scale and back into the extremes the span exists to avoid.
FAMILY = {
    # UNUSED as of 2026-08-24, and kept only for a figure that needs FSST-8 alongside the three
    # this paper decodes. Anything drawing the three should use tech-ours, so a codec keeps one
    # colour paper-wide; this family assigns them different ones because it has a fourth member.
    "codec":  (["OnPair-12", "OnPair-16", "FSST-12", "FSST-8"], "technique", (0.15, 0.78), "luminance"),
    "device": (["B300", "H100", "A100", "RTX PRO", "L40S"], "technique", (0.10, 0.85), "luminance"),
    # SPLIT BY MEMORY TECHNOLOGY, for figures whose argument turns on it. A single continuous
    # ramp cannot show a categorical boundary -- put the five devices on one scale and the
    # HBM/GDDR split lands mid-ramp, where B300 and L40S are adjacent hues in different groups.
    # Two scales give the split a hue change to live on, and each stays perceptually uniform.
    # BANDED, both on the technique scale, rather than one group per scale. Splitting them
    # across viridis and plasma did separate the groups, but it spent the analysis scale on a
    # device family -- so plasma would have meant "instrument reading" everywhere except here.
    # Two bands of one scale keep the categorical break and leave plasma meaning one thing.
    # Neither band reaches 1.0: viridis ends at a near-white yellow that disappears against the
    # page, which is what the span mechanism exists to prevent. Nor is the HBM band narrow --
    # three members in 0.42 came out TIGHT at 0.075.
    # Ordered as DEVICE_ORDER, so the darkest step of each band is that group's newest part and
    # the ramp lightens as it goes back through the generations.
    #
    # These SHARE ranges with the codec bands on purpose. No figure draws codecs and devices
    # together -- fig_perf_gen has devices and the Engine, fig_perf_real and fig_teaser have
    # codecs and the Engine -- so the dark band can serve tech-ours and device-hbm, and the light
    # band tech-nvcomp and device-gddr. What must NOT overlap is anything against tech-engine,
    # because the Engine appears in all three of those figures.
    #
    # ONE PAIR NOW COMES CLOSE, and it is recorded rather than claimed away: opening tech-engine
    # to 0.85 puts DE Snappy at luminance 0.575, and the L40S sits at 0.637. They share
    # fig_perf_gen. In colour they are yellow-orange against yellow-green; in greyscale they are
    # near-identical, and what separates them there is form, not tone -- the L40S is point marks
    # inside a chip's slot, DE Snappy is a rule spanning the whole slot. Anything that ever draws
    # the two as the same kind of artist has to revisit this.
    "device-hbm":  (["B300", "H100", "A100"], "technique", (0.00, 0.46), "luminance"),
    "device-gddr": (["RTX PRO", "L40S"], "technique", (0.63, 0.90), "luminance"),
    # Threads per block is an ORDER, not a set of identities, so it takes the interior
    # construction over the whole scale: three points at 0.25, 0.5 and 0.75 of viridis.
    "threads": (["T=64", "T=128", "T=256"], "analysis", (0.0, 1.0), "interior", 1.5),
    "pipe":   (["gather", "drain", "readback", "emit"], "analysis", (0.15, 0.80), "interior", 1.5),
    "level":  (["L1", "L2", "device memory"], "analysis", (0.30, 0.75), "luminance"),
    # ONE PROGRESSION over the whole memory path, ordered by distance from the SM: the
    # dictionary gather is darkest and device memory lightest. The four L1 segments are drawn in
    # colour and the last two are desaturated to the grey of matching brightness, so the set
    # reads as a single luminance ramp with hue dropping away for the two context bars. Compute
    # is deliberately NOT a member -- it is not on this path.
    "mempath": (["gather", "drain", "readback", "emit", "L2", "device memory"],
                "analysis", (0.10, 0.90), "luminance"),
    # BANDED TECHNIQUE GROUPS. Each group takes its own region of viridis, so a reader sees
    # which FAMILY a mark belongs to before reading which member, and the bands do not overlap.
    # Zstd is not here: software byte-stream codecs take the neutral greys, since they are the
    # context the positional claim is made against rather than a family being compared.
    # Band widths are NOT equal, deliberately. "ours" gets the widest because it is the group
    # whose members the paper actually compares against each other; the Engine's four codecs and
    # the two Bitcomp variants only need to be told apart from other GROUPS, which the marker
    # shape already does.
    # THE ENGINE IS OFF VIRIDIS ENTIRELY. It sat in viridis's middle, and viridis's middle is
    # green, so any band there collided with something: with FSST-12 and the nvCOMP group in
    # fig_perf_real, and with the A100 and the RTX PRO in fig_perf_gen. Its own scale removes the
    # constraint rather than negotiating around it. inferno's mid-range is red through orange,
    # which no viridis band reaches, and it cannot clash with plasma either because no figure
    # draws the Engine and an analysis quantity together.
    # Ordered OnPair-16 first so the band darkest-to-lightest matches the order fig_teaser
    # draws its bars in, which makes that figure read as one ramp left to right. The other
    # two figures using this family are scatters, where the draw order does not show.
    "tech-ours":   (["OnPair-16", "OnPair-12", "FSST-12"], "technique", (0.00, 0.46), "luminance"),
    # Deflate (5) first, matching fig_perf_real's legend order and putting the darkest step on
    # the codec that actually appears most -- it is drawn on 14 of 15 columns, against once for
    # Deflate (0).
    # SPAN OPENED AT THE LIGHT END ONLY, 0.72 to 0.85. All four codecs are drawn per column in
    # fig_perf_gen now rather than the best of them, and at 0.72 the top two were #e9612b and
    # #f68013 -- two oranges 0.09 apart in luminance, which read as one thick line wherever LZ4
    # and Snappy landed close in rate. Internal gaps are now 0.16. The cap is 0.85 and not higher
    # because gANS, the top of viridis's light band, sits at luminance 0.637: hi=0.88 would put DE
    # Snappy at 0.639, identical in greyscale to a mark that shares a panel with it in
    # fig_perf_real. 0.85 leaves DE Snappy at 0.575 and 1.68:1 against the page, which clears the
    # 1.53:1 the viridis cap was set at. The dark end does not move, so the Engine's darkest step
    # is the same colour it has been in all three figures that draw it.
    "tech-engine": (["DE Deflate (5)", "DE Deflate (0)", "DE LZ4", "DE Snappy"],
                    "baseline", (0.40, 0.85), "luminance"),
    "tech-nvcomp": (["Bitcomp-default", "Bitcomp-sparse", "gANS"],
                    "technique", (0.63, 0.90), "luminance"),
    # The three groups a corpus column can belong to. A diagnostic split rather than a technique,
    # so it takes the analysis scale. Used by fig_tokendist, where the groups do not tile the
    # panel grid evenly and colour is what carries the grouping instead of position.
    "corpus": (["real", "real-short", "generated"], "analysis", (0.15, 0.75), "luminance"),
}

# Hatches carry identity where colour cannot. Ordered so adjacent members differ in
# density as well as direction; "" first so the common case stays clean.
# One repetition, not three: at bar widths of a few millimetres "///" reads as a solid
# screen and swamps the fill colour it is meant to supplement.
HATCHES = ["", "/", ".", "x", "\\", "+", "o", "-"]

# CONTEXT, not subject. Bars or lines that exist only to show what the subject is
# measured against take a neutral ramp, so they never compete with a family colour for
# the reader's attention and never collide with one. Light to dark.
NEUTRAL = ["#d9d9d9", "#a6a6a6", "#6e6e6e", "#404040"]

# GROUND, not a member: a region wash that says "under here is worse", never an
# encoding of a value. Ice rather than grey ON PURPOSE. fig_perf_real fills the
# baseline envelope and draws the three Zstd levels from NEUTRAL on top of it, so a
# grey wash under grey marks left the dark end (#404040) sitting in its own tint and
# the light end (#d9d9d9) invisible. A tint differing in HUE from the marks it sits
# behind separates them at almost no ink. Opaque, not alpha over white, so nothing
# composites with a mark drawn above it.
WASH = "#e8f0f7"


def neutral(i=0):
    """i-th context grey, light to dark."""
    return NEUTRAL[i % len(NEUTRAL)]


def _members(family):
    """(members, scale, span, mode, spread), padding spread to its 1.0 default."""
    try:
        spec = FAMILY[family]
        return spec if len(spec) == 5 else (spec + (1.0,))
    except KeyError:
        raise KeyError("unknown palette family %r; known: %s"
                       % (family, ", ".join(sorted(FAMILY)))) from None


def _positions(scale, lo, hi, n):
    """n positions in [lo,hi] whose LUMINANCES are equally spaced, not their positions.

    Equal steps along a colormap do not give equal steps in brightness: both plasma and
    viridis compress luminance at the dark end, so evenly spaced samples bunch together
    exactly where a greyscale printer can least afford it. Walking a fine lookup table
    and picking equal luminance instead maximises the smallest gap the printer has to
    resolve, which is what greyscale_report() measures.
    """
    if n == 1:
        return [lo]
    import matplotlib
    cm = matplotlib.colormaps[SCALE[scale]]
    grid = [lo + (hi - lo) * k / 512.0 for k in range(513)]
    lums = [_luminance(matplotlib.colors.to_hex(cm(g))) for g in grid]
    lo_l, hi_l = lums[0], lums[-1]
    out = []
    for i in range(n):
        want = lo_l + (hi_l - lo_l) * i / (n - 1)
        out.append(min(zip(grid, lums), key=lambda gl: abs(gl[1] - want))[0])
    return out


def colour(family, member):
    """Hex for one member of one family, sampled from that family's scale."""
    members, scale, (lo, hi), mode, spread = _members(family)
    if member not in members:
        raise KeyError("%r is not in the %r family; known: %s"
                       % (member, family, ", ".join(members)))
    import matplotlib
    n = len(members)
    if mode == "interior":
        frac = (members.index(member) + 1) / (n + 1)
        frac = 0.5 + (frac - 0.5) * spread            # push outward from the centre
        frac = min(max(frac, 0.0), 1.0)               # clamp: never past the span's own ends
        pos = lo + (hi - lo) * frac
    else:
        pos = _positions(scale, lo, hi, n)[members.index(member)]
    return matplotlib.colors.to_hex(matplotlib.colormaps[SCALE[scale]](pos))


def hatch(family, member):
    """Hatch pattern for one member, for greyscale and for over-full families."""
    members = _members(family)[0]
    return HATCHES[members.index(member) % len(HATCHES)]


def desaturate(hexcol):
    """The grey of the same relative luminance as hexcol.

    Used for context members of a family whose progression should continue past the coloured
    ones: keeping the luminance means the ramp reads as one ordered sequence, and dropping the
    hue means those members stop competing for attention. It is also exactly what a greyscale
    printer would have done to them, so what the reader sees on paper matches print.
    """
    import matplotlib
    lum = _luminance(hexcol)
    v = 12.92 * lum if lum <= 0.0031308 else 1.055 * lum ** (1 / 2.4) - 0.055
    v = min(max(v, 0.0), 1.0)
    return matplotlib.colors.to_hex((v, v, v))


def cmap(kind="analysis"):
    """Colormap NAME for figures that map a continuous quantity (fig_hoist, heatmaps)."""
    return SCALE[kind]


def _luminance(hexcol):
    import matplotlib
    r, g, b = matplotlib.colors.to_rgb(hexcol)
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def greyscale_report(min_gap=0.10):
    """Print each family's greyscale separation. Run as `python3 common.py`.

    Reports the smallest luminance gap between any two members. A family under
    min_gap cannot be told apart on a monochrome printer by colour alone and needs
    shape or hatch doing the work; that is a fact about the family's SIZE more than
    about the scale, since any scale has one luminance axis to divide.
    """
    for fam in sorted(FAMILY):
        members, scale = FAMILY[fam][0], FAMILY[fam][1]
        lums = [(m, _luminance(colour(fam, m))) for m in members]
        gaps = [abs(a[1] - b[1]) for i, a in enumerate(lums) for b in lums[i + 1:]]
        worst = min(gaps) if gaps else 1.0
        flag = "OK " if worst >= min_gap else "TIGHT"
        print("%-8s %-10s n=%d  worst pairwise luminance gap %.3f  %s"
              % (fam, SCALE[scale], len(members), worst, flag))
        for m, l in lums:
            print("      %-16s %s  L=%.3f  hatch=%r" % (m, colour(fam, m), l, hatch(fam, m)))


if __name__ == "__main__":
    greyscale_report()
