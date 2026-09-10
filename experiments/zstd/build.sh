#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
SDK=${SDK:?Set SDK to the nvCOMP SDK directory containing include/ and lib/}
OUT=${OUT:?Choose a diagnostic output directory}
mkdir -p "$OUT"
nvcc --version > "$OUT/nvcc-version.txt"
nvcc -std=c++17 -O3 -lineinfo -arch="${CUDA_ARCH:-native}" "$HERE/zstd_verify.cu" -I"$SDK/include" -L"$SDK/lib" -Xlinker -rpath -Xlinker "$SDK/lib" -lnvcomp -lcudart -o "$OUT/zstd_verify" > "$OUT/build.log" 2>&1
sha256sum "$HERE/zstd_verify.cu" "$OUT/zstd_verify" > "$OUT/build-hashes.txt"
