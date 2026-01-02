---
description: Generate comprehensive PR descriptions following repository templates
model: sonnet
---

# Generate PR Description

You are tasked with generating a comprehensive pull request description following the repository's standard template.

## Repository Detection:

First, automatically detect whether this is a GitHub or GitLab repository:
- Check for information in the CLAUDE.md file or CLAUDE.local.md file if present.
- Check for GitHub: `git remote -v | grep -q 'github.com' && echo 'github' || echo 'unknown'`
- Check for GitLab: `git remote -v | grep -q 'gitlab.com' && echo 'gitlab' || echo 'unknown'`
- If both or neither are detected, ask the user: "Is this a GitHub or GitLab repository?"
- Set the appropriate CLI tool based on detection:
  - GitHub: use `gh` commands (Pull Requests)
  - GitLab: use `glab` commands (Merge Requests)

## Steps to follow:

1. **Read the PR description template:**
   - First, check if `.claude/thoughts/shared/pr_description.md` exists
   - If it exists, read the template carefully to understand all sections and requirements
   - If it doesn't exist, use this default template:
     ```
     <Short description>

     ## Key changes
     - **<Change 1>**: <Description>

     ## Breaking changes
     - **<Breaking change>**: <Description> (or "None")

     ## Configuration changes
     - **<Config change>**: <Description> (or "None")

     ## Testing
     - **<Test performed>**: <Description>
     ```


2. **Identify the PR/MR to describe:**
   - Check if the current branch has an associated PR/MR:
     - **GitHub**: `gh pr view --json url,number,title,state 2>/dev/null`
     - **GitLab**: `glab mr view --output json 2>/dev/null`
   - If no PR/MR exists for the current branch, or if on main/master, list open items:
     - **GitHub**: `gh pr list --limit 10 --json number,title,headRefName,author`
     - **GitLab**: `glab mr list --per-page 10`
   - Ask the user which PR/MR they want to describe

3. **Check for existing description:**
   - Check if `thoughts/shared/prs/{number}_description.md` already exists
   - If it exists, read it and inform the user you'll be updating it
   - Consider what has changed since the last description was written

4. **Gather comprehensive PR/MR information:**
   - Get the full diff:
     - **GitHub**: `gh pr diff {number}`
     - **GitLab**: `glab mr diff {number}`
   - If you get an error about no default remote repository:
     - **GitHub**: instruct the user to run `gh repo set-default` and select the appropriate repository
     - **GitLab**: instruct the user to set the repository with `-R` flag or configure default
   - Get commit history:
     - **GitHub**: `gh pr view {number} --json commits`
     - **GitLab**: `glab mr view {number} --output json` (check for commits field)
   - Review the base/target branch:
     - **GitHub**: `gh pr view {number} --json baseRefName`
     - **GitLab**: `glab mr view {number} --output json` (check for targetBranch field)
   - Get PR/MR metadata:
     - **GitHub**: `gh pr view {number} --json url,title,number,state`
     - **GitLab**: `glab mr view {number} --output json`

5. **Analyze the changes thoroughly:** (ultrathink about the code changes, their architectural implications, and potential impacts)
   - Read through the entire diff carefully
   - For context, read any files that are referenced but not shown in the diff
   - Understand the purpose and impact of each change
   - Identify user-facing changes vs internal implementation details
   - Look for breaking changes or migration requirements

6. **Handle verification requirements:**
   - Look for any checklist items in the "How to verify it" section of the template
   - For each verification step:
     - If it's a command you can run (like `make check test`, `npm test`, etc.), run it
     - If it passes, mark the checkbox as checked: `- [x]`
     - If it fails, keep it unchecked and note what failed: `- [ ]` with explanation
     - If it requires manual testing (UI interactions, external services), leave unchecked and note for user
   - Document any verification steps you couldn't complete

7. **Generate the concise description:**
   - Fill out each section from the template thoroughly, but concisely:
     - Answer each question/section based on your analysis
     - Be specific about problems solved and changes made
     - Focus on user impact where relevant
     - Include essential technical details in appropriate sections
     - Write a concise changelog entry
     - Include only essential information, detailed code changes can be found in the diff
   - Ensure all checklist items are addressed (checked or explained)

8. **Save and sync the description:**
   - Write the completed description to `.claude/thoughts/shared/prs/{number}_description.md`
   - Show the user the generated description
   - Wait for user input/approval before proceeding

9. **Update the PR/MR:**
   - Update the description directly:
     - **GitHub**: `gh pr edit {number} --body-file thoughts/shared/prs/{number}_description.md`
     - **GitLab**: `glab mr update {number} --description "$(cat thoughts/shared/prs/{number}_description.md)"`
   - Confirm the update was successful
   - If any verification steps remain unchecked, remind the user to complete them before merging

## Important notes:
- This command works across different repositories - always read the local template
- Be thorough but concise - descriptions should be scannable
- Focus on the "why" as much as the "what"
- Include any breaking changes or migration notes prominently
- If the PR touches multiple components, organize the description accordingly
- Always attempt to run verification commands when possible
- Clearly communicate which verification steps need manual testing
