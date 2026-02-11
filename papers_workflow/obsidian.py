"""Obsidian vault integration.

Creates per-paper markdown notes with YAML frontmatter and highlights,
and maintains a simple reading log.
"""

import logging
import shutil
from datetime import date
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from papers_workflow import config

log = logging.getLogger(__name__)

_DATAVIEW_TEMPLATE = """\
# Papers List

```dataview
TABLE date_added as "Added", choice(date_read, date_read, date_leafed) as "Completed", join(authors, ", ") as "Authors", choice(contains(tags, "leafed"), "Leafed", "Read") as "Status"
FROM "{folder}"
WHERE tags AND (contains(tags, "read") OR contains(tags, "leafed"))
SORT choice(date_read, date_read, date_leafed) DESC
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


def _leafed_dir() -> Optional[Path]:
    """Return the Leafed subdirectory in the papers folder, or None if unconfigured."""
    d = _papers_dir()
    if d is None:
        return None
    ld = d / "Leafed"
    ld.mkdir(parents=True, exist_ok=True)
    return ld


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


def move_inbox_pdf_to_leafed(title: str) -> Optional[Path]:
    """Move a PDF from the Inbox folder to the Leafed folder.

    Uses copy-then-delete for safety. Returns the destination path,
    or None if the source PDF doesn't exist or Obsidian is unconfigured.
    """
    inbox = _inbox_dir()
    ld = _leafed_dir()
    if inbox is None or ld is None:
        return None

    sanitized = _sanitize_note_name(title)
    src = inbox / f"{sanitized}.pdf"
    if not src.exists():
        log.info("No Inbox PDF to move for '%s'", title)
        return None

    dst = ld / f"{sanitized}.pdf"
    shutil.copy2(str(src), str(dst))
    if dst.exists():
        src.unlink()
        log.info("Moved PDF from Inbox to Leafed: %s", dst)
        return dst

    log.warning("Failed to copy PDF to Leafed for '%s'", title)
    return None


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


def create_paper_note(
    title: str,
    authors: List[str],
    date_added: str,
    zotero_item_key: str,
    highlights: Optional[List[str]] = None,
    pdf_filename: Optional[str] = None,
    doi: str = "",
    abstract: str = "",
    url: str = "",
    publication_date: str = "",
    journal: str = "",
    summary: str = "",
    takeaway: str = "",
    topic_tags: Optional[List[str]] = None,
    citation_count: int = 0,
    related_papers: Optional[List[dict]] = None,
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

    today = date.today().isoformat()

    # Build YAML frontmatter
    authors_yaml = "\n".join(f"  - {a}" for a in authors) if authors else "  - Unknown"
    all_tags = ["paper", "read"] + (topic_tags or [])
    tags_yaml = "\n".join(f"  - {t}" for t in all_tags)

    # Build highlights section
    if highlights:
        highlights_md = "\n".join(f"- \"{h}\"" for h in highlights)
    else:
        highlights_md = "*No highlights extracted.*"

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

    # Short takeaway as blockquote, then longer summary
    takeaway_md = f"> {takeaway}\n\n" if takeaway else ""
    summary_md = f"{summary}\n\n" if summary else ""

    # Optional abstract section
    if abstract:
        abstract_md = f"## Abstract\n\n> {abstract}\n\n"
    else:
        abstract_md = ""

    # Related papers section
    if related_papers:
        related_lines = []
        for rp in related_papers:
            rp_title = rp.get("title", "")
            rp_year = rp.get("year") or ""
            rp_url = rp.get("url", "")
            year_str = f" ({rp_year})" if rp_year else ""
            if rp_url:
                related_lines.append(f"- [{rp_title}]({rp_url}){year_str}")
            else:
                related_lines.append(f"- {rp_title}{year_str}")
        related_md = "## Related Papers\n\n" + "\n".join(related_lines) + "\n\n"
    else:
        related_md = ""

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

{takeaway_md}{summary_md}{pdf_embed}{abstract_md}## Highlights

{highlights_md}

{related_md}"""
    note_path.write_text(content)
    log.info("Created Obsidian note: %s", note_path)
    return note_path


def create_leafed_note(
    title: str,
    authors: List[str],
    date_added: str,
    zotero_item_key: str,
    pdf_filename: Optional[str] = None,
    doi: str = "",
    url: str = "",
    publication_date: str = "",
    journal: str = "",
    topic_tags: Optional[List[str]] = None,
    citation_count: int = 0,
) -> Optional[Path]:
    """Create a minimal Obsidian note for a leafed-through paper in the Leafed subfolder."""
    ld = _leafed_dir()
    if ld is None:
        return None

    sanitized = _sanitize_note_name(title)
    note_path = ld / f"{sanitized}.md"

    if note_path.exists():
        log.warning("Note already exists, skipping: %s", note_path)
        return None

    today = date.today().isoformat()

    authors_yaml = "\n".join(f"  - {a}" for a in authors) if authors else "  - Unknown"
    all_tags = ["paper", "leafed"] + (topic_tags or [])
    tags_yaml = "\n".join(f"  - {t}" for t in all_tags)

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
    pdf_embed = f"![[{pdf_filename}]]\n\n" if pdf_filename else ""

    content = f"""\
---
title: "{_escape_yaml(title)}"
authors:
{authors_yaml}
date_added: {date_added[:10]}
date_leafed: {today}
zotero: "zotero://select/library/items/{zotero_item_key}"{optional}{pdf_yaml}
tags:
{tags_yaml}
---

# {title}

{pdf_embed}## Quick Takeaways

-
"""
    note_path.write_text(content)
    log.info("Created leafed note: %s", note_path)
    return note_path


def append_to_reading_log(
    title: str,
    status: str,
    summary: str,
) -> None:
    """Append a paper entry to the Reading Log note.

    Flat bullet list, newest first. Creates the note if needed.
    Status should be "Read" or "Leafed".
    """
    d = _papers_dir()
    if d is None:
        return

    log_path = d / "Reading Log.md"
    today = date.today().isoformat()

    if not log_path.exists():
        log_path.write_text("# Reading Log\n\n")
        log.info("Created Reading Log: %s", log_path)

    existing = log_path.read_text()
    sanitized = _sanitize_note_name(title)
    bullet = f"- {today} — **{status}**: [[{sanitized}|{title}]] — {summary}\n"

    # Insert right after the "# Reading Log" header
    header_end = existing.index("\n\n") + 2 if "\n\n" in existing else len(existing)
    updated = existing[:header_end] + bullet + existing[header_end:]

    log_path.write_text(updated)
    log.info("Appended to Reading Log: %s (%s)", title, status)


def get_obsidian_uri(title: str, subfolder: str = "Read") -> Optional[str]:
    """Return an obsidian:// URI that opens the paper note in the vault.

    subfolder should be "Read" or "Leafed".
    Returns None if vault name is not configured.
    """
    if not config.OBSIDIAN_VAULT_NAME:
        return None

    sanitized = _sanitize_note_name(title)
    file_path = f"{config.OBSIDIAN_PAPERS_FOLDER}/{subfolder}/{sanitized}"
    return f"obsidian://open?vault={quote(config.OBSIDIAN_VAULT_NAME)}&file={quote(file_path)}"


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
