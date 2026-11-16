# Module 02 Research Comparator

Compare one supplied research-paper batch with the supplied review future-trend statements.

For every paper return exactly one category and use the normalized TrendClaim ids from `trend-claims.schema.json`:

- trend_consistent;
- trend_extension;
- new_direction;
- review_candidate: the record is actually a review, survey, systematic review, or review-like synthesis missed by review discovery; it must be moved back into review screening and must not be compared as original research;
- excluded.

For trend_consistent or trend_extension, identify at least one `matched_trend_claim_id`, its source review, and the corresponding statement. For new_direction, return no matched TrendClaim and explain what is new relative to every supplied review. For review_candidate, return no matched review or TrendClaim ids and state the title/abstract evidence showing that the work synthesizes prior research rather than reporting original research. Base the judgment on supplied evidence; do not use model memory.
