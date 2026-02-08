from tasksmd_sync.writeback import remove_done_tasks


def test_remove_done_tasks(tmp_path):
    tasks_file = tmp_path / "TASKS.md"
    tasks_file.write_text(
        """
# Project

## Todo
### Active Task
Keep this.

## Done
### Completed Task
Remove this.

### Another Done Task
Remove this too.

## Future
### Planned Task
Keep this.
""",
        encoding="utf-8",
    )

    modified = remove_done_tasks(tasks_file)
    assert modified is True

    content = tasks_file.read_text(encoding="utf-8")
    assert "Active Task" in content
    assert "Completed Task" not in content
    assert "Another Done Task" not in content
    assert "Planned Task" in content
    assert "## Done" in content


def test_remove_done_tasks_no_done(tmp_path):
    tasks_file = tmp_path / "TASKS.md"
    tasks_file.write_text(
        """
## Todo
### Active Task
""",
        encoding="utf-8",
    )

    modified = remove_done_tasks(tasks_file)
    assert modified is False


def test_remove_done_tasks_idempotent(tmp_path):
    """Running remove_done_tasks twice should be idempotent."""
    tasks_file = tmp_path / "TASKS.md"
    tasks_file.write_text(
        """\
# Tasks

## Todo

### Active Task
Keep this.

## Done

### Completed Task
Remove this.
""",
        encoding="utf-8",
    )

    # First run removes Done tasks
    modified = remove_done_tasks(tasks_file)
    assert modified is True
    content_after_first = tasks_file.read_text(encoding="utf-8")
    assert "Completed Task" not in content_after_first
    assert "Active Task" in content_after_first

    # Second run should be a no-op
    modified = remove_done_tasks(tasks_file)
    assert modified is False
    content_after_second = tasks_file.read_text(encoding="utf-8")
    assert content_after_first == content_after_second


def test_remove_done_tasks_empty_done_section(tmp_path):
    """An empty Done section should not cause issues."""
    tasks_file = tmp_path / "TASKS.md"
    tasks_file.write_text(
        """\
# Tasks

## Todo

### Active Task
Keep this.

## Done

""",
        encoding="utf-8",
    )

    modified = remove_done_tasks(tasks_file)
    assert modified is False
    content = tasks_file.read_text(encoding="utf-8")
    assert "Active Task" in content
