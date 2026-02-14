# Backlog

## Done

- ~~Smart storage~~ — PDFs deleted from Zotero after upload. Originals in Obsidian `Inbox/`, annotated in `Read/`. Zotero free tier is sustainable.
- ~~Re-process command~~ — `--reprocess "Paper Title"` re-runs highlights + PDF rendering + AI summaries.
- ~~Richer Obsidian notes~~ — DOI, abstract, journal, publication date, URL in YAML frontmatter.
- ~~Claude summarization~~ — Impact-focused one-liner + paragraph summary + key learnings with "so what". Sonnet for quality.
- ~~Weekly email digest~~ — `--digest` via Resend with read papers, summaries, URLs.
- ~~Zotero notes sync~~ — Summary + highlights pushed to Zotero child note.
- ~~Dry run mode~~ — `--dry-run` previews without changes.
- ~~Obsidian deep links~~ — "Open in Obsidian" attachment in Zotero.
- ~~Safety improvements~~ — Stale lock, create-then-delete, try-except, per-paper saves.
- ~~Two-column highlights~~ — y-sorted merging with boundary deduplication.
- ~~AI reading log~~ — `Reading Log.md` with dates and one-sentence summaries, sorted newest-first.
- ~~Paper suggestions~~ — `--suggest` daily email, `--promote` moves picks to RM root.
- ~~GitHub Actions~~ — Scheduled `--suggest`, `--digest`, `--sync-state`.
- ~~Semantic Scholar enrichment~~ — Citation counts at ingestion. `--backfill-s2` for existing papers.
- ~~Reading analytics dashboard~~ — `Reading Stats.md` Dataview note: monthly breakdown, topics, recent completions.
- ~~Monthly research themes~~ — `--themes` synthesizes a month's reading into a research narrative.
- ~~Leafed removal~~ — Never used in practice. Unified into single Read path.

---

## Tier 2 — High value, moderate effort

### Collection filtering
Only sync papers from specific Zotero collections (configurable via `ZOTERO_COLLECTIONS`). Skip everything else.

**Why**: Useful if you use Zotero broadly but only want some papers on reMarkable.

### Cross-paper wiki-links
At note creation time, find 2-3 existing papers with overlapping topic tags and add a `## Related Reading` section with `[[wiki-links]]`. No AI needed, just tag matching against state.json.

**Why**: Builds an organic knowledge graph as you read more papers. Most useful after 10+ read papers.

### Richer weekly digest
Add to the email: highlight count per paper, topic tags as colored pills, reading velocity, and Obsidian deep links for desktop readers.

**Why**: The current digest is functional but sparse.

### Queue health alerts
When the `--suggest` email fires, include a "queue health" section: total papers waiting, oldest paper age, papers added vs. processed this week.

**Why**: A growing backlog is invisible until it's overwhelming.

---

## Tier 3 — Ambitious, worth exploring

### Paper comparison tables
When you process a paper with tags similar to an existing one, Claude generates a comparison table (approach, dataset, key result, limitation) and appends it to both notes.

**Why**: Powerful for literature review prep. Requires cross-paper queries.

### Obsidian Canvas maps
Auto-generate a `.canvas` file connecting papers by shared topic tags. Nodes = papers, edges = shared tags.

**Why**: Visual research landscape. Obsidian Canvas is native, no plugins needed.

### Handwritten margin notes
Extract pen strokes from `.rm` files, render as SVG/PNG images, embed in the Obsidian note alongside text highlights.

**Why**: Some of the best thinking happens in margins. But rmscene pen stroke extraction is complex.

### Literature review generator
`--review "topic"` — Claude synthesizes all papers matching a topic tag into a structured mini literature review.

**Why**: The dream feature. Requires enough papers per topic to be useful.

---

## Dropped

- ~~Log rotation + better notifications~~ — Low impact. Current notifications work fine, logs don't grow fast enough to matter.
- ~~Read vs Leafed triage~~ — Zero papers ever used the Leafed path.
- ~~AI-generated topic tags~~ — Too noisy. Zotero's own arxiv/biorxiv categories are better.
- ~~Structured highlight categories~~ — AI classification into categories was too noisy; page-based grouping works better.
- ~~Open questions extraction~~ — Tried and dropped. Key learnings with "so what" bullet are more useful.
