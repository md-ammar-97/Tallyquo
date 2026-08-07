"""Public, unauthenticated invoice routes. No `get_current_user`/`get_db`
here -- every route resolves a share token to a tenant_id first
(share_service.resolve_share_token, no tenant context needed for that),
then opens its own `tenant_session()` explicitly, the same shape the
auth bootstrap flow uses before a JWT exists.
"""

from fastapi import APIRouter, HTTPException, Response

from tallyquo.billing import invoices_service, share_service
from tallyquo.billing.invoices_schemas import InvoiceOut
from tallyquo.core.tenant_context import tenant_session

router = APIRouter(prefix="/public/invoices", tags=["public"])


@router.get("/{token}", response_model=InvoiceOut)
async def get_shared_invoice(token: str) -> InvoiceOut:
    resolved = await share_service.resolve_share_token(token)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    tenant_id, invoice_id = resolved
    async with tenant_session(tenant_id) as session:
        row = await invoices_service.get_invoice(session, invoice_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return InvoiceOut(**row)


@router.get("/{token}/pdf")
async def get_shared_invoice_pdf(token: str) -> Response:
    resolved = await share_service.resolve_share_token(token)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    tenant_id, invoice_id = resolved
    async with tenant_session(tenant_id) as session:
        pdf_bytes = await invoices_service.render_pdf(session, tenant_id, invoice_id)
    if pdf_bytes is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return Response(content=pdf_bytes, media_type="application/pdf")
