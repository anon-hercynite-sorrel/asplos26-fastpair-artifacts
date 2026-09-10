#!/usr/bin/env python3
"""Independently validate unlocked-boost captures; never infer boost matching from policy.

Default input: ./evidence/<chip>/boost. Missing/incomplete nodes remain explicitly pending.
Writes ./reduced.json. This does not edit paper source or choose a figure cohort.
"""
import argparse
import csv
import hashlib
import json
import math
import re
import statistics as st
import sys
from pathlib import Path

import counter_helpers as counters

ROOT = Path(__file__).resolve().parent
ARTIFACT = ROOT.parent.parent
PAYLOAD, TOKENS = 999999899, 99090926
REVISION = 'f6d81878715bf322a0917ada32bcf40adffbd3ef'
INPUT_SHA = '067f1bc2a8df043e0b475eda6b2238cf76c93f497d3ca2b001e3a301e85cd5e6'
DEFAULT = 'onpair_dw_k6_t256_b4'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text())


def rates(samples):
    return {'n': len(samples), 'min_ns': min(samples), 'median_ns': st.median(samples),
            'min_GBps': PAYLOAD / min(samples), 'median_GBps': PAYLOAD / st.median(samples)}


def describe(values):
    return {'n': len(values), 'min': min(values), 'max': max(values),
            'mean': st.mean(values), 'median': st.median(values)} if values else None


def timing(path, names, iterations=100, discard=0):
    obj = read_json(path)
    g = obj['gpu']
    require(g['decoded_bytes'] == PAYLOAD and g['total_tokens'] == TOKENS and g['chunks'] == 1,
            f'{path.name}: wrong workload dimensions')
    require(g['verified'] is True and g['validated'] is True and abs(g['frac_le8'] - .37251443) < 1e-6,
            f'{path.name}: unvalidated/wrong input')
    rows = {k['kernel']: k for k in g['kernels']}
    require(len(rows) == len(g['kernels']) and set(rows) == set(names), f'{path.name}: kernel identity mismatch')
    for name, k in rows.items():
        samples = k['decode_ns_iters']
        require(k['applicable'] is True and k['verified'] is True and len(samples) == iterations + discard
                and all(type(x) is int and x > 0 for x in samples), f'{path.name}: invalid timings for {name}')
        if discard:
            # Validate every raw sample first; only the declared tail contributes
            # to confirmation selection and reported operating-point timings.
            rows[name] = dict(k, decode_ns_iters=samples[discard:])
    return rows


def geometry(kernel, metadata):
    # Public launch_config: ceil(ceil(tokens/chunk_tokens)/warps).
    threads, chunk = metadata['block_threads'], metadata['chunk_tokens']
    matched = re.fullmatch(r'onpair_d[wsgh]_k(\d+)_t(\d+)_b(\d+)(?:_[hs]\d+)?', kernel)
    if matched:
        require(threads == int(matched[2]) and chunk == int(matched[1]) * 32,
                f'{kernel}: metadata differs from encoded launch')
    require(threads > 0 and threads % 32 == 0 and chunk > 0, f'{kernel}: invalid launch metadata')
    grid = math.ceil(math.ceil(TOKENS / chunk) / (threads // 32))
    return threads, grid


def dimension(value):
    return math.prod(int(x) for x in re.findall(r'\d+', value))


def monitor_summary(path):
    rows, rejected = [], 0
    for row in csv.DictReader(path.open()):
        try:
            def number(prefix):
                val = next(v for k, v in row.items() if k and k.strip().startswith(prefix))
                return float(re.search(r'-?\d+(?:\.\d+)?', val)[0])
            rows.append({'sm_MHz': number('clocks.current.sm'), 'memory_MHz': number('clocks.current.memory'),
                         'utilization_pct': number('utilization.gpu'), 'power_W': number('power.draw'),
                         'temperature_C': number('temperature.gpu')})
        except (StopIteration, TypeError, ValueError):
            rejected += 1
    require(rows, 'empty/non-numeric clock monitor')
    summaries = {}
    for threshold in (50, 90):
        subset = [r for r in rows if r['utilization_pct'] >= threshold]
        summaries[f'utilization_ge_{threshold}pct'] = {k: describe([r[k] for r in subset]) for k in rows[0]}
    return {'n': len(rows), 'rejected_rows': rejected, 'all': {k: describe([r[k] for r in rows]) for k in rows[0]},
            **summaries,
            'scope': 'Whole-run monitor includes sweep, confirmation, setup and profiler replay; loaded samples are contextual, not per-kernel clock measurements.'}


def reduce_chip(chip, path, selection):
    if not path.exists() or not (path / 'CAPTURE_COMPLETE').exists() or not (path / 'exit-code').exists():
        state = {'status': 'pending', 'path': str(path)}
        if (path / 'exit-code').exists() and (path / 'exit-code').read_text().strip() != '0':
            state.update(status='failed', error='Remote run exited ' + (path / 'exit-code').read_text().strip())
        return state
    require((path / 'exit-code').read_text().strip() == '0', 'remote exit code nonzero')
    require((path / 'chip.txt').read_text().strip() == chip, 'chip identity mismatch')
    require((path / 'source-revision.txt').read_text().strip() == REVISION, 'source revision mismatch')
    settling = read_json(path / 'settling.json') if (path / 'settling.json').exists() else None
    if settling is not None:
        require(chip == 'b300' and settling == {'discard_per_kernel': 2000, 'retained_per_round': 100,
                                              'profile_skip': 2003, 'profile_gpu_iters': 2100},
                'unexpected settling protocol/chip')
    require(chip != 'b300' or settling is not None, 'B300 requires its declared within-process settling protocol')
    discard = settling['discard_per_kernel'] if settling else 0
    profile_skip = settling['profile_skip'] if settling else 3
    if (path / 'source-status.txt').exists():
        require(all(line == '?? vortex-cuda/kernels/gen/' for line in (path / 'source-status.txt').read_text().splitlines()),
                'source changes beyond generated kernel directory')
    hashes = [line.split(maxsplit=1) for line in (path / 'input-binary.sha256').read_text().splitlines()]
    require(len(hashes) == 2 and all(re.fullmatch('[0-9a-f]{64}', x[0]) for x in hashes), 'invalid input/binary hash record')
    require(any(digest == INPUT_SHA and name.endswith('/windows12.vortex') for digest, name in hashes), 'input hash mismatch')
    require(any(name.endswith('/onpair-chunk-bench') for _, name in hashes), 'missing binary hash')
    script = (path / 'run.py').read_text()
    require("'-rgc'" in script and "'-lgc'" not in script and "'--lock-gpu-clocks'" not in script,
            'runner lacks reset or contains a GPU lock')
    compact = re.sub(r'\s+', '', script)
    for pair in ("'--clock-control','none'", "'--cache-control','none'", "'--replay-mode','application'",
                 f"'--launch-skip','{profile_skip}'", "'--launch-count','4'"):
        require(pair in compact, 'runner profiler policy mismatch: ' + pair)
    if settling:
        require("'--gpu-iters','2100'" in compact, 'settled NCU launch count differs')
    reset = (path / 'reset-gpu-clocks.stdout').read_text() + (path / 'reset-gpu-clocks.stderr').read_text()
    # Newer drivers may print only "All done." for a successful -rgc. The
    # archived runner's checked command and final exit=0 establish its exit code.
    require("cmd(['sudo','nvidia-smi','-rgc'],'reset-gpu-clocks')" in compact
            and 'ifcheckandq.returncode:raiseRuntimeError' in compact,
            'runner does not enforce successful GPU reset command')
    require('success' in reset.lower() or 'reset' in reset.lower() or reset.strip() == 'All done.',
            'GPU reset log lacks success evidence')
    require(not re.search(r'failed|error|not supported|insufficient', reset, re.I), 'GPU reset failure in log')
    ncu_version = (path / 'ncu-version.stdout').read_text().strip()
    require('version' in ncu_version.lower(), 'missing NCU version')
    candidates = (path / 'candidates.txt').read_text().splitlines()
    require(len(candidates) == 561 and len(set(candidates)) == 561, 'wrong candidate count/duplicates')
    require(candidates == (ROOT / (chip + '-candidates.txt')).read_text().splitlines(), 'candidate file differs from declared list')
    require(read_json(path / 'selection.json')[chip] == selection, 'archived selection provenance mismatch')
    archived = [r for r in read_json(ARTIFACT / selection['source']) if r['codec'] == 'onpair' and r['bits'] == 12]
    require(len(archived) == 1, 'ambiguous archived input')
    archived_rows = {k['kernel']: k for k in archived[0]['gpu']['kernels']
                     if k['applicable'] and k['verified'] and len(k['decode_ns_iters']) == 100}
    require(set(archived_rows) == set(candidates), 'candidate set differs from archived valid set')
    timing(path / 'warmup.json', [selection['archived_winner']], 2000)
    sweep = timing(path / 'sweep.json', candidates)
    rank = sorted(sweep, key=lambda name: (min(sweep[name]['decode_ns_iters']), st.median(sweep[name]['decode_ns_iters']), name))
    shortlist = list(dict.fromkeys(rank[:3] + [selection['archived_winner'], DEFAULT]))
    pooled = {name: [] for name in shortlist}
    rounds = []
    for i in range(2):
        rows = timing(path / f'confirmation-{i}.json', shortlist, discard=discard)
        rounds.append({n: rates(k['decode_ns_iters']) for n, k in rows.items()})
        for name in shortlist:
            pooled[name] += rows[name]['decode_ns_iters']
    winner = min(shortlist, key=lambda name: (min(pooled[name]), st.median(pooled[name]), name))
    selected = read_json(path / 'selected.json')
    if settling:
        require(selected['discarded_per_kernel_per_confirmation_or_anchor'] == 2000
                and selected['retained_per_round'] == 100, 'selected settling declaration mismatch')
    require(selected['winner'] == winner and selected['recommended'] == DEFAULT
            and selected['archived_winner'] == selection['archived_winner']
            and selected['confirmation_candidates'] == shortlist and selected['full_sweep_count'] == 561,
            'recorded selection does not match independent calculation')
    for name, ts in pooled.items():
        summary = rates(ts)
        for key in ('n', 'min_GBps', 'median_GBps'):
            require(math.isclose(summary[key], selected['confirmed'][name][key], rel_tol=1e-10), 'confirmation summary mismatch')
    required = (path / 'capture-metrics.txt').read_text().strip().split(',')
    require(len(required) == len(set(required)) and len(required) >= 35, 'invalid metric inventory')
    missing = read_json(path / 'missing-metrics.json')
    require(not set(required).intersection(missing), 'missing metrics also listed as required')
    monitor = monitor_summary(path / 'clocks.csv')
    cells, warnings = [], []
    for name in dict.fromkeys([winner, DEFAULT]):
        before = timing(path / (name + '-before.json'), [name], discard=discard)[name]
        after = timing(path / (name + '-after.json'), [name], discard=discard)[name]
        require(geometry(name, before) == geometry(name, after), 'pre/post launch geometry changes')
        threads, grid = geometry(name, before)
        launches, errors = counters.parse_csv(path / (name + '.raw.csv'))
        require(not errors and len(launches) == 4, f'{name}: expected four clean launches; {errors}')
        derived = []
        for launch in launches:
            ident, metrics = launch['identity'], launch['metrics']
            require(ident['Kernel Name'] == name and dimension(ident['Block Size']) == threads
                    and dimension(ident['Grid Size']) == grid, f'{name}: profiler kernel/grid/block mismatch')
            require(set(required) <= set(metrics), f'{name}: missing/non-numeric metrics: {set(required)-set(metrics)}')
            derived.append(counters.derive(launch, PAYLOAD))
        for suffix in ('.ncu.log', '.profile.stdout', '.profile.stderr'):
            require('==ERROR==' not in (path / (name + suffix)).read_text(), f'{name}: NCU error log')
        common = set.intersection(*(set(v) for v in derived))
        # Do not publish the old helper's heuristic nonshared load/store split.
        common = {k for k in common if not k.startswith('estimated_nonshared_')}
        means = {k: st.mean(x[k] for x in derived) for k in sorted(common)}
        ranges = {k: [min(x[k] for x in derived), max(x[k] for x in derived)] for k in sorted(common)}
        if settling:
            low, high = ranges['sm_hz']
            if low < 2032e6 * .97:
                warnings.append(f'{name}: at least one B300 profile launch below 97% of archived 2032 MHz boost reference ({low / 1e6:.2f} MHz)')
            if high / low - 1 > .02:
                warnings.append(f'{name}: settled B300 profile SM spread exceeds 2% ({low / 1e6:.2f}–{high / 1e6:.2f} MHz)')
        raw_means = {k: st.mean(x['metrics'][k]['value'] for x in launches) for k in required}
        raw_ranges = {k: [min(x['metrics'][k]['value'] for x in launches), max(x['metrics'][k]['value'] for x in launches)] for k in required}
        pre, post = rates(before['decode_ns_iters']), rates(after['decode_ns_iters'])
        drift = post['median_GBps'] / pre['median_GBps'] - 1
        agreement_limit = .03 if settling else .05
        if abs(drift) > agreement_limit:
            warnings.append(f'{name}: pre/post median throughput drift {drift:+.1%}')
        prof_rate = PAYLOAD / means['duration_s'] / 1e9
        anchor = st.mean([pre['median_GBps'], post['median_GBps']])
        prof_diff = prof_rate / anchor - 1
        if abs(prof_diff) > agreement_limit:
            warnings.append(f'{name}: instrumented duration-derived throughput differs {prof_diff:+.1%} from uninstrumented anchors; investigate replay effects')
        comparisons = {}
        loaded = monitor['utilization_ge_50pct']
        for metric, mk in (('sm_hz', 'sm_MHz'), ('memory_hz', 'memory_MHz')):
            if loaded[mk] and loaded[mk]['median'] > 0:
                diff = means[metric] / (loaded[mk]['median'] * 1e6) - 1
                comparisons[metric + '_relative_loaded_monitor_median'] = diff
                if abs(diff) > (.03 if metric == 'sm_hz' else .01):
                    warnings.append(f'{name}: profile {metric} differs {diff:+.1%} from whole-run loaded monitor median; monitor mixes kernels and phases')
        if chip == 'h100' and means['sm_hz'] < 1980e6 * .97:
            warnings.append(f'{name}: profile SM clock below archived 1980 MHz H100 boost reference')
        archived_rate = rates(archived_rows[name]['decode_ns_iters'])
        cells.append({'roles': [r for r, k in [('winner', winner), ('recommended', DEFAULT)] if k == name], 'kernel': name,
                      'block_threads': threads, 'grid_blocks': grid, 'before': pre, 'after': post,
                      'confirmation': rates(pooled[name]), 'archived_same_kernel': archived_rate,
                      'confirmation_vs_archived_same_kernel': rates(pooled[name])['min_GBps'] / archived_rate['min_GBps'] - 1,
                      'anchor_median_drift_fraction': drift, 'profile_duration_derived_GBps': prof_rate,
                      'profile_duration_vs_anchor_median_fraction': prof_diff, 'profile_clock_comparisons': comparisons,
                      'metrics_mean': means, 'metrics_range': ranges, 'raw_metrics_mean': raw_means, 'raw_metrics_range': raw_ranges,
                      'attribution': 'Shared load/store/atom remain direct fractions of total; shared aggregate-minus-operations remains residual. Misc is physical only where directly exposed; nonshared LSU remains aggregated.'})
    winner_rate = rates(pooled[winner])['min_GBps']
    vs_archive = winner_rate / selection['archived_winner_GBps'] - 1
    if vs_archive < -.03:
        warnings.append(f'Fresh winner {vs_archive:+.1%} versus archived boost winner; performance operating point not reproduced within 3%')
    return {'status': 'validated_with_review_flags' if warnings else 'validated', 'winner': winner,
            'winner_vs_archived_best_fraction': vs_archive, 'archived_winner': selection,
            'confirmation_rounds': rounds, 'confirmation_candidates': shortlist,
            'sweep_top10': [{'kernel': n, **rates(sweep[n]['decode_ns_iters'])} for n in rank[:10]],
            'cells': cells, 'monitor': monitor, 'warnings': warnings, 'missing_metrics': missing,
            'ncu_version': ncu_version, 'source_revision': REVISION, 'input_and_binary_recorded_hashes': hashes,
            'runner_sha256': hashlib.sha256((path / 'run.py').read_bytes()).hexdigest(),
            'settling_protocol': settling,
            'clock_policy': 'Unlocked boost: successful GPU reset; application reset best-effort; NCU clock-control none.',
            'boost_match': 'Requires reviewing actual timing and profile clocks; policy and successful validation alone do not establish chips-at-best or causal bottlenecks.',
            'hash_scope': 'Remote runner verified source/data and recorded binary digest; local reduction verifies records, not unavailable remote binary bytes.'}
