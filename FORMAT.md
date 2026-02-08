# TASKS.md Format Specification

## Overview

TASKS.md is a human-readable, LLM-friendly markdown file that serves as the source of truth for project tasks in a repository. Each repository maintains its own TASKS.md containing only tasks relevant to that repo.

## Structure

A TASKS.md file is organized into **status sections**, each containing **task blocks**.

```markdown
# Tasks

## Todo

### Task title here
<!-- id: PVTI_lADOBx... -->
- **Assignee:** @username
- **Labels:** bug, urgent

Description of the task goes here. Can be multiple paragraphs,
include code blocks, lists, etc.

### Another task with no board ID yet
- **Labels:** feature

This task has no `id` comment, so the sync tool will create a
new project board item for it and inject the ID on the next
reverse-sync pass.

## In Progress

### Implement the flux capacitor
<!-- id: PVTI_lADOBx456 -->
- **Assignee:** @doc
- **Labels:** feature, core

Multi-paragraph description with code:

```python
capacitor.flux()
```

## Done

### Fix time paradox bug
<!-- id: PVTI_lADOBx789 -->
- **Assignee:** @marty
- **Labels:** bug

Resolved by avoiding grandfather paradox edge case.
```

## Parsing Rules

### Status Sections

- `## Todo` — maps to the "Todo" column on the project board
- `## In Progress` — maps to the "In Progress" column
- `## Done` — maps to the "Done" column
- Section names are matched case-insensitively; extra whitespace is trimmed
- Custom status names are supported — they map 1:1 to project board status field values

### Task Blocks

Each task block starts with a `### heading` (h3) and continues until the next `### heading` or `## section`.

**Required:**
- `### Title` — the task title (h3 heading)

**Optional metadata (in any order, immediately after the title):**
- `<!-- id: PVTI_... -->` — hidden project board item ID for matching. Injected by the sync tool on creation. If absent, a new board item is created.
- `- **Assignee:** @username` — GitHub username (with or without `@`)
- `- **Labels:** label1, label2` — comma-separated list of labels

**Description:**
Everything after the metadata lines until the next task or section heading. Supports full GitHub-flavored markdown.

### Metadata Field Formats

| Field | Format | Example |
|-------|--------|---------|
| Assignee | `@username` or `username` | `@octocat` |
| Labels | Comma-separated strings | `bug, urgent, P0` |
| Status | Determined by parent `##` section | (implicit) |

### ID Comments

The `<!-- id: ... -->` HTML comment is the primary key for matching tasks to project board items. Rules:

1. If present: the tool updates the existing project board item
2. If absent: the tool creates a new item and (in future reverse-sync) writes the ID back
3. If an ID exists in the board but is missing from TASKS.md: the item is archived on the board

### Whitespace & Formatting

- Blank lines between metadata fields are optional
- A blank line should separate metadata from description
- Indentation within descriptions is preserved
- Trailing whitespace is ignored
