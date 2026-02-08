"""Tests for execute_sync with mocked GitHubProjectClient.

These tests verify the full sync execution path, including API calls
for both DraftIssue and real Issue content types.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from tasksmd_sync.github_projects import GitHubProjectClient, ProjectField, ProjectItem
from tasksmd_sync.models import Task, TaskFile
from tasksmd_sync.sync import _apply_task_fields, _needs_update, execute_sync

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(title, status="Todo", board_id=None, **kwargs):
    return Task(title=title, status=status, board_item_id=board_id, **kwargs)


def _make_board_item(item_id, title="", status="Todo", **kwargs):
    return ProjectItem(item_id=item_id, title=title, status=status, **kwargs)


def _stub_fields():
    """Return a minimal field dict matching a typical board."""
    return {
        "Status": ProjectField(
            id="F_status",
            name="Status",
            data_type="SINGLE_SELECT",
            options={
                "Todo": "OPT_todo",
                "In Progress": "OPT_ip",
                "Done": "OPT_done",
            },
        ),
    }


def _mock_client(board_items: list[ProjectItem] | None = None) -> MagicMock:
    """Create a mock GitHubProjectClient pre-configured for testing."""
    client = MagicMock(spec=GitHubProjectClient)
    client.org = "harmoniqs"
    client.list_items.return_value = board_items or []
    client.get_fields.return_value = _stub_fields()
    client.add_draft_issue.return_value = "PVTI_new"
    client.create_issue.return_value = "I_new"
    client.add_item_to_project.return_value = "PVTI_new_issue"
    client.resolve_user_id.return_value = "U_alice123"
    client.resolve_label_ids.return_value = ["LA_bug", "LA_docs"]
    return client


# ===================================================================
# execute_sync — DraftIssue path
# ===================================================================


class TestExecuteSyncDraftIssue:
    """Tests for execute_sync when board items are DraftIssues."""

    def test_create_draft_issue(self):
        """New tasks should be created as draft issues with status set."""
        client = _mock_client()
        tf = TaskFile(tasks=[_make_task("New task", status="Todo")])

        result = execute_sync(client, tf)

        assert result.created == 1
        assert result.updated == 0
        client.add_draft_issue.assert_called_once_with("New task", "")
        client.update_item_field_single_select.assert_called_once_with(
            "PVTI_new", "F_status", "OPT_todo"
        )

    def test_create_does_not_call_assignee_or_label_mutations(self):
        """Created draft issues should NOT attempt assignee/label sync."""
        client = _mock_client()
        tf = TaskFile(
            tasks=[
                _make_task("Task", assignee="alice", labels=["bug"]),
            ]
        )

        execute_sync(client, tf)

        client.resolve_user_id.assert_not_called()
        client.set_issue_assignees.assert_not_called()
        client.resolve_label_ids.assert_not_called()
        client.set_issue_labels.assert_not_called()

    def test_create_records_id_in_result(self):
        """Created item IDs should appear in result.created_ids."""
        client = _mock_client()
        tf = TaskFile(tasks=[_make_task("My task")])

        result = execute_sync(client, tf)

        assert result.created_ids == {"My task": "PVTI_new"}

    def test_update_draft_issue_body(self):
        """Updating a DraftIssue should call update_draft_issue_body."""
        board = [
            _make_board_item(
                "PVTI_1",
                title="Old title",
                status="Todo",
                content_type="DraftIssue",
                content_id="DI_1",
            ),
        ]
        client = _mock_client(board)
        tf = TaskFile(
            tasks=[
                _make_task("New title", board_id="PVTI_1", status="In Progress"),
            ]
        )

        result = execute_sync(client, tf)

        assert result.updated == 1
        client.update_draft_issue_body.assert_called_once_with("DI_1", "New title", "")
        client.update_issue.assert_not_called()

    def test_update_draft_does_not_call_assignee_mutations(self):
        """Updating a DraftIssue should NOT attempt assignee sync."""
        board = [
            _make_board_item(
                "PVTI_1",
                title="Task",
                status="Todo",
                content_type="DraftIssue",
                content_id="DI_1",
                description="old",
            ),
        ]
        client = _mock_client(board)
        tf = TaskFile(
            tasks=[
                _make_task(
                    "Task", board_id="PVTI_1", description="new", assignee="alice"
                ),
            ]
        )

        execute_sync(client, tf)

        client.resolve_user_id.assert_not_called()
        client.set_issue_assignees.assert_not_called()

    def test_update_draft_does_not_call_label_mutations(self):
        """Updating a DraftIssue should NOT attempt label sync."""
        board = [
            _make_board_item(
                "PVTI_1",
                title="Task",
                status="Todo",
                content_type="DraftIssue",
                content_id="DI_1",
                description="old",
            ),
        ]
        client = _mock_client(board)
        tf = TaskFile(
            tasks=[
                _make_task(
                    "Task", board_id="PVTI_1", description="new", labels=["bug"]
                ),
            ]
        )

        execute_sync(client, tf)

        client.resolve_label_ids.assert_not_called()
        client.set_issue_labels.assert_not_called()

    def test_unchanged_draft_issue_no_api_calls(self):
        """An unchanged DraftIssue should not produce any write API calls."""
        board = [
            _make_board_item(
                "PVTI_1",
                title="Task",
                status="Todo",
                description="desc",
                content_type="DraftIssue",
                content_id="DI_1",
            ),
        ]
        client = _mock_client(board)
        tf = TaskFile(
            tasks=[
                _make_task(
                    "Task", board_id="PVTI_1", status="Todo", description="desc"
                ),
            ]
        )

        result = execute_sync(client, tf)

        assert result.unchanged == 1
        assert result.updated == 0
        client.add_draft_issue.assert_not_called()
        client.update_draft_issue_body.assert_not_called()
        client.update_item_field_single_select.assert_not_called()

    def test_archive_item(self):
        """Board items not in TASKS.md should be archived."""
        board = [_make_board_item("PVTI_gone", title="Deleted task")]
        client = _mock_client(board)
        tf = TaskFile(tasks=[])

        result = execute_sync(client, tf)

        assert result.archived == 1
        client.archive_item.assert_called_once_with("PVTI_gone")

    def test_create_error_recorded(self):
        """Errors during creation should be captured in result.errors."""
        client = _mock_client()
        client.add_draft_issue.side_effect = RuntimeError("API error")
        tf = TaskFile(tasks=[_make_task("Broken task")])

        result = execute_sync(client, tf)

        assert result.created == 0
        assert len(result.errors) == 1
        assert "Broken task" in result.errors[0]

    def test_draft_idempotent_with_assignee_and_labels(self):
        """A DraftIssue with matching fields but different assignee/labels
        should be considered unchanged (idempotent)."""
        board = [
            _make_board_item(
                "PVTI_1",
                title="Task",
                status="Todo",
                content_type="DraftIssue",
                content_id="DI_1",
                assignee=None,
                labels=[],
            ),
        ]
        client = _mock_client(board)
        tf = TaskFile(
            tasks=[
                _make_task(
                    "Task",
                    board_id="PVTI_1",
                    status="Todo",
                    assignee="alice",
                    labels=["bug", "docs"],
                ),
            ]
        )

        result = execute_sync(client, tf)

        assert result.unchanged == 1
        assert result.updated == 0


# ===================================================================
# execute_sync — real Issue path
# ===================================================================


class TestExecuteSyncIssue:
    """Tests for execute_sync when board items are real Issues."""

    def test_create_issue_when_repo_provided(self):
        """New tasks should create real Issues when repo_owner/repo_name are given."""
        client = _mock_client()
        tf = TaskFile(
            tasks=[_make_task("New issue task", status="Todo", assignee="alice")]
        )

        result = execute_sync(
            client,
            tf,
            repo_owner="harmoniqs",
            repo_name="tasksmd-sync",
        )

        assert result.created == 1
        client.create_issue.assert_called_once_with(
            "harmoniqs", "tasksmd-sync", "New issue task", ""
        )
        client.add_item_to_project.assert_called_once_with("I_new")
        client.update_item_field_single_select.assert_called_once_with(
            "PVTI_new_issue", "F_status", "OPT_todo"
        )
        client.set_issue_assignees.assert_called_once_with("I_new", ["U_alice123"])

    def test_convert_draft_issue_to_issue_when_repo_provided(self):
        """DraftIssues should be converted to Issues when repo info is provided."""
        board = [
            _make_board_item(
                "PVTI_1",
                title="Old draft",
                status="Todo",
                content_type="DraftIssue",
                content_id="DI_1",
            ),
        ]
        client = _mock_client(board)
        tf = TaskFile(
            tasks=[_make_task("Old draft", board_id="PVTI_1", status="In Progress")]
        )

        result = execute_sync(
            client,
            tf,
            repo_owner="harmoniqs",
            repo_name="tasksmd-sync",
        )

        assert result.updated == 1
        client.create_issue.assert_called_once_with(
            "harmoniqs", "tasksmd-sync", "Old draft", ""
        )
        client.add_item_to_project.assert_called_once_with("I_new")
        client.archive_item.assert_any_call("PVTI_1")
        client.update_issue.assert_called_once_with("I_new", "Old draft", "")
        # Ensure writeback uses the new item ID
        assert result.created_ids["Old draft"] == "PVTI_new_issue"

    def test_convert_draft_issue_even_when_unchanged(self):
        """DraftIssues should be converted even if no field diffs (unchanged path)."""
        board = [
            _make_board_item(
                "PVTI_1",
                title="Task",
                status="Todo",
                content_type="DraftIssue",
                content_id="DI_1",
                description="desc",
            ),
        ]
        client = _mock_client(board)
        tf = TaskFile(
            tasks=[
                _make_task("Task", board_id="PVTI_1", status="Todo", description="desc")
            ]
        )

        result = execute_sync(
            client,
            tf,
            repo_owner="harmoniqs",
            repo_name="tasksmd-sync",
        )

        # Even though the fields match, the DraftIssue is converted
        client.create_issue.assert_called_once_with(
            "harmoniqs", "tasksmd-sync", "Task", "desc"
        )
        client.add_item_to_project.assert_called_once_with("I_new")
        client.archive_item.assert_any_call("PVTI_1")
        client.update_issue.assert_called_once_with("I_new", "Task", "desc")
        assert result.updated == 1
        assert result.unchanged == 0
        assert result.created_ids["Task"] == "PVTI_new_issue"

    def test_update_issue_body(self):
        """Updating a real Issue should call update_issue (not update_draft_issue_body)."""
        board = [
            _make_board_item(
                "PVTI_1",
                title="Old title",
                status="Todo",
                content_type="Issue",
                content_id="I_1",
            ),
        ]
        client = _mock_client(board)
        tf = TaskFile(
            tasks=[
                _make_task("New title", board_id="PVTI_1", status="In Progress"),
            ]
        )

        result = execute_sync(client, tf)

        assert result.updated == 1
        client.update_issue.assert_called_once_with("I_1", "New title", "")
        client.update_draft_issue_body.assert_not_called()

    def test_update_issue_assignee(self):
        """Assignee changes on a real Issue should call resolve + set."""
        board = [
            _make_board_item(
                "PVTI_1",
                title="Task",
                status="Todo",
                content_type="Issue",
                content_id="I_1",
                assignee=None,
            ),
        ]
        client = _mock_client(board)
        tf = TaskFile(
            tasks=[
                _make_task("Task", board_id="PVTI_1", assignee="alice"),
            ]
        )

        result = execute_sync(client, tf)

        assert result.updated == 1
        client.resolve_user_id.assert_called_once_with("alice")
        client.set_issue_assignees.assert_called_once_with("I_1", ["U_alice123"])

    def test_update_issue_labels(self):
        """Label changes on a real Issue should call resolve + set."""
        board = [
            _make_board_item(
                "PVTI_1",
                title="Task",
                status="Todo",
                content_type="Issue",
                content_id="I_1",
                labels=[],
                repo_name="tasksmd-sync",
            ),
        ]
        client = _mock_client(board)
        tf = TaskFile(
            tasks=[
                _make_task("Task", board_id="PVTI_1", labels=["bug", "docs"]),
            ]
        )

        result = execute_sync(client, tf)

        assert result.updated == 1
        client.resolve_label_ids.assert_called_once_with(
            "harmoniqs", "tasksmd-sync", ["bug", "docs"]
        )
        client.set_issue_labels.assert_called_once_with("I_1", ["LA_bug", "LA_docs"])

    def test_update_issue_no_assignee_call_when_matching(self):
        """No assignee mutation when the assignee already matches."""
        board = [
            _make_board_item(
                "PVTI_1",
                title="Task",
                status="Todo",
                content_type="Issue",
                content_id="I_1",
                assignee="alice",
                description="old",
            ),
        ]
        client = _mock_client(board)
        tf = TaskFile(
            tasks=[
                _make_task(
                    "Task",
                    board_id="PVTI_1",
                    assignee="alice",
                    description="new",
                ),
            ]
        )

        execute_sync(client, tf)

        # Should be updated (description changed) but NOT trigger assignee mutation
        client.resolve_user_id.assert_not_called()
        client.set_issue_assignees.assert_not_called()

    def test_update_issue_no_label_call_when_matching(self):
        """No label mutation when labels already match."""
        board = [
            _make_board_item(
                "PVTI_1",
                title="Task",
                status="Todo",
                content_type="Issue",
                content_id="I_1",
                labels=["bug", "docs"],
                description="old",
            ),
        ]
        client = _mock_client(board)
        tf = TaskFile(
            tasks=[
                _make_task(
                    "Task",
                    board_id="PVTI_1",
                    labels=["docs", "bug"],
                    description="new",
                ),
            ]
        )

        execute_sync(client, tf)

        client.resolve_label_ids.assert_not_called()
        client.set_issue_labels.assert_not_called()

    def test_issue_unchanged_when_all_fields_match(self):
        """A real Issue with all fields matching should be unchanged."""
        board = [
            _make_board_item(
                "PVTI_1",
                title="Task",
                status="Done",
                content_type="Issue",
                content_id="I_1",
                assignee="alice",
                labels=["bug"],
                description="desc",
            ),
        ]
        client = _mock_client(board)
        tf = TaskFile(
            tasks=[
                _make_task(
                    "Task",
                    board_id="PVTI_1",
                    status="Done",
                    assignee="alice",
                    labels=["bug"],
                    description="desc",
                ),
            ]
        )

        result = execute_sync(client, tf)

        assert result.unchanged == 1
        assert result.updated == 0
        client.update_issue.assert_not_called()
        client.set_issue_assignees.assert_not_called()
        client.set_issue_labels.assert_not_called()

    def test_unresolvable_user_does_not_crash(self):
        """If resolve_user_id returns None, assignee sync should be skipped."""
        board = [
            _make_board_item(
                "PVTI_1",
                title="Task",
                status="Todo",
                content_type="Issue",
                content_id="I_1",
                assignee=None,
            ),
        ]
        client = _mock_client(board)
        client.resolve_user_id.return_value = None
        tf = TaskFile(
            tasks=[
                _make_task("Task", board_id="PVTI_1", assignee="ghost_user"),
            ]
        )

        result = execute_sync(client, tf)

        assert result.updated == 1
        client.resolve_user_id.assert_called_once_with("ghost_user")
        client.set_issue_assignees.assert_not_called()

    def test_unresolvable_labels_does_not_crash(self):
        """If resolve_label_ids returns [], label sync should be skipped."""
        board = [
            _make_board_item(
                "PVTI_1",
                title="Task",
                status="Todo",
                content_type="Issue",
                content_id="I_1",
                labels=[],
            ),
        ]
        client = _mock_client(board)
        client.resolve_label_ids.return_value = []
        tf = TaskFile(
            tasks=[
                _make_task("Task", board_id="PVTI_1", labels=["nonexistent"]),
            ]
        )

        result = execute_sync(client, tf)

        assert result.updated == 1
        client.set_issue_labels.assert_not_called()

    def test_update_error_recorded(self):
        """Errors during update should be captured in result.errors."""
        board = [
            _make_board_item(
                "PVTI_1",
                title="Task",
                status="Todo",
                content_type="Issue",
                content_id="I_1",
                description="old",
            ),
        ]
        client = _mock_client(board)
        client.update_item_field_single_select.side_effect = RuntimeError("API boom")
        tf = TaskFile(
            tasks=[
                _make_task("Task", board_id="PVTI_1", description="new"),
            ]
        )

        result = execute_sync(client, tf)

        assert result.updated == 0
        assert len(result.errors) == 1
        assert "Task" in result.errors[0]


# ===================================================================
# execute_sync — mixed operations
# ===================================================================


class TestExecuteSyncMixed:
    """Tests for mixed create/update/archive/unchanged scenarios."""

    def test_mixed_content_types(self):
        """A sync with both DraftIssue and Issue items should route correctly."""
        board = [
            _make_board_item(
                "PVTI_1",
                title="Draft task",
                status="Todo",
                content_type="DraftIssue",
                content_id="DI_1",
                description="old",
            ),
            _make_board_item(
                "PVTI_2",
                title="Real task",
                status="Todo",
                content_type="Issue",
                content_id="I_1",
                assignee=None,
            ),
            _make_board_item("PVTI_3", title="To archive"),
        ]
        client = _mock_client(board)
        tf = TaskFile(
            tasks=[
                _make_task("Draft task", board_id="PVTI_1", description="new"),
                _make_task("Real task", board_id="PVTI_2", assignee="alice"),
                _make_task("Brand new task"),
            ]
        )

        result = execute_sync(client, tf)

        assert result.created == 1
        assert result.updated == 2
        assert result.archived == 1

        # Draft path
        client.update_draft_issue_body.assert_called_once_with(
            "DI_1", "Draft task", "new"
        )

        # Issue path
        client.update_issue.assert_called_once_with("I_1", "Real task", "")
        client.resolve_user_id.assert_called_once_with("alice")
        client.set_issue_assignees.assert_called_once()

        # Create + archive
        client.add_draft_issue.assert_called_once()
        client.archive_item.assert_called_once_with("PVTI_3")

    def test_dry_run_makes_no_write_calls(self):
        """dry_run=True should report counts but make no write calls."""
        board = [
            _make_board_item(
                "PVTI_1",
                title="Task",
                status="Todo",
                content_type="Issue",
                content_id="I_1",
                description="old",
            ),
        ]
        client = _mock_client(board)
        tf = TaskFile(
            tasks=[
                _make_task("Task", board_id="PVTI_1", description="new"),
                _make_task("New task"),
            ]
        )

        result = execute_sync(client, tf, dry_run=True)

        assert result.created == 1
        assert result.updated == 1
        client.add_draft_issue.assert_not_called()
        client.update_issue.assert_not_called()
        client.update_draft_issue_body.assert_not_called()
        client.update_item_field_single_select.assert_not_called()
        client.archive_item.assert_not_called()

    def test_archive_scoped_by_repo_label(self):
        """Only items with the repo label should be archived."""
        board = [
            _make_board_item("PVTI_1", title="Ours", labels=["myrepo"]),
            _make_board_item("PVTI_2", title="Theirs", labels=["other"]),
        ]
        client = _mock_client(board)
        tf = TaskFile(tasks=[])

        result = execute_sync(client, tf, repo_label="myrepo")

        assert result.archived == 1
        client.archive_item.assert_called_once_with("PVTI_1")


# ===================================================================
# _needs_update — exhaustive edge cases
# ===================================================================


class TestNeedsUpdate:
    """Direct tests for the _needs_update comparison function."""

    def test_identical_returns_false(self):
        task = _make_task("T", status="Todo", description="d")
        board = _make_board_item("X", title="T", status="Todo", description="d")
        assert _needs_update(task, board) is False

    def test_title_diff(self):
        task = _make_task("New", status="Todo")
        board = _make_board_item("X", title="Old", status="Todo")
        assert _needs_update(task, board) is True

    def test_status_case_insensitive(self):
        task = _make_task("T", status="In Progress")
        board = _make_board_item("X", title="T", status="in progress")
        assert _needs_update(task, board) is False

    def test_empty_task_status_matches_anything(self):
        """If task has no status, it shouldn't trigger a diff."""
        task = _make_task("T", status="")
        board = _make_board_item("X", title="T", status="In Progress")
        assert _needs_update(task, board) is False

    def test_description_whitespace_normalised(self):
        task = _make_task("T", description="  hello  ")
        board = _make_board_item("X", title="T", description="hello")
        assert _needs_update(task, board) is False

    def test_assignee_ignored_when_content_type_none(self):
        """If content_type is not set, assignee diffs are ignored."""
        task = _make_task("T", assignee="alice")
        board = _make_board_item("X", title="T", assignee=None, content_type=None)
        assert _needs_update(task, board) is False

    def test_assignee_ignored_for_pull_request(self):
        """PullRequest content type should also skip assignee comparison."""
        task = _make_task("T", assignee="alice")
        board = _make_board_item(
            "X", title="T", assignee=None, content_type="PullRequest"
        )
        assert _needs_update(task, board) is False

    def test_labels_ignored_when_content_type_none(self):
        """If content_type is not set, label diffs are ignored."""
        task = _make_task("T", labels=["bug"])
        board = _make_board_item("X", title="T", labels=[], content_type=None)
        assert _needs_update(task, board) is False

    def test_no_diff_when_task_has_no_assignee(self):
        """If task has no assignee, board's assignee shouldn't cause a diff."""
        task = _make_task("T")
        board = _make_board_item("X", title="T", content_type="Issue", assignee="bob")
        assert _needs_update(task, board) is False

    def test_no_diff_when_task_has_no_labels(self):
        """If task has no labels, board's labels shouldn't cause a diff."""
        task = _make_task("T")
        board = _make_board_item("X", title="T", content_type="Issue", labels=["bug"])
        assert _needs_update(task, board) is False

    def test_label_order_irrelevant(self):
        """Labels should be compared as sets (order doesn't matter)."""
        task = _make_task("T", labels=["docs", "bug"])
        board = _make_board_item(
            "X", title="T", content_type="Issue", labels=["bug", "docs"]
        )
        assert _needs_update(task, board) is False


# ===================================================================
# _apply_task_fields — unit tests
# ===================================================================


class TestApplyTaskFields:
    """Direct tests for _apply_task_fields routing logic."""

    def test_sets_status(self):
        client = _mock_client()
        fields = _stub_fields()
        task = _make_task("T", status="In Progress")

        _apply_task_fields(client, "PVTI_1", task, fields)

        client.update_item_field_single_select.assert_called_once_with(
            "PVTI_1", "F_status", "OPT_ip"
        )

    def test_status_not_found_logs_warning(self):
        """Unknown status values should warn, not crash."""
        client = _mock_client()
        fields = _stub_fields()
        task = _make_task("T", status="Blocked")

        _apply_task_fields(client, "PVTI_1", task, fields)

        client.update_item_field_single_select.assert_not_called()

    def test_no_board_item_skips_assignee_labels(self):
        """When board_item is None (new item), skip assignee/label sync."""
        client = _mock_client()
        fields = _stub_fields()
        task = _make_task("T", assignee="alice", labels=["bug"])

        _apply_task_fields(client, "PVTI_1", task, fields, board_item=None)

        client.resolve_user_id.assert_not_called()
        client.set_issue_assignees.assert_not_called()
        client.resolve_label_ids.assert_not_called()
        client.set_issue_labels.assert_not_called()

    def test_draft_issue_skips_assignee_labels(self):
        """DraftIssue board_item should skip assignee/label sync."""
        client = _mock_client()
        fields = _stub_fields()
        task = _make_task("T", assignee="alice", labels=["bug"])
        bi = _make_board_item(
            "PVTI_1",
            title="T",
            content_type="DraftIssue",
            content_id="DI_1",
            assignee=None,
            labels=[],
        )

        _apply_task_fields(client, "PVTI_1", task, fields, board_item=bi)

        client.resolve_user_id.assert_not_called()
        client.set_issue_assignees.assert_not_called()

    def test_issue_syncs_assignee(self):
        """Real Issue with different assignee should call mutations."""
        client = _mock_client()
        fields = _stub_fields()
        task = _make_task("T", assignee="alice")
        bi = _make_board_item(
            "PVTI_1",
            title="T",
            content_type="Issue",
            content_id="I_1",
            assignee=None,
        )

        _apply_task_fields(client, "PVTI_1", task, fields, board_item=bi)

        client.resolve_user_id.assert_called_once_with("alice")
        client.set_issue_assignees.assert_called_once_with("I_1", ["U_alice123"])

    def test_issue_syncs_labels(self):
        """Real Issue with different labels should call mutations."""
        client = _mock_client()
        fields = _stub_fields()
        task = _make_task("T", labels=["bug", "docs"])
        bi = _make_board_item(
            "PVTI_1",
            title="T",
            content_type="Issue",
            content_id="I_1",
            labels=[],
            repo_name="tasksmd-sync",
        )

        _apply_task_fields(client, "PVTI_1", task, fields, board_item=bi)

        client.resolve_label_ids.assert_called_once_with(
            "harmoniqs", "tasksmd-sync", ["bug", "docs"]
        )
        client.set_issue_labels.assert_called_once_with("I_1", ["LA_bug", "LA_docs"])

    def test_issue_skips_assignee_when_already_matching(self):
        """Real Issue with matching assignee should not call mutations."""
        client = _mock_client()
        fields = _stub_fields()
        task = _make_task("T", assignee="alice")
        bi = _make_board_item(
            "PVTI_1",
            title="T",
            content_type="Issue",
            content_id="I_1",
            assignee="alice",
        )

        _apply_task_fields(client, "PVTI_1", task, fields, board_item=bi)

        client.resolve_user_id.assert_not_called()
        client.set_issue_assignees.assert_not_called()

    def test_issue_skips_labels_when_already_matching(self):
        """Real Issue with matching labels should not call mutations."""
        client = _mock_client()
        fields = _stub_fields()
        task = _make_task("T", labels=["bug", "docs"])
        bi = _make_board_item(
            "PVTI_1",
            title="T",
            content_type="Issue",
            content_id="I_1",
            labels=["docs", "bug"],
        )

        _apply_task_fields(client, "PVTI_1", task, fields, board_item=bi)

        client.resolve_label_ids.assert_not_called()
        client.set_issue_labels.assert_not_called()

    def test_issue_without_content_id_skips_assignee_labels(self):
        """Issue with no content_id should skip assignee/label sync."""
        client = _mock_client()
        fields = _stub_fields()
        task = _make_task("T", assignee="alice", labels=["bug"])
        bi = _make_board_item(
            "PVTI_1",
            title="T",
            content_type="Issue",
            content_id=None,
        )

        _apply_task_fields(client, "PVTI_1", task, fields, board_item=bi)

        client.resolve_user_id.assert_not_called()
        client.set_issue_labels.assert_not_called()


# ===================================================================
# _parse_item_node
# ===================================================================


class TestParseItemNode:
    """Tests for GitHubProjectClient._parse_item_node."""

    def _parse(self, node, status_field=None):
        """Call _parse_item_node as an unbound method (no API needed)."""
        # We instantiate with dummy values — _parse_item_node doesn't use them
        client = GitHubProjectClient.__new__(GitHubProjectClient)
        return client._parse_item_node(node, status_field)

    def test_parse_draft_issue(self):
        node = {
            "id": "PVTI_1",
            "content": {
                "__typename": "DraftIssue",
                "id": "DI_1",
                "title": "My draft",
                "body": "Some body",
                "assignees": {"nodes": [{"login": "alice"}]},
            },
            "fieldValues": {"nodes": []},
        }
        item = self._parse(node)
        assert item.item_id == "PVTI_1"
        assert item.content_type == "DraftIssue"
        assert item.content_id == "DI_1"
        assert item.title == "My draft"
        assert item.description == "Some body"
        assert item.assignee == "alice"
        assert item.labels == []  # DraftIssues don't have labels

    def test_parse_issue_with_labels(self):
        node = {
            "id": "PVTI_2",
            "content": {
                "__typename": "Issue",
                "id": "I_1",
                "title": "Real issue",
                "body": "Issue body",
                "assignees": {"nodes": [{"login": "bob"}]},
                "labels": {"nodes": [{"name": "bug"}, {"name": "docs"}]},
            },
            "fieldValues": {"nodes": []},
        }
        item = self._parse(node)
        assert item.content_type == "Issue"
        assert item.content_id == "I_1"
        assert item.assignee == "bob"
        assert item.labels == ["bug", "docs"]

    def test_parse_no_assignees(self):
        node = {
            "id": "PVTI_3",
            "content": {
                "__typename": "Issue",
                "id": "I_2",
                "title": "No assignee",
                "body": "",
                "assignees": {"nodes": []},
                "labels": {"nodes": []},
            },
            "fieldValues": {"nodes": []},
        }
        item = self._parse(node)
        assert item.assignee is None
        assert item.labels == []

    def test_parse_status_from_field_values(self):
        status_field = ProjectField(
            id="F_s",
            name="Status",
            data_type="SINGLE_SELECT",
            options={"Todo": "OPT_1"},
        )
        node = {
            "id": "PVTI_4",
            "content": {
                "__typename": "DraftIssue",
                "id": "DI_2",
                "title": "With status",
                "body": "",
                "assignees": {"nodes": []},
            },
            "fieldValues": {
                "nodes": [
                    {
                        "field": {"name": "Status"},
                        "name": "In Progress",
                    },
                ]
            },
        }
        item = self._parse(node, status_field)
        assert item.status == "In Progress"

    def test_parse_empty_content(self):
        """Items with no content (e.g. redacted) should not crash."""
        node = {
            "id": "PVTI_6",
            "content": None,
            "fieldValues": {"nodes": []},
        }
        item = self._parse(node)
        assert item.item_id == "PVTI_6"
        assert item.content_type is None
        assert item.title == ""

    def test_parse_null_body(self):
        """Null body should become empty string."""
        node = {
            "id": "PVTI_7",
            "content": {
                "__typename": "DraftIssue",
                "id": "DI_3",
                "title": "No body",
                "body": None,
                "assignees": {"nodes": []},
            },
            "fieldValues": {"nodes": []},
        }
        item = self._parse(node)
        assert item.description == ""


# ===================================================================
# execute_sync — unarchive path
# ===================================================================


class TestExecuteSyncUnarchive:
    """Tests for unarchive behaviour in execute_sync."""

    def test_unarchive_reopens_issue(self):
        """Unarchiving a task should reopen the underlying Issue."""
        # Board is empty (the item is archived), so the task triggers unarchive
        client = _mock_client(board_items=[])
        # After unarchive, get_item returns the now-visible item
        client.get_item.return_value = _make_board_item(
            "PVTI_archived",
            title="Revived task",
            status="Done",
            content_type="Issue",
            content_id="I_archived",
        )
        tf = TaskFile(
            tasks=[
                _make_task("Revived task", board_id="PVTI_archived", status="Todo"),
            ]
        )

        result = execute_sync(client, tf)

        assert result.unarchived == 1
        client.unarchive_item.assert_called_once_with("PVTI_archived")
        client.reopen_issue.assert_called_once_with("I_archived")
        # Status should also be applied
        client.update_item_field_single_select.assert_called_once_with(
            "PVTI_archived", "F_status", "OPT_todo"
        )

    def test_unarchive_draft_issue_does_not_reopen(self):
        """Unarchiving a DraftIssue should NOT call reopen_issue."""
        client = _mock_client(board_items=[])
        client.get_item.return_value = _make_board_item(
            "PVTI_archived",
            title="Draft task",
            content_type="DraftIssue",
            content_id="DI_1",
        )
        tf = TaskFile(
            tasks=[
                _make_task("Draft task", board_id="PVTI_archived", status="Todo"),
            ]
        )

        result = execute_sync(client, tf)

        assert result.unarchived == 1
        client.unarchive_item.assert_called_once_with("PVTI_archived")
        client.reopen_issue.assert_not_called()

    def test_unarchive_reopen_failure_does_not_crash(self):
        """If reopening the Issue fails, unarchive should still succeed."""
        client = _mock_client(board_items=[])
        client.get_item.return_value = _make_board_item(
            "PVTI_archived",
            title="Task",
            content_type="Issue",
            content_id="I_1",
        )
        client.reopen_issue.side_effect = RuntimeError("API error")
        tf = TaskFile(
            tasks=[
                _make_task("Task", board_id="PVTI_archived", status="Todo"),
            ]
        )

        result = execute_sync(client, tf)

        assert result.unarchived == 1
        assert len(result.errors) == 0  # reopen failure is warning-logged, not an error
