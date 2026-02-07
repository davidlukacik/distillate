"""Zotero Web API v3 client.

Handles polling for new items, downloading/uploading PDFs, and managing tags.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from papers_workflow import config

log = logging.getLogger(__name__)

_BASE = "https://api.zotero.org"
_HEADERS = {
    "Zotero-API-Version": "3",
    "Zotero-API-Key": config.ZOTERO_API_KEY,
}


def _url(path: str) -> str:
    return f"{_BASE}/users/{config.ZOTERO_USER_ID}{path}"


def _get(path: str, params: Optional[Dict] = None, **kwargs) -> requests.Response:
    resp = requests.get(
        _url(path), headers=_HEADERS, params=params,
        timeout=config.HTTP_TIMEOUT, **kwargs,
    )
    _handle_backoff(resp)
    resp.raise_for_status()
    return resp


def _post(path: str, **kwargs) -> requests.Response:
    resp = requests.post(
        _url(path), headers=_HEADERS,
        timeout=config.HTTP_TIMEOUT, **kwargs,
    )
    _handle_backoff(resp)
    resp.raise_for_status()
    return resp


def _patch(path: str, **kwargs) -> requests.Response:
    headers = {**_HEADERS, **kwargs.pop("headers", {})}
    resp = requests.patch(
        _url(path), headers=headers,
        timeout=config.HTTP_TIMEOUT, **kwargs,
    )
    _handle_backoff(resp)
    resp.raise_for_status()
    return resp


def _delete(path: str, **kwargs) -> requests.Response:
    headers = {**_HEADERS, **kwargs.pop("headers", {})}
    resp = requests.delete(
        _url(path), headers=headers,
        timeout=config.HTTP_TIMEOUT, **kwargs,
    )
    _handle_backoff(resp)
    resp.raise_for_status()
    return resp


def _handle_backoff(resp: requests.Response) -> None:
    backoff = resp.headers.get("Backoff") or resp.headers.get("Retry-After")
    if backoff:
        wait = int(backoff)
        log.warning("Zotero asked to back off for %d seconds", wait)
        time.sleep(wait)


# -- Polling --


def get_library_version() -> int:
    """Get the current library version (cheap check)."""
    resp = _get("/items", params={"limit": "0"})
    return int(resp.headers["Last-Modified-Version"])


def get_changed_item_keys(since_version: int) -> Tuple[Dict[str, int], int]:
    """Get item keys changed since a given library version.

    Returns (dict of {item_key: version}, new_library_version).
    """
    resp = _get("/items/top", params={
        "format": "versions",
        "since": str(since_version),
    })
    new_version = int(resp.headers["Last-Modified-Version"])
    return resp.json(), new_version


def get_items_by_keys(keys: List[str]) -> List[Dict[str, Any]]:
    """Fetch full item data for a list of item keys (max 50 per call)."""
    items = []
    for i in range(0, len(keys), 50):
        batch = keys[i : i + 50]
        resp = _get("/items", params={"itemKey": ",".join(batch)})
        items.extend(resp.json())
    return items


# -- Filtering --


def filter_new_papers(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter items to only new papers (no workflow tags, not attachments/notes)."""
    skip_types = {"attachment", "note"}
    workflow_tags = {config.ZOTERO_TAG_TO_READ, config.ZOTERO_TAG_READ}

    result = []
    for item in items:
        data = item.get("data", {})
        if data.get("itemType") in skip_types:
            continue
        item_tags = {t["tag"] for t in data.get("tags", [])}
        if item_tags & workflow_tags:
            continue
        result.append(item)
    return result


# -- Children & PDF --


def get_pdf_attachment(item_key: str) -> Optional[Dict[str, Any]]:
    """Find the first PDF attachment child of an item."""
    resp = _get(f"/items/{item_key}/children")
    for child in resp.json():
        data = child.get("data", {})
        if (
            data.get("itemType") == "attachment"
            and data.get("contentType") == "application/pdf"
            and data.get("linkMode") in ("imported_file", "imported_url")
        ):
            return child
    return None


def download_pdf(attachment_key: str) -> bytes:
    """Download the PDF file for an attachment item."""
    resp = _get(f"/items/{attachment_key}/file")
    return resp.content


# -- Tagging --


def add_tag(item_key: str, tag: str) -> None:
    """Add a tag to an item, preserving existing tags."""
    resp = _get(f"/items/{item_key}")
    item = resp.json()
    version = item["version"]
    existing_tags = [t["tag"] for t in item["data"].get("tags", [])]

    if tag in existing_tags:
        return

    existing_tags.append(tag)
    _patch(
        f"/items/{item_key}",
        json={"tags": [{"tag": t} for t in existing_tags]},
        headers={"If-Unmodified-Since-Version": str(version)},
    )
    log.info("Added tag '%s' to %s", tag, item_key)


def replace_tag(item_key: str, old_tag: str, new_tag: str) -> None:
    """Replace one tag with another on an item."""
    resp = _get(f"/items/{item_key}")
    item = resp.json()
    version = item["version"]
    tags = [t["tag"] for t in item["data"].get("tags", [])]

    new_tags = [new_tag if t == old_tag else t for t in tags]
    if new_tag not in new_tags:
        new_tags.append(new_tag)

    _patch(
        f"/items/{item_key}",
        json={"tags": [{"tag": t} for t in new_tags]},
        headers={"If-Unmodified-Since-Version": str(version)},
    )
    log.info("Replaced tag '%s' → '%s' on %s", old_tag, new_tag, item_key)



def delete_attachment(attachment_key: str) -> None:
    """Delete a PDF attachment item from Zotero (file + metadata entry).

    The parent item (paper metadata, tags, etc.) is preserved.
    """
    resp = _get(f"/items/{attachment_key}")
    version = resp.json()["version"]
    _delete(
        f"/items/{attachment_key}",
        headers={"If-Unmodified-Since-Version": str(version)},
    )
    log.info("Deleted attachment %s from Zotero", attachment_key)


# -- Convenience: extract metadata --


def extract_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    """Extract title and authors from a Zotero item."""
    data = item.get("data", {})
    title = data.get("title", "Untitled")
    creators = data.get("creators", [])
    authors = [
        c.get("lastName") or c.get("name", "Unknown")
        for c in creators
        if c.get("creatorType") == "author"
    ]
    if not authors:
        authors = [
            c.get("lastName") or c.get("name", "Unknown")
            for c in creators
        ]
    return {"title": title, "authors": authors}
