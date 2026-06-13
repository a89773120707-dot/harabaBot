---
name: plan-discuss-approve-implement
description: Strict workflow: receive plan → discuss → get explicit approval → implement in agent mode. Never write code before approval.
source: auto-skill
extracted_at: '2026-06-07T08:32:33.377Z'
updated_at: '2026-06-07T11:43:00.000Z'
---

## Workflow

1. **User sends plan** → save it to a file (e.g. `MVP_PLAN.md`)
2. **Discuss** → ask clarifying questions, propose structure, break into blocks
3. **User explicitly approves** → wait for signals like "утверждаю", "ОК", "давай", "реализуй"
4. **Implement in agent mode** → use subagent/tool-based execution, not direct code writing

## Rules

- **NEVER write implementation code before explicit user approval**
- **NEVER `git push` without explicit approval** — show commit message and files first, ask "пушим?"
- **NEVER deploy to VPS without explicit approval** — show full deploy plan first, ask "деплоим?"
- Push and deploy have blast radius — always get agreement before proceeding
- Each implementation block should have its own detailed sub-plan (e.g. `BLOCK1_PLAN.md`)
- Use agent mode (subagent calls) for all code implementation
- Maintain a `QUESTIONS.md` file for open questions that need resolution across sessions
- At session end, remind the user to discuss remaining items from `QUESTIONS.md`

## Block-based implementation

When a plan has multiple blocks:
- Implement strictly in order (1 → 2 → 3 → ...)
- Each block needs its own implementation plan before starting
- Verify block works with a test script before moving to the next one
- **First prove on one item** (e.g. one search model), **then scale to all** (e.g. all 8 models)
- Don't try to fix 8 errors at once — get one working completely first

## File conventions

| File | Purpose |
|------|---------|
| `MVP_PLAN.md` | Main plan summary |
| `BLOCK{N}_PLAN.md` | Detailed implementation plan for block N |
| `QUESTIONS.md` | Open questions to resolve across sessions |
| `test_block{N}.py` | Verification script for block N |
