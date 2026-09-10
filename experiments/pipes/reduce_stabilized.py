#!/usr/bin/env python3
"""Validate A100 within-process settled-boost follow-up independently."""
import hashlib
import json
import math
from pathlib import Path
import statistics as st
import reduce_capture as base

ROOT=Path(__file__).resolve().parent
p=ROOT/'evidence/a100/stabilized'
original=ROOT/'evidence/a100/boost'
out=ROOT/'stabilized-reduced.json'


def tail(path,names):
    rows=base.timing(path,names,2100)
    return rows,{n:k['decode_ns_iters'][2000:] for n,k in rows.items()}


def main():
    if not (p/'CAPTURE_COMPLETE').exists() or not (p/'exit-code').exists():
        return {'status':'pending','path':str(p)}
    base.require((p/'exit-code').read_text().strip()=='0','remote exit nonzero')
    base.require((p/'source-revision.txt').read_text().strip()==base.REVISION,'wrong source revision')
    base.require(base.INPUT_SHA in (p/'input-binary.sha256').read_text(),'wrong recorded input hash')
    base.require((p/'input-binary.sha256').read_bytes()==(original/'input-binary.sha256').read_bytes(),'binary/input differs from original boost run')
    script=(p/'run.py').read_text()
    compact=''.join(script.split())
    for text in ("'--clock-control','none'","'--cache-control','none'","'--launch-skip','2003'","'--launch-count','4'","'--gpu-iters','2100'","['sudo','nvidia-smi','-rgc']"):
        base.require(text in compact,'runner protocol mismatch '+text)
    base.require("'-lgc'" not in script,'clock lock present')
    reset=(p/'reset-gpu-clocks.stdout').read_text()+(p/'reset-gpu-clocks.stderr').read_text()
    base.require('All done.' in reset or 'success' in reset.lower() or 'reset' in reset.lower(),'reset success evidence absent')
    base.require(not any(s in reset.lower() for s in ('failed','error','not supported','insufficient')),'reset failure')
    selection=json.loads((ROOT/'selection.json').read_text())['a100']
    candidates=(ROOT/'a100-candidates.txt').read_text().splitlines()
    screen=base.timing(original/'sweep.json',candidates)
    rank=sorted(screen,key=lambda n:(min(screen[n]['decode_ns_iters']),st.median(screen[n]['decode_ns_iters']),n))
    shortlist=list(dict.fromkeys(rank[:3]+[selection['archived_winner'],base.DEFAULT]))
    provenance=json.loads((p/'screening-provenance.json').read_text())
    base.require(provenance['shortlist']==shortlist and provenance['sha256']==hashlib.sha256((original/'sweep.json').read_bytes()).hexdigest(),'screening provenance mismatch')
    pool={n:[] for n in shortlist};rounds=[]
    for i in range(2):
        _,ts=tail(p/f'confirmation-{i}.json',shortlist)
        rounds.append({n:base.rates(v) for n,v in ts.items()})
        for n in shortlist:pool[n]+=ts[n]
    winner=min(shortlist,key=lambda n:(min(pool[n]),st.median(pool[n]),n))
    selected=json.loads((p/'selected.json').read_text())
    base.require(selected['winner']==winner and selected['recommended']==base.DEFAULT and selected['confirmation_candidates']==shortlist,'incorrect selection')
    for n in shortlist:
        for key in ('n','min_GBps','median_GBps'):
            base.require(math.isclose(selected['confirmed'][n][key],base.rates(pool[n])[key],rel_tol=1e-10),'selected summary mismatch')
    required=(p/'capture-metrics.txt').read_text().strip().split(',')
    base.require((p/'capture-metrics.txt').read_bytes()==(original/'capture-metrics.txt').read_bytes(),'metric inventory changed')
    cells=[];flags=[]
    for n in dict.fromkeys((winner,base.DEFAULT)):
        before,bt=tail(p/(n+'-before.json'),[n]);after,at=tail(p/(n+'-after.json'),[n])
        threads,grid=base.geometry(n,before[n]);base.require((threads,grid)==base.geometry(n,after[n]),'geometry drift')
        launches,errors=base.counters.parse_csv(p/(n+'.raw.csv'))
        base.require(not errors and len(launches)==4,f'{n}: expected4clean launches {errors}')
        values=[]
        for launch in launches:
            ident=launch['identity'];m=launch['metrics']
            base.require(ident['Kernel Name']==n and base.dimension(ident['Block Size'])==threads and base.dimension(ident['Grid Size'])==grid,'NCU geometry mismatch')
            base.require(set(required)<=set(m),'missing/non-numeric NCU counters')
            values.append(base.counters.derive(launch,base.PAYLOAD))
        keys=set.intersection(*(set(v) for v in values))
        keys={k for k in keys if not k.startswith('estimated_nonshared_')}
        means={k:st.mean(v[k] for v in values) for k in sorted(keys)}
        ranges={k:[min(v[k] for v in values),max(v[k] for v in values)] for k in sorted(keys)}
        low,high=ranges['sm_hz']
        if low<1410e6*.97 or high/low-1>.02:flags.append(f'{n}: unsettled profile SM clocks {low/1e6:.2f}–{high/1e6:.2f}MHz')
        pre,post=base.rates(bt[n]),base.rates(at[n]);anchor=st.mean([pre['median_GBps'],post['median_GBps']])
        profile_rate=base.PAYLOAD/means['duration_s']/1e9
        if abs(profile_rate/anchor-1)>.03:flags.append(f'{n}: profile duration versus settled anchors differs {profile_rate/anchor-1:+.1%}')
        if abs(post['median_GBps']/pre['median_GBps']-1)>.03:flags.append(f'{n}: pre/post anchor drift exceeds3%')
        if abs(pre['median_GBps']/base.rates(pool[n])['median_GBps']-1)>.03:flags.append(f'{n}: preprofile anchor differs from confirmation by>3%')
        for suffix in ('.ncu.log','.profile.stdout','.profile.stderr'):
            base.require('==ERROR==' not in (p/(n+suffix)).read_text(),'NCU error log')
        cells.append({'roles':[role for role,k in [('winner',winner),('recommended',base.DEFAULT)] if n==k],
                      'kernel':n,'confirmation':base.rates(pool[n]),'before':pre,'after':post,
                      'before_discarded_first2000':base.rates(before[n]['decode_ns_iters'][:2000]),
                      'after_discarded_first2000':base.rates(after[n]['decode_ns_iters'][:2000]),
                      'profile_duration_derived_GBps':profile_rate,'profile_vs_anchor_fraction':profile_rate/anchor-1,
                      'metrics_mean':means,'metrics_range':ranges,'per_launch':[{'id':v['identity']['ID'],**d} for v,d in zip(launches,values)],
                      'raw_metrics_mean':{k:st.mean(v['metrics'][k]['value'] for v in launches) for k in required},
                      'raw_metrics_range':{k:[min(v['metrics'][k]['value'] for v in launches),max(v['metrics'][k]['value'] for v in launches)] for k in required}})
    gap=base.rates(pool[winner])['min_GBps']/selection['archived_winner_GBps']-1
    if gap<-.03:flags.append('Settled winner remains>3%below archived best')
    return {'status':'validated_with_review_flags' if flags else 'validated','winner':winner,'confirmation_candidates':shortlist,
            'confirmation_rounds':rounds,'winner_vs_archived_best_fraction':gap,'cells':cells,'warnings':flags,
            'monitor':base.monitor_summary(p/'clocks.csv'),'ncu_version':(p/'ncu-version.stdout').read_text().strip(),
            'missing_metrics':json.loads((p/'missing-metrics.json').read_text()),
            'protocol':'Prior561-point screen; two confirmation rounds per shortlisted candidate. Public binary2100iterations perkernel, discard first2000withinprocess; summarize final100. NCU applicationreplay skip2003 (validation+2internalwarmups+2000extra), capture4 with no clock/cache control; unlocked GPU.',
            'clock_acceptance':'Each NCU launch >=97%of1410MHz, withinprofile spread<=2%; profile duration versus tail100 anchors<=3%; anchor drift<=3%. These checks establish matched fast operating point, not causality on their own.'}
