#!/usr/bin/env python3
"""Build public Cargo's vendored Zstd 1.5.7 as a diagnostic shared library."""
import argparse,ctypes,hashlib,json,shlex,subprocess,tarfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--crate',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--cc',default='cc');p.add_argument('--crate-archive',type=Path);a=p.parse_args()
expected='91e19ebc2adc8f83e43039e79776e3fda8ca919132d68a1fed6a5faca2683748'
archive=a.crate_archive or a.crate.parents[2]/'cache'/a.crate.parent.name/(a.crate.name+'.crate')
assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected,'cached crate archive checksum differs public Cargo.lock'
lib=a.crate/'zstd/lib';sources=sorted(x for d in ['common','compress','decompress','dictBuilder'] for x in (lib/d).glob('*.c') if 'xxhash' not in x.name)
sources.append(lib/'decompress/huf_decompress_amd64.S')
# Verify vendored inputs against the exact lockfile-pinned .crate archive.
verified={}
with tarfile.open(archive) as tf:
 for member in tf.getmembers():
  rel=member.name.split('/',1)[-1]
  if member.isfile() and (rel.startswith('zstd/lib/') or rel in ['build.rs','Cargo.toml']):
   sha=hashlib.sha256(tf.extractfile(member).read()).hexdigest()
   actual=hashlib.sha256((a.crate/rel).read_bytes()).hexdigest();assert actual==sha,f'modified crate source: {rel}';verified[rel]=actual
a.output.mkdir(parents=True,exist_ok=True);out=a.output/'libzstd-review-1.5.7.so'
cmd=[a.cc,'-O3','-fPIC','-shared','-DZSTD_LIB_DEPRECATED=0','-DXXH_PRIVATE_API','-ffunction-sections','-fdata-sections','-fmerge-all-constants','-I'+str(lib),'-I'+str(lib/'common'),*[str(s) for s in sources],'-o',str(out)]
(a.output/'libzstd-build-command.txt').write_text(shlex.join(cmd)+'\n')
with (a.output/'libzstd-build.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
z=ctypes.CDLL(str(out.resolve()));z.ZSTD_versionString.restype=ctypes.c_char_p;version=z.ZSTD_versionString().decode();assert version=='1.5.7'
result={'public_cargo_package':'zstd-sys 2.0.16+zstd.1.5.7','cargo_package_checksum':expected,'zstd_version':version,'library':str(out.resolve()),'library_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'compiler':subprocess.check_output([a.cc,'--version'],text=True),'source_hashes':verified,'build_difference':'Shared exported symbols instead of Rust static hidden symbols; same common/compress/decompress/dictBuilder sources, ASM, no legacy or multithreading. Compiler options are recorded; this is a version-pinned diagnostic library, not the historical binary.'}
(a.output/'libzstd-provenance.json').write_text(json.dumps(result,indent=2)+'\n');print(out.resolve())
