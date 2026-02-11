# Backlog

## Done

- ~~Smart storage~~ — PDFs deleted from Zotero after upload. Originals in Obsidian `Inbox/`, annotated in `Read/`. Zotero free tier is sustainable.
- ~~Re-process command~~ — `--reprocess "Paper Title"` re-runs highlights + PDF rendering. Reuses cached summaries.
- ~~Richer Obsidian notes~~ — DOI, abstract, journal, publication date, URL in YAML frontmatter.
- ~~Claude summarization~~ — One-sentence takeaway + paragraph summary. Cached in state.
- ~~Weekly email digest~~ — `--digest` via Resend with read/leafed papers, summaries, URLs.
- ~~Zotero notes sync~~ — Summary + highlights pushed to Zotero child note.
- ~~Dry run mode~~ — `--dry-run` previews without changes.
- ~~Read vs Leafed triage~~ — Two processing paths with different depth.
- ~~Obsidian deep links~~ — "Open in Obsidian" attachment in Zotero.
- ~~Safety improvements~~ — Stale lock, create-then-delete, try-except, per-paper saves.
- ~~Two-column highlights~~ — y-sorted merging with boundary deduplication.
- ~~AI reading log~~ — `Reading Log.md` with dates and one-sentence summaries.
- ~~Topic tags~~ — 3-5 tags + paper type at ingestion. `--backfill-tags` for existing papers.
- ~~Paper suggestions~~ — `--suggest` daily email, `--promote` moves picks to RM root.
- ~~GitHub Actions~~ — Scheduled `--suggest`, `--digest`, `--sync-state`.
- ~~Semantic Scholar enrichment~~ — Citation counts + 5 related papers at ingestion. `--backfill-s2` for existing papers.
- ~~Structured highlights~~ — Claude classifies into Key Findings, Methods, Limitations, Future Work, Background.
- ~~Reading analytics dashboard~~ — `Reading Stats.md` Dataview note: monthly breakdown, topics, status distribution.
- ~~Monthly research themes~~ — `--themes` synthesizes a month's reading into a research narrative. GitHub Actions on 1st.

---

## Tier 2 — High value, moderate effort

### Collection filtering
Only sync papers from specific Zotero collections (configurable via `ZOTERO_COLLECTIONS`). Skip everything else.

**Why**: Useful if you use Zotero broadly but only want some papers on reMarkable. Simple config + one filter in Step 1.

### Research questions extraction
Claude extracts open questions and future directions from highlights. Add as a `## Open Questions` section in the note.

**Why**: The most actionable part of a paper is often what it *doesn't* answer. Having these extracted makes it easy to spot research gaps when reviewing notes later.

### Richer weekly digest
Add to the email: highlight count per paper, topic tags as colored pills, reading velocity ("you read 4 papers this week, up from 2"), and Obsidian deep links for desktop readers.

**Why**: The current digest is functional but sparse. Small additions make it something you actually look forward to opening.

### Queue health alerts
When the `--suggest` email fires, include a "queue health" section: total papers waiting, oldest paper age, papers added vs. processed this week. Flag papers sitting > 30 days.

**Why**: A growing backlog is invisible until it's overwhelming. Surfacing it in the daily email creates gentle accountability.

---

## Tier 3 — Ambitious, worth exploring

### Paper comparison tables
When you process a paper with tags similar to an existing one, Claude generates a comparison table (approach, dataset, key result, limitation) and appends it to both notes.

**Why**: Powerful for literature review prep. Requires cross-paper queries (match by tag overlap).

### Obsidian Canvas maps
Auto-generate a `.canvas` file connecting papers by shared topic tags. Nodes = papers, edges = shared tags. Update on each run.

**Why**: Visual research landscape. Obsidian Canvas is native, no plugins needed. But the format is JSON and finicky to generate well.

### Handwritten margin notes
Extract pen strokes from `.rm` files, render as SVG/PNG images, embed in the Obsidian note alongside text highlights.

**Why**: Some of the best thinking happens in margins. But rmscene pen stroke extraction is complex and rendering quality varies.

### Literature review generator
`--review "topic"` — Claude synthesizes all papers matching a topic tag into a structured mini literature review (intro, themes, gaps, conclusion). Export as a standalone Obsidian note.

**Why**: The dream feature. But requires good structured highlights (Tier 1) and enough papers per topic to be useful.

---

## Dropped

- ~~Log rotation + better notifications~~ — Low impact. Current notifications work fine, logs don't grow fast enough to matter.
