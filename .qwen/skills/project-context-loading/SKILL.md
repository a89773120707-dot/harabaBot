---
name: project-context-loading
description: Scan project for context files (context, prompts, system, instructions, AI), or fall back to full .md scan with structured report
source: auto-skill
extracted_at: '2026-06-12T11:16:09.774Z'
---

# Project Context Loading

When asked to load project context or when starting a new session, follow this two-tier approach:

## Tier 1 — Targeted Scan

Glob for context-specific files in the project root:
- `*context*` — AI-context.md, project-context.md, etc.
- `*prompt*` — PROMPTS.md, system_prompt.md, etc.
- `*system*` — SYSTEM.md, system.md
- `*instruction*` — instructions.md, INSTRUCTIONS.md
- `*AI*` — AI.md, ai_context.md
- `.qwen/*.md` — files in .qwen directory

If any are found → read each fully and report.

## Tier 2 — Full .md Fallback

If Tier 1 finds nothing, scan ALL `*.md` files in the project root (exclude `node_modules/`, `.git/`, `vendor/`, `build/`, `dist/`).

Read every `.md` file found.

## Report Format

Always show a structured report to the user:

### If Tier 1 succeeded:
```
📂 Загружены файлы контекста:
✅ AI_GLOBAL_CONTEXT.md
✅ project-context-auto.md

📋 Контекст загружен и применён к сессии!
```

### If Tier 2 (fallback):
```
📂 Файлы контекста не найдены. Выполнено полное сканирование проекта:

📋 Найдено N .md файлов:
✅ path/to/file.md (N строк) — краткое описание содержимого

📊 Структура проекта:
- README.md: [основная информация]
- docs/: [документация]

📝 Ключевая информация из файлов:
- [Основные сущности, зависимости, архитектурные решения]
- [TODO, планы, задачи]
```

## Key Principles

- **Never skip the fallback** — if no dedicated context files exist, full .md scan is mandatory
- **Read fully** — do not truncate context files
- **Summarise** — provide line counts and one-line descriptions for each file in the report
- **Apply** — use the loaded information to inform subsequent work in the session
- **Russian output** — all responses must be in Russian (per output-language.md)
