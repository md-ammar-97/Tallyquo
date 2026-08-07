from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.core.auth import get_db
from tallyquo.tax.context_builder import build_supply_context
from tallyquo.tax.engine import MissingJurisdiction, NoRateForDate, compute
from tallyquo.tax.loader import load_rate_table
from tallyquo.tax.schemas import PreviewTaxIn, PreviewTaxOut, TaxLineOut

router = APIRouter(prefix="/invoices", tags=["tax"])


@router.post("/preview-tax", response_model=PreviewTaxOut)
async def preview_tax(body: PreviewTaxIn, db: AsyncSession = Depends(get_db)) -> PreviewTaxOut:
    profile_row = (
        await db.execute(
            text(
                "SELECT registration_status, registration_effective_date "
                "FROM business_profile WHERE tenant_id = current_setting('app.tenant_id')::uuid"
            )
        )
    ).mappings().first()
    if profile_row is None:
        raise HTTPException(
            status_code=422, detail="Add your business profile before previewing tax."
        )

    client_row = (
        await db.execute(
            text(
                "SELECT country_code, region_code, is_gst_registered, tax_treatment, "
                "treatment_override_reason FROM client WHERE id = :id"
            ),
            {"id": body.client_id},
        )
    ).mappings().first()
    if client_row is None:
        raise HTTPException(status_code=404, detail="Client not found")

    evidence_count = (
        await db.execute(
            text(
                "SELECT count(*) FROM client_evidence WHERE client_id = :id "
                "AND kind = 'non_residency_attestation'"
            ),
            {"id": body.client_id},
        )
    ).scalar_one()

    ctx = build_supply_context(
        business_profile=dict(profile_row),
        client=dict(client_row),
        line_amounts=[(li.amount, li.is_taxable) for li in body.line_items],
        invoice_date=body.invoice_date,
        has_non_residency_evidence=evidence_count > 0,
        include_provincial_sales_tax=body.include_provincial_sales_tax,
    )
    rate_table = await load_rate_table(db)

    try:
        result = compute(ctx, rate_table)
    except (NoRateForDate, MissingJurisdiction) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    subtotal = sum((li.amount for li in body.line_items), start=Decimal("0.00"))
    return PreviewTaxOut(
        treatment=result.treatment.value,
        jurisdiction=result.jurisdiction,
        lines=[TaxLineOut(**vars(line)) for line in result.lines],
        subtotal=subtotal,
        tax_total=result.tax_total,
        total=subtotal + result.tax_total,
        warnings=list(result.warnings),
        table_version=result.table_version,
    )
