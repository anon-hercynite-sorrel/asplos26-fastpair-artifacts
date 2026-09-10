#include <qpl/qpl.h>
#include <vector>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <algorithm>
#include <chrono>
#include <fstream>
static std::vector<uint8_t> readf(const char* p){ std::ifstream f(p,std::ios::binary|std::ios::ate); auto n=f.tellg(); f.seekg(0); std::vector<uint8_t> v((size_t)n); f.read((char*)v.data(),n); return v; }
static qpl_status compress_block(qpl_path_t path,const uint8_t*in,uint32_t ilen,uint8_t*o,uint32_t*olen){
  uint32_t s; qpl_get_job_size(path,&s); std::vector<uint8_t> jb(s); qpl_job*j=(qpl_job*)jb.data();
  if(qpl_init_job(path,j)!=QPL_STS_OK) return (qpl_status)999;
  j->op=qpl_op_compress; j->level=qpl_default_level; j->next_in_ptr=(uint8_t*)in; j->available_in=ilen;
  j->next_out_ptr=o; j->available_out=*olen; j->flags=QPL_FLAG_FIRST|QPL_FLAG_LAST|QPL_FLAG_DYNAMIC_HUFFMAN|QPL_FLAG_OMIT_VERIFY;
  qpl_status st=qpl_execute_job(j); *olen=j->total_out; qpl_fini_job(j); return st; }
int main(int argc,char**argv){
  const char* path=argv[1]; size_t BLK=256*1024; size_t TILE=(getenv("TILE_MB")?atoll(getenv("TILE_MB")):256)*1024ULL*1024ULL;
  auto raw=readf(path); uint64_t nrows=*(const uint64_t*)raw.data(); size_t hdr=8+(size_t)(nrows+1)*4;
  const uint8_t* Pp=raw.data()+hdr; size_t plen=raw.size()-hdr;
  std::vector<uint8_t> tiled; tiled.reserve(TILE+plen); while(tiled.size()<TILE) tiled.insert(tiled.end(),Pp,Pp+plen);
  const uint8_t* DATA=tiled.data(); size_t total=tiled.size(); size_t nblk=(total+BLK-1)/BLK;
  std::vector<std::vector<uint8_t>> comp,out; std::vector<size_t> olen,ooff; size_t ctot=0,dtot=0,retries=0;
  for(size_t i=0;i<nblk;i++){ size_t off=i*BLK,len=std::min(BLK,total-off);
    std::vector<uint8_t> c(len+8192),o(len); uint32_t cl; qpl_status st=(qpl_status)1; int tries=0;
    while(st!=QPL_STS_OK && tries<12){ cl=(uint32_t)c.size(); st=compress_block(qpl_path_software,DATA+off,(uint32_t)len,c.data(),&cl); if(st!=QPL_STS_OK){tries++;retries++;} }
    if(st!=QPL_STS_OK){printf("%-18s compress blk %zu gave up status=%d\n",argv[1],i,(int)st);return 2;}
    c.resize(cl); ctot+=cl; ooff.push_back(off); dtot+=len; comp.push_back(std::move(c)); out.push_back(std::move(o)); olen.push_back(len);
  }
  uint32_t jsz; qpl_get_job_size(qpl_path_hardware,&jsz); std::vector<uint8_t> jbuf(jsz); qpl_job* job=(qpl_job*)jbuf.data();
  if(qpl_init_job(qpl_path_hardware,job)!=QPL_STS_OK){printf("HW init FAILED\n");return 1;}
  size_t vmis=0,dretry=0;
  for(size_t i=0;i<comp.size();i++){ qpl_status st=(qpl_status)1; int tr=0;
    while(st!=QPL_STS_OK && tr<16){ job->op=qpl_op_decompress; job->next_in_ptr=comp[i].data(); job->available_in=(uint32_t)comp[i].size();
      job->next_out_ptr=out[i].data(); job->available_out=(uint32_t)olen[i]; job->flags=QPL_FLAG_FIRST|QPL_FLAG_LAST;
      st=qpl_execute_job(job); if(st!=QPL_STS_OK){tr++;dretry++;} }
    if(st!=QPL_STS_OK){printf("%-18s IAA decode gave up blk %zu status=%d\n",argv[1],i,(int)st);return 3;}
    if(job->total_out!=olen[i]||memcmp(out[i].data(),DATA+ooff[i],olen[i])) vmis++; }
  auto pass=[&](){for(size_t i=0;i<comp.size();i++){job->op=qpl_op_decompress;job->next_in_ptr=comp[i].data();job->available_in=(uint32_t)comp[i].size();job->next_out_ptr=out[i].data();job->available_out=(uint32_t)olen[i];job->flags=QPL_FLAG_FIRST|QPL_FLAG_LAST;qpl_execute_job(job);}};
  pass(); auto t0=std::chrono::steady_clock::now(); pass();
  double one=std::max(1e-9,std::chrono::duration<double>(std::chrono::steady_clock::now()-t0).count());
  int it=std::max(3,(int)(0.7/one+0.999)); auto s0=std::chrono::steady_clock::now(); for(int k=0;k<it;k++)pass();
  double secs=std::chrono::duration<double>(std::chrono::steady_clock::now()-s0).count(); qpl_fini_job(job);
  printf("%-18s ratio %.2fx  IAA-decode %.2f GB/s  VERIFY %s  (compress retries=%zu)\n", argv[1], (double)dtot/ctot, (double)it*dtot/secs/1e9, vmis?"MISMATCH":"OK", retries+dretry);
  return 0;
}
