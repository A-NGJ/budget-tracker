# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

This project uses `uv` as the Python environment manager.

## Thoughts Directory

This project uses a `.thoughts/` directory for persistent context:

```
.thoughts/
├── research/      # Codebase research notes
├── plans/         # Implementation plans (created by /create-plan)
├── designs/       # Design documents
├── structures/    # Structure documents
├── tickets/       # Ticket documentation
├── prs/           # PR descriptions
├── reviews/       # Code review reports
```

### Usage

- **Research**: Document codebase findings in `.thoughts/research/`
- **Plans**: Store implementation plans in `.thoughts/plans/`
- **Designs**: Record architectural designs in `.thoughts/designs/`
- **Tickets**: Keep ticket context in `.thoughts/tickets/`

### Conventions

- The `.thoughts/` directory is gitignored
- Use descriptive filenames: `YYYY-MM-DD-feature-name.md`

## Implementing Plans

When implementing a plan from `.thoughts/plans/`, present intended changes for each phase before writing code. Pause between phases for manual verification. Update checkboxes in the plan file as items complete, and resume from the first unchecked item if checkboxes already exist.

## Development Conventions

All code must pass `ty` and `ruff` checks.
