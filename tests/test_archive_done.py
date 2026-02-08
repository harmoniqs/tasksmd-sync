from tasksmd_sync.writeback import remove_done_tasks


def test_remove_done_tasks(tmp_path):
    tasks_file = tmp_path / "TASKS.md"
    tasks_file.write_text("""
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
""", encoding="utf-8")

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
    tasks_file.write_text("""
## Todo
### Active Task
""", encoding="utf-8")

    modified = remove_done_tasks(tasks_file)
    assert modified is False
