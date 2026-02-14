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
                         ├── Note + highlights + AI summary → Obsidian
                         ├── PDF deleted from Zotero (free storage)
                         └── Document → Papers/Vault on reMarkable
```

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A [Zotero](https://www.zotero.org/) account with the browser connector
- A [reMarkable](https://remarkable.com/) tablet
- (Optional) An [Obsidian](https://obsidian.md/) vault
- (Optional) An [Anthropic API key](https://console.anthropic.com/) for AI summaries

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
git clone https://github.com/rlacombe/distillate.git
cd distillate
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e .
```

<details>
<summary>Without uv (pip only)</summary>

```bash
git clone https://github.com/rlacombe/distillate.git
cd distillate
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
distillate
```

On first run, the script sets a watermark at the current Zotero library version. Only papers added *after* this point will be synced. This prevents flooding your reMarkable with your entire existing library.

### What it does each run

1. **Polls Zotero** for new papers (added since last run)
2. Downloads their PDFs and uploads to reMarkable's `Papers/Inbox` folder
3. Tags them `inbox` in Zotero and enriches with Semantic Scholar citation data
4. **Checks reMarkable** `Papers/Read` folder for papers you've finished reading
5. Extracts highlighted text from the reMarkable document
6. Renders an annotated PDF with highlights and saves it to the Obsidian vault
7. Deletes the original PDF from Zotero to free storage (metadata is kept)
8. Creates an Obsidian note with metadata, highlights, AI summary (paragraph + key learnings), and an embedded PDF
9. Updates the Reading Log and tags the paper `read` in Zotero
10. Moves processed documents to `Papers/Vault` on reMarkable

### Additional commands

```bash
# Re-run highlights + summary for a previously processed paper
distillate --reprocess "Paper Title"

# Preview what the next run would do (no changes made)
distillate --dry-run

# Get 3 paper suggestions based on your reading history
distillate --suggest

# Move suggested papers to Papers/ root on reMarkable for easy access
distillate --promote

# Send a weekly digest email with recent reading activity
distillate --digest

# Generate a monthly research themes synthesis
distillate --themes 2026-02

# Backfill Semantic Scholar data for existing papers
distillate --backfill-s2

# Push state.json to a GitHub Gist (for GitHub Actions)
distillate --sync-state
```

### How highlights work

When you highlight text on the reMarkable using the built-in highlighter tool (with text recognition enabled), the highlighted text is embedded in the document's `.rm` files as `GlyphRange` items.

The script:
1. Downloads the raw document bundle (`rmapi get`)
2. Parses the `.rm` files using [rmscene](https://github.com/ricklupton/rmscene) to extract highlighted text
3. Searches for that text in the original PDF using [PyMuPDF](https://pymupdf.readthedocs.io/) and adds highlight annotations at the matching locations
4. Saves the annotated PDF to the Obsidian vault and writes the highlight text to the Obsidian note

### AI summaries

With an Anthropic API key set, the script generates for each paper:

- A **one-liner** explaining why the paper matters (shown as a blockquote and in the Reading Log)
- A **paragraph summary** describing what the paper does, its methods, and findings
- **Key learnings** — 4-6 bullet points distilling the most important insights, ending with a "so what"

Summaries and paper suggestions use Claude Sonnet for quality. Monthly themes use Claude Haiku for efficiency.

## Scheduling (macOS)

The recommended way to run the workflow automatically is with `launchd`.

### Quick setup

Run the included setup script:

```bash
./scripts/install-launchd.sh
```

This installs two Launch Agents:
- **Sync** — runs the workflow every 15 minutes
- **Auto-promote** — runs `--promote` every 8 hours (fires on wake if the laptop was asleep) to pick 3 papers and move them to the `Papers/` root on reMarkable

Papers you've started reading (turned at least one page) are kept at the root; unread promoted papers are demoted back to Inbox.

The script auto-detects your repo path, venv, and `rmapi` location.

### Manual setup

If you prefer to do it yourself, create `~/Library/LaunchAgents/com.distillate.sync.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.distillate.sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/distillate/.venv/bin/distillate</string>
    </array>
    <key>StartInterval</key>
    <integer>900</integer>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/you/Library/Logs/distillate.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/you/Library/Logs/distillate.log</string>
    <key>Nice</key>
    <integer>10</integer>
</dict>
</plist>
```

Then load it:

```bash
launchctl load ~/Library/LaunchAgents/com.distillate.sync.plist
```

### Scheduling with cron (Linux)

```
*/15 * * * * /path/to/distillate/.venv/bin/distillate >> /var/log/distillate.log 2>&1
```

### Useful commands

```bash
# Check logs
tail -f ~/Library/Logs/distillate.log

# Run immediately (without waiting for the schedule)
launchctl start com.distillate.sync

# Stop the schedule
launchctl unload ~/Library/LaunchAgents/com.distillate.sync.plist

# Restart after editing the plist
launchctl unload ~/Library/LaunchAgents/com.distillate.sync.plist
launchctl load ~/Library/LaunchAgents/com.distillate.sync.plist
```

## Configuration

All settings are in `.env`. See [.env.example](.env.example) for the full list.

| Setting | Default | Description |
|---|---|---|
| `RM_FOLDER_PAPERS` | `Papers` | Parent folder on reMarkable |
| `RM_FOLDER_INBOX` | `Papers/Inbox` | reMarkable folder for unread papers |
| `RM_FOLDER_READ` | `Papers/Read` | reMarkable folder — move papers here when done reading |
| `RM_FOLDER_SAVED` | `Papers/Saved` | reMarkable folder for processed papers |
| `ZOTERO_TAG_INBOX` | `inbox` | Zotero tag for papers sent to reMarkable |
| `ZOTERO_TAG_READ` | `read` | Zotero tag for fully read papers |
| `OBSIDIAN_VAULT_PATH` | *(empty)* | Path to Obsidian vault (disables Obsidian if unset) |
| `OBSIDIAN_PAPERS_FOLDER` | `Papers` | Subfolder for paper notes |
| `ANTHROPIC_API_KEY` | *(empty)* | Anthropic API key for AI summaries (falls back to abstract if unset) |
| `CLAUDE_SMART_MODEL` | `claude-sonnet-4-5` | Model for summaries and key learnings |
| `CLAUDE_FAST_MODEL` | `claude-haiku-4-5` | Model for suggestions and themes |
| `RESEND_API_KEY` | *(empty)* | Resend API key for email digest/suggestions |

## Your reading workflow

1. Save a paper to Zotero using the browser connector (works on iOS too)
2. Wait for the script to run (or run it manually)
3. Read and highlight the paper on your reMarkable
4. When done, move the document from `Papers/Inbox` to `Papers/Read`
5. The next script run will sync everything back

## License

MIT
