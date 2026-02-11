"""Weekly email digest and daily paper suggestions."""

import logging
from datetime import datetime, timedelta, timezone

import resend

from papers_workflow import config
from papers_workflow import summarizer
from papers_workflow.state import State

log = logging.getLogger(__name__)


def send_weekly_digest(days: int = 7) -> None:
    """Compile and send a digest of papers processed in the last N days."""
    config.setup_logging()

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
    leafed = [p for p in papers if p.get("reading_status") == "leafed"]

    subject = _build_subject()
    body = _build_body(read, leafed)

    resend.api_key = config.RESEND_API_KEY
    result = resend.Emails.send({
        "from": config.DIGEST_FROM,
        "to": [config.DIGEST_TO],
        "subject": subject,
        "html": body,
    })
    log.info("Sent weekly digest to %s: %s", config.DIGEST_TO, result)


def _build_subject():
    return datetime.now().strftime("Reading digest \u2013 %b %-d, %Y")


def _paper_url(p):
    """Return a URL to the paper, preferring direct URL over DOI."""
    meta = p.get("metadata", {})
    url = meta.get("url", "")
    doi = meta.get("doi", "")
    if url:
        return url
    if doi:
        return f"https://doi.org/{doi}"
    return ""


def _paper_html(p):
    title = p.get("title", "Untitled")
    summary = p.get("summary", "")
    url = _paper_url(p)

    summary_html = f" &mdash; {summary}" if summary else ""
    url_html = f'<br><a href="{url}">{url}</a>' if url else ""

    return (
        f"<li style='margin-bottom: 10px;'>"
        f"<strong>{title}</strong>{summary_html}{url_html}"
        f"</li>"
    )


def _build_body(read, leafed):
    lines = [
        "<html><body style='font-family: sans-serif; max-width: 600px; "
        "margin: 0 auto; padding: 20px; color: #333;'>",
    ]

    if read:
        lines.append("<p>Papers I read this week:</p>")
        lines.append("<ul style='padding-left: 20px;'>")
        for p in read:
            lines.append(_paper_html(p))
        lines.append("</ul>")

    if leafed:
        lines.append("<p>I also leafed through the following papers:</p>")
        lines.append("<ul style='padding-left: 20px;'>")
        for p in leafed:
            lines.append(_paper_html(p))
        lines.append("</ul>")

    lines.append("</body></html>")
    return "\n".join(lines)


def send_suggestion() -> None:
    """Send a daily email suggesting 3 papers to read next."""
    config.setup_logging()

    if not config.RESEND_API_KEY:
        log.error("RESEND_API_KEY not set, cannot send suggestion")
        return
    if not config.DIGEST_TO:
        log.error("DIGEST_TO not set, cannot send suggestion")
        return

    state = State()

    # Gather unread papers (on_remarkable)
    unread = state.documents_with_status("on_remarkable")
    if not unread:
        log.info("No papers in reading queue, skipping suggestion")
        return

    # Enrich with metadata fields the suggestion engine needs
    unread_enriched = []
    for doc in unread:
        meta = doc.get("metadata", {})
        unread_enriched.append({
            "title": doc["title"],
            "tags": meta.get("tags", []),
            "paper_type": meta.get("paper_type", ""),
            "uploaded_at": doc.get("uploaded_at", ""),
        })

    # Gather recent reads for context (last 30 days)
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    recent = state.documents_processed_since(since)
    recent_enriched = []
    for doc in recent:
        meta = doc.get("metadata", {})
        recent_enriched.append({
            "title": doc["title"],
            "tags": meta.get("tags", []),
            "summary": doc.get("summary", ""),
            "reading_status": doc.get("reading_status", "read"),
        })

    # Ask Claude
    result = summarizer.suggest_papers(unread_enriched, recent_enriched)
    if not result:
        log.warning("Could not generate suggestions")
        return

    subject = datetime.now().strftime("What to read next \u2013 %b %-d, %Y")
    body = _build_suggestion_body(result, unread)

    resend.api_key = config.RESEND_API_KEY
    send_result = resend.Emails.send({
        "from": config.DIGEST_FROM,
        "to": [config.DIGEST_TO],
        "subject": subject,
        "html": body,
    })
    log.info("Sent suggestion to %s: %s", config.DIGEST_TO, send_result)


def send_themes_email(month: str, themes_text: str) -> None:
    """Send a monthly research themes email."""
    config.setup_logging()

    if not config.RESEND_API_KEY:
        log.error("RESEND_API_KEY not set, cannot send themes email")
        return
    if not config.DIGEST_TO:
        log.error("DIGEST_TO not set, cannot send themes email")
        return

    # Convert markdown paragraphs to HTML
    paragraphs = themes_text.strip().split("\n\n")
    body_html = "\n".join(f"<p>{p.strip()}</p>" for p in paragraphs if p.strip())

    html = (
        "<html><body style='font-family: sans-serif; max-width: 600px; "
        "margin: 0 auto; padding: 20px; color: #333;'>"
        f"<h1>Research Themes \u2014 {month}</h1>"
        f"{body_html}"
        "</body></html>"
    )

    resend.api_key = config.RESEND_API_KEY
    result = resend.Emails.send({
        "from": config.DIGEST_FROM,
        "to": [config.DIGEST_TO],
        "subject": f"Research themes \u2014 {month}",
        "html": html,
    })
    log.info("Sent themes email to %s: %s", config.DIGEST_TO, result)


def _build_suggestion_body(suggestion_text, unread):
    """Build HTML body from Claude's suggestion text."""
    # Parse numbered suggestions and add URLs
    lines = [
        "<html><body style='font-family: sans-serif; max-width: 600px; "
        "margin: 0 auto; padding: 20px; color: #333;'>",
        f"<p>You have {len(unread)} papers in your reading queue. "
        f"Here are 3 to consider today:</p>",
        "<ol style='padding-left: 20px;'>",
    ]

    # Build title -> URL lookup
    url_lookup = {}
    for doc in unread:
        meta = doc.get("metadata", {})
        url = meta.get("url", "")
        doi = meta.get("doi", "")
        if url:
            url_lookup[doc["title"].lower()] = url
        elif doi:
            url_lookup[doc["title"].lower()] = f"https://doi.org/{doi}"

    for line in suggestion_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Try to find and link the paper title
        url = ""
        for title_lower, paper_url in url_lookup.items():
            if title_lower in line.lower():
                url = paper_url
                break
        url_html = f'<br><a href="{url}">{url}</a>' if url else ""
        lines.append(f"<li style='margin-bottom: 10px;'>{line}{url_html}</li>")

    lines.append("</ol>")
    lines.append("</body></html>")
    return "\n".join(lines)
