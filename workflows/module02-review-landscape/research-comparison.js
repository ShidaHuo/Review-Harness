// DeepSeek Harness Workflow 2 for Module 02: batched research-to-TrendClaim comparison.
// Run only after review analyses, TrendClaims, anchors, query planning and gap-only retrieval are persisted.

phase('Compare post-review research batches')
const researchComparisons = await parallel(
  args.researchBatchFiles.map(path => () => agent(
    `Read ${path}, the persisted TrendClaims, and prompts/module02-research-comparator.md. Return JSON matching schemas/research-trend-comparison.schema.json. Do not ask the user questions.`
  ))
)

return {
  module02RunId: args.module02RunId,
  researchComparisons,
}
