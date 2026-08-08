"""Deterministic server-side PDF rendering (ADR-004).

Pure-Python via reportlab -- deliberately not an HTML/CSS engine like
WeasyPrint, which needs system-level Pango/cairo libraries unavailable on
Render's standard Python buildpack without a custom Docker image. This
keeps rendering identical across local dev, CI, and production with zero
extra infrastructure.

The compliance block (supplier name/address, invoice number/date, client
name/address, tax breakdown, GST/HST number when registered) is always
rendered -- there is no code path that omits it, matching architecture.md
§12 ("no user-authored HTML/CSS/JS ... no injection surface because there
is no HTML input").

Payment instructions and the notes/footer section are the two genuinely
optional blocks (invoices_service.py gates both on whether the resolved
template's `blocks` array actually lists them) -- design.md §9's layout
order is "then payment instructions, then footer", so that's where they
land here too.
"""

from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_STYLES = getSampleStyleSheet()


def _money(amount: Decimal, currency: str) -> str:
    return f"{currency} {amount:,.2f}"


def render_invoice_pdf(
    *,
    invoice: dict,
    supplier: dict,
    client: dict,
    line_items: list[dict],
    tax_lines: list[dict],
    accent_color: str = "#0D99FF",
    payment_instruction: dict | None = None,
    notes_visible: bool = True,
) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        title=f"Invoice {invoice.get('number') or 'DRAFT'}",
    )
    accent = colors.HexColor(accent_color)
    title_style = ParagraphStyle(
        "InvoiceTitle", parent=_STYLES["Title"], textColor=accent, fontSize=20, alignment=2
    )
    label_style = ParagraphStyle("Label", parent=_STYLES["Normal"], textColor=colors.HexColor("#757575"), fontSize=8)
    body_style = ParagraphStyle("Body", parent=_STYLES["Normal"], fontSize=10)

    story = []

    # --- supplier + document header (side by side) -----------------------
    supplier_lines = [supplier.get("operating_name") or supplier["legal_name"]]
    if supplier.get("operating_name"):
        supplier_lines.append(f"{supplier['legal_name']}, sole proprietor")
    supplier_lines += [
        supplier.get("address_line1", ""),
        supplier.get("address_line2") or "",
        f"{supplier.get('city', '')}, {supplier.get('region_code', '')} {supplier.get('postal_code', '')}",
        supplier.get("email") or "",
    ]
    if supplier.get("gst_hst_number"):
        supplier_lines.append(f"GST/HST: {supplier['gst_hst_number']}")
    supplier_para = Paragraph("<br/>".join(line for line in supplier_lines if line), body_style)

    doc_meta = [
        f"<b>INVOICE</b> {invoice.get('number') or '(draft)'}",
        f"Date: {invoice.get('invoice_date') or ''}",
        f"Due: {invoice.get('due_date') or ''}",
        f"Currency: {invoice.get('currency', 'CAD')}",
    ]
    if invoice.get("service_period_start"):
        doc_meta.append(f"Service period: {invoice['service_period_start']} - {invoice.get('service_period_end', '')}")
    if invoice.get("po_reference"):
        doc_meta.append(f"PO: {invoice['po_reference']}")
    doc_meta_para = Paragraph("<br/>".join(doc_meta), ParagraphStyle("DocMeta", parent=body_style, alignment=2))

    header_table = Table([[supplier_para, doc_meta_para]], colWidths=[90 * mm, 80 * mm])
    header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(header_table)
    story.append(Spacer(1, 10 * mm))

    # --- bill-to -----------------------------------------------------------
    bill_to_lines = [
        "<b>Bill to</b>",
        client["legal_name"],
        client.get("address_line1") or "",
        client.get("address_line2") or "",
        f"{client.get('city', '')}, {client.get('region_code', '') or ''} {client.get('postal_code', '') or ''}",
        client.get("country_code", ""),
    ]
    story.append(Paragraph("<br/>".join(line for line in bill_to_lines if line), body_style))
    story.append(Spacer(1, 8 * mm))

    # --- line items ---------------------------------------------------------
    rows = [["Description", "Qty", "Unit", "Rate", "Amount"]]
    for li in line_items:
        rows.append(
            [
                li["description"],
                str(li["quantity"]),
                li["unit"],
                _money(Decimal(str(li["unit_rate"])), invoice.get("currency", "CAD")),
                _money(Decimal(str(li["amount"])), invoice.get("currency", "CAD")),
            ]
        )
    line_table = Table(rows, colWidths=[75 * mm, 15 * mm, 20 * mm, 30 * mm, 30 * mm])
    line_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5F5F5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#757575")),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#D9D9D9")),
                ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(line_table)
    story.append(Spacer(1, 6 * mm))

    # --- totals: subtotal, tax lines (the 3-variant contract), total -------
    currency = invoice.get("currency", "CAD")
    totals_rows = [["Subtotal", _money(Decimal(str(invoice["subtotal"])), currency)]]
    for tl in tax_lines:
        if tl.get("rate") is None and tl.get("display_note"):
            # "Not charged" / "Exempt" -- a statement, no amount column at
            # all (design.md §9: formatting it as CAD 0.00 would imply a
            # tax calculation happened when none did).
            totals_rows.append([f"GST/HST: {tl['display_note']}", ""])
        else:
            totals_rows.append([tl["label"], _money(Decimal(str(tl["amount"])), currency)])
    totals_rows.append(["Total due", _money(Decimal(str(invoice["total"])), currency)])

    totals_table = Table(totals_rows, colWidths=[130 * mm, 40 * mm])
    style_cmds = [
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LINEABOVE", (0, -1), (-1, -1), 1, accent),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    totals_table.setStyle(TableStyle(style_cmds))
    story.append(totals_table)
    story.append(Spacer(1, 10 * mm))

    # --- payment instructions (optional block, gated by the caller) --------
    if payment_instruction:
        lines = [f"<b>Payment instructions</b> ({payment_instruction['currency']})"]
        method = payment_instruction.get("method")
        if method:
            lines.append(method.replace("_", " ").title())
        if payment_instruction.get("provider"):
            lines.append(payment_instruction["provider"])
        if payment_instruction.get("account_holder"):
            lines.append(f"Account holder: {payment_instruction['account_holder']}")
        for key, value in (payment_instruction.get("fields") or {}).items():
            if value:
                lines.append(f"{key.replace('_', ' ').title()}: {value}")
        story.append(Paragraph("<br/>".join(lines), body_style))
        story.append(Spacer(1, 6 * mm))

    if notes_visible and invoice.get("notes"):
        story.append(Paragraph(f"<b>Notes</b><br/>{invoice['notes']}", body_style))

    doc.build(story)
    return buf.getvalue()
