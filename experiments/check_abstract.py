# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Re-derive the abstract's numbers and confirm the prose still prints them.

    uv run experiments/check_abstract.py [path/to/0_abstract.tex]

WHY THE ABSTRACT IS A SPECIAL CASE. Every other number the paper asserts can be a macro from
claims.tex, so drift fails at compile time. The abstract cannot: it is copied out of the .tex into
mail, slides and submission forms, and a macro pasted somewhere without a LaTeX engine renders as a
stray token. So its numbers are literals -- and literals are exactly what goes stale when a leg is
re-run. This closes that hole from outside the file.

WHAT IT CHECKS, and it is two things, because either alone is a hole. First, that each declared
value still re-derives from committed results. Second, that the literal still APPEARS in the
abstract body -- otherwise editing the prose and leaving the guard behind passes green while the
paper says something else. The guard block is comments at the END of the abstract file, after the
text, so it never travels with a copy-paste.

Declared as `% VERIFY <key> <literal>` lines. A key with no derivation here is a failure, not a
skip: an unrecognised key means the guard and this file have diverged, which is the state the guard
exists to prevent.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "figures"))
import suite as S  # noqa: E402

DEV = "b300"


def _de_multiples(root):
    """Our best byte-validated kernel over the engine's best configuration, per real column."""
    op = S.cells(root, DEV, "boost", "onpair")
    fs = S.cells(root, DEV, "boost", "fsst12")
    out = {}
    for _label, ds, col in S.REAL:
        best = None
        for store, bits in ((op, 12), (op, 16), (fs, 12)):
            c = store.get((ds, col, bits))
            t = S.best_rate_gb_s(c) if c else None
            if t and (best is None or t > best):
                best = t
        de = S.de_points(root, DEV, ds, col)
        if best and de:
            out[(ds, col)] = (best, max(t for _r, t, _c in de))
    return out


WORDS = {10: "ten", 11: "eleven", 12: "twelve", 9: "nine", 8: "eight"}


def derive(root):
    m = _de_multiples(root)
    mults = [o / d for o, d in m.values()]
    win = m.get(("loghub-windows", "line"))
    return {
        "de_mult_min": "%.1f" % round(min(mults), 1),
        "de_mult_max": "%.1f" % round(max(mults), 1),
        "windows_tbs": "%.1f" % round(win[0] / 1000.0, 1) if win else None,
        "real_columns": WORDS.get(len(mults), str(len(mults))),
    }


def main():
    # Was a single hardcoded ~/repos/onpair-gpu-paper, which is not where the paper lives.
    # analyze.sh exports PAPER_DIR; fall back to a short search for a direct invocation.
    import os
    _pd = os.environ.get("PAPER_DIR")
    _cands = ([Path(_pd)] if _pd else []) + [
        Path(__file__).resolve().parent.parent.parent / "onpair-gpu-paper",
        Path(__file__).resolve().parent.parent.parent.parent / "papers" / "onpair-gpu-paper",
        Path.home() / "repos" / "papers" / "onpair-gpu-paper",
        Path.home() / "repos" / "onpair-gpu-paper",
    ]
    default = next((c / "sections" / "0_abstract.tex" for c in _cands
                    if (c / "sections" / "0_abstract.tex").is_file()),
                   _cands[-1] / "sections" / "0_abstract.tex")
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    text = path.read_text()
    body = "\n".join(l for l in text.split("\n") if not l.lstrip().startswith("%"))
    declared = re.findall(r"^%\s*VERIFY\s+(\S+)\s+(.+?)\s*$", text, re.M)
    if not declared:
        print("FAIL: no '%% VERIFY' lines in %s -- the guard is gone" % path)
        return 1

    root = S.latest_root(None)
    if root is None:
        print("FAIL: no results/suite-* directory found")
        return 1
    got = derive(root)

    bad = 0
    for key, literal in declared:
        if key not in got:
            print("FAIL %-14s unknown key; the guard and check_abstract.py have diverged" % key)
            bad += 1
            continue
        want = got[key]
        if want is None:
            print("FAIL %-14s could not be derived from %s" % (key, root.name))
            bad += 1
            continue
        if literal != want:
            print("FAIL %-14s abstract declares %r, data gives %r" % (key, literal, want))
            bad += 1
            continue
        if literal not in body:
            print("FAIL %-14s declares %r but the abstract text no longer prints it"
                  % (key, literal))
            bad += 1
            continue
        print("ok   %-14s %s" % (key, literal))
    print("abstract: %d value(s) checked, %d failed" % (len(declared), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
