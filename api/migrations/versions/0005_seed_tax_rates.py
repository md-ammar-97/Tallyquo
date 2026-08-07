"""Seed tax rates as of August 2026 (problem-statement.md §6.4).

Verify against CRA and provincial sources before relying on this in a real
filing -- this is a product specification snapshot, not tax advice (see
the disclaimer at the foot of problem-statement.md). Future changes go
through the reviewed pipeline (architecture.md §7), never a bare migration.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-07

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VERSION_ID = "8b2f1b6a-2026-4a01-9c00-000000000001"

RATES = [
    # country, region, tax_type, rate, label, effective_from, effective_to, source_url
    ("CA", None, "gst", "0.05000", "GST", "1991-01-01", None),
    ("CA", "ON", "hst", "0.13000", "HST", "2010-07-01", None),
    ("CA", "NB", "hst", "0.15000", "HST", "2016-07-01", None),
    ("CA", "NL", "hst", "0.15000", "HST", "2016-07-01", None),
    ("CA", "PE", "hst", "0.15000", "HST", "2016-10-01", None),
    ("CA", "NS", "hst", "0.15000", "HST", "2010-07-01", "2025-03-31"),
    ("CA", "NS", "hst", "0.14000", "HST", "2025-04-01", None),
    ("CA", "QC", "qst", "0.09975", "QST", "2013-01-01", None),
    ("CA", "BC", "pst", "0.07000", "PST", "2013-04-01", None),
    ("CA", "SK", "pst", "0.06000", "PST", "2025-01-01", None),
    ("CA", "MB", "rst", "0.07000", "RST", "2019-07-01", None),
]

SOURCE_URL = "https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/charge-collect-which-rate.html"


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO tax_rate_version (id, label, approved_by, source_note) "
            "VALUES (:id, :label, :approved_by, :note)"
        ),
        {
            "id": VERSION_ID,
            "label": "2026-08",
            "approved_by": "seed-migration",
            "note": "Initial seed from problem-statement.md §6.4, verify before production use.",
        },
    )
    for country, region, tax_type, rate, label, eff_from, eff_to in RATES:
        conn.execute(
            sa.text(
                "INSERT INTO tax_rate "
                "(id, version_id, country_code, region_code, tax_type, rate, label, "
                " effective_from, effective_to, source_url) "
                "VALUES (:id, :version_id, :country, :region, :tax_type, :rate, :label, "
                " :eff_from, :eff_to, :source_url)"
            ),
            {
                "id": str(uuid.uuid4()),
                "version_id": VERSION_ID,
                "country": country,
                "region": region,
                "tax_type": tax_type,
                "rate": rate,
                "label": label,
                "eff_from": eff_from,
                "eff_to": eff_to,
                "source_url": SOURCE_URL,
            },
        )

    conn.execute(
        sa.text(
            "INSERT INTO tax_threshold (country_code, kind, amount, effective_from, source_url) "
            "VALUES ('CA', 'small_supplier', 30000.00, '1991-01-01', :url)"
        ),
        {"url": SOURCE_URL},
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM tax_threshold WHERE country_code = 'CA'")
    op.execute(f"DELETE FROM tax_rate WHERE version_id = '{VERSION_ID}'")
    op.execute(f"DELETE FROM tax_rate_version WHERE id = '{VERSION_ID}'")
