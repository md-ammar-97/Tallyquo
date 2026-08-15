# Implementation Plan

**Companion to:** `problem-statement.md`, `architecture.md`, `datamodel.md`, `design.md`, `edgecases.md`
**Status:** Draft v0.1
**Purpose:** Turn the four phases in `problem-statement.md` §10 into ordered, dependency-aware engineering workstreams, with explicit exit criteria and the edge-case IDs (`edgecases.md`) each workstream must close before the phase can ship.

This document does not re-derive product decisions already made in the other docs — it sequences the work. Where a phase's scope is ambiguous because an open question in `problem-statement.md` §12 is still unresolved, that is called out explicitly rather than silently assumed.

---

## 0. How to read this plan

- **Sizing tags** (`S` / `M` / `L` / `XL`) are relative complexity, not calendar time — nobody has estimated velocity yet. Use them to sequence and to spot the workstreams worth de-risking early.
- **P1 edge case IDs** (e.g. `X1`, `T2`) reference the numbered rows in `edgecases.md`. A phase is not done while any P1 in its scope is red.
- **"Depends on"** lines are hard sequencing constraints — building out of order re-does work.
- Nothing here overrides `problem-statement.md` §4 non-goals (N1–N7). If a task in this plan appears to reintroduce one of them, that's a bug in the plan, not a scope decision.

---

## 1. Sequencing overview

| Phase | Theme | Ship criterion |
|---|---|---|
| **0** | Foundations | A tenant-isolated, empty modular monolith exists with CI enforcing the adversarial cross-tenant gate on every PR |
| **1** | Correct invoices, nothing else | A contractor with an Ontario client and a US client can produce two correctly-taxed invoices without reading documentation |
| **2** | The record | Payments, expenses, recurring billing, and multi-currency all roll up into a trustworthy per-client and per-period history |
| **3** | The answer | The user can open one screen and know what to set aside, without it being phrased as advice |
| **4** | The ecosystem | Templates, integrations, and Quebec/French support extend reach without touching the tax-correctness core |

Phase 0 is not in the source phasing table but is split out here because none of Phase 1's product features are safe to build on an unproven tenancy boundary — isolation is the one thing that must be right before anything else is written (`architecture.md` principle 1).

---

## 2. Phase 0 — Foundations *(new — precedes the source doc's Phase 1)*

**Goal:** prove the isolation boundary and delivery pipeline before any product code exists on top of it.

| # | Workstream | Depends on | Size |
|---|---|---|---|
| 0.1 | Repo scaffold as a modular monolith: `identity`, `billing`, `tax`, `expenses`, `templates`, `reporting`, `notifications` module boundaries per ADR-002, even though most are empty | — | M |
| 0.2 | Postgres provisioning + migration tool; `tenant`, `app_user`, `session`, `otp_code` tables (`datamodel.md` §3) | 0.1 | S |
| 0.3 | RLS scaffolding: app DB role with **no `BYPASSRLS`**, `SET LOCAL app.tenant_id` middleware wired into the request lifecycle exactly per `architecture.md` §4, fail-closed (`current_setting` with no default) | 0.2 | M |
| 0.4 | Composite-FK convention established from the first migration: every tenant-scoped table gets `UNIQUE (tenant_id, id)`; document it as a lint rule, not tribal knowledge (`datamodel.md` §9) | 0.2 | S |
| 0.5 | CI adversarial cross-tenant test harness: authenticate as tenant A, request tenant B's resource IDs, assert `404` on every route — wired as a **merge gate**, not a nightly job | 0.3 | M |
| 0.6 | Object storage bucket, `{tenant_id}/` prefix convention, signed-URL helper (TTL ≤ 5 min), upload-through-API pattern (magic-byte MIME validation, size caps, EXIF strip) — `architecture.md` §11 | 0.1 | M |
| 0.7 | Observability skeleton: `request_id` + `tenant_id` on every log line; alert scaffolding for the four P1 signals even before there's volume to trigger them: `cross_tenant_denied`, `invoice_sequence_gap`, `tax_snapshot_mismatch`, `render_failure_rate` | 0.3 | S |
| 0.8 | Environments: local → staging → production; staging seeded with synthetic tenants only, **never** production data (`architecture.md` §14) | 0.1 | S |
| 0.9 | **Decision gate:** data residency (Canadian region) confirmed before vendor selection for DB, storage, and email — this blocks 0.2, 0.6, and any provider contract | — | Decision |

**Exit criteria:** `T1`–`T4` and `T6`–`T7` pass in CI on an otherwise-empty schema. A new tenant-scoped table added without RLS fails the build, not a code review.

---

## 3. Phase 1 — Correct invoices, nothing else

**Ship criterion (verbatim from `problem-statement.md` §10):** a contractor with an Ontario client and a US client can produce two correctly-taxed invoices without reading documentation.

The tax engine is the highest-blast-radius component in the whole product (§5.1–§5.3, risk table §11). It is sequenced first within this phase and gated by its own exhaustive test suite before the invoice builder is wired to it.

| # | Workstream | Depends on | Size |
|---|---|---|---|
| 1.1 | Auth: OTP request/verify/refresh/logout, rate limiting (3/15min per email, 10/hr per IP), constant-time compare, 5-attempt lockout, session with rotating refresh tokens + token-family revocation on replay (`architecture.md` §5). ⚠️ **Actual OTP delivery was never built until 2026-08-08** — `request_otp` had a `# TODO(Phase 1, notifications module): send code by email` stopgap that logged the code server-side instead, gated on `environment != "production"`. `ENVIRONMENT` was never explicitly set on the deployed Render service, so it silently defaulted to `"local"` and that dev-only path was live in real production the whole time (`edgecases.md` A16). Fixed: `ENVIRONMENT=production` set on Render, real delivery shipped via Resend (`core/resend_client.py`) | Phase 0 | M |
| 1.2 | Signed-in devices screen (`GET/DELETE /auth/sessions`); dual-OTP email-change flow | 1.1 | S |
| 1.3 | Business profile CRUD: identity fields, `registration_status` state machine with `registration_effective_date` driving automatic tax-charge behaviour (X6, X7) | Phase 0 | M |
| 1.4 | ⚠️ **Shipped much narrower than this row describes** (found 2026-08-08, while starting Phase 4 workstream 4.2 — not a new regression, just never annotated before, same pattern as 1.19). What actually existed until this fix: `payment_instruction` had full CRUD with column-level encryption, masking, and reveal-on-demand — but nothing in issuance or PDF rendering ever read it, and no frontend UI existed to create one at all. Every invoice this product had issued gave the client no way to pay. Fixed by: `invoice.payment_instruction_snapshot` column (migration 0020) frozen at issue time (same X4/L14 discipline as `supplier_snapshot`/`client_snapshot`), `pdf_renderer.py` rendering it as the "payment" block (already gated correctly by 1.19's `blocks` array), and a "Payment instructions" section added to Business profile so a tenant can actually create one | 1.3 | S |
| 1.5 | ⚠️ **Shipped much narrower than this row describes** (found 2026-08-08, while starting 4.2 — not a new regression, just never annotated before, same pattern as 1.4/1.19). What actually existed until this fix: `business_profile.logo_ref`/`logo_dark_ref` columns since migration 0002, referenced in the API schema, but no endpoint anywhere ever wrote to either — confirmed by grepping the whole codebase. Fixed alongside 4.2 (`POST /profile/logo?variant=light\|dark`, magic-byte validated to png/jpeg/gif, reuses the existing `storage.upload` signed-URL pattern from 0.6) because 4.2's "logo position" theme control would otherwise have had nothing to position | 1.3, 0.6 | S |
| 1.6 | Clients: CRUD, structured address with resolved `region_code` (never free text), `tax_treatment` enum + typed-reason override flow (X19), `taxable_requires_region` constraint (D7) | Phase 0 | M |
| 1.7 | `client_evidence` upload for non-residency attestation; persistent (non-blocking) warning when a `zero_rated_export` client has none on file (X12) | 1.6, 0.6 | S |
| 1.8 | **Tax engine core**, per ADR-003: pure `compute(supply_context, rate_table_snapshot) → tax_result`, no I/O. `resolve_treatment()`, then `resolve_jurisdiction()` — place of supply is the **recipient's** province, never the supplier's | 0.1 | L |
| 1.9 | `tax_rate` / `tax_rate_version` tables with the `EXCLUDE USING gist` overlap constraint; seed the August-2026 rate table from `problem-statement.md` §6.4, including the Nova Scotia split (X2/X3 boundary case) | 1.8 | M |
| 1.10 | Tax engine golden-file test suite — must be green before 1.11 starts: **X1–X6, X9–X11, X13, X15–X18, X20, X21**. This is the one place snapshot/byte-comparison testing is mandatory, not optional | 1.8, 1.9 | L |
| 1.11 | `POST /invoices/preview-tax` dry-run endpoint powering the live tax block in the builder | 1.10 | S |
| 1.12 | Invoice drafts: line items (`invoice_line`), unit types incl. `hours`, service period distinct from invoice date, PO/project reference, payment-terms → due-date computation | 1.6 | M |
| 1.13 | Lightweight `time_entry` log per client/project with "pull from time log" into a line item (manual entry always available as a fallback) | 1.12 | S |
| 1.14 | Compliance checklist blocking issue when a legally required field is missing (L4–L7); supplier/client snapshot composed at issue time | 1.12 | S |
| 1.15 | **Invoice issuance transaction** — built exactly per `architecture.md` §6: lock draft row → validate compliance → load client treatment + jurisdiction → `TaxEngine.compute()` → allocate number from `invoice_sequence FOR UPDATE` → write frozen snapshot (`tax_table_version`, treatment, jurisdiction, template pin) → transition `draft → issued` → append `audit_log`, all in one transaction; PDF render enqueued **after** commit | 1.10, 1.14 | L |
| 1.16 | Numbering edge cases: **N1–N8** — concurrent double-issue, rollback-doesn't-consume, year rollover uses invoice date not clock date, format changes apply forward-only | 1.15 | M |
| 1.17 | Credit note / revision skeleton — required from day one because "issued is immutable" is a Phase 1 rule (§5.3), not a Phase 2 nicety. `credit_note` table, `parent_invoice_id`/`revision` lineage on `invoice` | 1.15 | M |
| 1.18 | PDF rendering pipeline per ADR-004: isolated process, no network, pinned fonts embedded, fixed timezone/locale, content-hash storage at `tenant_id/invoices/{id}/{hash}.pdf`. Render failure never un-issues the invoice (L13) | 1.15, 0.6 | L |
| 1.19 | ⚠️ **Shipped much narrower than this row describes** (found 2026-08-08, while starting 4.1 — not a new regression, just never annotated before). What actually exists: 3 system template rows (`theme`+`blocks` JSONB) seeded in the DB, but no tenant-facing selection or editor of any kind, and `pdf_renderer.py` doesn't read `blocks` at all — rendering is one fixed reportlab layout. `theme.accent_color` existed as a column but wasn't even wired to the renderer until Phase 4's 4.1 fixed it (`invoices_service.py`: the template pinned on an invoice was never looked up). Brand colour/font scale/logo position/margins/block show-hide customization was never built. Real scope: `design.md` §8.6's drag-and-drop editor is 4.2, not this | 1.18 | L |
| 1.20 | Compliance block: not literally "locked in an editor" (there is no editor), but structurally guaranteed — `pdf_renderer.py` always renders the compliance-critical content regardless of `blocks`, so there was never a code path that could omit it. Pagination rules for long line-item tables (M5) — not verified either way | 1.19 | M |
| 1.21 | Ledger view: flat filterable table (date range, client, status, amount, currency, tax treatment), URL-persisted filter state, CSV export of the filtered set (§6.7 ledger half only — client roll-up view is Phase 2) | 1.15 | M |
| 1.22 | Design system base component library: block primitive, badges (tax-treatment + status), tables, buttons, inputs, tabular-figure money formatting — build once here, reused every phase after | 0.1 | L |
| 1.23 | ⚠️ **Partially shipped via SL.F (2026-08-10), not this phase.** Split form/live-preview layout: done — the live preview is the real `<InvoiceDocument>` component fed by actual backend tax computation, not an approximation. Still missing, unchanged by SL.F: a dedicated read-only tax block with inline override affordance (tax lines render inside the document preview instead; overriding a treatment requires editing the client record directly, not a builder-time action) and a sticky issue footer with an irreversibility confirmation dialog (issuing is a plain button today, server-enforced but with no client-side "this can't be undone" step) | 1.11, 1.19, 1.22 | L |
| 1.24 | `snapshot_verify` nightly job: recompute every issued invoice from its frozen snapshot, alert (P1) on any mismatch — running from day one even at low volume, because catching a divergence early is cheap and catching it after 500 invoices is not | 1.15 | M |
| 1.25 | WCAG 2.1 AA pass on the invoice builder specifically (NFR floor named explicitly in `problem-statement.md` §8) | 1.23 | M |

**Decisions to lock before or during this phase:**
- **Q6 (Quebec).** Building QST math into the tax engine (1.8–1.10) is low incremental cost and required regardless (a non-Quebec contractor can still bill a Quebec client). The open decision is narrower: does the product let a **Quebec-resident supplier** onboard in Phase 1, or gate that with an explicit "not yet supported" message until Phase 4, per the risk mitigation in §11? Recommend the latter — QST math ships now, Quebec-resident onboarding is gated.
- **Q9 (rate table ownership).** The human-reviewed rate pipeline (§6.4) needs a named owner and review SLA before 1.9's table is trusted in production. If there's no owner, buy a tax-rate data service instead of hand-maintaining it.
- **Q10 (pricing).** Doesn't block engineering, but a free-tier invoice cap (if any) needs to exist before public launch — decide before Phase 1 exit, not during.

**Exit criteria:**
- All P1 edge cases in scope are green in CI: **A6, T1–T4, N1, X1–X6, X11, X13, X20, L1, L14, M2, M5**.
- `snapshot_verify` has run clean for at least one full week against real drafts.
- Manual walkthrough: Ontario client + US client, two invoices, under 2 minutes each, zero documentation consulted.
- Success metric instrumented and reporting (even at low volume): activation (% issuing within 24h), target 40% per §9.

---

## 4. Phase 2 — The record

**Status: shipped 2026-08-07, extended 2026-08-07.** 2.1–2.12 and 2.14–2.17 built as specified below; 2.13 remains explicitly not built (see its row). 2.12 shipped in a materially different shape than originally planned, and 2.16/2.17 were scoped and then built as a same-day follow-up per direct user request. Deviations from the original plan are called out inline rather than silently folded in, so this table stays an accurate record of what actually happened, not just what was intended.

**Scope (from `problem-statement.md` §10):** client roll-up view, expenses with receipt upload and OCR, T2125 categorization, recurring invoices, payment tracking and aging, CSV exports.

Two Phase-1-deferred open questions resolve here per the doc's own recommendations: **Q1** (multi-currency: USD in Phase 2) and **Q2** (payment tracking: yes, manual only, no bank connection) and **Q4** (sending invoices — see 2.12/2.13's note; the original "verified sender domain" recommendation was superseded twice over).

| # | Workstream | Depends on | Size |
|---|---|---|---|
| 2.1 | ✅ `payment` table, manual payment recording, invoice status **derived** not stored (`partially_paid`/`paid`/`overdue` computed from `amount_paid` vs `total` vs `due_date` — L15), timezone-correct overdue evaluation (L16) | Phase 1 | M |
| 2.2 | ✅ Payment edge cases: overpayment blocked with 1¢ tolerance + credit offer (L10), payment blocked on cancelled invoices (L11), reversal with reason + audit (L12) | 2.1 | S |
| 2.3 | ✅ Aging report (0–30/31–60/61–90/90+) and client-level roll-up view — `design.md` §8.4. **Built as live `GROUP BY` queries, not the `mv_period_summary` materialized view** originally sketched: `REFRESH MATERIALIZED VIEW CONCURRENTLY` can't run inside the RLS-scoped per-request transaction, and a debounced refresh risks showing an outstanding balance that's already been paid. See `datamodel.md` §12 | 2.1 | M |
| 2.4 | ✅ Multi-currency: `fx_rate_to_cad` + `fx_rate_date` captured at issue via the **Bank of Canada Valet API** (free, public, no key — confirms the plan's own recommendation), never blocking issuance on FX-source failure (C2), FX gain/loss recorded explicitly on payment (C3/C4), never chained conversions (C7) | 2.1 | L |
| 2.5 | ✅ Currency edge cases: **C1–C8** — historical currency preserved on client-currency change (C5), CAD-normalized ledger totals with currency always labelled (C6), credit notes use the original invoice's rate (C8) | 2.4 | M |
| 2.6 | ✅ `recurring_rule` + `recurring_run`: generation job spread across the day by tenant timezone, draft-and-notify default, `auto_issue` opt-in strictly gated by the same compliance checklist from 1.14 (R8, P1). **Runs hourly via a scheduled GitHub Actions workflow, not a persistent job-queue worker** (the "Job Queue" component in `architecture.md` §2 isn't built — see §9's note) | Phase 1 | L |
| 2.7 | ✅ Recurring edge cases: day-of-month clamping (R1/R2), idempotency on `(rule_id, occurrence_date)` (R3, P1), missed-run backfill with correct original dates on recovery (R4), client-archive auto-pause (R5) | 2.6 | M |
| 2.8 | ✅ Expenses: receipt-first upload UI (drop zone as the primary surface, not a form), OCR integration with three-field confirmation (vendor/date/amount), manual entry always available as a same-quality fallback, target sub-15-second completion. OCR provider is **Groq's `qwen/qwen3.6-27b` vision model** (free tier). Receipt *upload* itself additionally needs Supabase Storage S3 keys, not yet generated — manual entry (this workstream's primary path anyway) is unaffected | Phase 0 (0.6) | L |
| 2.9 | ✅ `expense_category` seeded with T2125 line mapping, meals & entertainment 50% limit surfaced not hidden (E9), `business_use_pct`, `itc_eligible` hard-gated on `registered` status at the expense date (E7, P1; E8 — no retroactive eligibility) | 2.8 | M |
| 2.10 | ✅ Expense edge cases: dedup by content hash (E5), orphaned receipts surfaced under "Unprocessed" never silently dropped (E1), OCR-down falls straight to manual with no error dialog (E3), capital purchases flagged and excluded from ordinary deduction — no CCA computation (E11) | 2.8, 2.9 | M |
| 2.11 | ✅ Rebilled expenses: recorded as both an expense and an invoice line without double-counting in the P&L (E12) | 2.9, Phase 1 (1.12) | S |
| 2.12 | ✅ **Reframed, not built as originally planned.** The "verified sender domain, transactional email" build was superseded by explicit user direction mid-phase: no email sending at all — download, on-platform view, and a durable but revocable **public shareable link** per invoice instead (`invoice_share_lookup`, mirrors the identity module's bootstrap-lookup pattern). Q4 is answered differently than either original option. See `edgecases.md` §8 for the *next* pivot on this same workstream | Phase 1 | M |
| 2.13 | ⏸️ Payment reminder job — **not built.** Depended on 2.12's original email-sending shape, which didn't happen; a reminder needs a delivery channel to notify through. Revisit once 2.17 (below) ships | 2.12, 2.1 | S |
| 2.14 | ✅ CSV exports: invoices, expenses, clients, P&L (the **year-end zip pack** is Phase 3 — this is the per-entity export only). P&L income is `subtotal - discount_amount`, deliberately never the tax-inclusive total — collected GST/HST is held for the CRA, not revenue | 2.3, 2.9 | S |
| 2.15 | ✅ Responsive PWA polish + camera capture flow for receipts on mobile web (Q7 recommendation: PWA now, native only if receipt capture proves to be the core loop). Installable manifest + a minimal service worker that deliberately never caches API responses (a stale invoice/payment figure from a cache is worse than none) | 1.22, 2.8 | M |
| 2.16 | ✅ User-configured SMTP: `email_account` (tenant's own outgoing mail server, credentials column-encrypted via the same `encrypt_fields`/`decrypt_fields` helper as `payment_instruction.fields_encrypted`), a real connect-and-authenticate `verify` action (no message sent), multiple accounts per tenant with one marked default. Sends via `aiosmtplib`, a per-tenant SMTP relay — no platform-level sending identity | 1.4 (encryption pattern) | M |
| 2.17 | ✅ "Email invoice" compose window on an issued invoice — **never sends automatically**, always ends on an explicit Send. Editable subject/body (sensible defaults pre-filled from the invoice and client), To/Cc as chip inputs, the invoice PDF attached by default but removable, arbitrary extra attachments addable (logged by filename/size only, not persisted to object storage — works even without the Supabase Storage keys 2.8 is still missing). `invoice_email_log` is the durable append-only send record (O10). Full O1–O10 edge-case set closed — see `edgecases.md` §8 | 2.16 | M |

**Exit criteria:**
- P1 edge cases green: **R3, R8, E7**, plus the full C1–C8 currency set. All confirmed green as of the 2026-08-07 ship.
- `snapshot_verify` extended to cover FX-bearing invoices with no new mismatches. Confirmed.
- Success metric instrumented: % of active users logging ≥1 expense with a receipt (§9 — the real retention hook, not invoice volume).
- 2.16/2.17 shipped same-day as a follow-up, verified end-to-end against a real local SMTP server (not just mocked) — a compose-and-send round trip with a real message landing, correctly formed, with its attachment.

---

## 5. Phase 3 — The answer

**Status: shipped 2026-08-08.** 3.1-3.12 all built as specified below (3.10 deviates: live-query, not a background job; 3.11 deviates: synchronous within the request, not a queued job -- see their rows).

**Scope (from `problem-statement.md` §10):** income and set-aside projection, CPP estimate, GST/HST net-owing by filing period, small-supplier threshold tracker, instalment warnings, year-end accountant pack.

Note that a **narrow** version of GST/HST position (§12 Q3 tier (a), sales-tax-only) is mechanically available from Phase 1 since the tax engine already computes it per invoice — what's new here is the **aggregated, filing-period view** plus income tax/CPP (tier (b)) and instalment scheduling groundwork (tier (c) proper lands in Phase 4).

| # | Workstream | Depends on | Size |
|---|---|---|---|
| 3.1 | ✅ `income_tax_bracket` and `cpp_parameter` effective-dated reference tables: federal + 12 non-Quebec provinces/territories, 2025 (historical) and 2026 (current), each row individually verified after a batch fetch produced inconsistent data (`datamodel.md` §6) | Phase 0 | M |
| 3.2 | ✅ Projection engine (`projection/engine.py`) as a module separate from the tax engine — pure functions, no I/O, mirrors `tax/engine.py`'s discipline exactly. Consumes aggregated invoice/expense data, never touches invoice-level tax computation | 3.1, Phase 2 | M |
| 3.3 | ✅ Derived income mode: straight-line extrapolation from year-to-date net income plus scheduled-recurring invoice projection, `is_low_confidence` below 90 days of data (P1) | 3.2, 2.6 | M |
| 3.4 | ✅ Declared income mode: `income_declaration` table (one row per tenant per year), actual-vs-declared variance shown, neither silently preferred (P3) | 3.2 | S |
| 3.5 | ✅ Set-aside recommendation block: net business income → estimated federal + provincial income tax + CPP → recommended set-aside %, assumptions expandable inline in place (not a modal), never phrased as "you owe" (P9, `design.md` §8.1) | 3.3, 3.4 | M |
| 3.6 | ✅ CPP estimate: both self-employed halves, basic exemption, YMPE/YAMPE ceilings including CPP2, components shown not just the total (P8) | 3.1 | S |
| 3.7 | ✅ GST/HST net-owing by filing period (quarterly): collected − ITCs claimable, held-for-CRA framing, never rendered as revenue (P10). `itc_eligible` is the actual ITC signal, not the optional/often-blank `tax_type` column — a real bug caught and fixed while building this | Phase 2 (expenses/ITC) | M |
| 3.8 | ✅ Small-supplier threshold tracker: rolling four-consecutive-calendar-quarter total including zero-rated and pre-registration revenue (S1, P1), FX-converted per invoice, credit notes netted out (S7), 75%/90% escalating warnings with consequence-stated copy, second-business disclosure (S9). **Not built**: distinguishing an immediate single-quarter crossing from a gradual one (S2/S3), and persisting "once crossed, stays crossed" even if revenue later dips (S5) — documented as a gap in `edgecases.md` §5 rather than silently shipped | 3.7 | M |
| 3.9 | ✅ Quarterly instalment warning once projected net income tax + CPP owing crosses the CRA's $3,000 threshold — deliberately excludes GST/HST net-owing, a separate remittance with its own mechanics (a real bug caught while building this: the two were briefly summed together before a test caught it) | 3.5, 3.7 | S |
| 3.10 | **Deviates from spec**: no `projection_refresh` background job. Everything is computed live on each `GET /projection` — same precedent as 2.3's client roll-up (`rollup_service.py`), and for the same reason: at single-tenant data volumes a handful of aggregate queries per request is cheap, and a debounced cache risks showing a stale figure in a financial product. Revisit if that stops being true | 3.2 | S |
| 3.11 | ✅ Year-end accountant pack: invoice PDFs (rendered on demand, ADR-005 — nothing pre-stored) + expense CSV (T2125-mapped) + receipt images (fetched from storage) + GST/HST quarterly summary + P&L + a README, zipped and returned as a signed URL, 7-day TTL (`architecture.md` §11). **Deviates from spec**: built synchronously within the request, not as a queued async job — same reasoning as 3.10, and a storage-layer failure surfaces as a clean 502 rather than an unhandled 500 (caught while browser-verifying against local dev, at a point when storage genuinely wasn't configured yet — real Supabase Storage S3 credentials were generated and wired up 2026-08-08, verified end to end in production: import → issue → real signed URL → real downloaded zip) | 2.14, 3.7 | M |
| 3.12 | ✅ Fiscal-year vs GST-filing-period calendar separation: a year selector (← / → one year at a time, `design.md` mockup) drives the income-tax view; the GST section stays quarter-grained underneath it in the same year. December/January boundary (P11) needed no special-casing — the selector already defaults to the current calendar year and the prior year is one click away | 3.2 | S |

**Exit criteria:**
- ✅ P1 threshold edge case **S1** green, plus the full P1–P11 projection edge-case set (S2/S3/S5 are the one documented gap — `edgecases.md` §5).
- ✅ Every estimated figure carries the "estimate — not tax advice" affordance with visible assumptions — spot-checked on the set-aside block, the derived/declared income toggle, and the year-end pack's README.
- **Not built**: success metrics instrumentation (% opening the projection view monthly, % generating a year-end pack, §9's retention proof metric). This product has no analytics layer at all yet — a gap wider than Phase 3, out of scope to open here.

---

## 6. Phase 4 — The ecosystem

**Status: started 2026-08-08.** 4.1 built as specified below (in the process, closed a real, previously-unannotated gap in 1.19 — see that row's update).

**Scope (from `problem-statement.md` §10):** template import/export marketplace, custom template builder, bank feed, accounting-suite integrations, French localization.

This phase is lower-risk to sequence loosely — none of it touches the tax-correctness core, which is deliberate (§11 risk table: "scope creep toward full accounting" is the risk N1–N7 exist to prevent, and Phase 4 is where the product finally has room to extend without threatening that boundary).

| # | Workstream | Depends on | Size |
|---|---|---|---|
| 4.1 | ✅ Portable `.json` template package format (`package_schema_version`-gated), import validation that rejects — atomically, not partially — anything with an unknown block type, a malformed theme, or a missing compliance-critical block (M1, M2, P1). Also closes the real functional gap surfaced while building this: added `business_profile.default_template_id` (there was no template selection mechanism at all) and fixed `render_pdf` to actually look up an invoice's pinned template and apply its theme, instead of always using a hardcoded accent colour. **Not built**: embedded/referenced assets (a template package is theme+blocks only, no logo/font asset bundling — nothing in the current template system produces or consumes assets to bundle) | Phase 1 (1.19) | M |
| 4.2 | ✅ Custom template builder — still structured blocks + theme tokens, still no raw HTML/CSS input surface (the injection-safety property from Phase 1 must not regress here). Shipped 2026-08-08: `POST/PUT/DELETE /templates` for tenant-owned templates, `template_version_history` (an edit bumps `template.version` and freezes the superseded theme/blocks — closes a real X4/L14 gap found in the process: `render_pdf` previously looked up an issued invoice's template by id alone with no version filter, so editing a template would immediately change how every invoice already issued against it re-rendered), `POST /templates/preview` for the live-preview pane (renders against real supplier data + canned sample line items, never persisted), and a three-pane editor UI (`design.md` §8.6: block list with drag-to-reorder + visibility toggles for the two optional blocks, compliance block pinned and locked, live preview, theme controls). `font_scale` (existed in `theme` JSONB since migration 0006, never read) and `logo_position`/`margins_mm` (new) are now actually wired into `pdf_renderer.py` | 4.1 | L |
| 4.3 | Template marketplace / sharing surface | 4.1 | M |
| 4.4 | Quebec-resident supplier onboarding: QST registration flow, French invoicing (the tax **math** already exists from Phase 1 — this is registration UX, language, and Revenu Québec-specific compliance fields) | Phase 1 (tax engine) | L |
| 4.5 | French localization of the app UI (separate from 4.4 — Quebec support needs French invoices even for non-Quebec-locale users) | — | L |
| 4.6 | Bank feed integration (revisit of N4) — requires its own security review given the sensitivity of read access to bank data | — | XL |
| 4.7 | Accounting-suite integrations (QuickBooks Online, Xero, Wave) — **validate the CSV schema from Phase 3's year-end pack with 3–5 real accountants before committing to an integration contract** (Q8) | 3.11 | L |
| 4.8 | Instalment scheduling and filing-period calendars proper (§12 Q3 tier (c)) | Phase 3 | M |
| 4.9 | Dark mode — token swap only per `design.md` §2.5; the invoice **document** itself never inverts, it stays dark-ink-on-white regardless of app theme | 1.22 | S |

---

## 7. Sovereign Ledger redesign — UI/UX overhaul across Phases 1-4

**Status: shipped 2026-08-10.** Not a new functional phase — a full design-system replacement (`design.md`, merging in `docs/screens/DESIGN.md`'s original brief and mockups) applied across everything Phases 1-4 had already built. Planned and executed as ten sequential sub-phases, each committed, CI-gated, and browser-verified independently rather than as one big-bang change.

| # | Workstream | Depends on | Size |
|---|---|---|---|
| SL.A | ✅ Design tokens, self-hosted Inter/JetBrains Mono font loading (`@fontsource-variable/inter`, `@fontsource/jetbrains-mono` — no external network dependency), `lucide-react` icon library (previously absent from the app entirely) | — | M |
| SL.B | ✅ Shell/nav restructure: icon-led sidebar, persistent desktop topbar (previously mobile-only), avatar sign-out menu. Bell/Help ship as inert visual placeholders (no notifications backend or support destination exists to wire them to yet) | SL.A | M |
| SL.C | ✅ Clients list: new `GET /clients/summary` (paginated, per-client outstanding balance + overdue flag — a new aggregate query, deliberately not reusing `rollup_service.tenant_aging_report`, which excludes zero-balance/not-yet-due clients). **Deviates from the `clients.png` mockup**: the tax badge shows an honest `{region} — {rate}%` label derived from the real rate table rather than the mockup's fabricated compound "GST + PST" figure, since PST is an invoice-level opt-in flag, not a stored per-client default | SL.A, SL.B | M |
| SL.D | ✅ Dashboard remap: "How much is mine?" headline, YTD invoiced/expenses tiles (`income_service.ytd_actuals()` was already computed internally, just never exposed), full-width instalment banner, new Recent Invoices table. Reports extracted to its own `/reports` route | SL.A, SL.B | M |
| SL.E | ✅ Invoice document backend: `render_pdf`'s data-assembly logic extracted into `assemble_invoice_document`/`assemble_preview_document`, shared by the existing PDF renderer and three new JSON endpoints. Regression-gated by the pre-existing PDF test suite running unmodified — proved the extraction changed zero PDF output | SL.A | M |
| SL.F | ✅ Invoice builder rebuilt: two-column layout, live `<InvoiceDocument>` preview fed by real backend tax computation (not a client approximation), new Compliance checklist component (advisory only — verified fail-safe: a due-date-before-invoice-date invoice still gets server-rejected even with every checklist item showing complete). Surfaced and fixed two real gaps: `preview-document` wasn't forwarding `tax/engine.compute()`'s warnings, and the Clients "Add client" form never collected an address at all | SL.A, SL.B, SL.E | L |
| SL.G | ✅ `<InvoiceDocument>` applied to the authenticated invoice-detail page and the public share-link page. Frozen-snapshot guarantee (X4/L14) re-verified through the actual browser after a post-issue profile edit, on both pages, not just the pre-existing API-level test | SL.E, SL.F | S |
| SL.H | ✅ Settings hub (`/settings`) consolidating Business profile/Email accounts/Recurring/Templates, previously four separate top-level nav items. Every dangling link this move created was found and fixed (`grep` swept, not assumed clean). Re-skin of `Ledger`/`ClientDetail`/`Login` needed no changes — already token-driven from SL.A | SL.A, SL.B | M |
| SL.I | ✅ PWA theme-color/manifest colours updated to match | SL.A | S |
| SL.J | ✅ This reconciliation — `design.md` merged as the living spec, `docs/screens/DESIGN.md` marked superseded-but-kept, this table added. Surfaced two things worth a follow-up, not fixed here: the topbar's persistent tax-registration-status chip from `design.md` §7 was never built in this redesign (a real gap, not a deliberate cut), and badge text-on-tint contrast for the new green/gold tokens falls short of WCAG AA at badge text size (`design.md` §12 — 4.00:1 and 3.23:1 against the 4.5:1 floor, computed during this pass, never previously checked for either the old or new palette) | SL.A-SL.I | S |

---

## 8. IBM Carbon redesign — second full design-system replacement, across everything Sovereign Ledger had already restyled

**Status: shipped 2026-08-11.** Not a new functional phase — a second complete design-system replacement (`design.md`, merging in `docs/screens/dashboard_design.md`'s dashboard brief), applied on top of Sovereign Ledger (§7) rather than the original Figma-era system. Planned and executed as eleven sequential sub-phases, same discipline as §7: each committed, verified (build+lint+real browser walkthrough with seeded data, screenshots read back not just HTTP-200-assumed), and pushed independently.

| # | Workstream | Depends on | Size |
|---|---|---|---|
| CB.A | ✅ Design tokens: Carbon Gray neutrals, zero-radius everywhere except Tags/circular elements, IBM Plex Sans/Mono self-hosted fonts, `@carbon/motion`'s real duration/easing values as new CSS custom properties, Carbon's real dataviz categorical palette. Financial Blue and Set-aside Gold kept unchanged; Green/Red replaced with Carbon's actual Support Green 50/Red 60. Library installs: `recharts`, `motion`, `@carbon/icons-react`, `@carbon/motion`, `@carbon/themes`/`@carbon/colors` (dev, reference only) | `design.md` §2-5 | M |
| CB.B | ✅ Icon swap: `lucide-react` → `@carbon/icons-react` across 16 usages in 4 files (`Shell.tsx`, `Dashboard.tsx`, `Settings.tsx`, `ComplianceChecklist.tsx`) | CB.A | S |
| CB.C | ✅ Shell/nav + shared-component restyle: button variants (secondary/ghost), real Carbon Tag proportions (verified against `_tag.scss`, not assumed), table zebra-striping dropped, active-nav tint moved from Compliance Green to Financial-Blue-subtle (green no longer available once it means positive polarity everywhere else) | CB.A, CB.B | S |
| CB.D | ✅ Backend: `GET /reports/pnl` (JSON), `GET /reports/aging/summary` (new not-due bucket, a real gap in the pre-existing `tenant_aging_report`), `GET /reports/revenue-by-client`, `GET /expenses/by-category`, `GET /expenses/receipt-completeness`, `GET /projection/recurring-forecast`, `GET /reports/payment-speed` (v1: tenant-wide average only, trend/per-client explicitly deferred), `tax_reserve` table + `GET`/`PUT /projection/tax-reserve/{year}`. 40 new/extended tests, full local pytest suite green before push | — | L |
| CB.E | ✅ Dashboard rebuild 1/3: eight hero KPI tiles, 12-month Business performance chart, Safe-to-spend waterfall, Actual-vs-projected chart. Caught and fixed a real UX gap during its own verification: Safe-to-spend (projected basis) sat beside Net income (YTD-actual basis) with no distinguishing caption | CB.C, CB.D | L |
| CB.F | ✅ Dashboard rebuild 2/3: Tax Reserve progress tile (new user-enterable field), GST/HST control center chart, AR aging chart, Invoice status donut (client-side tally, no new endpoint) | CB.E | M |
| CB.G | ✅ Dashboard rebuild 3/3: Revenue by client, Expenses by category, Receipt completeness, Recurring revenue, Business momentum, Year-over-year (gated), Accountant readiness (computed client-side, deliberately not an opaque server score), Needs your attention, Recent activity | CB.F | M |
| CB.H | ✅ **Remaining 12 pages re-skin sweep — needed zero code changes.** Verified via full grep audit (2 intentional hardcoded hexes found, both correctly out-of-scope invoice-template defaults; 100% of colour-bearing inline styles already `var(--color-*)`-driven) plus a real Playwright walkthrough of all 12 pages (Ledger, ClientDetail, Clients, InvoiceBuilder, Settings, Profile, TemplateEditor, EmailAccounts, Recurring, InvoiceDetail, PublicInvoice, Login) with real seeded data. Sovereign Ledger's own class-reuse architecture did all the work | CB.C | S (verification only) |
| CB.I | ✅ Framer Motion cinematic layer: `@carbon/motion`-timed route transitions (`AnimatePresence`), staggered tile/panel entrance across every CB.E/F/G dashboard section, KPI count-ups that never animate from zero on first mount, chart draw-ins re-pointed at the same tokens, spring hover/press on the shared `KpiTile` wrapper, Carbon-timed CSS transitions added to buttons/table-rows/nav (previously instant-snap, no `transition` property at all). **`prefers-reduced-motion` implemented for the first time in this app's history**, both via `<MotionConfig reducedMotion="user">` and a global CSS fallback. Deliberately overrides Sovereign Ledger's "never animate numbers from zero" rule, per the user's own explicit cinematic-polish brief | CB.C, CB.E, CB.F, CB.G, CB.H | L |
| CB.J | ✅ PWA manifest `background_color` updated from Sovereign Ledger's `#F8FAFC` to Carbon Gray 10 `#F4F4F4` to match the real page background. `theme-color`/`theme_color` needed no change (Financial Blue kept) | CB.A | S |
| CB.K | ✅ This reconciliation — `design.md` rewritten as the new living spec, this table added, `docs/screens/dashboard_design.md` marked merged/superseded-but-kept. Real WCAG contrast re-check against the new Carbon palette (not assumed to pass because the hexes are "official IBM") surfaced genuine, previously-unchecked failures: Green 50 on its own paired tint at Tag text size (3.04:1, *worse* than the prior system's already-failing green), Gold on its tint (3.23:1, unchanged carry-over), and two plain-text usages at normal size outside the Tag component entirely (Business Momentum's %-change cells, Needs-your-attention's medium-severity items) — flagged for a follow-up pass, not fixed in this review-only phase | CB.A-CB.J | S |

---

## 9. Wise-inspired redesign — third full design-system replacement, moving off hand-rolled CSS onto Tailwind v4 + shadcn/ui

**Status: shipped 2026-08-15.** Not a new functional phase — a third complete design-system replacement (`design.md`, merging in `docs/screens/DESIGN (2).md`'s brief), applied on top of IBM Carbon (§8) rather than a from-scratch build. Structurally different from both prior redesigns in three ways: it moves off hand-rolled CSS custom properties entirely onto Tailwind CSS v4 + shadcn/ui (a styling paradigm this app had never used before), it pulls components from Watermelon UI (`ui.watermelon.sh`, a shadcn-compatible registry), and it adds a brand-new public marketing homepage plus a from-scratch multi-stage OTP verification animation — the first genuinely new *surfaces* either prior redesign didn't touch, not just a re-skin. Planned and executed as eleven sequential sub-phases, same discipline as §7/§8: each committed, verified (build+lint+real browser walkthrough with seeded data, screenshots read back not just HTTP-200-assumed), and pushed independently.

| # | Workstream | Depends on | Size |
|---|---|---|---|
| WI.A | ✅ Tailwind v4 + shadcn bootstrap: `@tailwindcss/vite`, `@theme` token block (Wise-inspired hex values verbatim from the brief), shadcn's real semantic-color contract (`:root`/`.dark` raw values re-exposed via a separate `@theme inline` block, not flattened), `components.json` (`nova` preset — Lucide-icon-based, matching the icon library already in use), path-alias fix needed in the *root* `tsconfig.json` too (not just `tsconfig.app.json`) to work around a real shadcn-CLI workspace-config bug. Watermelon UI confirmed real and reachable by the actual `shadcn` CLI (not just a browser) — install pattern for an existing project is plain `shadcn init` + per-component `add <registry-url>`, no `--preset` flag needed for that part (only their own from-scratch starter uses one). Fonts: Manrope (display, 800/900) + Inter (body, 400/600) self-hosted, replacing IBM Plex; a self-hosted JetBrains Mono for tabular money figures is a net-addition beyond the brief, which names no monospace face. **Real bug found and fixed**: Tailwind's own `@layer utilities` was losing to the legacy Carbon `index.css`'s plain unlayered selectors regardless of specificity — unlayered CSS always beats layered CSS, full stop — fixed by pre-registering a `legacy-carbon` layer at the lowest priority before Tailwind's own `@import` establishes its layer order | `design.md` §2-5 | L |
| WI.B | ✅ Public homepage (`/`) + auth-gated routing inversion: a `RootGate` component (not a repurposed auth guard — different responsibility) branches `/` between the new marketing `Home.tsx` (logged out) and `Shell` (logged in), since React Router can't have two sibling routes both claiming the same path. Every existing authenticated route stays a child of the same `<Route path="/">`, zero renaming, zero blast radius. Hero uses a real product-mockup card, not the AI-document-parsing graphic originally attached to the request — that graphic's own messaging describes a generic document-comprehension product, not what Tallyquo does (confirmed with the user directly before building) | WI.A | M |
| WI.C | ✅ Login rebuild + the redesign's most novel single deliverable: a three-state OTP animation confirmed with the user beyond the standard genre convention — on Verify, the six digit boxes animate into a circle and revolve together as a bespoke loading state (no off-the-shelf equivalent existed to reuse), then either converge into a single checkmark box (success) or un-circle into a red shake (failure, same treatment as a mistyped code). **Real bug found and fixed**: `input-otp`'s `render` prop path does not wrap children in `OTPInputContext.Provider` (only the `children` API does — a real library design quirk, confirmed by reading its source), which crashed the first render; fixed by reading `slots` from the `render` callback's own argument instead of `useContext`. **Real bug found and fixed**: a plain (non-memoized) `isAuthenticated()` check at the top of `Login.tsx` re-fired on the very next render after a successful verify and force-navigated away before the success animation could play at all — fixed by capturing auth state once via `useState(isAuthenticated)` at mount, not re-checking live | WI.A (hard), WI.B (soft) | L |
| WI.D1 | ✅ Shell repaint: sidebar/topbar/nav chrome onto Wise tokens + shadcn primitives, mobile slide-in drawer preserved. Sequenced before the Dashboard specifically because Dashboard renders inside Shell's `<Outlet/>` | WI.A | M |
| WI.D2 | ✅ Dashboard rebuild 1/3 + the real chart-library migration: `chart.tsx` (shadcn's official Recharts wrapper, confirmed to be exactly what Watermelon's own `chart.json` registry item installs) patched for Recharts v3's tightened `Tooltip`/`Legend` content-prop types (v2's types flowed `payload`/`label`/`active` through `ComponentProps<typeof Tooltip>` directly; v3 splits them into a separate `TooltipContentProps` type meant for the render-prop path, which `chart.tsx` wasn't written against). Hero KPI tiles (`KpiTile` restyled onto `Card`, `useCountUp`'s "never animate from zero on first mount" rule ported through unchanged), Business performance chart, Safe-to-spend waterfall + Actual-vs-projected chart migrated onto the categorical positive/warning/accent-cyan/accent-orange/mute palette — never brand lime, which stays reserved for the CTA identity, extending this project's own colour-polarity rule to charts for the first time | WI.D1 | L |
| WI.D3 | ✅ Dashboard rebuild 2/3 and 3/3 combined into one phase: Tax reserve/Threshold tracker progress tiles, GST/HST control center + AR aging chart-grid, Invoice status donut, Revenue-by-client + Expense-category chart-grid, Receipts/Recurring/Readiness tiles, Business momentum, Year-over-year, Needs-your-attention, Recent activity, Recent invoices — all onto the same Card/Progress/Badge/Table primitives, installing shadcn's `Table` component to de-duplicate four repeated raw `<table>` blocks. **Real bug found and fixed**: Recharts' pie-sector entrance animation runs `fill` through `react-smooth`'s colour interpolator, which can't parse CSS custom properties — it silently resolves `var(--color-*)` to black once the animation settles, even though the SVG `fill` attribute still shows the correct `var()` string. Bar/Line charts never animate colour (only size/position) so `var()` works fine there via the browser's own CSS engine; only the two Pie-based donuts hit this, fixed with literal hex values instead | WI.D2 | L |
| WI.E1 | ✅ Simpler-page sweep: Settings, Reports, Ledger, Recurring, Clients, ClientDetail, EmailAccounts, Profile (566 lines, five separate forms — a pure markup swap, business logic untouched), PublicInvoice. New shared `InvoiceBadges.tsx` (`InvoiceStatusBadge`/`TaxTreatmentBadge`) de-duplicates status/tax-treatment badge styling about to repeat across six files. Unlike CB.H's equivalent sweep, this one is real per-page JSX/className work, not a free cascade — Tailwind utility classes inlined in JSX don't cascade the way Sovereign Ledger's shared CSS classes did | WI.D1 | L |
| WI.E2 | ✅ Complex-page sweep: ComplianceChecklist, InvoiceBuilder (2-column sticky-preview layout), InvoiceDetail (655 lines — status/actions card, payments table, the email-invoice modal), TemplateEditor (3-column drag-to-reorder blocks/preview/theme editor). The hand-rolled `.modal-backdrop`/`.modal`/`.modal-footer` becomes shadcn's `Dialog` (Radix-based: real focus trap, ESC-to-close, ARIA). `InvoiceDocument.tsx` stays completely untouched throughout — `design.md` §9's boundary, respected by both prior redesigns too | WI.D1, WI.E1 | L |
| WI.F | ✅ PWA manifest `background_color`/`theme_color` and `index.html`'s `<meta name=theme-color>` updated from Carbon's navy `#1A365D` to canvas-soft `#e8ebe6` / ink `#0e0f0c` | WI.A | S |
| WI.G | ✅ Cleanup + real WCAG contrast re-check. **Found a real gap during this phase's own pre-deletion grep sweep**: `Expenses.tsx` was missing from the original WI.E1/E2 page inventory entirely and was the only page still on legacy Carbon classes — migrated here rather than silently deleting the stylesheet it depended on. `InvoiceDocument.tsx`'s styling extracted into its own self-contained `InvoiceDocument.css` (literal frozen values, not `var()` indirection into the stylesheet about to be deleted) before `index.css` itself was deleted, preserving the "invoice document never changes appearance across redesigns" invariant explicitly, not by accident; the one universal rule `index.css` carried (`prefers-reduced-motion`, covering every plain-CSS transition app-wide) was carried forward into `tailwind.css`'s own `@layer base`, not lost. `@carbon/motion`/`@carbon/colors`/`@carbon/themes`/`react-icons` removed from `package.json` (confirmed zero remaining imports first). Real contrast re-check (computed WCAG relative-luminance ratios, not estimated) found several genuine, previously-unchecked failures — see `design.md` §12 for the full list and fixes; the headline one is `--color-mute` (the brief's own literal `#868685`) failing AA as text on both app backgrounds despite being used almost everywhere as caption/secondary text, darkened to `#5f5e5a` | WI.A-WI.F | M |
| WI.H | ✅ This reconciliation — `design.md` rewritten as the new living spec, this table added, `docs/screens/DESIGN (2).md` marked merged/superseded-but-kept (same convention as `DESIGN.md`/`dashboard_design.md`) | WI.A-WI.G | S |

---

## 10. Cross-cutting requirements — every phase, not a phase

These are not deliverables with an exit date; they're standing constraints that must hold from Phase 0 onward and regress-test on every subsequent phase.

| Requirement | Source | Applies from |
|---|---|---|
| DB-level RLS `FORCE`d, app role without `BYPASSRLS`, adversarial CI gate on every route | `architecture.md` ADR-001, §4 | Phase 0 |
| Append-only `audit_log`, written in the same transaction as the mutation | `datamodel.md` §11 | Phase 0 |
| Issued financial records never hard-deleted; 7-year retention floor | `datamodel.md` §14 | Phase 1 |
| Every generated PDF byte-identical on re-render, forever | ADR-004, `edgecases.md` X4/L14 | Phase 1 |
| "Estimate, not advice" framing on every calculated tax/income figure | `problem-statement.md` §6.10, N2 | Phase 1 onward for tax lines, Phase 3 onward for projections |
| `404` not `403` on cross-tenant resource access | `architecture.md` §10, `edgecases.md` T1 | Phase 0 |
| No user-authored HTML/CSS/JS anywhere in the template system | `architecture.md` §12 | Phase 1 |
| Full data export available on demand, no lock-in | `edgecases.md` D13 | Phase 1 (basic), Phase 3 (year-end pack) |

---

## 11. Open decisions still blocking full commitment

Carried forward from `problem-statement.md` §12, mapped to the phase each one actually gates. Everything else in §12 already has a recommendation baked into the phase tables above.

| Q | Decision needed | Blocks |
|---|---|---|
| Q6 | Quebec-resident supplier onboarding: gate until Phase 4, or allow earlier? | Phase 1 client-onboarding scope (recommend: gate) |
| Q9 | Named owner + review SLA for the tax rate table | Phase 1 production launch — do not go live on unowned rate data |
| Q10 | Pricing model (free tier limits, if any) | Phase 1 public launch, not engineering |
| Q5 | Sole proprietors only through Phase 3 — confirmed, revisit only if incorporated-user demand appears | Phase 4 scoping |
| Q8 | Accounting-suite CSV schema validated with real accountants | Phase 4 (4.7), should start informally during Phase 3 |

---

*This plan sequences build order; it does not restate the "why" behind each decision. For rationale, see the companion documents this file is derived from.*
