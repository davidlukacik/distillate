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


def main():
    if "--register" in sys.argv:
        from papers_workflow.remarkable_auth import register_interactive
        register_interactive()
        return

    from papers_workflow import config
    from papers_workflow import zotero_client
    from papers_workflow import remarkable_client
    from papers_workflow import obsidian
    from papers_workflow import notify
    from papers_workflow import renderer
    from papers_workflow.state import State, acquire_lock, release_lock

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

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
                        pdf_bytes, config.RM_FOLDER_TO_READ, title
                    )
                    zotero_client.add_tag(item_key, config.ZOTERO_TAG_TO_READ)
                    state.set_status(item_key, "on_remarkable")
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
                            remarkable_client.list_folder(config.RM_FOLDER_TO_READ)
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
                                            remarkable_doc_name=title,
                                            title=title,
                                            authors=authors,
                                            status="awaiting_pdf",
                                        )
                                        continue
                                    raise
                                log.info("Downloaded PDF (%d bytes)", len(pdf_bytes))
                                remarkable_client.upload_pdf_bytes(
                                    pdf_bytes, config.RM_FOLDER_TO_READ, title
                                )

                            # Tag in Zotero
                            zotero_client.add_tag(item_key, config.ZOTERO_TAG_TO_READ)

                            # Track in state
                            state.add_document(
                                zotero_item_key=item_key,
                                zotero_attachment_key=att_key,
                                zotero_attachment_md5=att_md5,
                                remarkable_doc_name=title,
                                title=title,
                                authors=authors,
                            )
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
            att_key = doc["zotero_attachment_key"]
            att_md5 = doc["zotero_attachment_md5"]

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
                    # Delete original PDF from Zotero to free storage
                    zotero_client.delete_attachment(att_key)
                else:
                    log.warning(
                        "Could not get annotated PDF for '%s', "
                        "Zotero PDF left unchanged", rm_name,
                    )

            # Update Zotero tag
            zotero_client.replace_tag(
                item_key, config.ZOTERO_TAG_TO_READ, config.ZOTERO_TAG_READ,
            )

            # Create Obsidian note with extracted highlights
            obsidian.ensure_reading_logs()
            obsidian.create_paper_note(
                title=doc["title"],
                authors=doc["authors"],
                date_added=doc["uploaded_at"],
                zotero_item_key=item_key,
                highlights=highlights or None,
                pdf_filename=pdf_filename,
            )
            obsidian.append_to_reading_log(doc["title"], doc["authors"])

            # Move to Archive on reMarkable
            remarkable_client.move_document(
                rm_name, config.RM_FOLDER_READ, config.RM_FOLDER_ARCHIVE,
            )

            # Update state
            state.mark_processed(item_key)
            synced_count += 1
            log.info("Processed: %s", rm_name)

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
