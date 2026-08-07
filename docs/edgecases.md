# Edge Cases

**Companion to:** `problem-statement.md`, `architecture.md`, `datamodel.md`, `design.md`
**Status:** Draft v0.1
**Use:** Each row is a test case. Anything marked **P1** is a correctness defect that produces a wrong legal or financial record and blocks release.

---

## 1. Authentication and account

| # | Case | Expected behaviour |
|---|---|---|
| A1 | User requests OTP for an email that doesn't exist | Identical 200 response and identical timing to a known email. **No account enumeration.** Code is sent; first successful verification provisions the tenant |
| A2 | User requests multiple OTPs rapidly | Latest code invalidates prior ones. Rate limit 3 per 15 min per email, 10/hr per IP. Response never reveals which limit was hit |
| A3 | OTP arrives after expiry (slow mail server) | `Code expired. Request a new one.` — never accept an expired code, regardless of delivery delay |
| A4 | User pastes the code with whitespace or as `123 456` | Strip non-digits before comparing |
| A5 | Email with plus-addressing (`me+work@x.com`) | Treated as **distinct** from `me@x.com`. Do not normalize plus-addresses — some users deliberately separate businesses this way |
| A6 | Gmail dot variants (`m.e@gmail.com` vs `me@gmail.com`) | Treated as distinct. Provider-specific normalization would silently merge two tenants. **P1** |
| A7 | Uppercase email | Case-insensitive via `citext`; stored as entered, compared lowercased |
| A8 | Same code entered twice | Second attempt fails — codes are single-use |
| A9 | Brute force on a code | 5 attempts, then the code is invalidated and a new request is required |
| A10 | User loses access to their email entirely | No recovery path exists by design. Documented plainly at signup. Support-mediated recovery requires out-of-band identity proof and is fully audited |
| A11 | Refresh token replayed after rotation | Entire token family revoked; all sessions signed out; user notified by email |
| A12 | Email change to an address that already has a tenant | Rejected. `That email already has an account.` No merge path in v1 |
| A13 | Email change abandoned halfway | Old address remains authoritative and functional. Pending change expires in 24h |
| A14 | Session active while tenant is suspended | Next request returns 403 with a clear reason; read-only export access remains |
| A15 | Clock skew between server and mail delivery | OTP TTL measured server-side only |

---

## 2. Tenancy and isolation

| # | Case | Expected behaviour |
|---|---|---|
| T1 | Request for another tenant's invoice by UUID | `404`, never `403`. A 403 confirms the resource exists. **P1** |
| T2 | Application forgets to set `app.tenant_id` | Query errors (no default fallback). **Fail closed, never fail open.** **P1** |
| T3 | Background job with no tenant context | Job fails and alerts. Never runs unscoped |
| T4 | Attempt to link tenant A's invoice to tenant B's client | Rejected by composite FK at the database. **P1** |
| T5 | Signed storage URL shared or leaked | TTL ≤5 min; URL is scoped to one object; expiry is not extendable |
| T6 | Reporting or admin query written without a `WHERE tenant_id` | RLS filters it anyway. Emits `cross_tenant_denied` metric so the bug surfaces |
| T7 | Database restore from backup | Restore drill verifies RLS policies came back enabled — a restore that drops policies is a silent breach |
| T8 | Tenant closed, email later reused by a new signup | Email is permanently reserved. New signup rejected |

---

## 3. Invoice numbering

| # | Case | Expected behaviour |
|---|---|---|
| N1 | Two issue requests submitted simultaneously (double-click, two tabs) | Sequence row locked `FOR UPDATE`; second request either gets the next number or is deduplicated by idempotency key. **Never two invoices with the same number.** **P1** |
| N2 | Issue fails after number allocation | Transaction rolls back; number is **not** consumed. Numbering stays gapless |
| N3 | Invoice cancelled after issue | Number is retained and never reissued. The cancelled invoice remains visible in the ledger |
| N4 | Year rolls over with format `{PREFIX}-{YYYY}-{NNN}` | New scope key, counter resets to 001. An invoice dated Dec 31 issued Jan 2 uses the **invoice date's** year, not today's |
| N5 | User changes the number format mid-year | Applies to future invoices only. Existing numbers are immutable. Warn that the sequence appears to restart |
| N6 | User migrating from another tool wants to start at 247 | Supported: set the starting value once, at setup. Cannot be lowered afterwards |
| N7 | User manually types a number that collides | Rejected by `UNIQUE (tenant_id, number)` with a clear message |
| N8 | Revision of an issued invoice | New record `INV-2026-014-R1`, original preserved and linked. Does not consume a new base number |

---

## 4. Tax computation — the P1 zone

| # | Case | Expected behaviour |
|---|---|---|
| X1 | Client in Alberta, supplier in Ontario | **5% GST**, not 13% HST. Place of supply follows the recipient. **P1** |
| X2 | Invoice dated 2025-03-15 for a Nova Scotia client | **15%** (pre-change rate), even though today's rate is 14%. **P1** |
| X3 | Invoice dated 2025-04-01 for a Nova Scotia client | **14%**. Boundary is inclusive of the effective date |
| X4 | Historical invoice re-rendered in 2030 | Uses the frozen snapshot, not the live table. Byte-identical output. **P1** |
| X5 | Zero-rated export vs. not registered | Different `invoice_tax_line` rows, different display strings, different threshold and ITC consequences. Never collapsed into "0%". **P1** |
| X6 | Supplier becomes registered mid-year | Invoices before `registration_effective_date` render "not charged"; on/after charge tax. Automatic, from the invoice date |
| X7 | User backdates an invoice to before their registration date | Warn explicitly and apply the pre-registration treatment. Do not silently charge tax |
| X8 | Registration date backdated after invoices were already issued unregistered | **Do not retroactively alter issued invoices.** Surface a report of affected invoices and explain that corrections require credit notes and reissue |
| X9 | Client in Quebec | GST 5% + QST 9.975% as **two separate lines**, each computed on the pre-tax amount. Not compounded. Flag that QST requires separate Revenu Québec registration |
| X10 | Client in BC / SK / MB | GST + PST/RST as separate lines. Note that PST on services is narrower than GST — most professional services are PST-exempt. Default PST off for service lines, with an override |
| X11 | Client is a non-resident **but registered** for GST/HST | Most zero-rating provisions do not apply. Derived treatment is `taxable` with an explanatory note. **P1** |
| X12 | Zero-rated client with no non-residency evidence on file | Persistent warning on the client and on every invoice. Does not block issuing — nagging, not gating |
| X13 | Rate table has no row for the invoice date | Hard error, refuse to issue, alert operations. **Never fall back to a default rate.** **P1** |
| X14 | Two overlapping rate rows for a jurisdiction | Impossible — excluded by the database constraint. If it occurs, the constraint was dropped |
| X15 | Mixed invoice: some taxable lines, some exempt | Per-line `is_taxable`; the taxable base is the sum of taxable lines only |
| X16 | Rounding: 13% of $7,199.99 | Round half-up to 2dp at the **tax line** level, not per item. Document the rule; `sum(tax_lines) = tax_total` exactly |
| X17 | Discount applied to an invoice | Discount reduces the taxable base before tax is computed |
| X18 | Client moves province between invoices | Each invoice uses the jurisdiction snapshot from its own issue time. History does not shift |
| X19 | User overrides derived treatment | Typed reason required, stored on the client, audited. Override is shown on the invoice detail so it isn't forgotten |
| X20 | Rate crawler detects a change | Opens a review ticket only. **Never writes to `tax_rate`.** **P1** |
| X21 | Supplier and client both in a participating province, service performed elsewhere | Place-of-supply rules can diverge from the billing address. Flag for user confirmation rather than guessing |

---

## 5. Small supplier threshold

| # | Case | Expected behaviour |
|---|---|---|
| S1 | User bills only US clients (all zero-rated) | Zero-rated exports **count** toward the $30,000 threshold. This is the most expensive misconception in the segment. **P1** |
| S2 | Threshold crossed within a single calendar quarter | Registration obligation is immediate. Message states this clearly and distinguishes it from gradual crossing |
| S3 | Threshold crossed gradually across four quarters | Different timing rule and a short grace period. Message must not conflate the two cases |
| S4 | User approaches 75% / 90% | Escalating in-app notice with the consequence stated, not just the number |
| S5 | User crosses, then revenue falls below | Registration does not automatically lapse. Do not tell the user they can stop charging |
| S6 | Multi-currency revenue | Threshold computed in CAD using each invoice's frozen FX rate |
| S7 | Cancelled invoices and credit notes | Excluded / netted out of the threshold calculation |
| S8 | Exempt supplies in the mix | Excluded from the threshold. Only taxable (including zero-rated) counts |
| S9 | User has a second business | The $30,000 is shared across associated businesses. The product can only see one — state this limitation explicitly rather than implying the figure is complete |

---

## 6. Currency and FX

| # | Case | Expected behaviour |
|---|---|---|
| C1 | Invoice in USD, reporting in CAD | Capture FX rate and date at issue; store both. `total_cad` derived and frozen |
| C2 | FX source unavailable at issue time | Use last known rate, mark the invoice for review, **never block issuing** |
| C3 | Payment arrives at a different rate than the invoice | FX gain/loss recorded explicitly as its own figure. Not silently absorbed into revenue |
| C4 | Partial payments across different dates | Each payment carries its own rate and CAD amount |
| C5 | Client's default currency changed after past invoices | Historical invoices keep their original currency. Roll-ups display both, converted to CAD for totals |
| C6 | Ledger view mixing CAD and USD | Totals shown in CAD with a visible note. Currency code always shown next to every amount — never a bare `$` |
| C7 | Rounding on conversion | Convert once, at issue, to 2dp. Never chain conversions |
| C8 | Refund or credit note in a foreign currency | Uses the **original invoice's** rate, not today's |

---

## 7. Invoice lifecycle and immutability

| # | Case | Expected behaviour |
|---|---|---|
| L1 | User edits an issued invoice | Blocked at the API with 409, not just hidden in the UI. Offered: credit note, or revision. **P1** |
| L2 | User deletes an issued invoice | Not possible. Cancel only, with a reason, record retained |
| L3 | Draft older than 12 months | Retained, flagged stale. Never auto-deleted — it may be a work in progress |
| L4 | Issue attempted with no line items | Blocked. `Add at least one line item.` |
| L5 | Issue with a total of $0.00 | Permitted (legitimate for fully-credited or sample invoices) but confirmed explicitly |
| L6 | Negative total | Blocked. That is a credit note, and the UI redirects to creating one |
| L7 | Due date earlier than the invoice date | Blocked with a field-level error |
| L8 | Service period ends after the invoice date | Permitted with a note — advance billing is normal for retainers |
| L9 | Service period spans a tax rate change | Rate follows the **invoice date**, not the service period. Note this on the invoice where the two disagree |
| L10 | Payment recorded exceeding the total | Blocked above a 1¢ tolerance; user is offered an overpayment credit instead |
| L11 | Payment recorded on a cancelled invoice | Blocked |
| L12 | Invoice marked paid, then payment reversed | Delete the payment record with a reason; status recalculates. Audited |
| L13 | PDF render fails after a successful issue | Invoice is legally issued regardless. UI shows `Preparing document`; render retries; user can force regeneration |
| L14 | Template edited after invoices used it | Issued invoices pin the template version and re-render identically. **P1** |
| L15 | Overdue status | Computed, not stored — derived from `due_date < today AND amount_paid < total`. Never a stale stored flag |
| L16 | Timezone at a day boundary | Overdue evaluated in the business profile's timezone, not UTC |

---

## 8. Invoice sending (user-configured SMTP)

**Not yet built — planned 2026-08-07.** `implementation_plan.md` 2.16/2.17. Supersedes the original "verified sender domain" idea from `problem-statement.md` Q4 a second time: each tenant connects their own outgoing mail server, so the platform never authenticates a sending identity of its own. The one rule every case below serves: **an email only ever leaves because a human clicked send on that exact message**, never because a job scheduled it.

| # | Case | Expected behaviour |
|---|---|---|
| O1 | "Email invoice" clicked | Opens a compose window pre-filled with sensible defaults (client's email `To`, a standard subject/body, invoice PDF attached). **Never sends on open.** An explicit send action is always required |
| O2 | No SMTP account configured | "Email invoice" prompts to configure one first — never hidden without explanation, never silently falls back to a platform sender |
| O3 | SMTP credentials rejected at send time | Clear, specific error in the compose window; the composed subject/body/recipients/attachment choices are preserved so the user doesn't redo the work. Invoice status is unaffected — sending was always independent of issuing |
| O4 | SMTP credentials stored | Encrypted at the column level, same pattern as `payment_instruction.fields_encrypted` (`datamodel.md` §4) — never logged, never returned to the client in full, masked with reveal-on-demand only. **P1** |
| O5 | User unchecks the invoice PDF and adds no other attachment | Permitted (a reminder-only email is legitimate) but confirmed explicitly before sending, not sent silently empty-handed |
| O6 | Extra attachment exceeds a reasonable size | Rejected at attach time with the limit stated, before a send is attempted — not a bounce discovered after the fact |
| O7 | Send clicked twice (double-submit) | Idempotent per compose session — one email, not two, regardless of double-clicks or a slow network |
| O8 | Partial delivery failure (some recipients accepted, some rejected by the SMTP server) | Surfaced per-recipient. Never reported as a blanket success when part of it failed |
| O9 | Compose window closed without sending | No-op. Nothing is sent, nothing is silently queued for later |
| O10 | Every send attempt | Logged (recipients, subject, which attachments, which SMTP account, success/failure) so "was this invoice emailed, and to whom" has a durable answer distinct from the invoice's own immutable snapshot |

---

## 9. Recurring invoices

| # | Case | Expected behaviour |
|---|---|---|
| R1 | Monthly rule set to the 31st | Clamp to the last day of shorter months. Feb → 28/29, Apr → 30 |
| R2 | Feb 29 on a non-leap year | Clamp to Feb 28 |
| R3 | Job runs twice for the same occurrence | Idempotent on `(rule_id, occurrence_date)` — one invoice only. **P1** |
| R4 | Job doesn't run (outage) for several days | On recovery, generate missed occurrences as drafts with their **correct original dates**, not today's |
| R5 | Client archived while a rule is active | Rule auto-pauses; user notified |
| R6 | Rate changed on the client | Applies to future occurrences from the change date; existing drafts unaffected unless regenerated |
| R7 | Tax treatment changed on the client | Next generated draft picks up the new treatment. Existing unissued drafts show a "treatment changed" warning |
| R8 | Auto-issue enabled and the compliance check fails | Falls back to draft and notifies. **Never auto-issue a non-compliant invoice.** **P1** |
| R9 | Rule with an occurrence count reaching zero | Rule completes and is archived, not deleted |
| R10 | User pauses mid-cycle then resumes | Resumes from the next scheduled occurrence; skipped periods are not backfilled unless requested |
| R11 | Tenant timezone changed | Next run recalculated in the new timezone; no duplicate or skipped occurrence at the transition |
| R12 | Tax rate changes between rule creation and generation | The generated invoice uses the rate table for its own invoice date |

---

## 10. Expenses and receipts

| # | Case | Expected behaviour |
|---|---|---|
| E1 | Receipt uploaded, expense never completed | Orphan receipt is retained and listed under `Unprocessed receipts`. Never silently discarded |
| E2 | OCR misreads the total | Low-confidence fields highlighted; user correction always wins and is never overwritten by a re-run |
| E3 | OCR provider down | Falls straight to manual entry with no error dialog. The upload still succeeds |
| E4 | Receipt is a multi-page PDF | All pages retained; OCR reads page 1 by default with a page selector |
| E5 | Same receipt uploaded twice | Deduplicated by content hash; user is told it already exists and shown the existing expense |
| E6 | Expense in a foreign currency | FX at expense date; both original and CAD retained |
| E7 | Expense tax recorded but user is not registered | `itc_eligible = false`. The tax is part of the cost, not a credit. **P1** |
| E8 | User registers mid-year | ITC eligibility applies from the registration effective date forward. Prior expenses are not retroactively eligible |
| E9 | Meals and entertainment | 50% deductibility limit applied in reporting, with the full amount still recorded. The limit is shown, not hidden |
| E10 | Mixed personal/business expense | `business_use_pct` applied in reporting; the full receipt amount is retained for the record |
| E11 | Capital purchase (laptop, equipment) | Flagged as capital, excluded from ordinary expense deduction, surfaced separately for CCA treatment by the accountant. Product does **not** compute CCA |
| E12 | Rebilled expense | Recorded as both an expense and an invoice line. Must not be double-counted in the P&L |
| E13 | Receipt file corrupted or unsupported type | Rejected at upload with the accepted formats named. Type validated by magic bytes, not extension |
| E14 | Very large image from a phone camera | Compressed for storage and display; original retained if within the size cap |
| E15 | Expense dated in a closed prior year | Permitted with a warning that the year may already be filed |

---

## 11. Templates

| # | Case | Expected behaviour |
|---|---|---|
| M1 | Imported template from an unknown schema version | Rejected with the reason. Never partially applied |
| M2 | Imported template omits the compliance block | Compliance block is injected automatically. It is not user-removable. **P1** |
| M3 | Template with an unreadable colour combination | Contrast validated at save; below 4.5:1 for body text is blocked with an explanation |
| M4 | Very long business or client name | Wraps to two lines, then truncates with a tooltip. Never overlaps adjacent blocks |
| M5 | Many line items overflowing one page | Paginates with repeated column headers and `Page n of m`. Totals never split across a page break. **P1** |
| M6 | Logo is a huge PNG or a non-square aspect | Constrained to the template's box, aspect preserved, downscaled on upload |
| M7 | Logo with a transparent background on a coloured header | Preview shows the actual composite; a light/dark variant is offered |
| M8 | Template deleted while invoices reference it | Archived, not deleted. Version history retained for re-rendering |
| M9 | Non-Latin characters in names or descriptions | Font subset covers Latin Extended, French accents, and common symbols. Missing glyphs are detected at render and reported, never rendered as boxes |
| M10 | User sets a template as default for a client, then archives it | Client falls back to the tenant default with a notice |
| M11 | Extremely long line item description | Wraps within the cell; the row grows. Never clipped silently |

---

## 12. Reporting and projection

| # | Case | Expected behaviour |
|---|---|---|
| P1 | First-year user with two months of data | Projection is shown but clearly labelled low-confidence, with the extrapolation method visible |
| P2 | Highly seasonal or lumpy income | Straight-line extrapolation would mislead. Offer declared-income mode prominently and show actual vs. declared variance |
| P3 | User declares an income figure that conflicts with invoices | Show both, show the gap. Do not silently prefer one |
| P4 | Expenses exceed revenue | Net loss displayed correctly; set-aside is $0 with an explanation, not a negative number |
| P5 | Fiscal year ≠ calendar year | Sole proprietors generally use the calendar year for income tax; GST filing periods may differ. Keep the two calendars separate in the UI |
| P6 | Cash vs. accrual basis | State which basis the report uses. Without payment tracking, only accrual is possible — say so rather than implying otherwise |
| P7 | Income tax brackets change | Effective-dated parameters, same as sales tax. Projections use the parameters for the projection year |
| P8 | CPP estimate | Self-employed pay both halves, above the basic exemption, capped at the earnings ceiling. Show the components, not just the total |
| P9 | User asks "how much do I owe" | Never answered as a bill. Framed as a **recommended set-aside**, with assumptions visible and an estimate label |
| P10 | GST collected shown as revenue | Never. Displayed as a separate liability figure with the words "held for CRA" |
| P11 | Projection viewed mid-December vs. mid-January | Year boundary handling: December shows the closing year, January defaults to the new year with the prior year one click away |

---

## 13. Data, input, and platform

| # | Case | Expected behaviour |
|---|---|---|
| D1 | Amount entered as `1,234.56` or `$1 234,56` | Separators and symbols stripped on paste; parsed and reformatted on blur |
| D2 | Amount with more than 2 decimals | Rounded on blur with the change visible, not silently truncated |
| D3 | Quantity `0` on a line item | Permitted (renders as a $0 line); a total of exactly $0 triggers confirmation |
| D4 | Extremely large amount (>$99,999,999) | Rejected with a field-level message rather than overflowing the column |
| D5 | Emoji or control characters in a description | Stored; render substitutes unsupported glyphs and warns rather than producing boxes |
| D6 | Postal code format mismatched to country | Validated by country, warned not blocked — international addresses vary |
| D7 | Address with no province for a Canadian client | Blocked for `taxable` clients (the rate depends on it), permitted otherwise |
| D8 | Browser back during invoice creation | Draft autosaves every few seconds; navigation never loses work |
| D9 | Two tabs editing the same draft | Optimistic concurrency by version; the second save shows a conflict with both values, never a silent overwrite |
| D10 | Offline mid-edit | Draft buffered locally, synced on reconnect. Issuing requires connectivity and says so |
| D11 | Session expires mid-form | Re-authenticate in place; form state preserved across the OTP round trip |
| D12 | Very slow connection at month end | Issue action is optimistic in the UI but the server transaction is authoritative; duplicate submissions deduplicated by idempotency key |
| D13 | Full data export requested | Always available, complete, machine-readable. No lock-in — this is a trust feature |
| D14 | Tenant closure with statutory retention still running | Export offered, account closed, records retained for the statutory period. Stated plainly rather than implying full erasure |
| D15 | Print an invoice from the browser | Print stylesheet matches the generated PDF. A browser print must not produce a different-looking document than the one the client received |

---

## 14. Test priorities

If only a subset can be automated first, this is the order.

1. **X1–X6, X11, X13, X20** — tax derivation, effective dating, treatment states. Wrong output here is unrecoverable.
2. **T1–T4** — cross-tenant isolation. Run as a merge gate on every route.
3. **N1–N4** — numbering concurrency and gaplessness.
4. **L1, L14, X4** — immutability and historical reproduction.
5. **S1** — zero-rated exports counting toward the threshold.
6. **R3, R8** — recurring idempotency and the auto-issue compliance gate.
7. **E7** — ITC eligibility gated on registration status.

Everything above is a golden-file test where possible: fixed input, fixed expected output, byte-compared. Tax and rendering are exactly the domains where snapshot testing earns its keep.
