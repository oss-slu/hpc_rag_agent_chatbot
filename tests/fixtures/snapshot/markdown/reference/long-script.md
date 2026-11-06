<!-- Source: https://example.edu/reference/long-script/ | Retrieved: 2026-09-30T12:00:00Z -->
# Long Script

This page has one job script that is longer than a whole chunk.

```bash
#!/bin/bash
#SBATCH --job-name=example-pipeline
#SBATCH --partition=example
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=student@example.edu

# Stop on the first error, an unset variable, or a failed pipe.
set -euo pipefail

# ---------------------------------------------------------------
# Settings
# ---------------------------------------------------------------
PROJECT_DIR="/project/example-lab/pipeline"
INPUT_DIR="$PROJECT_DIR/input"
OUTPUT_DIR="$PROJECT_DIR/output/$SLURM_JOB_ID"
SCRATCH_DIR="/scratch/$USER/$SLURM_JOB_ID"
SAMPLES=(sample_a sample_b sample_c sample_d sample_e sample_f)
THREADS="${SLURM_CPUS_PER_TASK:-1}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

fail() {
    log "ERROR: $*"
    exit 1
}

# ---------------------------------------------------------------
# Environment
# ---------------------------------------------------------------
log "Job $SLURM_JOB_ID starting on $(hostname)"
module purge
module load example-python/3.12
module load example-tools/2.4

python -m venv "$SCRATCH_DIR/venv"
source "$SCRATCH_DIR/venv/bin/activate"
pip install --quiet --requirement "$PROJECT_DIR/requirements.txt"

mkdir -p "$OUTPUT_DIR" "$SCRATCH_DIR/work" logs

# ---------------------------------------------------------------
# Check inputs before doing any work
# ---------------------------------------------------------------
for sample in "${SAMPLES[@]}"; do
    if [[ ! -f "$INPUT_DIR/$sample.csv" ]]; then
        fail "missing input file for $sample"
    fi
done
log "All ${#SAMPLES[@]} input files found"

# ---------------------------------------------------------------
# Main loop: clean, analyze, and summarize each sample
# ---------------------------------------------------------------
for sample in "${SAMPLES[@]}"; do
    log "Processing $sample"
    work="$SCRATCH_DIR/work/$sample"
    mkdir -p "$work"

    cp "$INPUT_DIR/$sample.csv" "$work/raw.csv"

    python "$PROJECT_DIR/scripts/clean.py" \
        --input "$work/raw.csv" \
        --output "$work/clean.csv" \
        --drop-empty-rows \
        || fail "cleaning failed for $sample"

    python "$PROJECT_DIR/scripts/analyze.py" \
        --input "$work/clean.csv" \
        --output "$work/results.json" \
        --threads "$THREADS" \
        || fail "analysis failed for $sample"

    python "$PROJECT_DIR/scripts/summarize.py" \
        --input "$work/results.json" \
        --output "$OUTPUT_DIR/$sample-summary.txt" \
        || fail "summary failed for $sample"

    log "Finished $sample"
done

# ---------------------------------------------------------------
# Combine the summaries into one report
# ---------------------------------------------------------------
report="$OUTPUT_DIR/report.txt"
{
    echo "Pipeline report for job $SLURM_JOB_ID"
    echo "Samples: ${SAMPLES[*]}"
    echo
    for sample in "${SAMPLES[@]}"; do
        echo "== $sample =="
        cat "$OUTPUT_DIR/$sample-summary.txt"
        echo
    done
} > "$report"
log "Report written to $report"

# ---------------------------------------------------------------
# Clean up scratch space and record what the job used
# ---------------------------------------------------------------
deactivate
rm -rf "$SCRATCH_DIR"
sacct --jobs "$SLURM_JOB_ID" --format=JobID,Elapsed,MaxRSS,State
log "pipeline finished"
```

The end.
