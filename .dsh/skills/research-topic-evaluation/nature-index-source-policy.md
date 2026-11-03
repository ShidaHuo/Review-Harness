# Nature Index local-directory policy

## Authoritative source for this Harness version

Do not fetch or scrape the Nature website during Module 01 or Module 02. Read the bundled, user-supplied directory:

`nature-index-publications.tsv`

The file records the publication list copied from Nature Index FAQ item 18 on 2026-11-03, its official source URL, the stated total of 177 journals and conference proceedings, current-window article counts, and the January 2026 *Monthly Notices* Letters restriction.

The Python core must parse the file, verify that it has exactly 177 publication rows, compute its SHA-256, and attach one immutable snapshot to every Module 01 run. Module 02 reuses that snapshot.

## Matching

Match journal names after Unicode normalization, case folding, punctuation normalization, and treating `&` as `and`. Do not use OpenAlex or Crossref to decide Nature Index membership. ISSNs may later enrich matching but cannot override the local directory.

The January 2026 *Monthly Notices of the Royal Astronomical Society* entry is section-restricted: only Letters qualify. More generally, the local note states that some journals contribute only selected article sections. Report venue-directory membership, not a claim that every paper in the venue is counted by Nature Index.

## Metric definition

`Nature Index 期刊论文占比` means:

- numerator: semantically included primary journal articles whose journal matches the bundled directory;
- denominator: semantically included primary journal articles with an identifiable journal;
- exclusions: reviews, conference papers, editorials, commentaries, preprints, and records without an identifiable journal.

Report numerator, denominator, percentage, snapshot edition/date, and any unresolved journal-name matches.

## Failure behavior

If the local file is missing, malformed, does not contain 177 rows, or cannot be attached, report `暂无法核验` and stop Nature Index computation. Do not fall back to web retrieval or model memory.
