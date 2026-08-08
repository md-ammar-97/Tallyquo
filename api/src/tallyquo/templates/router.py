import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.core.auth import CurrentUser, get_current_user, get_db
from tallyquo.templates import service
from tallyquo.templates.schemas import SetDefaultTemplateIn, TemplateOut, TemplatePackage

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TemplateOut])
async def list_templates(
    current_user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[TemplateOut]:
    rows = await service.list_templates(db)
    return [TemplateOut(**row) for row in rows]


@router.get("/{template_id}/export")
async def export_template(
    template_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    template = await service.get_template(db, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found.")
    package = service.export_template(template)
    return Response(
        content=json.dumps(package, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{template["name"]}.tallyquo-template.json"'},
    )


@router.post("/import", response_model=TemplateOut, status_code=201)
async def import_template(
    body: TemplatePackage,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TemplateOut:
    try:
        row = await service.import_template(db, current_user.tenant_id, body.model_dump())
    except service.InvalidTemplatePackage as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return TemplateOut(**row)


@router.put("/default", status_code=204)
async def set_default_template(
    body: SetDefaultTemplateIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await service.set_default_template(db, current_user.tenant_id, body.template_id)
    except service.TemplateNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
