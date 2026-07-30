#!/bin/bash

#SBATCH -J fracture-sim-b4-r2-coarse
#SBATCH -A p0023647
#SBATCH -t 10080
#SBATCH --mem-per-cpu=4000
#SBATCH -n 96
#SBATCH -N 1
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/012-Fracture-Mesh-Sim-Split/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/012-Fracture-Mesh-Sim-Split/%x.out.%j
#SBATCH --mail-type=END
#SBATCH -C i01

# Convenience wrapper: runs the fracture simulation against the archived
# Bin4 reduce-2 coarse mesh (max_element_size_factor=3.0,
# max_facet_distance_factor=1.0) -- the pre-existing baseline config, not a
# separately generated duplicate. Requires
# job_generate_mesh_Bin4_reduce_2_CLUSTER.sh (array index 0 /
# config-Bin4-reduce-2-cluster-coarse.json) to have completed first, or
# job_generate_mesh_CLUSTER.sh run directly with the same config.

SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/012-Fracture-Mesh-Sim-Split"
SRUN_MEM_PER_CPU=4000 \
  bash "$SCRIPT_DIR/job_run_simulation_CLUSTER.sh" config-Bin4-reduce-2-cluster-coarse.json
