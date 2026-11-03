# Module 02 Review Screener

Use only title, abstract, publication type, and the frozen TopicProfile. Screen every retrieved candidate in one complete pass.

For every candidate return:

- `review_id`;
- `match_level`:
  - `exact`: the complete user topic is a central review subject;
  - `adjacent`: the review is not exact, but centrally covers one or more important topic concepts and can provide a useful comparison baseline;
  - `excluded`: incidental mention, wrong technical object, or not a review;
- `relevance_score`: 0–1 semantic relevance to the complete topic;
- `matched_keywords`: the important topic concepts that justify an `adjacent` result;
- `confidence`: low, medium, or high;
- `reason`: one evidence-based sentence.

Selection is deterministic after screening:

1. if one or more `exact` reviews exist, include all exact reviews and exclude adjacent reviews from PDF/trend analysis;
2. if no exact review exists, include at most the five highest-scoring `adjacent` reviews;
3. break equal scores by citation count, publication date, then stable record id.

Do not fetch or read PDFs during screening. Do not inflate relevance merely because a candidate contains generic words such as “device”, “materials”, or “review”.
