"""Write board item IDs back into a TASKS.md file."""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

RE_TASK_HEADING = re.compile(r"^###\s+(.+)$")
RE_BOARD_ID = re.compile(r"^<!--\s*id:\s*(\S+)\s*-->$")


def writeback_ids(
    tasks_path: str | Path,
    id_map: dict[str, str],
) -> bool:
    """Inject or replace board item IDs in a TASKS.md file.

    For tasks with no ID comment: injects a new `<!-- id: ... -->` line.
    For tasks with a stale ID: replaces the existing comment with the new ID.

    Args:
        tasks_path: Path to the TASKS.md file
        id_map: Mapping of task title -> board item ID

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

    # Determine line ending from original file
    eol = "\n"
    if lines and lines[0].endswith("\r\n"):
        eol = "\r\n"

    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip("\n").rstrip("\r")
        m = RE_TASK_HEADING.match(stripped)

        if m:
            title = m.group(1).strip()
            new_lines.append(line)
            i += 1

            # Scan ahead past blank lines to find an existing ID comment
            blank_buffer: list[str] = []
            has_id = False
            existing_id: str | None = None

            while i < len(lines):
                next_stripped = lines[i].rstrip("\n").rstrip("\r").strip()
                if next_stripped == "":
                    blank_buffer.append(lines[i])
                    i += 1
                    continue
                id_match = RE_BOARD_ID.match(next_stripped)
                if id_match:
                    has_id = True
                    existing_id = id_match.group(1)
                break

            if title in id_map:
                new_id = id_map[title]

                if has_id and existing_id == new_id:
                    # ID already correct — keep as-is
                    new_lines.extend(blank_buffer)
                    logger.debug(
                        "[WRITEBACK] '%s' already has correct ID %s", title, new_id
                    )
                elif has_id and existing_id != new_id:
                    # Replace stale ID
                    new_lines.extend(blank_buffer)
                    new_lines.append(f"<!-- id: {new_id} -->{eol}")
                    i += 1  # skip the old ID line
                    modified = True
                    logger.debug(
                        "[WRITEBACK] '%s' replaced stale ID %s -> %s",
                        title, existing_id, new_id,
                    )
                else:
                    # No ID yet — inject one
                    new_lines.append(f"<!-- id: {new_id} -->{eol}")
                    # Put the blank lines back after the injected ID
                    new_lines.extend(blank_buffer)
                    modified = True
                    logger.debug(
                        "[WRITEBACK] '%s' injected new ID %s", title, new_id
                    )
            else:
                # Not in id_map — preserve everything as-is
                new_lines.extend(blank_buffer)
        else:
            new_lines.append(line)
            i += 1

    if modified:
        path.write_text("".join(new_lines), encoding="utf-8")

    return modified
