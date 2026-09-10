// Cross-platform determinism probe for FSST-12 symbol-table training.
//
// The paper carries a comment asserting FSST-12's trained dictionary is platform-dependent because
// "the C++ symbol search does not fix hash iteration order". This build has no C++ in that path:
// fsst12 is fsst-rs, whose trainer samples with a FIXED seed (fsst_hash(4637947)) and dedups
// candidates in an FxHashMap with FxBuildHasher, which carries no random seed. The one place order
// could leak in is `for (symbol, gain) in candidates { pqueue.push(..) }`: the heap orders by
// (gain, len), so candidates tied on BOTH are separated by hash iteration order, and hashbrown's
// probe sequence depends on its SIMD group width, which is arch-specific.
//
// So: build inputs that MAXIMISE exact (gain, len) ties, train, and print a digest of the resulting
// table. Run on aarch64-darwin and x86_64-linux and compare. Equal digests on a tie-saturated input
// is strong evidence the claim is false; unequal digests localise it precisely.
use fsst12::fsst12::Compressor12;

fn digest(bytes: &[u8]) -> u64 {
    // FNV-1a. Fixed arithmetic, no std hasher, so the digest itself cannot vary by platform.
    let mut h: u64 = 0xcbf29ce484222325;
    for &b in bytes {
        h ^= b as u64;
        h = h.wrapping_mul(0x100000001b3);
    }
    h
}

/// Tie-saturated: every two-byte pair over a 26-letter alphabet appears the SAME number of times,
/// so gains collide across hundreds of same-length candidates -- the worst case for a tie-break.
fn tie_saturated_n(reps: usize) -> Vec<Vec<u8>> {
    let a = b"abcdefghijklmnopqrstuvwxyz";
    let mut rows = Vec::new();
    for _ in 0..reps {
        for &x in a.iter() {
            for &y in a.iter() {
                rows.push(vec![x, y, b' ']);
            }
        }
    }
    rows
}

/// 400 reps is 811 KB, UNDER FSST12_SAMPLETARGET (1 MiB), so the sampler returns the input
/// verbatim and this isolates the tie-break. 2000 reps is 4.1 MB, so the sampler's fixed-seed
/// modulo walk runs as well and the two paths interact -- which is the case the real 1 GB columns
/// are in.
fn tie_saturated() -> Vec<Vec<u8>> { tie_saturated_n(400) }
fn tie_saturated_big() -> Vec<Vec<u8>> { tie_saturated_n(2000) }

/// Log-shaped, resembling the loghub columns where the reported discrepancy was largest.
fn log_like() -> Vec<Vec<u8>> {
    let lvl = ["INFO", "WARN", "ERROR", "DEBUG"];
    let comp = ["executor.Executor", "storage.BlockManager", "scheduler.DAGScheduler"];
    let mut rows = Vec::new();
    for i in 0..60_000u32 {
        rows.push(
            format!(
                "26/09/02 11:{:02}:{:02} {} {}: task {} stage {} bytes {}",
                i % 60, (i * 7) % 60, lvl[(i % 4) as usize],
                comp[(i % 3) as usize], i, i % 97, (i * 1237) % 100_000
            )
            .into_bytes(),
        )
    }
    rows
}

/// Repetitive with a long shared prefix, which drives 8-byte merges.
fn urlish() -> Vec<Vec<u8>> {
    (0..60_000u32)
        .map(|i| format!("https://example.com/path/{}/item?id={}", i % 512, i).into_bytes())
        .collect()
}

/// Train on a real column dump: [u64 n][(n+1) u32 offsets][payload].
///
/// The synthetic cases below train 847 to 1219 symbols. Real columns train close to the 4096 code
/// space -- ClickBench URL reaches ~3747 -- where candidate ties are far denser, so a tie-order
/// difference has far more chances to fire. This path exists because the synthetic cases agreeing
/// did NOT establish that no input diverges.
fn from_dump(path: &str) -> Vec<Vec<u8>> {
    let raw = std::fs::read(path).expect("read dump");
    let n = u64::from_le_bytes(raw[..8].try_into().unwrap()) as usize;
    let off_end = 8 + 4 * (n + 1);
    let offs: Vec<u32> = raw[8..off_end]
        .chunks_exact(4)
        .map(|c| u32::from_le_bytes(c.try_into().unwrap()))
        .collect();
    let payload = &raw[off_end..];
    (0..n)
        .map(|i| payload[offs[i] as usize..offs[i + 1] as usize].to_vec())
        .collect()
}

fn main() {
    println!("arch={} os={} ptr_width={}",
        std::env::consts::ARCH, std::env::consts::OS, usize::BITS);
    let mut cases: Vec<(String, Vec<Vec<u8>>)> = Vec::new();
    for a in std::env::args().skip(1) {
        cases.push((format!("dump:{}", a.rsplit('/').next().unwrap_or(&a)), from_dump(&a)));
    }
    for (name, rows) in cases.into_iter().chain([
        ("tie_saturated".to_string(), tie_saturated()),
        ("tie_sat_sampled".to_string(), tie_saturated_big()),
        ("log_like".to_string(), log_like()),
        ("urlish".to_string(), urlish()),
    ]) {
        let refs: Vec<&[u8]> = rows.iter().map(|r| r.as_slice()).collect();
        let c = Compressor12::train(&refs);
        let table = c.symbol_table();
        let lens = c.symbol_lengths();
        let mut flat = Vec::with_capacity(table.len() * 9);
        for s in table {
            flat.extend_from_slice(&s.to_u64().to_le_bytes());
        }
        let table_digest = digest(&flat);
        let lens_digest = digest(lens);
        // Compressed size is the number the paper actually consumes, so report it too: a table
        // that differs only in tie ORDER can still compress to the same total.
        let total: usize = rows.iter().map(|r| c.compress(r).len()).sum();
        println!(
            "{:<20} n_symbols={:<5} table_digest={:016x} lens_digest={:016x} compressed_total={}",
            name, table.len(), table_digest, lens_digest, total
        );
    }
}
