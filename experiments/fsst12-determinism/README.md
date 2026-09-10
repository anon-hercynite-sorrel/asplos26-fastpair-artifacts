# Is FSST-12's trained dictionary platform-dependent?

**Yes — on real data.** Not on small synthetic inputs, which is why an earlier version of this
README said "No."

`cargo run --release [-- <column.bin> ...]` trains `Compressor12` and prints digests of the symbol
table. Pass one or more campaign column dumps (`[u64 n][(n+1) u32 offsets][payload]`, as under
`~/data/onpair-campaign-cols`) to train on real data; four fixed synthetic cases always run too.

Measured 2026-09-02, aarch64 macOS against x86_64 Linux:

```
                     n_symbols  table_digest        identical?
tie_saturated             847   2add3a93ec398d8d    yes
tie_sat_sampled           912   6bd900cee02f0575    yes
log_like                 1219   c9fa3c7879ab310c    yes
urlish                   1123   73d90f661ab99b45    yes
40 MB of ClickBench URL  3516   851506b18da03a52    NO -- Linux gives 3517, 39ead44a76add7fc
```

The synthetic cases train 847-1219 symbols against a 4096 code space; real columns train close to
3750, where candidate ties are dense enough for the divergence to fire. Two of the synthetic cases
were built specifically to saturate `(gain, length)` ties and still agree — so a test that stresses
the suspected mechanism is not a substitute for the data the claim is about.

The mechanism is NOT the one the paper used to name. `fsst12` is the Rust `fsst-rs` crate, not C++;
its sampler is seeded with a constant and its dedup hasher carries no random seed. What varies is
the drain of that map into the candidate heap, which separates symbols tied on both gain and length,
and hashbrown's probe order depends on an architecture-specific SIMD group width.

Consequence for the artifact: `results/suite-flat-20260830/b300/fsst12_stored_components.jsonl` was
measured on macOS against Linux-encoded cells, and seven of fifteen columns differ. See
`onpair-gpu-paper/docs/notes/2026-09-02-fsst12-platform-dependence.md`. Exposure on any reported
number is 0.039% at worst.
