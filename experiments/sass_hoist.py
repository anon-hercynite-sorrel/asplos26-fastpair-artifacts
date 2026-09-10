# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Did the hoist survive compilation? Read it out of the SASS.

    uv run experiments/sass_hoist.py results/suite-<id>/<chip>/kernel_sass.txt

WHY STATIC AND NOT RUNTIME. H is a scheduling knob: issue up to H high-plane loads before
consuming any of them. Whether that transformation happened is a property of instruction ORDER in
the native code, and ptxas is where scheduling and register allocation both occur. NUM_REGS cannot
answer it -- it reports what was allocated, not whether the loads moved -- and runtime counters
measure the consequence rather than the transformation.

The runtime half is already settled: registers are flat across H on all three chips (56/56/56/56
on the B300, 64 across the board on H100 and L40S) and local_bytes is zero, so the hoist costs
nothing. What is open is whether it DOES anything, and that is what this reads.

THE MEASUREMENT IS A COUNT, NOT A DIFF. SASS text carries absolute offsets, so a raw diff between
two variants is almost entirely noise. Three quantities, in increasing rigour:

  1. Opcode histogram -- LDG (global), LDS/STS (shared), and total. If H=1 and H=4 agree on all
     three, nothing moved.
  2. MAX OUTSTANDING GLOBAL LOADS before the first consumer. Walk the listing and count how many
     LDGs are in flight whose destination register has not yet been read. This should track H if
     the hoist works. If it stays flat regardless of H, the hoist is inert even when instructions
     shuffled. This is the quantity that answers the question.
  3. Scheduling control bits (stall counts, yield, barrier indices). Identical barrier allocation
     on the consumers means the compiler made no scheduling change. Not parsed here: the encoding
     is undocumented and version-specific, and quantity 2 already carries the argument.

DO NOT BUILD A CLAIM ON AN OPCODE SEQUENCE. SASS is undocumented and unstable across toolkit
versions. The durable statement is the counted one -- "the number of high-plane loads in flight
before the first consumer does not increase with H" -- which survives disassembly details and is
what the design model actually asserts.

Reading the outcome:
  outstanding does NOT rise with H  -> ptxas sank the hoist back. Since H demonstrably does
      something at B=8, that makes it a pressure-dependent scheduling choice by the compiler,
      which is a sharper mechanism sentence than the paper currently has.
  outstanding rises, registers flat -> the hoist survived and is free, reusing live ranges the
      non-hoisted schedule already held. Then its null effect at B<=4 means latency was already
      covered by K, which is the latency-coverage reading.
"""
import argparse
import collections
import re
import sys

# cuobjdump listings vary in decoration across versions; match the opcode as a word rather than
# anchoring on column positions.
OPCODE = re.compile(r"\b([A-Z][A-Z0-9_.]{1,15})\b")
# Destination register is the first operand after the opcode; sources are the rest. R2, R2.64 etc.
REG = re.compile(r"\bR(\d+)\b")
HEADER = re.compile(r"^=====\s+(\S+)")
# probe_k6_t256_b4 / probe_k6_t256_b4_h3 -> K, T, B, H (H absent means 1)
COORD = re.compile(r"_k(\d+)_t(\d+)_b(\d+)(?:_h(\d+))?$")


def kernels(path):
    """name -> [instruction text] for every kernel in a kernel_sass.txt."""
    out, cur = {}, None
    for line in open(path, errors="ignore"):
        m = HEADER.match(line)
        if m:
            cur = m.group(1)
            out[cur] = []
            continue
        if cur is None:
            continue
        # A SASS body line has an opcode and usually an address in /*....*/ form.
        if "*/" in line or re.search(r"^\s+[A-Z@]", line):
            out[cur].append(line.rstrip())
    return out


PRED = re.compile(r"^@!?U?P\d+\s+")


def insn_body(text):
    """The mnemonic-and-operands part of a cuobjdump line, with both comments removed.

    A real line looks like

        /*0000*/    LDG.E R6, desc[UR4][R2.64] ;    /* 0x... */

    so the body sits BETWEEN the address comment and the trailing encoding comment. Taking the
    text after the last `*/` -- which an earlier version did -- always lands on the empty tail
    after the encoding comment, so every line parsed as having no opcode and every count came out
    zero. The analyzer still printed a verdict from those zeros, which is why this is parsed
    positionally now and why main() refuses to conclude anything from an empty histogram."""
    body = text.split("*/", 1)[1] if "*/" in text else text
    body = body.split("/*", 1)[0]                 # drop the trailing encoding comment
    return PRED.sub("", body.strip()).strip()     # drop a @P0 / @!P0 predicate guard


def opcode_of(text):
    # A regex, not lstrip("@!PT "): lstrip removes CHARACTERS from that set, so it would eat the
    # leading P of PRMT and the T of TLD.
    m = OPCODE.match(insn_body(text))
    return m.group(1) if m else None


def histogram(instrs):
    h = collections.Counter()
    for t in instrs:
        op = opcode_of(t)
        if op:
            h[op.split(".")[0]] += 1
    return h


def max_outstanding_loads(instrs):
    """Peak number of global loads in flight whose destination has not yet been read.

    A load's destination enters the in-flight set when the LDG issues and leaves it the first time
    any later instruction reads that register. The peak of that set is the depth the schedule
    actually achieves, which is what H is supposed to raise."""
    inflight, peak = {}, 0
    for t in instrs:
        op = opcode_of(t)
        if not op:
            continue
        regs = REG.findall(insn_body(t))
        if not regs:
            continue
        dst, srcs = regs[0], regs[1:]
        for r in srcs:                      # a read retires the load that produced it
            inflight.pop(r, None)
        if op.startswith("LDG"):
            inflight[dst] = True
            peak = max(peak, len(inflight))
        else:
            inflight.pop(dst, None)         # overwritten without being read
    return peak


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sass", help="kernel_sass.txt from a suite leg")
    ap.add_argument("--coord", default="k6_t256_b4",
                    help="coordinate to compare H across, e.g. k6_t256_b4")
    a = ap.parse_args()
    ks = kernels(a.sass)
    if not ks:
        sys.exit("no kernels found; is this a cuobjdump --dump-sass listing?")

    sel = sorted(n for n in ks if a.coord in n)
    if not sel:
        sys.exit(f"no kernels matching {a.coord} in {a.sass}\n"
                 f"available: {', '.join(sorted(ks)[:8])}")
    print(f"{'kernel':<34}{'total':>7}{'LDG':>6}{'LDS':>6}{'STS':>6}{'max outstanding LDG':>21}")
    for n in sel:
        h = histogram(ks[n])
        print(f"{n:<34}{sum(h.values()):>7}{h.get('LDG', 0):>6}{h.get('LDS', 0):>6}"
              f"{h.get('STS', 0):>6}{max_outstanding_loads(ks[n]):>21}")
    # REFUSE TO CONCLUDE FROM AN EMPTY PARSE. When the body extraction was wrong every count came
    # out zero and this still printed "the hoist did not change the schedule" -- a parser failure
    # rendered as a finding, which is the one outcome worse than no output. Zero instructions or
    # zero global loads means the listing was not understood, not that the kernel has no loads.
    empty = [n for n in sel if not histogram(ks[n]) or histogram(ks[n]).get("LDG", 0) == 0]
    if empty:
        sys.exit("PARSE FAILED: no instructions or no LDG in %s.\n"
                 "Refusing to report a verdict: this says the listing was not understood, not "
                 "that the schedule is flat." % ", ".join(empty))

    # WHICH COMPARISON WAS I GIVEN? The H verdict below is only meaningful for a set that varies
    # in H at ONE (K,T,B). Handed a K sweep it would still have printed it, which is the same
    # fault as printing a verdict from an empty parse: a statement about a comparison that was
    # never made. So classify the set first and refuse the ambiguous case.
    coords = {n: COORD.search(n) for n in sel}
    if any(m is None for m in coords.values()):
        sys.exit("cannot parse a coordinate from: %s"
                 % ", ".join(n for n, m in coords.items() if m is None))
    ks_seen = {int(m.group(1)) for m in coords.values()}
    hs_seen = {int(m.group(4) or 1) for m in coords.values()}
    ktb_seen = {(int(m.group(1)), int(m.group(2)), int(m.group(3))) for m in coords.values()}
    if len(ks_seen) > 1 and len(hs_seen) > 1:
        sys.exit("selection varies in BOTH K %s and H %s, so neither arm is isolated.\n"
                 "Fix one: --coord k6_t256_b4 for the H arm, --coord _t256_b4 for the K arm."
                 % (sorted(ks_seen), sorted(hs_seen)))
    # The H verdict needs ONE launch configuration. A selection spanning several B values pools a
    # B effect into an H statement: at K=6 the depth is 12 at B<=4 and 6..9 at B=8, so a pooled
    # set "varies with H" while the variation is almost entirely B.
    if len(ks_seen) == 1 and len(ktb_seen) > 1:
        sys.exit("selection spans %d launch configurations %s, so an H verdict would pool a B\n"
                 "effect into it. Name one, e.g. --coord k%d_t%d_b%d."
                 % (len(ktb_seen), sorted(ktb_seen), *sorted(ktb_seen)[0]))

    if len(ks_seen) > 1:
        # THE K ARM: is the dictionary load sunk to its use, or reissued per code?
        # Sinking emits the same LDG once, so the count grows with the per-code loads alone and is
        # linear at roughly 3K. Rematerialization reissues it, adding a fourth per code. One
        # coordinate cannot tell them apart -- 25 at K=6 satisfies 3K+7 and 4K+1 both -- so the
        # slope across the arm is the measurement.
        rows = sorted((int(coords[n].group(1)), histogram(ks[n]).get("LDG", 0)) for n in sel)
        print("\nK ARM: global loads per thread against coarsening")
        for k, ldg in rows:
            print(f"  K={k:<2} LDG={ldg}")
        if len(rows) >= 2:
            (k0, l0), (k1, l1) = rows[0], rows[-1]
            slope = (l1 - l0) / (k1 - k0)
            print(f"\n  slope = {slope:.2f} LDG per code over K={k0}..{k1}, "
                  f"intercept = {l0 - slope * k0:.1f}")
            if slope < 3.5:
                print("  VERDICT: slope below 4 -- the dictionary load was SUNK to its use, not\n"
                      "           reissued. Coarsening costs no extra global accesses, which is\n"
                      "           what Section 3.1 needs to be true.")
            else:
                print("  VERDICT: slope at or above 4 -- a load is REISSUED per code. Coarsening\n"
                      "           trades registers for access rate, which INVERTS what Section 3.1\n"
                      "           implies. This is the outcome that changes the paper.")
        return

    peaks = {n: max_outstanding_loads(ks[n]) for n in sel}

    # WITH H=0 PRESENT, "depth varies" IS NO LONGER THE QUESTION. H=1 already hoists one round, so
    # a set of H>=1 kernels can only answer "does more hoisting change the schedule". H=0 is the
    # no-hoist control, and the hoist's stated purpose is to raise the number of high-plane loads
    # in flight -- so the comparison that matters is H=0 against the rest, DIRECTIONALLY. Reporting
    # "survived" because the numbers differ would call a regression a success.
    zero = next((n for n in sel if (coords[n].group(4) or "1") == "0"), None)
    if zero is not None:
        d0 = peaks[zero]
        others = {n: d for n, d in peaks.items() if n != zero}
        if not others:
            print("\nonly H=0 present; nothing to compare it against.")
            return
        best = max(others.values())
        print(f"\nH=0 (no hoist): depth {d0}")
        for n in sorted(others):
            print(f"  {n:34s} depth {peaks[n]}")
        if best > d0:
            print(f"\nVERDICT: hoisting RAISES load depth above the no-hoist path "
                  f"({d0} -> {best}). The hoist does what it claims here.")
        elif best == d0:
            print(f"\nVERDICT: no hoist rung exceeds the no-hoist path (both {d0}). The hoist "
                  f"buys no extra memory-level parallelism at this coordinate.")
        else:
            print(f"\nVERDICT: the NO-HOIST path is DEEPER than every hoist rung "
                  f"({d0} against a best of {best}). On this measure the hoist is a net loss at "
                  f"this coordinate, and any gain seen across H>=1 is recovering ground H=1 gave\n"
                  f"         up relative to not hoisting at all.")
        return

    if len(set(peaks.values())) == 1:
        print(f"\nVERDICT: outstanding-load depth is {next(iter(peaks.values()))} for every H at "
              f"{a.coord}.\n         The hoist did not change the schedule ptxas emitted.")
    else:
        print(f"\nVERDICT: depth varies with H at {a.coord}: {peaks}.\n"
              f"         The hoist survived compilation.")


if __name__ == "__main__":
    main()
