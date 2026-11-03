// DeepSeek Harness Workflow 1 for Module 02: review analysis and TrendClaim normalization.
// args.reviewBatchFiles are bounded project paths produced by export-review-batches.

phase('Analyze topic-specific review batches')
const reviewAnalyses = await parallel(
  args.reviewBatchFiles.map(path => () => agent(
    `Read ${path} and prompts/module02-review-analyzer.md. Analyze only supplied records and return JSON matching schemas/review-analysis.schema.json. Do not ask the user questions.`
  ))
)

phase('Normalize review future trends')
const trendClaims = await agent(
  `Normalize equivalent future-trend statements in the following review analyses into schemas/trend-claims.schema.json. Preserve source review ids and source statements. Use no model-memory claims. Analyses: ${JSON.stringify(reviewAnalyses)}`
)

return {
  module02RunId: args.module02RunId,
  reviewAnalyses,
  trendClaims,
}
