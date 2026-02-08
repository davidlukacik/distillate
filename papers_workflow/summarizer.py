"""AI-powered paper summarization using Claude."""

import logging
from typing import List, Optional

from papers_workflow import config

log = logging.getLogger(__name__)


def summarize_read_paper(
    title: str,
    abstract: str = "",
    highlights: Optional[List[str]] = None,
) -> str:
    """Generate a one-paragraph summary for a read paper.

    Uses highlights and abstract to produce a concise summary.
    Returns a fallback string if the API key is not configured or the call fails.
    """
    if not config.ANTHROPIC_API_KEY:
        return _fallback_read(title, abstract, highlights)

    context_parts = []
    if abstract:
        context_parts.append(f"Abstract: {abstract}")
    if highlights:
        context_parts.append("Highlights from reading:\n" + "\n".join(f"- {h}" for h in highlights))

    if not context_parts:
        return f"Read *{title}*. No abstract or highlights available."

    context = "\n\n".join(context_parts)

    prompt = (
        f"You are summarizing a research paper for a personal reading log. "
        f"Write exactly one paragraph (3-5 sentences) summarizing the key "
        f"contributions and findings of this paper. Write in third person. "
        f"Be specific about the results, not vague.\n\n"
        f"Paper: {title}\n\n{context}"
    )

    return _call_claude(prompt) or _fallback_read(title, abstract, highlights)


def summarize_skimmed_paper(
    title: str,
    abstract: str = "",
) -> str:
    """Generate a one-sentence summary for a skimmed paper.

    Uses the abstract to produce a brief summary.
    Returns a fallback string if the API key is not configured or the call fails.
    """
    if not config.ANTHROPIC_API_KEY:
        return _fallback_skimmed(title, abstract)

    if not abstract:
        return f"Skimmed *{title}*."

    prompt = (
        f"You are summarizing a research paper for a personal reading log. "
        f"Write exactly one sentence summarizing what this paper is about. "
        f"Be specific, not vague.\n\n"
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
            max_tokens=300,
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
        # Truncate abstract to ~2 sentences
        sentences = abstract.replace("\n", " ").split(". ")
        short = ". ".join(sentences[:2]).strip()
        if not short.endswith("."):
            short += "."
        return short
    if highlights:
        return highlights[0]
    return f"Read *{title}*."


def _fallback_skimmed(title: str, abstract: str) -> str:
    """Fallback summary when Claude API is unavailable."""
    if abstract:
        sentences = abstract.replace("\n", " ").split(". ")
        return sentences[0].strip() + ("." if not sentences[0].strip().endswith(".") else "")
    return f"Skimmed *{title}*."
