#!/usr/bin/env python3
"""Check archived Zstd settings and the bounded correctness rerun (no GPU)."""
import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(root=ROOT):
    base = root / 'results/zstd-validation-20260909'
    for line in (base / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        require(hashlib.sha256((base / name).read_bytes()).hexdigest() == digest,
                f'checksum mismatch: {name}')
    plan = json.loads((root / 'experiments/zstd/historical-settings.json').read_text())
    reconstructed = []
    for filename in ['zstd_frames.json', 'zstd_frames_shipinstruct.json']:
        for row in json.loads((root / 'results/suite-flat-20260830/b300' / filename).read_text()):
            for cell in row['gpu']['nvcomp_zstd']:
                reconstructed.append(dict(source=filename, dataset_id=row['dataset_id'],
                    column=row['column'], rows=row['rows'], sample_bytes=row['sample_bytes'],
                    training_seed=row['training_seed'], **{k: cell[k] for k in [
                    'zstd_level', 'values_per_frame', 'frames', 'raw_bytes',
                    'compressed_bytes', 'backend', 'iterations', 'supported']}))
    require(plan == reconstructed and len(plan) == 329, 'historical settings differ')
    for framing in ['prefix', 'flat']:
        doc = json.loads((base / f'windows19-{framing}-timings.json').read_text())
        manifest = json.loads((base / f'windows19-{framing}.manifest.json').read_text())
        require(doc['actual_decoded_bytes'] == doc['payload_bytes'] +
                (4 * doc['rows'] if framing == 'prefix' else 0), 'framing byte count')
        for key in ['payload_bytes', 'actual_decoded_bytes', 'compressed_bytes',
                    'rows', 'frames', 'values_per_frame', 'level']:
            require(doc[key] == manifest[key], f'manifest mismatch: {key}')
        blocks = doc['results']
        require([b['mode'] for b in blocks] == ['reuse', 'reprepare', 'reprepare', 'reuse'], 'ABBA order')
        for b in blocks:
            times = b['decode_ns_iters']
            require(b['validated'] is True and len(times) == b['iterations'] == 100, 'validation/sample count')
            require(all(math.isfinite(t) and t > 0 for t in times), 'invalid timing')
            for key in ['status_checks', 'size_checks']:
                require(b[key] == doc['frames'] * (b['iterations'] + 2), f'incomplete {key}')
            require(b['full_byte_guard_checked_iterations'] == [-2, 0, 99], 'missing byte/guard checks')
            for key, expected in [('min_ns', min(times)), ('median_ns', statistics.median(times)),
                                  ('max_ns', max(times)), ('payload_min_gb_s', doc['payload_bytes'] / min(times))]:
                require(math.isclose(b[key], expected, rel_tol=1e-9), f'summary mismatch: {key}')
        if framing == 'prefix':
            matches = [c for c in plan if c['dataset_id'] == 'loghub-windows' and c['zstd_level'] == 19
                       and c['values_per_frame'] == 271]
            require(len(matches) == 1, 'historical Windows cell missing/ambiguous')
            for key in ['compressed_bytes', 'frames', 'values_per_frame']:
                require(matches[0][key] == doc[key], f'historical fingerprint: {key}')
    print('Zstd: 329 historical settings match; 800 bounded timings and verification records pass.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    check(parser.parse_args().root)
