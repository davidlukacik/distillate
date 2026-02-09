# Papers Workflow

Automate your paper reading workflow between **Zotero**, **reMarkable**, and **Obsidian**.

```
Save paper in Zotero  ──▶  PDF uploaded to reMarkable Papers/Inbox
                                    │
                         Read & highlight on reMarkable
                         Move to Papers/Read when done
                                    │
                         Script picks it up:
                         ├── Annotated PDF → Obsidian vault
                         ├── Note + highlights → Obsidian
                         ├── PDF deleted from Zotero (free storage)
                         └── Document → Papers/Vault on reMarkable
```

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A [Zotero](https://www.zotero.org/) account with the browser connector
- A [reMarkable](https://remarkable.com/) tablet
- (Optional) An [Obsidian](https://obsidian.md/) vault

### Install rmapi

The script uses [ddvk/rmapi](https://github.com/ddvk/rmapi) to communicate with the reMarkable Cloud.

**macOS (Homebrew):**

```bash
brew install rmapi
```

**macOS (manual):**

```bash
# Download the latest release from https://github.com/ddvk/rmapi/releases
curl -L -o /usr/local/bin/rmapi \
  https://github.com/ddvk/rmapi/releases/latest/download/rmapi-macosx-x86_64
chmod +x /usr/local/bin/rmapi
```

**Linux:**

```bash
curl -L -o /usr/local/bin/rmapi \
  https://github.com/ddvk/rmapi/releases/latest/download/rmapi-linuxx86-64
chmod +x /usr/local/bin/rmapi
```

After installing, authenticate by running:

```bash
rmapi ls /
```

This will prompt you to visit https://my.remarkable.com/device/browser/connect and enter a one-time code.

## Setup

1. Clone and install:

```bash
git clone https://github.com/rlacombe/papers-workflow.git
cd papers-workflow
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e .
```

<details>
<summary>Without uv (pip only)</summary>

```bash
git clone https://github.com/rlacombe/papers-workflow.git
cd papers-workflow
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

</details>

2. Copy the example config and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with:

- **`ZOTERO_API_KEY`** — Create one at https://www.zotero.org/settings/keys/new (enable library access + write access)
- **`ZOTERO_USER_ID`** — Your numeric user ID, shown at https://www.zotero.org/settings/keys

3. (Optional) Set your Obsidian vault path in `.env`:

```
OBSIDIAN_VAULT_PATH=/path/to/your/vault
```

## Usage

Run the workflow once:

```bash
papers-workflow
```

On first run, the script sets a watermark at the current Zotero library version. Only papers added *after* this point will be synced. This prevents flooding your reMarkable with your entire existing library.

### What it does each run

1. **Polls Zotero** for new papers (added since last run)
2. Downloads their PDFs and uploads to reMarkable's `Papers/Inbox` folder
3. Tags them `inbox` in Zotero
4. **Checks reMarkable** `Papers/Read` folder for papers you've finished reading
5. Extracts highlighted text from the reMarkable document
6. Renders an annotated PDF with highlights and saves it to the Obsidian vault
7. Deletes the original PDF from Zotero to free storage (metadata is kept)
8. Creates an Obsidian note with metadata, highlights, and an embedded PDF link
9. **Checks** `Papers/Leafed` for papers you leafed through (minimal notes, no highlights)
10. Moves processed documents to `Papers/Vault` on reMarkable
11. Sends a macOS notification summarizing what happened

### How highlights work

When you highlight text on the reMarkable using the built-in highlighter tool (with text recognition enabled), the highlighted text is embedded in the document's `.rm` files as `GlyphRange` items.

The script:
1. Downloads the raw document bundle (`rmapi get`)
2. Parses the `.rm` files using [rmscene](https://github.com/ricklupton/rmscene) to extract highlighted text
3. Searches for that text in the original PDF using [PyMuPDF](https://pymupdf.readthedocs.io/) and adds highlight annotations at the matching locations
4. Saves the annotated PDF to the Obsidian vault and writes the highlight text to the Obsidian note

## Scheduling (macOS)

The recommended way to run the workflow automatically is with `launchd`.

### Quick setup

Run the included setup script:

```bash
./scripts/install-launchd.sh
```

This installs a Launch Agent that runs the workflow every 15 minutes. It auto-detects your repo path, venv, and `rmapi` location.

### Manual setup

If you prefer to do it yourself, create `~/Library/LaunchAgents/com.papers-workflow.sync.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.papers-workflow.sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/papers-workflow/.venv/bin/papers-workflow</string>
    </array>
    <key>StartInterval</key>
    <integer>900</integer>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/you/Library/Logs/papers-workflow.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/you/Library/Logs/papers-workflow.log</string>
    <key>Nice</key>
    <integer>10</integer>
</dict>
</plist>
```

Then load it:

```bash
launchctl load ~/Library/LaunchAgents/com.papers-workflow.sync.plist
```

### Scheduling with cron (Linux)

```
*/15 * * * * /path/to/papers-workflow/.venv/bin/papers-workflow >> /var/log/papers-workflow.log 2>&1
```

### Useful commands

```bash
# Check logs
tail -f ~/Library/Logs/papers-workflow.log

# Run immediately (without waiting for the schedule)
launchctl start com.papers-workflow.sync

# Stop the schedule
launchctl unload ~/Library/LaunchAgents/com.papers-workflow.sync.plist

# Restart after editing the plist
launchctl unload ~/Library/LaunchAgents/com.papers-workflow.sync.plist
launchctl load ~/Library/LaunchAgents/com.papers-workflow.sync.plist
```

## Configuration

All settings are in `.env`. See [.env.example](.env.example) for the full list.

| Setting | Default | Description |
|---|---|---|
| `RM_FOLDER_PAPERS` | `Papers` | Parent folder on reMarkable |
| `RM_FOLDER_INBOX` | `Papers/Inbox` | reMarkable folder for unread papers |
| `RM_FOLDER_READ` | `Papers/Read` | reMarkable folder — move papers here when done reading |
| `RM_FOLDER_LEAFED` | `Papers/Leafed` | reMarkable folder — move papers here if just leafed through |
| `RM_FOLDER_VAULT` | `Papers/Vault` | reMarkable folder for processed papers |
| `ZOTERO_TAG_INBOX` | `inbox` | Zotero tag for papers sent to reMarkable |
| `ZOTERO_TAG_READ` | `read` | Zotero tag for fully read papers |
| `ZOTERO_TAG_LEAFED` | `leafed` | Zotero tag for leafed-through papers |
| `OBSIDIAN_VAULT_PATH` | *(empty)* | Path to Obsidian vault (disables Obsidian if unset) |
| `OBSIDIAN_PAPERS_FOLDER` | `Papers` | Subfolder for paper notes |

## Your reading workflow

1. Save a paper to Zotero using the browser connector (works on iOS too)
2. Wait for the script to run (or run it manually)
3. Read and highlight the paper on your reMarkable
4. When done, move the document from `Papers/Inbox` to `Papers/Read` (or `Papers/Leafed` if you just skimmed it)
5. The next script run will sync everything back

## License

MIT
