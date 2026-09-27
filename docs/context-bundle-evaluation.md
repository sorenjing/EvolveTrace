# Evaluating ContextBundle against ordinary repository search

Use a real, reviewable task that needs facts from at least two repositories. Record the task, repository commits, tool versions, time budget, authoritative source paths, and acceptance commands **before** either run. Keep private task details outside this repository.

Run two attempts against the same immutable code versions:

1. Ordinary search: use the usual file listing and text search tools.
2. ContextBundle: export the task's bundle, inspect `freshness`, source IDs, scope, and digests, then use ordinary tools to check any missing or stale facts.

For each attempt, record elapsed time, context bytes, authoritative sources found, incorrect or missed facts, acceptance command results, and reviewer corrections. A bundle is evidence of delivered context, not proof that an agent read or understood it. Mark stale bundles as stale; do not count generated context as current source coverage without checking the source revision.

Compare source coverage and acceptance outcomes first. Treat elapsed time from one person repeating the same task as descriptive only: the second attempt benefits from learning. Use independent operators or counterbalanced tasks before making a causal efficiency claim. Do not publish an improvement percentage without a reliable comparison. Publish only generic methodology and synthetic examples here; retain specific private task records in a private workspace.
