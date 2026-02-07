# Papers Workflow

Automate your paper reading workflow between **Zotero**, **reMarkable**, and **Obsidian**.

```
Save paper in Zotero  ──▶  PDF uploaded to reMarkable /To Read
                                      │
                           Read & highlight on reMarkable
                           Move to /Read when done
                                      │
                           Script picks it up:
                           ├── Annotated PDF → Zotero
                           ├── Note + highlights → Obsidian
                           └── Document → /Archive on reMarkable
```

## Prerequisites

- Python 3.9+
- A [Zotero](https://www.zotero.org/) account with the browser connector
- A [reMarkable](https://remarkable.com/) tablet
- (Optional) An [Obsidian](https://obsidian.md/) vault

### Install rmapi

The script uses [ddvk/rmapi](https://github.com/ddvk/rmapi) to communicate with the reMarkable Cloud. Install it before proceeding.

**macOS (recommended):**

Download the latest binary from [GitHub releases](https://github.com/ddvk/rmapi/releases):

```bash
# Download the latest release (check for newer versions)
curl -L -o /usr/local/bin/rmapi \
  https://github.com/ddvk/rmapi/releases/download/v0.0.32/rmapi-macosx-x86_64.zip

# Or for Apple Silicon, download the zip and extract:
curl -L -o /tmp/rmapi.zip \
  https://github.com/ddvk/rmapi/releases/download/v0.0.32/rmapi-macosx-x86_64.zip
unzip /tmp/rmapi.zip -d /usr/local/bin/
chmod +x /usr/local/bin/rmapi
```

**Alternative — Homebrew:**

```bash
brew install rmapi
```

> Note: The Homebrew version may lag behind. If you get HTTP 410 errors, download the binary directly from the releases page.

**Linux:**

```bash
curl -L -o /usr/local/bin/rmapi \
  https://github.com/ddvk/rmapi/releases/latest/download/rmapi-linuxx86-64
chmod +x /usr/local/bin/rmapi
```

After installing, authenticate rmapi by running:

```bash
rmapi ls /
```

This will prompt you to visit https://my.remarkable.com/device/browser/connect and enter a one-time code. The first run may take a minute to build the document tree.

## Setup

1. Clone and install:

```bash
git clone https://github.com/rlacombe/papers-workflow.git
cd papers-workflow
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

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
2. Downloads their PDFs and uploads to reMarkable's `/To Read` folder
3. Tags them `to-read` in Zotero
4. **Checks reMarkable** `/Read` folder for papers you've finished
5. Downloads annotated PDFs back to Zotero
6. Creates an Obsidian note with metadata (highlights extraction is a planned feature)
7. Archives the document on reMarkable
8. Sends a macOS notification summarizing what happened

### Scheduling

Run every 5 minutes via **launchd** (macOS):

```xml
<!-- ~/Library/LaunchAgents/com.user.papers-workflow.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.papers-workflow</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/papers-workflow/.venv/bin/papers-workflow</string>
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

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.user.papers-workflow.plist
```

Or via **cron**:

```
*/5 * * * * /path/to/papers-workflow/.venv/bin/papers-workflow >> /tmp/papers-workflow.log 2>&1
```

## Configuration

All settings are in `.env`. See [.env.example](.env.example) for the full list.

| Setting | Default | Description |
|---|---|---|
| `RM_FOLDER_TO_READ` | `To Read` | reMarkable folder for unread papers |
| `RM_FOLDER_READ` | `Read` | reMarkable folder — move papers here when done |
| `RM_FOLDER_ARCHIVE` | `Archive` | reMarkable folder for processed papers |
| `ZOTERO_TAG_TO_READ` | `to-read` | Zotero tag for papers sent to reMarkable |
| `ZOTERO_TAG_READ` | `read` | Zotero tag for papers synced back |
| `OBSIDIAN_VAULT_PATH` | *(empty)* | Path to Obsidian vault (disables Obsidian if unset) |
| `OBSIDIAN_PAPERS_FOLDER` | `Papers` | Subfolder for paper notes |

## Your reading workflow

1. Save a paper to Zotero using the browser connector (works on iOS too)
2. Wait for the script to run (or run it manually)
3. Read and highlight the paper on your reMarkable
4. When done, move the document from `/To Read` to `/Read` on the reMarkable
5. The next script run will sync everything back

## License

MIT
