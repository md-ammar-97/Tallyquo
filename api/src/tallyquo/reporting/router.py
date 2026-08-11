import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.core.auth import get_db
from tallyquo.reporting import service
from tallyquo.reporting.schemas import PnlRowOut

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/pnl", response_model=list[PnlRowOut])
async def get_pnl(group_by: str = "month", db: AsyncSession = Depends(get_db)) -> list[PnlRowOut]:
    # Carbon redesign Dashboard's 12-month Revenue/Expenses/Net-Income
    # chart and Monthly Expense Trend (dashboard_design.md §4, §16) --
    # a thin JSON wrapper around the same pnl_rows() the CSV export
    # below already uses, zero new aggregation logic.
    try:
        rows = await service.pnl_rows(db, group_by=group_by)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return [PnlRowOut(**row) for row in rows]


@router.get("/pnl.csv")
async def export_pnl_csv(group_by: str = "month", db: AsyncSession = Depends(get_db)) -> Response:
    try:
        rows = await service.pnl_rows(db, group_by=group_by)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["period", "income_cad", "expenses_cad", "net_income_cad"])
    for row in rows:
        writer.writerow([row["period"], row["income"], row["expenses"], row["net_income"]])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pnl.csv"},
    )
