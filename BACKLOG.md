# Backlog

## Tier 1 — Next up

### 1. Smart storage: delete PDFs from Zotero, annotated copies to Obsidian
Zotero free tier is 300MB and we currently double storage per paper (original + annotated).
New flow: save the annotated PDF to the Obsidian vault (`Papers/attachments/`), link it from the note, then **delete the original PDF attachment from Zotero** (keep the metadata item). Papers can always be re-downloaded. This makes the free tier sustainable indefinitely.

### 2. Richer Obsidian notes
Pull abstract, DOI, journal/venue, and URL from Zotero metadata. Add to YAML frontmatter and note body. Foundation for Dataview queries and Claude summarization.

### 3. Claude paper summarization
After extracting highlights, call Claude API to generate:
- One-paragraph summary (under `## Summary` in the note)
- Auto-suggested topic tags (`protein-engineering`, `single-cell`, `ML-methods`, etc.)
- One-sentence elevator pitch (stored in frontmatter for the weekly digest)

### 4. Weekly email digest
Every Sunday, compile papers read that week into a formatted email:
- One-sentence Claude summary per paper
- Link to Zotero item and Obsidian note
- Total highlights count
- Use Resend, SendGrid, or simple SMTP
- Doubles as a shareable "what I read this week" newsletter

### 5. GitHub Actions scheduling
Run the workflow in the cloud on a cron (works when laptop is closed):
- Secrets: Zotero API key, reMarkable device token, Claude API key
- Persist `state.json` across runs (commit to repo or use artifacts)
- Push Obsidian notes to vault repo (if git-backed) or skip Obsidian in cloud mode
- Trigger weekly email from a separate scheduled workflow

## Tier 2 — High value, moderate effort

### 6. Re-process command
`papers-workflow --reprocess "Paper Title"` to re-run highlight extraction + PDF rendering on an already-processed paper. Useful after adding more highlights on a second read.

### 7. Zotero notes sync
Push the Claude summary + highlights back to the Zotero item's note field. Makes the summary searchable in Zotero and visible on mobile.

### 8. Smart highlight categories
Use Claude to classify each highlight as "key finding", "method", "limitation", "future work", "background". Group them in the Obsidian note under labeled sections instead of a flat list.

### 9. Related papers discovery
After processing a paper, use Semantic Scholar API to find related papers. Add a `## Related` section to the Obsidian note with titles + links. Could auto-add the most relevant ones to Zotero.

### 10. Zotero collection filtering
Only sync papers from specific collections (configurable via `ZOTERO_COLLECTIONS`). For people who use Zotero broadly but only want some papers on reMarkable.

### 11. Reading queue insights
Track how long papers sit in `/To Read`. Notify if a paper has been unread for >2 weeks. Suggest which to read next based on topic diversity or recency.

## Tier 3 — Nice to have

### 12. Paper comparison tables
When multiple papers on the same topic are processed, Claude generates a comparison table (approach, dataset, key result, limitation) as a standalone Obsidian note.

### 13. Research questions extraction
Claude identifies open questions and future directions from the paper. Add as a section in the note. Helps identify research gaps.

### 14. Obsidian Canvas integration
Auto-generate a research map (Canvas file) connecting papers by shared topics/citations. Visual overview of your reading.

### 15. Reading stats dashboard
Papers per week/month, highlights per paper, topic distribution, reading streaks. Obsidian Dataview note or standalone HTML report.

### 16. Handwritten margin notes
Extract pen strokes from `.rm` files, render as images, embed in Obsidian note alongside text highlights.

### 17. Dry run mode
`papers-workflow --dry-run` to preview what would happen without making any changes.

### 18. Log rotation + better notifications
Rotate log files, richer macOS notifications (paper titles), optional Slack/Discord webhooks.

### 19. Literature review generator
Select a set of papers, Claude generates a mini literature review section synthesizing their findings. Export as markdown or LaTeX.
