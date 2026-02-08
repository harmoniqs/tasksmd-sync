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

### Add `--repo` flag for creating real Issues instead of DraftIssues
<!-- id: PVTI_lADOC9ysqc4BETyazglCHLs -->

New items can now be created as real GitHub Issues when `--repo owner/name` is
provided. The sync creates the Issue, adds it to the project, applies status,
assignee, and labels, and writes back the item ID. Falls back to DraftIssue when
`--repo` is omitted.

### Support converting DraftIssues to real Issues
<!-- id: PVTI_lADOC9ysqc4BETyazglCHL4 -->
- **Labels:** feature

DraftIssues are automatically converted to real Issues when `--repo` is
provided, even if they were previously unchanged. The old draft item is
archived, the Issue is created in the target repo, added to the project, and
the new item ID is written back.

### Idempotent sync for DraftIssues and real Issues
<!-- id: PVTI_lADOC9ysqc4BETyazglCHME -->
- **Labels:** bug, sync

The sync engine now correctly handles both DraftIssues and real Issues:
- `_needs_update` is content-type-aware (skips assignee/label comparison
  for DraftIssues since those fields can't be written via the API)
- `_apply_task_fields` routes assignee/label mutations only for real Issues
- `execute_sync` update path handles both `updateProjectV2DraftIssue` and
  `updateIssue` mutations

Fully working and tested with 98 passing tests.

### Fix idempotency bug with spurious updates on second run
<!-- id: PVTI_lADOC9ysqc4BETyazglCHMI -->

Running `tasksmd-sync` twice produced 4 spurious updates on the second run.
Root cause: `_needs_update` compared `task.assignee` and `task.labels` against
the board item, but `_apply_task_fields` couldn't actually write those fields
to DraftIssues — creating a perpetual diff.

Fixed by making `_needs_update` content-type-aware: assignee/label comparisons
are only performed when `board_item.content_type == "Issue"`.
