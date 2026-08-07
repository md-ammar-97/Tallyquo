from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.billing import clients_service as service
from tallyquo.billing.clients_schemas import ClientEvidenceIn, ClientEvidenceOut, ClientIn, ClientOut
from tallyquo.core.auth import CurrentUser, get_current_user, get_db

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[ClientOut])
async def list_clients(db: AsyncSession = Depends(get_db)) -> list[ClientOut]:
    rows = await service.list_clients(db)
    return [ClientOut(**row) for row in rows]


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
