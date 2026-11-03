import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'review-perspective-branches'
export const inject = ['tools', 'sessionController']

function boundedTitle(rank, title) {
  const value = `Module 03 · 视角${rank} · ${title}`
  return Array.from(value).slice(0, 36).join('')
}

export function apply(ctx) {
  ctx.tools.register(defineTool({
    name: 'create_review_perspective_branches',
    description: 'Create real persistent DeepSeek Harness Session forks for saved Module 02 perspectives. Existing mapped sessions are reused. No prompt is sent and Module 03 is not started.',
    parameters: {
      module02_run_id: {
        type: 'string',
        required: true,
        description: 'Persisted Module 02 run id whose perspectives are ready.',
      },
      perspectives: {
        type: 'array',
        required: true,
        description: 'The 1-5 saved perspectives in rank order. Pass an existing_session_id when rebuilding so the tool does not create a duplicate fork.',
        items: {
          type: 'object',
          additionalProperties: false,
          properties: {
            rank: { type: 'number', required: true },
            title: { type: 'string', required: true },
            existing_session_id: { type: 'string' },
          },
        },
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          module02_run_id: { type: 'string', required: true },
          source_session_id: { type: 'string', required: true },
          complete: { type: 'boolean', required: true },
          branches: {
            type: 'array',
            required: true,
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                rank: { type: 'number', required: true },
                title: { type: 'string', required: true },
                session_id: { type: 'string', required: true },
                reused: { type: 'boolean', required: true },
              },
            },
          },
          errors: {
            type: 'array',
            required: true,
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                rank: { type: 'number', required: true },
                message: { type: 'string', required: true },
              },
            },
          },
        },
      },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
    },
    async execute(args, exec) {
      if (exec.agent === undefined) {
        throw new Error('Perspective branch creation requires a live root agent.')
      }
      if (args.perspectives.length < 1 || args.perspectives.length > 5) {
        throw new Error('Perspective branch creation requires 1-5 perspectives.')
      }
      if (args.perspectives.some(item => !Number.isInteger(item.rank) || item.rank < 1 || item.rank > 5 || item.title.trim().length === 0)) {
        throw new Error('Each perspective needs an integer rank from 1 to 5 and a non-empty title.')
      }
      const ranks = new Set(args.perspectives.map(item => item.rank))
      if (ranks.size !== args.perspectives.length) {
        throw new Error('Perspective ranks must be unique.')
      }

      const sourceSessionId = exec.agent.session.id
      const branches = []
      const errors = []
      for (const perspective of [...args.perspectives].sort((a, b) => a.rank - b.rank)) {
        const title = boundedTitle(perspective.rank, perspective.title.trim())
        if (perspective.existing_session_id?.trim()) {
          branches.push({
            rank: perspective.rank,
            title,
            session_id: perspective.existing_session_id.trim(),
            reused: true,
          })
          continue
        }
        try {
          const forked = await ctx.sessionController.fork({
            sessionId: sourceSessionId,
            allowMigration: true,
          })
          await ctx.sessionController.rename({ sessionId: forked.sessionId, title })
          branches.push({
            rank: perspective.rank,
            title,
            session_id: forked.sessionId,
            reused: false,
          })
        } catch (error) {
          errors.push({
            rank: perspective.rank,
            message: error instanceof Error ? error.message : String(error),
          })
        }
      }
      return {
        module02_run_id: args.module02_run_id,
        source_session_id: sourceSessionId,
        complete: errors.length === 0 && branches.length === args.perspectives.length,
        branches,
        errors,
      }
    },
  }))
}
