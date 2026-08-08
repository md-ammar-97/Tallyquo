from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.core.auth import CurrentUser, get_current_user, get_db
from tallyquo.exports import year_end_service
from tallyquo.exports.schemas import YearEndPackOut

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("/year-end", response_model=YearEndPackOut)
async def create_year_end_pack(
    year: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> YearEndPackOut:
    try:
        result = await year_end_service.create_year_end_pack_url(db, current_user.tenant_id, year)
    except year_end_service.NoBusinessProfile as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except year_end_service.PackStorageUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    return YearEndPackOut(**result)
