//! CPU-SOTA decode competitors, measured the same way as the OnPair fat/entries
//! decode: single-core decode throughput (GB/s of output, decimal 1e9) and compression
//! ratio, so FastPair-CPU sits in the same field as the GPU SOTA figure.
//!
//! Byte-stream codecs (Zstd, LZ4, Deflate) compress in 256 KiB blocks, matching the GPU
//! chunking; FSST is string-aware (one symbol table over the column's rows), like OnPair's
//! dictionary. The DE's three modes are mirrored: LZ4, Deflate-hi (level 9), Deflate-fast
//! (level 1); Zstd is swept at the same levels as the GPU (-10/1/3).
use std::mem::MaybeUninit;
use std::time::Instant;

const BLOCK: usize = 256 * 1024; // 256 KiB, matching the GPU chunk size
const TARGET_SECS: f64 = 0.7;

pub struct CompResult {
    pub codec: String,
    pub decode_gbs: f64, // single-core decode throughput, GB/s of output (decimal 1e9)
    pub ratio: f64,      // raw_bytes / compressed_bytes
}

/// Loop `decode` (which fills an owned output buffer) for ~TARGET_SECS; return GB/s of
/// `out_len` decoded output bytes. The caller black-boxes its buffer to defeat elision.
fn measure(out_len: usize, mut decode: impl FnMut()) -> f64 {
    let t0 = Instant::now();
    decode();
    let one = t0.elapsed().as_secs_f64().max(1e-9);
    let iters = ((TARGET_SECS / one).ceil() as usize).max(3);
    let start = Instant::now();
    for _ in 0..iters {
        decode();
    }
    let secs = start.elapsed().as_secs_f64().max(1e-9);
    (iters as f64 * out_len as f64) / secs / 1e9
}

fn block_lens(bytes: &[u8]) -> Vec<usize> {
    bytes.chunks(BLOCK).map(<[u8]>::len).collect()
}

/// Zstd at a given level, block-wise; decode into a reused buffer (no per-iteration alloc).
pub fn zstd_codec(bytes: &[u8], level: i32, label: &str) -> CompResult {
    let lens = block_lens(bytes);
    let comp: Vec<Vec<u8>> = bytes
        .chunks(BLOCK)
        .map(|b| zstd::bulk::compress(b, level).expect("zstd compress"))
        .collect();
    let csz: usize = comp.iter().map(Vec::len).sum();
    let mut out = vec![0u8; bytes.len()];
    let mut dec = zstd::bulk::Decompressor::new().expect("zstd decompressor");
    let gbs = measure(bytes.len(), || {
        let mut off = 0usize;
        for (c, &bl) in comp.iter().zip(&lens) {
            dec.decompress_to_buffer(c, &mut out[off..off + bl]).expect("zstd decode");
            off += bl;
        }
        std::hint::black_box(&out);
    });
    CompResult { codec: label.to_string(), decode_gbs: gbs, ratio: bytes.len() as f64 / csz as f64 }
}

/// LZ4 (lz4_flex block), block-wise.
pub fn lz4_codec(bytes: &[u8]) -> CompResult {
    let lens = block_lens(bytes);
    let comp: Vec<Vec<u8>> = bytes.chunks(BLOCK).map(lz4_flex::block::compress).collect();
    let csz: usize = comp.iter().map(Vec::len).sum();
    let mut out = vec![0u8; bytes.len()];
    let gbs = measure(bytes.len(), || {
        let mut off = 0usize;
        for (c, &bl) in comp.iter().zip(&lens) {
            lz4_flex::block::decompress_into(c, &mut out[off..off + bl]).expect("lz4 decode");
            off += bl;
        }
        std::hint::black_box(&out);
    });
    CompResult { codec: "LZ4".to_string(), decode_gbs: gbs, ratio: bytes.len() as f64 / csz as f64 }
}

/// Raw Deflate at a given level (9 = hi, 1 = fast), block-wise; one reused decompressor.
pub fn deflate_codec(bytes: &[u8], level: u32, label: &str) -> CompResult {
    use flate2::{Compress, Compression, Decompress, FlushCompress, FlushDecompress};
    let lens = block_lens(bytes);
    let comp: Vec<Vec<u8>> = bytes
        .chunks(BLOCK)
        .map(|b| {
            let mut c = Compress::new(Compression::new(level), false);
            let mut o = Vec::with_capacity(b.len());
            c.compress_vec(b, &mut o, FlushCompress::Finish).expect("deflate compress");
            o
        })
        .collect();
    let csz: usize = comp.iter().map(Vec::len).sum();
    let mut out = vec![0u8; bytes.len()];
    let mut d = Decompress::new(false);
    let gbs = measure(bytes.len(), || {
        let mut off = 0usize;
        for (c, &bl) in comp.iter().zip(&lens) {
            d.reset(false);
            d.decompress(c, &mut out[off..off + bl], FlushDecompress::Finish).expect("deflate decode");
            off += bl;
        }
        std::hint::black_box(&out);
    });
    CompResult { codec: label.to_string(), decode_gbs: gbs, ratio: bytes.len() as f64 / csz as f64 }
}

/// FSST: one symbol table trained over the column's rows; decode row-by-row into a buffer.
pub fn fsst_codec(bytes: &[u8], offsets: &[u32]) -> CompResult {
    let rows: Vec<&[u8]> = offsets
        .windows(2)
        .map(|w| &bytes[w[0] as usize..w[1] as usize])
        .collect();
    let compressor = fsst::Compressor::train(&rows);
    let comp: Vec<Vec<u8>> = rows.iter().map(|r| compressor.compress(r)).collect();
    let csz: usize = comp.iter().map(Vec::len).sum();
    let lens: Vec<usize> = rows.iter().map(|r| r.len()).collect();
    let decompressor = compressor.decompressor();
    // +16: FSST decompress_into may over-write up to a symbol's width past the logical end.
    let mut out: Vec<MaybeUninit<u8>> = Vec::with_capacity(bytes.len() + 16);
    unsafe { out.set_len(bytes.len() + 16) };
    let gbs = measure(bytes.len(), || {
        let mut off = 0usize;
        for (c, &rl) in comp.iter().zip(&lens) {
            decompressor.decompress_into(c, &mut out[off..off + rl + 16]);
            off += rl;
        }
        std::hint::black_box(&out);
    });
    CompResult { codec: "FSST".to_string(), decode_gbs: gbs, ratio: bytes.len() as f64 / csz as f64 }
}

/// The full competitor field for one column's raw bytes/rows.
pub fn run_all(bytes: &[u8], offsets: &[u32]) -> Vec<CompResult> {
    vec![
        fsst_codec(bytes, offsets),
        zstd_codec(bytes, -10, "Zstd (-10)"),
        zstd_codec(bytes, 1, "Zstd (1)"),
        zstd_codec(bytes, 3, "Zstd (3)"),
        lz4_codec(bytes),
        deflate_codec(bytes, 9, "Deflate (9)"),
        deflate_codec(bytes, 1, "Deflate (1)"),
    ]
}
