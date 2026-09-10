#!/usr/bin/env bash
# iaa_drive.sh -- laptop-side driver for the IAA aggregate run on GCP c3-standard-192-metal.
#
# The harness run-job.sh can't do this flow: the IAA setup needs a mid-run REBOOT (to bring
# up intel_iommu=on,sm_on), but run-job.sh tears the box down in its EXIT trap. So this driver
# owns the box lifecycle directly: create -> stage -> phase1 (reboot) -> wait -> phase2 -> collect
# -> delete, with a GUARANTEED teardown trap AND a GCP-side --max-run-duration=DELETE backstop
# (so the box dies even if this laptop process is killed). Name+zone scoped: only ever touches
# the one box this run launches.
set -uo pipefail

PROJECT="${PROJECT:?set PROJECT to your own GCP project}"
ZONE=us-central1-a
MACHINE=c3-standard-192-metal
IMG_FAMILY=ubuntu-2404-lts-amd64
IMG_PROJECT=ubuntu-os-cloud
DISK_TYPE=hyperdisk-balanced
DISK_GB=200
MAXRUN=5400s                                   # 90 min hard cap -> auto DELETE backstop
NAME="iaa-bench-$(date +%s)-$$"
KEY="$HOME/.ssh/id_ed25519"
USER_=ubuntu
HERE="$(cd "$(dirname "$0")" && pwd)"
COLS_DIR="$HOME/data/onpair-cpu-cols"
OUT="$HERE/iaa_mt_RESULTS.txt"
SSHO=(-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=10)
log(){ printf '\n\033[1;36m[drive %s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }

gone=0
terminate(){ [ "$gone" = 1 ] && return; gone=1; log "TEARDOWN: deleting $NAME"; \
  gcloud auth print-access-token >/dev/null 2>&1 || true; \
  gcloud compute instances delete "$NAME" --project "$PROJECT" --zone "$ZONE" --quiet 2>&1 | tail -2; }
trap terminate EXIT INT TERM

ip_of(){ gcloud compute instances describe "$NAME" --project "$PROJECT" --zone "$ZONE" \
  --format='value(networkInterfaces[0].accessConfigs[0].natIP)' 2>/dev/null; }
rsh(){ ssh -i "$KEY" "${SSHO[@]}" "$USER_@$IP" "$@"; }

# ── auth check ──
tok=$(gcloud auth print-access-token 2>/dev/null)
[ "${#tok}" -gt 50 ] || { log "GCP auth FAILED -- run 'gcloud auth login'"; exit 1; }

# ── create (metal needs maintenance=TERMINATE; backstop = max-run-duration + DELETE) ──
log "creating $NAME ($MACHINE, $ZONE)"
gcloud compute instances create "$NAME" \
  --project "$PROJECT" --zone "$ZONE" --machine-type "$MACHINE" \
  --image-family "$IMG_FAMILY" --image-project "$IMG_PROJECT" \
  --boot-disk-size "${DISK_GB}GB" --boot-disk-type "$DISK_TYPE" --boot-disk-auto-delete \
  --maintenance-policy=TERMINATE \
  --max-run-duration="$MAXRUN" --instance-termination-action=DELETE \
  --metadata "enable-oslogin=FALSE,ssh-keys=${USER_}:$(cat "$KEY.pub")" \
  --format='value(name)' 2>&1 | tail -3 || { log "CREATE FAILED"; exit 2; }

IP=$(ip_of); log "IP=$IP"
[ -n "$IP" ] || { log "no IP"; exit 2; }

# ── wait for first-boot SSH ──
log "waiting for ssh"
for i in $(seq 1 40); do rsh true 2>/dev/null && { log "ssh up (try $i)"; break; }; sleep 10; \
  [ "$i" = 40 ] && { log "ssh never came up"; exit 3; }; done

# ── stage: setup script + bench source -> ~/iaa, col files -> ~/iaa/cols ──
log "staging artifacts (~615MB of columns -- this is the slow step)"
rsh 'mkdir -p ~/iaa/cols'
scp -i "$KEY" "${SSHO[@]}" "$HERE/iaa_mt_setup_run.sh" "$HERE/iaa_bench_mt.cpp" "$USER_@$IP:~/iaa/" 2>&1 | tail -1
scp -i "$KEY" "${SSHO[@]}" "$HERE/iaa_mt_setup_run.sh" "$USER_@$IP:~/" 2>&1 | tail -1
scp -i "$KEY" "${SSHO[@]}" "$COLS_DIR"/*.bin "$USER_@$IP:~/iaa/cols/" 2>&1 | tail -1
log "staged: $(rsh 'ls ~/iaa/cols | wc -l') columns"

# ── phase 1: enable IOMMU + reboot (ssh drops; expected) ──
log "PHASE 1 (enable intel_iommu + reboot)"
rsh 'bash ~/iaa_mt_setup_run.sh' 2>&1 | tail -8 || true

# ── wait for reboot + intel_iommu live ──
log "waiting for reboot"
sleep 30
for i in $(seq 1 40); do
  if rsh 'grep -q intel_iommu=on /proc/cmdline' 2>/dev/null; then log "back, intel_iommu live (try $i)"; break; fi
  sleep 10; [ "$i" = 40 ] && { log "reboot/iommu never came up"; exit 4; }
done

# ── phase 2: configure engines, build QPL+bench, run sweep ──
log "PHASE 2 (configure + build + sweep) -- this runs the full column x thread sweep"
rsh 'bash ~/iaa_mt_setup_run.sh' 2>&1 | tail -60

# ── collect ──
log "collecting results"
scp -i "$KEY" "${SSHO[@]}" "$USER_@$IP:~/iaa_mt_RESULTS.txt" "$OUT" 2>&1 | tail -1 && {
  log "RESULTS -> $OUT"; echo "================ iaa_mt_RESULTS.txt ================"; cat "$OUT"; }

log "DONE -- teardown follows"
