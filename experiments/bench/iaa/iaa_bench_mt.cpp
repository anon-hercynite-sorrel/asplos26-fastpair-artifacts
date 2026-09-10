// iaa_bench_mt.cpp -- multi-engine IAA hardware-Deflate decode benchmark.
//
// Why this exists: the single-WQ synchronous iaa_bench.cpp drives ONE of the box's
// IAA engines, which understates IAA (its design point is many concurrent jobs across
// all engines) and is not symmetric to the GPU "whole-GPU OnPair vs the DE" framing.
// This version saturates ALL engines: T worker threads, each pinned across both NUMA
// nodes, each holding its own hardware qpl_job, pulling 256 KB blocks off a shared
// atomic counter and decoding on the IAA hardware path. QPL routes each thread's job to
// an enabled shared WQ on the thread's NUMA node, so threads on node0 use that socket's
// IAA devices and node1's threads the other socket -> all engines busy.
//
// De-risked (status-503 = QPL_STS_INIT_WORK_QUEUES_NOT_AVAILABLE) by: (1) run AS ROOT
// (the original per-engine data was collected as root and worked; 503 was the single
// small shared WQ filling, not a privilege issue), (2) shared WQs on all engines sized
// 8x128 with block_on_fault=1, (3) mlock the compressed + output buffers so a fault can
// never fail a descriptor. Busy-queue (QPL_STS_QUEUES_ARE_BUSY_ERR=5) is retried, not
// fatal. (A prior non-root `iaa`-user attempt HUNG: chown /dev/iax is not a complete
// SVA/PASID setup, so block_on_fault waited forever; root + QPL's SVA bind translates.)
//
// Reports aggregate GB/s at the requested thread count. Sweep T (1,4,8,16,32,...) to
// find IAA's saturation point; T=1 reproduces the per-engine number for cross-check.
#include <qpl/qpl.h>
#include <vector>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <algorithm>
#include <atomic>
#include <thread>
#include <chrono>
#include <fstream>
#include <sys/mman.h>
#include <sched.h>

static std::vector<uint8_t> readf(const char* p){
  std::ifstream f(p,std::ios::binary|std::ios::ate); auto n=f.tellg(); f.seekg(0);
  std::vector<uint8_t> v((size_t)n); f.read((char*)v.data(),n); return v;
}
static qpl_status compress_block(qpl_path_t path,const uint8_t*in,uint32_t ilen,uint8_t*o,uint32_t*olen){
  uint32_t s; qpl_get_job_size(path,&s); std::vector<uint8_t> jb(s); qpl_job*j=(qpl_job*)jb.data();
  if(qpl_init_job(path,j)!=QPL_STS_OK) return (qpl_status)999;
  j->op=qpl_op_compress; j->level=qpl_default_level; j->next_in_ptr=(uint8_t*)in; j->available_in=ilen;
  j->next_out_ptr=o; j->available_out=*olen;
  j->flags=QPL_FLAG_FIRST|QPL_FLAG_LAST|QPL_FLAG_DYNAMIC_HUFFMAN|QPL_FLAG_OMIT_VERIFY;
  qpl_status st=qpl_execute_job(j); *olen=j->total_out; qpl_fini_job(j); return st;
}

struct Blk { const uint8_t* cptr; uint32_t clen; uint8_t* optr; uint32_t olen; };

int main(int argc,char**argv){
  if(argc<2){ printf("usage: %s <colfile> [threads] [tile_mb]\n",argv[0]); return 1; }
  const char* path=argv[1];
  int T = argc>2 ? atoi(argv[2]) : (int)std::thread::hardware_concurrency();
  if(T<1) T=1;
  size_t BLK=256*1024;
  size_t TILE=(argc>3?atoll(argv[3]):(getenv("TILE_MB")?atoll(getenv("TILE_MB")):256))*1024ULL*1024ULL;

  auto raw=readf(path);
  uint64_t nrows=*(const uint64_t*)raw.data(); size_t hdr=8+(size_t)(nrows+1)*4;
  const uint8_t* Pp=raw.data()+hdr; size_t plen=raw.size()-hdr;
  std::vector<uint8_t> tiled; tiled.reserve(TILE+plen);
  while(tiled.size()<TILE) tiled.insert(tiled.end(),Pp,Pp+plen);
  const uint8_t* DATA=tiled.data(); size_t total=tiled.size(); size_t nblk=(total+BLK-1)/BLK;

  // Software-compress every block once (QPL software path), keep the compressed bytes
  // and a same-size output slot. Identical uncompressed bytes the OnPair decoder sees.
  std::vector<std::vector<uint8_t>> comp(nblk), out(nblk);
  std::vector<size_t> ooff(nblk);
  size_t ctot=0,dtot=0,cretry=0;
  for(size_t i=0;i<nblk;i++){
    size_t off=i*BLK,len=std::min(BLK,total-off);
    std::vector<uint8_t> c(len+8192); uint32_t cl; qpl_status st=(qpl_status)1; int tries=0;
    while(st!=QPL_STS_OK && tries<12){ cl=(uint32_t)c.size(); st=compress_block(qpl_path_software,DATA+off,(uint32_t)len,c.data(),&cl); if(st!=QPL_STS_OK){tries++;cretry++;} }
    if(st!=QPL_STS_OK){ printf("%-18s compress blk %zu gave up status=%d\n",path,i,(int)st); return 2; }
    c.resize(cl); comp[i]=std::move(c); out[i].assign(len,0); ooff[i]=off; ctot+=cl; dtot+=len;
  }
  // mlock the compressed + output buffers so no descriptor ever fails on a page fault.
  for(size_t i=0;i<nblk;i++){ mlock(comp[i].data(),comp[i].size()); mlock(out[i].data(),out[i].size()); }

  int ncpu = (int)std::thread::hardware_concurrency(); if(ncpu<1) ncpu=T;

  // One decode pass: T threads, each own hardware job, pull blocks off a shared counter.
  auto one_pass=[&](std::atomic<size_t>& vmis)->void{
    std::atomic<size_t> next{0};
    auto worker=[&](int tid){
      cpu_set_t set; CPU_ZERO(&set); CPU_SET(tid % ncpu, &set);
      pthread_setaffinity_np(pthread_self(), sizeof(set), &set);   // spread across both sockets
      uint32_t jsz; qpl_get_job_size(qpl_path_hardware,&jsz);
      std::vector<uint8_t> jb(jsz); qpl_job* job=(qpl_job*)jb.data();
      if(qpl_init_job(qpl_path_hardware,job)!=QPL_STS_OK) return;
      for(;;){
        size_t i=next.fetch_add(1); if(i>=nblk) break;
        qpl_status st=(qpl_status)1; int tr=0;
        while(st!=QPL_STS_OK && tr<64){
          job->op=qpl_op_decompress; job->next_in_ptr=comp[i].data(); job->available_in=(uint32_t)comp[i].size();
          job->next_out_ptr=out[i].data(); job->available_out=(uint32_t)out[i].size();
          job->flags=QPL_FLAG_FIRST|QPL_FLAG_LAST;
          st=qpl_execute_job(job);
          if(st!=QPL_STS_OK) tr++;     // busy/transient -> retry on the shared WQ
        }
        if(st!=QPL_STS_OK){ vmis.fetch_add(1); continue; }
        if(job->total_out!=out[i].size() || memcmp(out[i].data(),DATA+ooff[i],out[i].size())) vmis.fetch_add(1);
      }
      qpl_fini_job(job);
    };
    std::vector<std::thread> ths; for(int t=0;t<T;t++) ths.emplace_back(worker,t);
    for(auto&th:ths) th.join();
  };

  std::atomic<size_t> vmis{0};
  one_pass(vmis);                                   // warm + verify
  auto t0=std::chrono::steady_clock::now(); { std::atomic<size_t> d{0}; one_pass(d); }
  double one=std::max(1e-9,std::chrono::duration<double>(std::chrono::steady_clock::now()-t0).count());
  int it=std::max(3,(int)(0.7/one+0.999));
  double best=1e30;
  for(int k=0;k<it;k++){ std::atomic<size_t> d{0}; auto s0=std::chrono::steady_clock::now(); one_pass(d);
    double s=std::chrono::duration<double>(std::chrono::steady_clock::now()-s0).count(); if(s<best) best=s; }

  printf("%-18s threads=%-3d ratio %.2fx  IAA-decode %.2f GB/s  VERIFY %s  (cretry=%zu)\n",
         path, T, (double)dtot/ctot, (double)dtot/best/1e9, vmis.load()?"MISMATCH":"OK", cretry);
  return 0;
}
