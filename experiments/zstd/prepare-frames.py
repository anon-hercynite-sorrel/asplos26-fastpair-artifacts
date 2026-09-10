#!/usr/bin/env python3
"""CPU-only public zstd::bulk-style compression; explicit flat vs u32-prefixed framing."""
import argparse,ctypes as C,ctypes.util,hashlib,json,struct,time
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--payload',type=Path,required=True);ap.add_argument('--lengths',type=Path,required=True);ap.add_argument('--framing',choices=['flat','prefix'],required=True);ap.add_argument('--level',type=int,default=19);ap.add_argument('--values-per-frame',type=int,default=271);ap.add_argument('--libzstd');ap.add_argument('--output-prefix',type=Path,required=True);a=ap.parse_args()
lib=C.CDLL(a.libzstd or ctypes.util.find_library('zstd'))
for name,rest,args in [('ZSTD_versionString',C.c_char_p,[]),('ZSTD_createCCtx',C.c_void_p,[]),('ZSTD_freeCCtx',C.c_size_t,[C.c_void_p]),('ZSTD_compressBound',C.c_size_t,[C.c_size_t]),('ZSTD_CCtx_setParameter',C.c_size_t,[C.c_void_p,C.c_int,C.c_int]),('ZSTD_CCtx_loadDictionary',C.c_size_t,[C.c_void_p,C.c_void_p,C.c_size_t]),('ZSTD_compress2',C.c_size_t,[C.c_void_p,C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t]),('ZSTD_isError',C.c_uint,[C.c_size_t]),('ZSTD_getErrorName',C.c_char_p,[C.c_size_t])]:
 fn=getattr(lib,name);fn.restype=rest;fn.argtypes=args
version=lib.ZSTD_versionString().decode()
if version!='1.5.7':raise RuntimeError(f'Public Cargo pins Zstd 1.5.7, found {version}; use --libzstd with build-pinned-zstd.py output')
raw=a.payload.read_bytes();lb=a.lengths.read_bytes();assert len(lb)%8==0
lengths=[x[0] for x in struct.iter_unpack('<Q',lb)];assert sum(lengths)==len(raw) and a.values_per_frame>0
ctx=lib.ZSTD_createCCtx();assert ctx
rc=lib.ZSTD_CCtx_setParameter(ctx,100,a.level);assert not lib.ZSTD_isError(rc)
rc=lib.ZSTD_CCtx_loadDictionary(ctx,None,0);assert not lib.ZSTD_isError(rc)
a.output_prefix.parent.mkdir(parents=True,exist_ok=True);archive=a.output_prefix.with_suffix('.zrv');expected=a.output_prefix.with_suffix('.expected.bin');nframes=(len(lengths)+a.values_per_frame-1)//a.values_per_frame;outbytes=len(raw)+(4*len(lengths) if a.framing=='prefix' else 0);frame_sizes=[];comp_sizes=[];offset=0;t0=time.monotonic()
with archive.open('wb') as af,expected.open('wb') as ef:
 af.write(b'ZRV00001');af.write(struct.pack('<6Qq',nframes,outbytes,len(raw),a.values_per_frame,len(lengths),int(a.framing=='prefix'),a.level))
 for start in range(0,len(lengths),a.values_per_frame):
  group=lengths[start:start+a.values_per_frame];parts=[]
  for size in group:
   if a.framing=='prefix':parts.append(struct.pack('<I',size))
   parts.append(raw[offset:offset+size]);offset+=size
  frame=b''.join(parts);bound=lib.ZSTD_compressBound(len(frame));dst=C.create_string_buffer(bound);src=C.create_string_buffer(frame);n=lib.ZSTD_compress2(ctx,dst,bound,src,len(frame))
  if lib.ZSTD_isError(n):raise RuntimeError(lib.ZSTD_getErrorName(n).decode())
  af.write(struct.pack('<QQ',n,len(frame)));af.write(dst.raw[:n]);ef.write(frame);frame_sizes.append(len(frame));comp_sizes.append(n)
lib.ZSTD_freeCCtx(ctx)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1<<20),b''):h.update(x)
 return h.hexdigest()
meta={'framing':a.framing,'level':a.level,'values_per_frame':a.values_per_frame,'rows':len(lengths),'frames':nframes,'payload_bytes':len(raw),'actual_decoded_bytes':outbytes,'compressed_bytes':sum(comp_sizes),'payload_compression_ratio':len(raw)/sum(comp_sizes),'frame_min_bytes':min(frame_sizes),'frame_max_bytes':max(frame_sizes),'zstd_version':lib.ZSTD_versionString().decode(),'cpu_compress_seconds':time.monotonic()-t0,'payload_sha256':hashlib.sha256(raw).hexdigest(),'lengths_sha256':hashlib.sha256(lb).hexdigest(),'archive_sha256':sha(archive),'expected_sha256':sha(expected),'historical_windows_level19_vpf271_compressed_bytes':53516006,'matches_historical_compressed_byte_count':a.level==19 and a.values_per_frame==271 and sum(comp_sizes)==53516006}
a.output_prefix.with_suffix('.manifest.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))
