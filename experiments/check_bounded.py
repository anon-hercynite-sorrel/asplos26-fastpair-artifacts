#!/usr/bin/env python3
"""Check the recorded B300 execution of the bounded measurement workflows."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / 'results/b300-validation-20260910'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def checksums(directory):
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        path = (directory / name).resolve()
        require(path.is_relative_to(directory.resolve()), 'Invalid checksum path')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == digest,
                f'Checksum mismatch: {name}')


def run(*args):
    subprocess.run([sys.executable, *map(str, args)], cwd=ROOT, check=True)


def main():
    checksums(RECORD)
    with tempfile.TemporaryDirectory(prefix='fastpair-b300-check-') as work:
        work = Path(work)
        with tarfile.open(RECORD / 'evidence.tar.gz') as archive:
            for member in archive:
                path = (work / member.name).resolve()
                require(member.isfile() and path.is_relative_to(work), 'Invalid archive member')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.extractfile(member).read())
        checksums(work)
        provenance = json.loads((RECORD / 'publication-provenance.json').read_text())
        for record in provenance['files']:
            require(hashlib.sha256((work / record['path']).read_bytes()).hexdigest()
                    == record['published_sha256'], 'Publication provenance mismatch')
        rows = json.loads((work / 'entry-summary.json').read_text())
        require(len(rows) == 1, 'Expected one configured-grid cell')
        row = rows[0]
        require((row['dataset_id'], row['column'], row['bits'], row['rows'], row['sample_bytes'])
                == ('loghub-windows', 'line', 12, 4139945, 999999899), 'Wrong input cell')
        gpu = row['gpu']
        require(row['verified'] is True and gpu['verified'] is True
                and gpu['validated'] is True, 'Entry output verification failed')
        require(gpu['decoded_bytes'] == row['sample_bytes'] and gpu['total_tokens'] == 99090926,
                'Entry input statistics differ')
        kernels = [k for k in gpu['kernels'] if k.get('applicable')]
        require(len(kernels) == 585, 'Configured grid is incomplete')
        for kernel in kernels:
            times = kernel['decode_ns_iters']
            require(kernel['verified'] is True and len(times) == 100
                    and all(math.isfinite(t) and t > 0 for t in times),
                    f"Invalid kernel record: {kernel['kernel']}")
        winner = min(kernels, key=lambda k: min(k['decode_ns_iters']))
        print(f"Configured grid: {len(kernels)} byte-verified kernels; "
              f"{winner['kernel']}, {row['sample_bytes']/min(winner['decode_ns_iters']):.2f} GB/s",
              flush=True)
        run('experiments/pipes/check_capture.py', work / 'pipes', '--chip', 'b300',
            '--output', work / 'pipes-check.json')
        run('experiments/staging/summarize.py', work / 'staging.json')
        run('experiments/sidecar/verify.py', '--directory', work / 'sidecar')
        run('experiments/zstd/check-replay.py', work / 'zstd-summary.json')
    print('B300 workflow records: all checks passed')


if __name__ == '__main__':
    main()
