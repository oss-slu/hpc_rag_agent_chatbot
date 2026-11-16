<!-- Source: https://example.edu/how-to/submit-job/ | Retrieved: 2026-09-30T12:00:00Z -->
Skip to content
# Submit a Job

Jobs run through the scheduler. Write a script, then submit it.

## Batch jobs

A batch job runs without you watching it.

### GPU jobs

Ask for a GPU in your script.

```bash
#!/bin/bash
#SBATCH --gpus=1

## this line is a comment inside the code block, not a heading
python train.py
```

#### Tips

Keep your script short.

## Interactive jobs

Use an interactive job to test things.

[Previous: Connect](https://example.edu/how-to/connect/)
[Next: Storage](https://example.edu/how-to/storage/)
Back to top
Made with Material for MkDocs
