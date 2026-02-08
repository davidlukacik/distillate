"""Weekly email digest of papers read and skimmed."""

import logging
from datetime import datetime, timedelta, timezone

import resend

from papers_workflow import config
from papers_workflow.state import State

log = logging.getLogger(__name__)


def send_weekly_digest(days: int = 7) -> None:
    """Compile and send a digest of papers processed in the last N days."""
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not config.RESEND_API_KEY:
        log.error("RESEND_API_KEY not set, cannot send digest")
        return
    if not config.DIGEST_TO:
        log.error("DIGEST_TO not set, cannot send digest")
        return

    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    state = State()
    papers = state.documents_processed_since(since)

    if not papers:
        log.info("No papers processed in the last %d days, skipping digest", days)
        return

    read = [p for p in papers if p.get("reading_status", "read") == "read"]
    skimmed = [p for p in papers if p.get("reading_status") == "skimmed"]

    subject = _build_subject(len(read), len(skimmed))
    body = _build_body(read, skimmed)

    resend.api_key = config.RESEND_API_KEY
    result = resend.Emails.send({
        "from": config.DIGEST_FROM,
        "to": [config.DIGEST_TO],
        "subject": subject,
        "html": body,
    })
    log.info("Sent weekly digest to %s: %s", config.DIGEST_TO, result)


def _build_subject(n_read, n_skimmed):
    parts = []
    if n_read:
        parts.append(f"{n_read} read")
    if n_skimmed:
        parts.append(f"{n_skimmed} skimmed")
    week = datetime.now().strftime("%b %-d")
    return f"Reading digest — {', '.join(parts)} (week of {week})"


def _paper_html(p):
    title = p.get("title", "Untitled")
    authors = p.get("authors", [])
    meta = p.get("metadata", {})
    doi = meta.get("doi", "")
    summary = p.get("summary", "")

    author_str = ", ".join(authors[:3])
    if len(authors) > 3:
        author_str += " et al."

    if doi:
        title_html = f'<a href="https://doi.org/{doi}">{title}</a>'
    elif meta.get("url"):
        title_html = f'<a href="{meta["url"]}">{title}</a>'
    else:
        title_html = title

    summary_html = f"<br>{summary}" if summary else ""

    return (
        f"<li style='margin-bottom: 10px;'>"
        f"{title_html} — {author_str}"
        f"{summary_html}"
        f"</li>"
    )


def _build_body(read, skimmed):
    lines = [
        "<html><body style='font-family: sans-serif; max-width: 600px; "
        "margin: 0 auto; padding: 20px; color: #333;'>",
    ]

    if read:
        lines.append(f"<p><strong>Read ({len(read)})</strong></p>")
        lines.append("<ul style='padding-left: 20px;'>")
        for p in read:
            lines.append(_paper_html(p))
        lines.append("</ul>")

    if skimmed:
        lines.append(f"<p><strong>Skimmed ({len(skimmed)})</strong></p>")
        lines.append("<ul style='padding-left: 20px;'>")
        for p in skimmed:
            lines.append(_paper_html(p))
        lines.append("</ul>")

    lines.append("<p style='color: #999; font-size: 11px;'>Sent by papers-workflow</p>")
    lines.append("</body></html>")
    return "\n".join(lines)
