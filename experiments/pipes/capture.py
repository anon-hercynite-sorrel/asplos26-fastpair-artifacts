#!/usr/bin/env python3
"""Repeat the Windows OnPair-12 boost screen and profile on one local GPU.
Requires an otherwise idle GPU, a built public harness, the prepared input, and
sudo access for resetting clocks and accessing NCU counters. Does not provision GPUs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import tarfile

ARTIFACT=Path(__file__).resolve().parents[2]
REVISION='f6d81878715bf322a0917ada32bcf40adffbd3ef'
INPUT_SHA='067f1bc2a8df043e0b475eda6b2238cf76c93f497d3ca2b001e3a301e85cd5e6'
PAYLOAD=999999899
DEFAULT='onpair_dw_k6_t256_b4'


def file_sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def validate_workload(gpu):
    if not(gpu['decoded_bytes']==PAYLOAD and gpu['total_tokens']==99090926 and gpu['chunks']==1
           and gpu['verified'] is True and gpu['validated'] is True and abs(gpu['frac_le8']-.37251443)<1e-6):
        raise ValueError('wrong workload statistics or unvalidated decoded bytes')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--chip',choices=['a100','h100','b300','l40s','rtxpro'],required=True)
    ap.add_argument('--harness',type=Path,required=True)
    ap.add_argument('--vortex',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True,help='New directory; never overwrites an existing capture.')
    ap.add_argument('--expected-revision',help='Optional exact harness commit to require; default records the current checkout.')
    ap.add_argument('--expected-input-sha256',help='Optional exact prepared-container digest to require; default validates workload statistics and decoded bytes.')
    args=ap.parse_args()
    harness=args.harness.resolve(); data=args.vortex.resolve(); out=args.output.resolve()
    bench=harness/'target/release/onpair-chunk-bench'
    if not bench.is_file():ap.error('build onpair-chunk-bench first')
    input_sha=file_sha256(data)
    if args.expected_input_sha256 and input_sha!=args.expected_input_sha256.lower():
        ap.error('input digest differs from --expected-input-sha256')
    revision=subprocess.check_output(['git','-C',str(harness),'rev-parse','HEAD'],text=True).strip()
    if args.expected_revision and revision!=args.expected_revision:ap.error('harness revision differs from --expected-revision')
    ncu=shutil.which('ncu')
    if not ncu:ap.error('ncu not found on PATH')
    ncu=str(Path(ncu).resolve())
    out.mkdir(parents=True,exist_ok=False)
    env={k:v for k,v in os.environ.items() if not k.startswith('ONPAIR_')}
    env['ONPAIR_FAST']='1'
    with tarfile.open(ARTIFACT/'results/pipes-boost-20260909/evidence.tar.gz') as ar:
        def member(name):return ar.extractfile(name).read()
        selection=json.loads(member('selection.json'))[args.chip]
        candidates=member(args.chip+'-candidates.txt').decode().splitlines()
        for name in ['capture-metrics.txt','missing-metrics.json']:
            (out/name).write_bytes(member(f'evidence/{args.chip}/boost/{name}'))
    (out/'candidates.txt').write_text('\n'.join(candidates)+'\n')
    (out/'selection.json').write_text(json.dumps({args.chip:selection},indent=2)+'\n')
    (out/'chip.txt').write_text(args.chip+'\n')
    (out/'source-revision.txt').write_text(revision+'\n')
    (out/'source-status.txt').write_text(subprocess.check_output(['git','-C',str(harness),'status','--porcelain'],text=True))
    (out/'input-binary.sha256').write_text(input_sha+'  '+str(data)+'\n'+file_sha256(bench)+'  '+str(bench)+'\n')
    (out/'input-identity.json').write_text(json.dumps({
        'container_sha256':input_sha, 'archived_container_sha256':INPUT_SHA,
        'archived_input_container_match':input_sha==INPUT_SHA,
        'expected_input_sha256':args.expected_input_sha256,
        'source_revision':revision, 'archived_source_revision_match':revision==REVISION,
        'expected_revision':args.expected_revision,
        'validation_scope':'Each timing cell must match the archived decoded-byte count, code count, chunk count and short-token fraction, and pass byte validation against its own input. Equal statistics do not prove identity with the archived encoded stream or original text.'
    },indent=2)+'\n')
    shutil.copyfile(__file__,out/'run.py')
    discard=2000 if args.chip in ('a100','b300') else 0
    protocol={'discard_per_kernel':discard,'retained_per_round':100,'profile_skip':3+discard,
              'profile_gpu_iters':2100 if discard else 8}
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    def run(cmd,stem,extra=None,check=True):
        with (out/(stem+'.stdout')).open('w') as stdout,(out/(stem+'.stderr')).open('w') as stderr:
            result=subprocess.run([str(x) for x in cmd],env=dict(env,**(extra or {})),stdout=stdout,stderr=stderr)
        if check and result.returncode:raise RuntimeError(f'{stem} failed; see its stderr file')
    def timing(stem,names,count=100,drop=0,seed=None):
        run([bench,'gpu-decode-vortex','--vortex',data,'--column','line','--gpu-iters',count+drop,
             '--gpu-validate','--gpu-kernels',','.join(names)],stem,{'ONPAIR_SHUFFLE_SEED':str(seed)} if seed else None)
        path=out/(stem+'.json');(out/(stem+'.stdout')).rename(path)
        gpu=json.loads(path.read_text())['gpu']
        validate_workload(gpu)
        rows={k['kernel']:k for k in gpu['kernels']}
        if len(rows)!=len(gpu['kernels']) or set(rows)!=set(names):raise ValueError('kernel set differs')
        samples={}
        for name,k in rows.items():
            times=k['decode_ns_iters']
            if not(k['applicable'] and k['verified'] and len(times)==count+drop and all(type(t)is int and t>0 for t in times)):
                raise ValueError('invalid timings: '+name)
            samples[name]=times[drop:]
        return samples
    def rank(times):return sorted(times,key=lambda n:(min(times[n]),statistics.median(times[n]),n))
    monitor=None;code=1
    try:
        run(['nvidia-smi','-q'],'nvidia-before')
        run(['sudo','nvidia-smi','-pm','1'],'persistence',check=False)
        run(['sudo','nvidia-smi','-rgc'],'reset-gpu-clocks')
        run(['sudo','nvidia-smi','-rac'],'reset-application-clocks',check=False)
        for program in [ncu,'nvcc','rustc']:run([program,'--version'],Path(program).name+'-version')
        tmpdir=out/'ncu-tmp'
        subprocess.run(['sudo','mkdir','-p',str(tmpdir)],check=True)
        subprocess.run(['sudo','chmod','700',str(tmpdir)],check=True)
        clocks=(out/'clocks.csv').open('w')
        monitor=subprocess.Popen(['nvidia-smi','--query-gpu=timestamp,clocks.sm,clocks.mem,pstate,power.draw,temperature.gpu,utilization.gpu','--format=csv','--loop-ms=100'],stdout=clocks,stderr=subprocess.STDOUT)
        timing('warmup',[selection['archived_winner']],count=2000)
        sweep=timing('sweep',candidates,seed=20260909)
        shortlist=list(dict.fromkeys(rank(sweep)[:3]+[selection['archived_winner'],DEFAULT]))
        pooled={n:[] for n in shortlist}
        for i in range(2):
            for n,ts in timing(f'confirmation-{i}',shortlist,drop=discard,seed=20260910+i).items():pooled[n]+=ts
        winner=rank(pooled)[0]
        selected={'winner':winner,'recommended':DEFAULT,'archived_winner':selection['archived_winner'],
                  'full_sweep_count':len(candidates),'confirmation_candidates':shortlist,
                  'confirmed':{n:{'n':len(ts),'min_GBps':PAYLOAD/min(ts),'median_GBps':PAYLOAD/statistics.median(ts)} for n,ts in pooled.items()},
                  'protocol':protocol}
        (out/'selected.json').write_text(json.dumps(selected,indent=2)+'\n')
        print('Selected',winner,flush=True)
        metrics=(out/'capture-metrics.txt').read_text().strip()
        for name in dict.fromkeys([winner,DEFAULT]):
            timing(name+'-before',[name],drop=discard)
            run(['sudo','env','TMPDIR='+str(tmpdir),'ONPAIR_FAST=1',ncu,'--replay-mode','application',
                 '--app-replay-match','grid','--clock-control','none','--cache-control','none',
                 '--kernel-name-base','function','--kernel-name',name,'--launch-skip',protocol['profile_skip'],
                 '--launch-count','4','--metrics',metrics,'--export',out/name,'--log-file',out/(name+'.ncu.log'),
                 bench,'gpu-decode-vortex','--vortex',data,'--column','line','--gpu-iters',protocol['profile_gpu_iters'],
                 '--gpu-validate','--gpu-kernels',name],name+'.profile')
            run([ncu,'--import',out/(name+'.ncu-rep'),'--page','raw','--csv','--print-units','base'],name+'.raw')
            (out/(name+'.raw.stdout')).rename(out/(name+'.raw.csv'))
            timing(name+'-after',[name],drop=discard)
        run(['nvidia-smi','-q'],'nvidia-after')
        (out/'CAPTURE_COMPLETE').write_text('Collection complete; clock and raw-counter acceptance still required.\n')
        code=0
    finally:
        if monitor:monitor.terminate();monitor.wait(timeout=10);clocks.close()
        (out/'exit-code').write_text(str(code)+'\n')
    print('Capture saved in',out)
    print('Compare selection, clocks and timing/profile agreement before interpreting this capture; see README.md.')

if __name__=='__main__':main()
