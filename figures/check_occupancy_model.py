# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Check the paper's occupancy formula against CUDA's own occupancy calculator.

WHAT THIS IS NOT. `blocks_per_sm` in the probe output comes from
`cuOccupancyMaxActiveBlocksPerMultiprocessor` (jobs/onpair-resource-probe.sh:134); the kernels are
never launched. So this compares OUR hand formula against NVIDIA's calculator over the same
compiled kernels -- agreement between two calculations, not agreement with observed hardware
residency. Claiming the latter would overstate it. What it does establish is that the paper's
arithmetic reproduces the vendor's allocation rules, including the granularities below.

    predicted_blocks = min( 65536         // (granule(regs_per_thread) * T),
                            shared_per_sm // (static_shared + PER_BLOCK_RESERVED),
                            max_warps     // (T / 32) )

NOTE ON min_blocks (corrected 2026-08-21 after a codex re-derivation): a row whose measured
blocks_per_sm is BELOW the min_blocks it was compiled for is NOT evidence of an unsatisfiable
launch bound. __launch_bounds__(T, minBlocksPerMultiprocessor) constrains the compiler's REGISTER
allocation; it does not promise that many blocks will be resident. When shared memory binds
instead, achieved residency is legitimately lower, and the min() model above predicts exactly
that. Excluding those rows was wrong, so the exclusion is reported as an ablation rather than
applied.
"""
import glob, json, os, sys

REGS_PER_SM = 65536
WARP = 32
GRANULE_REGS_PER_WARP = 256
PER_BLOCK_RESERVED = 1024
SHARED_GRANULE = 128   # CUDA rounds a block's total shared allocation up to 128 B on these arches
SHARED_PER_SM = {"a100": 164*1024, "l40s": 100*1024, "h100": 228*1024, "b300": 228*1024}
# Committed, pinned, one capture per chip. The previous glob read ~/agents/harness, which no clean
# clone has -- HOME=/tmp/empty found zero rows and died in a ZeroDivisionError -- and it swept every
# historical capture, so the row set depended on what happened to be on the machine.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = os.path.join(ROOT, "results", "resource-probe-20260818", "*_kernel_resources.jsonl")
EXPECT_ROWS_PER_CHIP = 120

def granule(r):
    if r <= 0: return 0
    return (-(-(r*WARP)//GRANULE_REGS_PER_WARP)*GRANULE_REGS_PER_WARP)//WARP

rows=[]
files=sorted(glob.glob(PROBE))
if not files:
    sys.exit("no committed probe inputs at %s" % PROBE)
for f in files:
    chip=os.path.basename(f).split("_kernel_resources")[0]
    for line in open(f):
        line=line.strip()
        if not line: continue
        try: d=json.loads(line)
        except json.JSONDecodeError: continue
        d["_chip"]=chip; rows.append(d)

# DEDUPE. The probe legs were collected twice for a100/h100/b300 and once for l40s, so the raw
# row set double-counts three chips and single-counts the one where the model differs most, which
# skews every aggregate. Key on the identity of a kernel configuration, not on the file it came from.
seen=set(); dedup=[]
for r in rows:
    k=(r.get("_chip"), r.get("kernel"), r.get("block_threads"), r.get("min_blocks"),
       r.get("tokens_per_thread"), r.get("regs_per_thread"), r.get("static_shared_bytes"))
    if k in seen: continue
    seen.add(k); dedup.append(r)
rows=dedup

# Fail early and loudly on an inventory that is not what the analysis assumes.
per_chip={}
for r in rows: per_chip[r["_chip"]]=per_chip.get(r["_chip"],0)+1
bad=[(c,n) for c,n in sorted(per_chip.items()) if n!=EXPECT_ROWS_PER_CHIP]
if bad:
    sys.exit("inventory is not %d rows per chip: %s" % (EXPECT_ROWS_PER_CHIP, bad))

usable=[r for r in rows if r.get("buildable") and r.get("blocks_per_sm") and r["_chip"] in SHARED_PER_SM
        and r.get("block_threads") and r.get("regs_per_thread")]

def predict(r, rounding=True, reserve=True, granulate_shared=True):
    T=r["block_threads"]
    regs=granule(r["regs_per_thread"]) if rounding else r["regs_per_thread"]
    shared=(r.get("static_shared_bytes") or 0)+(PER_BLOCK_RESERVED if reserve else 0)
    if shared and granulate_shared:
        shared=-(-shared//SHARED_GRANULE)*SHARED_GRANULE
    by_r=REGS_PER_SM//(regs*T)
    by_s=SHARED_PER_SM[r["_chip"]]//shared if shared else 10**6
    by_w=(r.get("max_warps_per_sm") or 64)//max(1,T//WARP)
    return min(by_r,by_s,by_w),by_r,by_s,by_w

below=[r for r in usable if (r.get("min_blocks") or 0) and r["blocks_per_sm"]<r["min_blocks"]]
print("usable rows: %d   of which blocks_per_sm < min_blocks: %d" % (len(usable), len(below)))
ok_below=sum(1 for r in below if predict(r)[0]==r["blocks_per_sm"])
print("  -> of those %d, the model predicts %d EXACTLY (%.0f%%)"
      % (len(below), ok_below, 100*ok_below/len(below) if below else 0))
print("     so they are shared-memory-limited, not unsatisfiable. NOT excluded.\n")

print("%-6s %6s %8s %9s %7s   %s" % ("chip","n","exact","within1","worse","binding term"))
tot=[0,0,0]
for chip in ("a100","l40s","h100","b300"):
    sub=[r for r in usable if r["_chip"]==chip]
    if not sub: continue
    e=w=x=0; binds={"regs":0,"shared":0,"warps":0}
    for r in sub:
        p,br,bs,bw=predict(r); m=r["blocks_per_sm"]
        if p==m: e+=1
        elif abs(p-m)<=1: w+=1
        else: x+=1
        lo=min(br,bs,bw)                      # ties counted in EVERY limiting term, not just regs
        if br==lo: binds["regs"]+=1
        if bs==lo: binds["shared"]+=1
        if bw==lo: binds["warps"]+=1
    n=e+w+x; tot[0]+=e; tot[1]+=w; tot[2]+=x
    print("%-6s %6d %7.0f%% %8.0f%% %6.0f%%   %s" % (chip,n,100*e/n,100*w/n,100*x/n,
          ", ".join("%s %d"%kv for kv in sorted(binds.items(), key=lambda k:-k[1]))))
N=sum(tot)
print("\nALL    %6d %7.0f%% %8.0f%% %6.0f%%" % (N,100*tot[0]/N,100*tot[1]/N,100*tot[2]/N))

print("\nablation (exact-match rate over all %d usable rows):" % N)
for lbl,rd,rv,*g in (("as modelled",True,True),("no granule rounding",False,True),
                  ("no 1 KiB reservation",True,False),("no 128 B shared granule",True,True,False),("neither",False,False)):
    gs=g[0] if g else True
    ok=sum(1 for r in usable if predict(r,rd,rv,gs)[0]==r["blocks_per_sm"])
    print("  %-22s %4d/%4d = %3.0f%%" % (lbl,ok,N,100*ok/N))
