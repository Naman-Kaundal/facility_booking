"""Where uploaded proof documents are kept (final release).

Files are saved on the server's disk under random names in a private folder (``UPLOAD_DIR``),
never under the name the user gave them, and are never served as static files: the API
streams a file only to the requester and to Facilities staff. Details about each file
(request, original name, type, size, SHA-256) live in PostgreSQL (``request_documents``).

The file type is decided by the file's first bytes, not by its name or by what the browser
claims, so a renamed program can't be uploaded as a "PDF".
"""

import os
import re
import uuid
from pathlib import Path

# content type -> (magic bytes at the start of the file, extension we store it with)
ALLOWED_TYPES: dict[str, tuple[bytes, str]] = {
    "application/pdf": (b"%PDF-", ".pdf"),
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
}
STORED_NAME = re.compile(r"^[0-9a-f]{32}\.(pdf|png|jpg)$")


def detect_type(data: bytes) -> tuple[str, str] | None:
    """(content type, extension) from the file's first bytes, or None if it isn't allowed."""
    for content_type, (magic, ext) in ALLOWED_TYPES.items():
        if data.startswith(magic):
            return content_type, ext
    return None


def clean_filename(name: str | None) -> str:
    """The user's file name, as shown to Facilities: no folders, no control characters, at most 200 chars."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = "".join(ch for ch in base if ch.isprintable()).strip()
    return base[:200] or "document"


class LocalDocumentStorage:
    """Saves files in one folder on this computer. Can be swapped for other storage later."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def save(self, data: bytes, ext: str) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}{ext}"
        final = self.root / stored_name
        temp = self.root / f".{stored_name}.part"
        temp.write_bytes(data)
        os.replace(temp, final)  # the file appears complete or not at all
        return stored_name

    def path(self, stored_name: str) -> Path:
        if not STORED_NAME.match(stored_name):  # never follow a name we didn't create
            raise ValueError("Invalid stored document name.")
        return self.root / stored_name

    def delete(self, stored_name: str) -> None:
        try:
            self.path(stored_name).unlink(missing_ok=True)
        except (OSError, ValueError):
            pass
