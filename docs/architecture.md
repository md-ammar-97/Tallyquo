# Architecture

**Companion to:** `problem-statement.md`
**Status:** Draft v0.1
**Scope:** Phases 1–3. Phase 4 items marked `[P4]`.

---

## 1. Architectural principles

These are the constraints every decision below is derived from. When a trade-off appears, resolve it in this order.

1. **Isolation is enforced by the database, not the application.** The app layer will have bugs. The database must not let them become a breach.
2. **Financial records are append-only.** Issued invoices, tax snapshots, and audit entries are never updated in place. Corrections are new rows.
3. **Tax rates are data with a lifetime, not constants.** Every computed tax figure is reproducible from `(invoice_date, jurisdiction, rate_table_version)`.
4. **Boring, single-region, modular monolith.** A one-person-business product with month-end spikes does not need microservices. It needs correctness and cheap operations.
5. **Every generated artifact is deterministic.** The same invoice re-rendered in two years must be byte-identical.

---

## 2. System context

```
┌──────────────┐        ┌──────────────┐        ┌──────────────┐
│  Web app     │        │  Mobile web  │        │  Email       │
│  (React SPA) │        │  (PWA, P2)   │        │  (OTP, docs) │
└──────┬───────┘        └──────┬───────┘        └──────▲───────┘
       │                       │                       │
       └───────────┬───────────┘                       │
                   │ HTTPS / JSON                      │
          ┌────────▼─────────────────────────────┐     │
          │           API Gateway / BFF          │     │
          │   auth · rate limit · tenant context │     │
          └────────┬─────────────────────────────┘     │
                   │                                   │
   ┌───────────────┼───────────────┬──────────────┐    │
   │               │               │              │    │
┌──▼────────┐ ┌────▼──────┐ ┌──────▼─────┐ ┌──────▼────┴──┐
│ Core API  │ │ Tax       │ │ Render     │ │ Notification │
│ (modular  │ │ Engine    │ │ Service    │ │ Service      │
│  monolith)│ │ (in-proc  │ │ (PDF)      │ │ (email)      │
└──┬────────┘ │  library) │ └──────┬─────┘ └──────────────┘
   │          └───────────┘        │
   │                               │
┌──▼──────────────┐  ┌─────────────▼───┐  ┌──────────────────┐
│  PostgreSQL     │  │  Object Storage │  │  Job Queue       │
│  (RLS enforced) │  │  (logos, PDFs,  │  │  (recurring,     │
│                 │  │   receipts)     │  │   OCR, reminders)│
└─────────────────┘  └─────────────────┘  └──────────────────┘
                              │
                     ┌────────▼────────┐   ┌──────────────────┐
                     │  OCR Provider   │   │  Rate Monitor    │
                     │  (receipts, P2) │   │  (scheduled)     │
                     └─────────────────┘   └──────────────────┘
```

**External dependencies (deliberately few):**

| Dependency | Purpose | Failure mode | Mitigation |
|---|---|---|---|
| Transactional email | OTP delivery only | User cannot log in | Second provider on standby; OTP is the only critical path |
| User-configured SMTP *(shipped 2026-08-07)* | Invoice delivery — **not a platform-level provider**. Each tenant connects their own mail server; there is no shared sending identity to authenticate | One tenant's outgoing mail breaks | Isolated per tenant by construction; a failure never affects another tenant or any other feature. See `datamodel.md` §4, `edgecases.md` §8 |
| Object storage | Logos, receipts, generated PDFs | Cannot render or retrieve | Regenerate PDFs from stored invoice data (source of truth is the DB, not the file) |
| OCR provider — **Groq (`qwen/qwen3.6-27b`, free tier)** | Receipt extraction | Degrades to manual entry | Always allow manual entry; OCR is an accelerator, never a gate |
| Bank of Canada Valet API | Daily rate for USD invoices. Free, public, no key | Cannot compute CAD equivalent | Cache last known rate, flag invoice for review, never block issuing |
| Rate sources (CRA, provincial) | Tax rate change detection | Stale rates | Human-reviewed pipeline; rates change rarely and are announced in advance |

---

## 3. Technology decisions

Recorded ADR-style: decision, reasoning, and what would make us revisit.

### ADR-001 — PostgreSQL with row-level security as the isolation boundary
**Decision.** Single Postgres cluster, single logical database, shared schema, `tenant_id` on every tenant-scoped table, RLS policies enabled and `FORCE`d on all of them. The application connects as a role that has no `BYPASSRLS`.

**Reasoning.** Schema-per-tenant and database-per-tenant both scale badly at the migration layer for a product expected to have thousands of small tenants. RLS gives us defence in depth at the layer that cannot be bypassed by an ORM mistake, a forgotten `WHERE` clause, or a raw query in a reporting endpoint.

**Revisit if.** A single tenant's data volume becomes atypical (unlikely for this persona), or a regulatory requirement demands physical separation.

### ADR-002 — Modular monolith, not microservices
**Decision.** One deployable API with enforced internal module boundaries: `identity`, `billing` (invoices/clients), `tax`, `expenses`, `templates`, `reporting`, `notifications`. Modules communicate through explicit interfaces, not by reaching into each other's tables.

**Reasoning.** The team is small, transactions cross module boundaries constantly (issuing an invoice touches numbering, tax, rendering, and audit atomically), and the load profile is spiky but small. Distributed transactions would be pure cost.

**Revisit if.** Rendering or OCR volume justifies independent scaling — both are already carved out as separate processes below, which is the natural first split.

### ADR-003 — Tax engine as an in-process, pure library
**Decision.** The tax engine is a deterministic pure function with no I/O:
`compute(supply_context, rate_table_snapshot) → tax_result`. Rate loading happens outside it.

**Reasoning.** Purity makes it exhaustively unit-testable, which is exactly what a component with existential correctness risk needs. It also makes historical reproduction trivial: feed it the archived table version and the original context, get the original answer.

**Revisit if.** Never, ideally. If the engine ever needs a network call to produce a number, something has gone wrong.

### ADR-004 — Server-side deterministic PDF rendering
**Decision.** Rendering runs in a separate process (headless browser or a typesetting engine) with pinned fonts, pinned engine version, no network access at render time, and no client-side generation.

**Reasoning.** Client-side PDF generation produces different output on different devices, which is unacceptable for a legal document. Deterministic rendering means an invoice re-rendered in 2033 matches the one the client received in 2026. Font embedding is mandatory — a font substitution changes line breaks, which changes pagination.

**Revisit if.** Never for issued invoices. Draft previews may render client-side for speed.

### ADR-005 — Object storage is a cache, the database is the truth
**Decision.** Generated PDFs are stored, but the canonical record is the invoice row plus its frozen snapshot. Any PDF can be regenerated. Receipts and logos are the exception — those are user-supplied originals and are irreplaceable.

**Reasoning.** Separates "things we can rebuild" from "things we must never lose," which gives two different backup and retention policies rather than one expensive one.

### ADR-006 — OTP-only authentication, no passwords
**Decision.** Email + 6-digit OTP. No password storage at all. Sessions issued as opaque refresh tokens with short-lived access tokens.

**Reasoning.** The user's requirement, and independently the right call: no password database means no password breach, no reset flow, no credential stuffing. The cost is dependence on email deliverability, which is why the email provider gets a standby.

**Revisit if.** Users report OTP friction at a rate that hurts activation. The escape hatch is passkeys, not passwords.

---

## 4. Request lifecycle and tenant context

Every authenticated request follows the same path. There are no exceptions, including internal jobs.

```
1. Ingress          TLS terminated, request ID assigned
2. Rate limit       per IP, per email, per tenant, per route class
3. Authenticate     access token verified → session → tenant_id, user_id
4. Open transaction BEGIN
5. Set context      SET LOCAL app.tenant_id = '<uuid>'
                    SET LOCAL app.actor_id  = '<uuid>'
6. Handle           all queries now filtered by RLS automatically
7. Audit            mutations append to audit_log within the same transaction
8. Commit           COMMIT (or ROLLBACK — audit rolls back with the change)
```

**Critical rule:** step 5 is performed by shared middleware and is the *only* place `app.tenant_id` is ever set. Background jobs run through the same middleware with an explicit tenant context loaded from the job payload. A job that cannot establish a tenant context fails rather than running unscoped.

**Cross-tenant test gate.** CI runs an adversarial suite that, for every route, authenticates as tenant A and requests tenant B's resource IDs. Any response that is not 404 fails the build. This runs on every pull request, not nightly.

---

## 5. Authentication flow

```
POST /auth/request-otp  { email }
  → normalize email (lowercase, strip dots for known providers? NO — see edgecases.md)
  → rate limit: 3/15min per email, 10/hour per IP
  → generate 6-digit code, cryptographically random
  → store hash(code) + expires_at (10 min) + attempt_count
  → send email
  → ALWAYS return 200 with the same body (no account enumeration)

POST /auth/verify-otp  { email, code }
  → constant-time compare against hash
  → max 5 attempts per code, then invalidate
  → on success: invalidate code, create session, issue tokens
  → if email unknown: create tenant + user atomically (signup == login)

POST /auth/refresh     { refresh_token }
  → rotate refresh token on every use (detect replay → revoke family)

POST /auth/logout      revoke this session
GET  /auth/sessions    list active devices
DELETE /auth/sessions/:id  revoke one
```

**Signup and login are the same flow.** There is no separate registration. First successful OTP for an unknown email provisions the tenant. This removes an entire class of onboarding drop-off.

**Email change** is a two-sided flow: OTP to the current address to authorize, then OTP to the new address to confirm. Until both complete, the old address remains authoritative. The tenant ID never changes.

---

## 6. Invoice issuance — the critical transaction

Issuing is the one operation where correctness matters more than everything else. It is a single database transaction with no external calls inside it.

```
BEGIN
  1. Load invoice (draft), lock row
  2. Validate compliance checklist — reject with field-level errors if incomplete
  3. Load client tax treatment + resolved jurisdiction
  4. Load active rate table version for invoice_date
  5. tax_result = TaxEngine.compute(supply_context, rate_snapshot)   [pure, no I/O]
  6. Allocate invoice number from per-tenant sequence
       SELECT ... FROM invoice_sequence WHERE tenant_id = $1 FOR UPDATE
       (serializes concurrent issues within a tenant — the contention is one
        user clicking twice, so this is free)
  7. Write frozen snapshot:
       tax_table_version, treatment, jurisdiction, rates applied,
       fx_rate + fx_date if applicable, template_id + template_version
  8. Transition status draft → issued, set issued_at
  9. Append audit_log entry
COMMIT

AFTER COMMIT (async, idempotent, retryable):
  10. Enqueue PDF render job
  11. Enqueue delivery job [P2, only if user opted to send]
```

**Why numbering is allocated at issue, not at draft creation.** Drafts get abandoned. If numbers were allocated at creation, the sequence would develop gaps, and a gapped invoice sequence is the first thing an auditor asks about. Allocating at issue makes the sequence gapless by construction.

**Why the render is outside the transaction.** Rendering takes seconds and can fail. The legal record is the row; the PDF is a derived artifact. An invoice is issued the moment the transaction commits, whether or not the PDF exists yet. The UI shows "preparing document" rather than blocking the issue action.

---

## 7. Tax engine

```
                 ┌──────────────────────────────────────┐
  supply_context │ supplier_registration_status         │
                 │ supplier_registration_effective_date │
                 │ recipient_country, recipient_region  │
                 │ recipient_is_gst_registered          │
                 │ recipient_non_residency_evidence     │
                 │ supply_type (service | ipp | goods)  │
                 │ invoice_date                         │
                 │ line_items[]                         │
                 └──────────────┬───────────────────────┘
                                │
                 ┌──────────────▼───────────────────────┐
                 │  resolve_treatment()                 │
                 │   → NOT_REGISTERED                   │
                 │   → TAXABLE (rate from jurisdiction) │
                 │   → ZERO_RATED_EXPORT                │
                 │   → EXEMPT                           │
                 └──────────────┬───────────────────────┘
                                │
                 ┌──────────────▼───────────────────────┐
                 │  resolve_jurisdiction()              │
                 │   place of supply = RECIPIENT's      │
                 │   province, not supplier's           │
                 └──────────────┬───────────────────────┘
                                │
                 ┌──────────────▼───────────────────────┐
                 │  apply_rates(rate_table @ inv_date)  │
                 │   HST single line                    │
                 │   GST + PST/QST/RST as separate      │
                 │   lines, each on the pre-tax amount  │
                 └──────────────┬───────────────────────┘
                                │
                 ┌──────────────▼───────────────────────┐
                 │  tax_result                          │
                 │   lines[] {type, label, rate, amount}│
                 │   display_note (for 0% cases)        │
                 │   warnings[]                         │
                 │   table_version                      │
                 └──────────────────────────────────────┘
```

**Rate table update pipeline** — deliberately not fully automated:

```
Scheduled crawler (weekly)
  → fetch known rate pages (CRA + 13 provincial/territorial finance sites)
  → normalize + diff against current active table
  → no change: log and exit
  → change detected: open a review ticket with the diff and source URLs,
    alert the named owner (see problem-statement.md Q9)
  → human reviews against the primary source
  → approve → INSERT new row with effective_from
              UPDATE previous row SET effective_to
  → publish → in-app notice to tenants with clients in that jurisdiction
```

A crawler must never write to `tax_rate`. The failure mode of a bad automated write is wrong tax on real invoices, which is the one thing we said is existential.

**Reproducibility test.** A nightly job re-computes every issued invoice from its frozen snapshot and compares to the stored figures. Any mismatch is a P1 alert — it means either a snapshot is corrupt or the engine changed behaviour for historical input.

---

## 8. Rendering pipeline

```
render_job(invoice_id)
  1. Load invoice + lines + client + business profile + template (pinned version)
  2. Compose a render document (structured JSON, no user HTML)
  3. Render in isolated process:
       - no network, no filesystem write outside temp
       - fonts bundled and embedded in output
       - fixed timezone (business profile TZ), fixed locale
       - PDF/A-conformant where practical for archival
  4. Compute content hash → store PDF at tenant_id/invoices/{id}/{hash}.pdf
  5. Record pdf_ref + hash on the invoice
```

**Determinism requirements:** no `now()` in templates, no remote images (the logo is fetched from storage and inlined before render), pinned renderer version recorded alongside the output, and no CSS that depends on system font metrics.

**Templates never execute user code.** A template is `{theme_tokens, block_layout[], locked_compliance_block}`. The renderer maps block types to built-in components. There is no HTML injection surface because there is no HTML input.

---

## 9. Background jobs

| Job | Trigger | Idempotency key | Notes |
|---|---|---|---|
| `render_invoice` | After issue | invoice_id + template_version | Retry with backoff; regenerable at any time |
| `generate_recurring` | **Hourly** (GitHub Actions schedule) | rule_id + occurrence_date | Creates a **draft**, notifies user. Auto-issue only if opted in. Hourly rather than once daily so generation lands close to each tenant's own local midnight without needing per-tenant-timezone scheduling (R11) |
| `ocr_receipt` | **Inline with the upload request, not a separate async job** | file_hash | Failure → manual entry, never blocks the expense. Groq's response time is low enough that this didn't need queueing; revisit if that changes |
| `payment_reminder` `[P2, not built]` | Daily | invoice_id + reminder_stage | Skipped if invoice paid or cancelled since scheduling. Blocked on the SMTP email feature (`datamodel.md` §4) — a reminder needs a delivery channel |
| `rate_crawl` | Weekly | crawl_date | Produces review tickets only |
| `snapshot_verify` | Nightly (GitHub Actions schedule, 08:00 UTC) | invoice_id + date | Recompute-and-compare integrity check |
| `projection_refresh` | On invoice/expense mutation, debounced | tenant_id + period | Materializes the projection view |
| `retention_sweep` | Monthly | — | Enforces retention policy, never hard-deletes financial records |

**As built:** `generate_recurring` and `snapshot_verify` run as scheduled GitHub Actions workflows invoking the job function directly against the live database, not as workers pulling from the persistent "Job Queue" component shown in §2's diagram — that component isn't built. Simpler, and sufficient at the invoice volumes this product targets; revisit if job volume or latency requirements ever justify a real queue.

All jobs are idempotent, run inside a tenant context, and record their outcome to the audit log where they mutate financial data.

---

## 10. API surface (shape, not exhaustive)

```
POST   /auth/request-otp | /auth/verify-otp | /auth/refresh | /auth/logout
GET    /auth/sessions          DELETE /auth/sessions/:id

GET    /profile                PATCH  /profile
POST   /profile/logo           PATCH  /profile/registration

GET    /clients                POST   /clients
GET    /clients/:id            PATCH  /clients/:id
POST   /clients/:id/evidence   (non-residency documentation)
GET    /clients/:id/summary    (period roll-up)

GET    /invoices               ?from&to&client&status&min&max&currency&treatment
POST   /invoices               (draft)
PATCH  /invoices/:id           (draft only — 409 if issued)
POST   /invoices/:id/issue     (the critical transaction)
POST   /invoices/:id/cancel
POST   /invoices/:id/credit-note
POST   /invoices/:id/payments  GET  /invoices/:id/payments
DELETE /invoices/payments/:id  (reversal, with a reason — L12)
GET    /invoices/:id/pdf       (signed URL redirect)
POST   /invoices/preview-tax   (dry run, no persistence — powers live preview)

POST   /invoices/:id/share     (get-or-create a public link — 409 if still a draft)
DELETE /invoices/:id/share     (revoke; regenerating after issues a genuinely new token)
GET    /public/invoices/:token             (no auth — resolves token -> tenant, edgecases.md §2 bootstrap pattern)
GET    /public/invoices/:token/pdf         (no auth)

POST   /invoices/:id/email     *(shipped 2026-08-07)* — the compose window's Send action;
                                 recipients/subject/body/attachments are all caller-supplied,
                                 never defaulted server-side, and the send is always a direct
                                 result of this one explicit call, never scheduled or implicit
                                 (`edgecases.md` §8, O1). Draft invoices are rejected (409).
GET    /invoices/:id/email-log *(shipped 2026-08-07)* — append-only send history for one invoice

GET    /email-accounts         POST /email-accounts          *(shipped 2026-08-07)*
POST   /email-accounts/:id/verify   DELETE /email-accounts/:id *(shipped 2026-08-07)*
                                 user-configured SMTP, `datamodel.md` §4. verify connects and
                                 authenticates only — no message sent, no password ever returned

GET    /recurring              POST /recurring
PATCH  /recurring/:id          POST /recurring/:id/skip

GET    /expenses               POST /expenses
POST   /expenses/receipt       (upload first, expense created from it)
PATCH  /expenses/:id

GET    /templates              POST /templates
POST   /templates/import       GET  /templates/:id/export

GET    /reports/pnl            ?period

GET    /projection             ?year  *(shipped 2026-08-08)* — set-aside (federal +
                                 provincial income tax, CPP), quarterly GST/HST
                                 net-owing, small-supplier threshold, and the
                                 instalment warning, all in one response rather
                                 than the three separate /reports/projection,
                                 /reports/gst-position, /reports/threshold
                                 endpoints originally sketched here — one
                                 dashboard load, one round trip
                                 (implementation_plan.md 3.2-3.9)
PUT    /projection/declared-income     *(shipped 2026-08-08)* — declared-income mode
DELETE /projection/declared-income/:year *(shipped 2026-08-08)* — revert to derived

POST   /exports/year-end       ?year  *(shipped 2026-08-08)* — invoice PDFs +
                                 expenses.csv (T2125-mapped) + receipt images +
                                 gst_hst_summary.csv + profit_and_loss.csv + a
                                 README, zipped and returned as a signed URL
                                 (7-day TTL, see §11). Built synchronously
                                 within the request rather than as a queued
                                 job — same reasoning as 3.10: at these data
                                 volumes it's a sub-second-to-few-second
                                 operation, not something needing a queue
                                 this product doesn't otherwise have
                                 (implementation_plan.md 3.11)
GET    /exports/all            (full data export, no lock-in)
```

**Response conventions:** resources not belonging to the caller's tenant return `404`, never `403` — a `403` confirms existence. Validation errors are field-scoped so the invoice builder can highlight in place.

---

## 11. Storage layout and access

```
s3://bucket/
  {tenant_id}/
    logo/{hash}.{ext}
    invoices/{invoice_id}/{content_hash}.pdf
    receipts/{expense_id}/{content_hash}.{ext}
    evidence/{client_id}/{content_hash}.{ext}
    year-end-packs/{year}-{uuid}.zip  (TTL 7 days -- shipped 2026-08-08, implementation_plan.md 3.11)
```

- No public objects. Ever.
- Access exclusively via signed URLs, TTL ≤ 5 minutes, generated only after the API has verified tenant ownership of the underlying row. **One deliberate exception**: the year-end accountant pack's link is valid 7 days — it's meant to be handed to (or re-downloaded by) an accountant over the following days, not fetched once immediately after the API call that created it. Every other signed URL in this product still uses the 5-minute default.
- Uploads go through the API (which validates MIME type by magic bytes, not extension, enforces size caps, and strips EXIF from images) rather than direct-to-bucket, so that ownership is established before the object exists.
- Content-addressed filenames deduplicate re-uploads and make integrity verification trivial.

---

## 12. Security posture

| Control | Implementation |
|---|---|
| Tenant isolation | Postgres RLS `FORCE`d; app role without `BYPASSRLS`; CI adversarial suite |
| Transport | TLS 1.3, HSTS, secure + httpOnly + sameSite cookies for refresh token |
| At rest | Volume encryption; column encryption for banking fields in payment instructions |
| OTP | Hashed at rest, 10-min TTL, single use, 5-attempt cap, constant-time compare, per-email and per-IP rate limits |
| Session | Rotating refresh tokens, replay detection revokes the token family, device list visible to user |
| Uploads | Magic-byte type validation, size caps, EXIF stripping, malware scan before the file becomes retrievable |
| Injection | No user-authored HTML/CSS/JS anywhere in the template system; parameterized queries only |
| PII in logs | Structured logging with an allowlist; email addresses hashed in logs; no invoice amounts in application logs |
| Audit | Append-only `audit_log`, written in the same transaction as the mutation |
| Secrets | Managed secret store, no secrets in environment files in the repo |
| Data residency | Canadian region for both database and object storage — confirm before vendor selection |

---

## 13. Observability

**Business-correctness signals matter more than infrastructure ones here.** Standard latency and error dashboards are table stakes; these are the alerts that indicate the product is doing damage:

- `tax_snapshot_mismatch` — nightly verification failure. **P1.**
- `invoice_sequence_gap` — a gap appeared in a tenant's numbering. **P1.**
- `cross_tenant_denied` — RLS blocked a query the app tried to run. Should be zero. Non-zero means an application bug reached production. **P1.**
- `rate_table_stale` — no successful crawl in 14 days. **P2.**
- `void_within_7_days` — rising rate means users are issuing wrong invoices. Product signal, not an alert.
- `otp_delivery_latency_p95` — above 30s, users start abandoning login.
- `render_failure_rate` — invoices issued without a retrievable PDF.

Every log line carries `request_id` and `tenant_id`. Traces span the issue → render → deliver chain.

---

## 14. Environments and delivery

- **Local → staging → production.** Staging holds synthetic tenants only; no production data is ever copied down, because this is financial data and there is no safe anonymization of an invoice.
- **Migrations** are forward-only and backward-compatible for one release (expand → migrate → contract), so a rollback never strands the schema.
- **Rate table changes are deployed as data, not code**, through the reviewed pipeline — decoupled from application releases entirely.
- **Feature flags** per tenant for phased rollout of the projection and expense modules.
- **Backups:** point-in-time recovery on the database; versioned, cross-region-replicated object storage. Restore drills quarterly — an untested backup is not a backup.

---

## 15. Scaling notes

The load profile is unusual and worth designing to: near-flat for 25 days, then a sharp spike in the last three and first two days of each month, when everyone invoices.

- Render workers autoscale on queue depth; this is the only component that spikes hard.
- Read replicas for reporting queries once the ledger view gets slow; the projection is materialized rather than computed per request.
- Recurring generation is spread across the day by tenant timezone rather than firing at a single UTC hour.
- Everything else — a few thousand tenants with a few hundred rows each — fits comfortably on a single modest Postgres instance for a long time. Resist premature partitioning.

---

## 16. What is deliberately not here

- No event sourcing. The audit log plus immutable issued records gives the same guarantees at a fraction of the complexity.
- No CQRS. One materialized projection view is the entire read-model requirement.
- No message broker beyond a job queue. There are no cross-service events to publish.
- No caching layer in Phase 1. The data is small and per-tenant; the database is the cache.
- No bank connection. Deliberate — see `problem-statement.md` N4 and Q2.
