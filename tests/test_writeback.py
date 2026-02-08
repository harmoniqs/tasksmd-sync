"""Tests for the ID writeback into TASKS.md."""

from pathlib import Path

from tasksmd_sync.writeback import writeback_ids


SAMPLE = """\
# Tasks

## Todo

### Task with existing ID
<!-- id: PVTI_existing -->
- **Labels:** feature

Description here.

### Task without ID
- **Assignee:** @alice
- **Labels:** bug

Needs an ID.

### Another without ID

Just a description.

## In Progress

### In progress task
<!-- id: PVTI_inprog -->
- **Due:** 2025-06-01

Working on it.
"""


def test_writeback_injects_id(tmp_path: Path):
    f = tmp_path / "TASKS.md"
    f.write_text(SAMPLE)

    modified = writeback_ids(f, {"Task without ID": "PVTI_new123"})
    assert modified is True

    content = f.read_text()
    lines = content.splitlines()

    # Find the "Task without ID" heading and check the next line
    idx = next(i for i, l in enumerate(lines) if "### Task without ID" in l)
    assert lines[idx + 1] == "<!-- id: PVTI_new123 -->"
    # Original metadata should still follow
    assert "**Assignee:**" in lines[idx + 2]


def test_writeback_multiple_ids(tmp_path: Path):
    f = tmp_path / "TASKS.md"
    f.write_text(SAMPLE)

    id_map = {
        "Task without ID": "PVTI_new1",
        "Another without ID": "PVTI_new2",
    }
    modified = writeback_ids(f, id_map)
    assert modified is True

    content = f.read_text()
    assert "<!-- id: PVTI_new1 -->" in content
    assert "<!-- id: PVTI_new2 -->" in content


def test_writeback_replaces_stale_id(tmp_path: Path):
    f = tmp_path / "TASKS.md"
    f.write_text(SAMPLE)

    # Writeback a different ID for a task that already has one
    modified = writeback_ids(f, {"Task with existing ID": "PVTI_replacement"})
    assert modified is True

    content = f.read_text()
    # Old ID should be gone, new one present
    assert "<!-- id: PVTI_existing -->" not in content
    assert "<!-- id: PVTI_replacement -->" in content


def test_writeback_skips_when_id_already_correct(tmp_path: Path):
    f = tmp_path / "TASKS.md"
    f.write_text(SAMPLE)

    # Writeback the same ID that already exists
    modified = writeback_ids(f, {"Task with existing ID": "PVTI_existing"})
    assert modified is False

    content = f.read_text()
    assert "<!-- id: PVTI_existing -->" in content


def test_writeback_no_changes_when_empty_map(tmp_path: Path):
    f = tmp_path / "TASKS.md"
    f.write_text(SAMPLE)

    modified = writeback_ids(f, {})
    assert modified is False


def test_writeback_no_changes_when_title_not_found(tmp_path: Path):
    f = tmp_path / "TASKS.md"
    f.write_text(SAMPLE)

    modified = writeback_ids(f, {"Nonexistent task": "PVTI_xxx"})
    assert modified is False


def test_writeback_preserves_structure(tmp_path: Path):
    f = tmp_path / "TASKS.md"
    f.write_text(SAMPLE)

    writeback_ids(f, {"Task without ID": "PVTI_injected"})
    content = f.read_text()

    # Existing IDs should be untouched
    assert "<!-- id: PVTI_existing -->" in content
    assert "<!-- id: PVTI_inprog -->" in content

    # All original headings should still be present
    assert "### Task with existing ID" in content
    assert "### Task without ID" in content
    assert "### Another without ID" in content
    assert "### In progress task" in content

    # Descriptions should be preserved
    assert "Description here." in content
    assert "Needs an ID." in content
    assert "Working on it." in content
