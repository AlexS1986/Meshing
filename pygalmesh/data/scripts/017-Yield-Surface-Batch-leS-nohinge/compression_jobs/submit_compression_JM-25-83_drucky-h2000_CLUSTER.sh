#!/usr/bin/env bash
# erzeugt von setup_compression_jobs.py - 1D-Druckversuch Studie 017
# Aufruf auf dem Login-Node nach dem Sync nach $HPC_SCRATCH:
#   DRY_RUN=1 .../compression_jobs/submit_compression_CLUSTER.sh   # nur anzeigen
#   .../compression_jobs/submit_compression_CLUSTER.sh
set -euo pipefail
P="$HPC_SCRATCH/pygalmesh/data/scripts/017-Yield-Surface-Batch-leS-nohinge"
DRY="${DRY_RUN:-0}"
ACC="${JOB_ACCOUNT:-p0023647}"
sb() { if [[ "$DRY" == 1 ]]; then echo "[dry-run] sbatch $*" >&2; echo 000000; else sbatch --parsable "$@" | sed "s/;.*//" | grep -E "^[0-9]+$" | tail -n 1; fi; }

# 1) Netz mit Schale nur in y (JM-25-83_les_r4_drucky); uebersprungen, wenn dlfx_mesh.xdmf schon da ist
SUBVOL="/data/scripts/017-Yield-Surface-Batch-leS-nohinge/JM-25-83_les_r4_drucky_segmented/JM-25-83_les_r4_drucky_segmented_3D"; SUBVOL="${SUBVOL/#\/data/$HPC_SCRATCH/pygalmesh/data}"
PREP=""
if compgen -G "$SUBVOL/subvolume_x*_y*/dlfx_mesh.xdmf" > /dev/null; then echo "Netz vorhanden: $SUBVOL"; else
  PREP="$(sb -A "$ACC" --time="${PREP_JOB_TIME:-120}" -J prep-JM-25-83-drucky "$P/job_prepare_mesh_CLUSTER.sh" config-JM-25-83-r4-drucky-sigy100h2000.json)"
  echo "Netzvorbereitung: Job $PREP"
fi

# 2) JM-25-83_drucky_sigy100h2000: Kette aus 3 Gliedern (Exit 3 = Zeitlimit -> naechstes Glied setzt fort)
J="$P/compression_jobs/JM-25-83_drucky_sigy100h2000/ys_druck_y/job_ys_druck_y_CLUSTER.sh"; L="$P/compression_jobs/JM-25-83_drucky_sigy100h2000/ys_druck_y"
DEP=(); [[ -n "$PREP" ]] && DEP=(--dependency="afterok:$PREP" --kill-on-invalid-dep=yes)
PREV="$(sb -A "$ACC" "${DEP[@]}" --error="$L/%x.err.%j" --output="$L/%x.out.%j" "$J")"
echo "JM-25-83_drucky_sigy100h2000: Glied 1 = $PREV"
for i in $(seq 2 3); do
  D="afternotok:$PREV"; [[ -n "$PREP" ]] && D="afterok:$PREP,$D"
  PREV="$(sb -A "$ACC" --dependency="$D" --kill-on-invalid-dep=yes --error="$L/%x.err.%j" --output="$L/%x.out.%j" "$J")"
  echo "JM-25-83_drucky_sigy100h2000: Glied $i = $PREV"
done

echo "Status: squeue -u $USER   Logs: $P/compression_jobs/*/*/"
