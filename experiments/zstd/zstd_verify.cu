// Standalone diagnostic derived from public vortex nvcomp/zstd.rs call sequence.
// No Vortex/internal campaign binaries are used. This is not an exact allocator replica.
#include <cuda_runtime.h>
#include <nvcomp/zstd.h>
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#define CU(x) do { auto e=(x); if(e!=cudaSuccess)throw std::runtime_error(std::string(#x)+": "+cudaGetErrorString(e)); }while(0)
#define NV(x) do { auto e=(x); if(e!=nvcompSuccess)throw std::runtime_error(std::string(#x)+": nvcomp status "+std::to_string((int)e)); }while(0)
struct Frames {uint64_t n,output,payload,vpf,rows,framing;int64_t level;std::vector<std::vector<char>> data;std::vector<size_t> sizes,outs;size_t compressed=0;};
uint64_t u64(std::istream& s){uint64_t x;s.read((char*)&x,8);if(!s)throw std::runtime_error("truncated archive");return x;}
Frames read_frames(const char* path){std::ifstream s(path,std::ios::binary);char magic[8];s.read(magic,8);if(std::string(magic,8)!="ZRV00001")throw std::runtime_error("bad archive");Frames f;f.n=u64(s);f.output=u64(s);f.payload=u64(s);f.vpf=u64(s);f.rows=u64(s);f.framing=u64(s);f.level=(int64_t)u64(s);size_t total=0;for(size_t i=0;i<f.n;i++){size_t c=u64(s),o=u64(s);if(!c||!o||c>(1ull<<32)||o>(1ull<<32))throw std::runtime_error("invalid frame size");f.data.emplace_back(c);s.read(f.data.back().data(),c);if(!s)throw std::runtime_error("truncated frame");f.sizes.push_back(c);f.outs.push_back(o);total+=o;f.compressed+=c;}if(total!=f.output||s.peek()!=EOF)throw std::runtime_error("archive size mismatch");return f;}
std::vector<char> read_bytes(const char* path){std::ifstream s(path,std::ios::binary|std::ios::ate);if(!s)throw std::runtime_error("cannot open expected bytes");size_t n=s.tellg();s.seekg(0);std::vector<char> b(n);s.read(b.data(),n);if(!s)throw std::runtime_error("truncated expected bytes");return b;}
struct Prep {
 std::vector<void*> allocations;std::vector<const void*> h_in;std::vector<void*> h_out;const void** in=nullptr;void** out=nullptr;size_t *ins=nullptr,*outs=nullptr,*actual=nullptr;nvcompStatus_t* statuses=nullptr;char* output=nullptr;void* temp=nullptr;size_t temp_bytes=0;cudaStream_t stream;
 void* alloc(size_t n){void* p;CU(cudaMalloc(&p,std::max<size_t>(n,1)));allocations.push_back(p);return p;}
 void upload(void* dst,const void* src,size_t n){CU(cudaMemcpyAsync(dst,src,n,cudaMemcpyHostToDevice,stream));}
 Prep(const Frames& f,cudaStream_t s,nvcompBatchedZstdDecompressOpts_t opts):stream(s){
  NV(nvcompBatchedZstdDecompressGetTempSizeAsync(f.n,*std::max_element(f.outs.begin(),f.outs.end()),opts,&temp_bytes,f.output));
  for(auto& x:f.data){void* p=alloc(x.size());upload(p,x.data(),x.size());h_in.push_back(p);}
  output=(char*)alloc(f.output+256);size_t offset=0;for(auto n:f.outs){h_out.push_back(output+offset);offset+=n;}
  in=(const void**)alloc(f.n*sizeof(void*));out=(void**)alloc(f.n*sizeof(void*));ins=(size_t*)alloc(f.n*sizeof(size_t));outs=(size_t*)alloc(f.n*sizeof(size_t));actual=(size_t*)alloc(f.n*sizeof(size_t));statuses=(nvcompStatus_t*)alloc(f.n*sizeof(nvcompStatus_t));temp=alloc(temp_bytes);
  upload((void*)in,h_in.data(),f.n*sizeof(void*));upload(out,h_out.data(),f.n*sizeof(void*));upload(ins,f.sizes.data(),f.n*sizeof(size_t));upload(outs,f.outs.data(),f.n*sizeof(size_t));
 }
 ~Prep(){cudaStreamSynchronize(stream);for(auto p:allocations)cudaFree(p);}
};
struct Result {std::string mode;std::vector<double> ns;std::vector<int> byte_checked;size_t status_checks=0,size_checks=0,temp_bytes=0;};
int main(int argc,char**argv){try{
 if(argc<4){std::fprintf(stderr,"usage: zstd_verify ARCHIVE EXPECTED OUTPUT_JSON [ITERS=100] [ORDER=reuse,reprepare] [BACKEND=default|cuda]\n");return 2;}
 int iters=argc>4?std::atoi(argv[4]):100;if(iters<100)throw std::runtime_error("at least100iterations required");std::string order=argc>5?argv[5]:"reuse,reprepare",backend=argc>6?argv[6]:"default";
 Frames f=read_frames(argv[1]);auto expected=read_bytes(argv[2]);if(expected.size()!=f.output)throw std::runtime_error("expected size differs archive");
 nvcompBatchedZstdDecompressOpts_t opts{};if(backend=="default")opts.backend=NVCOMP_DECOMPRESS_BACKEND_DEFAULT;else if(backend=="cuda")opts.backend=NVCOMP_DECOMPRESS_BACKEND_CUDA;else throw std::runtime_error("backend must default orcuda; do not silently switch on failure");
 cudaStream_t stream;CU(cudaStreamCreate(&stream));cudaEvent_t begin,end;CU(cudaEventCreateWithFlags(&begin,cudaEventBlockingSync));CU(cudaEventCreateWithFlags(&end,cudaEventBlockingSync));
 std::vector<nvcompStatus_t> host_status(f.n);std::vector<size_t> host_sizes(f.n);std::vector<char> observed(f.output+256);std::vector<Result> results;
 size_t pos=0;while(pos<order.size()){
  size_t comma=order.find(',',pos);std::string mode=order.substr(pos,comma==std::string::npos?comma:comma-pos);pos=comma==std::string::npos?order.size():comma+1;if(mode!="reuse"&&mode!="reprepare")throw std::runtime_error("invalid order mode");
  Result r;r.mode=mode;std::unique_ptr<Prep> reusable;if(mode=="reuse")reusable=std::make_unique<Prep>(f,stream,opts);
  // Two warmups, then100 event samples. Both modes get equivalent checks.
  for(int iter=-2;iter<iters;iter++){
   std::unique_ptr<Prep> fresh;if(mode=="reprepare")fresh=std::make_unique<Prep>(f,stream,opts);Prep& p=mode=="reuse"?*reusable:*fresh;r.temp_bytes=p.temp_bytes;
   const bool check_bytes=iter==-2||iter==0||iter==iters-1;
   if(check_bytes)CU(cudaMemsetAsync(p.output,0xA5,f.output+256,stream));
   CU(cudaMemsetAsync(p.actual,0xff,f.n*sizeof(size_t),stream));CU(cudaMemsetAsync(p.statuses,0xff,f.n*sizeof(nvcompStatus_t),stream));
   CU(cudaEventRecord(begin,stream));
   NV(nvcompBatchedZstdDecompressAsync(p.in,p.ins,p.outs,p.actual,f.n,p.temp,p.temp_bytes,p.out,opts,p.statuses,stream));
   CU(cudaEventRecord(end,stream));CU(cudaEventSynchronize(end));float ms;CU(cudaEventElapsedTime(&ms,begin,end));if(iter>=0)r.ns.push_back(double(ms)*1e6);
   // Per-frame completion status/size verification EVERY launch, outside timed events.
   CU(cudaMemcpyAsync(host_status.data(),p.statuses,f.n*sizeof(nvcompStatus_t),cudaMemcpyDeviceToHost,stream));CU(cudaMemcpyAsync(host_sizes.data(),p.actual,f.n*sizeof(size_t),cudaMemcpyDeviceToHost,stream));CU(cudaStreamSynchronize(stream));
   for(size_t i=0;i<f.n;i++){if(host_status[i]!=nvcompSuccess)throw std::runtime_error("frame status failure frame="+std::to_string(i)+" code="+std::to_string((int)host_status[i]));if(host_sizes[i]!=f.outs[i])throw std::runtime_error("frame actual size mismatch frame="+std::to_string(i));}r.status_checks+=f.n;r.size_checks+=f.n;
   if(check_bytes){CU(cudaMemcpy(observed.data(),p.output,f.output+256,cudaMemcpyDeviceToHost));if(!std::equal(expected.begin(),expected.end(),observed.begin())){size_t i=0;while(i<f.output&&expected[i]==observed[i])i++;throw std::runtime_error("decoded byte mismatch offset="+std::to_string(i));}for(size_t i=f.output;i<f.output+256;i++)if((unsigned char)observed[i]!=0xA5)throw std::runtime_error("output guard overwrite");r.byte_checked.push_back(iter);}
  }
  results.push_back(std::move(r));
 }
 std::ofstream o(argv[3]);o<<std::setprecision(17);o<<"{\"backend\":\""<<backend<<"\",\"allocation_api\":\"cudaMalloc, separate compressed frame allocations\",\"payload_bytes\":"<<f.payload<<",\"actual_decoded_bytes\":"<<f.output<<",\"compressed_bytes\":"<<f.compressed<<",\"rows\":"<<f.rows<<",\"frames\":"<<f.n<<",\"values_per_frame\":"<<f.vpf<<",\"level\":"<<f.level<<",\"framing\":\""<<(f.framing?"u32-prefix":"flat")<<"\",\"results\":[";
 for(size_t j=0;j<results.size();j++){auto&r=results[j];auto sorted=r.ns;std::sort(sorted.begin(),sorted.end());double median=(sorted[(iters-1)/2]+sorted[iters/2])/2;if(j)o<<",";o<<"{\"mode\":\""<<r.mode<<"\",\"iterations\":"<<iters<<",\"validated\":true,\"status_checks\":"<<r.status_checks<<",\"size_checks\":"<<r.size_checks<<",\"workspace_bytes\":"<<r.temp_bytes<<",\"min_ns\":"<<sorted.front()<<",\"median_ns\":"<<median<<",\"max_ns\":"<<sorted.back()<<",\"payload_min_gb_s\":"<<f.payload/sorted.front()<<",\"payload_median_gb_s\":"<<f.payload/median<<",\"actual_output_min_gb_s\":"<<f.output/sorted.front()<<",\"full_byte_guard_checked_iterations\":[";for(size_t i=0;i<r.byte_checked.size();i++){if(i)o<<",";o<<r.byte_checked[i];}o<<"],\"decode_ns_iters\":[";for(size_t i=0;i<r.ns.size();i++){if(i)o<<",";o<<r.ns[i];}o<<"]}";}
 o<<"]}\n";if(!o)throw std::runtime_error("failed writing result");CU(cudaEventDestroy(begin));CU(cudaEventDestroy(end));CU(cudaStreamDestroy(stream));return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"FAILED: %s\n",e.what());return 1;}}
