from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.billing import recurring_service as service
from tallyquo.billing.recurring_schemas import RecurringRuleIn, RecurringRuleOut, RecurringRulePatch
from tallyquo.core.auth import CurrentUser, get_current_user, get_db

router = APIRouter(prefix="/recurring", tags=["recurring"])


@router.get("", response_model=list[RecurringRuleOut])
async def list_rules(db: AsyncSession = Depends(get_db)) -> list[RecurringRuleOut]:
    rows = await service.list_rules(db)
    return [RecurringRuleOut(**row) for row in rows]


@router.post("", response_model=RecurringRuleOut, status_code=201)
async def create_rule(
    body: RecurringRuleIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecurringRuleOut:
    row = await service.create_rule(db, current_user.tenant_id, body.model_dump())
    return RecurringRuleOut(**row)


@router.get("/{rule_id}", response_model=RecurringRuleOut)
async def get_rule(rule_id: UUID, db: AsyncSession = Depends(get_db)) -> RecurringRuleOut:
    row = await service.get_rule(db, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Recurring rule not found")
    return RecurringRuleOut(**row)


@router.patch("/{rule_id}", response_model=RecurringRuleOut)
async def update_rule(rule_id: UUID, body: RecurringRulePatch, db: AsyncSession = Depends(get_db)) -> RecurringRuleOut:
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    row = await service.update_rule(db, rule_id, data)
    if row is None:
        raise HTTPException(status_code=404, detail="Recurring rule not found")
    return RecurringRuleOut(**row)


@router.post("/{rule_id}/pause", response_model=RecurringRuleOut)
async def pause_rule(rule_id: UUID, db: AsyncSession = Depends(get_db)) -> RecurringRuleOut:
    row = await service.update_rule(db, rule_id, {"is_paused": True})
    if row is None:
        raise HTTPException(status_code=404, detail="Recurring rule not found")
    return RecurringRuleOut(**row)


@router.post("/{rule_id}/resume", response_model=RecurringRuleOut)
async def resume_rule(rule_id: UUID, db: AsyncSession = Depends(get_db)) -> RecurringRuleOut:
    row = await service.resume_rule(db, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Recurring rule not found")
    return RecurringRuleOut(**row)


@router.post("/{rule_id}/skip", response_model=RecurringRuleOut)
async def skip_next(
    rule_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecurringRuleOut:
    row = await service.skip_next(db, current_user.tenant_id, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Recurring rule not found")
    return RecurringRuleOut(**row)
