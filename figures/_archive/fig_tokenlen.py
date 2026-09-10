# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. tokenlen: token-length distribution per dataset (ORCHID-style intensity strips).

One horizontal strip per dataset; the band at length L is shaded by the fraction of
decoded tokens of that length (occurrence-weighted, dict-12). The synthetic columns
are degenerate --- l_shipinstruct is a few discrete lengths, the synthetic URL corpus
is spread --- while the real text columns concentrate at short tokens with a tail.
Source: results/token-length-hist.json (onpair-cpu-bench ONPAIR_BENCH_HIST).
"""
import json
import numpy as np
import common as C

# (json column, label, origin) in display order: synthetic group then real.
ROWS = [
    ("l_shipinstruct", "TPC-H l_shipinstruct", "S"),
    ("synthetic_url", "synthetic URL", "S"),
    ("l_comment", "TPC-H l_comment", "S"),
    ("clickbench_url", "ClickBench URL", "R"),
    ("book_reviews", "Amazon Books", "R"),
]


def main():
    raw = {d["column"]: d for d in json.load(open(C.RESULTS / "token-length-hist.json"))}
    plt = C.apply_theme()
    fig, ax = plt.subplots(figsize=(5.2, 2.1))
    mat, labels, means = [], [], []
    for col, lab, origin in ROWS:
        h = np.array(raw[col]["hist"], dtype=float)
        frac = h / h.sum()
        mat.append(frac)
        labels.append(("○ " if origin == "S" else "● ") + lab)  # open=synth, filled=real
        means.append(((np.arange(1, 17)) * frac).sum())
    mat = np.array(mat)
    im = ax.imshow(mat, aspect="auto", cmap="Blues", vmin=0,
                   extent=[0.5, 16.5, len(ROWS) - 0.5, -0.5])
    # mean-length marker per row
    ax.scatter(means, range(len(ROWS)), s=14, color=C.WARM, edgecolor="white", linewidths=0.6, zorder=3)
    ax.set_yticks(range(len(ROWS))); ax.set_yticklabels(labels, fontsize=7)
    ax.set_xticks(range(1, 17)); ax.set_xticklabels(range(1, 17), fontsize=6)
    ax.set_xlabel("token length (bytes)")
    for y in np.arange(0.5, len(ROWS) - 1): ax.axhline(y, color="white", lw=1.0)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("fraction of tokens", fontsize=6.5); cb.ax.tick_params(labelsize=6)
    ax.text(16.5, -0.5, "● mean", color=C.WARM, fontsize=6, ha="right", va="bottom")
    fig.tight_layout()
    C.save(fig, "fig_tokenlen")


if __name__ == "__main__":
    main()
