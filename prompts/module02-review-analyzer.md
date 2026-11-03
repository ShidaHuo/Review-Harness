# Module 02 Review Analyzer

Analyze only the supplied review record. Use accessible full text when available.

Return:

- review_id;
- review_match_level: exact or adjacent, copied from the persisted screening result;
- nature_index_status: yes, no, or unverified, using the bundled Module 01 Nature Index snapshot;
- evidence_level: full_text, abstract_only, or metadata_only;
- fulltext_access_status supplied by the deterministic access stage;
- review_reason;
- structure: ordered section/theme list;
- future_trends: discrete claims actually made by the review;
- source_urls;
- limitations.

Do not infer structure or future trends from title metadata. If full text is unavailable, return empty arrays where evidence is insufficient.
