# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`
- **Read an issue**: `gh issue view <number> --comments`
- **List issues**: `gh issue list --state open` with appropriate `--label` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

Infer the repo from the git remote; `gh` does this automatically inside a clone.

## Pull requests as a triage surface

**PRs as a request surface: no.** Set to `yes` if this repo treats external PRs as feature requests.

## Workflow state

- **State (labels):** `todo`, `in-progress`. Swap with `gh issue edit <number> --add-label in-progress --remove-label todo`. A closed issue is done; there is no `done` label.
- **Branch naming:** `<type>/<issue-id>-<slug>`, type `feature` | `bugfix` | `hotfix`.
- **Create and link a branch:** `gh issue develop <number> --name <branch> --base <default-branch>`.
- **Pull request:** `gh pr create --base <default-branch> --head <branch> --title "..." --body-file <file>`, with `Closes #<number>` in the body.
- **On pull request open:** remove the `in-progress` label.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.
