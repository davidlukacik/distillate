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
) -> Tuple[str, str]:
    """Generate summaries for a read paper.

    Returns (note_summary, log_sentence):
      - note_summary: 3-4 sentence paragraph for the Obsidian note
      - log_sentence: one sentence for the reading log
    """
    if not config.ANTHROPIC_API_KEY:
        return _fallback_read(title, abstract, highlights)

    context_parts = []
    if abstract:
        context_parts.append(f"Abstract: {abstract}")
    if highlights:
        context_parts.append("Highlights from reading:\n" + "\n".join(f"- {h}" for h in highlights))

    if not context_parts:
        return f"Read *{title}*.", f"Read *{title}*."

    context = "\n\n".join(context_parts)

    prompt = (
        f"You are summarizing a research paper for a personal reading log.\n\n"
        f"Paper: {title}\n\n{context}\n\n"
        f"Provide two summaries, separated by the exact line '---':\n"
        f"1. A paragraph (3-4 sentences) for the top of my note. State the key "
        f"idea directly as fact — never start with 'this paper' or 'the authors'. "
        f"Include specific methods, results, or numbers where possible.\n"
        f"2. The core idea in ONE punchy sentence (25 words max). Focus on the single "
        f"most important takeaway — don't rephrase or elaborate. Never start "
        f"with 'the paper' or 'this study'. Just state the idea directly.\n\n"
        f"Format:\n[paragraph]\n---\n[sentences]"
    )

    result = _call_claude(prompt)
    if result and "---" in result:
        parts = result.split("---", 1)
        note_summary = parts[0].strip()
        log_sentence = parts[1].strip()
        return note_summary, log_sentence

    if result:
        # Couldn't parse, use full result as note summary, first sentence as log
        sentences = result.split(". ")
        return result, sentences[0].strip() + ("." if not sentences[0].strip().endswith(".") else "")

    return _fallback_read(title, abstract, highlights)


def extract_questions(
    title: str,
    highlights: Optional[List[str]] = None,
    abstract: str = "",
) -> List[str]:
    """Extract 2-3 open research questions from a paper's highlights.

    Returns a list of question strings, or empty list on failure.
    """
    if not config.ANTHROPIC_API_KEY:
        return []

    context_parts = []
    if highlights:
        context_parts.append("Highlights:\n" + "\n".join(f"- {h}" for h in highlights))
    if abstract:
        context_parts.append(f"Abstract: {abstract}")

    if not context_parts:
        return []

    context = "\n\n".join(context_parts)

    prompt = (
        f"Based on these highlights from the paper \"{title}\", identify 2-3 "
        f"open research questions, gaps, or directions for future work that "
        f"emerge from the reading.\n\n"
        f"{context}\n\n"
        f"Be specific and actionable — each question should point toward a "
        f"concrete investigation, not a vague area. Return a numbered list.\n"
        f"If no clear questions emerge, return exactly: none"
    )

    result = _call_claude(prompt, max_tokens=200)
    if not result or result.strip().lower() == "none":
        return []

    questions = []
    for line in result.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Strip leading number + punctuation (e.g. "1. ", "1) ", "- ")
        cleaned = re.sub(r"^\d+[.)]\s*", "", line)
        cleaned = re.sub(r"^[-*]\s*", "", cleaned)
        if cleaned:
            questions.append(cleaned)

    return questions[:3]


def extract_tags(title: str, abstract: str = "") -> Tuple[List[str], str]:
    """Extract topic tags and paper type from a paper's abstract.

    Returns (tags, paper_type):
      - tags: 3-5 lowercase kebab-case topic tags
      - paper_type: one of empirical, methods, review, opinion, theoretical
    """
    if not config.ANTHROPIC_API_KEY or not abstract:
        return [], ""

    prompt = (
        f"Analyze this research paper and return:\n"
        f"1. 3-5 topic tags (lowercase, kebab-case like 'bayesian-inference' or "
        f"'protein-engineering'). Cover the research area, methodology, and "
        f"application domain.\n"
        f"2. Paper type: one of empirical, methods, review, opinion, theoretical.\n\n"
        f"Paper: {title}\nAbstract: {abstract}\n\n"
        f"Format (exactly):\ntags: tag1, tag2, tag3\ntype: paper_type"
    )

    result = _call_claude(prompt, max_tokens=100)
    if not result:
        return [], ""

    tags = []
    paper_type = ""
    for line in result.strip().split("\n"):
        line = line.strip().lower()
        if line.startswith("tags:"):
            raw = line[5:].strip()
            tags = [t.strip() for t in raw.split(",") if t.strip()]
        elif line.startswith("type:"):
            paper_type = line[5:].strip()

    return tags, paper_type


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
) -> Tuple[str, str]:
    """Fallback summaries when Claude API is unavailable."""
    if abstract:
        sentences = abstract.replace("\n", " ").split(". ")
        note = ". ".join(sentences[:3]).strip()
        if not note.endswith("."):
            note += "."
        log_s = sentences[0].strip()
        if not log_s.endswith("."):
            log_s += "."
        return note, log_s
    if highlights:
        return highlights[0], highlights[0]
    return f"Read *{title}*.", f"Read *{title}*."


