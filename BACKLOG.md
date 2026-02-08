# Backlog

## Done

- ~~Smart storage~~ — PDFs deleted from Zotero immediately after upload to reMarkable. Originals kept in Obsidian `Papers/To Read/`, annotated copies in `Papers/`. Zotero free tier is sustainable.
- ~~Re-process command~~ — `papers-workflow --reprocess "Paper Title"` re-runs highlight extraction + PDF rendering. Reuses cached AI summaries.
- ~~Richer Obsidian notes~~ — DOI, abstract, journal, publication date, URL in YAML frontmatter and note body.
- ~~Claude paper summarization~~ — AI-generated 1-2 sentence takeaway (blockquote) + paragraph summary at top of note. Cached in state to avoid redundant API calls.
- ~~Weekly email digest~~ — `--digest` sends plain HTML email via Resend with read/skimmed papers, summaries, and direct URLs.
- ~~Zotero notes sync~~ — Summary + highlights pushed to Zotero child note, searchable and visible on mobile.
- ~~Dry run mode~~ — `--dry-run` previews what would happen without making any changes.
- ~~Read vs Skimmed triage~~ — Papers in `/Skimmed` on reMarkable get minimal notes, different Zotero tag, shorter summaries.
- ~~Obsidian deep links~~ — "Open in Obsidian" linked_url attachment in Zotero (desktop).
- ~~Safety improvements~~ — Stale lock detection, create-then-delete ordering, try-except per document, per-paper state saves.
- ~~Two-column highlight fix~~ — GlyphRange items sorted by y-coordinate before merging, with word deduplication at boundaries.
- ~~AI reading log~~ — Flat bullet list in `Reading Log.md` with inline dates and one-sentence summaries.

## Tier 2 — High value, moderate effort

### 7. Smart highlight categories
Use Claude to classify each highlight as "key finding", "method", "limitation", "future work", "background". Group them in the Obsidian note under labeled sections instead of a flat list.

### 8. Related papers discovery
After processing a paper, use Semantic Scholar API to find related papers. Add a `## Related` section to the Obsidian note with titles + links. Could auto-add the most relevant ones to Zotero.

### 9. Zotero collection filtering
Only sync papers from specific collections (configurable via `ZOTERO_COLLECTIONS`). For people who use Zotero broadly but only want some papers on reMarkable.

### 10. Reading queue insights
Track how long papers sit in `/To Read`. Notify if a paper has been unread for >2 weeks. Suggest which to read next based on topic diversity or recency.

## Tier 3 — Nice to have

### 11. Paper comparison tables
When multiple papers on the same topic are processed, Claude generates a comparison table (approach, dataset, key result, limitation) as a standalone Obsidian note.

### 12. Research questions extraction
Claude identifies open questions and future directions from the paper. Add as a section in the note. Helps identify research gaps.

### 13. Obsidian Canvas integration
Auto-generate a research map (Canvas file) connecting papers by shared topics/citations. Visual overview of your reading.

### 14. Reading stats dashboard
Papers per week/month, highlights per paper, topic distribution, reading streaks. Obsidian Dataview note or standalone HTML report.

### 15. Handwritten margin notes
Extract pen strokes from `.rm` files, render as images, embed in Obsidian note alongside text highlights.

### 16. GitHub Actions scheduling
Run the workflow in the cloud on a cron (works when laptop is closed). Out of scope for now.

### 17. Log rotation + better notifications
Rotate log files, richer macOS notifications (paper titles), optional Slack/Discord webhooks.

### 18. Literature review generator
Select a set of papers, Claude generates a mini literature review section synthesizing their findings. Export as markdown or LaTeX.
