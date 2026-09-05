#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/config.sh"
POINTS="${1:-${YIELD_SURFACE_POINTS:-6}}"
RADIUS="${YIELD_SURFACE_STRAIN_RADIUS:-0.25}"
BASE_CONFIG="${YIELD_SURFACE_BASE_CONFIG:-config-A01-les.json}"
SETUP_ARGS=(
  --points "$POINTS"
  --radius "$RADIUS"
  --base-config "$BASE_CONFIG"
)
if [[ -n "${YIELD_SURFACE_OUTPUT_DIR:-}" ]]; then
  SETUP_ARGS+=(--output-dir "$YIELD_SURFACE_OUTPUT_DIR")
fi
SETUP_ARGS+=(
  --job-ntasks "${YIELD_JOB_NTASKS:-96}"
  --job-nodes "${YIELD_JOB_NODES:-0}"
  --job-mem-per-cpu "${YIELD_JOB_MEM_PER_CPU:-9000}"
  --job-constraint "${YIELD_JOB_CONSTRAINT-}"
  --job-time "${YIELD_JOB_TIME:-10080}"
  --job-partition "${YIELD_JOB_PARTITION:-}"
  --job-account "${JOB_ACCOUNT:-l0003507}"
)

if [[ -n "${YIELD_JOB_NAME_PREFIX:-}" ]]; then
  SETUP_ARGS+=(--job-name-prefix "$YIELD_JOB_NAME_PREFIX")
fi
if [[ -n "${YIELD_JOB_SCRATCH_ROOT:-}" ]]; then
  SETUP_ARGS+=(--scratch-root "$YIELD_JOB_SCRATCH_ROOT")
fi
python3 "$SCRIPT_DIR/setup_yield_surface_jobs.py" "${SETUP_ARGS[@]}"
