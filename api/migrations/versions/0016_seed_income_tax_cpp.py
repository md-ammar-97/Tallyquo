"""Seed income tax brackets (federal + 12 non-Quebec jurisdictions) and
CPP parameters for 2025 and 2026 (problem-statement.md §10, Phase 3 3.1).

Verify against CRA and provincial sources before relying on this in a
real filing -- same disclaimer as 0005_seed_tax_rates. Quebec is
absent: QPP replaces CPP and Quebec runs its own income tax system,
out of scope until implementation_plan.md 4.4 (Phase 4).

Modelling choice, documented once here rather than per-row: the basic
personal amount (BPA) is represented as a synthetic $0-to-BPA bracket
at 0%, prepended to each jurisdiction's real brackets, rather than as
a separate credit applied after computing tax. These are
mathematically identical *when the BPA credit rate equals the
jurisdiction's lowest marginal rate*, which is true by design in
every jurisdiction seeded here -- so this isn't an approximation, it's
an equivalent representation that avoids a second reference table.

Known, deliberate simplifications (all in the direction of a rougher
but still directionally-correct "recommended set-aside", never used
for actual filing -- P9, edgecases.md §12):
- No federal high-income BPA phase-out (the ~$180k-$258k band where
  the credit shrinks) -- the seeded 4th/5th bracket rates use the
  clean statutory rate (e.g. 29%, not the blended ~29.3% effective
  rate the phase-out produces).
- No provincial surtaxes (Ontario, PEI) -- these compound on top of
  the bracket rate at higher incomes and are not modelled.
- Yukon's BPA mirrors the federal BPA by statute; the maximum (not
  income-reduced) federal BPA figure is used for simplicity.
- CPP2 parameters are seeded (2024+ second contribution tier) even
  though 3.6's CPP estimate may start with base CPP only -- having
  both available now avoids a second migration later.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-07

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tt(code: str) -> str:
    return f"https://www.taxtips.ca/taxrates/{code}.htm"


# jurisdiction -> { year: (bpa, [(income_from, income_to, rate), ...], source_url) }
# income_to = None means the top, unbounded bracket.
JURISDICTIONS: dict[str, dict[int, tuple]] = {
    "federal": {
        2025: (16129, [
            (16129, 57375, 0.14500), (57375, 114750, 0.20500),
            (114750, 177882, 0.26000), (177882, 253414, 0.29000),
            (253414, None, 0.33000),
        ], _tt("canada")),
        2026: (16452, [
            (16452, 58523, 0.14000), (58523, 117045, 0.20500),
            (117045, 181440, 0.26000), (181440, 258482, 0.29000),
            (258482, None, 0.33000),
        ], _tt("canada")),
    },
    "ON": {
        2025: (12747, [
            (12747, 52886, 0.05050), (52886, 105775, 0.09150),
            (105775, 150000, 0.11160), (150000, 220000, 0.12160),
            (220000, None, 0.13160),
        ], _tt("on")),
        2026: (12989, [
            (12989, 53891, 0.05050), (53891, 107785, 0.09150),
            (107785, 150000, 0.11160), (150000, 220000, 0.12160),
            (220000, None, 0.13160),
        ], _tt("on")),
    },
    "BC": {
        2025: (12932, [
            (12932, 49279, 0.05060), (49279, 98560, 0.07700),
            (98560, 113158, 0.10500), (113158, 137407, 0.12290),
            (137407, 186306, 0.14700), (186306, 259829, 0.16800),
            (259829, None, 0.20500),
        ], _tt("bc")),
        2026: (13216, [
            (13216, 50363, 0.05600), (50363, 100728, 0.07700),
            (100728, 115648, 0.10500), (115648, 140430, 0.12290),
            (140430, 190405, 0.14700), (190405, 265545, 0.16800),
            (265545, None, 0.20500),
        ], _tt("bc")),
    },
    "AB": {
        2025: (22323, [
            (22323, 60000, 0.08000), (60000, 151234, 0.10000),
            (151234, 181481, 0.12000), (181481, 241974, 0.13000),
            (241974, 362961, 0.14000), (362961, None, 0.15000),
        ], _tt("ab")),
        2026: (22769, [
            (22769, 61200, 0.08000), (61200, 154259, 0.10000),
            (154259, 185111, 0.12000), (185111, 246813, 0.13000),
            (246813, 370220, 0.14000), (370220, None, 0.15000),
        ], _tt("ab")),
    },
    "SK": {
        2025: (19491, [
            (19491, 53463, 0.10500), (53463, 152750, 0.12500),
            (152750, None, 0.14500),
        ], _tt("sk")),
        2026: (20381, [
            (20381, 54532, 0.10500), (54532, 155805, 0.12500),
            (155805, None, 0.14500),
        ], _tt("sk")),
    },
    "MB": {
        2025: (15780, [
            (15780, 47000, 0.10800), (47000, 100000, 0.12750),
            (100000, None, 0.17400),
        ], _tt("mb")),
        2026: (15780, [
            (15780, 47000, 0.10800), (47000, 100000, 0.12750),
            (100000, None, 0.17400),
        ], _tt("mb")),  # 2026 Budget: indexation frozen, unchanged from 2025
    },
    "NB": {
        2025: (13396, [
            (13396, 51306, 0.09400), (51306, 102614, 0.14000),
            (102614, 190060, 0.16000), (190060, None, 0.19500),
        ], _tt("nb")),
        2026: (13664, [
            (13664, 52333, 0.09400), (52333, 104666, 0.14000),
            (104666, 193861, 0.16000), (193861, None, 0.19500),
        ], _tt("nb")),
    },
    "NS": {
        2025: (11744, [
            (11744, 30507, 0.08790), (30507, 61015, 0.14950),
            (61015, 95883, 0.16670), (95883, 154650, 0.17500),
            (154650, None, 0.21000),
        ], _tt("ns")),
        2026: (11932, [
            (11932, 30995, 0.08790), (30995, 61991, 0.14950),
            (61991, 97417, 0.16670), (97417, 157124, 0.17500),
            (157124, None, 0.21000),
        ], _tt("ns")),
    },
    "PE": {
        2025: (14650, [
            (14650, 33328, 0.09500), (33328, 64656, 0.13470),
            (64656, 105000, 0.16600), (105000, 140000, 0.17620),
            (140000, None, 0.19000),
        ], _tt("pe")),
        2026: (15000, [
            (15000, 33928, 0.09500), (33928, 65820, 0.13470),
            (65820, 106890, 0.16600), (106890, 142250, 0.17620),
            (142250, 200000, 0.19000), (200000, None, 0.20000),
        ], _tt("pe")),
    },
    "NL": {
        2025: (11067, [
            (11067, 44192, 0.08700), (44192, 88382, 0.14500),
            (88382, 157792, 0.15800), (157792, 220910, 0.17800),
            (220910, 282214, 0.19800), (282214, 564429, 0.20800),
            (564429, 1128858, 0.21300), (1128858, None, 0.21800),
        ], _tt("nl")),
        2026: (13094, [
            (13094, 44678, 0.08700), (44678, 89354, 0.14500),
            (89354, 159528, 0.15800), (159528, 223340, 0.17800),
            (223340, 285319, 0.19800), (285319, 570638, 0.20800),
            (570638, 1141275, 0.21300), (1141275, None, 0.21800),
        ], _tt("nl")),
    },
    "YT": {
        2025: (16129, [
            (16129, 57375, 0.06400), (57375, 114750, 0.09000),
            (114750, 177882, 0.10900), (177882, 500000, 0.12800),
            (500000, None, 0.15000),
        ], _tt("yt")),
        2026: (16452, [
            (16452, 58523, 0.06400), (58523, 117045, 0.09000),
            (117045, 181440, 0.10900), (181440, 500000, 0.12800),
            (500000, None, 0.15000),
        ], _tt("yt")),
    },
    "NT": {
        2025: (17842, [
            (17842, 51964, 0.05900), (51964, 103930, 0.08600),
            (103930, 168967, 0.12200), (168967, None, 0.14050),
        ], _tt("nt")),
        2026: (18198, [
            (18198, 53003, 0.05900), (53003, 106009, 0.08600),
            (106009, 172346, 0.12200), (172346, None, 0.14050),
        ], _tt("nt")),
    },
    "NU": {
        2025: (19274, [
            (19274, 54707, 0.04000), (54707, 109413, 0.07000),
            (109413, 177881, 0.09000), (177881, None, 0.11500),
        ], _tt("nu")),
        2026: (19659, [
            (19659, 55801, 0.04000), (55801, 111602, 0.07000),
            (111602, 181439, 0.09000), (181439, None, 0.11500),
        ], _tt("nu")),
    },
}

YEAR_DATES = {2025: ("2025-01-01", "2025-12-31"), 2026: ("2026-01-01", None)}

CPP_SOURCE = "https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/payroll/payroll-deductions-contributions/canada-pension-plan-cpp/cpp-contribution-rates-maximums-exemptions.html"

# year -> (basic_exemption, ympe, yampe, employee_rate, self_employed_rate, cpp2_employee_rate, cpp2_self_employed_rate)
CPP_PARAMS = {
    2025: (3500.00, 71300.00, 81200.00, 0.05950, 0.11900, 0.04000, 0.08000),
    2026: (3500.00, 74600.00, 85000.00, 0.05950, 0.11900, 0.04000, 0.08000),
}


def upgrade() -> None:
    conn = op.get_bind()

    bracket_insert = sa.text(
        "INSERT INTO income_tax_bracket "
        "(id, jurisdiction, income_from, income_to, rate, effective_from, effective_to, source_url) "
        "VALUES (:id, :jurisdiction, :income_from, :income_to, :rate, :eff_from, :eff_to, :source_url)"
    )

    for jurisdiction, years in JURISDICTIONS.items():
        for year, (bpa, brackets, source_url) in years.items():
            eff_from, eff_to = YEAR_DATES[year]
            rows = [(0, bpa, 0.0), *brackets]
            for income_from, income_to, rate in rows:
                conn.execute(
                    bracket_insert,
                    {
                        "id": str(uuid.uuid4()),
                        "jurisdiction": jurisdiction,
                        "income_from": income_from,
                        "income_to": income_to,
                        "rate": rate,
                        "eff_from": eff_from,
                        "eff_to": eff_to,
                        "source_url": source_url,
                    },
                )

    cpp_insert = sa.text(
        "INSERT INTO cpp_parameter "
        "(id, basic_exemption, ympe, yampe, employee_rate, self_employed_rate, "
        " cpp2_employee_rate, cpp2_self_employed_rate, effective_from, effective_to, source_url) "
        "VALUES (:id, :basic_exemption, :ympe, :yampe, :employee_rate, :self_employed_rate, "
        " :cpp2_employee_rate, :cpp2_self_employed_rate, :eff_from, :eff_to, :source_url)"
    )
    for year, params in CPP_PARAMS.items():
        eff_from, eff_to = YEAR_DATES[year]
        (basic_exemption, ympe, yampe, employee_rate, self_employed_rate,
         cpp2_employee_rate, cpp2_self_employed_rate) = params
        conn.execute(
            cpp_insert,
            {
                "id": str(uuid.uuid4()),
                "basic_exemption": basic_exemption,
                "ympe": ympe,
                "yampe": yampe,
                "employee_rate": employee_rate,
                "self_employed_rate": self_employed_rate,
                "cpp2_employee_rate": cpp2_employee_rate,
                "cpp2_self_employed_rate": cpp2_self_employed_rate,
                "eff_from": eff_from,
                "eff_to": eff_to,
                "source_url": CPP_SOURCE,
            },
        )


def downgrade() -> None:
    op.execute("DELETE FROM cpp_parameter")
    op.execute("DELETE FROM income_tax_bracket")
