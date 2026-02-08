# Tasks

## Todo

### Add `--repo` flag for creating real Issues instead of DraftIssues
<!-- id: PVTI_lADOC9ysqc4BETyazglCGJE -->

New items are currently always created as DraftIssues on the project board.
To create real GitHub Issues, the CLI needs a `--repo owner/name` flag so
it knows which repository to file them in.

Implementation requires:
- Add `--repo` CLI argument to `cli.py`
- Add `create_issue(repo_owner, repo_name, title, body)` method using the
  `createIssue` GraphQL mutation
- Add `add_item_to_project(content_id)` method using the
  `addProjectV2ItemById` mutation
- Route `execute_sync` create path: if `--repo` is provided, create a real
  Issue and add it to the board; otherwise create a DraftIssue (current behavior)
- After creating a real Issue, sync assignees/labels immediately

### Add PR comment summary for dry-run in CI
<!-- id: PVTI_lADOC9ysqc4BETyazglCGJQ -->
- **Labels:** feature, ci

When `tasksmd-sync` runs in dry-run mode on a pull request, it should post
a comment summarizing what would change (e.g. "2 create, 1 update, 0 archive").
The GitHub Action workflow already runs dry-run on PRs but doesn't post
a summary comment yet.

### Support converting DraftIssues to real Issues
<!-- id: PVTI_lADOC9ysqc4BETyazglCGJY -->
- **Labels:** feature

When `--repo` is provided and an existing board item is a DraftIssue, offer
a way to convert it into a real Issue in the target repo. This would allow
teams to start with DraftIssues and promote them to real Issues later.

### Remove due date syncing
<!-- id: PVTI_lADOC9ysqc4BETyazglCGJg -->
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
<!-- id: PVTI_lADOC9ysqc4BETyazglCGJs -->
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

### Idempotent sync for DraftIssues and real Issues
<!-- id: PVTI_lADOC9ysqc4BETyazglCGJ4 -->
- **Labels:** bug, sync

The sync engine now correctly handles both DraftIssues and real Issues:
- `_needs_update` is content-type-aware (skips assignee/label comparison
  for DraftIssues since those fields can't be written via the API)
- `_apply_task_fields` routes assignee/label mutations only for real Issues
- `execute_sync` update path handles both `updateProjectV2DraftIssue` and
  `updateIssue` mutations

Fully working and tested with 98 passing tests.

### Fix idempotency bug with spurious updates on second run
<!-- id: PVTI_lADOC9ysqc4BETyazglCGJ8 -->

Running `tasksmd-sync` twice produced 4 spurious updates on the second run.
Root cause: `_needs_update` compared `task.assignee` and `task.labels` against
the board item, but `_apply_task_fields` couldn't actually write those fields
to DraftIssues — creating a perpetual diff.

Fixed by making `_needs_update` content-type-aware: assignee/label comparisons
are only performed when `board_item.content_type == "Issue"`.
