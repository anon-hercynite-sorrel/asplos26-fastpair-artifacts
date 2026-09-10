# `b300-widthncu-eval` — the access-width isolation on EVALUATED columns

B300 SXM6, Nebius uk-south1, 2026-08-13. Harness run `b300-fineweb-widthncu-*`, vortex rev
`2d909147f`. Four captures, all CAPTURE-VERIFIED: FineWeb `text` and Wikipedia `text`, each
under `split8read` and the stride-16 `onpair_shmem_4tpt`.

Supersedes the ClickBench `MobilePhoneModel` isolation in `b300-splitncu` for the paper's
purposes. That column isolates access width most cleanly (frac_le8 = 0.991, so the long-token
fallback essentially never fires) but is a DIAGNOSTIC column outside `tab:datasets`. FineWeb
(0.986) and Wikipedia (0.981) have effectively the same property and ARE evaluated columns,
so citing them removes the disclosure without weakening the isolation.

split8read / stride-16:

| column | frac_le8 | wavefronts | sectors | sm cycles | L1 hit% |
|---|---|---|---|---|---|
| FineWeb `text` | 0.986 | **0.767** | 1.002 | 0.892 | 89.0 -> 90.9 |
| Wikipedia `text` | 0.981 | **0.780** | 1.004 | 0.903 | 89.1 -> 91.0 |

Same shape as the diagnostic column: wavefronts fall by about a quarter, sector count is flat
to within 0.4%, and the hit rate moves under two points. The wavefront drop is slightly
smaller than MobilePhoneModel's 0.72 because these columns' fallback fires marginally more
often, which is the direction the (1 - frac_le8) term predicts.
