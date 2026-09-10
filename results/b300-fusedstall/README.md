# `b300-fusedstall` — fused output positioning is slow for a reason that is not our stall

B300 SXM6 (sm_103), Nebius uk-south1, 2026-08-15. Harness run
`b300-fusedstall-20260814-231350`, vortex rev `96809ccf6` on branch
`mp/onpair-expts-0810`. Two cells, ClickBench `URL` and TPC-H `l_comment`, 1 GB single
chunk, FastPair-12, 100 iterations, every kernel byte-validated in the same run.

Answers three open questions in one session. All rates are relative to the shipped
`onpair_shmem_4tpt_split8read` measured on the same cell in the same run.

## 1. Removing the block-wide stall is worth nothing

Fused positioning computes each batch's output position DURING the decode, instead of
reading it from the stored sidecar or regenerating it in a separate pass. The existing
kernel measured about 2.9x slower than the shipped decode, and that number was reported as
a fact about our kernel rather than about the technique, because warp 0 performed the
look-back while the other fifteen warps waited at a barrier.

`onpair_shmem_4tpt_split8read_lookback_noshift` removes that stall: it emits at scratch
offset 0, so the emit no longer depends on `out_start` and runs in warps 1..N-1 while warp 0
is stalled on descriptor latency, and the drain pays the resulting misalignment on the read
side with two aligned shared words and a funnel shift. The two kernels are otherwise
identical -- same ticket ring, epoch tagging, release/acquire protocol, ballot-first
look-back -- so the gap between them is the stall and nothing else.

| kernel | ClickBench URL | TPC-H l_comment | geomean |
|---|---|---|---|
| fused, base (stalls) | 0.334x | 0.368x | **0.350x** |
| fused, NO stall | 0.336x | 0.365x | **0.350x** |

**1.00x.** The stall costs nothing measurable. The hypothesis that motivated this kernel
was wrong, and the earlier caveat that the fused number did not bound the technique is now
itself bounded: the largest named handicap is gone and the number did not move.

## 2. The block-width sweep says the same thing, in the opposite direction

The base kernel's width sweep exists to measure the same stall independently: at one warp
per block nothing waits, so narrowing the block should recover the idle time.

| configuration | ClickBench URL | TPC-H l_comment | geomean |
|---|---|---|---|
| 16 warps/block (default) | 0.334x | 0.368x | 0.350x |
| 4 warps/block | 0.255x | 0.270x | 0.263x |
| 2 warps/block | 0.215x | 0.228x | 0.221x |
| 1 warp/block | 0.148x | 0.154x | **0.151x** |

Narrower is monotonically WORSE, and the configuration where nothing stalls at all is the
worst by a factor of 2.3. Both experiments therefore refute the stall account from opposite
directions. What costs is the look-back's cross-block coordination -- more blocks means more
descriptor traffic per unit of work and less intra-block reuse -- and with many blocks
resident the SM already hides one block's spin behind another block's work, which is why
removing the intra-block idle recovers nothing.

**Consequence for the paper.** Section~\ref{sec:contrib:positions} justifies the stored
sidecar against regeneration as a SEPARATE PASS (14-19%). The obvious reviewer reply is to
fuse the regeneration into the decode instead, which pays neither the sidecar's storage nor
a second pass over the codes. That option is now measured, on a correct implementation,
without the handicap it could have been dismissed for: about 2.9x slower than reading the
position from the sidecar.

## 3. Streaming hint on the drain edges: no effect

`onpair_shmem_4tpt_split8read_stcsedge` gives the head and tail drain stores the evict-first
policy the aligned body already has via `__stcs`. Head plus tail is at most 15 + 15 bytes per
warp against roughly 768 B of output, so the question was cache pollution rather than bytes.

| cell | rel. shipped |
|---|---|
| ClickBench URL | 1.004x |
| TPC-H l_comment | 0.998x |
| geomean | **1.001x** |

Inside run-to-run dispersion on both cells. The edges are not worth a policy change, and the
shipped kernel's mixed policy costs nothing.

## Correctness

`lookback_test.log`: 2 passed, 0 failed, **0 ignored**. (Two dependency-resolution lines in
that log named their source organisation; the org is replaced with `<redacted-org>` and the
crate and revision are untouched. Everything else is verbatim cargo output.) The 0-ignored
matters --
`vortex_cuda_macros::test` degrades to `#[test] #[ignore]` without nvcc, so a green run with
zero tests would be a false pass, and the job asserts the count. Every case runs against BOTH
look-back kernels; the noshift kernel changes the drain's addressing, which is where an
off-by-one on a shifted output would hide. Independently, every rate above carries its own
`verified: true` from the bench's byte-validation, and the experimental kernels are excluded
from `best_kernel` selection so none can leak into a headline.

The timing job runs the differential test as a GATE before any measurement: a rate from an
unverified kernel is worse than no rate.
