# Papers Workflow — Architecture Plan

## Overview

A **one-shot script** (designed for cron/launchd scheduling) that bridges **Zotero**, **reMarkable**, and **Obsidian** to automate a paper reading workflow. Uses **Zotero tags** for status tracking and **collections** for topic organization.

```
  Zotero                    reMarkable                    Zotero + Obsidian
  ┌──────────────┐          ┌───────────────────┐         ┌──────────────────┐
  │  New paper    │── PDF ─▶│  /To Read folder   │         │  Annotated PDF   │
  │  added via    │  tag:   │                   │         │  tag: read       │
  │  browser ext  │  to-read│  User reads &     │         └──────────────────┘
  │  (any device) │         │  highlights, then │                ▲
  └──────────────┘          │  moves to /Read   │                │
                            │                   │         ┌──────────────────┐
                            │  /Read folder     │── PDF ─▶│  Obsidian note   │
                            │                   │  +.rm   │  with highlights │
                            │  /Archive folder  │◀── mv ──└──────────────────┘
                            └───────────────────┘
```

### Zotero organization strategy

- **Tags for workflow state**: `to-read`, `read` (color-code these in the Zotero app for visual scanning)
- **Collections for topics**: "Transformers", "RLHF", etc. — organized independently by the user
- Tags are API-friendly (`?tag=to-read`), lightweight to update, and don't interfere with collection organization
- **New papers only** — the script ignores items already in Zotero before first run. To re-process an old paper, remove its `to-read`/`read` tag.

### Flow in detail

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                      ONE-SHOT SCRIPT (run via cron/launchd)                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─── Step 1: Poll Zotero for new papers ─────────────────────────────┐    │
│  │                                                                     │    │
│  │  1. GET /users/{id}/items?limit=0                                   │    │
│  │     → Compare Last-Modified-Version to stored version               │    │
│  │                                                                     │    │
│  │  2. If changed:                                                     │    │
│  │     GET /users/{id}/items?format=versions&since={stored_ver}        │    │
│  │     → Get changed item keys                                        │    │
│  │                                                                     │    │
│  │  3. Fetch full items, filter for NEW top-level items                │    │
│  │     (no "to-read" or "read" tag, has PDF attachment)                │    │
│  │                                                                     │    │
│  │  4. For each new paper:                                             │    │
│  │     a. GET children → find PDF attachment                           │    │
│  │     b. GET attachment /file → download PDF bytes                    │    │
│  │     c. Upload PDF to reMarkable /To Read/ folder                    │    │
│  │     d. Tag item as "to-read" in Zotero                              │    │
│  │     e. Record mapping: {zotero_item_key → remarkable_doc_name}      │    │
│  │                                                                     │    │
│  │  5. Update stored Zotero library version                            │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                            │
│  ┌─── Step 2: Poll reMarkable for read papers ────────────────────────┐    │
│  │                                                                     │    │
│  │  1. List documents in reMarkable /Read/ folder                      │    │
│  │                                                                     │    │
│  │  2. For each tracked document found in /Read/:                      │    │
│  │     a. Download document (PDF + .rm annotation files)               │    │
│  │     b. Render annotations onto PDF (using rmrl)                     │    │
│  │     c. Extract highlighted text passages (using remarks)            │    │
│  │     d. Upload annotated PDF to Zotero (replace original)            │    │
│  │     e. Change Zotero tag from "to-read" → "read"                   │    │
│  │     f. Create Obsidian note with metadata + extracted highlights    │    │
│  │     g. Move document to reMarkable /Archive/ folder                 │    │
│  │     h. Mark document as processed in state                          │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                            │
│  ┌─── Step 3: Notify ─────────────────────────────────────────────────┐    │
│  │                                                                     │    │
│  │  If anything happened, send a macOS notification:                   │    │
│  │  "Papers Workflow: 2 sent to reMarkable, 1 synced back"            │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                            │
│  Exit.                                                                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Script Architecture

### Language & approach

**Python 3.9+** — best library ecosystem for both APIs (`requests` for Zotero, `rmapi` CLI wrapper for reMarkable, `rmrl` for annotation rendering, `remarks` for highlight text extraction). **One-shot execution** — the script runs once and exits, scheduled by cron or launchd.

### Project structure

```
papers-workflow/
├── papers_workflow/
│   ├── __init__.py
│   ├── main.py              # Entry point: run steps 1-3, then exit
│   ├── config.py             # Load config from env / .env file
│   ├── state.py              # Persistent state (library version, mappings)
│   ├── zotero_client.py      # All Zotero API interactions
│   ├── remarkable_client.py  # All reMarkable interactions (wraps rmapi CLI)
│   ├── remarkable_auth.py    # One-time device registration
│   ├── renderer.py           # .rm → annotated PDF + highlight extraction
│   ├── obsidian.py           # Write reading notes to Obsidian vault
│   └── notify.py             # macOS notifications
├── .env.example              # Template for required env vars (committed)
├── .env                      # Actual secrets (git-ignored)
├── .gitignore
├── state.json                # Persistent state file (git-ignored)
├── pyproject.toml            # Dependencies & project metadata
├── PLAN.md                   # This file
└── README.md                 # Setup & usage instructions (later)
```

### Key modules

| Module | Responsibility |
|---|---|
| `main.py` | Parse args (`--register` or default run). Run steps 1→2→3, then exit. |
| `config.py` | Load and validate all config from environment variables (via `.env`). |
| `state.py` | Read/write `state.json` — stores: Zotero library version number, document mappings, processed set. |
| `zotero_client.py` | Thin wrapper around Zotero Web API v3. Methods: `check_for_changes()`, `get_new_items()`, `download_pdf(attachment_key)`, `upload_pdf(attachment_key, pdf_bytes, current_md5)`, `set_tags(item_key, tags)`. |
| `remarkable_client.py` | Wrapper around `rmapi` CLI. Methods: `ensure_folders()`, `upload_pdf(path, folder)`, `list_folder(folder)`, `download_document(doc_path)`, `move_document(doc, folder)`. |
| `remarkable_auth.py` | One-time interactive device registration flow. |
| `renderer.py` | Takes a downloaded reMarkable document archive. Uses `rmrl` to render annotations onto the PDF. Uses `remarks` to extract highlighted text. Returns both. |
| `obsidian.py` | Creates a markdown note per paper in the Obsidian vault with YAML frontmatter, Zotero link, and extracted highlights. |
| `notify.py` | Sends a macOS notification via `osascript` summarizing what happened. |

### Why wrap `rmapi` CLI instead of using `rmapy` directly?

`rmapi` (Go) is the most actively maintained and battle-tested reMarkable Cloud client. It has survived multiple API changes. `rmapy` (Python) is convenient but has lagged behind API changes in the past. Wrapping the CLI via `subprocess` gives us the reliability of `rmapi` with the flexibility of Python orchestration. We can always swap to a pure-Python client later since it's behind an abstraction.

---

## Obsidian Integration

Each processed paper gets a markdown note in the Obsidian vault:

**File**: `{OBSIDIAN_VAULT_PATH}/Papers/{sanitized-title}.md`

```markdown
---
title: "Attention Is All You Need"
authors:
  - Vaswani
  - Shazeer
  - Parmar
date_added: 2025-12-15
date_read: 2025-12-18
zotero: "zotero://select/items/ABCD1234"
tags:
  - paper
  - read
---

# Attention Is All You Need

## Highlights

- "The dominant sequence transduction models are based on complex recurrent
  or convolutional neural networks..."
- "We propose a new simple network architecture, the Transformer, based
  solely on attention mechanisms..."

## Notes

```

**Design notes:**
- YAML frontmatter enables Obsidian Dataview queries (e.g., list all papers read this month)
- `zotero://` deep link opens the item directly in the Zotero desktop app
- Highlights are extracted text under reMarkable highlighter strokes (via `remarks`)
- The `## Notes` section is left empty for the user to fill in
- File name is sanitized (no special chars) to avoid filesystem issues

### Reading Log

Two reading logs are maintained, both in the papers subfolder:

**a) Dataview query note** (`Reading Log.md`) — created once, auto-updates:

```markdown
# Reading Log

\```dataview
TABLE date_added as "Added", date_read as "Read", join(authors, ", ") as "Authors"
FROM "Papers"
WHERE tags AND contains(tags, "read")
SORT date_read DESC
\```
```

**b) Append-style log** (`Reading Log (Simple).md`) — works without Dataview plugin:

```markdown
# Reading Log

- 2025-12-18 — [[Attention Is All You Need]] (Vaswani, Shazeer, Parmar)
- 2025-12-20 — [[Scaling Laws for Neural LMs]] (Kaplan et al.)
```

Each entry wikilinks to the individual paper note. A new line is appended each time a paper is processed.

### Paper titles on reMarkable

PDFs are uploaded to reMarkable using the **paper title from Zotero metadata** (not the PDF filename, which may be an arxiv ID like `2401.12345v1.pdf`). This ensures papers are always readable on the device.

---

## Persistent State

`state.json` tracks sync state across runs:

```json
{
  "zotero_library_version": 1542,
  "last_poll_timestamp": "2025-12-15T10:30:00Z",
  "documents": {
    "ABCD1234": {
      "zotero_item_key": "ABCD1234",
      "zotero_attachment_key": "EFGH5678",
      "zotero_attachment_md5": "d41d8cd98f00b204e9800998ecf8427e",
      "remarkable_doc_name": "Attention Is All You Need",
      "title": "Attention Is All You Need",
      "authors": ["Vaswani", "Shazeer", "Parmar"],
      "status": "on_remarkable",
      "uploaded_at": "2025-12-15T10:30:00Z",
      "processed_at": null
    }
  }
}
```

Document status lifecycle: `on_remarkable` → `processed`

---

## Credentials & Configuration

### Required credentials

| Credential | How to obtain | Env variable |
|---|---|---|
| **Zotero API Key** | https://www.zotero.org/settings/keys/new — create a key with "Allow library access" + "Allow write access" on Personal Library | `ZOTERO_API_KEY` |
| **Zotero User ID** | Shown at https://www.zotero.org/settings/keys (numeric ID at top of page) | `ZOTERO_USER_ID` |
| **reMarkable Device Token** | One-time setup: go to https://my.remarkable.com/device/browser/connect, get a code, then exchange it via `papers-workflow --register` | `REMARKABLE_DEVICE_TOKEN` |

### Optional configuration

| Setting | Default | Env variable |
|---|---|---|
| reMarkable "To Read" folder name | `To Read` | `RM_FOLDER_TO_READ` |
| reMarkable "Read" folder name | `Read` | `RM_FOLDER_READ` |
| reMarkable "Archive" folder name | `Archive` | `RM_FOLDER_ARCHIVE` |
| Zotero tag for unread papers | `to-read` | `ZOTERO_TAG_TO_READ` |
| Zotero tag for read papers | `read` | `ZOTERO_TAG_READ` |
| Obsidian vault path | *(none — disables Obsidian if unset)* | `OBSIDIAN_VAULT_PATH` |
| Obsidian papers subfolder | `Papers` | `OBSIDIAN_PAPERS_FOLDER` |
| Obsidian reading log filename | `Reading Log (Simple).md` | `OBSIDIAN_LOG_FILE` |
| HTTP request timeout (seconds) | `30` | `HTTP_TIMEOUT` |
| Log level | `INFO` | `LOG_LEVEL` |

### How credentials are stored safely

1. **`.env` file** in project root, loaded via `python-dotenv`. This file is in `.gitignore`.
2. **`.env.example`** is committed with placeholder values so contributors know what's needed.
3. The reMarkable device token setup is a one-time interactive step (`papers-workflow --register`).

---

## Dependencies

| Package | Purpose |
|---|---|
| `requests` | HTTP client for Zotero API |
| `python-dotenv` | Load `.env` file |
| `rmrl` | Render reMarkable annotations onto PDFs |
| `remarks` | Extract highlighted text from reMarkable annotations |

External tool (installed separately):

| Tool | Purpose |
|---|---|
| `rmapi` | reMarkable Cloud CLI client (Go binary) |

`rmapi` install: Download a binary from https://github.com/ddvk/rmapi/releases (the original `juruen/rmapi` is archived and no longer works).

---

## Scheduling

### macOS (launchd — preferred)

A `launchd` plist runs the script on a schedule. Survives reboots, can retry on failure.

```xml
<!-- ~/Library/LaunchAgents/com.user.papers-workflow.plist -->
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.papers-workflow</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/.venv/bin/papers-workflow</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>StandardOutPath</key>
    <string>/tmp/papers-workflow.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/papers-workflow.err</string>
</dict>
</plist>
```

### Linux / fallback (cron)

```
*/5 * * * * /path/to/.venv/bin/papers-workflow >> /tmp/papers-workflow.log 2>&1
```

---

## Edge Cases & Design Decisions

### What if a paper in Zotero has no PDF attachment?
Skip it. Log a warning. Some Zotero items are just metadata (e.g., bookmarks saved without a PDF).

### What if the paper already exists on reMarkable?
The state mapping is the primary dedup mechanism. If a Zotero item key is already in state, skip it. Also check by name as a safety net.

### What if Zotero item is modified (not new)?
The `since` parameter returns both new and modified items. We filter: only process items that have no `to-read` or `read` tag (i.e., untagged new items with a PDF).

### What if the user deletes a paper from reMarkable?
If a tracked document disappears from `/To Read`, `/Read`, and `/Archive`, mark it as `deleted` in state and stop tracking it. Don't touch the Zotero side.

### What if `rmrl` or `remarks` fails?
For `rmrl`: fall back to the original PDF (no annotations baked in). For `remarks`: create the Obsidian note without highlights (just metadata). Log a warning. Don't block the rest of the pipeline.

### What about Zotero's 3-step file upload?
1. POST file metadata (md5, size, filename) with `If-Match: {current_md5}` → get upload URL + prefix/suffix
2. POST file bytes (prefix + pdf_bytes + suffix) to the upload URL
3. POST upload confirmation with `upload={uploadKey}`

If step 2 or 3 fails, retry from step 1. The `If-Match` header prevents accidental overwrites.

### Concurrency / locking
One-shot execution means no long-running process. A file lock (`state.json.lock`) prevents overlapping runs if cron fires before the previous run finishes.

### Logging
Use Python's `logging` module. INFO for normal operations, WARNING for skipped items, ERROR for API failures.

### Obsidian note already exists?
If a note with the same filename already exists, do not overwrite — the user may have added their own notes. Log a warning and skip.

---

## Implementation Order

1. ~~**Project scaffolding** — `pyproject.toml`, `.gitignore`, `.env.example`, directory structure~~ ✅
2. ~~**`config.py`** — env var loading, validation~~ ✅
3. ~~**reMarkable registration** — `--register` subcommand~~ ✅
4. ~~**`state.py`** — JSON state read/write with atomic file updates~~ ✅
5. ~~**`zotero_client.py`** — polling, new item detection, PDF download, tagging, PDF upload~~ ✅
6. ~~**`remarkable_client.py`** — `rmapi` wrapper, folder creation, PDF upload, folder listing, document download, move~~ ✅
7. **`renderer.py`** — annotated PDF via `rmrl` + highlight text extraction via `remarks` *(deferred — `rmapi geta` handles annotation rendering for now)*
8. ~~**`obsidian.py`** — markdown note creation with frontmatter and highlights~~ ✅
9. ~~**`notify.py`** — macOS notification via `osascript`~~ ✅
10. ~~**`main.py`** — wire up the one-shot flow (steps 1→2→3)~~ ✅
11. **Scheduling** — launchd plist or cron setup
12. **Testing** — Step 1 (Zotero → reMarkable) tested ✅ with 35 papers. Step 2 (reMarkable → Zotero/Obsidian) pending.
