"""reMarkable Cloud client wrapping the ddvk/rmapi CLI.

All interactions with the reMarkable Cloud go through the `rmapi` binary,
which handles the sync15 protocol and authentication.
"""

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from papers_workflow import config

log = logging.getLogger(__name__)


def _run(args: List[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run an rmapi command and return the result."""
    rmapi = shutil.which("rmapi")
    if not rmapi:
        raise RuntimeError(
            "rmapi not found. Install it: "
            "https://github.com/ddvk/rmapi/releases"
        )
    cmd = [rmapi] + args
    log.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=120,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"rmapi {' '.join(args)} failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return result


def ensure_folders() -> None:
    """Create the workflow folders on reMarkable if they don't exist."""
    existing = {
        line.split("\t", 1)[-1].strip()
        for line in _run(["ls", "/"]).stdout.splitlines()
        if line.startswith("[d]")
    }
    for folder in (
        config.RM_FOLDER_TO_READ,
        config.RM_FOLDER_READ,
        config.RM_FOLDER_ARCHIVE,
    ):
        if folder not in existing:
            _run(["mkdir", f"/{folder}"])
            log.info("Created reMarkable folder: /%s", folder)


def list_folder(folder: str) -> List[str]:
    """List document names in a reMarkable folder."""
    result = _run(["ls", f"/{folder}"])
    names = []
    for line in result.stdout.splitlines():
        if line.startswith("[f]"):
            name = line.split("\t", 1)[-1].strip()
            names.append(name)
    return names


def upload_pdf(pdf_path: Path, folder: str, title: str) -> None:
    """Upload a PDF to a reMarkable folder with a given title.

    The file is copied to a temp file named after the title so that
    rmapi uses the title as the document name on the device.
    """
    sanitized = _sanitize_filename(title)
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / f"{sanitized}.pdf"
        shutil.copy2(pdf_path, dest)
        _run(["put", str(dest), f"/{folder}/"])
    log.info("Uploaded '%s' to /%s/", title, folder)


def upload_pdf_bytes(pdf_bytes: bytes, folder: str, title: str) -> None:
    """Upload PDF bytes to a reMarkable folder with a given title.

    If a document with the same name already exists, skips the upload.
    """
    sanitized = _sanitize_filename(title)
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / f"{sanitized}.pdf"
        dest.write_bytes(pdf_bytes)
        result = _run(["put", str(dest), f"/{folder}/"], check=False)
        if result.returncode != 0:
            if "entry already exists" in result.stderr:
                log.info("Already on reMarkable, skipping: '%s'", title)
                return
            raise RuntimeError(
                f"rmapi put failed (exit {result.returncode}): "
                f"{result.stderr.strip()}"
            )
    log.info("Uploaded '%s' to /%s/", title, folder)


def download_document_bundle_to(folder: str, doc_name: str, output_path: Path) -> bool:
    """Download a raw document bundle (zip) using rmapi get.

    Returns True on success, False on failure.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        rmapi = shutil.which("rmapi")
        if not rmapi:
            raise RuntimeError("rmapi not found")

        result = subprocess.run(
            [rmapi, "get", f"/{folder}/{doc_name}"],
            capture_output=True, text=True, timeout=120,
            cwd=tmpdir,
        )
        if result.returncode != 0:
            log.warning(
                "Failed to download bundle for '%s': %s",
                doc_name, result.stderr.strip(),
            )
            return False

        # rmapi get produces a .zip or .rmdoc file in the working directory
        zips = list(Path(tmpdir).glob("*.zip")) + list(Path(tmpdir).glob("*.rmdoc"))
        if not zips:
            log.warning("rmapi get produced no bundle for '%s'", doc_name)
            return False

        shutil.move(str(zips[0]), str(output_path))
        log.info("Downloaded document bundle: %s", output_path)
        return True


def download_annotated_pdf(folder: str, doc_name: str, output_dir: Path) -> Optional[Path]:
    """Download a document as an annotated PDF using rmapi geta.

    Returns the path to the downloaded PDF, or None on failure.
    """
    result = _run(
        ["geta", f"/{folder}/{doc_name}"],
        check=False,
    )
    if result.returncode != 0:
        log.warning(
            "Failed to download annotated PDF for '%s': %s",
            doc_name, result.stderr.strip(),
        )
        return None

    # geta writes a .pdf file in the current directory with the doc name
    # We need to find it and move it to output_dir
    # rmapi geta outputs to current working directory, so we run from output_dir
    # Actually, let's look for the file
    sanitized = _sanitize_filename(doc_name)
    for pattern in [f"{sanitized}.pdf", f"{doc_name}.pdf"]:
        candidate = Path.cwd() / pattern
        if candidate.exists():
            dest = output_dir / pattern
            shutil.move(str(candidate), str(dest))
            log.info("Downloaded annotated PDF: %s", dest)
            return dest

    # geta may output to a zip file or use a different name
    log.warning("Could not find downloaded PDF for '%s'", doc_name)
    return None


def download_annotated_pdf_to(folder: str, doc_name: str, output_path: Path) -> bool:
    """Download a document as annotated PDF to a specific path.

    Returns True on success, False on failure.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run geta from the temp directory so the output lands there
        rmapi = shutil.which("rmapi")
        if not rmapi:
            raise RuntimeError("rmapi not found")

        result = subprocess.run(
            [rmapi, "geta", f"/{folder}/{doc_name}"],
            capture_output=True, text=True, timeout=120,
            cwd=tmpdir,
        )
        if result.returncode != 0:
            log.warning(
                "Failed to download annotated PDF for '%s': %s",
                doc_name, result.stderr.strip(),
            )
            return False

        # Find the generated PDF in tmpdir
        pdfs = list(Path(tmpdir).glob("*.pdf"))
        if not pdfs:
            log.warning("rmapi geta produced no PDF for '%s'", doc_name)
            return False

        shutil.move(str(pdfs[0]), str(output_path))
        log.info("Downloaded annotated PDF: %s", output_path)
        return True


def move_document(doc_name: str, from_folder: str, to_folder: str) -> None:
    """Move a document between reMarkable folders."""
    _run(["mv", f"/{from_folder}/{doc_name}", f"/{to_folder}/"])
    log.info("Moved '%s' from /%s/ to /%s/", doc_name, from_folder, to_folder)


def _sanitize_filename(name: str) -> str:
    """Remove characters that are problematic in filenames."""
    bad_chars = '<>:"/\\|?*'
    result = name
    for c in bad_chars:
        result = result.replace(c, "")
    # Collapse whitespace
    result = " ".join(result.split())
    # Trim to reasonable length
    return result[:200].strip()
