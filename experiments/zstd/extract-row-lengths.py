#!/usr/bin/env python3
import argparse,hashlib,json,struct
from pathlib import Path
import pyarrow.parquet as pq
ap=argparse.ArgumentParser();ap.add_argument('parquet');ap.add_argument('--column',default='line');ap.add_argument('--rows',type=int,default=4139945);ap.add_argument('--expected-payload-sha256',default='3d23f57e7e19710603c91e58ca19c7c54c5a643031bf68d4af5a42bec34e1d23');ap.add_argument('--payload-output',type=Path);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
a.output.parent.mkdir(parents=True,exist_ok=True)
payload_out=a.payload_output.open('wb') if a.payload_output else None
h=hashlib.sha256();n=b=0
with a.output.open('wb') as out:
 for batch in pq.ParquetFile(a.parquet).iter_batches(batch_size=65536,columns=[a.column]):
  for value in batch.column(0).to_pylist():
   if n==a.rows:break
   if value is None:raise ValueError('unexpected null in Windows prefix; do not silently alter row boundaries')
   data=value.encode('utf8') if isinstance(value,str) else bytes(value);h.update(data);b+=len(data);n+=1;out.write(struct.pack('<Q',len(data)))
   if payload_out:payload_out.write(data)
  if n==a.rows:break
if payload_out:payload_out.close()
assert n==a.rows and h.hexdigest()==a.expected_payload_sha256,(n,b,h.hexdigest())
meta={'rows':n,'payload_bytes':b,'payload_sha256':h.hexdigest(),'lengths_sha256':hashlib.sha256(a.output.read_bytes()).hexdigest(),'parquet':a.parquet,'column':a.column};a.output.with_suffix('.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta))
