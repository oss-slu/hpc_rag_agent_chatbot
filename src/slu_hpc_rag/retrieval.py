"""Search over the documentation index.

STUB: returns made-up chunks so the agent and UI can be built before the
real index exists. #12 replaces the body with hybrid vector + full-text
search; the signature and return type stay the same.
"""

from slu_hpc_rag.contracts import Chunk

_FAKE_CHUNKS = (
    Chunk(
        url="https://example.edu/how-to/batch-jobs/",
        title="Batch jobs (example)",
        heading="Batch jobs (example) > Submitting a job",
        source="libra",
        body="Made-up text: write a job script and submit it with `sbatch job.sh`.",
        score=0.92,
    ),
    Chunk(
        url="https://example.edu/how-to/monitor-jobs/",
        title="Monitoring jobs (example)",
        heading="Monitoring jobs (example)",
        source="libra",
        body="Made-up text: `squeue --me` lists your queued and running jobs.",
        score=0.81,
    ),
    Chunk(
        url="https://example.edu/slurm/sbatch/",
        title="sbatch (example)",
        heading="sbatch (example) > Options",
        source="slurm",
        body="Made-up text: `--time` sets the job's wall-clock limit.",
        score=0.64,
    ),
)


def search(query: str, k: int = 8) -> list[Chunk]:
    """The ``k`` chunks most relevant to ``query``, best first."""
    return list(_FAKE_CHUNKS[:k])
