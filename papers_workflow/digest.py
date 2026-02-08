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

    subject = _build_subject()
    body = _build_body(read, skimmed)

    resend.api_key = config.RESEND_API_KEY
    result = resend.Emails.send({
        "from": config.DIGEST_FROM,
        "to": [config.DIGEST_TO],
        "subject": subject,
        "text": body,
    })
    log.info("Sent weekly digest to %s: %s", config.DIGEST_TO, result)


def _build_subject():
    year, week, _ = datetime.now().isocalendar()
    return f"Reading log - {year}-W{week:02d}"


def _paper_url(p):
    """Return a URL to the paper (DOI or URL), or empty string."""
    meta = p.get("metadata", {})
    doi = meta.get("doi", "")
    url = meta.get("url", "")
    if doi:
        return f"https://doi.org/{doi}"
    if url:
        return url
    return ""


def _paper_line(p):
    title = p.get("title", "Untitled")
    summary = p.get("summary", "")
    url = _paper_url(p)

    line = f"- {title}"
    if summary:
        line += f" — {summary}"
    if url:
        line += f"\n  {url}"
    return line


def _build_body(read, skimmed):
    lines = []

    if read:
        lines.append("Papers I read this week:\n")
        for p in read:
            lines.append(_paper_line(p))
        lines.append("")

    if skimmed:
        lines.append("I also saw the following papers:\n")
        for p in skimmed:
            lines.append(_paper_line(p))
        lines.append("")

    return "\n".join(lines)
