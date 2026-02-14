"""AI-powered paper summarization using Claude."""

import logging
import re
from typing import List, Optional, Tuple

from papers_workflow import config

log = logging.getLogger(__name__)


def summarize_read_paper(
    title: str,
    abstract: str = "",
    highlights: Optional[List[str]] = None,
) -> str:
    """Generate a high-level summary for a read paper.

    Returns a 2-3 sentence summary describing what the paper does and its
    core thesis. Used identically in the Obsidian note and reading log.
    """
    if not config.ANTHROPIC_API_KEY:
        return _fallback_read(title, abstract, highlights)

    context_parts = []
    if abstract:
        context_parts.append(f"Abstract: {abstract}")
    if highlights:
        context_parts.append("Highlights from reading:\n" + "\n".join(f"- {h}" for h in highlights))

    if not context_parts:
        return f"Read *{title}*."

    context = "\n\n".join(context_parts)

    prompt = (
        f"You are summarizing a research paper for a personal reading log.\n\n"
        f"Paper: {title}\n\n{context}\n\n"
        f"Write a 2-3 sentence summary that describes what this paper does and "
        f"its core thesis. Write so that someone who read this paper years ago "
        f"can immediately recall what it was about. State the idea directly as "
        f"fact — never start with 'this paper' or 'the authors'. Include "
        f"specific methods, results, or numbers where possible.\n\n"
        f"Return ONLY the summary, nothing else."
    )

    result = _call_claude(prompt)
    if result:
        return result

    return _fallback_read(title, abstract, highlights)


def extract_insights(
    title: str,
    highlights: Optional[List[str]] = None,
    abstract: str = "",
) -> Tuple[List[str], List[str]]:
    """Extract key learnings and open questions from a paper's highlights.

    Returns (learnings, questions) — each a list of short bullet-point strings.
    """
    if not config.ANTHROPIC_API_KEY:
        return [], []

    context_parts = []
    if highlights:
        context_parts.append("Highlights:\n" + "\n".join(f"- {h}" for h in highlights))
    if abstract:
        context_parts.append(f"Abstract: {abstract}")

    if not context_parts:
        return [], []

    context = "\n\n".join(context_parts)

    prompt = (
        f"From these highlights of \"{title}\":\n\n"
        f"{context}\n\n"
        f"Return two sections separated by '---':\n"
        f"LEARNINGS: 3-5 key facts or insights. Each must be one short sentence "
        f"(max 15 words). State facts directly, no filler.\n"
        f"QUESTIONS: 2-3 open questions or gaps. Each must be one short sentence "
        f"(max 15 words). Be specific.\n\n"
        f"Format:\n"
        f"- learning one\n"
        f"- learning two\n"
        f"---\n"
        f"- question one\n"
        f"- question two"
    )

    result = _call_claude(prompt, max_tokens=300)
    if not result:
        return [], []

    learnings = []
    questions = []
    target = learnings
    for line in result.strip().split("\n"):
        line = line.strip()
        if line == "---":
            target = questions
            continue
        if not line:
            continue
        cleaned = re.sub(r"^\d+[.)]\s*", "", line)
        cleaned = re.sub(r"^[-*]\s*", "", cleaned)
        cleaned = re.sub(r"^\*\*.*?\*\*\s*", "", cleaned)  # strip bold labels
        cleaned = re.sub(r"^(LEARNINGS|QUESTIONS):?\s*", "", cleaned, flags=re.IGNORECASE)
        if cleaned:
            target.append(cleaned)

    return learnings[:5], questions[:3]



def suggest_papers(
    unread: List[dict],
    recent_reads: List[dict],
) -> Optional[str]:
    """Ask Claude to pick the 3 best papers to read next.

    Returns the raw response text, or None on failure.
    """
    if not config.ANTHROPIC_API_KEY:
        return None

    # Build recent reads context
    reads_lines = []
    for p in recent_reads[:10]:
        tags = ", ".join(p.get("tags", []))
        summary = p.get("summary", "")
        status = p.get("reading_status", "read")
        reads_lines.append(f"- [{status}] {p['title']} [{tags}] — {summary}")

    # Build unread queue
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    queue_lines = []
    for i, p in enumerate(unread, 1):
        tags = ", ".join(p.get("tags", []))
        paper_type = p.get("paper_type", "")
        uploaded = p.get("uploaded_at", "")
        days = 0
        if uploaded:
            try:
                dt = datetime.fromisoformat(uploaded)
                days = (now - dt).days
            except (ValueError, TypeError):
                pass
        type_str = f" ({paper_type})" if paper_type else ""
        queue_lines.append(
            f"{i}. {p['title']} [{tags}]{type_str} — {days} days in queue"
        )

    if not queue_lines:
        return None

    reads_section = "\n".join(reads_lines) if reads_lines else "(no recent reads)"

    prompt = (
        f"I keep a reading queue of research papers. Help me pick the 3 I "
        f"should read next.\n\n"
        f"Papers I've read recently:\n{reads_section}\n\n"
        f"My reading queue:\n" + "\n".join(queue_lines) + "\n\n"
        f"Pick exactly 3 papers by number. For each, give one sentence "
        f"explaining why I should read it now. Balance:\n"
        f"- Relevance to my recent interests\n"
        f"- Diversity (don't pick 3 on the same topic)\n"
        f"- Queue age (papers sitting too long deserve attention)\n\n"
        f"Format:\n[number]. [title] — [reason]\n[number]. [title] — [reason]\n"
        f"[number]. [title] — [reason]"
    )

    return _call_claude(prompt, max_tokens=300)


def generate_monthly_themes(
    month_label: str,
    papers: List[dict],
) -> Optional[str]:
    """Synthesize all papers from a month into a research narrative.

    Returns a 300-500 word first-person synthesis, or None on failure.
    Each paper dict should have: title, tags, summary, reading_status, paper_type.
    """
    if not config.ANTHROPIC_API_KEY or not papers:
        return None

    paper_lines = []
    for p in papers:
        tags = ", ".join(p.get("tags", []))
        summary = p.get("summary", "")
        status = p.get("reading_status", "read")
        paper_type = p.get("paper_type", "")
        type_str = f" [{paper_type}]" if paper_type else ""
        paper_lines.append(
            f"- ({status}) {p['title']} [{tags}]{type_str} — {summary}"
        )

    papers_text = "\n".join(paper_lines)

    prompt = (
        f"I read these research papers in {month_label}:\n\n"
        f"{papers_text}\n\n"
        f"Write a 300-500 word first-person synthesis of my reading this month. "
        f"Cover:\n"
        f"- What themes and topics I explored\n"
        f"- Connections between papers (shared methods, complementary findings)\n"
        f"- Gaps or questions that emerged\n"
        f"- How this month's reading fits into broader research directions\n\n"
        f"Write in a reflective, personal tone — like a research diary entry. "
        f"Reference specific papers by name. Don't use bullet points or headers "
        f"— write flowing prose."
    )

    return _call_claude(prompt, max_tokens=800)


def _call_claude(prompt: str, max_tokens: int = 400) -> Optional[str]:
    """Call Claude API and return the response text, or None on failure."""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        log.info("Generated summary (%d chars)", len(text))
        return text
    except Exception:
        log.exception("Failed to generate summary via Claude API")
        return None


def _fallback_read(
    title: str, abstract: str, highlights: Optional[List[str]],
) -> str:
    """Fallback summary when Claude API is unavailable."""
    if abstract:
        sentences = abstract.replace("\n", " ").split(". ")
        summary = ". ".join(sentences[:3]).strip()
        if not summary.endswith("."):
            summary += "."
        return summary
    if highlights:
        return highlights[0]
    return f"Read *{title}*."


