#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_PATH="${CONFIG_PATH:-$SCRIPT_DIR/config-Bin4-reduce-2.json}" "$SCRIPT_DIR/job_yield_surface_LOCAL.sh"
