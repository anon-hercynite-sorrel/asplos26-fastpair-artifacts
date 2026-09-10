#!/usr/bin/env bash
# Regenerate figures and check recorded values; PAPER_DIR enables manuscript comparisons.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
ANALYZE_TMP="$(mktemp -d "${TMPDIR:-/tmp}/fastpair-analyze.XXXXXX")"
# Retain logs for failures and independent simultaneous checkouts.
echo "Analysis logs: $ANALYZE_TMP"

# Keep the committed figure list usable without a manuscript checkout.
FIGLIST="experiments/paper-figures.txt"
[ -f "$FIGLIST" ] || { echo "FATAL: missing $FIGLIST"; exit 2; }

if [ -z "${PAPER_DIR:-}" ]; then
  for cand in "$ROOT/../onpair-gpu-paper" "$ROOT/../../papers/onpair-gpu-paper" \
              "$HOME/repos/papers/onpair-gpu-paper" "$HOME/repos/onpair-gpu-paper"; do
    if [ -f "$cand/main.tex" ]; then PAPER_DIR="$(cd "$cand" && pwd)"; break; fi
  done
fi
if [ -n "${PAPER_DIR:-}" ] && [ ! -f "${PAPER_DIR}/main.tex" ]; then
  echo "  note: PAPER_DIR=\"$PAPER_DIR\" has no main.tex -- proceeding without a manuscript"
  PAPER_DIR=""
fi
PAPER_DIR="${PAPER_DIR:-}"
export PAPER_DIR
SKIPPED=0

paper_figs(){
  grep -ho 'includegraphics\[[^]]*\]{[^}]*}' "$PAPER_DIR"/sections/*.tex "$PAPER_DIR"/main.tex 2>/dev/null \
    | sed -e 's/.*{//' -e 's/}$//' -e 's#.*/##' -e 's/\.pdf$//' | sort -u
}
committed_figs(){ grep -v '^[[:space:]]*#' "$FIGLIST" | grep -v '^[[:space:]]*$' | sort -u; }

# Use a loop rather than mapfile for compatibility with Bash 3.2.
LIVE_FIGS=()
MISSING_GEN=()
while read -r f; do
  [ -n "$f" ] || continue
  if [ -f "figures/$f.py" ]; then LIVE_FIGS+=("$f"); else MISSING_GEN+=("$f"); fi
done <<EOF
$(committed_figs)
EOF
if [ "${#LIVE_FIGS[@]}" -eq 0 ]; then
  echo "FATAL: $FIGLIST names no figure with a generator in figures/"; exit 2
fi

if [ -n "$PAPER_DIR" ]; then
  if ! diff -u <(committed_figs) <(paper_figs) > "$ANALYZE_TMP/figset.diff" 2>&1; then
    echo "FATAL: $FIGLIST disagrees with what the paper prints (-committed +paper):"
    sed -n '3,$p' "$ANALYZE_TMP/figset.diff" | sed 's/^/    /'
    echo "    Update $FIGLIST -- see the regeneration command in its header."
    exit 1
  fi
  echo "== ${#LIVE_FIGS[@]} figures, committed set verified against the manuscript =="
else
  echo "== ${#LIVE_FIGS[@]} figures, from $FIGLIST (no manuscript checkout found) =="
fi
for f in "${MISSING_GEN[@]:-}"; do
  [ -n "$f" ] && echo "  note: $f is in the figure set and has no generator here"
done

command -v uv >/dev/null 2>&1 || { echo "FATAL: need 'uv' (https://docs.astral.sh/uv/)"; exit 2; }

echo "== regenerating tab:datasets rows from ${CLAIM_LEG:-results/suite-paper-20260821} =="
if ! uv run figures/tab_datasets_suite.py > "$ANALYZE_TMP/tab_datasets.regen" 2>"$ANALYZE_TMP/tab_datasets.err"; then
  echo "FATAL: could not regenerate the tab:datasets rows"; cat "$ANALYZE_TMP/tab_datasets.err"; exit 1
fi
if [ -n "$PAPER_DIR" ]; then
  if ! uv run experiments/check_tab_datasets.py "$ANALYZE_TMP/tab_datasets.regen"; then
    echo "FATAL: tab:datasets in the paper disagrees with what the data produces"; exit 1
  fi
else
  echo "  SKIP comparison against the paper's printed table (no manuscript checkout)"
  SKIPPED=$((SKIPPED+1))
fi

if [ -n "$PAPER_DIR" ]; then
  echo "== checking the abstract's literals against the data =="
  if ! uv run experiments/check_abstract.py "$PAPER_DIR/sections/0_abstract.tex"; then
    echo "FATAL: the abstract's numbers disagree with the data, or the prose stopped printing them"; exit 1
  fi
else
  echo "== SKIP the abstract's literals (no manuscript checkout) =="
  SKIPPED=$((SKIPPED+1))
fi

# Select the paper suite explicitly; the claim script has a different default.
CLAIM_LEG="${CLAIM_LEG:-results/suite-paper-20260821}"
echo "== regenerating the Section 3-5 claim macros from ${CLAIM_LEG} =="
CLAIMS_TEX="${CLAIMS_TEX:-${PAPER_DIR:+$PAPER_DIR/sections/generated/claims.tex}}"
uv run experiments/paper_claims.py --suite-root "$CLAIM_LEG" --emit-tex "$ANALYZE_TMP/claims.regen.tex" || {
  echo "FATAL: could not derive the claim macros"; exit 1; }
if [ -n "$CLAIMS_TEX" ] && [ -f "$CLAIMS_TEX" ]; then
  if ! diff -q "$CLAIMS_TEX" "$ANALYZE_TMP/claims.regen.tex" >/dev/null; then
    echo "FATAL: $CLAIMS_TEX is stale. Diff:"
    diff "$CLAIMS_TEX" "$ANALYZE_TMP/claims.regen.tex" || true
    exit 1
  fi
else
  echo "  SKIP comparison against the paper's committed claims.tex (no manuscript checkout)"
  SKIPPED=$((SKIPPED+1))
fi
echo "== re-deriving the declared Section 3-5 claims =="
if ! uv run experiments/paper_claims.py --suite-root "$CLAIM_LEG" --check; then
  echo "FATAL: a Section 3-4 claim does not re-derive (see above)"
  exit 1
fi

echo "== regenerating ${#LIVE_FIGS[@]} figures from results/ =="
figfail=0
for f in "${LIVE_FIGS[@]}"; do
  if uv run "figures/$f.py" >"$ANALYZE_TMP/verify_$f.log" 2>&1; then
    echo "  ok   $f"
  else
    echo "  FAIL $f  (see $ANALYZE_TMP/verify_$f.log)"; tail -3 "$ANALYZE_TMP/verify_$f.log" | sed 's/^/        /'
    figfail=$((figfail+1))
  fi
done

echo
echo "== selected boost pipes captures and five-bin reduction =="
uv run experiments/check_pipes.py --check
pipesrc=$?

echo "== Zstd archived settings and validation evidence =="
python3 experiments/zstd/check.py
zstdrc=$?

echo "== bounded B300 workflow records =="
python3 experiments/check_bounded.py > "$ANALYZE_TMP/verify_bounded.log" 2>&1
boundedrc=$?
if [ "$boundedrc" = 0 ]; then
  tail -1 "$ANALYZE_TMP/verify_bounded.log"
else
  cat "$ANALYZE_TMP/verify_bounded.log"
fi

echo "== sidecar-regeneration penalty =="
uv run experiments/regen_penalty.py --check > "$ANALYZE_TMP/verify_regen.log" 2>&1
regenrc=$?
if [ "$regenrc" = 0 ]; then
  tail -4 "$ANALYZE_TMP/verify_regen.log" | sed 's/^/  /'
else
  echo "  FAIL regen_penalty (see $ANALYZE_TMP/verify_regen.log)"; tail -6 "$ANALYZE_TMP/verify_regen.log" | sed 's/^/        /'
fi

echo
echo "== re-deriving headline numbers =="
uv run experiments/validate.py
valrc=$?

echo
if [ "$figfail" = 0 ] && [ "$valrc" = 0 ] && [ "$regenrc" = 0 ] && [ "$pipesrc" = 0 ] && [ "$zstdrc" = 0 ] && [ "$boundedrc" = 0 ]; then
  if [ "$SKIPPED" = 0 ]; then
    echo "ANALYZE OK -- all figures rebuilt and all headline numbers re-derive from committed data,"
    echo "and the three cross-repo guards agree with the manuscript."
  else
    echo "ANALYZE OK -- all figures rebuilt and all headline numbers re-derive from committed data."
    echo "$SKIPPED of 3 manuscript guards skipped: no manuscript checkout was found, so the printed"
    echo "tab:datasets rows, the abstract's literals and the committed claims.tex were not compared"
    echo "against it. Everything derivable from results/ alone was checked. Set PAPER_DIR to a"
    echo "manuscript checkout to run those three as well."
  fi
  exit 0
fi
echo "ANALYZE FAILED -- figures_failed=$figfail validate_rc=$valrc regen_rc=$regenrc pipes_rc=$pipesrc zstd_rc=$zstdrc bounded_rc=$boundedrc"
exit 1
