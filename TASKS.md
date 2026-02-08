# Tasks

## Done

### Add PR comment summary for dry-run in CI
<!-- id: PVTI_lADOC9ysqc4BETyazglCHLI -->

When `tasksmd-sync` runs in dry-run mode on a pull request, it should post
a comment summarizing what would change (e.g. "2 create, 1 update, 0 archive").
The GitHub Action workflow already runs dry-run on PRs but doesn't post
a summary comment yet.

### Remove due date syncing
<!-- id: PVTI_lADOC9ysqc4BETyazglCHLQ -->

Due dates should be managed entirely in the GitHub Projects interface, not
synced from TASKS.md. Remove due date support from the sync pipeline:
- Remove the `RE_DUE` pattern from `parser.py` (stop parsing `- **Due:**` lines)
- Remove the `due_date` field from `Task` in `models.py`
- Remove the `due_date` comparison in `_needs_update` in `sync.py`
- Remove the "End date" / "Due" field write in `_apply_task_fields`
- Keep the `due_date` field on `ProjectItem` (read-only, for display)
- Update `FORMAT.md` and `README.md` to remove Due date references

### Implement label syncing for items
<!-- id: PVTI_lADOC9ysqc4BETyazglCOOI -->
Ensure that labels defined in TASKS.md are correctly synchronized with the
corresponding GitHub Issues. This includes:
- Resolving label names to IDs within the correct repository context.
- Adding missing labels to issues.
- Removing labels that are no longer present in TASKS.md.

