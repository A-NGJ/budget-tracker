---
description: Create detailed implementation plans through interactive research and iteration
model: opus
---

# Implementation Plan

Create detailed implementation plans through an interactive, iterative process. Be skeptical, thorough, and collaborative.

## Initial Response

If a file path or ticket reference was provided, read it fully and begin research. Otherwise respond:
```
I'll help you create a detailed implementation plan.

Please provide:
1. The task/ticket description (or reference to a ticket file)
2. Any relevant context, constraints, or requirements

Tip: `/create-plan thoughts/tickets/eng_1234.md`
```

## Process Steps

### Step 1: Context Gathering

1. **Read all mentioned files fully** (no limit/offset) before spawning sub-tasks
2. **Spawn parallel research tasks:**
   - **codebase-locator**: Find files related to the task
   - **codebase-analyzer**: Understand current implementation
   - **thoughts-locator**: Find existing docs about this feature
3. **Read all files identified by research tasks**
4. **Present informed understanding:**
   ```
   Based on the ticket and my research:

   I've found that:
   - [Current implementation detail with file:line reference]
   - [Relevant pattern or constraint discovered]

   Questions my research couldn't answer:
   - [Specific technical question requiring human judgment]
   ```

### Step 2: Research & Discovery

After initial clarifications:

1. **Verify any corrections** - spawn new research tasks, don't just accept
2. **Create research todo list** using TodoWrite
3. **Spawn parallel sub-tasks** for deeper investigation:
   - **codebase-pattern-finder**: Find similar features to model after
   - **thoughts-analyzer**: Extract insights from relevant documents
4. **Present findings and design options:**
   ```
   **Current State:**
   - [Key discovery about existing code]

   **Design Options:**
   1. [Option A] - [pros/cons]
   2. [Option B] - [pros/cons]

   Which approach aligns best?
   ```

### Step 3: Plan Structure

Get buy-in on structure before writing details:
```
Proposed plan structure:

## Overview
[1-2 sentence summary]

## Implementation Phases:
1. [Phase] - [what it accomplishes]
2. [Phase] - [what it accomplishes]

Does this phasing make sense?
```

### Step 4: Write the Plan

Save to `.claude/thoughts/shared/plans/YYYY-MM-DD-ENG-XXXX-description.md`
- Format: `YYYY-MM-DD-ENG-XXXX-description.md`
- Without ticket: `2025-01-08-improve-error-handling.md`

**Template:**

````markdown
# [Feature/Task Name] Implementation Plan

## Overview
[Brief description of what we're implementing and why]

## Current State Analysis
[What exists now, key constraints discovered]

### Key Discoveries:
- [Important finding with file:line reference]

## Desired End State
[Specification of end state and how to verify it]

## What We're NOT Doing
[Out-of-scope items to prevent scope creep]

## Implementation Approach
[High-level strategy and reasoning]

## Phase 1: [Descriptive Name]

### Overview
[What this phase accomplishes]

### Changes Required:

#### 1. [Component/File Group]
**File**: `path/to/file.ext`
**Changes**: [Summary]

```[language]
// Specific code to add/modify
```

#### 2. [Component/File Group tests]
**File**: `path/to/test_file.ext`
**Changes**: [Summary]

```[language]
// Specific test code to add/modify
```

### Success Criteria:

#### Automated Verification:
- [ ] Tests pass: `make test`
- [ ] Type checking: `npm run typecheck`
- [ ] Linting: `make lint`

#### Manual Verification:
- [ ] Feature works as expected in UI
- [ ] Edge cases verified manually

**Note**: Pause for manual confirmation before proceeding to next phase.

---

## Phase 2: [Descriptive Name]
[Similar structure...]

---

## Testing Strategy

### Unit Tests:
- [What to test, key edge cases].
- References to tests cases added in each phase.

### Manual Testing:
1. [Specific verification step]

## References
- Original ticket: `path/to/ticket.md`
- Similar implementation: `[file:line]`
````

### Step 5: Review & Iterate

1. Present the draft plan location
2. Iterate based on feedback
3. Continue until user is satisfied

## Guidelines

1. **Be Skeptical**: Question vague requirements, verify with code
2. **Be Interactive**: Get buy-in at each step, don't write full plan in one shot
3. **Be Thorough**: Include specific file paths and line numbers
4. **Be Practical**: Focus on incremental, testable changes
5. **No Open Questions**: Resolve all questions before finalizing

## Common Patterns

**Database Changes:** Schema/migration -> Store methods -> Business logic -> API -> Clients

**New Features:** Research patterns -> Data model -> Backend -> API -> UI

**Refactoring:** Document behavior -> Incremental changes -> Maintain compatibility
