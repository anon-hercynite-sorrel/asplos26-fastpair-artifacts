# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Compare the manuscript's tab:datasets with regenerated rows.

    uv run experiments/check_tab_datasets.py /tmp/tab_datasets.regen

Rows are keyed by label, so reordering is allowed. Numeric TeX thin spaces and
cell whitespace are normalized. A manuscript row absent from the generated table
is a failure, as is a generated row absent from the manuscript table.
"""
import re
import sys
from pathlib import Path

def _find_paper_dir():
    """Locate the manuscript checkout. Previously a single hardcoded
    ~/repos/onpair-gpu-paper, which is not where the paper lives, so this checker aborted
    for anyone who did not set PAPER_DIR by hand. analyze.sh exports PAPER_DIR; this is the
    fallback for a direct invocation."""
    here = Path(__file__).resolve().parent.parent
    for cand in (here.parent / "onpair-gpu-paper",
                 here.parent.parent / "papers" / "onpair-gpu-paper",
                 Path.home() / "repos" / "papers" / "onpair-gpu-paper",
                 Path.home() / "repos" / "onpair-gpu-paper"):
        if (cand / "main.tex").is_file():
            return str(cand)
    return ""


PAPER = Path(
    __import__("os").environ.get("PAPER_DIR", _find_paper_dir())
)
TABLE_FILE = PAPER / "sections/1_introduction_asplos.tex"


def norm_cell(c):
    c = c.strip()
    c = c.replace("\\,", "")        # TeX thin space inside numbers
    c = re.sub(r"\s+", " ", c)
    return c


def rows_from(text):
    """{row label: [cells]} for every tabular row that looks like a data row."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("%"):
            continue
        if "&" not in line or not line.rstrip().endswith("\\\\"):
            continue
        body = line.rstrip()[:-2]
        cells = [norm_cell(c) for c in body.split("&")]
        label = cells[0]
        # Header rows carry \multicolumn or are the column-name row; neither is data.
        if not label or label == "Dataset" or "multicolumn" in body or "$\\lvert" in body:
            continue
        out[label] = cells[1:]
    return out


def main(argv):
    if len(argv) < 2:
        print("usage: check_tab_datasets.py <regenerated-rows-file>", file=sys.stderr)
        return 2
    regen = rows_from(Path(argv[1]).read_text())
    if not TABLE_FILE.exists():
        print(f"FATAL: cannot read the paper's table at {TABLE_FILE}", file=sys.stderr)
        return 2
    text = TABLE_FILE.read_text()
    tables = re.findall(r"\\begin\{table\*?\}.*?\\end\{table\*?\}", text, re.S)
    tables = [t for t in tables if r"\label{tab:datasets}" in t]
    if len(tables) != 1:
        print("FATAL: expected exactly one table labeled tab:datasets", file=sys.stderr)
        return 1
    paper = rows_from(tables[0])

    if not paper:
        print("FATAL: no tab:datasets rows in the paper matched the generator's row labels.",
              file=sys.stderr)
        print("       generator labels: " + ", ".join(sorted(regen)[:4]) + " ...", file=sys.stderr)
        return 1

    bad = 0
    for label in sorted(set(paper) - set(regen)):
        bad += 1
        print(f"  MISMATCH unknown manuscript dataset row: {label!r}")
    checked = 0
    for label, want in sorted(regen.items()):
        got = paper.get(label)
        if got is None:
            bad += 1
            print(f"  MISMATCH missing manuscript dataset row: {label!r}")
            continue
        for i, (w, g) in enumerate(zip(want, got)):
            checked += 1
            if w != g:
                bad += 1
                print(f"  MISMATCH {label!r} cell {i + 1}: paper {g!r} vs data {w!r}")
        if len(want) != len(got):
            bad += 1
            print(f"  MISMATCH {label!r}: paper has {len(got)} cells, data produces {len(want)}")

    print(f"tab:datasets: {checked} cells compared across {len(paper)} rows, {bad} disagree")
    if bad:
        print("A disagreement means the paper prints a number the committed data does not produce.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
