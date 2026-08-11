from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.billing import payments_service, rollup_service
from tallyquo.billing.clients_schemas import (
    AgingReportRowOut,
    AgingSummaryOut,
    PaymentSpeedOut,
    RevenueByClientRowOut,
)
from tallyquo.core.auth import get_db

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/aging", response_model=list[AgingReportRowOut])
async def aging_report(db: AsyncSession = Depends(get_db)) -> list[AgingReportRowOut]:
    rows = await rollup_service.tenant_aging_report(db)
    return [AgingReportRowOut(**row) for row in rows]


@router.get("/aging/summary", response_model=AgingSummaryOut)
async def aging_summary(db: AsyncSession = Depends(get_db)) -> AgingSummaryOut:
    # Carbon redesign Dashboard's AR aging chart (dashboard_design.md
    # §10) -- one tenant-wide summed row including a not-due bucket,
    # unlike the per-client, overdue-only report above.
    row = await rollup_service.tenant_aging_summary(db)
    return AgingSummaryOut(**row)


@router.get("/revenue-by-client", response_model=list[RevenueByClientRowOut])
async def revenue_by_client(db: AsyncSession = Depends(get_db)) -> list[RevenueByClientRowOut]:
    rows = await rollup_service.tenant_revenue_by_client(db)
    return [RevenueByClientRowOut(**row) for row in rows]


@router.get("/payment-speed", response_model=PaymentSpeedOut)
async def payment_speed(db: AsyncSession = Depends(get_db)) -> PaymentSpeedOut:
    row = await payments_service.average_days_to_payment(db)
    return PaymentSpeedOut(**row)
