"""AI-powered paper summarization using Claude."""

import logging
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
        f"2. The core idea in one sentence (two short ones max). Focus on the single "
        f"most important takeaway — don't rephrase it a second way. Never start "
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


def summarize_skimmed_paper(
    title: str,
    abstract: str = "",
) -> str:
    """Generate a one-sentence summary for a skimmed paper.

    Returns a single sentence for both the reading log and the note.
    """
    if not config.ANTHROPIC_API_KEY:
        return _fallback_skimmed(title, abstract)

    if not abstract:
        return f"Skimmed *{title}*."

    prompt = (
        f"Write one or two short sentences stating the core idea of this paper. "
        f"Never start with 'this paper' or 'the authors' — just state the idea "
        f"directly. Focus on the single most important takeaway.\n\n"
        f"Paper: {title}\n\nAbstract: {abstract}"
    )

    return _call_claude(prompt) or _fallback_skimmed(title, abstract)


def _call_claude(prompt: str) -> Optional[str]:
    """Call Claude API and return the response text, or None on failure."""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
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


def _fallback_skimmed(title: str, abstract: str) -> str:
    """Fallback summary when Claude API is unavailable."""
    if abstract:
        sentences = abstract.replace("\n", " ").split(". ")
        return sentences[0].strip() + ("." if not sentences[0].strip().endswith(".") else "")
    return f"Skimmed *{title}*."
