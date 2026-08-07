# Problem Statement — Invoicing & Financial Record-Keeping for Canadian Sole Proprietors

**Working title:** (TBD)
**Document type:** Problem statement / product definition — pre-PRD
**Status:** Draft v0.1 — contains open decisions flagged in §12
**Author:** Ammar
**Date:** August 2026

---

## 1. One-line framing

A sole proprietor in Canada does not have an accounting problem. They have a **record-keeping problem that only becomes an accounting problem once a year**, and by then the records are gone. This product is the place where the record gets created at the moment work is billed, and stays correct until the accountant asks for it.

---

## 2. Who this is for

**Primary persona — "the solo contractor"**
- Canadian resident, registered or unregistered sole proprietor (may operate under a trade name / "operating as").
- Bills 1–10 recurring clients, typically monthly, typically hourly or by fixed retainer.
- Clients may be in Canada (any province) or the US.
- Annual revenue roughly $20k–$250k.
- Uses Word/Google Docs templates today, or a generic invoicing tool that does not understand Canadian tax.
- Does their own bookkeeping badly; hands a shoebox to an accountant in March/April.

**Secondary persona — "the accountant / bookkeeper"**
- Not a paying user in v1, but the *destination* of the data. If the year-end export does not save them time, the product has no retention hook.

**Explicitly out of persona (for now):** incorporated businesses, businesses with employees or payroll, product/inventory sellers, multi-user firms.

---

## 3. The problem, stated honestly

Existing tools fail these users in one of two directions:

| Direction | Examples of the failure |
|---|---|
| **Too little** — generic invoice generators | Beautiful templates, zero tax intelligence. Charges 13% to a US client who should be zero-rated. No history, no per-client roll-up, no expense side, no answer to "how much of this is actually mine?" |
| **Too much** — full accounting suites | Double-entry bookkeeping, chart of accounts, bank reconciliation, journal entries. A one-person business abandons setup in week two and goes back to Word. |

The unserved middle is a person who needs to answer six questions and nothing more:

1. Can I send a correct, professional, legally sufficient invoice in under two minutes?
2. Do I charge tax on *this* client, and at what rate?
3. What have I billed this client, this quarter, this year?
4. What did I spend, and where is the receipt?
5. Of the money that came in, how much is actually mine after tax and CPP?
6. When my accountant asks in March, can I hand over one file?

Everything in scope below exists to answer one of those six. Anything that answers none of them is out of scope.

---

## 4. Goals and non-goals

### Goals
- **G1** — Produce compliant, customizable, professional invoices with correct Canadian tax treatment, automatically.
- **G2** — Maintain a permanent, filterable, per-client billing history that survives the year.
- **G3** — Capture expenses and receipts with near-zero friction, categorized for year-end.
- **G4** — Give an honest, continuously updated estimate of income, tax set-aside, and net take-home.
- **G5** — Guarantee that one tenant can never, under any circumstance, see another tenant's data.

### Non-goals (v1)
- **N1** — We do not file anything. Not GST/HST returns, not T2125, not instalments. We prepare, we do not submit.
- **N2** — We do not give tax advice. Every calculated tax figure is an **estimate**, labelled as such, with the assumptions visible.
- **N3** — No double-entry bookkeeping, chart of accounts, or journal entries.
- **N4** — No bank connection / transaction feed in v1 (revisit v2 — see §12).
- **N5** — No payroll, no employees, no contractors-of-contractors.
- **N6** — No payment processing in v1. We display payment instructions; we do not collect money.
- **N7** — No multi-user accounts, roles, or permissions. One email = one business = one tenant.

**The non-goals are the product.** The reason the incumbents lose this segment is that they said yes to N3–N7.

---

## 5. The four hard problems

Everything else is CRUD. These four are where the product is won or lost.

### 5.1 Tax correctness is a *state*, not a number

Most invoicing tools model tax as a percentage field. That is wrong for this market. A single Canadian sole proprietor's invoice can be in one of at least four distinct tax states, and the user's own template already shows three of them:

| State | Line rendered on invoice | When |
|---|---|---|
| **Not registered** | `GST/HST: Not charged — supplier not yet registered` | Small supplier under the $30,000 threshold, no BN issued |
| **Registered, taxable** | `HST (ON) — 13%: CAD 936.00` | Registered, Canadian client, place of supply in a participating province |
| **Registered, zero-rated export** | `GST/HST — 0% zero-rated supply: CAD 0.00` | Registered, service exported to a non-resident, non-registered recipient |
| **Registered, exempt** | `GST/HST: Exempt supply` | Rare in this segment, but must not be conflated with zero-rated |

**Zero-rated and "not charged" both display $0.00 and mean completely different things.** Zero-rated supplies are taxable at 0%, count toward the $30,000 registration threshold, and permit input tax credits on expenses. Non-registration means no ITCs at all. If the product treats these as the same "$0 tax" case, the entire expense and projection layer downstream is wrong.

**Design implication:** tax treatment is an enum stored per client and per invoice, not a rate field. The rate is derived from the state.

### 5.2 Place of supply is the customer's location, not the user's

This is the single most common error in this segment. A contractor in Ontario billing a client in Alberta generally charges 5% GST, not 13% HST. The rate follows the **recipient's** location under the place-of-supply rules, not the supplier's.

The product must therefore:
- Store a **billing address with a resolved province/territory code** on every client (not a free-text address blob).
- Derive the applicable rate from `client.jurisdiction`, not `tenant.jurisdiction`.
- Flag, at client-creation time, when the derived treatment differs from what the user did last time — because they will not notice.
- Handle the US/non-resident case as a first-class path, not an edge case. For this user base it is frequently the *majority* of revenue.

For non-resident recipients, zero-rating under Part V of Schedule VI to the Excise Tax Act depends on the recipient being a non-resident and, for most provisions, not registered for GST/HST. **The CRA places the burden of retaining satisfactory evidence of non-resident status on the supplier.** The product should therefore prompt for and store a non-residency attestation / supporting document against the client record — this is a differentiating feature, not a nicety.

### 5.3 An issued invoice is an immutable legal record

Users will want to "just fix a typo" on an invoice sent three months ago. Allowing that silently destroys the audit trail and the tax history.

Rules:
- Invoices have a lifecycle: `draft → issued → (paid | overdue | cancelled)`.
- **Draft is mutable. Issued is not.** Corrections to an issued invoice create a **credit note** or a **revision** (`ORB-2026-001-R1`) with the original preserved and linked.
- Invoice numbers are **sequential and gapless per tenant**, allocated at issue time (not at draft creation), following a user-configurable scheme (`{PREFIX}-{YYYY}-{NNN}`).
- Every issued invoice stores a **frozen tax snapshot**: the rate table version, the treatment enum, the resolved jurisdiction, and the FX rate used. Historical invoices must never be re-rendered against today's rate table.

This last point is the reason the tax engine needs versioning (§6.4) and why "just update the rates" is not a maintenance task — it is an architectural requirement.

### 5.4 "How much is mine?" needs three separate calculations

The user's example — *"our user is emitting an invoice for $7,000, so you will have to calculate the tax on that invoice. This much will be your income, and this much will be going in taxes"* — actually spans three unrelated tax systems that must not be blended into one number:

| Layer | What it is | Whose money is it |
|---|---|---|
| **Sales tax (GST/HST/PST)** | Collected *on behalf of* government, added on top of the fee | Never the user's. Held in trust, remitted. |
| **Income tax** | Federal + provincial, on **net** business income (revenue − eligible expenses) | User's liability, progressive brackets |
| **CPP contributions** | Self-employed pay **both** the employee and employer halves on net business income above the basic exemption | User's liability, flat-rate band |

A sole proprietor's most expensive misconception is treating collected HST as revenue. The product's headline number must therefore be a **set-aside recommendation**, not a tax bill:

> Invoiced this year: $84,000 · Expenses: $9,200 · Net business income: $74,800
> **Recommended set-aside: $21,400** (est. income tax $14,900 + CPP $6,500)
> GST/HST collected and owed to CRA: $0.00 (zero-rated exports)

Plus a secondary alert the incumbents do not offer: **quarterly instalment warning** once estimated net tax owing crosses the CRA threshold, since a first-year contractor typically discovers instalments only after being penalized for missing them.

---

## 6. Functional scope

### 6.1 Identity, auth, tenancy
- Email address + 6-digit OTP. No password, no Google, no social, no SSO.
- OTP: short TTL, single-use, rate-limited per email and per IP, constant-time comparison, lockout after N failures.
- Session = long-lived refresh token, device-bound, revocable from a "signed-in devices" screen.
- **One email = one tenant.** Tenant ID is derived at signup and is immutable.
- Email change is a sensitive flow requiring OTP confirmation at both old and new addresses.

**Isolation requirements (non-negotiable):**
- `tenant_id` on every table, no exceptions, including logs and uploads.
- Postgres row-level security enforced at the database layer, not the application layer — the application must not be the only thing standing between two tenants.
- Object storage keyed by `tenant_id/` prefix; all file access via short-lived signed URLs; no public buckets.
- Automated test suite includes an adversarial cross-tenant probe on every endpoint as a merge gate.

### 6.2 Business profile
Legal name, operating/trade name, business address, email, phone, website, social links, logo (with dark/light variants), GST/HST number (BN + RT0001), provincial tax registration numbers, default currency, default payment terms, default payment instructions (EFT / ACH / wire fields), invoice number scheme, fiscal year start.

Registration status is a state machine: `not_registered → registration_pending → registered (effective date)`. The **effective date matters** — invoices before it must render "not charged", invoices after must charge tax. This should be automatic, not manual.

### 6.3 Clients
Legal name, billing address with structured country + province/state, contact person, email, default currency, default payment terms, **tax treatment enum + evidence document**, project/PO reference defaults, notes.

Per-client tax treatment is the field that makes the user's requirement — *"GST/HST % will vary per customer / per user"* — work correctly.

### 6.4 Tax engine

This is the component that must be built as a **versioned, effective-dated rate table**, not hardcoded constants.

Current rates (as of August 2026 — to be verified against CRA at build time and continuously thereafter):

| Jurisdiction | Federal | Provincial | Combined | Notes |
|---|---|---|---|---|
| Ontario | — | — | **13% HST** | |
| New Brunswick | — | — | **15% HST** | |
| Newfoundland & Labrador | — | — | **15% HST** | |
| Prince Edward Island | — | — | **15% HST** | |
| Nova Scotia | — | — | **14% HST** | Reduced from 15% effective 1 Apr 2025 |
| Quebec | 5% GST | 9.975% QST | 14.975% | QST administered by Revenu Québec, separate registration & filing |
| British Columbia | 5% GST | 7% PST | 12% | Separate line items, each on pre-tax amount |
| Saskatchewan | 5% GST | 6% PST | 11% | PST raised from 5% in 2025 |
| Manitoba | 5% GST | 7% RST | 12% | RST expanded to cloud/software/data services 1 Jan 2026 — relevant if user sells SaaS |
| Alberta | 5% GST | — | 5% | |
| Yukon / NWT / Nunavut | 5% GST | — | 5% | |
| Non-resident (US etc.) | 0% | — | **0%** | Zero-rated export, evidence required |

**The Nova Scotia change is the argument for the whole architecture.** A tool with a hardcoded 15% silently produced wrong invoices for every NS client after April 2025. Our table must be:
- Effective-dated: `(jurisdiction, tax_type, rate, effective_from, effective_to)`.
- Applied by **invoice date**, never by today's date.
- Versioned, with the version ID stamped onto every issued invoice.

**Rate monitoring pipeline** (the user's requirement to "monitor what the tax rates are… and update them if there is any change on the government sites"):
- Scheduled scrape/diff of canada.ca GST/HST rate pages plus each provincial finance authority.
- A change produces an **alert to an internal reviewer, never an automatic production write.** Tax rates are the last thing to trust an unattended scraper with.
- Reviewer approves → new effective-dated row → users on affected jurisdictions get an in-app notice.
- Manual override path for emergency changes announced in a budget before the web pages update.

**Small supplier threshold tracking** — a genuine differentiator:
- Track a rolling **four-consecutive-calendar-quarter** total of worldwide taxable supplies, **including zero-rated exports** (a frequent and expensive misunderstanding for contractors billing US clients).
- Warn at 75% and 90% of the $30,000 threshold; hard alert on crossing, with a plain-language explanation of the difference between crossing gradually and crossing within a single quarter.
- Surface the retroactive-liability risk explicitly: tax not collected on invoices issued after the obligation arose comes out of the user's own pocket.

### 6.5 Invoice builder
- Line items with `description / quantity / unit / rate / amount`; unit ∈ {hours, days, fixed, units}.
- **Hourly billing is first-class**: an optional lightweight time log per client/project that rolls up into a line item, plus a manual hours entry for users who track elsewhere. Hours and rate must be *visible on the invoice* — this is what makes it defensible under CRA scrutiny and what the user's own template does.
- Service period (distinct from invoice date), project/PO reference, payment terms → auto-computed due date.
- Discounts, deposits/retainers applied, late fees.
- Multi-currency: invoice currency ≠ reporting currency. See §12 Q1.
- Live preview; tax lines rendered per the client's treatment; a compliance checklist that blocks issuing if a legally required field is missing.

**Mandatory compliance block** (rendered by every template, not user-removable, contents varying by registration status): supplier legal/operating name, supplier address, invoice date, invoice number, client name and address, description of supply, total, tax breakdown by type and rate, and — when registered — the GST/HST registration number. The registration number is legally required on invoices above CRA thresholds for the client to claim their own ITCs; omitting it makes the client's accountant reject the invoice.

### 6.6 Template system

Three tiers, matching the three things the user asked for:

1. **Provided templates** — a curated library (Classic / Minimal / Modern / Trades / Consulting), each Canada-compliant out of the box.
2. **Customized templates** — the user edits a provided template: brand color, accent, font family/size, logo size and position, block order, show/hide optional blocks, page margins, footer text, watermark. Saved as their own.
3. **User templates** — built up, named, set as default per client, duplicated, archived.

**Critical design decision: do not let users author arbitrary HTML/CSS.** A template is a **structured document**: a JSON theme (design tokens) + a block layout array + a locked compliance block. This keeps every template renderable, printable, legally complete, and safe from injection — and makes import/export trivial.

**Import/export** = a portable `.json` template package (schema-versioned, with embedded assets or asset references). Shareable via the web space, validated on import, rejected if it fails compliance-block requirements.

### 6.7 History, search, and roll-ups

The user's requirement — *"they are billing a customer called ABC every month for $500… it should be consolidated"* — implies two views, not one:

- **Ledger view** — flat, filterable table of all invoices. Filters: date range, client, status, amount range, currency, tax treatment, project. Saved filter presets. Column sort. CSV export of any filtered set.
- **Client view** — one client, with a period-by-period roll-up (monthly / quarterly / annual / custom term), total billed, total collected, outstanding, average days-to-pay, and a sparkline. This is the view that answers "which month, how much".

Plus: aging report (0–30 / 31–60 / 61–90 / 90+), because a solo contractor's real problem is not writing the invoice, it is remembering who has not paid.

### 6.8 Recurring invoices & automation
- Any invoice can be promoted to a recurring schedule: monthly / bi-weekly / quarterly / custom, with end date or occurrence count.
- **Default to draft-and-notify, not auto-send.** Generate the draft, notify the user, one tap to issue. Auto-send is opt-in per schedule. An invoice sent with a wrong amount costs more trust than one sent two days late.
- Automatic rebuild of the service period and invoice date per occurrence.
- Pause/skip a single occurrence; rate change effective from a given occurrence.
- Payment reminders: configurable pre-due and post-due nudges (see §12 Q4 on whether we send email at all).

### 6.9 Expenses

Design principle: **the receipt is the entry point, not the form.** A user who must fill a form before uploading a receipt will not record expenses.

- Flow: capture/upload receipt → OCR extracts merchant, date, total, tax → user confirms or corrects three fields → saved. Target under 15 seconds.
- Fallback manual entry: date, amount, tax amount, category, vendor, payment method, notes, client/project (for billable expenses).
- **Categories map to CRA T2125 expense lines** (advertising, meals & entertainment at the 50% limit, office expenses, professional fees, supplies, travel, motor vehicle, business-use-of-home, capital assets). Mapping to the actual form is what makes year-end export valuable rather than decorative.
- Business-use-percentage field for mixed-use expenses (home office, vehicle, phone).
- **Track GST/HST paid separately** — for a registered user this is their input tax credit, and it directly reduces what they owe. For a non-registered user it is simply part of the cost. The product must know which.
- Recurring expenses (software subscriptions, insurance) on a schedule.
- Receipt files retained and re-downloadable — CRA generally expects supporting records to be kept for six years.

### 6.10 Income & tax projection

Two input modes, as the user proposed, and both should coexist:
- **Derived** — projected annual revenue extrapolated from issued invoices plus scheduled recurring invoices.
- **Declared** — user states expected annual income; the product tracks actual vs. declared and shows the variance.

Outputs:
- Revenue, expenses, net business income, year to date and projected.
- Estimated income tax (federal + provincial brackets for the user's province of residence).
- Estimated CPP self-employment contributions.
- **Recommended set-aside %** and a running "safe to spend" figure.
- GST/HST collected, ITCs claimable, and **net tax owed to CRA** by filing period — this is the number that matters and no generic invoicing tool provides it.
- Quarterly instalment warning when projected net tax owing crosses the CRA threshold.
- Simple P&L by month/quarter/year, exportable.

Every figure carries a visible "estimate — not tax advice; assumptions: [...]" affordance with the assumptions expandable. This is both an honesty requirement and a liability requirement.

### 6.11 Exports
- Individual invoice PDF (deterministic, pixel-stable, embedded fonts).
- Bulk PDF export of a filtered set.
- CSV: invoices, expenses, clients, P&L.
- **Year-end accountant pack**: a single zip — invoice PDFs, expense CSV mapped to T2125 lines, all receipt images, GST/HST summary by period, P&L. If this one artifact is good, the product retains users through every March.
- **Public shareable link** (shipped Phase 2): a durable, revocable, unauthenticated view/download URL per issued invoice — the "share it yourself" complement to download-and-send-yourself.
- **Email, via the user's own SMTP** (shipped Phase 2, see Q4): a compose window on an issued invoice, always requiring an explicit send, never automatic.

---

## 7. Data model sketch

```
tenant            id, email, created_at, status
business_profile  tenant_id, legal_name, operating_name, address, contacts,
                  logo_ref, gst_hst_number, registration_status,
                  registration_effective_date, defaults...
client            tenant_id, legal_name, address{country, region_code},
                  tax_treatment, non_residency_evidence_ref, currency, terms
project           tenant_id, client_id, name, code, default_rate
invoice           tenant_id, client_id, number, status, invoice_date,
                  service_period, currency, fx_rate, fx_date, subtotal,
                  tax_lines[], total, template_id, tax_table_version,
                  tax_treatment_snapshot, issued_at, pdf_ref
invoice_line      invoice_id, description, qty, unit, rate, amount, taxable
credit_note       tenant_id, invoice_id, reason, amount, issued_at
payment           tenant_id, invoice_id, amount, date, method, note
recurring_rule    tenant_id, template_invoice_id, cadence, next_run, status
expense           tenant_id, date, vendor, amount, tax_amount, currency,
                  category (T2125 line), business_use_pct, client_id?,
                  receipt_ref, source (ocr|manual)
template          tenant_id?, name, schema_version, theme_json,
                  blocks_json, is_system
tax_rate          jurisdiction, tax_type, rate, effective_from, effective_to,
                  source_url, version_id            -- global, not tenant-scoped
audit_log         tenant_id, actor, action, entity, before, after, at
```

Every tenant-scoped table carries `tenant_id` and an RLS policy. `tax_rate` is the only global table.

---

## 8. Non-functional requirements

| Area | Requirement |
|---|---|
| **Isolation** | DB-level RLS; adversarial cross-tenant tests in CI as a merge gate |
| **Retention** | Records retained and exportable for at least 7 years (CRA expects 6) |
| **Immutability** | Issued invoices and their PDFs are write-once; corrections via credit note/revision |
| **Auditability** | Append-only audit log for every mutation on financial entities |
| **Data residency** | Canadian region strongly preferred; confirm before vendor selection |
| **Availability** | Invoice rendering must work offline-tolerant / degrade gracefully; month-end is a spike |
| **PDF fidelity** | Deterministic server-side rendering; identical output across devices and time |
| **Security** | Encryption at rest and in transit; signed short-lived URLs for all uploads; OTP rate limiting; no PII in logs |
| **Export** | Full data export on demand, no lock-in — this is a trust feature for a financial record system |
| **Accessibility** | WCAG 2.1 AA on the invoice builder at minimum |
| **Performance** | Invoice creation from template to issued in under 2 minutes for a repeat client; under 20 seconds for a recurring one |

---

## 9. Success metrics

**Activation:** % of signups who issue a first invoice within 24 hours. *(Target: 40%)*
**Core loop:** % of active users who issue ≥1 invoice in consecutive months. *(Target: 70%)*
**The real hook:** % of users who log ≥1 expense with a receipt. *(Expenses, not invoices, are what create switching costs — invoices are portable, an expense archive is not.)*
**Tax value proof:** % of users who open the projection/set-aside view monthly.
**Retention proof:** % of users who generate a year-end accountant pack.
**Correctness (leading indicator of churn):** rate of invoices voided or credit-noted within 7 days of issue.

---

## 10. Phasing

**Phase 1 — Correct invoices, nothing else**
Auth + tenancy, business profile, clients with tax treatment, 3 system templates with theme customization, invoice builder with hourly support, versioned tax engine, PDF export, ledger history with filters.
*Ship criterion: a contractor with an Ontario client and a US client can produce two correctly-taxed invoices without reading documentation.*

**Phase 2 — The record**
Client roll-up view, expenses with receipt upload and OCR, T2125 categorization, recurring invoices, payment tracking and aging, CSV exports.

**Phase 3 — The answer**
Income and set-aside projection, CPP estimate, GST/HST net-owing by filing period, small-supplier threshold tracker, instalment warnings, year-end accountant pack.

**Phase 4 — The ecosystem**
Template import/export marketplace, custom template builder, bank feed, accounting-suite integrations, French localization.

---

## 11. Key risks

| Risk | Impact | Mitigation |
|---|---|---|
| **Wrong tax on an issued invoice** | Existential — user is financially liable, product is unrecoverable | Effective-dated versioned rates; frozen snapshots; human-reviewed rate updates; compliance checklist blocks issue |
| **Perceived as giving tax advice** | Legal exposure | Explicit estimate framing everywhere, visible assumptions, terms of use, no "you owe $X" phrasing |
| **Cross-tenant leak** | Existential — financial data | RLS at DB layer, CI adversarial tests, scoped storage |
| **Template flexibility breaks compliance** | Invoices rejected by clients' accountants | Structured templates with a locked compliance block; no raw HTML |
| **Expense capture friction kills the loop** | Product degrades into an invoice generator with worse templates than Word | Receipt-first OCR flow, sub-15-second target, measured as a primary metric |
| **Scope creep toward full accounting** | Segment abandonment | Non-goals N1–N7 treated as binding, not aspirational |
| **Quebec complexity** | QST is a separate registration, separate agency, and French invoicing expectations | Consider deferring Quebec-resident users to Phase 4 with an explicit "not yet supported" message rather than shipping something half-right |

---

## 12. Open questions — decisions needed before PRD

These change the shape of the build materially. Ordered by blast radius.

**Q1 — Multi-currency.** Your own template invoices a US client **in CAD**. Do we support issuing in USD? If yes, we need FX rate capture at invoice date (Bank of Canada daily rate) for CAD reporting, an FX gain/loss concept when payment differs from invoice date, and dual-currency roll-ups. If CAD-only, the build shrinks significantly. *Recommendation: CAD-only issuing in Phase 1, USD in Phase 2.*

**Q2 — Do we track payments received?** Invoice-generation-only is a much smaller product, but without payment tracking there is no aging report, no "outstanding" figure, and the P&L is accrual-basis only — which is not how most sole proprietors think or how CRA lets them report. *Recommendation: yes, manual payment marking in Phase 2 — no bank connection.*

**Q3 — How deep does the tax projection go?** Three tiers of ambition, three very different liability profiles:
 (a) sales tax only — what's owed to CRA from collected GST/HST;
 (b) + income tax and CPP set-aside estimate;
 (c) + instalment scheduling and filing-period calendars.
*Recommendation: (b) in Phase 3, (c) in Phase 4, with (a) available from Phase 1.*

**Q4 — Does the product send email to the user's clients?** Sending invoices directly is a strong feature and a large build — deliverability, domain authentication, bounce handling, open tracking, and a support burden when a client claims they never received it. The alternative is download-and-send-yourself. *Original recommendation: download-only in Phase 1; sending in Phase 2 behind a verified sender domain.*

**Resolved twice over, differently each time.** Phase 2 shipped without a "verified sender domain" at all — by direct user decision, download, on-platform view, and a durable, revocable **public shareable link** per invoice replaced sending entirely (`implementation_plan.md` 2.12). That sidesteps the domain-authentication/deliverability problem completely rather than solving it.

A second, separate pivot shipped the same day (2026-08-07): **user-configured SMTP**. Each tenant connects their own outgoing mail server — their own Gmail, Outlook, or custom SMTP host — so any email sent carries their own sender reputation, not the platform's. This avoids the verified-sender-domain problem a different way: there's no platform-level sending identity to authenticate at all. "Email invoice" is available once an invoice is issued, but **never sends automatically** — it opens a compose window (editable subject and body, To/CC, the invoice PDF attached by default but removable, extra attachments addable) that requires an explicit send action every time. See `implementation_plan.md` 2.16/2.17 and `edgecases.md` §8.

**Q5 — Sole proprietors only, or also single-member corporations?** Incorporated users need corporate tax rates, dividend/salary decisions, and a fiscal year that isn't the calendar year. This is a different product, not a setting. *Recommendation: sole proprietors only through Phase 3.*

**Q6 — Quebec in or out of v1?** QST requires separate registration and filing with Revenu Québec, and Quebec has French-language expectations for commercial documents. Supporting it half-way is worse than not supporting it.

**Q7 — Mobile.** You mentioned logging in "using a mobile." Is that mobile-web (a responsive PWA) or a native app? Receipt capture argues strongly for at least a good camera flow on mobile web. *Recommendation: responsive PWA with camera access in Phase 2; native only if receipt capture proves to be the core loop.*

**Q8 — Accountant handoff format.** Is a CSV + zip pack sufficient for v1, or do we need integrations (QuickBooks Online, Xero, Wave) to be credible? Integrations are a Phase 4 item but should be validated with 3–5 accountants before we commit to the CSV schema.

**Q9 — Who owns the rate table?** Continuous monitoring of 13 jurisdictions plus federal is an ongoing operational commitment, not a one-time build. Is there a named owner and a review SLA? If not, buy a tax-rate data service instead of scraping.

**Q10 — Pricing.** Not asked, but it shapes scope: a $10/month tool cannot fund a human-reviewed tax pipeline. Free tier with N invoices, then flat monthly? Annual-only, priced against the value of the year-end pack?

---

## 13. Appendix — reference invoice anatomy

Derived from the supplied Orbyn Labs template; this is the minimum field set every template must be able to render.

**Supplier block:** logo · operating name · legal name + "sole proprietor, operating as" · address · email · phone · GST/HST number (conditional on registration status)

**Document block:** "INVOICE" · invoice number · invoice date · service period · payment terms · payment due date · currency

**Bill-to block:** client legal name · full address including country

**Services block:** project reference · narrative description of services and the governing agreement · line table (project/period, hours, rate, amount)

**Totals block:** subtotal · tax line rendered per treatment state · total due

**Payment block:** account holder · payment method · provider · account currency · institution/transit/account numbers · US routing/account (conditional) · payment reference = invoice number

**Conditional tax line variants — all three must be supported:**
```
GST/HST — 13%:                              CAD 936.00
GST/HST — 0% zero-rated supply:             CAD   0.00
GST/HST: Not charged — supplier not yet registered
```

---

*Tax rates and thresholds in this document reflect publicly available information as of August 2026 and must be verified against CRA and provincial sources before implementation. This document is a product specification, not tax advice.*
