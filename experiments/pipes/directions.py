#!/usr/bin/env python3
"""Analyze direct/estimated direction splits from accepted raw boost captures.
Standard library only. Does not modify the manuscript or production figure.
"""
import argparse
import csv
import hashlib
import json
import math
import statistics as st
from pathlib import Path

M = {
 'total':'l1tex__data_pipe_lsu_wavefronts.sum',
 'shared':'l1tex__data_pipe_lsu_wavefronts_mem_shared.sum',
 'sread':'l1tex__data_pipe_lsu_wavefronts_mem_shared_op_ld.sum',
 'swrite':'l1tex__data_pipe_lsu_wavefronts_mem_shared_op_st.sum',
 'atom':'l1tex__data_pipe_lsu_wavefronts_mem_shared_op_atom.sum',
 'tread':'l1tex__t_output_wavefronts_pipe_lsu_mem_global_op_ld.sum',
 'twrite':'l1tex__t_output_wavefronts_pipe_lsu_mem_global_op_st.sum',
 'dread':'l1tex__data_pipe_lsu_wavefronts_mem_lgds_cmd_read.sum',
 'dwrite':'l1tex__data_pipe_lsu_wavefronts_mem_lgds_cmd_write.sum',
 'local_read':'l1tex__t_sectors_pipe_lsu_mem_local_op_ld.sum',
 'local_write':'l1tex__t_sectors_pipe_lsu_mem_local_op_st.sum',
 'util':'l1tex__data_pipe_lsu_wavefronts.avg.pct_of_peak_sustained_elapsed',
}
ORDER=['a100','h100','b300','l40s','rtxpro']

def read_launches(path,kernel):
 with path.open() as f:
  rows=list(csv.DictReader(f))
 units=rows.pop(0)
 assert len(rows)==4, (path,len(rows))
 result=[]
 for row in rows:
  assert row['Kernel Name']==kernel
  m={}
  for key,name in M.items():
   if name not in row:
    assert key in ('dread','dwrite'),(path,name)
    continue
   assert units[name] in ('wavefront','sector','%',''),(name,units[name])
   m[key]=float(row[name].replace(',',''))
   assert math.isfinite(m[key]) and m[key]>=0
  assert m['local_read']==m['local_write']==m['atom']==0
  assert ('dread' in m)==('dwrite' in m)
  n,s=m['total'],m['shared'];u=100*(n-s)/n
  assert 0<s<n and m['sread']+m['swrite']<=s
  tag=m['tread']/(m['tread']+m['twrite'])
  direct=m['dread']/(m['dread']+m['dwrite']) if 'dread' in m else None
  chosen=direct if direct is not None else tag
  parts={'global_reads':u*chosen,'global_writes':u*(1-chosen),
         'shared_reads':100*m['sread']/n,'shared_writes':100*m['swrite']/n,
         'other':100*(s-m['sread']-m['swrite'])/n}
  assert math.isclose(sum(parts.values()),100,abs_tol=1e-10)
  result.append({'id':row['ID'],'raw':m,'tag_read_fraction':tag,'direct_read_fraction':direct,
    'shares_pct':parts,'peak_points':{k:v*m['util']/100 for k,v in parts.items()},
    'estimated_global_read_share_pct':u*tag,'estimated_global_write_share_pct':u*(1-tag),
    'estimate_minus_direct_read_share_pp':u*(tag-direct) if direct is not None else None,
    'estimate_minus_direct_read_peak_pp':u*(tag-direct)*m['util']/100 if direct is not None else None,
    'direct_nonshared_closure_share_pp':100*((n-s)-m['dread']-m['dwrite'])/n if direct is not None else None})
 return result
