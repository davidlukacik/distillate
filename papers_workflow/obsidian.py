"""Obsidian vault integration.

Creates per-paper markdown notes with YAML frontmatter and highlights,
and maintains a simple reading log.
"""

import logging
from datetime import date
from pathlib import Path
from typing import List, Optional

from papers_workflow import config

log = logging.getLogger(__name__)

_DATAVIEW_TEMPLATE = """\
# Papers Dataview

```dataview
TABLE date_added as "Added", date_read as "Read", join(authors, ", ") as "Authors"
FROM "{folder}"
WHERE tags AND contains(tags, "read")
SORT date_read DESC
```
"""


def _papers_dir() -> Optional[Path]:
    """Return the papers directory in the Obsidian vault, or None if unconfigured."""
    if not config.OBSIDIAN_VAULT_PATH:
        return None
    d = Path(config.OBSIDIAN_VAULT_PATH) / config.OBSIDIAN_PAPERS_FOLDER
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_reading_logs() -> None:
    """Create the Dataview reading log note if it doesn't exist."""
    d = _papers_dir()
    if d is None:
        return

    dataview_path = d / "Papers Dataview.md"
    if not dataview_path.exists():
        dataview_path.write_text(
            _DATAVIEW_TEMPLATE.format(folder=config.OBSIDIAN_PAPERS_FOLDER)
        )
        log.info("Created Dataview reading log: %s", dataview_path)

    simple_path = d / config.OBSIDIAN_LOG_FILE
    if not simple_path.exists():
        simple_path.write_text("# Reading Log\n\n")
        log.info("Created simple reading log: %s", simple_path)


def create_paper_note(
    title: str,
    authors: List[str],
    date_added: str,
    zotero_item_key: str,
    highlights: Optional[List[str]] = None,
) -> Optional[Path]:
    """Create an Obsidian note for a read paper.

    Returns the path to the created note, or None if Obsidian is unconfigured
    or the note already exists.
    """
    d = _papers_dir()
    if d is None:
        return None

    sanitized = _sanitize_note_name(title)
    note_path = d / f"{sanitized}.md"

    if note_path.exists():
        log.warning("Note already exists, skipping: %s", note_path)
        return None

    today = date.today().isoformat()

    # Build YAML frontmatter
    authors_yaml = "\n".join(f"  - {a}" for a in authors) if authors else "  - Unknown"
    tags_yaml = "\n".join(f"  - {t}" for t in ["paper", "read"])

    # Build highlights section
    if highlights:
        highlights_md = "\n".join(f"- \"{h}\"" for h in highlights)
    else:
        highlights_md = "*No highlights extracted.*"

    content = f"""\
---
title: "{_escape_yaml(title)}"
authors:
{authors_yaml}
date_added: {date_added[:10]}
date_read: {today}
zotero: "zotero://select/items/{zotero_item_key}"
tags:
{tags_yaml}
---

# {title}

## Highlights

{highlights_md}

## Notes

"""
    note_path.write_text(content)
    log.info("Created Obsidian note: %s", note_path)
    return note_path


def append_to_reading_log(title: str, authors: List[str]) -> None:
    """Append an entry to the simple reading log."""
    d = _papers_dir()
    if d is None:
        return

    log_path = d / config.OBSIDIAN_LOG_FILE
    if not log_path.exists():
        log_path.write_text("# Reading Log\n\n")

    today = date.today().isoformat()
    if authors:
        authors_str = ", ".join(authors[:3])
        if len(authors) > 3:
            authors_str += " et al."
    else:
        authors_str = "Unknown"

    entry = f"- {today} — [[{title}]] ({authors_str})\n"

    with open(log_path, "a") as f:
        f.write(entry)

    log.info("Appended to reading log: %s", title)


def _sanitize_note_name(name: str) -> str:
    """Sanitize a string for use as an Obsidian note filename."""
    bad_chars = '<>:"/\\|?*#^[]'
    result = name
    for c in bad_chars:
        result = result.replace(c, "")
    result = " ".join(result.split())
    return result[:200].strip()


def _escape_yaml(s: str) -> str:
    """Escape a string for use in YAML double-quoted context."""
    return s.replace("\\", "\\\\").replace('"', '\\"')
