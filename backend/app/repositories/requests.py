"""Database access for booking requests and their lines."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BookingRequest, RequestLine


class RequestRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_user(self, user_id: int) -> list[BookingRequest]:
        stmt = (
            select(BookingRequest)
            .where(BookingRequest.user_id == user_id)
            .order_by(BookingRequest.created_at.desc(), BookingRequest.id.desc())
        )
        return list(self.session.scalars(stmt))

    def get_for_user(self, request_id: int, user_id: int) -> BookingRequest | None:
        """Returns None for another user's request, so callers answer 404 and reveal nothing."""
        stmt = select(BookingRequest).where(BookingRequest.id == request_id, BookingRequest.user_id == user_id)
        return self.session.scalars(stmt).first()

    def add(self, request: BookingRequest) -> None:
        self.session.add(request)

    def delete(self, request: BookingRequest) -> None:
        self.session.delete(request)

    def get_line(self, request: BookingRequest, line_id: int) -> RequestLine | None:
        return next((line for line in request.lines if line.id == line_id), None)
