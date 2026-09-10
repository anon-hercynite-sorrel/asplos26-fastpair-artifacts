//! OnPair CPU decode microbenchmark.
//!
//! Three decode layouts over identical compressed columns, all using inlined
//! copies (no runtime-length `memcpy`), so the only differences are addressing
//! and copy strategy:
//!   * **fat** — the current `onpair` crate decoder: `data + code*16`, one
//!     independent fixed-stride load per token + 16-byte over-copy. This work's
//!     layout; structurally FSST's fixed-stride decode at OnPair's dict scale.
//!   * **entries** — variable-stride addressing (`dict_offsets[c] → dict_bytes`,
//!     a *dependent* offset→bytes load) with the same 16-byte over-copy. This IS
//!     the published OnPair decode (Gargiulo & Venturini, arXiv:2508.02280):
//!     a compact Arrow-style offsets dict + fixed 16-byte over-copy.
//!   * **naive** — variable-stride addressing + an inlined *exact* per-token copy
//!     (`copy_token_bytes`). A simple non-over-copying baseline to ground the
//!     others; NOT a real codec (every real one over-copies).
//!
//! All three produce byte-identical output (asserted before timing). Reports
//! decode throughput (GiB/s of output) at 1 / 4 / 8 threads per column. Build
//! with `RUSTFLAGS="-C target-cpu=native"`.

use std::mem::MaybeUninit;
use std::time::Instant;

use onpair::{
    compress, decompress, decompress_into_unchecked, decompressed_len, Bits, Config, Parts,
    DEFAULT_CONFIG,
};

mod competitors;

/// Thread counts to sweep, from `ONPAIR_BENCH_THREADS` (comma-separated), default 1/4/8.
fn thread_counts() -> Vec<usize> {
    match std::env::var("ONPAIR_BENCH_THREADS") {
        Ok(s) => {
            let v: Vec<usize> = s.split(',').filter_map(|x| x.trim().parse().ok()).collect();
            if v.is_empty() { vec![1, 4, 8] } else { v }
        }
        Err(_) => vec![1, 4, 8],
    }
}
const TARGET_SECS: f64 = 0.7;
/// Untimed warmup passes dropped before the timed passes (faults in pages, warms caches/branch
/// predictors). Matches the GPU bench's discard-then-measure discipline (vs the old single warmup).
const WARMUP_PASSES: usize = 3;
/// Upper bound on timed passes per cell. We log raw per-pass nanoseconds and reduce with `min` at
/// figure-gen (the GPU convention: `decoded_bytes / min(decode_ns_iters)`). ~100 samples is plenty
/// for a stable min; capped so the 10-machine fleet sweep stays bounded (see also TARGET_SECS).
const MAX_TIMED_PASSES: usize = 100;
/// Floor on timed passes, so even a slow ~256 MiB decode still yields a few raw samples for the min.
const MIN_TIMED_PASSES: usize = 3;

// ----------------------------- deterministic corpus -----------------------------

struct Lcg(u64);
impl Lcg {
    #[inline]
    fn next(&mut self) -> u64 {
        self.0 = self
            .0
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        self.0
    }
    #[inline]
    fn below(&mut self, n: usize) -> usize {
        ((self.next() >> 33) as usize) % n
    }
}

fn push_row(bytes: &mut Vec<u8>, offsets: &mut Vec<u32>, row: &[u8]) {
    bytes.extend_from_slice(row);
    offsets.push(bytes.len() as u32);
}

/// ClickBench-style URLs: small vocabulary, long shared prefixes.
fn gen_urls(target: usize) -> (Vec<u8>, Vec<u32>) {
    let hosts = ["example.com", "test.org", "data.io", "shop.net", "news.co"];
    let paths = ["index", "page", "item", "user", "search", "product", "article", "list"];
    let mut b = Vec::with_capacity(target + 4096);
    let mut o = vec![0u32];
    let mut r = Lcg(0x1234_5678);
    let mut i = 0u64;
    while b.len() < target {
        let row = format!(
            "https://www.{}/{}/{}?id={}&q={}",
            hosts[r.below(hosts.len())],
            paths[r.below(paths.len())],
            paths[r.below(paths.len())],
            i % 100_000,
            i % 37
        );
        push_row(&mut b, &mut o, row.as_bytes());
        i += 1;
    }
    (b, o)
}

/// TPC-H comment-style: random words from a small pool.
fn gen_comments(target: usize) -> (Vec<u8>, Vec<u32>) {
    let words = [
        "the", "quick", "carefully", "ironic", "requests", "across", "final", "deposits",
        "blithely", "regular", "accounts", "sleep", "furiously", "pending", "theodolites",
        "express", "packages", "among", "slyly", "bold",
    ];
    let mut b = Vec::with_capacity(target + 4096);
    let mut o = vec![0u32];
    let mut r = Lcg(0xdead_beef);
    while b.len() < target {
        let n = 6 + r.below(20);
        let mut row = Vec::new();
        for k in 0..n {
            if k > 0 {
                row.push(b' ');
            }
            row.extend_from_slice(words[r.below(words.len())].as_bytes());
        }
        push_row(&mut b, &mut o, &row);
    }
    (b, o)
}

/// Natural-text-style: large random vocabulary, long rows (high-cardinality dict).
fn gen_text(target: usize) -> (Vec<u8>, Vec<u32>) {
    let mut r = Lcg(0x00C0_FFEE);
    let vocab: Vec<String> = (0..2000)
        .map(|_| {
            let len = 3 + r.below(9);
            (0..len).map(|_| (b'a' + r.below(26) as u8) as char).collect()
        })
        .collect();
    let mut b = Vec::with_capacity(target + 4096);
    let mut o = vec![0u32];
    while b.len() < target {
        let n = 20 + r.below(60);
        let mut row = Vec::new();
        for k in 0..n {
            if k > 0 {
                row.push(b' ');
            }
            row.extend_from_slice(vocab[r.below(vocab.len())].as_bytes());
        }
        push_row(&mut b, &mut o, &row);
    }
    (b, o)
}

// ----------------------------- inlined copy primitives (from onpair scalar.rs) -----------------------------

#[inline(always)]
unsafe fn copy16(src: *const u8, dst: *mut u8) {
    dst.cast::<[u8; 16]>()
        .write_unaligned(src.cast::<[u8; 16]>().read_unaligned());
}

/// Inlined exact copy of `len <= 16` bytes via overlapping power-of-two stores.
#[inline(always)]
unsafe fn copy_token_bytes(src: *const u8, dst: *mut u8, len: usize) {
    match len {
        0 => {}
        1 => *dst = *src,
        2 | 3 => {
            dst.cast::<u16>().write_unaligned(src.cast::<u16>().read_unaligned());
            dst.add(len - 2)
                .cast::<u16>()
                .write_unaligned(src.add(len - 2).cast::<u16>().read_unaligned());
        }
        4..=7 => {
            dst.cast::<u32>().write_unaligned(src.cast::<u32>().read_unaligned());
            dst.add(len - 4)
                .cast::<u32>()
                .write_unaligned(src.add(len - 4).cast::<u32>().read_unaligned());
        }
        8..=15 => {
            dst.cast::<u64>().write_unaligned(src.cast::<u64>().read_unaligned());
            dst.add(len - 8)
                .cast::<u64>()
                .write_unaligned(src.add(len - 8).cast::<u64>().read_unaligned());
        }
        _ => copy16(src, dst),
    }
}

// ----------------------------- the three decode paths -----------------------------

#[derive(Copy, Clone, Debug)]
enum Kind {
    Fat,
    Entries,
    Naive,
}

/// `entries`: dependent offset→bytes load, 16-byte over-copy (needs ≥16 slack past `out_len`).
#[inline]
unsafe fn decode_entries_unchecked(p: Parts, out: *mut u8) -> usize {
    let db = p.dict_bytes.as_ptr();
    let off = p.dict_offsets;
    let mut w = 0usize;
    for &code in p.codes {
        let c = code as usize;
        let s = *off.get_unchecked(c) as usize;
        let len = *off.get_unchecked(c + 1) as usize - s;
        copy16(db.add(s), out.add(w));
        w += len;
    }
    w
}

/// `naive`: dependent offset→bytes load, inlined exact copy (non-over-copying baseline).
#[inline]
unsafe fn decode_naive_unchecked(p: Parts, out: *mut u8) -> usize {
    let db = p.dict_bytes.as_ptr();
    let off = p.dict_offsets;
    let mut w = 0usize;
    for &code in p.codes {
        let c = code as usize;
        let s = *off.get_unchecked(c) as usize;
        let len = *off.get_unchecked(c + 1) as usize - s;
        copy_token_bytes(db.add(s), out.add(w), len);
        w += len;
    }
    w
}

#[inline]
fn decode(kind: Kind, p: Parts, buf: &mut [MaybeUninit<u8>]) -> usize {
    let op = buf.as_mut_ptr() as *mut u8;
    unsafe {
        match kind {
            Kind::Fat => decompress_into_unchecked(p, buf),
            Kind::Entries => decode_entries_unchecked(p, op),
            Kind::Naive => decode_naive_unchecked(p, op),
        }
    }
}

// ----------------------------- timing -----------------------------

/// Serialize raw per-pass nanoseconds as a JSON array literal (matches the hand-written JSON
/// emission used elsewhere in this bench; no serde dependency).
fn ns_array(ns: &[u64]) -> String {
    let body: Vec<String> = ns.iter().map(|v| v.to_string()).collect();
    format!("[{}]", body.join(","))
}

/// Time one `kind` decode at `threads`-way concurrency with FULL RAW PROVENANCE.
///
/// Every worker allocates its output buffer ONCE (no allocation inside the timed region), runs
/// `WARMUP_PASSES` untimed passes, then `passes` timed passes — each pass is one full decode of the
/// whole `out_len` payload, wrapped in its own `Instant` so we capture a raw per-pass nanosecond
/// sample. `Instant::now()` overhead is ns-scale against a multi-ms 256 MiB decode, so the sampling
/// is non-perturbing. All workers run concurrently inside one scope, so their per-pass times reflect
/// the loaded (shared-memory-contended) state — the same regime the old single window measured.
///
/// Returns `(gibs, ns_iters)` where:
///   * `ns_iters` is the pooled raw per-pass times across ALL threads (one u64 ns per timed pass per
///     thread) — logged verbatim so figure-gen owns min/median/dispersion (GPU-bench parity).
///   * `gibs` is the aggregate throughput derived from the MIN per-pass time (the noise-floor
///     reduction: best achievable per-thread rate, scaled by `threads`), i.e.
///     `threads * out_len / min_ns / 2^30` GiB/s — the same shape as the old mean-window formula
///     (`threads * iters * out_len / total_secs`) with `min` swapped in for the window mean.
fn run_threads(p: Parts, threads: usize, kind: Kind) -> (f64, Vec<u64>) {
    let out_len = decompressed_len(p);
    let cap = out_len + 16; // slack so the entries over-copy of the last token stays in bounds

    // Size the timed pass count from a single warmup decode: aim for ~TARGET_SECS of decoding,
    // floored at MIN_TIMED_PASSES and capped at MAX_TIMED_PASSES (~100) so a fast column does not
    // blow the per-cell budget on the 10-machine fleet. This probe also faults in the buffer.
    let mut probe: Vec<MaybeUninit<u8>> = Vec::with_capacity(cap);
    unsafe { probe.set_len(cap) };
    let t0 = Instant::now();
    std::hint::black_box(decode(kind, p, &mut probe));
    let one = t0.elapsed().as_secs_f64().max(1e-9);
    let passes = ((TARGET_SECS / one).ceil() as usize)
        .clamp(MIN_TIMED_PASSES, MAX_TIMED_PASSES);

    // Each worker returns its own Vec<u64> of raw per-pass nanoseconds; we pool them after the join.
    let per_thread: Vec<Vec<u64>> = std::thread::scope(|s| {
        let handles: Vec<_> = (0..threads)
            .map(|_| {
                s.spawn(move || {
                    // Allocate ONCE, before any timing.
                    let mut buf: Vec<MaybeUninit<u8>> = Vec::with_capacity(cap);
                    unsafe { buf.set_len(cap) };
                    // Untimed warmup: drop the first WARMUP_PASSES passes entirely.
                    for _ in 0..WARMUP_PASSES {
                        std::hint::black_box(decode(kind, p, &mut buf));
                    }
                    // Timed passes: one Instant per full-payload decode -> one raw ns sample.
                    let mut ns: Vec<u64> = Vec::with_capacity(passes);
                    for _ in 0..passes {
                        let t = Instant::now();
                        std::hint::black_box(decode(kind, p, &mut buf));
                        ns.push(t.elapsed().as_nanos() as u64);
                    }
                    ns
                })
            })
            .collect();
        handles.into_iter().map(|h| h.join().unwrap()).collect()
    });

    let ns_iters: Vec<u64> = per_thread.into_iter().flatten().collect();
    // MIN per-pass time is the correct microbenchmark noise floor (scheduling/boost removed).
    let min_ns = ns_iters.iter().copied().min().unwrap_or(0).max(1) as f64;
    // out_len/min_ns is the best per-thread rate; scale by threads for the aggregate (old formula's
    // shape). min_ns is in nanoseconds, so divide by 1e9 to get seconds.
    let gibs =
        (threads as f64 * out_len as f64) / (min_ns / 1e9) / (1u64 << 30) as f64;
    (gibs, ns_iters)
}

/// Decode `kind` into a fresh buffer and return the logical `out_len` bytes.
fn decode_to_vec(kind: Kind, p: Parts) -> Vec<u8> {
    let out_len = decompressed_len(p);
    let mut buf: Vec<MaybeUninit<u8>> = Vec::with_capacity(out_len + 16);
    unsafe { buf.set_len(out_len + 16) };
    decode(kind, p, &mut buf);
    (0..out_len).map(|i| unsafe { buf[i].assume_init() }).collect()
}

/// Read a column .bin (u64 n; (n+1) u32 offsets LE; then the bytes) into (bytes, offsets).
fn read_bin(path: &str) -> std::io::Result<(Vec<u8>, Vec<u32>)> {
    let data = std::fs::read(path)?;
    let n = u64::from_le_bytes(data[0..8].try_into().unwrap()) as usize;
    let off0 = 8;
    let mut offsets = Vec::with_capacity(n + 1);
    for i in 0..=n {
        let s = off0 + i * 4;
        offsets.push(u32::from_le_bytes(data[s..s + 4].try_into().unwrap()));
    }
    let bytes = data[off0 + (n + 1) * 4..].to_vec();
    Ok((bytes, offsets))
}

/// Repeat a column until it covers `target` bytes. Replication leaves the dictionary unchanged,
/// so a small shipped sample still measures a memory-bound working set.
fn replicate(bytes: &[u8], offsets: &[u32], target: usize) -> (Vec<u8>, Vec<u32>) {
    if bytes.is_empty() {
        return (bytes.to_vec(), offsets.to_vec());
    }
    let reps = ((target + bytes.len() - 1) / bytes.len()).max(1);
    let mut b = Vec::with_capacity(bytes.len() * reps);
    let mut o = Vec::with_capacity((offsets.len() - 1) * reps + 1);
    o.push(0u32);
    for _ in 0..reps {
        let base = b.len() as u32;
        b.extend_from_slice(bytes);
        for w in offsets.windows(2) {
            o.push(base + w[1]);
        }
    }
    (b, o)
}

/// Dict widths to sweep, from `ONPAIR_BENCH_BITS` (comma-separated). The codec's `Bits`
/// accepts 9..=16, so values outside that range are dropped; default 12/16.
fn bits_list() -> Vec<u8> {
    std::env::var("ONPAIR_BENCH_BITS")
        .ok()
        .map(|s| {
            s.split(',')
                .filter_map(|x| x.trim().parse().ok())
                .filter(|b| (9..=16).contains(b))
                .collect::<Vec<u8>>()
        })
        .filter(|v| !v.is_empty())
        .unwrap_or_else(|| vec![12, 16])
}

/// Focused single-config decode loop for `perf` / Top-Down (TMA) attribution.
/// `ONPAIR_BENCH_PERF="layout:column:bits[:threads]"` (e.g. "fat:book_reviews:12" or
/// "fat:book_reviews:12:4") loops that one decode on `threads` threads (default 1) for
/// `ONPAIR_BENCH_PERF_SECS` (default 10) so perf samples steady-state decode, not setup. Pin the
/// process to physical cores externally (taskset/numactl) for topology-controlled measurement.
fn perf_mode(spec: &str) {
    let mb: usize = std::env::var("ONPAIR_BENCH_MB").ok().and_then(|s| s.parse().ok()).unwrap_or(64);
    let target = mb * 1024 * 1024;
    let secs: f64 = std::env::var("ONPAIR_BENCH_PERF_SECS").ok().and_then(|s| s.parse().ok()).unwrap_or(10.0);
    let parts: Vec<&str> = spec.split(':').collect();
    assert!(parts.len() == 3 || parts.len() == 4, "ONPAIR_BENCH_PERF must be layout:column:bits[:threads]");
    let threads: usize = if parts.len() == 4 { parts[3].parse().expect("threads") } else { 1 };
    let kind = match parts[0] {
        "fat" => Kind::Fat,
        "entries" => Kind::Entries,
        "naive" => Kind::Naive,
        other => panic!("unknown layout {other}"),
    };
    let (colname, bits) = (parts[1], parts[2].parse::<u8>().expect("bits"));
    let (bytes, offsets) = match colname {
        "synthetic_url" => gen_urls(target),
        "tpch_comment" => gen_comments(target),
        "fineweb_text" => gen_text(target),
        name => {
            let dir = std::env::var("ONPAIR_BENCH_COLS_DIR")
                .expect("ONPAIR_BENCH_COLS_DIR required for a real column");
            let (b, o) = read_bin(&format!("{dir}/{name}.bin")).expect("read column .bin");
            replicate(&b, &o, target)
        }
    };
    let cfg = Config { bits: Bits::new(bits).unwrap(), ..DEFAULT_CONFIG };
    let col = compress(&bytes, &offsets, cfg).expect("compress failed");
    let p = col.as_parts();
    let out_len = decompressed_len(p);
    let cap = out_len + 16;
    {
        let mut buf: Vec<MaybeUninit<u8>> = Vec::with_capacity(cap);
        unsafe { buf.set_len(cap) };
        decode(kind, p, &mut buf); // warm + fault in the compressed input
    }
    eprintln!(
        "# perf-mode: {} {colname} b{bits} x{threads}t  dict_entries={} out={} MiB  looping {secs}s",
        parts[0], p.dict_offsets.len() - 1, out_len / 1024 / 1024
    );
    // Spawn `threads` workers, each looping the decode until `secs` elapse; perf stat attached to the
    // process captures the aggregate Top-Down of the multi-threaded decode.
    let start = Instant::now();
    let total: u64 = std::thread::scope(|s| {
        let handles: Vec<_> = (0..threads)
            .map(|_| {
                s.spawn(move || {
                    let mut buf: Vec<MaybeUninit<u8>> = Vec::with_capacity(cap);
                    unsafe { buf.set_len(cap) };
                    let mut iters: u64 = 0;
                    while start.elapsed().as_secs_f64() < secs {
                        for _ in 0..32 {
                            std::hint::black_box(decode(kind, p, &mut buf));
                            iters += 1;
                        }
                    }
                    iters
                })
            })
            .collect();
        handles.into_iter().map(|h| h.join().unwrap()).sum()
    });
    let gibs = (total as f64 * out_len as f64) / start.elapsed().as_secs_f64() / (1u64 << 30) as f64;
    eprintln!("# perf-mode done: {threads} threads, {total} decodes, {gibs:.1} GiB/s aggregate");
}

/// Dump the occurrence-weighted token-length histogram for one column, as JSON.
/// `ONPAIR_BENCH_HIST="column:bits"` — bins each decoded token by its true length
/// (dict_offsets[c+1]-dict_offsets[c]) weighted by how often its code occurs, so the
/// distribution reflects the data, not just the dictionary. Lengths clamp to 1..=16.
fn hist_mode(spec: &str) {
    let mb: usize = std::env::var("ONPAIR_BENCH_MB").ok().and_then(|s| s.parse().ok()).unwrap_or(64);
    let target = mb * 1024 * 1024;
    let parts: Vec<&str> = spec.split(':').collect();
    assert!(parts.len() == 2, "ONPAIR_BENCH_HIST must be column:bits");
    let (colname, bits) = (parts[0], parts[1].parse::<u8>().expect("bits"));
    let (bytes, offsets) = match colname {
        "synthetic_url" => gen_urls(target),
        "tpch_comment" => gen_comments(target),
        "fineweb_text" => gen_text(target),
        name => {
            let dir = std::env::var("ONPAIR_BENCH_COLS_DIR").expect("ONPAIR_BENCH_COLS_DIR required");
            let (b, o) = read_bin(&format!("{dir}/{name}.bin")).expect("read column .bin");
            replicate(&b, &o, target)
        }
    };
    let cfg = Config { bits: Bits::new(bits).unwrap(), ..DEFAULT_CONFIG };
    let col = compress(&bytes, &offsets, cfg).expect("compress failed");
    let p = col.as_parts();
    let mut hist = [0u64; 17]; // index = token length (1..=16)
    for &code in p.codes {
        let c = code as usize;
        if c + 1 < p.dict_offsets.len() {
            let len = (p.dict_offsets[c + 1] - p.dict_offsets[c]) as usize;
            if (1..=16).contains(&len) {
                hist[len] += 1;
            }
        }
    }
    let total: u64 = hist.iter().sum();
    let body: Vec<String> = (1..=16).map(|l| hist[l].to_string()).collect();
    println!("{{\"column\":\"{colname}\",\"bits\":{bits},\"total\":{total},\"hist\":[{}]}}", body.join(","));
}

fn main() {
    if let Ok(spec) = std::env::var("ONPAIR_BENCH_HIST") {
        if !spec.trim().is_empty() {
            hist_mode(&spec);
            return;
        }
    }
    if let Ok(spec) = std::env::var("ONPAIR_BENCH_PERF") {
        if !spec.trim().is_empty() {
            perf_mode(&spec);
            return;
        }
    }
    let mb: usize = std::env::var("ONPAIR_BENCH_MB")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(64);
    let target = mb * 1024 * 1024;

    // synthetic_url is a generated stand-in (matches the GPU's regenerated low-cardinality URL
    // corpus); every other column is the SAME real dataset the GPU eval used, shipped as .bin.
    // Together these are the GPU eval's full synth+real set. (gen_comments/gen_text remain above
    // for the no-dir fallback / perf+hist modes.)
    let mut corpora: Vec<(String, (Vec<u8>, Vec<u32>))> =
        vec![("synthetic_url".to_string(), gen_urls(target))];
    if let Ok(dir) = std::env::var("ONPAIR_BENCH_COLS_DIR") {
        for name in [
            "clickbench_url", "l_comment", "ps_comment", "l_shipinstruct", "fineweb",
            "wikipedia", "book_reviews", "amazon_movies", "amazon_electronics",
        ] {
            let path = format!("{dir}/{name}.bin");
            match read_bin(&path) {
                Ok((b, o)) => corpora.push((name.to_string(), replicate(&b, &o, target))),
                Err(e) => eprintln!("# real column {path} unavailable ({e}), skipping"),
            }
        }
    } else {
        // No real columns available: fall back to the synthetic stand-ins for a self-contained run.
        corpora.push(("tpch_comment".to_string(), gen_comments(target)));
        corpora.push(("fineweb_text".to_string(), gen_text(target)));
    }

    let thread_counts = thread_counts();
    let bits_list = bits_list();
    eprintln!(
        "# onpair-cpu-bench  input={mb} MiB/column  bits={bits_list:?}  threads={thread_counts:?}  columns={}",
        corpora.len()
    );
    println!("{{\"mb\": {mb}, \"results\": [");
    let mut first = true;
    let mut comp_out: Vec<(String, Vec<competitors::CompResult>)> = Vec::new();
    for (name, (bytes, offsets)) in &corpora {
        // CPU-SOTA competitors: codec-independent of OnPair's bit-width, so run once per
        // column on its raw bytes (decode throughput + ratio for FSST/Zstd/LZ4/Deflate).
        let cr = competitors::run_all(bytes, offsets);
        for r in &cr {
            eprintln!("  [{name}] {:14} {:7.1} GB/s  ratio {:.2}x", r.codec, r.decode_gbs, r.ratio);
        }
        comp_out.push((name.clone(), cr));
        for &bits in &bits_list {
            let cfg = Config {
                bits: Bits::new(bits).unwrap(),
                ..DEFAULT_CONFIG
            };
            let col = compress(bytes, offsets, cfg).expect("compress failed");
            let p = col.as_parts();
            let dict_entries = p.dict_offsets.len() - 1; // fat table spans dict_entries * 16 bytes
            // Correctness: every layout reproduces the input exactly.
            assert_eq!(&decompress(p), bytes, "fat output mismatch ({name} b{bits})");
            assert_eq!(&decode_to_vec(Kind::Entries, p), bytes, "entries mismatch ({name} b{bits})");
            assert_eq!(&decode_to_vec(Kind::Naive, p), bytes, "naive mismatch ({name} b{bits})");
            eprintln!(
                "[{name} b{bits}] {} MiB in, {} codes, {} dict tokens — byte-exact OK",
                bytes.len() / 1024 / 1024,
                p.codes.len(),
                p.dict_offsets.len() - 1
            );
            for &t in &thread_counts {
                // Each run returns the MIN-derived aggregate GiB/s plus the raw per-pass ns samples.
                let (fat, fat_ns) = run_threads(p, t, Kind::Fat);
                let (entries, entries_ns) = run_threads(p, t, Kind::Entries);
                let (naive, naive_ns) = run_threads(p, t, Kind::Naive);
                eprintln!(
                    "  threads={t}: fat={fat:6.1}  entries={entries:6.1}  naive={naive:6.1} GiB/s ({} passes/thr)  | fat/naive={:.2}x fat/entries={:.2}x",
                    fat_ns.len() / t.max(1),
                    fat / naive,
                    fat / entries
                );
                if !first {
                    println!(",");
                }
                first = false;
                // *_gibs / *_over_* are the reduced aggregates (derived from min per-pass time);
                // *_ns_iters are the raw provenance (u64 ns, one per timed pass per thread, pooled
                // across threads) — figure-gen re-derives GB/s = out_len/min(ns) (GPU-bench parity).
                print!(
                    "  {{\"column\":\"{name}\",\"bits\":{bits},\"dict_entries\":{dict_entries},\"threads\":{t},\"fat_gibs\":{fat:.2},\"entries_gibs\":{entries:.2},\"naive_gibs\":{naive:.2},\"fat_over_naive\":{:.3},\"fat_over_entries\":{:.3},\"fat_ns_iters\":{},\"entries_ns_iters\":{},\"naive_ns_iters\":{}}}",
                    fat / naive,
                    fat / entries,
                    ns_array(&fat_ns),
                    ns_array(&entries_ns),
                    ns_array(&naive_ns)
                );
            }
        }
    }
    println!("\n], \"competitors\": [");
    let mut cfirst = true;
    for (name, results) in &comp_out {
        for r in results {
            if !cfirst {
                println!(",");
            }
            cfirst = false;
            print!(
                "  {{\"column\":\"{name}\",\"codec\":\"{}\",\"decode_gbs\":{:.2},\"ratio\":{:.3}}}",
                r.codec, r.decode_gbs, r.ratio
            );
        }
    }
    println!("\n]}}");
}
