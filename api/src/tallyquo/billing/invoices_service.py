"""Invoice drafts and the issuance transaction.

`issue_invoice` follows architecture.md §6 step for step -- the ordering
there is deliberate (tax computed BEFORE the number is allocated, so a
tax failure never consumes a number) and is preserved exactly here.
"""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tallyquo.billing import fx
from tallyquo.tax.context_builder import build_supply_context
from tallyquo.tax.engine import MissingJurisdiction, NoRateForDate, compute
from tallyquo.tax.loader import load_rate_table


class ComplianceError(Exception):
    """L4-L7: a legally required field is missing or invalid. The message
    is user-facing (design.md voice: state what happened and what to do)."""


class InvoiceNotDraft(Exception):
    """L1, P1: issued invoices are immutable -- edits/re-issue are a 409."""


# ---- drafts -----------------------------------------------------------

_LINE_COLUMNS = "id, description, quantity, unit, unit_rate, amount, is_taxable, project_ref"


async def _fetch_lines(session: AsyncSession, invoice_id: UUID) -> list[dict]:
    result = await session.execute(
        text(f"SELECT {_LINE_COLUMNS} FROM invoice_line WHERE invoice_id = :id ORDER BY position"),
        {"id": invoice_id},
    )
    return [dict(row) for row in result.mappings().all()]


async def _fetch_tax_lines(session: AsyncSession, invoice_id: UUID) -> list[dict]:
    result = await session.execute(
        text(
            "SELECT tax_type, label, rate, taxable_base, amount, display_note "
            "FROM invoice_tax_line WHERE invoice_id = :id ORDER BY position"
        ),
        {"id": invoice_id},
    )
    return [dict(row) for row in result.mappings().all()]


# edgecases.md L15: "Overdue status | Computed, not stored -- derived from
# due_date < today AND amount_paid < total. Never a stale stored flag."
# The `status` column only ever holds draft/issued/cancelled directly;
# paid/partially_paid/overdue are derived here at read time, evaluated in
# the tenant's own timezone (L16), not UTC.
_EFFECTIVE_STATUS_EXPR = """
    CASE
      WHEN invoice.status = 'cancelled' THEN 'cancelled'
      WHEN invoice.status = 'draft' THEN 'draft'
      WHEN invoice.amount_paid >= invoice.total AND invoice.total > 0 THEN 'paid'
      WHEN invoice.amount_paid > 0 THEN 'partially_paid'
      WHEN invoice.due_date IS NOT NULL
           AND invoice.due_date < (now() AT TIME ZONE COALESCE(bp.timezone, 'America/Toronto'))::date
        THEN 'overdue'
      ELSE 'issued'
    END
"""

_INVOICE_COLUMNS = (
    f"invoice.id, invoice.client_id, invoice.number, ({_EFFECTIVE_STATUS_EXPR}) AS status, "
    "invoice.invoice_date, invoice.service_period_start, invoice.service_period_end, "
    "invoice.due_date, invoice.currency, invoice.subtotal, invoice.discount_amount, "
    "invoice.tax_total, invoice.total, invoice.amount_paid, invoice.tax_treatment_snapshot, "
    "invoice.tax_jurisdiction_snapshot, invoice.po_reference, invoice.notes, invoice.created_at, "
    "invoice.issued_at, invoice.cancelled_at, invoice.revision, invoice.parent_invoice_id, "
    "invoice.total_cad, invoice.fx_rate_to_cad, invoice.fx_rate_date, invoice.fx_rate_source, "
    # Never the token itself here -- InvoiceOut is a general-purpose read
    # response, and leaking a live public-access secret into it would
    # defeat the point of it being revocable/hard-to-guess in the first
    # place. Just enough to let the UI offer "view" vs. "get" across a
    # page reload without silently minting a fresh link on every view.
    "invoice.share_token IS NOT NULL AS has_share_link"
)
_INVOICE_FROM = "invoice LEFT JOIN business_profile bp ON bp.tenant_id = invoice.tenant_id"


async def get_invoice(session: AsyncSession, invoice_id: UUID) -> dict | None:
    result = await session.execute(
        text(f"SELECT {_INVOICE_COLUMNS} FROM {_INVOICE_FROM} WHERE invoice.id = :id"),
        {"id": invoice_id},
    )
    row = result.mappings().first()
    if row is None:
        return None
    data = dict(row)
    data["line_items"] = await _fetch_lines(session, invoice_id)
    data["tax_lines"] = await _fetch_tax_lines(session, invoice_id)
    return data


async def list_invoices(
    session: AsyncSession,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    client_id: UUID | None = None,
    status: str | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
    currency: str | None = None,
    tax_treatment: str | None = None,
) -> list[dict]:
    # design.md §8.3: ledger filters as removable chips -- date range,
    # client, status, tax treatment, amount range, currency.
    where = ["1=1"]
    params: dict = {}
    if date_from is not None:
        where.append("invoice.invoice_date >= :date_from")
        params["date_from"] = date_from
    if date_to is not None:
        where.append("invoice.invoice_date <= :date_to")
        params["date_to"] = date_to
    if client_id is not None:
        where.append("invoice.client_id = :client_id")
        params["client_id"] = client_id
    if status is not None:
        # Filters against the same derived expression the SELECT exposes as
        # `status` -- so filtering by "overdue"/"paid" works even though
        # neither is ever a value the `status` column literally holds.
        where.append(f"({_EFFECTIVE_STATUS_EXPR}) = :status")
        params["status"] = status
    if min_amount is not None:
        where.append("invoice.total >= :min_amount")
        params["min_amount"] = min_amount
    if max_amount is not None:
        where.append("invoice.total <= :max_amount")
        params["max_amount"] = max_amount
    if currency is not None:
        where.append("invoice.currency = :currency")
        params["currency"] = currency
    if tax_treatment is not None:
        where.append("invoice.tax_treatment_snapshot = :tax_treatment")
        params["tax_treatment"] = tax_treatment

    result = await session.execute(
        text(
            f"SELECT {_INVOICE_COLUMNS} FROM {_INVOICE_FROM} WHERE {' AND '.join(where)} "
            "ORDER BY invoice.invoice_date DESC NULLS FIRST, invoice.created_at DESC"
        ),
        params,
    )
    return [dict(row) for row in result.mappings().all()]


def _recompute_subtotal(line_items: list[dict]) -> Decimal:
    return sum((li["amount"] for li in line_items), start=Decimal("0.00"))


async def create_draft(session: AsyncSession, tenant_id: UUID, data: dict) -> dict:
    invoice_id = uuid4()
    line_items = data.pop("line_items", [])
    data.pop("include_provincial_sales_tax", None)
    data.pop("template_id", None)  # stored at issue time once a real template pin exists
    subtotal = _recompute_subtotal(line_items)

    columns = [*data.keys(), "id", "tenant_id", "subtotal", "total"]
    placeholders = ", ".join(f":{c}" for c in columns)
    await session.execute(
        text(f"INSERT INTO invoice ({', '.join(columns)}) VALUES ({placeholders})"),
        {**data, "id": invoice_id, "tenant_id": tenant_id, "subtotal": subtotal, "total": subtotal},
    )
    await _replace_lines(session, tenant_id, invoice_id, line_items)
    return await get_invoice(session, invoice_id)  # type: ignore[return-value]


async def _replace_lines(
    session: AsyncSession, tenant_id: UUID, invoice_id: UUID, line_items: list[dict]
) -> None:
    await session.execute(text("DELETE FROM invoice_line WHERE invoice_id = :id"), {"id": invoice_id})
    for position, line in enumerate(line_items):
        await session.execute(
            text(
                "INSERT INTO invoice_line "
                "(id, tenant_id, invoice_id, position, description, quantity, unit, "
                " unit_rate, amount, is_taxable, project_ref) "
                "VALUES (:id, :tenant_id, :invoice_id, :position, :description, :quantity, "
                " :unit, :unit_rate, :amount, :is_taxable, :project_ref)"
            ),
            {
                "id": uuid4(),
                "tenant_id": tenant_id,
                "invoice_id": invoice_id,
                "position": position,
                **line,
            },
        )


async def update_draft(session: AsyncSession, tenant_id: UUID, invoice_id: UUID, data: dict) -> dict:
    existing = await get_invoice(session, invoice_id)
    if existing is None:
        raise ValueError("not_found")
    if existing["status"] != "draft":
        # edgecases.md L1, P1: blocked at the API with 409, not just hidden in the UI.
        raise InvoiceNotDraft("Issued invoices can't be edited. Create a credit note or issue a revision instead.")

    line_items = data.pop("line_items", None)
    data.pop("include_provincial_sales_tax", None)
    data.pop("template_id", None)
    if line_items is not None:
        await _replace_lines(session, tenant_id, invoice_id, line_items)
        subtotal = _recompute_subtotal(line_items)
        data["subtotal"] = subtotal
        data["total"] = subtotal - Decimal("0.00")

    if data:
        set_clause = ", ".join(f"{c} = :{c}" for c in data)
        await session.execute(
            text(f"UPDATE invoice SET {set_clause} WHERE id = :id"), {**data, "id": invoice_id}
        )
    return await get_invoice(session, invoice_id)  # type: ignore[return-value]


# ---- issuance -----------------------------------------------------------

def _format_invoice_number(fmt: str, prefix: str, year: int, number: int) -> str:
    result = fmt.replace("{PREFIX}", prefix).replace("{YYYY}", str(year))
    # {NNN}, {NNNN}, ... -- pad to however many N's appear.
    import re

    def _pad(m: "re.Match[str]") -> str:
        width = len(m.group(0)) - 2  # minus the braces
        return str(number).zfill(width)

    return re.sub(r"\{N+\}", _pad, result)


async def _allocate_number(session: AsyncSession, tenant_id: UUID, fmt: str, prefix: str, invoice_date: date) -> str:
    # N4: scope key uses the INVOICE's year, never today's -- a Dec-31
    # invoice issued Jan 2 still gets last year's sequence. Formats
    # without {YYYY} share one scope for the tenant's whole lifetime.
    scope_key = str(invoice_date.year) if "{YYYY}" in fmt else "_no_year"
    result = await session.execute(
        text(
            "INSERT INTO invoice_sequence (tenant_id, scope_key, next_value) "
            "VALUES (:tenant_id, :scope_key, 2) "
            "ON CONFLICT (tenant_id, scope_key) DO UPDATE "
            "SET next_value = invoice_sequence.next_value + 1 "
            "RETURNING next_value - 1"
        ),
        {"tenant_id": tenant_id, "scope_key": scope_key},
    )
    allocated = result.scalar_one()
    return _format_invoice_number(fmt, prefix, invoice_date.year, allocated)


async def issue_invoice(
    session: AsyncSession,
    tenant_id: UUID,
    actor_id: UUID | None,
    invoice_id: UUID,
    confirm_zero_total: bool,
    *,
    actor_kind: str = "user",
) -> dict:
    # Step 1: load + lock. FOR UPDATE OF invoice scopes the row lock to the
    # invoice table alone -- _INVOICE_FROM's join to business_profile
    # (for the effective-status timezone calc) must not also lock that row.
    result = await session.execute(
        text(f"SELECT {_INVOICE_COLUMNS} FROM {_INVOICE_FROM} WHERE invoice.id = :id FOR UPDATE OF invoice"),
        {"id": invoice_id},
    )
    row = result.mappings().first()
    if row is None:
        raise ValueError("not_found")
    invoice = dict(row)
    if invoice["status"] != "draft":
        raise InvoiceNotDraft("This invoice has already been issued.")

    line_items = await _fetch_lines(session, invoice_id)

    # Step 2: compliance checklist (L4-L7).
    if not line_items:
        raise ComplianceError("Add at least one line item.")
    subtotal = _recompute_subtotal(line_items)
    total = subtotal - invoice["discount_amount"]
    if total < 0:
        raise ComplianceError("That is a credit note. Issue a credit note against the original invoice instead.")
    if total == 0 and not confirm_zero_total:
        raise ComplianceError("This invoice totals $0.00. Confirm that's intentional before issuing.")

    invoice_date = invoice["invoice_date"] or date.today()
    profile_row = (
        await session.execute(
            text(
                "SELECT legal_name, operating_name, address_line1, address_line2, city, "
                "region_code, postal_code, country_code, email, phone, gst_hst_number, "
                "registration_status, registration_effective_date, default_payment_terms_days, "
                "invoice_number_format, invoice_number_prefix "
                "FROM business_profile WHERE tenant_id = :t"
            ),
            {"t": tenant_id},
        )
    ).mappings().first()
    if profile_row is None:
        raise ComplianceError("Add your business profile before issuing invoices.")
    profile = dict(profile_row)

    due_date = invoice["due_date"]
    terms_days = invoice.get("payment_terms_days") or profile["default_payment_terms_days"]
    if due_date is None:
        due_date = invoice_date + timedelta(days=terms_days or 30)
    if due_date < invoice_date:
        raise ComplianceError("Due date can't be before the invoice date.")

    client_row = (
        await session.execute(
            text(
                "SELECT legal_name, address_line1, address_line2, city, region_code, "
                "postal_code, country_code, email, tax_treatment, is_gst_registered, "
                "treatment_override_reason FROM client WHERE id = :id"
            ),
            {"id": invoice["client_id"]},
        )
    ).mappings().first()
    if client_row is None:
        raise ComplianceError("This invoice's client no longer exists.")
    client = dict(client_row)

    evidence_count = (
        await session.execute(
            text(
                "SELECT count(*) FROM client_evidence WHERE client_id = :id "
                "AND kind = 'non_residency_attestation'"
            ),
            {"id": invoice["client_id"]},
        )
    ).scalar_one()

    # Steps 3-5: derive treatment/jurisdiction and compute tax -- BEFORE
    # allocating a number, so a tax failure never consumes one.
    ctx = build_supply_context(
        business_profile=profile,
        client=client,
        line_amounts=[(li["amount"], li["is_taxable"]) for li in line_items],
        invoice_date=invoice_date,
        has_non_residency_evidence=evidence_count > 0,
    )
    rate_table = await load_rate_table(session)
    try:
        tax_result = compute(ctx, rate_table)
    except (NoRateForDate, MissingJurisdiction) as exc:
        raise ComplianceError(str(exc)) from None

    tax_total = tax_result.tax_total
    grand_total = total + tax_total

    # C1/C2/C7: captured once, at issue, and frozen -- never re-derived on
    # a later read. A source failure never blocks issuing; it just leaves
    # the invoice without a CAD figure until someone revisits it (the NULL
    # itself is the "marked for review" signal -- fx_rate_source records
    # why rather than adding a second flag column for the same fact).
    fx_rate_to_cad = fx_rate_date = fx_rate_source = total_cad = None
    if invoice["currency"] == "CAD":
        total_cad = grand_total
    else:
        fx_result = await fx.fetch_rate(invoice["currency"], invoice_date)
        if fx_result is not None:
            fx_rate_to_cad = fx_result.rate
            fx_rate_date = fx_result.rate_date
            fx_rate_source = fx_result.source
            total_cad = fx.convert(grand_total, fx_result.rate)
        else:
            fx_rate_source = "unavailable_at_issue"

    # Template pin: default to the tenant's default system template if none chosen.
    template_row = (
        await session.execute(
            text(
                "SELECT id, version FROM template "
                "WHERE is_system = true AND (tenant_id IS NULL) "
                "ORDER BY is_default DESC LIMIT 1"
            )
        )
    ).mappings().first()

    # Step 6: allocate the number.
    number = await _allocate_number(
        session, tenant_id, profile["invoice_number_format"], profile["invoice_number_prefix"], invoice_date
    )

    supplier_snapshot = {
        "legal_name": profile["legal_name"],
        "operating_name": profile["operating_name"],
        "address_line1": profile["address_line1"],
        "address_line2": profile["address_line2"],
        "city": profile["city"],
        "region_code": profile["region_code"],
        "postal_code": profile["postal_code"],
        "country_code": profile["country_code"],
        "email": profile["email"],
        "phone": profile["phone"],
        "gst_hst_number": profile["gst_hst_number"],
    }
    client_snapshot = {
        "legal_name": client["legal_name"],
        "address_line1": client["address_line1"],
        "address_line2": client["address_line2"],
        "city": client["city"],
        "region_code": client["region_code"],
        "postal_code": client["postal_code"],
        "country_code": client["country_code"],
    }

    # Step 7: write the frozen snapshot + step 8: transition status.
    await session.execute(
        text(
            "UPDATE invoice SET "
            "number = :number, status = 'issued', invoice_date = :invoice_date, "
            "due_date = :due_date, subtotal = :subtotal, tax_total = :tax_total, "
            "total = :total, total_cad = :total_cad, fx_rate_to_cad = :fx_rate_to_cad, "
            "fx_rate_date = :fx_rate_date, fx_rate_source = :fx_rate_source, "
            "tax_treatment_snapshot = :treatment, "
            "tax_jurisdiction_snapshot = :jurisdiction, tax_version_id = :version_id, "
            "template_id = :template_id, template_version = :template_version, "
            "supplier_snapshot = :supplier_snapshot, client_snapshot = :client_snapshot, "
            "issued_at = now() "
            "WHERE id = :id"
        ),
        {
            "number": number,
            "invoice_date": invoice_date,
            "due_date": due_date,
            "subtotal": subtotal,
            "tax_total": tax_total,
            "total": grand_total,
            "treatment": tax_result.treatment.value,
            "jurisdiction": tax_result.jurisdiction,
            "version_id": tax_result.table_version if _is_uuid(tax_result.table_version) else None,
            "template_id": template_row["id"] if template_row else None,
            "template_version": template_row["version"] if template_row else None,
            "supplier_snapshot": json.dumps(supplier_snapshot, default=str),
            "client_snapshot": json.dumps(client_snapshot, default=str),
            "total_cad": total_cad,
            "fx_rate_to_cad": fx_rate_to_cad,
            "fx_rate_date": fx_rate_date,
            "fx_rate_source": fx_rate_source,
            "id": invoice_id,
        },
    )

    for position, line in enumerate(tax_result.lines):
        await session.execute(
            text(
                "INSERT INTO invoice_tax_line "
                "(id, tenant_id, invoice_id, tax_type, label, rate, taxable_base, amount, "
                " display_note, position) "
                "VALUES (:id, :tenant_id, :invoice_id, :tax_type, :label, :rate, :base, "
                " :amount, :note, :position)"
            ),
            {
                "id": uuid4(),
                "tenant_id": tenant_id,
                "invoice_id": invoice_id,
                "tax_type": line.tax_type,
                "label": line.label,
                "rate": line.rate,
                "base": line.taxable_base,
                "amount": line.amount,
                "note": line.display_note,
                "position": position,
            },
        )

    # Step 9: audit log.
    await session.execute(
        text(
            "INSERT INTO audit_log (tenant_id, actor_user_id, actor_kind, action, "
            "entity_type, entity_id, after) "
            "VALUES (:tenant_id, :actor_id, :actor_kind, 'invoice.issued', 'invoice', :entity_id, :after)"
        ),
        {
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "actor_kind": actor_kind,
            "entity_id": invoice_id,
            "after": json.dumps({"number": number, "total": str(grand_total)}),
        },
    )

    return await get_invoice(session, invoice_id)  # type: ignore[return-value]


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except ValueError:
        return False


async def cancel_invoice(session: AsyncSession, invoice_id: UUID, reason: str) -> bool:
    result = await session.execute(
        text(
            "UPDATE invoice SET status = 'cancelled', cancelled_at = now(), cancel_reason = :reason "
            "WHERE id = :id AND status NOT IN ('cancelled', 'draft')"
        ),
        {"id": invoice_id, "reason": reason},
    )
    return result.rowcount > 0


async def create_credit_note(
    session: AsyncSession, tenant_id: UUID, invoice_id: UUID, data: dict
) -> dict | None:
    invoice = await get_invoice(session, invoice_id)
    if invoice is None or invoice["status"] not in ("issued", "partially_paid", "paid", "overdue"):
        return None

    # C8: a foreign-currency credit note uses the original invoice's rate,
    # not today's -- satisfied by never fetching a fresh one here at all.
    # credit_note has no fx columns of its own; any future CAD reporting
    # need must join through invoice.fx_rate_to_cad, not call fx.fetch_rate
    # again for "today".
    credit_note_id = uuid4()
    number = f"{invoice['number']}-CN{await _next_credit_note_seq(session, invoice_id)}"
    await session.execute(
        text(
            "INSERT INTO credit_note (id, tenant_id, invoice_id, number, amount, tax_amount, "
            "currency, reason) "
            "VALUES (:id, :tenant_id, :invoice_id, :number, :amount, :tax_amount, :currency, :reason)"
        ),
        {
            "id": credit_note_id,
            "tenant_id": tenant_id,
            "invoice_id": invoice_id,
            "number": number,
            "currency": invoice["currency"],
            **data,
        },
    )
    result = await session.execute(
        text(
            "SELECT id, invoice_id, number, amount, tax_amount, currency, reason, issued_at "
            "FROM credit_note WHERE id = :id"
        ),
        {"id": credit_note_id},
    )
    return dict(result.mappings().one())


async def render_pdf(session: AsyncSession, tenant_id: UUID, invoice_id: UUID) -> bytes | None:
    """Renders on demand rather than persisting to storage -- the DB row is
    the source of truth (architecture.md ADR-005: "any PDF can be
    regenerated"), and issued invoices use the frozen snapshot so a PDF
    generated today matches one generated in 2033 byte-for-byte (X4), even
    if the business profile or client address has since changed."""
    from tallyquo.templates.pdf_renderer import render_invoice_pdf

    invoice = await get_invoice(session, invoice_id)
    if invoice is None:
        return None

    if invoice["status"] == "draft":
        profile_row = (
            await session.execute(
                text(
                    "SELECT legal_name, operating_name, address_line1, address_line2, city, "
                    "region_code, postal_code, email, gst_hst_number "
                    "FROM business_profile WHERE tenant_id = :t"
                ),
                {"t": tenant_id},
            )
        ).mappings().first()
        client_row = (
            await session.execute(
                text(
                    "SELECT legal_name, address_line1, address_line2, city, region_code, "
                    "postal_code, country_code FROM client WHERE id = :id"
                ),
                {"id": invoice["client_id"]},
            )
        ).mappings().first()
        supplier = dict(profile_row) if profile_row else {"legal_name": "(business profile not set)"}
        client = dict(client_row) if client_row else {"legal_name": "(client not found)"}
    else:
        snap_result = await session.execute(
            text("SELECT supplier_snapshot, client_snapshot FROM invoice WHERE id = :id"),
            {"id": invoice_id},
        )
        snap = snap_result.mappings().one()
        supplier = snap["supplier_snapshot"] or {}
        client = snap["client_snapshot"] or {}

    return render_invoice_pdf(
        invoice=invoice,
        supplier=supplier,
        client=client,
        line_items=invoice["line_items"],
        tax_lines=invoice["tax_lines"],
    )


async def _next_credit_note_seq(session: AsyncSession, invoice_id: UUID) -> int:
    result = await session.execute(
        text("SELECT count(*) FROM credit_note WHERE invoice_id = :id"), {"id": invoice_id}
    )
    return result.scalar_one() + 1
