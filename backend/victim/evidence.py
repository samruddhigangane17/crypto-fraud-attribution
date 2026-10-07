"""Evidence vault helpers: type/size checks, malware screening and blob storage."""

import os
import re
from pathlib import Path
from typing import Optional

MAX_BYTES = 10 * 1024 * 1024
MAX_FILES_PER_COMPLAINT = 25

_ALLOWED = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".json": "application/json",
}

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


class EvidenceRejected(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def sanitize_filename(name: str) -> str:
    base = os.path.basename((name or "").replace("\\", "/"))
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", base).strip(" .")
    return (base or "file")[:120]


def sniff_mime(filename: str, data: bytes) -> str:
    """Return the mime type, checking the file's real content matches its extension."""
    ext = os.path.splitext(filename.lower())[1]
    mime = _ALLOWED.get(ext)
    if mime is None:
        raise EvidenceRejected("TYPE_NOT_ALLOWED",
                               "This file type is not allowed. Use PNG, JPG, WEBP, PDF, TXT, CSV or JSON.")
    if not data:
        raise EvidenceRejected("EMPTY_FILE", "The file is empty.")
    head = data[:12]
    ok = {
        "image/png": head.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": head.startswith(b"\xff\xd8\xff"),
        "image/webp": head[:4] == b"RIFF" and data[8:12] == b"WEBP",
        "application/pdf": head.startswith(b"%PDF-"),
    }.get(mime)
    if ok is False:
        raise EvidenceRejected("CONTENT_MISMATCH", "The file content does not match its type.")
    if ok is None:  # text-like: must be UTF-8 without NUL bytes
        if b"\x00" in data:
            raise EvidenceRejected("CONTENT_MISMATCH", "The file content does not match its type.")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            raise EvidenceRejected("CONTENT_MISMATCH", "Text files must be UTF-8.")
    return mime


class BasicScanner:
    """Heuristic screening. NOT a replacement for an antivirus engine.

    For production, put ClamAV (or a cloud scanning service) behind the same `scan` interface.
    """

    def scan(self, data: bytes, mime: str) -> Optional[str]:
        """Return a reason string if the file is unsafe, else None."""
        if EICAR in data:
            return "malware test signature"
        if data[:2] == b"MZ" or data[:4] == b"\x7fELF" or data[:2] == b"#!":
            return "executable content"
        lower = data[:2_000_000].lower()
        if mime == "application/pdf" and any(
            tag in lower for tag in (b"/javascript", b"/js ", b"/launch", b"/embeddedfile", b"/openaction")
        ):
            return "active content in PDF"
        if mime in ("text/plain", "text/csv", "application/json") and b"<script" in lower:
            return "script content"
        return None


class BlobStore:
    """Stores evidence bytes on local disk (EVIDENCE_DIR). Swap for Supabase Storage in production."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base = Path(base_dir or os.getenv("EVIDENCE_DIR", "evidence_store"))

    def path_for(self, complaint_id: str, file_id: str, version: int) -> Path:
        return self.base / complaint_id / file_id / f"v{version}.bin"

    def write(self, complaint_id: str, file_id: str, version: int, data: bytes) -> str:
        p = self.path_for(complaint_id, file_id, version)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():  # append-only: never overwrite a stored version
            raise FileExistsError(str(p))
        p.write_bytes(data)
        return str(p)

    def read(self, blob_path: str) -> bytes:
        return Path(blob_path).read_bytes()


global_scanner = BasicScanner()
global_blob_store = BlobStore()
