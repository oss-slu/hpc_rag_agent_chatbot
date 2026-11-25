"""Check a SLURM job script for common mistakes.

STUB: finds nothing yet. The real checker compares the script's #SBATCH
options with the cluster's partitions; the signature stays the same.
"""

from slu_hpc_rag.contracts import Finding


def check_script(text: str) -> list[Finding]:
    """Problems found in the job script ``text``, in line order."""
    return []
