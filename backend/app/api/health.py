from collections.abc import Callable

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import get_app_settings
from app.core.config import Settings
from app.db.session import get_db_pinger
from app.schemas.facility import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut, responses={503: {"model": HealthOut}})
def health(
    pinger: Callable[[], bool] = Depends(get_db_pinger),
    settings: Settings = Depends(get_app_settings),
):
    db_ok = pinger()
    body = HealthOut(
        status="ok" if db_ok else "degraded",
        database="ok" if db_ok else "unreachable",
        environment=settings.app_env,
    )
    return JSONResponse(status_code=200 if db_ok else 503, content=body.model_dump())
