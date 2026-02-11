"""Semantic Scholar API integration.

Looks up papers by DOI (preferred) or title to fetch citation counts
and recommended related papers. Free API, no key needed.
"""

import logging
from typing import Any, Dict, List, Optional

import requests

from papers_workflow import config

log = logging.getLogger(__name__)

_BASE = "https://api.semanticscholar.org"
_PAPER_FIELDS = "citationCount,influentialCitationCount,url,paperId"
_REC_FIELDS = "title,externalIds,year,url"


def lookup_paper(doi: str = "", title: str = "") -> Optional[Dict[str, Any]]:
    """Look up a paper on Semantic Scholar.

    Tries DOI first, falls back to title search.
    Returns None if the paper can't be found or the API fails.
    """
    paper = None
    if doi:
        paper = _fetch_by_doi(doi)
    if paper is None and title:
        paper = _fetch_by_title(title)
    if paper is None:
        return None

    citation_count = paper.get("citationCount") or 0
    influential = paper.get("influentialCitationCount") or 0
    s2_url = paper.get("url") or ""
    paper_id = paper.get("paperId") or ""

    related = _fetch_recommendations(paper_id) if paper_id else []

    return {
        "citation_count": citation_count,
        "influential_citation_count": influential,
        "s2_url": s2_url,
        "related_papers": related,
    }


def _fetch_by_doi(doi: str) -> Optional[Dict[str, Any]]:
    """Fetch paper metadata by DOI."""
    try:
        resp = requests.get(
            f"{_BASE}/graph/v1/paper/DOI:{doi}",
            params={"fields": _PAPER_FIELDS},
            timeout=config.HTTP_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json()
        log.debug("S2 DOI lookup returned %d for %s", resp.status_code, doi)
    except Exception:
        log.debug("S2 DOI lookup failed for %s", doi, exc_info=True)
    return None


def _fetch_by_title(title: str) -> Optional[Dict[str, Any]]:
    """Fetch paper metadata by title search (first result)."""
    try:
        resp = requests.get(
            f"{_BASE}/graph/v1/paper/search",
            params={"query": title, "limit": 1, "fields": _PAPER_FIELDS},
            timeout=config.HTTP_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            papers = data.get("data", [])
            if papers:
                return papers[0]
        log.debug("S2 title search returned %d for '%s'", resp.status_code, title)
    except Exception:
        log.debug("S2 title search failed for '%s'", title, exc_info=True)
    return None


def _fetch_recommendations(paper_id: str) -> List[Dict[str, str]]:
    """Fetch up to 5 recommended papers."""
    try:
        resp = requests.get(
            f"{_BASE}/recommendations/v1/papers/forpaper/{paper_id}",
            params={"fields": _REC_FIELDS, "limit": 5},
            timeout=config.HTTP_TIMEOUT,
        )
        if resp.status_code != 200:
            log.debug("S2 recommendations returned %d", resp.status_code)
            return []

        results = []
        for p in resp.json().get("recommendedPapers", [])[:5]:
            ext = p.get("externalIds") or {}
            results.append({
                "title": p.get("title", ""),
                "year": p.get("year") or 0,
                "url": p.get("url", ""),
                "doi": ext.get("DOI", ""),
            })
        return results
    except Exception:
        log.debug("S2 recommendations failed for %s", paper_id, exc_info=True)
        return []
