"""Obsidian vault integration.

Creates per-paper markdown notes with YAML frontmatter and highlights,
and maintains a simple reading log.
"""

import logging
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Union
from urllib.parse import quote

from papers_workflow import config

log = logging.getLogger(__name__)

_DATAVIEW_TEMPLATE = """\
# Papers List

```dataview
TABLE date_added as "Added", date_read as "Completed", join(authors, ", ") as "Authors"
FROM "{folder}"
WHERE tags AND contains(tags, "read")
SORT date_read DESC
```
"""


_STATS_TEMPLATE = """\
# Reading Stats

## Monthly Breakdown

```dataview
TABLE length(rows) as "Papers"
FROM "{folder}"
WHERE tags AND contains(tags, "read")
GROUP BY dateformat(date_read, "yyyy-MM") as "Month"
SORT rows[0].date_read DESC
```

## Top Topics

```dataview
TABLE length(rows) as "Papers"
FROM "{folder}"
WHERE tags AND contains(tags, "read")
FLATTEN tags as tag
WHERE tag != "paper" AND tag != "read"
GROUP BY tag as "Topic"
SORT length(rows) DESC
LIMIT 15
```

## Recent Completions

```dataview
TABLE date_read as "Completed", join(authors, ", ") as "Authors"
FROM "{folder}"
WHERE tags AND contains(tags, "read")
SORT date_read DESC
LIMIT 10
```
"""


def _papers_dir() -> Optional[Path]:
    """Return the papers directory in the Obsidian vault, or None if unconfigured."""
    if not config.OBSIDIAN_VAULT_PATH:
        return None
    d = Path(config.OBSIDIAN_VAULT_PATH) / config.OBSIDIAN_PAPERS_FOLDER
    d.mkdir(parents=True, exist_ok=True)
    return d


def _inbox_dir() -> Optional[Path]:
    """Return the Inbox subdirectory in the papers folder, or None if unconfigured."""
    d = _papers_dir()
    if d is None:
        return None
    inbox = d / "Inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    return inbox


def _read_dir() -> Optional[Path]:
    """Return the Read subdirectory in the papers folder, or None if unconfigured."""
    d = _papers_dir()
    if d is None:
        return None
    rd = d / "Read"
    rd.mkdir(parents=True, exist_ok=True)
    return rd


def save_inbox_pdf(title: str, pdf_bytes: bytes) -> Optional[Path]:
    """Save an original PDF to the Obsidian vault Inbox folder.

    Returns the path to the saved file, or None if Obsidian is unconfigured.
    """
    inbox = _inbox_dir()
    if inbox is None:
        return None

    sanitized = _sanitize_note_name(title)
    pdf_path = inbox / f"{sanitized}.pdf"
    pdf_path.write_bytes(pdf_bytes)
    log.info("Saved PDF to Inbox: %s", pdf_path)
    return pdf_path


def delete_inbox_pdf(title: str) -> None:
    """Delete a PDF from the Inbox folder after processing."""
    inbox = _inbox_dir()
    if inbox is None:
        return

    sanitized = _sanitize_note_name(title)
    pdf_path = inbox / f"{sanitized}.pdf"
    if pdf_path.exists():
        pdf_path.unlink()
        log.info("Removed from Inbox: %s", pdf_path)


def delete_paper_note(title: str) -> None:
    """Delete an existing paper note if it exists (checks Read/ subfolder)."""
    rd = _read_dir()
    if rd is None:
        return

    sanitized = _sanitize_note_name(title)
    note_path = rd / f"{sanitized}.md"
    if note_path.exists():
        note_path.unlink()
        log.info("Deleted existing note: %s", note_path)

    # Also check papers root for notes created before subfolder migration
    d = _papers_dir()
    if d is None:
        return
    legacy_path = d / f"{sanitized}.md"
    if legacy_path.exists():
        legacy_path.unlink()
        log.info("Deleted legacy note: %s", legacy_path)


def save_annotated_pdf(title: str, pdf_bytes: bytes) -> Optional[Path]:
    """Save an annotated PDF to the Obsidian vault Read folder.

    Returns the path to the saved file, or None if Obsidian is unconfigured.
    """
    rd = _read_dir()
    if rd is None:
        return None

    sanitized = _sanitize_note_name(title)
    pdf_path = rd / f"{sanitized}.pdf"
    pdf_path.write_bytes(pdf_bytes)
    log.info("Saved annotated PDF: %s", pdf_path)
    return pdf_path


def ensure_dataview_note() -> None:
    """Create the Dataview reading log note if it doesn't exist."""
    d = _papers_dir()
    if d is None:
        return

    dataview_path = d / "Papers List.md"
    if not dataview_path.exists():
        dataview_path.write_text(
            _DATAVIEW_TEMPLATE.format(folder=config.OBSIDIAN_PAPERS_FOLDER)
        )
        log.info("Created Dataview note: %s", dataview_path)


def ensure_stats_note() -> None:
    """Create the Reading Stats dashboard note if it doesn't exist."""
    d = _papers_dir()
    if d is None:
        return

    stats_path = d / "Reading Stats.md"
    if not stats_path.exists():
        stats_path.write_text(
            _STATS_TEMPLATE.format(folder=config.OBSIDIAN_PAPERS_FOLDER)
        )
        log.info("Created Reading Stats note: %s", stats_path)


def _render_highlights_md(
    highlights: Optional[Union[List[str], Dict[int, List[str]]]],
) -> str:
    """Render highlights as markdown.

    Accepts either a flat list (legacy) or a page-based dict
    mapping page numbers to highlight lists.
    """
    if not highlights:
        return "*No highlights extracted.*"

    # Flat list — single section
    if isinstance(highlights, list):
        return "\n".join(f"- \"{h}\"" for h in highlights)

    # Page-based dict
    if len(highlights) == 1:
        # Single page — no headers needed
        items = next(iter(highlights.values()))
        return "\n".join(f"- \"{h}\"" for h in items)

    sections = []
    for page_num in sorted(highlights.keys()):
        items = highlights[page_num]
        sections.append(f"### Page {page_num}\n")
        sections.append("\n".join(f"- \"{h}\"" for h in items))
    return "\n\n".join(sections)


def create_paper_note(
    title: str,
    authors: List[str],
    date_added: str,
    zotero_item_key: str,
    highlights: Optional[Union[List[str], Dict[int, List[str]]]] = None,
    pdf_filename: Optional[str] = None,
    doi: str = "",
    abstract: str = "",
    url: str = "",
    publication_date: str = "",
    journal: str = "",
    summary: str = "",
    one_liner: str = "",
    topic_tags: Optional[List[str]] = None,
    citation_count: int = 0,
    key_learnings: Optional[List[str]] = None,
    open_questions: Optional[List[str]] = None,
    date_read: str = "",
) -> Optional[Path]:
    """Create an Obsidian note for a read paper in the Read subfolder.

    Returns the path to the created note, or None if Obsidian is unconfigured
    or the note already exists.
    """
    rd = _read_dir()
    if rd is None:
        return None

    sanitized = _sanitize_note_name(title)
    note_path = rd / f"{sanitized}.md"

    if note_path.exists():
        log.warning("Note already exists, skipping: %s", note_path)
        return None

    today = date_read[:10] if date_read else date.today().isoformat()

    # Build YAML frontmatter
    authors_yaml = "\n".join(f"  - {a}" for a in authors) if authors else "  - Unknown"
    all_tags = ["paper", "read"] + (topic_tags or [])
    tags_yaml = "\n".join(f"  - {t}" for t in all_tags)

    # Build highlights section
    highlights_md = _render_highlights_md(highlights)

    # Optional frontmatter lines
    optional = ""
    if doi:
        optional += f'\ndoi: "{_escape_yaml(doi)}"'
    if journal:
        optional += f'\njournal: "{_escape_yaml(journal)}"'
    if publication_date:
        optional += f'\npublication_date: "{publication_date}"'
    if url:
        optional += f'\nurl: "{_escape_yaml(url)}"'
    if citation_count:
        optional += f"\ncitation_count: {citation_count}"
    pdf_yaml = f'\npdf: "[[{pdf_filename}]]"' if pdf_filename else ""

    # Optional PDF embed in note body
    pdf_embed = f"![[{pdf_filename}]]\n\n" if pdf_filename else ""

    # One-liner blockquote at top
    oneliner_md = f"> {one_liner}\n\n" if one_liner else ""

    # Summary paragraph
    summary_md = f"{summary}\n\n" if summary else ""

    # Key ideas as bare bullet list (no header)
    if key_learnings:
        learnings_md = "\n".join(f"- {l}" for l in key_learnings) + "\n\n"
    else:
        learnings_md = ""

    # Optional open questions section
    if open_questions:
        questions_md = "## Open Questions\n\n" + "\n".join(f"- {q}" for q in open_questions) + "\n\n"
    else:
        questions_md = ""

    # Optional abstract section
    if abstract:
        abstract_md = f"## Abstract\n\n> {abstract}\n\n"
    else:
        abstract_md = ""

    content = f"""\
---
title: "{_escape_yaml(title)}"
authors:
{authors_yaml}
date_added: {date_added[:10]}
date_read: {today}
zotero: "zotero://select/library/items/{zotero_item_key}"{optional}{pdf_yaml}
tags:
{tags_yaml}
---

# {title}

{oneliner_md}{summary_md}{learnings_md}{questions_md}{pdf_embed}{abstract_md}## Highlights

{highlights_md}
"""
    note_path.write_text(content)
    log.info("Created Obsidian note: %s", note_path)
    return note_path


def append_to_reading_log(
    title: str,
    status: str,
    summary: str,
    date_read: str = "",
) -> None:
    """Append a paper entry to the Reading Log note.

    Flat bullet list, newest first. Creates the note if needed.
    Removes ALL existing entries for the same paper to prevent duplicates.
    """
    d = _papers_dir()
    if d is None:
        return

    log_path = d / "Reading Log.md"
    entry_date = date_read[:10] if date_read else date.today().isoformat()

    if not log_path.exists():
        log_path.write_text("# Reading Log\n\n")
        log.info("Created Reading Log: %s", log_path)

    existing = log_path.read_text()
    sanitized = _sanitize_note_name(title)
    bullet = f"- {entry_date} — **{status}**: [[{sanitized}|{title}]] — {summary}"

    # Remove ALL existing entries for this paper
    link_marker = f"[[{sanitized}|"
    lines = existing.split("\n")
    cleaned = [line for line in lines if link_marker not in line]

    if len(cleaned) < len(lines):
        # Had existing entries — insert updated one after header
        existing = "\n".join(cleaned)
        log.info("Removed %d old Reading Log entries for: %s", len(lines) - len(cleaned), title)

    # Insert right after the "# Reading Log" header
    header_end = existing.index("\n\n") + 2 if "\n\n" in existing else len(existing)
    updated = existing[:header_end] + bullet + "\n" + existing[header_end:]
    log_path.write_text(updated)
    log.info("Updated Reading Log: %s (%s)", title, status)


def get_obsidian_uri(title: str, subfolder: str = "Read") -> Optional[str]:
    """Return an obsidian:// URI that opens the paper note in the vault.

    Returns None if vault name is not configured.
    """
    if not config.OBSIDIAN_VAULT_NAME:
        return None

    sanitized = _sanitize_note_name(title)
    file_path = f"{config.OBSIDIAN_PAPERS_FOLDER}/{subfolder}/{sanitized}"
    return f"obsidian://open?vault={quote(config.OBSIDIAN_VAULT_NAME)}&file={quote(file_path)}"


def _themes_dir() -> Optional[Path]:
    """Return the Themes subdirectory in the papers folder, or None if unconfigured."""
    d = _papers_dir()
    if d is None:
        return None
    td = d / "Themes"
    td.mkdir(parents=True, exist_ok=True)
    return td


def create_themes_note(month: str, content: str) -> Optional[Path]:
    """Create a monthly themes note in Papers/Themes/.

    month should be like '2026-02'. Returns the path, or None if unconfigured.
    """
    td = _themes_dir()
    if td is None:
        return None

    note_path = td / f"{month}.md"

    themes_content = f"""\
---
tags:
  - themes
  - monthly-review
month: {month}
---

# Research Themes — {month}

{content}
"""
    note_path.write_text(themes_content)
    log.info("Created themes note: %s", note_path)
    return note_path


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
