from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.billing import rollup_service
from tallyquo.billing.clients_schemas import AgingReportRowOut
from tallyquo.core.auth import get_db

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/aging", response_model=list[AgingReportRowOut])
async def aging_report(db: AsyncSession = Depends(get_db)) -> list[AgingReportRowOut]:
    rows = await rollup_service.tenant_aging_report(db)
    return [AgingReportRowOut(**row) for row in rows]
