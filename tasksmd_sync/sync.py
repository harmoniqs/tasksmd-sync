"""Sync engine: applies TASKS.md state to a GitHub Project board."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .github_projects import GitHubProjectClient, ProjectItem
from .models import Task, TaskFile

logger = logging.getLogger(__name__)


@dataclass
class SyncPlan:
    """Describes what the sync will do, without executing it."""

    create: list[Task] = field(default_factory=list)
    update: list[tuple[Task, ProjectItem]] = field(default_factory=list)
    archive: list[ProjectItem] = field(default_factory=list)
    unchanged: list[Task] = field(default_factory=list)
    title_matched: set[str] = field(default_factory=set)  # titles resolved via fallback


@dataclass
class SyncResult:
    """Summary of what the sync actually did."""

    created: int = 0
    updated: int = 0
    archived: int = 0
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)
    created_ids: dict[str, str] = field(default_factory=dict)  # title -> new_item_id
    matched_ids: dict[str, str] = field(default_factory=dict)  # title -> matched_item_id


def build_sync_plan(
    task_file: TaskFile,
    board_items: list[ProjectItem],
    repo_label: str | None = None,
) -> SyncPlan:
    """Compare TASKS.md state to board state and produce a plan.

    Args:
        task_file: Parsed TASKS.md
        board_items: Current items on the project board
        repo_label: If set, only consider board items with this label for
                     archive detection (so we don't archive items from other repos)
    """
    plan = SyncPlan()

    # Index board items by their item_id and by title (for fallback matching)
    board_by_id: dict[str, ProjectItem] = {bi.item_id: bi for bi in board_items}
    board_by_title: dict[str, ProjectItem] = {}
    for bi in board_items:
        if bi.title:
            board_by_title.setdefault(bi.title, bi)

    # Track which board item IDs are accounted for by tasks
    seen_board_ids: set[str] = set()

    for task in task_file.tasks:
        if task.board_item_id and task.board_item_id in board_by_id:
            # Existing task matched by ID — check if it needs updating
            seen_board_ids.add(task.board_item_id)
            board_item = board_by_id[task.board_item_id]
            if _needs_update(task, board_item):
                plan.update.append((task, board_item))
            else:
                plan.unchanged.append(task)
        elif task.board_item_id and task.board_item_id not in board_by_id:
            # Task references a board ID that doesn't exist — try title fallback
            matched = _title_fallback_match(task, board_by_title, seen_board_ids)
            if matched:
                seen_board_ids.add(matched.item_id)
                stale_id = task.board_item_id
                task.board_item_id = matched.item_id
                plan.title_matched.add(task.title)
                logger.debug(
                    "Task '%s' had stale ID '%s'; matched by title to %s",
                    task.title, stale_id, matched.item_id,
                )
                if _needs_update(task, matched):
                    plan.update.append((task, matched))
                else:
                    plan.unchanged.append(task)
            else:
                logger.warning(
                    "Task '%s' references board ID '%s' which was not found; will create new",
                    task.title,
                    task.board_item_id,
                )
                plan.create.append(task)
        else:
            # No board ID — try title fallback before creating
            matched = _title_fallback_match(task, board_by_title, seen_board_ids)
            if matched:
                seen_board_ids.add(matched.item_id)
                task.board_item_id = matched.item_id
                plan.title_matched.add(task.title)
                logger.debug(
                    "Task '%s' matched by title to existing board item %s",
                    task.title, matched.item_id,
                )
                if _needs_update(task, matched):
                    plan.update.append((task, matched))
                else:
                    plan.unchanged.append(task)
            else:
                plan.create.append(task)

    # Board items not in TASKS.md should be archived
    for bi in board_items:
        if bi.item_id in seen_board_ids:
            continue
        # If repo_label is set, only archive items that belong to this repo
        if repo_label and repo_label not in bi.labels:
            continue
        plan.archive.append(bi)

    return plan


def execute_sync(
    client: GitHubProjectClient,
    task_file: TaskFile,
    repo_label: str | None = None,
    dry_run: bool = False,
) -> SyncResult:
    """Execute a full sync from TASKS.md to the project board.

    Args:
        client: Authenticated GitHub Projects client
        task_file: Parsed TASKS.md
        repo_label: Label to scope archive detection to this repo's items
        dry_run: If True, only log what would happen without making changes
    """
    result = SyncResult()

    logger.info("Fetching current board state...")
    board_items = client.list_items()
    logger.info("Found %d items on the board", len(board_items))

    plan = build_sync_plan(task_file, board_items, repo_label)

    logger.info(
        "Sync plan: %d create, %d update, %d archive, %d unchanged",
        len(plan.create),
        len(plan.update),
        len(plan.archive),
        len(plan.unchanged),
    )

    # Record title-matched IDs (these were resolved during plan building)
    for task, board_item in plan.update:
        if task.title in [t.title for t in task_file.tasks if not t.has_board_id or t.board_item_id == board_item.item_id]:
            result.matched_ids[task.title] = board_item.item_id
    for task in plan.unchanged:
        if task.board_item_id:
            result.matched_ids[task.title] = task.board_item_id

    if dry_run:
        _log_dry_run(plan)
        result.created = len(plan.create)
        result.updated = len(plan.update)
        result.archived = len(plan.archive)
        result.unchanged = len(plan.unchanged)
        return result

    fields = client.get_fields()

    # Create new items
    for task in plan.create:
        try:
            item_id = client.add_draft_issue(task.title, task.description)
            logger.info("Created board item '%s' -> %s", task.title, item_id)
            _apply_task_fields(client, item_id, task, fields)
            result.created += 1
            result.created_ids[task.title] = item_id
        except Exception as e:
            msg = f"Failed to create '{task.title}': {e}"
            logger.error(msg)
            result.errors.append(msg)

    # Update existing items
    for task, board_item in plan.update:
        try:
            _apply_task_fields(client, board_item.item_id, task, fields)
            # Update title/body on draft issues (requires the content node ID)
            if board_item.content_type == "DraftIssue" and board_item.content_id:
                try:
                    client.update_draft_issue_body(
                        board_item.content_id, task.title, task.description
                    )
                except Exception as e:
                    logger.debug(
                        "Failed to update draft issue body for '%s': %s",
                        task.title, e,
                    )
            logger.info("Updated board item '%s' (%s)", task.title, board_item.item_id)
            result.updated += 1
        except Exception as e:
            msg = f"Failed to update '{task.title}': {e}"
            logger.error(msg)
            result.errors.append(msg)

    # Archive removed items
    for board_item in plan.archive:
        try:
            client.archive_item(board_item.item_id)
            logger.info(
                "Archived board item '%s' (%s)", board_item.title, board_item.item_id
            )
            result.archived += 1
        except Exception as e:
            msg = f"Failed to archive '{board_item.title}': {e}"
            logger.error(msg)
            result.errors.append(msg)

    result.unchanged = len(plan.unchanged)
    return result


def _title_fallback_match(
    task: Task,
    board_by_title: dict[str, ProjectItem],
    seen_board_ids: set[str],
) -> ProjectItem | None:
    """Try to match a task to a board item by title.

    Only matches items that haven't already been claimed by another task.
    """
    matched = board_by_title.get(task.title)
    if matched and matched.item_id not in seen_board_ids:
        return matched
    return None


def _needs_update(task: Task, board_item: ProjectItem) -> bool:
    """Check if a task's fields differ from the board item."""
    if task.title != board_item.title:
        logger.debug(
            "  [DIFF] '%s' title: %r != %r", task.title, task.title, board_item.title
        )
        return True
    if task.status and task.status.lower() != (board_item.status or "").lower():
        logger.debug(
            "  [DIFF] '%s' status: %r != %r", task.title, task.status, board_item.status
        )
        return True
    if task.description.strip() != (board_item.description or "").strip():
        task_desc = task.description.strip()
        board_desc = (board_item.description or "").strip()
        logger.debug(
            "  [DIFF] '%s' description: %d chars vs %d chars",
            task.title, len(task_desc), len(board_desc),
        )
        if len(task_desc) < 200 and len(board_desc) < 200:
            logger.debug("    task:  %r", task_desc)
            logger.debug("    board: %r", board_desc)
        return True
    if task.assignee and task.assignee != board_item.assignee:
        logger.debug(
            "  [DIFF] '%s' assignee: %r != %r",
            task.title, task.assignee, board_item.assignee,
        )
        return True
    if task.due_date and task.due_date != board_item.due_date:
        logger.debug(
            "  [DIFF] '%s' due_date: %s != %s",
            task.title, task.due_date, board_item.due_date,
        )
        return True
    if task.labels and sorted(task.labels) != sorted(board_item.labels):
        logger.debug(
            "  [DIFF] '%s' labels: %r != %r",
            task.title, sorted(task.labels), sorted(board_item.labels),
        )
        return True
    # Note: Assignees and Labels are not compared here because _apply_task_fields
    # cannot sync them to DraftIssues via the Projects API. Comparing them would
    # create perpetual diffs. Re-enable when assignee/label sync is implemented.
    return False


    if task.labels and sorted(task.labels) != sorted(board_item.labels):
        logger.debug(
            "  [DIFF] '%s' labels: %r != %r",
            task.title, sorted(task.labels), sorted(board_item.labels),
        )
        return True
    return False


def _apply_task_fields(
    client: GitHubProjectClient,
    item_id: str,
    task: Task,
    fields: dict,
) -> None:
    """Apply task metadata to a board item's project fields."""
    # Status — match case-insensitively against board options
    if task.status and "Status" in fields:
        status_field = fields["Status"]
        option_id = _match_status_option(task.status, status_field.options)
        if option_id:
            client.update_item_field_single_select(item_id, status_field.id, option_id)
        else:
            logger.warning(
                "Status '%s' not found in project options: %s",
                task.status,
                list(status_field.options.keys()),
            )

    # Due date — map to "End date" field (or "Due" as fallback)
    if task.due_date:
        due_field = fields.get("End date") or fields.get("Due")
        if due_field:
            client.update_item_field_date(item_id, due_field.id, task.due_date)

    # Note: Assignees and Labels are properties of the underlying Issue/DraftIssue
    # content, not project fields. For draft issues created via the API, these are
    # set via the draft issue mutation. Full issue assignee/label sync would require
    # converting draft issues to real issues — left as a future enhancement.


def _match_status_option(
    task_status: str, options: dict[str, str]
) -> str | None:
    """Match a task status to a board option, case-insensitively.

    The board might have "In progress" while we parse "In Progress".
    """
    # Exact match first
    if task_status in options:
        return options[task_status]
    # Case-insensitive fallback
    lowered = task_status.lower()
    for name, option_id in options.items():
        if name.lower() == lowered:
            return option_id
    return None


def _log_dry_run(plan: SyncPlan) -> None:
    """Log what a sync would do without executing."""
    if plan.title_matched:
        logger.debug(
            "[DRY RUN] %d task(s) resolved via title fallback matching:",
            len(plan.title_matched),
        )
        for title in sorted(plan.title_matched):
            logger.debug("  [TITLE MATCH] '%s'", title)

    for task in plan.create:
        logger.info("[DRY RUN] Would create: '%s' (status: %s)", task.title, task.status)
    for task, bi in plan.update:
        match_note = " [title-matched]" if task.title in plan.title_matched else ""
        logger.info(
            "[DRY RUN] Would update: '%s' (%s)%s", task.title, bi.item_id, match_note
        )
    for task in plan.unchanged:
        match_note = " [title-matched]" if task.title in plan.title_matched else ""
        logger.debug(
            "[DRY RUN] Unchanged: '%s' (%s)%s",
            task.title, task.board_item_id or "?", match_note,
        )
    for bi in plan.archive:
        logger.info(
            "[DRY RUN] Would archive: '%s' (%s)", bi.title, bi.item_id
        )

    # Writeback preview
    writeback_titles = [
        t.title for t in plan.create
    ] + [
        t.title for t in (plan.unchanged + [pair[0] for pair in plan.update])
        if t.title in plan.title_matched
    ]
    if writeback_titles:
        logger.info(
            "[DRY RUN] Would write back %d ID(s) to TASKS.md:",
            len(writeback_titles),
        )
        for title in writeback_titles:
            logger.info("  [WRITEBACK] '%s'", title)
