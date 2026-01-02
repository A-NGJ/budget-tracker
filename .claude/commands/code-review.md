---
description: Perform a comprehensive code review using multiple specialized agents focusing on code quality, security, and test coverage.
model: opus
tools: Read, Glob, Grep, WebSearch, WebFetch, BashOutput, Bash
---

Perform a code review using multiple specialized agents with explicit Task tool invocations.

Parameters:
--ref [optional]: Git reference for the base of the code changes. Defaults to main branch if not provided.
--pr [optional]: Pull Request or Merge Request number to describe.

Those Parameters are mutually exclusive; only one should be provided. If a user specifies both, prompt them to choose one.

Execute parallel reviews using `Task` tool with specialized agents:

## 1. Repository detection

## 2. Get the code changes

### If `--pr` is provided.

1. **Detect repository type (GitHub or GitLab):**

First, automatically detect whether this is a GitHub or GitLab repository:

- Check for GitHub: `git remote -v | grep -q 'github.com' && echo 'github' || echo 'unknown'`
- Check for GitLab: `git remote -v | grep -q 'gitlab.com' && echo 'gitlab' || echo 'unknown'`
- If both or neither are detected, ask the user: "Is this a GitHub or GitLab repository?"
- Set the appropriate CLI tool based on detection:
  - GitHub: use `gh` commands (Pull Requests)
  - GitLab: use `glab` commands (Merge Requests)

2. **Identify the PR/MR to describe:**

   - Check if the current branch has an associated PR/MR:
     - **GitHub**: `gh pr view --json url,number,title,state 2>/dev/null`
     - **GitLab**: `glab mr view --output json 2>/dev/null`

3. **Gather comprehensive PR/MR information:**

   - Get the full diff:
     - **GitHub**: `gh pr diff {number}`
     - **GitLab**: `glab mr diff {number}`
   - Get commit history:
     - **GitHub**: `gh pr view {number} --json commits`
     - **GitLab**: `glab mr view {number} --output json` (check for commits field)
   - Review the base/target branch:
     - **GitHub**: `gh pr view {number} --json baseRefName`
     - **GitLab**: `glab mr view {number} --output json` (check for targetBranch field)
   - Get PR/MR metadata:
     - **GitHub**: `gh pr view {number} --json url,title,number,state`
     - **GitLab**: `glab mr view {number} --output json`

### If `--ref` is provided 

1.  **Fetch the specified reference:**
    - `git fetch origin {ref}:{ref}`
2.  **Get the diff between the specified reference and the current branch:**
    - `git diff {ref}...HEAD`
3.  **Get commit history between the two references:**
    - `git log {ref}..HEAD --oneline`
4.  **Get metadata about the specified reference:**
    - `git show {ref} --summary`

### If `--ref` is not provided

1.  **Default to main branch:**
    - `git fetch origin main:main`
2. **Get diff stat between main and current branch:**
   - `git diff main...HEAD --stat`
3.  **Get the diff between main and the current branch:**
    - `git diff main...HEAD`
4.  **Get commit history between main and the current branch:**
    - `git log main..HEAD --oneline`
5.  **Get metadata about the main branch:**
    - `git show main --summary`

5.  **Prepare for specialized reviews:**
    - Write an index of code changes to a TEMPORARY file in the `/tmp/` directory. It should include 3 sections, each for a specialized review:
      - Code Quality Review
      - Security Audit
      - Test Coverage Assessment
    - Each section should contain:
      - List of changed files with paths. Relevant for the review type
      - Summary of changes (added, modified, deleted files). Relevant for the review type.
      - Relevant commit messages.
    - Pass the path to this file as `$ARGUMENTS` to each specialized agent below
    - DO NOT include the full diff in `$ARGUMENTS`.

## 3. Code Quality Review

- Use Task tool with subagent_type="code-reviewer"
- Prompt: "Review code quality and maintainability for: $ARGUMENTS. Check for code smells, readability, documentation, and adherence to best practices. Focus on the code quality, following best practices considering the project context. DO NOT RUN tests."
- Focus: Clean code principles, SOLID, DRY, naming conventions

## 4. Security Audit

- Use Task tool with subagent_type="security-auditor"
- Prompt: "Perform security audit on: $ARGUMENTS. Check for vulnerabilities, OWASP compliance, authentication issues, and data protection."
- Focus: Injection risks, authentication, authorization, data encryption

## 5. Test Coverage Assessment

- Use Task tool with subagent_type="code-reviewer"
- Prompt: "Evaluate test coverage and quality for: $ARGUMENTS. Assess unit tests, integration tests, and identify gaps in test coverage."
- Focus: Coverage metrics, test quality, edge cases, test maintainability

## Consolidated Report Structure

Compile all feedback into a unified report:

- **Critical Issues** (must fix): Security vulnerabilities, broken functionality, architectural flaws
- **Recommendations** (should fix): Performance bottlenecks, code quality issues, missing tests
- **Suggestions** (nice to have): Refactoring opportunities, documentation improvements
- **Positive Feedback** (what's done well): Good practices to maintain and replicate

After compiling feedback, **save the plan** to `.claude/thoughts/code-reviews/YYYY-MM-DD-XXX-code-review-report.md`

- Format: `YYYY-MM-DD-ENG-XXXX-description.md` where:
- YYYY-MM-DD is today's date
- XXX is a branch name or ticket number (if available). Replace all `/` with `-`.
- description is a brief kebab-case description
- Examples:
- `2025-01-08-feature-renaming-parent-child-tracking.md`
