"""Papers workflow entry point.

One-shot script: polls Zotero and reMarkable, processes papers, then exits.
Designed to be run on a schedule via cron or launchd.
"""

import logging
import sys
import tempfile
from pathlib import Path

import requests

log = logging.getLogger("papers_workflow")


def _reprocess(args: list[str]) -> None:
    """Re-run highlight extraction + PDF rendering on processed papers."""
    from papers_workflow import config
    from papers_workflow import remarkable_client
    from papers_workflow import obsidian
    from papers_workflow import renderer
    from papers_workflow import summarizer
    from papers_workflow import zotero_client
    from papers_workflow.state import State

    config.setup_logging()

    state = State()
    processed = state.documents_with_status("processed")

    if not processed:
        log.info("No processed papers to reprocess")
        return

    # Filter to specific title if provided
    if args:
        query = " ".join(args).lower()
        matches = [d for d in processed if query in d["title"].lower()]
        if not matches:
            log.error("No processed paper matching '%s'", " ".join(args))
            log.info("Processed papers: %s", ", ".join(d["title"] for d in processed))
            return
        processed = matches

    log.info("Reprocessing %d paper(s)...", len(processed))

    for doc in processed:
        title = doc["title"]
        rm_name = doc["remarkable_doc_name"]
        item_key = doc["zotero_item_key"]
        log.info("Reprocessing: %s", title)

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / f"{rm_name}.zip"
            pdf_path = Path(tmpdir) / f"{rm_name}.pdf"

            bundle_ok = remarkable_client.download_document_bundle_to(
                config.RM_FOLDER_VAULT, rm_name, zip_path,
            )

            if not bundle_ok or not zip_path.exists():
                log.warning("Could not download bundle for '%s', skipping", title)
                continue

            highlights = renderer.extract_highlights(zip_path)
            render_ok = renderer.render_annotated_pdf(zip_path, pdf_path)

            if render_ok and pdf_path.exists():
                annotated_bytes = pdf_path.read_bytes()
                saved = obsidian.save_annotated_pdf(title, annotated_bytes)
                pdf_filename = saved.name if saved else None
                log.info("Saved annotated PDF to Obsidian vault")
            else:
                log.warning("Could not render annotated PDF for '%s'", title)
                saved = None
                pdf_filename = None

            # Update linked attachment to point to annotated PDF
            linked = zotero_client.get_linked_attachment(item_key)
            if saved:
                new_att = zotero_client.create_linked_attachment(
                    item_key, saved.name, str(saved),
                )
                if new_att and linked:
                    zotero_client.delete_attachment(linked["key"])
            elif linked:
                zotero_client.delete_attachment(linked["key"])

            # Fetch fresh metadata from Zotero
            meta = doc.get("metadata", {})
            if not meta:
                items = zotero_client.get_items_by_keys([item_key])
                if items:
                    meta = zotero_client.extract_metadata(items[0])
                    doc["metadata"] = meta

            # Reuse stored summaries, only call API if missing
            log_sentence = doc.get("summary", "")
            note_summary = doc.get("note_summary", "")
            if not log_sentence or not note_summary:
                note_summary, log_sentence = summarizer.summarize_read_paper(
                    title, abstract=meta.get("abstract", ""), highlights=highlights,
                )

            # Recreate Obsidian note (delete existing first)
            obsidian.ensure_dataview_note()
            obsidian.delete_paper_note(title)
            obsidian.create_paper_note(
                title=title,
                authors=doc["authors"],
                date_added=doc["uploaded_at"],
                zotero_item_key=item_key,
                highlights=highlights or None,
                pdf_filename=pdf_filename,
                doi=meta.get("doi", ""),
                abstract=meta.get("abstract", ""),
                url=meta.get("url", ""),
                publication_date=meta.get("publication_date", ""),
                journal=meta.get("journal", ""),
                summary=note_summary,
                takeaway=log_sentence,
                topic_tags=meta.get("tags"),
            )

            # Add Obsidian deep link in Zotero
            obsidian_uri = obsidian.get_obsidian_uri(title)
            if obsidian_uri:
                zotero_client.create_obsidian_link(item_key, obsidian_uri)

            # Sync note to Zotero
            zotero_note_html = zotero_client._build_note_html(
                takeaway=log_sentence, summary=note_summary, highlights=highlights,
            )
            zotero_client.set_note(item_key, zotero_note_html)

            # Update reading log
            obsidian.append_to_reading_log(title, "Read", log_sentence)

            # Save summaries to state
            state.mark_processed(
                item_key, summary=log_sentence, note_summary=note_summary,
            )
            state.save()

            log.info("Reprocessed: %s", title)


def _dry_run() -> None:
    """Preview what the workflow would do without making any changes."""
    from papers_workflow import config
    from papers_workflow import zotero_client
    from papers_workflow import remarkable_client
    from papers_workflow.state import State

    config.setup_logging()

    log.info("=== DRY RUN — no changes will be made ===")
    state = State()

    # Retry queue
    awaiting = state.documents_with_status("awaiting_pdf")
    if awaiting:
        log.info("[dry-run] %d paper(s) awaiting PDF sync:", len(awaiting))
        for doc in awaiting:
            log.info("  - %s", doc["title"])

    # Step 1: Check Zotero for new papers
    current_version = zotero_client.get_library_version()
    stored_version = state.zotero_library_version

    if stored_version == 0:
        log.info("[dry-run] First run — would set version watermark to %d", current_version)
    elif current_version == stored_version:
        log.info("[dry-run] Zotero library unchanged (version %d)", current_version)
    else:
        log.info("[dry-run] Zotero library changed: %d → %d", stored_version, current_version)
        changed_keys, _ = zotero_client.get_changed_item_keys(stored_version)
        new_keys = [k for k in changed_keys if not state.has_document(k)]
        if new_keys:
            items = zotero_client.get_items_by_keys(new_keys)
            new_papers = zotero_client.filter_new_papers(items)
            if new_papers:
                log.info("[dry-run] Would send %d paper(s) to reMarkable:", len(new_papers))
                for p in new_papers:
                    meta = zotero_client.extract_metadata(p)
                    log.info("  - %s (%s)", meta["title"], ", ".join(meta["authors"][:2]))
            else:
                log.info("[dry-run] No new papers to send")
        else:
            log.info("[dry-run] All changed items already tracked")

    # Step 2: Check reMarkable for read papers
    on_remarkable = state.documents_with_status("on_remarkable")
    read_docs = remarkable_client.list_folder(config.RM_FOLDER_READ)

    read_matches = [d for d in on_remarkable if d["remarkable_doc_name"] in read_docs]
    if read_matches:
        log.info("[dry-run] Would process %d read paper(s):", len(read_matches))
        for doc in read_matches:
            log.info("  - %s", doc["title"])
    else:
        log.info("[dry-run] No read papers to process")

    # Step 2b: Check reMarkable for leafed papers
    leafed_docs = remarkable_client.list_folder(config.RM_FOLDER_LEAFED)

    leafed_matches = [d for d in on_remarkable if d["remarkable_doc_name"] in leafed_docs]
    if leafed_matches:
        log.info("[dry-run] Would process %d leafed paper(s):", len(leafed_matches))
        for doc in leafed_matches:
            log.info("  - %s", doc["title"])
    else:
        log.info("[dry-run] No leafed papers to process")

    # Summary
    total = len(read_matches) + len(leafed_matches)
    if awaiting:
        total += len(awaiting)
    if total:
        log.info("[dry-run] Total actions: %d paper(s) would be processed", total)
    else:
        log.info("[dry-run] Nothing to do")

    log.info("=== DRY RUN complete ===")


def _backfill_tags() -> None:
    """Backfill topic tags for papers that don't have them yet."""
    from papers_workflow import config
    from papers_workflow import summarizer
    from papers_workflow import zotero_client
    from papers_workflow.state import State

    config.setup_logging()

    state = State()
    count = 0

    for key, doc in state.documents.items():
        meta = doc.get("metadata", {})
        if meta.get("tags"):
            continue

        # Fetch metadata from Zotero if missing
        if not meta.get("abstract"):
            items = zotero_client.get_items_by_keys([key])
            if items:
                meta = zotero_client.extract_metadata(items[0])
                doc["metadata"] = meta

        abstract = meta.get("abstract", "")
        if not abstract:
            log.info("No abstract for '%s', skipping tags", doc["title"])
            continue

        tags, paper_type = summarizer.extract_tags(doc["title"], abstract)
        if tags:
            meta["tags"] = tags
            log.info("Tagged '%s': %s", doc["title"], ", ".join(tags))
        if paper_type:
            meta["paper_type"] = paper_type

        doc["metadata"] = meta
        state.save()
        count += 1

    log.info("Backfilled tags for %d paper(s)", count)


def _sync_state() -> None:
    """Upload state.json to a private GitHub Gist for GitHub Actions."""
    import subprocess

    from papers_workflow import config

    config.setup_logging()

    gist_id = config.STATE_GIST_ID
    if not gist_id:
        log.error("STATE_GIST_ID not set — run: gh gist create state.json")
        return

    from papers_workflow.state import STATE_PATH
    if not STATE_PATH.exists():
        log.info("No state.json to sync")
        return

    subprocess.run(
        ["gh", "gist", "edit", gist_id, "-f", "state.json", str(STATE_PATH)],
        check=True,
    )
    log.info("Synced state.json to gist %s", gist_id)


def _promote() -> None:
    """Pick 3 papers to read next and move them to the Papers root on reMarkable."""
    from datetime import datetime, timedelta, timezone

    from papers_workflow import config
    from papers_workflow import remarkable_client
    from papers_workflow import summarizer
    from papers_workflow.state import State

    config.setup_logging()

    state = State()

    # Demote old promoted papers back to Inbox
    old_promoted = state.promoted_papers
    if old_promoted:
        papers_root_docs = remarkable_client.list_folder(config.RM_FOLDER_PAPERS)
        for key in old_promoted:
            doc = state.get_document(key)
            if not doc or doc["status"] != "on_remarkable":
                continue
            rm_name = doc["remarkable_doc_name"]
            if rm_name in papers_root_docs:
                remarkable_client.move_document(
                    rm_name, config.RM_FOLDER_PAPERS, config.RM_FOLDER_INBOX,
                )
                log.info("Demoted: %s", doc["title"])
        state.promoted_papers = []
        state.save()

    # Gather unread papers for suggestion
    unread = state.documents_with_status("on_remarkable")
    if not unread:
        log.info("No papers in reading queue, nothing to promote")
        return

    # Build enriched lists for suggestion engine
    unread_enriched = []
    for doc in unread:
        meta = doc.get("metadata", {})
        unread_enriched.append({
            "title": doc["title"],
            "tags": meta.get("tags", []),
            "paper_type": meta.get("paper_type", ""),
            "uploaded_at": doc.get("uploaded_at", ""),
        })

    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    recent = state.documents_processed_since(since)
    recent_enriched = []
    for doc in recent:
        meta = doc.get("metadata", {})
        recent_enriched.append({
            "title": doc["title"],
            "tags": meta.get("tags", []),
            "summary": doc.get("summary", ""),
            "reading_status": doc.get("reading_status", "read"),
        })

    # Ask Claude to pick 3
    result = summarizer.suggest_papers(unread_enriched, recent_enriched)
    if not result:
        log.warning("Could not generate suggestions")
        return

    # Match suggested titles back to documents
    inbox_docs = remarkable_client.list_folder(config.RM_FOLDER_INBOX)
    title_to_key = {doc["title"].lower(): doc["zotero_item_key"] for doc in unread}
    title_to_rm = {doc["title"].lower(): doc["remarkable_doc_name"] for doc in unread}

    promoted_keys = []
    for line in result.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        for title_lower, key in title_to_key.items():
            if title_lower in line.lower() and key not in promoted_keys:
                rm_name = title_to_rm[title_lower]
                if rm_name in inbox_docs:
                    remarkable_client.move_document(
                        rm_name, config.RM_FOLDER_INBOX, config.RM_FOLDER_PAPERS,
                    )
                    promoted_keys.append(key)
                    log.info("Promoted: %s", rm_name)
                break
        if len(promoted_keys) >= 3:
            break

    state.promoted_papers = promoted_keys
    state.save()
    log.info("Promoted %d paper(s) to Papers root", len(promoted_keys))


def main():
    if "--register" in sys.argv:
        from papers_workflow.remarkable_auth import register_interactive
        register_interactive()
        return

    if "--reprocess" in sys.argv:
        idx = sys.argv.index("--reprocess")
        _reprocess(sys.argv[idx + 1:])
        return

    if "--digest" in sys.argv:
        from papers_workflow import digest
        digest.send_weekly_digest()
        return

    if "--dry-run" in sys.argv:
        _dry_run()
        return

    if "--backfill-tags" in sys.argv:
        _backfill_tags()
        return

    if "--suggest" in sys.argv:
        from papers_workflow import digest
        digest.send_suggestion()
        return

    if "--promote" in sys.argv:
        _promote()
        return

    if "--sync-state" in sys.argv:
        _sync_state()
        return

    from papers_workflow import config
    from papers_workflow import zotero_client
    from papers_workflow import remarkable_client
    from papers_workflow import obsidian
    from papers_workflow import notify
    from papers_workflow import renderer
    from papers_workflow import summarizer
    from papers_workflow.state import State, acquire_lock, release_lock

    config.setup_logging()

    # Prevent overlapping runs
    if not acquire_lock():
        log.warning("Another instance is running (lock held), exiting")
        return

    try:
        state = State()
        sent_count = 0
        synced_count = 0

        # -- Retry papers awaiting PDF sync --
        awaiting = state.documents_with_status("awaiting_pdf")
        if awaiting:
            log.info("Retrying %d papers awaiting PDF sync...", len(awaiting))
            remarkable_client.ensure_folders()
            for doc in awaiting:
                title = doc["title"]
                att_key = doc["zotero_attachment_key"]
                item_key = doc["zotero_item_key"]
                try:
                    pdf_bytes = zotero_client.download_pdf(att_key)
                    log.info("PDF now available for '%s' (%d bytes)", title, len(pdf_bytes))
                    remarkable_client.upload_pdf_bytes(
                        pdf_bytes, config.RM_FOLDER_INBOX, title
                    )
                    saved = obsidian.save_inbox_pdf(title, pdf_bytes)
                    if saved:
                        new_att = zotero_client.create_linked_attachment(
                            item_key, saved.name, str(saved),
                        )
                        if new_att:
                            zotero_client.delete_attachment(att_key)
                        else:
                            log.warning("Could not create linked attachment for '%s', keeping imported PDF", title)
                    else:
                        zotero_client.delete_attachment(att_key)
                    zotero_client.add_tag(item_key, config.ZOTERO_TAG_INBOX)
                    state.set_status(item_key, "on_remarkable")
                    state.save()
                    sent_count += 1
                    log.info("Sent to reMarkable: %s", title)
                except requests.exceptions.HTTPError as e:
                    if e.response is not None and e.response.status_code == 404:
                        log.info("PDF still not synced for '%s', will retry", title)
                    else:
                        log.warning("Failed to retry '%s': %s", title, e)
                except Exception:
                    log.exception("Failed to retry '%s'", title)
            state.save()

        # -- Step 1: Poll Zotero for new papers --
        log.info("Step 1: Checking Zotero for new papers...")

        current_version = zotero_client.get_library_version()
        stored_version = state.zotero_library_version

        if stored_version == 0:
            # First run: just record the current version, don't process
            # existing items. Only papers added after this point will be synced.
            log.info(
                "First run: setting Zotero version watermark to %d "
                "(existing papers will not be processed)",
                current_version,
            )
            state.zotero_library_version = current_version
            state.save()
        elif current_version == stored_version:
            log.info("Zotero library unchanged (version %d)", current_version)
        else:
            log.info(
                "Zotero library changed: %d → %d",
                stored_version, current_version,
            )
            changed_keys, new_version = zotero_client.get_changed_item_keys(
                stored_version
            )

            if changed_keys:
                # Filter out items we already track
                new_keys = [
                    k for k in changed_keys if not state.has_document(k)
                ]

                if new_keys:
                    items = zotero_client.get_items_by_keys(new_keys)
                    new_papers = zotero_client.filter_new_papers(items)
                    log.info("Found %d new papers", len(new_papers))

                    # Ensure reMarkable folders exist and get existing docs
                    if new_papers:
                        remarkable_client.ensure_folders()
                        existing_on_rm = set(
                            remarkable_client.list_folder(config.RM_FOLDER_INBOX)
                        )
                    else:
                        existing_on_rm = set()

                    for paper in new_papers:
                        try:
                            item_key = paper["key"]
                            meta = zotero_client.extract_metadata(paper)
                            title = meta["title"]
                            authors = meta["authors"]

                            log.info("Processing: %s", title)

                            # Find PDF attachment
                            attachment = zotero_client.get_pdf_attachment(item_key)
                            if not attachment:
                                log.warning("No PDF attachment for '%s', skipping", title)
                                continue

                            att_key = attachment["key"]
                            att_md5 = attachment["data"].get("md5", "")

                            # Upload to reMarkable (skip if already there)
                            if title in existing_on_rm:
                                log.info("Already on reMarkable, skipping upload: %s", title)
                            else:
                                try:
                                    pdf_bytes = zotero_client.download_pdf(att_key)
                                except requests.exceptions.HTTPError as e:
                                    if e.response is not None and e.response.status_code == 404:
                                        log.warning(
                                            "PDF not yet synced to Zotero cloud for '%s', "
                                            "will retry next run", title,
                                        )
                                        state.add_document(
                                            zotero_item_key=item_key,
                                            zotero_attachment_key=att_key,
                                            zotero_attachment_md5=att_md5,
                                            remarkable_doc_name=remarkable_client._sanitize_filename(title),
                                            title=title,
                                            authors=authors,
                                            status="awaiting_pdf",
                                            metadata=meta,
                                        )
                                        continue
                                    raise
                                log.info("Downloaded PDF (%d bytes)", len(pdf_bytes))
                                remarkable_client.upload_pdf_bytes(
                                    pdf_bytes, config.RM_FOLDER_INBOX, title
                                )
                                # Save original to Obsidian Inbox folder
                                saved = obsidian.save_inbox_pdf(title, pdf_bytes)
                                # Create linked attachment, then delete imported
                                if saved:
                                    new_att = zotero_client.create_linked_attachment(
                                        item_key, saved.name, str(saved),
                                    )
                                    if new_att:
                                        zotero_client.delete_attachment(att_key)
                                    else:
                                        log.warning("Could not create linked attachment for '%s', keeping imported PDF", title)
                                else:
                                    zotero_client.delete_attachment(att_key)

                            # Extract topic tags
                            tags, paper_type = summarizer.extract_tags(
                                title, meta.get("abstract", ""),
                            )
                            if tags:
                                meta["tags"] = tags
                            if paper_type:
                                meta["paper_type"] = paper_type

                            # Tag in Zotero
                            zotero_client.add_tag(item_key, config.ZOTERO_TAG_INBOX)

                            # Track in state
                            state.add_document(
                                zotero_item_key=item_key,
                                zotero_attachment_key=att_key,
                                zotero_attachment_md5=att_md5,
                                remarkable_doc_name=remarkable_client._sanitize_filename(title),
                                title=title,
                                authors=authors,
                                metadata=meta,
                            )
                            state.save()
                            sent_count += 1
                            log.info("Sent to reMarkable: %s", title)

                        except Exception:
                            log.exception("Failed to process paper '%s', skipping",
                                          paper.get("data", {}).get("title", paper.get("key")))
                            continue

            state.zotero_library_version = current_version
            state.save()

        # -- Step 2: Poll reMarkable for read papers --
        log.info("Step 2: Checking reMarkable for read papers...")

        read_docs = remarkable_client.list_folder(config.RM_FOLDER_READ)
        on_remarkable = state.documents_with_status("on_remarkable")

        for doc in on_remarkable:
            rm_name = doc["remarkable_doc_name"]

            if rm_name not in read_docs:
                continue

            log.info("Found read paper: %s", rm_name)
            item_key = doc["zotero_item_key"]

            try:
                highlights = None

                with tempfile.TemporaryDirectory() as tmpdir:
                    zip_path = Path(tmpdir) / f"{rm_name}.zip"
                    pdf_path = Path(tmpdir) / f"{rm_name}.pdf"

                    # Download raw document bundle
                    bundle_ok = remarkable_client.download_document_bundle_to(
                        config.RM_FOLDER_READ, rm_name, zip_path,
                    )

                    if bundle_ok and zip_path.exists():
                        # Extract highlighted text
                        highlights = renderer.extract_highlights(zip_path)
                        if not highlights:
                            log.info("No text highlights found for '%s'", rm_name)

                        # Render annotated PDF
                        render_ok = renderer.render_annotated_pdf(zip_path, pdf_path)
                    else:
                        render_ok = False

                    # Fall back to geta if render failed
                    if not render_ok:
                        log.info("Falling back to rmapi geta for '%s'", rm_name)
                        render_ok = remarkable_client.download_annotated_pdf_to(
                            config.RM_FOLDER_READ, rm_name, pdf_path,
                        )

                    pdf_filename = None
                    if render_ok and pdf_path.exists():
                        annotated_bytes = pdf_path.read_bytes()
                        saved = obsidian.save_annotated_pdf(doc["title"], annotated_bytes)
                        if saved:
                            pdf_filename = saved.name
                            log.info("Saved annotated PDF to Obsidian vault")
                    else:
                        log.warning(
                            "Could not get annotated PDF for '%s'", rm_name,
                        )

                    # Clean up original from Inbox folder
                    obsidian.delete_inbox_pdf(doc["title"])

                    # Update linked attachment to point to annotated PDF
                    linked = zotero_client.get_linked_attachment(item_key)
                    if saved:
                        new_att = zotero_client.create_linked_attachment(
                            item_key, saved.name, str(saved),
                        )
                        if new_att and linked:
                            zotero_client.delete_attachment(linked["key"])
                    elif linked:
                        zotero_client.delete_attachment(linked["key"])

                # Update Zotero tag
                zotero_client.replace_tag(
                    item_key, config.ZOTERO_TAG_INBOX, config.ZOTERO_TAG_READ,
                )

                # Generate AI summaries
                meta = doc.get("metadata", {})
                note_summary, log_sentence = summarizer.summarize_read_paper(
                    doc["title"],
                    abstract=meta.get("abstract", ""),
                    highlights=highlights,
                )

                # Create Obsidian note with extracted highlights
                obsidian.ensure_dataview_note()
                obsidian.create_paper_note(
                    title=doc["title"],
                    authors=doc["authors"],
                    date_added=doc["uploaded_at"],
                    zotero_item_key=item_key,
                    highlights=highlights or None,
                    pdf_filename=pdf_filename,
                    doi=meta.get("doi", ""),
                    abstract=meta.get("abstract", ""),
                    url=meta.get("url", ""),
                    publication_date=meta.get("publication_date", ""),
                    journal=meta.get("journal", ""),
                    summary=note_summary,
                    takeaway=log_sentence,
                    topic_tags=meta.get("tags"),
                )

                # Add Obsidian deep link in Zotero
                obsidian_uri = obsidian.get_obsidian_uri(doc["title"])
                if obsidian_uri:
                    zotero_client.create_obsidian_link(item_key, obsidian_uri)

                # Sync note to Zotero
                zotero_note_html = zotero_client._build_note_html(
                    takeaway=log_sentence, summary=note_summary,
                    highlights=highlights,
                )
                zotero_client.set_note(item_key, zotero_note_html)

                # Append to reading log
                obsidian.append_to_reading_log(doc["title"], "Read", log_sentence)

                # Move to Vault on reMarkable
                remarkable_client.move_document(
                    rm_name, config.RM_FOLDER_READ, config.RM_FOLDER_VAULT,
                )

                # Update state
                state.mark_processed(
                    item_key, summary=log_sentence, note_summary=note_summary,
                )
                state.save()
                synced_count += 1
                log.info("Processed: %s", rm_name)

            except Exception:
                log.exception("Failed to process read paper '%s', skipping", rm_name)
                continue

        # -- Step 2b: Poll reMarkable for leafed papers --
        log.info("Step 2b: Checking reMarkable for leafed papers...")

        leafed_docs = remarkable_client.list_folder(config.RM_FOLDER_LEAFED)

        for doc in on_remarkable:
            rm_name = doc["remarkable_doc_name"]

            if rm_name not in leafed_docs:
                continue

            log.info("Found leafed paper: %s", rm_name)
            item_key = doc["zotero_item_key"]

            try:
                # Move original PDF from Inbox to Leafed folder
                moved = obsidian.move_inbox_pdf_to_leafed(doc["title"])
                pdf_filename = moved.name if moved else None

                # Update linked attachment to point to moved PDF
                linked = zotero_client.get_linked_attachment(item_key)
                if moved:
                    new_att = zotero_client.create_linked_attachment(
                        item_key, moved.name, str(moved),
                    )
                    if new_att and linked:
                        zotero_client.delete_attachment(linked["key"])
                elif linked:
                    zotero_client.delete_attachment(linked["key"])

                # Update Zotero tag
                zotero_client.replace_tag(
                    item_key, config.ZOTERO_TAG_INBOX, config.ZOTERO_TAG_LEAFED,
                )

                # Create minimal Obsidian note
                meta = doc.get("metadata", {})
                obsidian.ensure_dataview_note()
                obsidian.create_leafed_note(
                    title=doc["title"],
                    authors=doc["authors"],
                    date_added=doc["uploaded_at"],
                    zotero_item_key=item_key,
                    pdf_filename=pdf_filename,
                    doi=meta.get("doi", ""),
                    url=meta.get("url", ""),
                    publication_date=meta.get("publication_date", ""),
                    journal=meta.get("journal", ""),
                    topic_tags=meta.get("tags"),
                )

                # Add Obsidian deep link in Zotero
                obsidian_uri = obsidian.get_obsidian_uri(doc["title"], subfolder="Leafed")
                if obsidian_uri:
                    zotero_client.create_obsidian_link(item_key, obsidian_uri)

                # Generate leafed summary
                leafed_summary = summarizer.summarize_leafed_paper(
                    doc["title"], abstract=meta.get("abstract", ""),
                )

                # Append to reading log
                obsidian.append_to_reading_log(
                    doc["title"], "Leafed", leafed_summary,
                )

                # Sync note to Zotero
                zotero_note_html = zotero_client._build_note_html(takeaway=leafed_summary)
                zotero_client.set_note(item_key, zotero_note_html)

                # Move to Vault on reMarkable
                remarkable_client.move_document(
                    rm_name, config.RM_FOLDER_LEAFED, config.RM_FOLDER_VAULT,
                )

                # Update state
                state.mark_processed(item_key, summary=leafed_summary, reading_status="leafed")
                state.save()
                synced_count += 1
                log.info("Processed (leafed): %s", rm_name)

            except Exception:
                log.exception("Failed to process leafed paper '%s', skipping", rm_name)
                continue

        state.touch_poll_timestamp()
        state.save()

        # -- Step 3: Notify --
        if sent_count or synced_count:
            log.info("Done: %d sent, %d synced", sent_count, synced_count)
            notify.notify_summary(sent_count, synced_count)
        else:
            log.info("Nothing to do.")

    except Exception:
        log.exception("Unexpected error")
        raise
    finally:
        release_lock()


if __name__ == "__main__":
    main()
