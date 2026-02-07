"""Parser for TASKS.md files."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .models import Task, TaskFile

# Regex patterns
RE_STATUS_HEADING = re.compile(r"^##\s+(.+)$")
RE_TASK_HEADING = re.compile(r"^###\s+(.+)$")
RE_BOARD_ID = re.compile(r"^<!--\s*id:\s*(\S+)\s*-->$")
RE_ASSIGNEE = re.compile(r"^-\s+\*\*Assignee:\*\*\s*@?(\S+)\s*$")
RE_LABELS = re.compile(r"^-\s+\*\*Labels:\*\*\s*(.+)$")
RE_DUE = re.compile(r"^-\s+\*\*Due:\*\*\s*(\d{4}-\d{2}-\d{2})\s*$")

# Set of metadata patterns for detecting the boundary between metadata and description
METADATA_PATTERNS = [RE_BOARD_ID, RE_ASSIGNEE, RE_LABELS, RE_DUE]


def parse_tasks_md(content: str, source_path: str = "") -> TaskFile:
    """Parse a TASKS.md string into a TaskFile model."""
    lines = content.splitlines()
    tasks: list[Task] = []
    current_status: str | None = None
    current_task: _TaskBuilder | None = None

    for line in lines:
        # Check for status heading (## ...)
        m = RE_STATUS_HEADING.match(line)
        if m:
            if current_task:
                tasks.append(current_task.build())
                current_task = None
            current_status = _normalize_status(m.group(1).strip())
            continue

        # Check for task heading (### ...)
        m = RE_TASK_HEADING.match(line)
        if m:
            if current_task:
                tasks.append(current_task.build())
            if current_status is None:
                current_status = "Todo"
            current_task = _TaskBuilder(title=m.group(1).strip(), status=current_status)
            continue

        # If we're inside a task block, parse metadata or accumulate description
        if current_task is not None:
            current_task.feed_line(line)

    # Don't forget the last task
    if current_task is not None:
        tasks.append(current_task.build())

    return TaskFile(tasks=tasks, source_path=source_path)


def parse_tasks_file(path: str | Path) -> TaskFile:
    """Parse a TASKS.md file from disk."""
    p = Path(path)
    content = p.read_text(encoding="utf-8")
    return parse_tasks_md(content, source_path=str(p))


def _normalize_status(raw: str) -> str:
    """Normalize status strings to canonical forms."""
    lowered = raw.lower().strip()
    mapping = {
        "todo": "Todo",
        "to do": "Todo",
        "to-do": "Todo",
        "in progress": "In Progress",
        "in-progress": "In Progress",
        "inprogress": "In Progress",
        "done": "Done",
        "completed": "Done",
        "closed": "Done",
    }
    return mapping.get(lowered, raw.strip())


class _TaskBuilder:
    """Accumulates lines for a single task block and builds a Task."""

    def __init__(self, title: str, status: str) -> None:
        self.title = title
        self.status = status
        self.board_item_id: str | None = None
        self.assignee: str | None = None
        self.labels: list[str] = []
        self.due_date: date | None = None
        self._desc_lines: list[str] = []
        self._in_metadata = True

    def feed_line(self, line: str) -> None:
        if self._in_metadata:
            # Try each metadata pattern
            m = RE_BOARD_ID.match(line)
            if m:
                self.board_item_id = m.group(1)
                return

            m = RE_ASSIGNEE.match(line)
            if m:
                self.assignee = m.group(1)
                return

            m = RE_LABELS.match(line)
            if m:
                raw = m.group(1)
                self.labels = [l.strip() for l in raw.split(",") if l.strip()]
                return

            m = RE_DUE.match(line)
            if m:
                self.due_date = date.fromisoformat(m.group(1))
                return

            # Blank lines in metadata zone are skipped
            if line.strip() == "":
                return

            # Non-metadata, non-blank line — we've left the metadata zone
            self._in_metadata = False
            self._desc_lines.append(line)
        else:
            self._desc_lines.append(line)

    def build(self) -> Task:
        desc = "\n".join(self._desc_lines).strip()
        return Task(
            title=self.title,
            status=self.status,
            description=desc,
            board_item_id=self.board_item_id,
            assignee=self.assignee,
            labels=self.labels,
            due_date=self.due_date,
        )
