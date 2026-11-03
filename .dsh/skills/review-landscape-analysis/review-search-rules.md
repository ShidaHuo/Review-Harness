# Module 02 review search rules

## Inclusion strategy

Use a two-level strategy:

1. **Exact-topic reviews** (`exact`): the complete user topic is a central review subject.
2. **Adjacent-topic reviews** (`adjacent`): no exact review exists, but the review centrally covers important technical objects, mechanisms, materials, device classes, methods, or applications from the frozen TopicProfile.

If at least one exact-topic review exists, include exact reviews and do not substitute broader reviews. If none exists, explicitly state that no review anchors all core topic keywords, then include all highest-scoring eligible adjacent reviews up to five. Every adjacent review must name the matched important keywords, be labeled as adjacent evidence, and continue through the complete Module 02 pipeline rather than stopping after screening. Incidental mentions and generic parent-field reviews remain excluded. Enter `no_related_reviews` only when both exact and eligible adjacent sets are empty.

## Dual-channel discovery

OpenAlex publication type is a hint, not an inclusion rule. The Python core deterministically derives up to four review queries from the first two frozen direct-topic queries:

1. up to two typed queries that send `type:review`;
2. up to two untyped review-intent queries formed by adding `review` when no review-intent term is present.

`module02-next` returns the required ids. Run `search-reviews --query-id <id>` only. Agents must not provide, edit, calibrate, broaden, or narrow review query strings.

Screen all candidates together with `review-screening.schema.json`. The Python core selects exact reviews or, only when exact reviews are absent, the top five adjacent reviews. Ranking is by semantic relevance score, then citation count, publication date, and stable record id.

## Retrieval and metadata

- Provider: OpenAlex for discovery and citation snapshots.
- Pagination: up to 10 pages of 100 records per query.
- Ranking: semantic relevance controls fallback selection.
- Deduplication: DOI, OpenAlex ID, then normalized title plus year.
- Citation count: record `citation_as_of`; counts change over time.
- Link priority: DOI URL, public publisher/repository landing page, then OpenAlex URL.
- Nature Index: reuse the Module 01 bundled local snapshot.
- Full-text analysis: only after selection; follow `fulltext-access.md`.
