# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib"]
# ///
"""Fig. envelope: shipped-selector decode rate per column, on the three measured devices.

Two figures, emitted separately and deliberately NOT combined:

  fig_perf_real -- the ten real-data columns
  fig_perf_gen  -- the five columns from data generators

Keeping them apart is the point. Generated columns decode FASTER than every real column
(l_shipinstruct at 1651 GB/s against the fastest real column's 1423 on the B300), so a single
panel invites a reader to take the envelope's top edge as a real-data result. They are a
labelled group studied for generator effects, never pooled into a real-data claim.

Columns are ordered by the OnPair-12 short-token fraction, DESCENDING, which is the order of
Table 1 in the paper. Rate rises left to right as that fraction falls, so the ordering is the
result: rate tracks the token length profile, not the compression ratio.

RATE IS THE SHIPPED SELECTOR'S KERNEL, not an oracle. Each cell records 475 kernels, 19
`production` and 456 `experimental` probes, and the fastest probe beats the shipped selector by
up to 7.7%. Quoting that maximum as the codec's rate is the error an earlier retraction was
about, so `auto_kernel` is what is plotted here. GB/s = decoded_bytes / min(decode_ns_iters),
min-of-100, and bytes/ns is exactly GB/s.

Source: results/campaign-20260820/{b300,h100,a100}/sweep_summary_<label>_boost.json, the
2026-08-20 campaign. This data does NOT live under results/<gpu>/ and is not read by
common.load(), whose filename and directory conventions belong to the older corpus.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

CAMPAIGN = common.RESULTS / "campaign-20260820"
DEVICES = ["a100", "h100", "b300"]      # bandwidth order, matching GPU_RAMP light -> dark
GENERATED_PREFIXES = ("tpch-sf15", "tpch-sf45", "tpch-sf263")

LABEL = {
    ("loghub-windows", "line"): "Windows",
    ("loghub-spark", "line"): "Spark",
    ("loghub-thunderbird", "line"): "Thunderbird",
    ("loghub-hdfs", "line"): "HDFS",
    ("loghub-android", "line"): "Android",
    ("clickbench", "Title"): "Title",
    ("clickbench", "URL"): "URL",
    ("codeparrot", "content"): "CodeParrot",
    ("wikipedia", "text"): "Wikipedia",
    ("fineweb2-zh", "text"): "FineWeb2",
    ("tpch-sf15", "l_comment"): "l_comment",
    ("tpch-sf15", "ps_comment"): "ps_comment",
    ("tpch-sf15", "l_shipinstruct"): "l_shipinstruct",
    ("tpch-sf45", "o_clerk"): "o_clerk",
    ("tpch-sf263", "c_address"): "c_address",
}


def is_generated(dataset_id):
    return dataset_id.startswith(GENERATED_PREFIXES)


def shipped_gb_s(gpu):
    """{(dataset, column, bits): (GB/s, frac_le8)} for the boost pass of one device."""
    out = {}
    d = CAMPAIGN / gpu
    if not d.is_dir():
        raise SystemExit("missing %s; stage the campaign results first" % d)
    for f in sorted(d.glob("sweep_summary_*_boost.json")):
        for c in json.load(open(f)):
            g = c["gpu"]
            auto = g.get("auto_kernel")
            for k in g.get("kernels") or []:
                if k["kernel"] == auto and k.get("decode_ns_iters"):
                    out[(c["dataset_id"], c["column"], c["bits"])] = (
                        g["decoded_bytes"] / min(k["decode_ns_iters"]),
                        g.get("frac_le8"),
                    )
    return out


DATA = {g: shipped_gb_s(g) for g in DEVICES}


def draw(keys, name, caption_width):
    plt = common.apply_theme()
    fig, axes = plt.subplots(1, 2, figsize=(caption_width, 2.25), sharey=True)
    for ax, bits in zip(axes, (12, 16)):
        xs = list(range(len(keys)))
        for gpu in DEVICES:
            ys = [DATA[gpu].get((ds, col, bits), (None, None))[0] for ds, col in keys]
            ax.plot(xs, ys, marker="o", markersize=3.2, linewidth=1.1,
                    color=common.GPU_RAMP[gpu], label=common.GPU_LABEL[gpu],
                    clip_on=False, zorder=3)
        ax.set_xticks(xs)
        ax.set_xticklabels([LABEL[k] for k in keys], rotation=38, ha="right")
        ax.set_title("OnPair-%d" % bits, pad=3)
        ax.set_xlim(-0.4, len(keys) - 0.6)
        ax.set_ylim(0, None)
    axes[0].set_ylabel("Decode rate (GB/s)")
    axes[0].legend(frameon=False, loc="upper left", handlelength=1.4, borderaxespad=0.2)
    fig.subplots_adjust(wspace=0.08)
    common.save(fig, name)


# Order by the OnPair-12 short-token fraction, descending: the paper's Table 1 order.
def ordered(pred):
    keys = {(ds, col) for (ds, col, b) in DATA["b300"] if pred(ds)}
    return sorted(keys, key=lambda k: -DATA["b300"][(k[0], k[1], 12)][1])


real = ordered(lambda ds: not is_generated(ds))
gen = ordered(is_generated)
assert len(real) == 10 and len(gen) == 5, (len(real), len(gen))

draw(real, "fig_perf_real", 7.0)   # \textwidth, two-column float
draw(gen, "fig_perf_gen", 5.0)     # narrower: five columns

for name, keys in (("real", real), ("generated", gen)):
    peak = max(DATA["b300"][(ds, col, b)][0] for ds, col in keys for b in (12, 16))
    print("%-9s n=%d  b300 peak shipped %.0f GB/s" % (name, len(keys), peak))
