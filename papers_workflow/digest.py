"""Weekly email digest and daily paper suggestions."""

import logging
from datetime import datetime, timedelta, timezone

import resend

from papers_workflow import config
from papers_workflow import summarizer
from papers_workflow.state import State

log = logging.getLogger(__name__)

# Pastel palette for tag pills (deterministic by tag name hash)
_PILL_COLORS = [
    "#e8f0fe",  # blue
    "#fce8e6",  # red
    "#e6f4ea",  # green
    "#fef7e0",  # yellow
    "#f3e8fd",  # purple
    "#e8f7f0",  # teal
    "#fde8ef",  # pink
    "#e8eaf6",  # indigo
]


def _tag_pills_html(tags: list) -> str:
    """Render topic tags as colored HTML pill badges."""
    if not tags:
        return ""
    pills = []
    for tag in tags:
        bg = _PILL_COLORS[hash(tag) % len(_PILL_COLORS)]
        pills.append(
            f'<span style="display:inline-block;background:{bg};'
            f'color:#333;padding:2px 8px;border-radius:12px;'
            f'font-size:8px;margin:2px 2px;">{tag}</span>'
        )
    return " ".join(pills)


def _reading_velocity_html(state: State) -> str:
    """Render reading velocity: 'Read N papers this week, M this month.'"""
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()
    month_ago = (now - timedelta(days=30)).isoformat()

    week_count = len(state.documents_processed_since(week_ago))
    month_count = len(state.documents_processed_since(month_ago))

    return (
        f'<p style="color:#666;font-size:14px;margin-bottom:16px;">'
        f'Read {week_count} paper{"s" if week_count != 1 else ""} this week, '
        f'{month_count} this month.</p>'
    )


def _recent_topic_tags(state: State, limit: int = 5) -> list:
    """Return the most common topic tags from recent reads (last 30 days)."""
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    recent = state.documents_processed_since(since)
    tag_counts: dict = {}
    for doc in recent:
        for tag in doc.get("metadata", {}).get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    # Sort by frequency, return top tags
    return [t for t, _ in sorted(tag_counts.items(), key=lambda x: -x[1])][:limit]


def _queue_health_html(state: State) -> str:
    """Render queue health snapshot for the suggest email."""
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()

    queue = state.documents_with_status("on_remarkable")
    total = len(queue)

    oldest_days = 0
    if queue:
        oldest_uploaded = min(d.get("uploaded_at", "") for d in queue)
        if oldest_uploaded:
            try:
                oldest_dt = datetime.fromisoformat(oldest_uploaded)
                oldest_days = (now - oldest_dt).days
            except (ValueError, TypeError):
                pass

    added_this_week = sum(
        1 for d in state.documents.values()
        if (d.get("uploaded_at") or "") >= week_ago
        and d.get("status") in ("on_remarkable", "processed")
    )
    processed_this_week = len(state.documents_processed_since(week_ago))

    awaiting = len(state.documents_with_status("awaiting_pdf"))
    awaiting_html = (
        f' &middot; {awaiting} missing PDF{"s" if awaiting != 1 else ""}'
        if awaiting else ""
    )

    return (
        f'<hr style="border:none;border-top:1px solid #eee;margin:20px 0;">'
        f'<p style="color:#999;font-size:12px;">'
        f'Queue: {total} papers waiting'
        f' &middot; oldest: {oldest_days} days'
        f' &middot; this week: +{added_this_week} added, '
        f'-{processed_this_week} read{awaiting_html}</p>'
    )


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

    subject = _build_subject()
    body = _build_body(papers, state)

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
    meta = p.get("metadata", {})
    tags = meta.get("tags", [])
    highlight_count = p.get("highlight_count", 0)

    # Title with Obsidian deep link
    from papers_workflow import obsidian
    obsidian_uri = obsidian.get_obsidian_uri(title)
    if obsidian_uri:
        title_html = (
            f'<a href="{obsidian_uri}" style="color:#333;text-decoration:none;">'
            f'<strong>{title}</strong></a>'
        )
    else:
        title_html = f"<strong>{title}</strong>"

    hl_html = ""
    if highlight_count:
        hl_html = (
            f' <span style="color:#999;font-size:12px;">'
            f'({highlight_count} highlight{"s" if highlight_count != 1 else ""})</span>'
        )

    summary_html = f" &mdash; {summary}" if summary else ""
    pills_html = f" {_tag_pills_html(tags)}" if tags else ""
    url_html = (
        f'<br><a href="{url}" style="color:#666;font-size:13px;">{url}</a>'
        if url else ""
    )

    return (
        f"<li style='margin-bottom: 14px;'>"
        f"{title_html}{hl_html}{summary_html}{pills_html}{url_html}"
        f"</li>"
    )


def _build_body(papers, state: State):
    velocity = _reading_velocity_html(state)

    lines = [
        "<html><body style='font-family: sans-serif; max-width: 600px; "
        "margin: 0 auto; padding: 20px; color: #333;'>",
        velocity,
        "<p>Papers I read this week:</p>",
        "<ul style='padding-left: 20px;'>",
    ]

    for p in papers:
        lines.append(_paper_html(p))

    lines.append("</ul>")
    lines.append(_queue_health_html(state))
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
        })

    # Ask Claude
    result = summarizer.suggest_papers(unread_enriched, recent_enriched)
    if not result:
        log.warning("Could not generate suggestions")
        return

    subject = datetime.now().strftime("What to read next \u2013 %b %-d, %Y")
    body = _build_suggestion_body(result, unread, state)

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


def _build_suggestion_body(suggestion_text, unread, state: State):
    """Build HTML body from Claude's suggestion text."""
    import re

    # Build title -> doc lookup from full unread list
    url_lookup = {}
    tags_lookup = {}
    for doc in unread:
        meta = doc.get("metadata", {})
        url = meta.get("url", "")
        doi = meta.get("doi", "")
        title_lower = doc["title"].lower()
        if url:
            url_lookup[title_lower] = url
        elif doi:
            url_lookup[title_lower] = f"https://doi.org/{doi}"
        tags_lookup[title_lower] = meta.get("tags", [])

    intro = (
        f"<p>You have {len(unread)} papers in your queue, "
        f"here are 3 to consider today:</p>"
    )

    lines = [
        "<html><body style='font-family: sans-serif; max-width: 600px; "
        "margin: 0 auto; padding: 20px; color: #333;'>",
        _reading_velocity_html(state),
        intro,
        "<ul style='padding-left: 20px;'>",
    ]

    # Parse suggestion lines: "[number]. [title] — [reason]"
    # Claude may wrap in **bold** markdown or add preamble text
    for line in suggestion_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        # Strip markdown bold markers
        clean = line.replace("**", "")

        # Extract queue number and rest
        m = re.match(r"(\d+)\.\s*(.*)", clean)
        if not m:
            continue
        queue_num = m.group(1)
        rest = m.group(2)

        # Match title to a known paper
        url = ""
        tags = []
        matched_title = ""
        for title_lower in tags_lookup:
            if title_lower in rest.lower():
                url = url_lookup.get(title_lower, "")
                tags = tags_lookup.get(title_lower, [])
                # Find the original-cased title in rest
                idx = rest.lower().index(title_lower)
                matched_title = rest[idx:idx + len(title_lower)]
                break

        # Split into title and reason at " — " or " - "
        if matched_title:
            # Replace title with bold version
            title_end = rest.lower().index(matched_title.lower()) + len(matched_title)
            title_part = rest[:title_end]
            reason_part = rest[title_end:].lstrip(" —-").strip()
        elif " — " in rest:
            title_part, reason_part = rest.split(" — ", 1)
        elif " - " in rest:
            title_part, reason_part = rest.split(" - ", 1)
        else:
            title_part = rest
            reason_part = ""

        title_html = f"<strong>{title_part.strip()}</strong>"
        reason_html = f" &mdash; {reason_part}" if reason_part else ""
        pills_html = f" {_tag_pills_html(tags)}" if tags else ""
        url_html = (
            f'<br><a href="{url}" style="color:#666;font-size:13px;">{url}</a>'
            if url else ""
        )

        lines.append(
            f"<li style='margin-bottom: 14px;'>"
            f'<span style="color:#999;">[{queue_num}]</span> '
            f"{title_html}{reason_html}{pills_html}{url_html}"
            f"</li>"
        )

    lines.append("</ul>")
    lines.append(_queue_health_html(state))
    lines.append("</body></html>")
    return "\n".join(lines)
