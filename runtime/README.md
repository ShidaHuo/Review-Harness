# Runtime data

This directory contains local, reproducible run state.

Generated files are ignored by Git:

- `research.sqlite3`: workflow state and normalized metadata;
- `raw/<run_id>/`: immutable API response pages and query manifests.

Do not place API keys or copyrighted full text in the database. Source PDFs will use a separate access-controlled project store in a later module.
