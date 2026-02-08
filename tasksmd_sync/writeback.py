"""Write board item IDs back into a TASKS.md file."""

from __future__ import annotations

import re
from pathlib import Path

RE_TASK_HEADING = re.compile(r"^###\s+(.+)$")
RE_BOARD_ID = re.compile(r"^<!--\s*id:\s*\S+\s*-->$")


def writeback_ids(
    tasks_path: str | Path,
    id_map: dict[str, str],
) -> bool:
    """Inject board item IDs into a TASKS.md file.

    Args:
        tasks_path: Path to the TASKS.md file
        id_map: Mapping of task title -> board item ID to inject

    Returns:
        True if the file was modified, False if no changes needed.
    """
    if not id_map:
        return False

    path = Path(tasks_path)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines: list[str] = []
    modified = False
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip("\n").rstrip("\r")
        m = RE_TASK_HEADING.match(stripped)

        if m:
            title = m.group(1).strip()
            new_lines.append(line)
            i += 1

            # Check if the next non-blank line is already an ID comment
            has_id = False
            while i < len(lines):
                next_stripped = lines[i].rstrip("\n").rstrip("\r")
                if next_stripped.strip() == "":
                    # Blank line — keep it and keep looking
                    new_lines.append(lines[i])
                    i += 1
                    continue
                if RE_BOARD_ID.match(next_stripped.strip()):
                    has_id = True
                break

            # If no ID yet and we have one to inject, insert it
            if not has_id and title in id_map:
                item_id = id_map[title]
                # Determine line ending from original file
                eol = "\n"
                if lines and lines[0].endswith("\r\n"):
                    eol = "\r\n"
                new_lines.append(f"<!-- id: {item_id} -->{eol}")
                modified = True
        else:
            new_lines.append(line)
            i += 1

    if modified:
        path.write_text("".join(new_lines), encoding="utf-8")

    return modified
