#!/usr/bin/env python3
"""Validate a fresh public-harness Zstd cell against its archived configuration."""
import argparse
import json
import math
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('summary', type=Path)
p.add_argument('--dataset', default='loghub-windows')
p.add_argument('--column', default='line')
p.add_argument('--level', type=int, default=19)
p.add_argument('--values-per-frame', type=int, default=271)
a = p.parse_args()

def require(ok, message):
    if not ok:
        raise ValueError(message)

plan = json.loads(Path(__file__).with_name('historical-settings.json').read_text())
settings = [r for r in plan if (r['dataset_id'], r['column'], r['zstd_level'], r['values_per_frame'])
            == (a.dataset, a.column, a.level, a.values_per_frame)]
require(len(settings) == 1, 'requested historical cell missing or ambiguous')
expected = settings[0]
rows = [r for r in json.loads(a.summary.read_text()) if r.get('dataset_id') == a.dataset
        and r.get('column') == a.column and r.get('bits') == 12]
require(len(rows) == 1, 'requested summary row missing or ambiguous')
r = rows[0]
for key in ['rows', 'sample_bytes', 'training_seed']:
    require(r[key] == expected[key], f'input mismatch: {key}')
cells = [c for c in r['gpu'].get('nvcomp_zstd', []) if c['zstd_level'] == a.level
         and c['values_per_frame'] == a.values_per_frame]
require(len(cells) == 1, 'requested Zstd cell missing or ambiguous')
c = cells[0]
require(c.get('supported') is True and c.get('verified') is True,
        'requested Zstd decode failed, unsupported, or lacks output verification')
for key in ['raw_bytes', 'compressed_bytes', 'frames', 'backend']:
    require(c[key] == expected[key], f'historical fingerprint differs: {key}')
require(c.get('framing') == 'u32-length-prefixed', 'unexpected framing')
require(c.get('actual_decoded_bytes') == r['sample_bytes'] + 4*r['rows'], 'decoded byte count differs')
times = c['decode_ms_iters']
require(len(times) == c['iterations'] and len(times) >= 1, 'missing timings')
require(all(math.isfinite(t) and t > 0 for t in times), 'invalid timing')
require(c.get('full_byte_checks') == (2 if len(times) == 1 else 3), 'incomplete byte checks')
require(math.isclose(c['decode_ms'], min(times), rel_tol=1e-9), 'incorrect minimum reduction')
print(f'Validated {a.dataset}/{a.column}: historical framing/configuration fingerprint matches; '
      f'{len(times)} new timings, minimum {min(times):.6f} ms. Clock conditions must be compared separately.')
