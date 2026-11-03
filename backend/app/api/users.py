from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_current_session
from app.core.config import Settings
from app.db.models import User, UserSession
from app.db.session import get_db
from app.schemas.user import MeOut, RateCategoryIn
from app.services import auth_service, roles_service

router = APIRouter(prefix="/users", tags=["users"])


def me_out(user: User, session: UserSession, settings: Settings, roles: list[str] | None = None) -> MeOut:
    is_iit = auth_service.is_iit_email(user.email, settings.iit_email_domain)
    return MeOut(
        id=user.id,
        email=user.email,
        name=user.name,
        rate_category=user.rate_category,
        is_iit=is_iit,
        needs_category=user.rate_category is None,
        csrf_token=session.csrf_token,
        roles=roles or [],
    )


@router.get("/me", response_model=MeOut)
def get_me(
    session: UserSession = Depends(get_current_session),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> MeOut:
    return me_out(session.user, session, settings, roles_service.active_roles(db, session.user.email))


@router.put("/me/rate-category", response_model=MeOut)
def set_rate_category(
    body: RateCategoryIn,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> MeOut:
    user = auth_service.set_external_category(db, session.user, body.rate_category, settings.iit_email_domain)
    return me_out(user, session, settings, roles_service.active_roles(db, user.email))
