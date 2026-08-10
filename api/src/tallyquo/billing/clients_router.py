import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.billing import clients_service as service
from tallyquo.billing import rollup_service
from tallyquo.billing.clients_schemas import (
    ClientEvidenceIn,
    ClientEvidenceOut,
    ClientIn,
    ClientOut,
    ClientRollupOut,
    ClientSummaryOut,
    ClientSummaryPageOut,
)
from tallyquo.core.auth import CurrentUser, get_current_user, get_db

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[ClientOut])
async def list_clients(db: AsyncSession = Depends(get_db)) -> list[ClientOut]:
    rows = await service.list_clients(db)
    return [ClientOut(**row) for row in rows]


@router.get("/export.csv")
async def export_clients_csv(db: AsyncSession = Depends(get_db)) -> Response:
    rows = await service.list_clients(db)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["legal_name", "display_name", "email", "country_code", "region_code", "tax_treatment", "default_currency"]
    )
    for row in rows:
        writer.writerow(
            [
                row["legal_name"],
                row["display_name"] or "",
                row["email"] or "",
                row["country_code"],
                row["region_code"] or "",
                row["tax_treatment"],
                row["default_currency"],
            ]
        )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=clients.csv"},
    )


@router.get("/summary", response_model=ClientSummaryPageOut)
async def list_clients_summary(
    limit: int = 20, offset: int = 0, db: AsyncSession = Depends(get_db)
) -> ClientSummaryPageOut:
    items, total = await service.list_clients_summary(db, limit=limit, offset=offset)
    return ClientSummaryPageOut(items=[ClientSummaryOut(**row) for row in items], total=total)


@router.post("", response_model=ClientOut, status_code=201)
async def create_client(
    body: ClientIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClientOut:
    row = await service.create_client(db, current_user.tenant_id, body.model_dump())
    return ClientOut(**row)


@router.get("/{client_id}", response_model=ClientOut)
async def get_client(client_id: UUID, db: AsyncSession = Depends(get_db)) -> ClientOut:
    row = await service.get_client(db, client_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return ClientOut(**row)


@router.patch("/{client_id}", response_model=ClientOut)
async def update_client(
    client_id: UUID, body: ClientIn, db: AsyncSession = Depends(get_db)
) -> ClientOut:
    row = await service.update_client(db, client_id, body.model_dump())
    if row is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return ClientOut(**row)


@router.delete("/{client_id}", status_code=204)
async def archive_client(client_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    found = await service.archive_client(db, client_id)
    if not found:
        raise HTTPException(status_code=404, detail="Client not found")


@router.get("/{client_id}/rollup", response_model=ClientRollupOut)
async def get_client_rollup(client_id: UUID, db: AsyncSession = Depends(get_db)) -> ClientRollupOut:
    if await service.get_client(db, client_id) is None:
        raise HTTPException(status_code=404, detail="Client not found")
    periods = await rollup_service.client_period_rollup(db, client_id)
    aging = await rollup_service.client_aging(db, client_id)
    return ClientRollupOut(periods=periods, aging=aging)


@router.get("/{client_id}/evidence", response_model=list[ClientEvidenceOut])
async def list_evidence(client_id: UUID, db: AsyncSession = Depends(get_db)) -> list[ClientEvidenceOut]:
    rows = await service.list_evidence(db, client_id)
    return [ClientEvidenceOut(**row) for row in rows]


@router.post("/{client_id}/evidence", response_model=ClientEvidenceOut, status_code=201)
async def add_evidence(
    client_id: UUID,
    body: ClientEvidenceIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClientEvidenceOut:
    if await service.get_client(db, client_id) is None:
        raise HTTPException(status_code=404, detail="Client not found")
    data = body.model_dump()
    data["file_hash"] = data["file_hash"].encode()
    row = await service.add_evidence(db, current_user.tenant_id, client_id, data)
    return ClientEvidenceOut(**row)
