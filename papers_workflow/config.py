import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)


def _require(var: str) -> str:
    value = os.environ.get(var, "").strip()
    if not value or value.startswith("your_"):
        print(f"Error: {var} is not set. Fill it in .env")
        sys.exit(1)
    return value


def save_to_env(key: str, value: str) -> None:
    """Update a single key in the .env file, preserving all other content."""
    if ENV_PATH.exists():
        text = ENV_PATH.read_text()
    else:
        text = ""

    pattern = rf"^{re.escape(key)}=.*$"
    replacement = f"{key}={value}"

    if re.search(pattern, text, flags=re.MULTILINE):
        text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
    else:
        text = text.rstrip("\n") + f"\n{replacement}\n"

    ENV_PATH.write_text(text)
    os.environ[key] = value


# Required
ZOTERO_API_KEY: str = _require("ZOTERO_API_KEY")
ZOTERO_USER_ID: str = _require("ZOTERO_USER_ID")

# Optional — reMarkable token is set later via --register
REMARKABLE_DEVICE_TOKEN: str = os.environ.get("REMARKABLE_DEVICE_TOKEN", "").strip()

# Configurable with defaults
RM_FOLDER_TO_READ: str = os.environ.get("RM_FOLDER_TO_READ", "To Read").strip()
RM_FOLDER_READ: str = os.environ.get("RM_FOLDER_READ", "Read").strip()
RM_FOLDER_ARCHIVE: str = os.environ.get("RM_FOLDER_ARCHIVE", "Archive").strip()
RM_FOLDER_SKIMMED: str = os.environ.get("RM_FOLDER_SKIMMED", "Skimmed").strip()

ZOTERO_TAG_TO_READ: str = os.environ.get("ZOTERO_TAG_TO_READ", "to-read").strip()
ZOTERO_TAG_READ: str = os.environ.get("ZOTERO_TAG_READ", "read").strip()
ZOTERO_TAG_SKIMMED: str = os.environ.get("ZOTERO_TAG_SKIMMED", "skimmed").strip()

OBSIDIAN_VAULT_PATH: str = os.environ.get("OBSIDIAN_VAULT_PATH", "").strip()
OBSIDIAN_PAPERS_FOLDER: str = os.environ.get("OBSIDIAN_PAPERS_FOLDER", "Papers").strip()
OBSIDIAN_VAULT_NAME: str = (
    os.environ.get("OBSIDIAN_VAULT_NAME", "").strip()
    or (Path(OBSIDIAN_VAULT_PATH).name if OBSIDIAN_VAULT_PATH else "")
)

ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "").strip()

RESEND_API_KEY: str = os.environ.get("RESEND_API_KEY", "").strip()
DIGEST_FROM: str = os.environ.get("DIGEST_FROM", "onboarding@resend.dev").strip()
DIGEST_TO: str = os.environ.get("DIGEST_TO", "").strip()

STATE_GIST_ID: str = os.environ.get("STATE_GIST_ID", "").strip()

HTTP_TIMEOUT: int = int(os.environ.get("HTTP_TIMEOUT", "30"))
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
