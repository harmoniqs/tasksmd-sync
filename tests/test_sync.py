"""Tests for the sync engine (plan building, no API calls)."""

from datetime import date

from tasksmd_sync.github_projects import ProjectItem
from tasksmd_sync.models import Task, TaskFile
from tasksmd_sync.sync import build_sync_plan


def _make_task(title, status="Todo", board_id=None, **kwargs):
    return Task(title=title, status=status, board_item_id=board_id, **kwargs)


def _make_board_item(item_id, title="", status="Todo", **kwargs):
    return ProjectItem(item_id=item_id, title=title, status=status, **kwargs)


def test_new_tasks_are_created():
    tf = TaskFile(tasks=[
        _make_task("Task A"),
        _make_task("Task B"),
    ])
    plan = build_sync_plan(tf, [])
    assert len(plan.create) == 2
    assert len(plan.update) == 0
    assert len(plan.archive) == 0


def test_matching_task_is_unchanged():
    tf = TaskFile(tasks=[
        _make_task("Task A", board_id="PVTI_1", status="Todo", description="desc"),
    ])
    board = [
        _make_board_item("PVTI_1", title="Task A", status="Todo", description="desc"),
    ]
    plan = build_sync_plan(tf, board)
    assert len(plan.unchanged) == 1
    assert len(plan.create) == 0
    assert len(plan.update) == 0


def test_changed_task_is_updated():
    tf = TaskFile(tasks=[
        _make_task("Task A (renamed)", board_id="PVTI_1", status="In Progress"),
    ])
    board = [
        _make_board_item("PVTI_1", title="Task A", status="Todo"),
    ]
    plan = build_sync_plan(tf, board)
    assert len(plan.update) == 1
    assert plan.update[0][0].title == "Task A (renamed)"


def test_removed_task_is_archived():
    tf = TaskFile(tasks=[])
    board = [
        _make_board_item("PVTI_1", title="Task A"),
    ]
    plan = build_sync_plan(tf, board)
    assert len(plan.archive) == 1
    assert plan.archive[0].item_id == "PVTI_1"


def test_archive_scoped_to_repo_label():
    """Board items without the repo label should NOT be archived."""
    tf = TaskFile(tasks=[])
    board = [
        _make_board_item("PVTI_1", title="My repo task", labels=["Piccolo.jl"]),
        _make_board_item("PVTI_2", title="Other repo task", labels=["Vault"]),
    ]
    plan = build_sync_plan(tf, board, repo_label="Piccolo.jl")
    assert len(plan.archive) == 1
    assert plan.archive[0].item_id == "PVTI_1"


def test_mixed_operations():
    tf = TaskFile(tasks=[
        _make_task("Existing unchanged", board_id="PVTI_1", status="Todo", description="d"),
        _make_task("Existing changed", board_id="PVTI_2", status="In Progress"),
        _make_task("Brand new"),
    ])
    board = [
        _make_board_item("PVTI_1", title="Existing unchanged", status="Todo", description="d"),
        _make_board_item("PVTI_2", title="Existing changed", status="Todo"),
        _make_board_item("PVTI_3", title="To be archived"),
    ]
    plan = build_sync_plan(tf, board)
    assert len(plan.unchanged) == 1
    assert len(plan.update) == 1
    assert len(plan.create) == 1
    assert len(plan.archive) == 1


def test_missing_board_id_treated_as_new():
    """If a task has a board_id that doesn't exist on the board, create it."""
    tf = TaskFile(tasks=[
        _make_task("Ghost", board_id="PVTI_nonexistent"),
    ])
    plan = build_sync_plan(tf, [])
    assert len(plan.create) == 1


def test_status_change_triggers_update():
    tf = TaskFile(tasks=[
        _make_task("Task", board_id="PVTI_1", status="Done"),
    ])
    board = [
        _make_board_item("PVTI_1", title="Task", status="In Progress"),
    ]
    plan = build_sync_plan(tf, board)
    assert len(plan.update) == 1


def test_description_change_triggers_update():
    tf = TaskFile(tasks=[
        _make_task("Task", board_id="PVTI_1", description="new description"),
    ])
    board = [
        _make_board_item("PVTI_1", title="Task", description="old description"),
    ]
    plan = build_sync_plan(tf, board)
    assert len(plan.update) == 1


def test_due_date_change_triggers_update():
    tf = TaskFile(tasks=[
        _make_task("Task", board_id="PVTI_1", due_date=date(2025, 12, 1)),
    ])
    board = [
        _make_board_item("PVTI_1", title="Task", due_date=date(2025, 6, 1)),
    ]
    plan = build_sync_plan(tf, board)
    assert len(plan.update) == 1


# --- Title fallback matching ---


def test_title_fallback_matches_unlinked_task():
    """A task with no board ID should match an existing board item by title."""
    tf = TaskFile(tasks=[
        _make_task("Fix the bug", status="In Progress", description="new desc"),
    ])
    board = [
        _make_board_item("PVTI_99", title="Fix the bug", status="Todo", description="old desc"),
    ]
    plan = build_sync_plan(tf, board)
    assert len(plan.create) == 0
    assert len(plan.update) == 1
    assert plan.update[0][1].item_id == "PVTI_99"
    # The task should have been assigned the board item's ID
    assert tf.tasks[0].board_item_id == "PVTI_99"


def test_title_fallback_matches_stale_id():
    """A task with a stale board ID should fall back to title matching."""
    tf = TaskFile(tasks=[
        _make_task("Fix the bug", board_id="PVTI_gone", status="In Progress"),
    ])
    board = [
        _make_board_item("PVTI_real", title="Fix the bug", status="Todo"),
    ]
    plan = build_sync_plan(tf, board)
    assert len(plan.create) == 0
    assert len(plan.update) == 1
    assert plan.update[0][1].item_id == "PVTI_real"


def test_title_fallback_no_match_creates():
    """If title doesn't match anything on the board, still create."""
    tf = TaskFile(tasks=[
        _make_task("Completely new task"),
    ])
    board = [
        _make_board_item("PVTI_1", title="Something else"),
    ]
    plan = build_sync_plan(tf, board)
    assert len(plan.create) == 1


def test_title_fallback_unchanged_when_matching():
    """A title-matched task with no field differences should be unchanged."""
    tf = TaskFile(tasks=[
        _make_task("Same task", status="Todo", description="same"),
    ])
    board = [
        _make_board_item("PVTI_1", title="Same task", status="Todo", description="same"),
    ]
    plan = build_sync_plan(tf, board)
    assert len(plan.unchanged) == 1
    assert len(plan.update) == 0
    assert len(plan.create) == 0
    assert tf.tasks[0].board_item_id == "PVTI_1"


def test_title_fallback_no_double_match():
    """Two tasks with the same title should not both match the same board item."""
    tf = TaskFile(tasks=[
        _make_task("Duplicate title", status="Todo"),
        _make_task("Duplicate title", status="In Progress"),
    ])
    board = [
        _make_board_item("PVTI_1", title="Duplicate title", status="Todo"),
    ]
    plan = build_sync_plan(tf, board)
    # First one matches, second one should be created
    matched = len(plan.update) + len(plan.unchanged)
    assert matched == 1
    assert len(plan.create) == 1
