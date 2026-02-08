"""Data models for tasks parsed from TASKS.md."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Task:
    """A single task parsed from a TASKS.md file."""

    title: str
    status: str
    description: str = ""
    board_item_id: str | None = None
    assignee: str | None = None
    labels: list[str] = field(default_factory=list)

    @property
    def has_board_id(self) -> bool:
        return self.board_item_id is not None

    def metadata_dict(self) -> dict:
        """Return a dict of non-None metadata fields for comparison."""
        d: dict = {
            "title": self.title,
            "status": self.status,
            "description": self.description.strip(),
        }
        if self.assignee:
            d["assignee"] = self.assignee
        if self.labels:
            d["labels"] = sorted(self.labels)
        return d


@dataclass
class TaskFile:
    """A complete parsed TASKS.md file."""

    tasks: list[Task] = field(default_factory=list)
    source_path: str = ""

    @property
    def by_status(self) -> dict[str, list[Task]]:
        groups: dict[str, list[Task]] = {}
        for task in self.tasks:
            groups.setdefault(task.status, []).append(task)
        return groups

    @property
    def by_board_id(self) -> dict[str, Task]:
        return {t.board_item_id: t for t in self.tasks if t.board_item_id is not None}

    @property
    def unlinked_tasks(self) -> list[Task]:
        return [t for t in self.tasks if not t.has_board_id]
