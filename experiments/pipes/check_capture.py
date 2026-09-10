#!/usr/bin/env python3
"""Validate one new local capture without requiring the historical winning kernel."""
import argparse
import json
import math
import re
from pathlib import Path
import statistics as st
import reduce_capture as base
import directions


def check(path, chip):
    require=base.require
    require((path/'exit-code').read_text().strip()=='0' and (path/'CAPTURE_COMPLETE').is_file(), 'incomplete capture')
    hashes=[line.split(maxsplit=1) for line in (path/'input-binary.sha256').read_text().splitlines()]
    require(len(hashes)==2 and all(len(v)==2 and re.fullmatch('[0-9a-f]{64}',v[0]) for v in hashes), 'invalid input/binary digest records')
    identity_path=path/'input-identity.json'
    if identity_path.exists():
        identity=base.read_json(identity_path)
        require(identity['container_sha256']==hashes[0][0], 'input digest metadata differs')
        require(identity['archived_input_container_match']==(hashes[0][0]==base.INPUT_SHA), 'incorrect archived-container match flag')
        if identity.get('expected_input_sha256'):
            require(hashes[0][0]==identity['expected_input_sha256'].lower(),'explicit input digest pin violated')
        revision=(path/'source-revision.txt').read_text().strip()
        require(identity['source_revision']==revision,'source revision metadata differs')
        if identity.get('expected_revision'):
            require(revision==identity['expected_revision'],'explicit revision pin violated')
    else:
        # Compatibility with the original archived collection format.
        require(hashes[0][0]==base.INPUT_SHA,'legacy capture lacks rebuilt-input identity metadata')
        identity={'container_sha256':hashes[0][0],'archived_input_container_match':True}

    protocol=base.read_json(path/'protocol.json')
    discard=2000 if chip in ('a100','b300') else 0
    require(protocol=={'discard_per_kernel':discard,'retained_per_round':100,'profile_skip':3+discard,'profile_gpu_iters':2100 if discard else 8},'unexpected protocol')
    candidates=(path/'candidates.txt').read_text().splitlines()
    require(len(candidates)==len(set(candidates))==561,'wrong candidate set')
    selection=base.read_json(path/'selection.json')[chip]
    sweep=base.timing(path/'sweep.json',candidates)
    rank=sorted(sweep,key=lambda n:(min(sweep[n]['decode_ns_iters']),st.median(sweep[n]['decode_ns_iters']),n))
    shortlist=list(dict.fromkeys(rank[:3]+[selection['archived_winner'],base.DEFAULT]))
    pooled={n:[] for n in shortlist}
    for i in range(2):
        for n,k in base.timing(path/f'confirmation-{i}.json',shortlist,discard=discard).items():pooled[n]+=k['decode_ns_iters']
    winner=min(shortlist,key=lambda n:(min(pooled[n]),st.median(pooled[n]),n))
    selected=base.read_json(path/'selected.json')
    require(selected['winner']==winner and selected['confirmation_candidates']==shortlist and selected['recommended']==base.DEFAULT,'incorrect winner selection')
    metrics=(path/'capture-metrics.txt').read_text().strip().split(',')
    missing=base.read_json(path/'missing-metrics.json')
    require(not set(metrics)&set(missing),'ambiguous metric inventory')
    reset=(path/'reset-gpu-clocks.stdout').read_text()+(path/'reset-gpu-clocks.stderr').read_text()
    require(('All done.' in reset or 'success' in reset.lower() or 'reset' in reset.lower())
            and not any(x in reset.lower() for x in ('failed','error','not supported','insufficient')), 'clock reset lacks success evidence')
    monitor=base.monitor_summary(path/'clocks.csv')
    rows=[];flags=[]
    for name in dict.fromkeys([winner,base.DEFAULT]):
        before=base.timing(path/(name+'-before.json'),[name],discard=discard)[name]
        after=base.timing(path/(name+'-after.json'),[name],discard=discard)[name]
        geometry=base.geometry(name,before)
        require(geometry==base.geometry(name,after),'geometry drift')
        launches,errors=base.counters.parse_csv(path/(name+'.raw.csv'))
        require(not errors and len(launches)==4,'invalid NCU capture')
        for launch in launches:
            ident=launch['identity']
            require(ident['Kernel Name']==name and base.dimension(ident['Block Size'])==geometry[0] and base.dimension(ident['Grid Size'])==geometry[1],'NCU launch identity mismatch')
            require(set(metrics)<=set(launch['metrics']),'missing/non-numeric metrics')
        values=[base.counters.derive(l,base.PAYLOAD) for l in launches]
        direction_rows=directions.read_launches(path/(name+'.raw.csv'),name)
        direct=all(l['direct_read_fraction'] is not None for l in direction_rows)
        pre,post=base.rates(before['decode_ns_iters']),base.rates(after['decode_ns_iters'])
        profile=base.PAYLOAD/st.mean(v['duration_s'] for v in values)/1e9
        limit=.03 if discard else .05
        if abs(post['median_GBps']/pre['median_GBps']-1)>limit:flags.append(name+': anchor drift')
        if abs(profile/st.mean([pre['median_GBps'],post['median_GBps']])-1)>limit:flags.append(name+': profile/anchor mismatch')
        sm=[v['sm_hz'] for v in values]
        if discard and (min(sm)<{'a100':1410e6,'b300':2032e6}[chip]*.97 or max(sm)/min(sm)-1>.02):flags.append(name+': SM clock not settled at reference boost')
        for metric,key,limit_clock in [('sm_hz','sm_MHz',.03),('memory_hz','memory_MHz',.01)]:
            loaded=monitor['utilization_ge_50pct'][key]
            # A100's original accepted follow-up gates settled per-launch clocks;
            # its whole-run monitor is contextual, not its acceptance reference.
            if chip!='a100' and loaded and loaded['median']>0 and abs(st.mean(v[metric] for v in values)/(loaded['median']*1e6)-1)>limit_clock:
                flags.append(name+': '+metric+' differs from loaded monitor')
        if chip=='h100' and st.mean(sm)<1980e6*.97:flags.append(name+': below reference H100 boost')
        for suffix in ('.ncu.log','.profile.stdout','.profile.stderr'):
            require('==ERROR==' not in (path/(name+suffix)).read_text(),'NCU error')
        rows.append({'kernel':name,'roles':[role for role,n in [('winner',winner),('recommended',base.DEFAULT)] if n==name],
                     'before':pre,'after':post,'profile_GBps':profile,'sm_hz':sm,
                     'direction_method':'direct_lgds_ratio' if direct else 'estimated_tag_ratio',
                     'peak_points':{k:st.mean(l['peak_points'][k] for l in direction_rows) for k in direction_rows[0]['peak_points']},
                     'metrics_mean':{k:st.mean(v[k] for v in values) for k in set.intersection(*(set(v) for v in values))}})
    if base.rates(pooled[winner])['min_GBps']/selection['archived_winner_GBps']-1<-.03:flags.append('winner below archived boost by more than 3%')
    return {'chip':chip,'winner':winner,'status':'needs_review' if flags else 'validated',
            'review_flags':flags,'source_revision':(path/'source-revision.txt').read_text().strip(),
            'cells':rows,'input_identity':identity,
            'scope':'Checks capture records and matching workload statistics with per-input byte validation; a rebuilt-container digest does not prove identity with the archived encoded stream or original text. Does not prove identity of an unavailable binary or causal bottlenecks.'}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('capture',type=Path)
    ap.add_argument('--chip',choices=['a100','h100','b300','l40s','rtxpro'],required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    try:report=check(args.capture,args.chip)
    except (ValueError,AssertionError,KeyError,OSError) as e:
        report={'status':'failed','error':str(e)}
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'],report.get('winner',''),report.get('review_flags',report.get('error','')))
    return int(report['status']!='validated')
if __name__=='__main__':raise SystemExit(main())
