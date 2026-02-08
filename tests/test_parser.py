"""Tests for the TASKS.md parser."""


from tasksmd_sync.parser import parse_tasks_md

SAMPLE_TASKS_MD = """\
# Tasks

## Todo

### Implement user authentication
<!-- id: PVTI_abc123 -->
- **Assignee:** @alice
- **Labels:** feature, security

We need to add OAuth2 support for the login flow.
This should support both GitHub and Google providers.

### Write API documentation
- **Labels:** docs

Document all public API endpoints.

## In Progress

### Fix memory leak in worker pool
<!-- id: PVTI_def456 -->
- **Assignee:** @bob
- **Labels:** bug, urgent

The worker pool is not releasing connections properly.

```python
pool.release(conn)
```

## Done

### Set up CI pipeline
<!-- id: PVTI_ghi789 -->
- **Assignee:** @charlie

Configured GitHub Actions for tests and linting.
"""


def test_parse_basic_structure():
    tf = parse_tasks_md(SAMPLE_TASKS_MD)
    assert len(tf.tasks) == 4


def test_parse_task_titles():
    tf = parse_tasks_md(SAMPLE_TASKS_MD)
    titles = [t.title for t in tf.tasks]
    assert titles == [
        "Implement user authentication",
        "Write API documentation",
        "Fix memory leak in worker pool",
        "Set up CI pipeline",
    ]


def test_parse_statuses():
    tf = parse_tasks_md(SAMPLE_TASKS_MD)
    statuses = [t.status for t in tf.tasks]
    assert statuses == ["Todo", "Todo", "In Progress", "Done"]


def test_parse_board_ids():
    tf = parse_tasks_md(SAMPLE_TASKS_MD)
    ids = [t.board_item_id for t in tf.tasks]
    assert ids == ["PVTI_abc123", None, "PVTI_def456", "PVTI_ghi789"]


def test_parse_assignees():
    tf = parse_tasks_md(SAMPLE_TASKS_MD)
    assignees = [t.assignee for t in tf.tasks]
    assert assignees == ["alice", None, "bob", "charlie"]


def test_parse_labels():
    tf = parse_tasks_md(SAMPLE_TASKS_MD)
    assert tf.tasks[0].labels == ["feature", "security"]
    assert tf.tasks[1].labels == ["docs"]
    assert tf.tasks[2].labels == ["bug", "urgent"]
    assert tf.tasks[3].labels == []


def test_parse_descriptions():
    tf = parse_tasks_md(SAMPLE_TASKS_MD)
    # First task: multi-line description
    assert "OAuth2 support" in tf.tasks[0].description
    assert "GitHub and Google" in tf.tasks[0].description

    # Second task: single-line
    assert "Document all public API" in tf.tasks[1].description

    # Third task: description with code block
    assert "pool.release(conn)" in tf.tasks[2].description

    # Fourth task
    assert "GitHub Actions" in tf.tasks[3].description


def test_by_status_grouping():
    tf = parse_tasks_md(SAMPLE_TASKS_MD)
    groups = tf.by_status
    assert len(groups["Todo"]) == 2
    assert len(groups["In Progress"]) == 1
    assert len(groups["Done"]) == 1


def test_by_board_id():
    tf = parse_tasks_md(SAMPLE_TASKS_MD)
    by_id = tf.by_board_id
    assert "PVTI_abc123" in by_id
    assert "PVTI_def456" in by_id
    assert "PVTI_ghi789" in by_id
    assert len(by_id) == 3


def test_unlinked_tasks():
    tf = parse_tasks_md(SAMPLE_TASKS_MD)
    unlinked = tf.unlinked_tasks
    assert len(unlinked) == 1
    assert unlinked[0].title == "Write API documentation"


def test_empty_file():
    tf = parse_tasks_md("")
    assert len(tf.tasks) == 0


def test_file_with_only_heading():
    tf = parse_tasks_md("# Tasks\n\n## Todo\n")
    assert len(tf.tasks) == 0


def test_status_normalization():
    content = """\
## To Do

### Task A

Description A

## In-Progress

### Task B

Description B

## Completed

### Task C

Description C
"""
    tf = parse_tasks_md(content)
    assert tf.tasks[0].status == "Todo"
    assert tf.tasks[1].status == "In Progress"
    assert tf.tasks[2].status == "Done"


def test_minimal_task():
    content = """\
## Todo

### Just a title
"""
    tf = parse_tasks_md(content)
    assert len(tf.tasks) == 1
    assert tf.tasks[0].title == "Just a title"
    assert tf.tasks[0].status == "Todo"
    assert tf.tasks[0].description == ""
    assert tf.tasks[0].assignee is None
    assert tf.tasks[0].labels == []
    assert tf.tasks[0].board_item_id is None


def test_metadata_in_any_order():
    content = """\
## Todo

### Flexible metadata
<!-- id: PVTI_flex -->
- **Labels:** a, b
- **Assignee:** @zara

The description starts here.
"""
    tf = parse_tasks_md(content)
    t = tf.tasks[0]
    assert t.board_item_id == "PVTI_flex"
    assert t.assignee == "zara"
    assert t.labels == ["a", "b"]
    assert "description starts here" in t.description
