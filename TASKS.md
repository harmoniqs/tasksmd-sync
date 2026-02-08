# Tasks

## Todo

### Add PR comment summary for dry-run in CI
<!-- id: PVTI_lADOC9ysqc4BETyazglCHLI -->
- **Labels:** feature, ci

When `tasksmd-sync` runs in dry-run mode on a pull request, it should post
a comment summarizing what would change (e.g. "2 create, 1 update, 0 archive").
The GitHub Action workflow already runs dry-run on PRs but doesn't post
a summary comment yet.

### Remove due date syncing
<!-- id: PVTI_lADOC9ysqc4BETyazglCHLQ -->
- **Labels:** feature

Due dates should be managed entirely in the GitHub Projects interface, not
synced from TASKS.md. Remove due date support from the sync pipeline:
- Remove the `RE_DUE` pattern from `parser.py` (stop parsing `- **Due:**` lines)
- Remove the `due_date` field from `Task` in `models.py`
- Remove the `due_date` comparison in `_needs_update` in `sync.py`
- Remove the "End date" / "Due" field write in `_apply_task_fields`
- Keep the `due_date` field on `ProjectItem` (read-only, for display)
- Update `FORMAT.md` and `README.md` to remove Due date references

### Add `--flush` flag to remove completed tasks from TASKS.md
<!-- id: PVTI_lADOC9ysqc4BETyazglCHLk -->
- **Labels:** feature

Add a `--flush` CLI flag that removes tasks in the `## Done` section from
TASKS.md after syncing. Before removing them, ensure the corresponding board
items are marked as completed (status set to "Done") on the project. This
keeps TASKS.md clean over time — completed work gets flushed out, and the
project board remains the historical record.

Behavior:
- After a normal sync, if `--flush` is passed, delete all task blocks
  under `## Done` from the TASKS.md file
- Before deleting, verify each task's board item has status "Done" (set it
  if not already)
- The `## Done` section heading itself should remain (empty) so the file
  structure stays valid
- Should work with `--dry-run` to preview what would be flushed

## Done

