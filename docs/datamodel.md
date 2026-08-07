# Data Model

**Companion to:** `problem-statement.md`, `architecture.md`
**Status:** Draft v0.1
**Target:** PostgreSQL 15+

---

## 1. Modelling rules

Applied uniformly. Violations of these are schema bugs, not style preferences.

1. **Every tenant-scoped table has `tenant_id uuid NOT NULL` and an RLS policy.** No exceptions, including logs, uploads, and lookup tables that reference tenant data.
2. **Money is `numeric(14,2)`, never float.** Rates are `numeric(7,5)` to hold `0.09975` (QST) exactly. FX rates are `numeric(14,8)`.
3. **Every money column has a companion currency**, or belongs to a row that has one. There are no bare amounts.
4. **Timestamps are `timestamptz`, stored UTC.** Business dates (invoice date, service period, expense date) are `date` — they are calendar facts, not instants, and must not shift by timezone.
5. **Enums are Postgres enum types**, not free text, for anything the tax engine or state machine branches on.
6. **Financial rows are never hard-deleted.** `deleted_at` on entities that can be archived; issued invoices cannot even be archived.
7. **Foreign keys always include `tenant_id`** in composite form where it prevents cross-tenant references (see §9).

---

## 2. Enum types

```sql
CREATE TYPE registration_status AS ENUM (
  'not_registered',      -- small supplier, no BN
  'registration_pending',-- applied, awaiting BN
  'registered'           -- BN issued; see registration_effective_date
);

CREATE TYPE tax_treatment AS ENUM (
  'not_registered',      -- supplier not registered → no tax, no ITCs
  'taxable',             -- rate derived from recipient jurisdiction
  'zero_rated_export',   -- 0%, counts toward threshold, ITCs allowed
  'exempt'               -- not taxable, no ITCs
);

CREATE TYPE tax_type AS ENUM ('gst', 'hst', 'pst', 'qst', 'rst');

CREATE TYPE invoice_status AS ENUM (
  'draft', 'issued', 'partially_paid', 'paid', 'overdue', 'cancelled'
);

CREATE TYPE line_unit AS ENUM ('hours', 'days', 'units', 'fixed');

CREATE TYPE recurrence_cadence AS ENUM (
  'weekly', 'biweekly', 'monthly', 'quarterly', 'semiannual', 'annual'
);

CREATE TYPE expense_source AS ENUM ('manual', 'ocr', 'recurring', 'import');

CREATE TYPE payment_method AS ENUM (
  'eft', 'ach', 'wire', 'cheque', 'cash', 'card', 'etransfer', 'other'
);

CREATE TYPE evidence_kind AS ENUM (
  'non_residency_attestation', 'contract', 'registration_certificate', 'other'
);
```

`tax_treatment` is the single most important type in the schema. Storing `0.00` in a rate column instead of distinguishing `zero_rated_export` from `not_registered` is the defect this enum exists to prevent — see `problem-statement.md` §5.1.

---

## 3. Identity and tenancy

```sql
CREATE TABLE tenant (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  status        text NOT NULL DEFAULT 'active',   -- active | suspended | closed
  created_at    timestamptz NOT NULL DEFAULT now(),
  closed_at     timestamptz
);

CREATE TABLE app_user (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenant(id),
  email         citext NOT NULL,
  email_verified_at timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  last_seen_at  timestamptz,
  UNIQUE (email)                    -- one email = one tenant, globally
);

CREATE TABLE otp_code (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email         citext NOT NULL,
  code_hash     bytea NOT NULL,
  expires_at    timestamptz NOT NULL,
  attempts      smallint NOT NULL DEFAULT 0,
  consumed_at   timestamptz,
  ip_hash       bytea,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON otp_code (email, created_at DESC);
-- Not tenant-scoped: exists before a tenant does. Purged after 24h.

CREATE TABLE session (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         uuid NOT NULL REFERENCES tenant(id),
  user_id           uuid NOT NULL REFERENCES app_user(id),
  refresh_token_hash bytea NOT NULL,
  token_family      uuid NOT NULL,     -- rotation lineage; replay revokes family
  device_label      text,
  ip_hash           bytea,
  created_at        timestamptz NOT NULL DEFAULT now(),
  last_used_at      timestamptz,
  expires_at        timestamptz NOT NULL,
  revoked_at        timestamptz
);
```

**Note on `UNIQUE (email)` on `app_user`.** This is what enforces "one email = one tenant." It also means an email cannot be reused after a tenant closes — deliberate, because reuse would risk surfacing a prior tenant's data through any reference we missed.

---

## 4. Business profile

```sql
CREATE TABLE business_profile (
  tenant_id     uuid PRIMARY KEY REFERENCES tenant(id),
  legal_name    text NOT NULL,          -- "Mohammad Ammar"
  operating_name text,                  -- "Orbyn Labs"
  sole_prop_label text DEFAULT 'sole proprietor, operating as',

  address_line1 text NOT NULL,
  address_line2 text,
  city          text NOT NULL,
  region_code   text NOT NULL,          -- 'ON', 'BC' — ISO 3166-2 subdivision
  postal_code   text NOT NULL,
  country_code  char(2) NOT NULL DEFAULT 'CA',

  email         citext,
  phone         text,
  website       text,
  social_links  jsonb NOT NULL DEFAULT '[]',  -- [{platform, url}]

  logo_ref      text,                   -- storage key
  logo_dark_ref text,

  registration_status registration_status NOT NULL DEFAULT 'not_registered',
  gst_hst_number text,                  -- '123456789RT0001'
  registration_effective_date date,
  qst_number    text,                   -- Revenu Québec, separate
  pst_numbers   jsonb NOT NULL DEFAULT '{}',  -- {"BC":"PST-1234-5678"}

  default_currency char(3) NOT NULL DEFAULT 'CAD',
  default_payment_terms_days smallint NOT NULL DEFAULT 30,
  invoice_number_format text NOT NULL DEFAULT '{PREFIX}-{YYYY}-{NNN}',
  invoice_number_prefix text NOT NULL DEFAULT 'INV',
  fiscal_year_start_month smallint NOT NULL DEFAULT 1,
  timezone      text NOT NULL DEFAULT 'America/Toronto',
  gst_filing_frequency text,            -- annual | quarterly | monthly

  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT registered_requires_bn CHECK (
    registration_status <> 'registered'
    OR (gst_hst_number IS NOT NULL AND registration_effective_date IS NOT NULL)
  )
);

CREATE TABLE payment_instruction (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenant(id),
  label         text NOT NULL,            -- 'Canadian EFT', 'US ACH'
  method        payment_method NOT NULL,
  provider      text,                     -- 'Wise Business'
  account_holder text,
  currency      char(3) NOT NULL,
  fields_encrypted bytea,                 -- institution/transit/account/routing
  is_default    boolean NOT NULL DEFAULT false,
  archived_at   timestamptz
);
```

Banking fields are stored encrypted at the column level, not in plaintext JSON. They are decrypted only in the render process, and never returned to the client in full — the UI shows masked values with an explicit reveal action.

**`registration_effective_date` is load-bearing.** Invoices dated before it must render "not charged"; invoices on or after must charge tax. This is derived automatically, never toggled by hand.

**Shipped 2026-08-07: user-configured SMTP for invoice sending.** `implementation_plan.md` 2.16/2.17, `edgecases.md` §8. Migration `0014_email_sending`.

```sql
CREATE TABLE email_account (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  label         text NOT NULL,            -- 'My Gmail', 'Work Outlook'
  from_name     text NOT NULL,
  from_address  citext NOT NULL,
  smtp_host     text NOT NULL,
  smtp_port     smallint NOT NULL,
  smtp_security text NOT NULL DEFAULT 'starttls',  -- starttls | tls | none
  smtp_username text NOT NULL,
  credentials_encrypted bytea NOT NULL,    -- password / app-password, column-level encrypted -- same pattern as payment_instruction.fields_encrypted above
  is_default    boolean NOT NULL DEFAULT false,
  verified_at   timestamptz,               -- last successful "Test" (connect + authenticate, no message sent); unverified accounts are usable but flagged
  created_at    timestamptz NOT NULL DEFAULT now(),
  archived_at   timestamptz,
  UNIQUE (tenant_id, id),
  CONSTRAINT email_account_security_check CHECK (smtp_security IN ('starttls', 'tls', 'none'))
);

CREATE TABLE invoice_email_log (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  invoice_id    uuid NOT NULL,
  email_account_id uuid NOT NULL,
  to_addresses  jsonb NOT NULL,            -- ["client@example.com"]
  cc_addresses  jsonb NOT NULL DEFAULT '[]',
  subject       text NOT NULL,
  body          text NOT NULL,
  attached_invoice_pdf boolean NOT NULL DEFAULT true,  -- O5: the default attachment is removable
  extra_attachments jsonb NOT NULL DEFAULT '[]',       -- [{filename, byte_size, mime_type}] -- metadata only, not persisted to storage; extra attachments live for the one send and are not retrievable again afterward
  sent_by_user_id uuid,
  status        text NOT NULL,             -- sent | failed
  error_detail  text,
  sent_at       timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoice (tenant_id, id),
  FOREIGN KEY (tenant_id, email_account_id) REFERENCES email_account (tenant_id, id),
  CONSTRAINT invoice_email_log_status_check CHECK (status IN ('sent', 'failed'))
);
```

Both tables carry `FORCE ROW LEVEL SECURITY` and the standard `tenant_isolation` policy (§1). `invoice_email_log` is append-only in spirit (like `audit_log`, §11) — it's the durable answer to "was this invoice emailed, and to whom" (O10), kept distinct from the invoice's own frozen snapshot; its grant is `SELECT, INSERT` only, no `UPDATE`/`DELETE`. Nothing here is ever written by a background job; every row corresponds to one explicit, human-initiated send (O1, O7, O9) — and a row is written whether that send fully succeeded, partially succeeded, or failed outright, all in the same transaction as the attempt.

`email_account.credentials_encrypted` is never decrypted back to the client once saved — there's no reveal endpoint for it at all (unlike `payment_instruction`, where a human occasionally needs to re-see banking details). Confirming a saved password still works is what the "Test" action is for.

---

## 5. Clients and projects

```sql
CREATE TABLE client (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenant(id),
  legal_name    text NOT NULL,
  display_name  text,
  contact_name  text,
  email         citext,
  phone         text,

  address_line1 text,
  address_line2 text,
  city          text,
  region_code   text,        -- 'ON', 'CA-QC', 'US-CA' — resolved, not free text
  postal_code   text,
  country_code  char(2) NOT NULL,

  tax_treatment tax_treatment NOT NULL,
  is_gst_registered boolean,           -- recipient's own registration status
  treatment_override_reason text,      -- required if user overrides the derived value

  default_currency char(3) NOT NULL DEFAULT 'CAD',
  default_payment_terms_days smallint,
  default_rate  numeric(14,2),
  default_template_id uuid,
  notes         text,

  created_at    timestamptz NOT NULL DEFAULT now(),
  archived_at   timestamptz,

  UNIQUE (tenant_id, id),
  CONSTRAINT taxable_requires_region CHECK (
    tax_treatment <> 'taxable' OR region_code IS NOT NULL
  )
);
CREATE INDEX ON client (tenant_id, archived_at, legal_name);

CREATE TABLE client_evidence (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  client_id     uuid NOT NULL,
  kind          evidence_kind NOT NULL,
  file_ref      text NOT NULL,
  file_hash     bytea NOT NULL,
  effective_date date,
  expires_at    date,
  note          text,
  uploaded_at   timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_id) REFERENCES client (tenant_id, id)
);

CREATE TABLE project (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  client_id     uuid NOT NULL,
  name          text NOT NULL,
  code          text,
  default_rate  numeric(14,2),
  archived_at   timestamptz,
  FOREIGN KEY (tenant_id, client_id) REFERENCES client (tenant_id, id)
);
```

`client_evidence` is where the non-residency attestation lives. For a `zero_rated_export` client, the absence of evidence produces a warning on every invoice — the CRA places the burden of retaining proof of non-resident status on the supplier, so the product should nag until it exists.

---

## 6. Tax reference data

The only global (non-tenant-scoped) tables in the schema.

```sql
CREATE TABLE tax_rate_version (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  label         text NOT NULL,            -- '2026-04' 
  published_at  timestamptz NOT NULL,
  approved_by   text NOT NULL,            -- human reviewer, never a job
  source_note   text
);

CREATE TABLE tax_rate (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  version_id    uuid NOT NULL REFERENCES tax_rate_version(id),
  country_code  char(2) NOT NULL,
  region_code   text,                     -- NULL = country-wide (federal GST)
  tax_type      tax_type NOT NULL,
  rate          numeric(7,5) NOT NULL,    -- 0.13000, 0.09975
  label         text NOT NULL,            -- 'HST', 'GST', 'QST'
  compounds_on_gst boolean NOT NULL DEFAULT false,  -- always false in CA today
  effective_from date NOT NULL,
  effective_to  date,                     -- NULL = current
  source_url    text NOT NULL,
  EXCLUDE USING gist (
    country_code WITH =, region_code WITH =, tax_type WITH =,
    daterange(effective_from, effective_to) WITH &&
  )
);
```

The exclusion constraint is the important line: it makes overlapping effective periods for the same `(jurisdiction, tax_type)` **impossible at the database level**. A bad rate update cannot create ambiguity about which rate applied on a given date.

**Seed data as of August 2026** (verify against CRA before implementation):

| country | region | type | rate | effective_from |
|---|---|---|---|---|
| CA | — | gst | 0.05000 | 1991-01-01 |
| CA | ON | hst | 0.13000 | 2010-07-01 |
| CA | NB | hst | 0.15000 | 2016-07-01 |
| CA | NL | hst | 0.15000 | 2016-07-01 |
| CA | PE | hst | 0.15000 | 2016-10-01 |
| CA | NS | hst | 0.15000 | 2010-07-01 → *to* 2025-03-31 |
| CA | NS | hst | 0.14000 | **2025-04-01** |
| CA | QC | qst | 0.09975 | 2013-01-01 |
| CA | BC | pst | 0.07000 | 2013-04-01 |
| CA | SK | pst | 0.06000 | 2025-01-01 |
| CA | MB | rst | 0.07000 | 2019-07-01 |
| CA | AB/YT/NT/NU | — | — | GST only |

The Nova Scotia pair is the canonical test case: an invoice dated 2025-03-15 must resolve 15%, an invoice dated 2025-04-15 must resolve 14%, and both must still resolve correctly when queried in 2030.

```sql
CREATE TABLE tax_threshold (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  country_code  char(2) NOT NULL,
  kind          text NOT NULL,         -- 'small_supplier', 'instalment'
  amount        numeric(14,2) NOT NULL,
  effective_from date NOT NULL,
  effective_to  date,
  source_url    text NOT NULL
);
-- seed: CA / small_supplier / 30000.00 / 1991-01-01
```

**Shipped 2026-08-07 (Phase 3, `implementation_plan.md` 3.1): `income_tax_bracket` and `cpp_parameter`.** Same effective-dated shape as `tax_rate` above, used only by the Phase 3 projection module — they never touch invoice-level tax computation, which stays on `tax_rate` alone.

```sql
CREATE TABLE income_tax_bracket (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  jurisdiction  text NOT NULL,           -- 'federal' or a 2-letter province/territory code
  income_from   numeric(14,2) NOT NULL,
  income_to     numeric(14,2),           -- NULL = top, unbounded bracket
  rate          numeric(7,5) NOT NULL,
  effective_from date NOT NULL,
  effective_to  date,
  source_url    text NOT NULL,
  EXCLUDE USING gist (
    jurisdiction WITH =,
    numrange(income_from, income_to) WITH &&,
    daterange(effective_from, effective_to) WITH &&
  )
);

CREATE TABLE cpp_parameter (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  basic_exemption numeric(12,2) NOT NULL,   -- 3,500.00, unchanged for years
  ympe          numeric(12,2) NOT NULL,     -- year's maximum pensionable earnings (tier 1 ceiling)
  yampe         numeric(12,2) NOT NULL,     -- year's additional maximum pensionable earnings (CPP2 ceiling)
  employee_rate numeric(6,5) NOT NULL,
  self_employed_rate numeric(6,5) NOT NULL, -- 2x employee_rate: both halves
  cpp2_employee_rate numeric(6,5) NOT NULL,
  cpp2_self_employed_rate numeric(6,5) NOT NULL,
  effective_from date NOT NULL,
  effective_to  date,
  source_url    text NOT NULL,
  EXCLUDE USING gist (daterange(effective_from, effective_to) WITH &&)
);
```

**Modelling choice:** the basic personal amount (BPA) is not a separate column or table — it's represented as a synthetic `$0`-to-`BPA` bracket at a `0.00000` rate, prepended to each jurisdiction's real brackets. This is exact, not an approximation: it's mathematically identical to applying the BPA as a credit at the lowest marginal rate, which is how every jurisdiction seeded here actually defines it.

**Coverage:** federal plus the 12 non-Quebec provinces/territories, for 2025 (historical) and 2026 (current, `effective_to` NULL). Quebec is absent — QPP replaces CPP entirely and Quebec runs its own income tax system, out of scope until `implementation_plan.md` 4.4. Every row's `source_url` is the specific per-jurisdiction TaxTips.ca page it was verified against, not one shared URL — cross-checked individually per jurisdiction after an initial batch fetch produced internally inconsistent numbers (rows shuffled between provinces), which is documented in migration `0016_seed_income_tax_cpp.py` as the reason single-page verification was used instead.

Known, deliberate simplifications (all documented once, in the migration, rather than per-row): no federal high-income BPA phase-out band, no provincial surtaxes (Ontario, PEI), Yukon's BPA uses the federal maximum rather than its own income-reduced figure.

Both tables carry the same grant shape as `tax_rate` (§10): `SELECT` only for `tallyquo_app`, no writes from the running API — changes only ever land through a reviewed migration.

---

## 7. Invoices

```sql
CREATE TABLE invoice_sequence (
  tenant_id     uuid NOT NULL,
  scope_key     text NOT NULL,          -- e.g. '2026' when format includes {YYYY}
  next_value    integer NOT NULL DEFAULT 1,
  PRIMARY KEY (tenant_id, scope_key)
);

CREATE TABLE invoice (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  client_id     uuid NOT NULL,
  project_id    uuid,

  number        text,                   -- NULL while draft
  status        invoice_status NOT NULL DEFAULT 'draft',

  invoice_date  date,
  service_period_start date,
  service_period_end   date,
  payment_terms_days smallint,
  due_date      date,

  currency      char(3) NOT NULL,
  fx_rate_to_cad numeric(14,8),         -- NULL when currency = 'CAD'
  fx_rate_date  date,
  fx_rate_source text,

  subtotal      numeric(14,2) NOT NULL DEFAULT 0,
  discount_amount numeric(14,2) NOT NULL DEFAULT 0,
  tax_total     numeric(14,2) NOT NULL DEFAULT 0,
  total         numeric(14,2) NOT NULL DEFAULT 0,
  amount_paid   numeric(14,2) NOT NULL DEFAULT 0,
  total_cad     numeric(14,2),          -- derived, for reporting

  -- frozen at issue; never recomputed
  tax_treatment_snapshot tax_treatment,
  tax_jurisdiction_snapshot text,
  tax_version_id uuid REFERENCES tax_rate_version(id),
  template_id   uuid,
  template_version integer,
  supplier_snapshot jsonb,              -- name, address, BN at time of issue
  client_snapshot   jsonb,              -- name, address at time of issue

  po_reference  text,
  description   text,
  notes         text,
  footer_text   text,

  pdf_ref       text,
  pdf_hash      bytea,

  parent_invoice_id uuid,               -- revision lineage
  revision      smallint NOT NULL DEFAULT 0,

  created_at    timestamptz NOT NULL DEFAULT now(),
  issued_at     timestamptz,
  cancelled_at  timestamptz,
  cancel_reason text,

  UNIQUE (tenant_id, number),
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, client_id) REFERENCES client (tenant_id, id),

  CONSTRAINT issued_has_number CHECK (
    status = 'draft' OR (number IS NOT NULL AND issued_at IS NOT NULL
                         AND invoice_date IS NOT NULL)
  ),
  CONSTRAINT issued_has_snapshot CHECK (
    status = 'draft' OR (tax_treatment_snapshot IS NOT NULL
                         AND tax_version_id IS NOT NULL)
  ),
  CONSTRAINT fx_pair CHECK (
    (currency = 'CAD' AND fx_rate_to_cad IS NULL)
    OR (currency <> 'CAD' AND fx_rate_to_cad IS NOT NULL AND fx_rate_date IS NOT NULL)
  ),
  CONSTRAINT paid_not_over CHECK (amount_paid <= total + 0.01)
);

CREATE INDEX ON invoice (tenant_id, invoice_date DESC);
CREATE INDEX ON invoice (tenant_id, client_id, invoice_date DESC);
CREATE INDEX ON invoice (tenant_id, status) WHERE status IN ('issued','partially_paid','overdue');
```

**Why snapshots are stored as `jsonb` rather than joined.** A user who changes their business address in 2027 must not retroactively alter an invoice sent in 2026. The supplier and client details printed on an issued invoice are historical facts, not live references. The FK to `client` remains for filtering and roll-up; the snapshot is what renders.

```sql
CREATE TABLE invoice_line (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  invoice_id    uuid NOT NULL,
  position      smallint NOT NULL,
  description   text NOT NULL,
  quantity      numeric(12,3) NOT NULL DEFAULT 1,
  unit          line_unit NOT NULL DEFAULT 'fixed',
  unit_rate     numeric(14,2) NOT NULL,
  amount        numeric(14,2) NOT NULL,
  is_taxable    boolean NOT NULL DEFAULT true,
  project_ref   text,
  FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoice (tenant_id, id) ON DELETE CASCADE,
  UNIQUE (invoice_id, position)
);

CREATE TABLE invoice_tax_line (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  invoice_id    uuid NOT NULL,
  tax_type      tax_type,               -- NULL for the "not charged" note case
  label         text NOT NULL,          -- 'HST (ON) — 13%'
  rate          numeric(7,5),           -- NULL when not applicable
  taxable_base  numeric(14,2) NOT NULL,
  amount        numeric(14,2) NOT NULL,
  display_note  text,                   -- 'zero-rated supply' / 'supplier not registered'
  position      smallint NOT NULL,
  FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoice (tenant_id, id) ON DELETE CASCADE
);
```

`invoice_tax_line` is what renders the three variants from the reference template. A zero-rated invoice gets a row with `rate = 0.00000` and `display_note = 'zero-rated supply'`; an unregistered supplier gets a row with `rate = NULL`, `amount = 0`, and `display_note = 'supplier not yet registered'`. Different rows, different meanings, both printing zero.

```sql
CREATE TABLE credit_note (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  invoice_id    uuid NOT NULL,
  number        text NOT NULL,
  amount        numeric(14,2) NOT NULL,
  tax_amount    numeric(14,2) NOT NULL DEFAULT 0,
  currency      char(3) NOT NULL,
  reason        text NOT NULL,
  issued_at     timestamptz NOT NULL DEFAULT now(),
  pdf_ref       text,
  UNIQUE (tenant_id, number),
  FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoice (tenant_id, id)
);

CREATE TABLE payment (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  invoice_id    uuid NOT NULL,
  amount        numeric(14,2) NOT NULL,
  currency      char(3) NOT NULL,
  amount_cad    numeric(14,2),
  fx_rate_to_cad numeric(14,8),
  received_date date NOT NULL,
  method        payment_method,
  reference     text,
  note          text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoice (tenant_id, id)
);
```

FX gain/loss falls out of `payment.amount_cad` differing from the invoice's proportional `total_cad` — recorded, not hidden, because it is reportable income or expense.

---

## 8. Recurring, templates, expenses, time

```sql
CREATE TABLE recurring_rule (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  client_id     uuid NOT NULL,
  source_invoice_id uuid,               -- the shape to copy
  cadence       recurrence_cadence NOT NULL,
  day_of_period smallint,               -- 1..31; clamped, see edgecases.md
  next_run_date date NOT NULL,
  end_date      date,
  occurrences_remaining smallint,
  auto_issue    boolean NOT NULL DEFAULT false,   -- default is draft + notify
  is_paused     boolean NOT NULL DEFAULT false,
  last_run_date date,
  created_at    timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_id) REFERENCES client (tenant_id, id)
);

CREATE TABLE recurring_run (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  rule_id       uuid NOT NULL,
  occurrence_date date NOT NULL,
  invoice_id    uuid,
  outcome       text NOT NULL,          -- created | skipped | failed
  detail        text,
  UNIQUE (rule_id, occurrence_date)     -- idempotency
);

CREATE TABLE template (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid,                   -- NULL = system template
  name          text NOT NULL,
  schema_version integer NOT NULL,
  version       integer NOT NULL DEFAULT 1,
  theme         jsonb NOT NULL,         -- design tokens, see design.md
  blocks        jsonb NOT NULL,         -- ordered block descriptors
  is_system     boolean NOT NULL DEFAULT false,
  is_default    boolean NOT NULL DEFAULT false,
  archived_at   timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE template_version_history (
  template_id   uuid NOT NULL,
  version       integer NOT NULL,
  theme         jsonb NOT NULL,
  blocks        jsonb NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (template_id, version)
);
```

Template versions are retained because issued invoices pin `(template_id, template_version)`. Editing a template must never change how an already-issued invoice re-renders.

```sql
CREATE TABLE expense_category (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid,                   -- NULL = system category
  name          text NOT NULL,
  t2125_line    text,                   -- '8521' advertising, '8523' meals, ...
  deductible_pct numeric(5,2) NOT NULL DEFAULT 100.00,  -- meals = 50.00
  is_capital    boolean NOT NULL DEFAULT false,
  cca_class     text,
  archived_at   timestamptz
);

CREATE TABLE expense (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  expense_date  date NOT NULL,
  vendor        text,
  description   text,
  category_id   uuid REFERENCES expense_category(id),
  currency      char(3) NOT NULL,
  amount_total  numeric(14,2) NOT NULL,   -- as printed on the receipt
  tax_amount    numeric(14,2) NOT NULL DEFAULT 0,
  tax_type      tax_type,
  amount_net    numeric(14,2) NOT NULL,   -- total - tax
  fx_rate_to_cad numeric(14,8),
  amount_cad    numeric(14,2),
  business_use_pct numeric(5,2) NOT NULL DEFAULT 100.00,
  itc_eligible  boolean NOT NULL DEFAULT false,  -- false unless registered
  client_id     uuid,                    -- billable/rebillable
  is_rebilled   boolean NOT NULL DEFAULT false,
  rebilled_invoice_id uuid,
  payment_method payment_method,
  source        expense_source NOT NULL DEFAULT 'manual',
  ocr_confidence numeric(4,3),
  ocr_raw       jsonb,
  created_at    timestamptz NOT NULL DEFAULT now(),
  deleted_at    timestamptz,
  CONSTRAINT amounts_consistent CHECK (
    abs(amount_net + tax_amount - amount_total) < 0.02
  )
);
CREATE INDEX ON expense (tenant_id, expense_date DESC) WHERE deleted_at IS NULL;

CREATE TABLE receipt (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  expense_id    uuid,                   -- nullable: receipt uploaded first
  file_ref      text NOT NULL,
  file_hash     bytea NOT NULL,
  mime_type     text NOT NULL,
  byte_size     integer NOT NULL,
  page_count    smallint,
  uploaded_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, file_hash)         -- dedupe re-uploads
);

CREATE TABLE time_entry (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  client_id     uuid NOT NULL,
  project_id    uuid,
  entry_date    date NOT NULL,
  hours         numeric(6,2) NOT NULL,
  description   text,
  rate          numeric(14,2),
  invoice_id    uuid,                   -- set when billed; locks the entry
  created_at    timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_id) REFERENCES client (tenant_id, id)
);
CREATE INDEX ON time_entry (tenant_id, client_id, entry_date)
  WHERE invoice_id IS NULL;
```

`itc_eligible` defaults to `false` and is set true only when the business profile was registered on the expense date. This is the downstream consequence of §2's distinction between zero-rated and unregistered: get the treatment enum wrong and every input tax credit in the system is wrong too.

---

## 9. Cross-tenant referential integrity

Standard single-column foreign keys permit a bug to link tenant A's invoice to tenant B's client. Composite keys make that impossible:

```sql
ALTER TABLE client   ADD UNIQUE (tenant_id, id);
ALTER TABLE invoice  ADD UNIQUE (tenant_id, id);
ALTER TABLE project  ADD UNIQUE (tenant_id, id);

ALTER TABLE invoice
  ADD FOREIGN KEY (tenant_id, client_id) REFERENCES client (tenant_id, id);
```

The redundant `UNIQUE (tenant_id, id)` alongside the primary key is the price of this guarantee, and it is cheap. Combined with RLS it means a cross-tenant reference is rejected by the database even if the application constructs one.

---

## 10. Row-level security

```sql
ALTER TABLE invoice ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON invoice
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
```

Applied identically to every tenant-scoped table. Points that matter:

- `FORCE` ensures the policy applies even to the table owner.
- The application role must **not** have `BYPASSRLS`.
- `WITH CHECK` prevents writing a row belonging to another tenant, not just reading one.
- `current_setting('app.tenant_id')` with no fallback: if the middleware fails to set it, queries error rather than returning everything. Fail closed.
- Global tables (`tax_rate`, `tax_rate_version`, `tax_threshold`, system `template` and `expense_category` rows) are read-only to the app role and exempt from RLS.

---

## 11. Audit log

```sql
CREATE TABLE audit_log (
  id            bigserial PRIMARY KEY,
  tenant_id     uuid NOT NULL,
  actor_user_id uuid,
  actor_kind    text NOT NULL,          -- user | job | system
  action        text NOT NULL,          -- invoice.issued, client.tax_treatment_changed
  entity_type   text NOT NULL,
  entity_id     uuid NOT NULL,
  before        jsonb,
  after         jsonb,
  request_id    text,
  ip_hash       bytea,
  occurred_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON audit_log (tenant_id, entity_type, entity_id, occurred_at DESC);

REVOKE UPDATE, DELETE ON audit_log FROM app_role;   -- append-only
```

Written in the same transaction as the mutation, so a rolled-back change leaves no audit entry and a committed change always has one.

---

## 12. Derived and materialized data

```sql
CREATE MATERIALIZED VIEW mv_period_summary AS
SELECT tenant_id, client_id,
       date_trunc('month', invoice_date)::date AS period,
       count(*) FILTER (WHERE status <> 'cancelled')       AS invoice_count,
       sum(total_cad) FILTER (WHERE status <> 'cancelled') AS billed_cad,
       sum(tax_total) FILTER (WHERE status <> 'cancelled') AS tax_collected_cad,
       sum(amount_paid)                                    AS collected_cad
FROM invoice
WHERE status <> 'draft'
GROUP BY 1,2,3;
```

Refreshed on invoice mutation, debounced. Powers the client roll-up view and the P&L.

**As built (2026-08-07): live queries, not this materialized view.** `REFRESH MATERIALIZED VIEW CONCURRENTLY` can't run inside the RLS-scoped per-request transaction (`SET LOCAL app.tenant_id` requires an open transaction; `CONCURRENTLY` forbids one), and a debounced refresh risks showing an outstanding balance that's already been paid — the wrong kind of stale read in a financial product. `billing_cad`/`collected_cad` are computed with a live `GROUP BY` over `invoice.total_cad` and `payment.amount_cad` instead, excluding rows without a CAD figure (an FX fetch failure at issue) rather than falling back to a native-currency amount as if it were CAD. Cheap at the invoice volumes this product targets (a single sole proprietor); revisit if that changes.

**Small supplier threshold** is computed, not stored — a rolling sum over the last four complete calendar quarters of `total_cad` for invoices whose treatment is `taxable` **or** `zero_rated_export`, excluding `exempt`. The inclusion of zero-rated exports is the part users get wrong; encoding it here means the product warns them before the CRA does.

---

## 13. Invariants

These should be enforced by constraint where possible, and by the nightly integrity job where not. Each has a corresponding test.

| # | Invariant |
|---|---|
| I1 | Every row in a tenant-scoped table has a `tenant_id` matching the session context |
| I2 | An `issued` invoice has a number, invoice date, tax snapshot, and version pin |
| I3 | Invoice numbers are unique and gapless per `(tenant_id, scope_key)` |
| I4 | An issued invoice's financial fields never change after `issued_at` |
| I5 | `sum(invoice_line.amount) - discount = subtotal`; `subtotal + tax_total = total` |
| I6 | `sum(invoice_tax_line.amount) = tax_total` |
| I7 | Recomputing tax from the frozen snapshot reproduces the stored `tax_total` exactly |
| I8 | `amount_paid ≤ total` (tolerance 0.01); overpayment requires an explicit credit |
| I9 | No two `tax_rate` rows overlap for the same jurisdiction and type (DB-enforced) |
| I10 | A non-CAD invoice has both `fx_rate_to_cad` and `fx_rate_date` |
| I11 | `itc_eligible` is true only if the profile was `registered` on the expense date |
| I12 | Every FK crossing tenant-scoped tables is composite on `(tenant_id, id)` |
| I13 | No financial row is ever hard-deleted while the tenant is active |

---

## 14. Retention and deletion

- **Financial records** (invoices, credit notes, payments, expenses, receipts, audit log) are retained a minimum of 7 years, exceeding CRA's general 6-year expectation.
- **Soft delete only** for expenses and drafts. Issued invoices cannot be deleted at all — only cancelled, which preserves the number and the record.
- **OTP codes** purged after 24 hours; sessions after expiry plus 30 days.
- **Tenant closure**: account is marked closed, a full export is generated and made available for 90 days, and financial data is retained for the statutory period rather than erased. This must be stated plainly in the terms — a user asking for deletion of records they are legally obliged to keep needs to understand the conflict, and the product should offer export-then-close rather than a silent erase.
- **Export before delete** is always offered, never optional to implement.
