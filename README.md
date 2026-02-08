# tasksmd-sync

One-way sync from `TASKS.md` files to GitHub Project boards.

## Overview

`tasksmd-sync` is a CLI tool and GitHub Action that synchronizes task definitions
from human-readable `TASKS.md` files in your repositories to a centralized
GitHub Projects (v2) board. The `TASKS.md` file is the source of truth.

## How It Works

```
TASKS.md (in repo)  ──sync──>  GitHub Project Board
```

Each repository maintains its own `TASKS.md` containing tasks relevant to that
repo. When `TASKS.md` is updated and pushed, the sync tool:

1. Parses the `TASKS.md` file
2. Compares against the current state of the GitHub Project board
3. Creates, updates, or archives board items to match

## TASKS.md Format

Tasks are organized by status sections using markdown headings:

```markdown
# Tasks

## Todo

### Implement user authentication
<!-- id: PVTI_abc123 -->
- **Assignee:** @alice
- **Labels:** feature, security

Description of the task goes here. Supports full GitHub-flavored
markdown including code blocks, lists, and links.

## In Progress

### Fix connection pooling bug
<!-- id: PVTI_def456 -->
- **Assignee:** @bob
- **Labels:** bug

The connection pool leaks under high concurrency.

## Done

### Set up CI pipeline
<!-- id: PVTI_ghi789 -->

Configured GitHub Actions for tests and linting.
```

### Task Fields

| Field | Syntax | Required |
|-------|--------|----------|
| Title | `### Title text` | Yes |
| Board ID | `<!-- id: PVTI_... -->` | No (auto-assigned) |
| Assignee | `- **Assignee:** @username` | No |
| Labels | `- **Labels:** label1, label2` | No |
| Status | Determined by parent `##` section | Yes (implicit) |
| Description | Free text after metadata | No |

See [FORMAT.md](FORMAT.md) for the full specification.

## Installation

```bash
pip install .
```

## CLI Usage

```bash
# Dry run (preview what would change)
tasksmd-sync TASKS.md \
  --org harmoniqs \
  --project-number 2 \
  --dry-run \
  --verbose

# Live sync
tasksmd-sync TASKS.md \
  --org harmoniqs \
  --project-number 2 \
  --token "$GITHUB_TOKEN"

# Scoped sync (only archive items tagged with this repo's label)
tasksmd-sync TASKS.md \
  --org harmoniqs \
  --project-number 2 \
  --repo-label "Piccolo.jl"
```

### Options

| Flag | Description |
|------|-------------|
| `--org` | GitHub org login (required) |
| `--project-number` | Project board number (required) |
| `--token` | GitHub token (or set `GITHUB_TOKEN` / `TASKSMD_GITHUB_TOKEN` env var) |
| `--repo` | Target repository for creating real Issues (format: `owner/repo`) |
| `--repo-label` | Label to scope archive detection to this repo's items |
| `--archive-done` | Archive tasks in the `Done` section and remove them from `TASKS.md` |
| `--writeback` | Write board item IDs back into `TASKS.md` (default: false) |
| `--dry-run` | Preview changes without executing |
| `--verbose` / `-v` | Enable debug logging |
| `--output-json` | Write sync results to a JSON file |

## GitHub Action

Add this workflow to any opted-in repository:

```yaml
# .github/workflows/tasksmd-sync.yml
name: Sync TASKS.md

on:
  push:
    branches: [main]
    paths: ['TASKS.md']
  pull_request:
    paths: ['TASKS.md']

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: harmoniqs/tasksmd-sync@main
        with:
          tasks-file: TASKS.md
          org: harmoniqs
          project-number: '2'
          repo-label: ${{ github.event.repository.name }}
          github-token: ${{ secrets.PROJECTS_TOKEN }}
          dry-run: ${{ github.event_name == 'pull_request' }}
```

On **pull requests**, the action runs in dry-run mode and posts a comment
summarizing what would change. On **push to main**, it executes the sync.

## Configuration

### Token Permissions

The GitHub token needs the following scope:
- `project` — read and write access to organization projects

A fine-grained PAT or GitHub App token with Projects permissions works.
The default `GITHUB_TOKEN` does **not** have project access.

### Repo Label Convention

Use `--repo-label` to tag items on the board with their source repository.
This ensures that archive detection only removes items belonging to *this*
repo's `TASKS.md`, not items from other repos.

## Opted-In Repositories

Currently configured for:
- `Piccolo.jl`
- `NamedTrajectories.jl`
- `DirectTrajOpt.jl`
- `Piccolissimo.jl`
- `vault` (for non-code tasks)

## Development

```bash
# Install for development
pip install -e .
pip install pytest

# Run tests
pytest

# Run the parser on a sample file
python -m tasksmd_sync.cli sample_TASKS.md --org harmoniqs --project-number 2 --dry-run -v
```

## License

MIT
