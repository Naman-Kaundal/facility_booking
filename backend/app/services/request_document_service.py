"""Govt./PSU proof documents attached to booking requests (final release).

Rules:
- only the requester uploads, and only while the request can be edited (a draft, or returned
  by Facilities for correction); uploading again replaces the document;
- only accounts on the Govt./PSU rate upload one, and they can't submit without it;
- the requester and Facilities staff can open it; nobody else (other desks get a 404).
"""

import hashlib

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.time import utc_now
from app.db.models import BookingRequest, RequestDocument, User
from app.schemas.request import RequestOut
from app.services.document_storage import LocalDocumentStorage, clean_filename, detect_type
from app.services.request_service import EDITABLE_STATUSES, RequestService


class RequestDocumentService:
    def __init__(self, db: Session, storage: LocalDocumentStorage, *, max_bytes: int) -> None:
        self.db = db
        self.storage = storage
        self.max_bytes = max_bytes
        self.requests = RequestService(db)

    def upload(self, user: User, request_id: int, filename: str | None, data: bytes) -> RequestOut:
        request = self.requests.get(user, request_id)  # 404 unless it's the user's own request
        if request.status not in EDITABLE_STATUSES:
            raise AppError(
                "REQUEST_NOT_EDITABLE", f"This request is {request.status} and can no longer be changed.", 409
            )
        if user.rate_category != "GOVT":
            raise AppError(
                "DOCUMENT_NOT_NEEDED", "Only requests at the Govt./PSU rate need a proof document.", 409
            )
        content_type, ext = self._check(data)

        stored_name = self.storage.save(data, ext)
        details = {
            "original_filename": clean_filename(filename),
            "stored_name": stored_name,
            "content_type": content_type,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "uploaded_by": user.id,
        }
        replaced = request.document.stored_name if request.document is not None else None
        try:
            if request.document is None:
                request.document = RequestDocument(**details)
            else:
                for field, value in details.items():
                    setattr(request.document, field, value)
                request.document.uploaded_at = utc_now()
            self.db.commit()
        except Exception:
            self.db.rollback()
            self.storage.delete(stored_name)  # never leave an orphan file behind
            raise
        if replaced:
            self.storage.delete(replaced)
        self.db.expire_all()
        return self.requests.detail(user, request_id)

    def for_requester(self, user: User, request_id: int) -> tuple:
        return self._file(self.requests.get(user, request_id))

    def for_staff(self, request_id: int) -> tuple:
        request = self.db.get(BookingRequest, request_id)
        if request is None or request.status == "DRAFT":  # staff never see drafts
            raise AppError("REQUEST_NOT_FOUND", "Request not found.", 404)
        return self._file(request)

    # ----- helpers -----

    def _check(self, data: bytes) -> tuple[str, str]:
        if not data:
            raise AppError("EMPTY_FILE", "The file is empty.", 422, {"field": "file"})
        if len(data) > self.max_bytes:
            limit_mb = self.max_bytes // (1024 * 1024)
            raise AppError("FILE_TOO_LARGE", f"The file is larger than {limit_mb} MB.", 422, {"field": "file"})
        kind = detect_type(data)
        if kind is None:
            raise AppError("UNSUPPORTED_FILE", "Upload a PDF, JPG or PNG file.", 422, {"field": "file"})
        return kind

    def _file(self, request: BookingRequest) -> tuple:
        """(path, content type, original file name) of the request's document."""
        doc = request.document
        if doc is None:
            raise AppError("DOCUMENT_NOT_FOUND", "This request has no proof document.", 404)
        path = self.storage.path(doc.stored_name)
        if not path.is_file():
            raise AppError(
                "DOCUMENT_NOT_FOUND", "The document file is missing. Ask the requester to upload it again.", 404
            )
        return path, doc.content_type, doc.original_filename

