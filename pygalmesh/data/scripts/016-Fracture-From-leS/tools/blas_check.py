#!/usr/bin/env python3
# BLAS-Selbsttest (aus 015, scratch/mumps_sanity/blas_check.py, 05.09.2026).
# Kriterium sind NUR die dgemm/dgesv-Zeilen. Auf i02 ohne OPENBLAS_CORETYPE=SkylakeX:
# core Cooperlake, dgemm ~22 (falsch). Mit Fix: core SkylakeX, dgemm/dgesv ~1e-13.
# Aufruf (Apptainer bindet nur cwd, /home, /data -> Container-Pfad benutzen!):
#   sbatch -A p0023647 -p deflt -C i02 -n 1 --mem-per-cpu=8000 -t 10 -J blas-mit \
#     --export=ALL,OPENBLAS_CORETYPE=SkylakeX,APPTAINERENV_OPENBLAS_CORETYPE=SkylakeX \
#     --wrap "apptainer exec --bind $HPC_SCRATCH/pygalmesh/data:/data $HOME/dolfinx_alex/alex-dolfinx.sif \
#             python3 /data/scripts/016-Fracture-From-leS/tools/blas_check.py"
#   (ohne Fix: --export=NONE und die beiden Variablen weglassen)
import numpy as np, ctypes, os
try:
    lib = ctypes.CDLL("libopenblas.so.0"); lib.openblas_get_config.restype = ctypes.c_char_p; lib.openblas_get_corename.restype = ctypes.c_char_p
    print("OpenBLAS:", lib.openblas_get_config().decode(), "| core:", lib.openblas_get_corename().decode(), "| OPENBLAS_CORETYPE=", os.environ.get("OPENBLAS_CORETYPE"))
except Exception as e: print("openblas info:", e)
rng = np.random.default_rng(0); A = rng.random((600, 600)); B = rng.random((600, 600))
ref = np.einsum("ij,jk->ik", A, B); print("dgemm max|A@B - einsum| =", np.abs(A @ B - ref).max(), "(erwartet ~1e-12)")
x = rng.random(600); print("dgesv max|A x - b| =", np.abs(A @ np.linalg.solve(A, A @ x) - A @ x).max(), "(erwartet ~1e-10)")
