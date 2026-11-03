# Lightweight research-paper search rules

## Publication window

Every query uses the rolling two-year window ending on the current system date. No publication outside the window contributes to Module 01.

## Dynamic topic levels

- `direct`: original research on the user's complete topic.
- `technical`: original research on the nearest coherent parent technology after removing the principal restrictive qualifier.
- `excluded`: records that fail the boundary or are not original research.

Example: for “紫外微型计算光谱仪”, `direct` means “紫外微型计算光谱仪研究论文” and `technical` means “微型计算光谱仪研究论文”.

## Research-work filter

Retain original research articles, research preprints, and original conference research papers. Exclude reviews, surveys, perspectives, editorials, commentaries, news, book chapters, reference entries, peer reviews, and paratext.

## Search budget

| Internal scope | Maximum queries | Maximum records/query |
|---|---:|---:|
| direct | 3 | 50 |
| technical | 3 | 50 |
| Total | 6 | 300 |

Use one page per query. There is no review query and no foundational query.

Prefer precise title-and-abstract concept intersections. Do not use broad parent-field terms that swamp the requested topic. If OpenAlex fails or rate-limits a query, report incomplete evidence and stop without provider substitution.

## Deduplication

1. normalized DOI;
2. provider identifier;
3. normalized title and publication year.

Do not silently merge fuzzy title candidates.

## Stop conditions

Stop when all six allowed queries finish, 300 candidates are reached, the provider blocks further requests, or enough evidence exists to populate the short report.
