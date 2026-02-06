# Papers Workflow — Architecture Plan

## Overview

A daemon/script that bridges **Zotero** and **reMarkable** to automate a paper reading workflow:

```
  Zotero (save paper)          reMarkable (read & highlight)         Zotero (annotated PDF)
  ┌──────────────┐             ┌───────────────────────┐             ┌──────────────────┐
  │  New paper    │─── PDF ──▶ │  /To Read  folder     │             │  Updated PDF     │
  │  added via    │            │                       │             │  with highlights  │
  │  browser ext  │            │  User reads & moves   │             │  baked in         │
  └──────────────┘             │  to /Read when done   │             └──────────────────┘
                               │                       │                     ▲
                               │  /Read  folder        │── annotated PDF ────┘
                               └───────────────────────┘
```

### Flow in detail

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          POLLING LOOP                                  │
│                     (runs every N seconds)                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─── Poll Zotero ──────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  1. GET /users/{id}/items?limit=0                                │  │
│  │     → Compare Last-Modified-Version to stored version            │  │
│  │                                                                  │  │
│  │  2. If changed:                                                  │  │
│  │     GET /users/{id}/items?format=versions&since={stored_ver}     │  │
│  │     → Get changed item keys                                     │  │
│  │                                                                  │  │
│  │  3. Fetch full items, filter for NEW top-level items             │  │
│  │     (dateAdded > last poll time, itemType != attachment/note)    │  │
│  │                                                                  │  │
│  │  4. For each new paper:                                          │  │
│  │     a. GET children → find PDF attachment                        │  │
│  │     b. GET attachment /file → download PDF bytes                 │  │
│  │     c. Upload PDF to reMarkable /To Read/ folder                 │  │
│  │     d. Record mapping: {zotero_item_key → remarkable_doc_uuid}   │  │
│  │                                                                  │  │
│  │  5. Update stored Zotero library version                         │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌─── Poll reMarkable ──────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  1. Sync document index from reMarkable Cloud                    │  │
│  │                                                                  │  │
│  │  2. Compare each tracked document's parent folder UUID           │  │
│  │     against last snapshot                                        │  │
│  │                                                                  │  │
│  │  3. If a document moved from "To Read" → "Read":                 │  │
│  │     a. Download document (PDF + .rm annotation files)            │  │
│  │     b. Render annotations onto PDF (using rmrl)                  │  │
│  │     c. Look up Zotero attachment key from mapping                │  │
│  │     d. Upload annotated PDF to Zotero (replace original)         │  │
│  │     e. Mark document as processed                                │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Script Architecture

### Language & approach

**Python 3.11+** — best library ecosystem for both APIs (`requests` for Zotero, `rmapi` CLI wrapper or `rmapy` for reMarkable, `rmrl` for annotation rendering).

### Project structure

```
papers-workflow/
├── papers_workflow/
│   ├── __init__.py
│   ├── main.py              # Entry point: polling loop orchestration
│   ├── config.py             # Load config from env / .env file
│   ├── state.py              # Persistent state (library version, mappings)
│   ├── zotero_client.py      # All Zotero API interactions
│   ├── remarkable_client.py  # All reMarkable interactions (wraps rmapi CLI)
│   └── renderer.py           # .rm → annotated PDF rendering (wraps rmrl)
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
| `main.py` | Run the polling loop on an interval. Coordinate the two poll tasks. Handle signals (graceful shutdown). |
| `config.py` | Load and validate all config: Zotero API key, user ID, reMarkable device token, folder names, poll interval. Source: environment variables (via `.env`). |
| `state.py` | Read/write `state.json` — stores: Zotero library version number, mapping of `{zotero_item_key: remarkable_doc_uuid}`, set of already-processed document UUIDs, last poll timestamp. |
| `zotero_client.py` | Thin wrapper around Zotero Web API v3. Methods: `check_for_changes()`, `get_new_items()`, `download_pdf(attachment_key)`, `upload_pdf(attachment_key, pdf_bytes, current_md5)`. |
| `remarkable_client.py` | Wrapper around `rmapi` CLI. Methods: `ensure_folders()`, `upload_pdf(path, folder)`, `list_folder(folder)`, `download_document(doc_path)`, `get_doc_metadata()`. |
| `renderer.py` | Takes a downloaded reMarkable document archive, uses `rmrl` to render annotations onto the original PDF, returns the annotated PDF bytes. |

### Why wrap `rmapi` CLI instead of using `rmapy` directly?

`rmapi` (Go) is the most actively maintained and battle-tested reMarkable Cloud client. It has survived multiple API changes. `rmapy` (Python) is convenient but has lagged behind API changes in the past. Wrapping the CLI via `subprocess` gives us the reliability of `rmapi` with the flexibility of Python orchestration. We can always swap to a pure-Python client later since it's behind an abstraction.

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
      "remarkable_doc_uuid": "550e8400-e29b-41d4-a716-446655440000",
      "remarkable_doc_name": "Attention Is All You Need",
      "status": "on_remarkable",
      "uploaded_at": "2025-12-15T10:30:00Z",
      "processed_at": null
    }
  }
}
```

Document status lifecycle: `on_remarkable` → `read` → `processed`

---

## Credentials & Configuration

### Required credentials

| Credential | How to obtain | Env variable |
|---|---|---|
| **Zotero API Key** | https://www.zotero.org/settings/keys/new — create a key with "Allow library access" + "Allow write access" on Personal Library | `ZOTERO_API_KEY` |
| **Zotero User ID** | Shown at https://www.zotero.org/settings/keys (numeric ID at top of page) | `ZOTERO_USER_ID` |
| **reMarkable Device Token** | One-time setup: go to https://my.remarkable.com/device/browser/connect, get a code, then exchange it via the script's `--register` command | `REMARKABLE_DEVICE_TOKEN` |

### Optional configuration

| Setting | Default | Env variable |
|---|---|---|
| reMarkable "To Read" folder name | `To Read` | `RM_FOLDER_TO_READ` |
| reMarkable "Read" folder name | `Read` | `RM_FOLDER_READ` |
| Poll interval (seconds) | `300` (5 min) | `POLL_INTERVAL` |

### How credentials are stored safely

1. **`.env` file** in project root, loaded via `python-dotenv`. This file is in `.gitignore`.
2. **`.env.example`** is committed with placeholder values so contributors know what's needed.
3. The reMarkable device token setup is a one-time interactive step (script has a `--register` subcommand that prompts for the one-time code, exchanges it, and writes the token to `.env`).

`.env.example`:
```bash
# Zotero — get these from https://www.zotero.org/settings/keys
ZOTERO_API_KEY=your_api_key_here
ZOTERO_USER_ID=your_user_id_here

# reMarkable — populated by running: python -m papers_workflow --register
REMARKABLE_DEVICE_TOKEN=

# Optional
RM_FOLDER_TO_READ=To Read
RM_FOLDER_READ=Read
POLL_INTERVAL=300
```

`.gitignore` must include:
```
.env
state.json
*.pdf
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `requests` | HTTP client for Zotero API |
| `python-dotenv` | Load `.env` file |
| `rmrl` | Render reMarkable annotations onto PDFs |

External tool (installed separately):
| Tool | Purpose |
|---|---|
| `rmapi` | reMarkable Cloud CLI client (Go binary) |

`rmapi` install: `go install github.com/juruen/rmapi@latest` or download a binary release from GitHub. We should document both options and detect if it's available at startup.

---

## Edge Cases & Design Decisions

### What if a paper in Zotero has no PDF attachment?
Skip it. Log a warning. Some Zotero items are just metadata (e.g., bookmarks saved without a PDF).

### What if the paper already exists on reMarkable?
Check by name before uploading. If a document with the same name exists in `/To Read` or `/Read`, skip the upload and log it. Use the state mapping as the primary dedup mechanism.

### What if Zotero item is modified (not new)?
The `since` parameter returns both new and modified items. We filter: only process items where `dateAdded` is after our last poll timestamp AND the item key is not already in our state mapping.

### What if the user deletes a paper from reMarkable?
If a tracked document disappears from both `/To Read` and `/Read`, mark it as `deleted` in state and stop tracking it. Don't touch the Zotero side.

### What if `rmrl` fails to render annotations?
Fall back to the original PDF (no annotations). Log a warning. The user can re-read or manually export. Don't block the rest of the pipeline.

### What about Zotero's 3-step file upload dance?
The upload flow is:
1. POST file metadata (md5, size, filename) with `If-Match: {current_md5}` → get upload URL + prefix/suffix
2. POST file bytes (prefix + pdf_bytes + suffix) to the upload URL
3. POST upload confirmation with `upload={uploadKey}`

This needs careful implementation. If step 2 or 3 fails, we can retry from step 1. The `If-Match` header prevents accidental overwrites.

### Concurrency / locking
Single-process, single-threaded. The polling loop runs both checks sequentially. No concurrency concerns. A simple PID file or file lock can prevent duplicate instances.

### Logging
Use Python's `logging` module. INFO level for normal operations (new paper detected, uploaded, processed). WARNING for skipped items. ERROR for API failures. Configurable via `LOG_LEVEL` env var.

---

## Implementation Order

1. **Project scaffolding** — `pyproject.toml`, `.gitignore`, `.env.example`, directory structure
2. **`config.py`** — env var loading, validation
3. **`state.py`** — JSON state read/write with atomic file updates
4. **`zotero_client.py`** — polling, new item detection, PDF download
5. **`remarkable_client.py`** — `rmapi` wrapper, folder creation, PDF upload, folder listing, document download
6. **`renderer.py`** — `.rm` → annotated PDF via `rmrl`
7. **`main.py`** — polling loop, signal handling, wiring it all together
8. **reMarkable registration flow** — `--register` subcommand
9. **Testing** — manual end-to-end test with a real paper
