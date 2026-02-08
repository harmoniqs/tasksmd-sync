"""CLI entry point for tasksmd-sync."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .github_projects import GitHubProjectClient
from .parser import parse_tasks_file
from .sync import execute_sync
from .writeback import writeback_ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tasksmd-sync",
        description="One-way sync from TASKS.md to a GitHub Project board.",
    )
    parser.add_argument(
        "tasks_file",
        type=str,
        help="Path to the TASKS.md file",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="GitHub token with Projects scope (or set GITHUB_TOKEN env var)",
    )
    parser.add_argument(
        "--org",
        type=str,
        required=True,
        help="GitHub organization login (e.g. 'harmoniqs')",
    )
    parser.add_argument(
        "--project-number",
        type=int,
        required=True,
        help="GitHub Project board number",
    )
    parser.add_argument(
        "--repo-label",
        type=str,
        default=None,
        help="Label to scope this repo's items (for archive detection). "
        "Only board items with this label will be archived when removed from TASKS.md.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would happen without making changes",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--writeback",
        action="store_true",
        help="Write board item IDs back into the TASKS.md file after sync",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Write sync results to a JSON file (useful for CI)",
    )

    args = parser.parse_args(argv)

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(message)s",
    )

    # Resolve token
    token = args.token
    if not token:
        import os
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("TASKSMD_GITHUB_TOKEN")
    if not token:
        logging.error(
            "No GitHub token provided. Use --token or set GITHUB_TOKEN / TASKSMD_GITHUB_TOKEN"
        )
        return 1

    # Validate file exists
    tasks_path = Path(args.tasks_file)
    if not tasks_path.is_file():
        logging.error("TASKS.md file not found: %s", tasks_path)
        return 1

    # Parse
    logging.info("Parsing %s ...", tasks_path)
    task_file = parse_tasks_file(tasks_path)
    logging.info("Found %d tasks", len(task_file.tasks))

    # Sync
    client = GitHubProjectClient(
        token=token,
        org=args.org,
        project_number=args.project_number,
    )
    try:
        result = execute_sync(
            client=client,
            task_file=task_file,
            repo_label=args.repo_label,
            dry_run=args.dry_run,
        )
    finally:
        client.close()

    # Writeback IDs into TASKS.md
    if args.writeback:
        all_ids = {**result.matched_ids, **result.created_ids}
        if args.dry_run:
            if all_ids:
                logging.info(
                    "[DRY RUN] Would write back %d ID(s) to %s",
                    len(all_ids),
                    tasks_path,
                )
            else:
                logging.info("[DRY RUN] No IDs to write back to %s", tasks_path)
        elif all_ids:
            if writeback_ids(tasks_path, all_ids):
                logging.info(
                    "Wrote %d board item ID(s) back into %s",
                    len(all_ids),
                    tasks_path,
                )
            else:
                logging.info("No new IDs to write back (all tasks already have IDs)")
        else:
            logging.info("No new IDs to write back")

    # Report
    logging.info(
        "Sync complete: %d created, %d updated, %d archived, %d unchanged",
        result.created,
        result.updated,
        result.archived,
        result.unchanged,
    )
    if result.errors:
        logging.warning("Errors encountered:")
        for err in result.errors:
            logging.warning("  - %s", err)

    # Write JSON output for CI
    if args.output_json:
        out = {
            "created": result.created,
            "updated": result.updated,
            "archived": result.archived,
            "unchanged": result.unchanged,
            "errors": result.errors,
            "created_ids": result.created_ids,
        }
        Path(args.output_json).write_text(json.dumps(out, indent=2))
        logging.info("Results written to %s", args.output_json)

    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
