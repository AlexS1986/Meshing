#!/usr/bin/env bash
# erzeugt von setup_compression_jobs.py - 1D-Druckversuch Studie 017
# Aufruf auf dem Login-Node nach dem Sync nach $HPC_SCRATCH:
#   DRY_RUN=1 .../compression_jobs/submit_compression_CLUSTER.sh   # nur anzeigen
#   .../compression_jobs/submit_compression_CLUSTER.sh
set -euo pipefail
P="$HPC_SCRATCH/pygalmesh/data/scripts/017-Yield-Surface-Batch-leS-nohinge"
DRY="${DRY_RUN:-0}"
ACC="${JOB_ACCOUNT:-p0023647}"
sb() { if [[ "$DRY" == 1 ]]; then echo "[dry-run] sbatch $*"; echo 000000; else sbatch --parsable "$@" | sed "s/;.*//" | grep -E "^[0-9]+$" | tail -n 1; fi; }

# 1) Netz mit Schale nur in x (JM-25-71_les_r4_druckx); uebersprungen, wenn dlfx_mesh.xdmf schon da ist
SUBVOL="/data/scripts/017-Yield-Surface-Batch-leS-nohinge/JM-25-71_les_r4_druckx_segmented/JM-25-71_les_r4_druckx_segmented_3D"; SUBVOL="${SUBVOL/#\/data/$HPC_SCRATCH/pygalmesh/data}"
PREP=""
if compgen -G "$SUBVOL/subvolume_x*_y*/dlfx_mesh.xdmf" > /dev/null; then echo "Netz vorhanden: $SUBVOL"; else
  PREP="$(sb -A "$ACC" --time="${PREP_JOB_TIME:-120}" -J prep-JM-25-71-druckx "$P/job_prepare_mesh_CLUSTER.sh" config-JM-25-71-r4-druckx-sigy075.json)"
  echo "Netzvorbereitung: Job $PREP"
fi

# 2) JM-25-71_druckx_sigy075: Kette aus 3 Gliedern (Exit 3 = Zeitlimit -> naechstes Glied setzt fort)
J="$P/compression_jobs/JM-25-71_druckx_sigy075/ys_druck_x/job_ys_druck_x_CLUSTER.sh"; L="$P/compression_jobs/JM-25-71_druckx_sigy075/ys_druck_x"
DEP=(); [[ -n "$PREP" ]] && DEP=(--dependency="afterok:$PREP" --kill-on-invalid-dep=yes)
PREV="$(sb -A "$ACC" "${DEP[@]}" --error="$L/%x.err.%j" --output="$L/%x.out.%j" "$J")"
echo "JM-25-71_druckx_sigy075: Glied 1 = $PREV"
for i in $(seq 2 3); do
  D="afternotok:$PREV"; [[ -n "$PREP" ]] && D="afterok:$PREP,$D"
  PREV="$(sb -A "$ACC" --dependency="$D" --kill-on-invalid-dep=yes --error="$L/%x.err.%j" --output="$L/%x.out.%j" "$J")"
  echo "JM-25-71_druckx_sigy075: Glied $i = $PREV"
done

# 2) JM-25-71_druckx_sigy180: Kette aus 3 Gliedern (Exit 3 = Zeitlimit -> naechstes Glied setzt fort)
J="$P/compression_jobs/JM-25-71_druckx_sigy180/ys_druck_x/job_ys_druck_x_CLUSTER.sh"; L="$P/compression_jobs/JM-25-71_druckx_sigy180/ys_druck_x"
DEP=(); [[ -n "$PREP" ]] && DEP=(--dependency="afterok:$PREP" --kill-on-invalid-dep=yes)
PREV="$(sb -A "$ACC" "${DEP[@]}" --error="$L/%x.err.%j" --output="$L/%x.out.%j" "$J")"
echo "JM-25-71_druckx_sigy180: Glied 1 = $PREV"
for i in $(seq 2 3); do
  D="afternotok:$PREV"; [[ -n "$PREP" ]] && D="afterok:$PREP,$D"
  PREV="$(sb -A "$ACC" --dependency="$D" --kill-on-invalid-dep=yes --error="$L/%x.err.%j" --output="$L/%x.out.%j" "$J")"
  echo "JM-25-71_druckx_sigy180: Glied $i = $PREV"
done

# 2) JM-25-71_druckx_sigy100: Kette aus 3 Gliedern (Exit 3 = Zeitlimit -> naechstes Glied setzt fort)
J="$P/compression_jobs/JM-25-71_druckx_sigy100/ys_druck_x/job_ys_druck_x_CLUSTER.sh"; L="$P/compression_jobs/JM-25-71_druckx_sigy100/ys_druck_x"
DEP=(); [[ -n "$PREP" ]] && DEP=(--dependency="afterok:$PREP" --kill-on-invalid-dep=yes)
PREV="$(sb -A "$ACC" "${DEP[@]}" --error="$L/%x.err.%j" --output="$L/%x.out.%j" "$J")"
echo "JM-25-71_druckx_sigy100: Glied 1 = $PREV"
for i in $(seq 2 3); do
  D="afternotok:$PREV"; [[ -n "$PREP" ]] && D="afterok:$PREP,$D"
  PREV="$(sb -A "$ACC" --dependency="$D" --kill-on-invalid-dep=yes --error="$L/%x.err.%j" --output="$L/%x.out.%j" "$J")"
  echo "JM-25-71_druckx_sigy100: Glied $i = $PREV"
done

echo "Status: squeue -u $USER   Logs: $P/compression_jobs/*/*/"
