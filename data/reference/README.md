# Reference data

Nature Index membership is no longer fetched at runtime. The active directory is bundled with the Module 01 Skill at:

`.dsh/skills/research-topic-evaluation/nature-index-publications.tsv`

It contains the 177 publication venues copied from Nature Index FAQ item 18 on 2026-11-03. The Python core validates the row count, hashes the file, and attaches the resulting immutable snapshot to each Module 01 run. Module 02 reuses that snapshot.

The CSV file in this directory is retained only as an inactive historical template and must not be used by the workflow.
