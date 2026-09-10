#!/usr/bin/env bash
# iaa_mt_setup_run.sh -- RUN ON THE GCP c3-standard-192-metal BOX (Sapphire, 8 IAA engines).
# Idempotent across the one required reboot: detects whether intel_iommu is live and runs
# phase 1 (enable IOMMU + reboot) or phase 2 (configure all engines, build, benchmark).
#
# Driven manually from the laptop (the harness can't reboot a box inside its teardown trap):
#   scp this + iaa_bench_mt.cpp + ~/data/onpair-cpu-cols/*.bin + the onpair-cpu-bench repo
#   ssh 'bash iaa_mt_setup_run.sh'          # phase 1 -> reboots
#   (wait for ssh to return)
#   ssh 'bash iaa_mt_setup_run.sh'          # phase 2 -> writes ~/iaa_mt_RESULTS.txt
#
# Fix for the prior single-WQ status-503 (QPL_STS_INIT_WORK_QUEUES_NOT_AVAILABLE): the 503
# was the single size-16 shared WQ filling under rapid submission (ENQCMD-on-full), NOT a
# privilege problem -- the original per-engine data was collected AS ROOT and worked. Cure
# the 503 with MORE/BIGGER shared WQs (8x128, one per device), keep block_on_fault=1 + the
# bench's mlock'd buffers, and run the bench AS ROOT. (A prior switch to a non-root `iaa`
# user HUNG: chown /dev/iax alone is not a complete SVA/PASID setup, so block_on_fault waited
# forever on untranslatable addresses. Root with QPL's own SVA bind translates cleanly.)
set -uo pipefail
WORK="$HOME/iaa"; mkdir -p "$WORK"
log(){ printf '\n\033[1;35m[iaa %s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }

# ───────────────────────── phase 1: enable IOMMU scalable mode + reboot ─────────────────────────
if ! grep -q 'intel_iommu=on' /proc/cmdline; then
  log "PHASE 1: enabling intel_iommu=on,sm_on (needed for IAA shared WQ + SVA), then rebooting"
  sudo apt-get update -y -q >/dev/null 2>&1
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q \
       build-essential cmake nasm pkg-config git pciutils accel-config numactl \
       "linux-modules-extra-$(uname -r)" >/dev/null 2>&1 \
       || log "WARN: apt deps non-zero"
  # idxd ships in linux-modules-extra on the -gcp/-aws kernels, NOT the base image -- without
  # it modprobe idxd fails and no iax devices appear. (This was the first-run gotcha.)
  # Append the IOMMU cmdline to GRUB and regenerate. iommu=pt keeps DMA fast for non-IAA devices.
  sudo sed -i 's/\(GRUB_CMDLINE_LINUX="[^"]*\)"/\1 intel_iommu=on,sm_on iommu=pt"/' /etc/default/grub
  grep GRUB_CMDLINE_LINUX= /etc/default/grub | tail -1
  sudo update-grub 2>&1 | tail -2 || sudo update-grub2 2>&1 | tail -2 || true
  log "rebooting now -- reconnect and re-run this script for phase 2"
  sudo reboot
  exit 0
fi

# ───────────────────────── phase 2: configure all engines, build, benchmark ─────────────────────────
log "PHASE 2: intel_iommu live ($(grep -o 'intel_iommu=[^ ]*' /proc/cmdline)). Configuring all IAA engines."
sudo modprobe idxd 2>&1 | tail -1 || true
sudo modprobe idxd_uacce 2>&1 | tail -1 || true

# A shared user work queue on EVERY iax device, block_on_fault=1 (waits out page faults
# instead of failing the descriptor), wq size = device max. dsadev group + a non-root user
# owning the char devices is what kills the status-503.
NIAX=0
for dev in /sys/bus/dsa/devices/iax*; do
  [ -d "$dev" ] || continue
  D=$(basename "$dev"); N="${D#iax}"
  MAXWQ=$(cat "$dev/max_work_queues_size" 2>/dev/null || echo 128)
  MAXENG=$(cat "$dev/max_engines" 2>/dev/null || echo 8)
  sudo accel-config disable-device "$D" 2>/dev/null
  # One shared user WQ per device, block_on_fault=1, threshold half of size; ALL engines of the
  # device in the same group so the WQ uses the device's full decode capacity.
  sudo accel-config config-wq     "$D/wq$N.0" -g 0 -s "$MAXWQ" -p 10 -m shared -b 1 -t $((MAXWQ/2)) -y user -n iaamt -d user 2>&1 | tail -1
  for e in $(seq 0 $((MAXENG-1))); do sudo accel-config config-engine "$D/engine$N.$e" -g 0 2>/dev/null; done
  sudo accel-config enable-device  "$D" 2>&1 | tail -1
  sudo accel-config enable-wq      "$D/wq$N.0" 2>&1 | tail -1
  NIAX=$((NIAX+1))
done
log "configured $NIAX IAA engines; enabled WQs: $(sudo accel-config list 2>/dev/null | grep -c '"state": "enabled"')"

# Char devices stay root-owned; the bench runs as root (sudo) below. No non-root user.
ls -l /dev/iax* 2>/dev/null | head

# ── Build Intel QPL from source (no stable apt package yet) ──
if [ ! -f /usr/local/lib/libqpl.a ] && [ ! -f /usr/local/lib64/libqpl.a ]; then
  log "building Intel QPL from source"
  cd "$WORK"; [ -d qpl ] || git clone -q --depth 1 --recurse-submodules https://github.com/intel/qpl.git
  cd qpl && git submodule update --init --recursive 2>/dev/null   # google-benchmark etc. (not in --depth 1)
  mkdir -p build && cd build
  cmake -DCMAKE_BUILD_TYPE=Release -DQPL_LIBRARY_TYPE=STATIC -DQPL_BUILD_TESTS=OFF .. >/dev/null 2>&1 && make -j"$(nproc)" >/dev/null 2>&1 \
    && sudo make install >/dev/null 2>&1 && log "QPL built + installed" || { log "QPL build FAILED"; tail -20 CMakeFiles/CMakeError.log 2>/dev/null; }
fi
QPL_INC=$(dirname "$(find /usr/local -name qpl.h 2>/dev/null | head -1)" 2>/dev/null)
QPL_LIB=$(dirname "$(find /usr/local -name 'libqpl.*' 2>/dev/null | head -1)" 2>/dev/null)

# ── Build the multi-engine bench ──
log "building iaa_bench_mt"
g++ -O3 -std=c++17 "$WORK/iaa_bench_mt.cpp" -o "$WORK/iaa_mt" \
    -I"${QPL_INC:-/usr/local/include}/.." -I"${QPL_INC:-/usr/local/include}" \
    -L"${QPL_LIB:-/usr/local/lib}" -lqpl -lpthread -ldl 2>&1 | tail -5 \
    && log "iaa_mt built" || { log "bench build FAILED"; exit 3; }

# ── Run the IAA aggregate sweep: every column x thread counts (run as the iaa user) ──
COLS_DIR="$WORK/cols"
RES="$HOME/iaa_mt_RESULTS.txt"
{
  echo "# Multi-engine IAA hardware-Deflate decode -- GCP c3-standard-192-metal (Sapphire, $NIAX IAA engines)"
  echo "# $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs); $(nproc) vCPU; intel_iommu=$(grep -o 'intel_iommu=[^ ]*' /proc/cmdline)"
  echo "# Shared WQ per device (8x128), block_on_fault=1, run AS ROOT, mlock'd buffers; aggregate GB/s vs thread count."
  echo "# col  threads  ratio  IAA-GB/s  verify"
} > "$RES"
for col in "$COLS_DIR"/*.bin; do
  [ -f "$col" ] || continue
  for T in 1 2 4 8 16 32 64 96; do
    line=$(sudo env LD_LIBRARY_PATH="${QPL_LIB:-/usr/local/lib}" "$WORK/iaa_mt" "$col" "$T" 256 2>/dev/null)
    echo "$line" | tee -a "$RES"
  done
done
log "IAA sweep done -> $RES"
cat "$RES"
