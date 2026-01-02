# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

This is a personal budget tracker written in Python.

## Thoughts Directory

This project uses a `.claude/thoughts/` directory for persistent context:

```
.claude/thoughts/
├── shared/           # Shared across all worktrees/branches
│   ├── plans/        # Implementation plans (created by /create-plan)
│   ├── research/     # Codebase research notes
│   └── decisions/    # Architecture decision records
└── local/            # Branch-specific notes (gitignored)
    └── scratch/      # Temporary working notes
```

### Usage

- **Plans**: Store implementation plans in `thoughts/shared/plans/`
- **Research**: Document codebase findings in `thoughts/shared/research/`
- **Decisions**: Record architectural decisions in `thoughts/shared/decisions/`
- **Scratch**: Use `thoughts/local/scratch/` for temporary notes

### Conventions

- Shared thoughts are committed to git
- Local thoughts are gitignored for branch-specific work
- Use descriptive filenames: `feature-name.md`, `2024-01-15-decision.md`

## Development Conventions

Code quality checks:
- Type checking: `ty check`
- Linting: `ruff check`
- Formatting: `ruff format --check`
