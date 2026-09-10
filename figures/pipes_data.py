"""Validate and reduce the accepted Windows boost capture cohort, using no GPU."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys
import tarfile
import tempfile

ARTIFACT = Path(__file__).resolve().parent.parent
CAMPAIGN = ARTIFACT / 'results/pipes-boost-20260909'
sys.path.insert(0, str(ARTIFACT / 'experiments/pipes'))
import reduce_capture as base
import reduce_stabilized as stabilized
import directions as direction

WINNERS = {'a100':'onpair_dw_k4_t128_b2', 'h100':'onpair_dw_k7_t256_b4',
           'b300':'onpair_ds_k6_t128_b8_s14', 'l40s':'onpair_dg_k8_t128_b2',
           'rtxpro':'onpair_ds_k8_t128_b4_s12'}


def equal_numbers(actual, expected, label):
    """Compare the data retained in the submitted figure, not file paths or formatting."""
    if isinstance(expected, dict):
        base.require(set(actual) == set(expected), f'{label}: field mismatch')
        for key in expected:
            equal_numbers(actual[key], expected[key], label + '/' + key)
    elif isinstance(expected, list):
        base.require(len(actual) == len(expected), f'{label}: length mismatch')
        for i, (a, e) in enumerate(zip(actual, expected)):
            equal_numbers(a, e, f'{label}/{i}')
    elif isinstance(expected, (int, float)):
        base.require(math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-9),
                     f'{label}: {actual} differs from {expected}')
    else:
        base.require(actual == expected, f'{label}: value mismatch')


def load(campaign=CAMPAIGN, check_reference=True):
    campaign = Path(campaign)
    checksums = (campaign / 'SHA256SUMS').read_text().splitlines()
    for line in checksums:
        digest, name = line.split(maxsplit=1)
        base.require(hashlib.sha256((campaign/name).read_bytes()).hexdigest() == digest,
                     f'archive checksum mismatch: {name}')
    reference = json.loads((campaign/'accepted.json').read_text())
    reference_directions = json.loads((campaign/'directions.json').read_text())
    with tempfile.TemporaryDirectory(prefix='fastpair-pipes-') as temp:
        root = Path(temp)
        with tarfile.open(campaign/'evidence.tar.gz', 'r:gz') as archive:
            for member in archive.getmembers():
                base.require(member.isfile() and not Path(member.name).is_absolute()
                             and '..' not in Path(member.name).parts, 'unsafe evidence archive member')
            for member in archive.getmembers():
                target = root/member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
        base.ROOT = root
        base.ARTIFACT = ARTIFACT
        selection = base.read_json(root/'selection.json')
        base.require(set(selection) == set(WINNERS), 'device cohort mismatch')
        accepted = {}
        # Preserve the initial A100 reduction for diagnostics; its settled follow-up is primary.
        for chip in WINNERS:
            value = base.reduce_chip(chip, root/'evidence'/chip/'boost', selection[chip])
            if chip == 'a100':
                stabilized.ROOT = root
                stabilized.p = root/'evidence/a100/stabilized'
                stabilized.original = root/'evidence/a100/boost'
                value = stabilized.main()
            base.require(value['status'] == 'validated', f'{chip}: {value.get("warnings", value)}')
            base.require(value['winner'] == WINNERS[chip], f'{chip}: accepted winner changed')
            if check_reference:
                for cell in value['cells']:
                    ref = next(c for c in reference[chip]['cells'] if c['kernel'] == cell['kernel'])
                    for key in ('roles','metrics_mean','metrics_range','before','after','confirmation'):
                        equal_numbers(cell[key], ref[key], f'{chip}/{cell["kernel"]}/{key}')
            accepted[chip] = value
        result = {'cells': [], 'method': reference_directions['method'],
                  'accepted_sha256': hashlib.sha256((campaign/'accepted.json').read_bytes()).hexdigest()}
        for chip in direction.ORDER:
            for cell in accepted[chip]['cells']:
                rel = Path('evidence')/chip/('stabilized' if chip=='a100' else 'boost')/(cell['kernel']+'.raw.csv')
                launches = direction.read_launches(root/rel, cell['kernel'])
                direct = all(x['direct_read_fraction'] is not None for x in launches)
                base.require(direct == (chip in ('h100','b300','rtxpro')), f'{chip}: direction inventory changed')
                row = {'chip':chip, 'kernel':cell['kernel'], 'roles':cell['roles'],
                       'direction_method':'direct_lgds_ratio' if direct else 'estimated_tag_ratio',
                       'raw_path':str(rel), 'raw_sha256':hashlib.sha256((root/rel).read_bytes()).hexdigest(),
                       'launches':launches}
                for field in ('shares_pct','peak_points'):
                    row[field] = {k:statistics.mean(x[field][k] for x in launches) for k in launches[0][field]}
                for field in ('estimated_global_read_share_pct','estimated_global_write_share_pct',
                              'estimate_minus_direct_read_share_pp','estimate_minus_direct_read_peak_pp',
                              'direct_nonshared_closure_share_pp'):
                    values = [x[field] for x in launches if x[field] is not None]
                    row[field] = {'mean':statistics.mean(values), 'min':min(values),'max':max(values)} if values else None
                base.require(math.isclose(sum(row['peak_points'].values()), cell['metrics_mean']['l1_elapsed_pct'], abs_tol=1e-9),
                             f'{chip}: stack does not conserve elapsed-normalized L1 total')
                if check_reference:
                    ref = next(c for c in reference_directions['cells'] if c['chip']==chip and c['kernel']==cell['kernel'])
                    equal_numbers(row, ref, f'{chip}/{cell["kernel"]}/directions')
                result['cells'].append(row)
        return accepted, result
