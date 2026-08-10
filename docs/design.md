# Design System

**Companion to:** `problem-statement.md`, `architecture.md`, `datamodel.md`
**Direction:** "Sovereign Ledger" — financial-blue/compliance-green/set-aside-gold, block-based composition
**Status:** Shipped 2026-08-10 (`implementation_plan.md` Sovereign Ledger redesign, phases A-J)

**2026-08-10 note:** This document originally specified a "Figma UI" system (blue accent, five-colour Figma brand spectrum for tax states). That system shipped and ran in production for Phase 1-4. It has since been fully replaced by **Sovereign Ledger**, whose token brief and mockups live in `docs/screens/DESIGN.md` — this document is now the merged, living spec; `docs/screens/DESIGN.md` is kept as the original source reference, not a second spec to keep in sync by hand. Sections below reflect what actually shipped, including the deliberate deviations from the original brief (noted inline with ⚠️, matching `implementation_plan.md`'s convention).

---

## 1. Design thesis

The product handles money that isn't the user's, on documents that are legal records. The interface should feel like a **precision instrument, not a marketing site** — dense without being cluttered, using colour as signal rather than decoration, never asking the user to admire it. Sovereign Ledger's own vocabulary carries this now: financial-blue for structure and interaction, compliance-green for "this is correct/complete," set-aside-gold for "this needs your attention or is being held aside," and error-red reserved for genuinely wrong states. Three hues, not five — a deliberate narrowing from the earlier Figma-spectrum system (see §2.3's history note).

Three principles carried through every decision below:

**Blocks, not pages.** Every surface is composed of self-contained blocks with a consistent anatomy — header row, body, optional footer action. This mirrors the invoice itself, which is also a stack of blocks. The same mental model runs from the app chrome down into the document being produced.

**Colour is meaning.** Financial Blue, Compliance Green, and Set-aside Gold are each rationed to one job: blue for interactive elements and chrome, green/gold/red for tax and payment states, never decoration. A user must be able to glance at a list of thirty invoices and read their tax treatment by colour alone.

**Quiet by default, loud on consequence.** Issuing an invoice is irreversible. Crossing the small supplier threshold changes a legal obligation. These moments get the only visual weight in the product; everything else is neutral greys and hairlines.

---

## 2. Colour tokens

### 2.1 Foundation — Sovereign Ledger neutrals

```
--color-bg-default        #FFFFFF   app canvas, block surfaces
--color-bg-secondary      #F8FAFC   page background behind blocks
--color-bg-tertiary       #F1F5F9   input wells, table zebra
--color-bg-hover          #F1F5F9   row and button hover
--color-bg-pressed        #E2E8F0
--color-bg-selected       #E6ECF3   selected row (accent-tinted)

--color-border-default    #E2E8F0   the workhorse hairline
--color-border-strong     #CBD5E1   input borders
--color-border-focus      #1A365D   focus ring
--color-border-subtle     #F1F5F9   internal table rules

--color-text-primary      #0F172A   headings, values, amounts
--color-text-secondary    #64748B   labels, metadata, helper text
--color-text-tertiary     #94A3B8   placeholders, disabled
--color-text-caption      #64748B   helper text, timestamps
--color-text-onbrand      #FFFFFF
--color-text-link         #1A365D
```

### 2.2 Accent — Financial Blue

```
--color-accent-default    #1A365D   primary actions, focus, selection
--color-accent-hover      #15294A
--color-accent-pressed    #0F1D36
--color-accent-subtle     #E6ECF3   backgrounds for accent surfaces
--color-accent-border     #B8C7DA
```

Used **only** for interactive affordances, the current selection, and app chrome (sidebar active state uses green — see §2.3). Never for decoration, never for illustration, never for a hero gradient.

### 2.3 Semantic assignments — Compliance Green / Set-aside Gold / Error Red

**History note:** the original Figma-derived system used five brand hues (purple/blue/grey/green/red/orange) to distinguish tax states. Sovereign Ledger narrows this to three semantic hues — compliance-green, set-aside-gold, error-red — plus neutral grey. Shipping this required a real remap, not a find-replace, since the two systems don't have a 1:1 hue mapping. The remap actually shipped (`clients_router`/`Clients.tsx`, `implementation_plan.md` Sovereign Ledger Phase C):

| Token | Hex | Assigned meaning |
|---|---|---|
| `--color-state-taxable` / `--color-status-paid` | `#2F855A` (Compliance Green) | **Taxable / Paid / active collection** — tax is being correctly collected, or money has arrived |
| `--color-state-zero-rated` / `--color-status-attention` | `#B7791F` (Set-aside Gold) | **Zero-rated export / attention / partially-paid** — a special case that needs the user's awareness, or money being held aside |
| `--color-state-unregistered` | `#64748B` (neutral grey) | **Not charged, not registered, exempt, draft** — deliberately grey, not a colour: the absence of an active position |
| `--color-status-overdue` | `#C53030` (Error Red) | Overdue / error / destructive — the one hue reserved for genuinely wrong states |

**Why zero-rated shares gold with "attention" rather than keeping its own hue.** The five-hue system gave zero-rated a distinct blue specifically so it read as "an active tax position, not an absence." Sovereign Ledger's narrower vocabulary doesn't have a fourth hue to spend on that distinction, so zero-rated instead borrows gold's "special case, pay attention" meaning — a US client's invoice is not wrong (it's not red), but it is exactly the kind of case (`edgecases.md` X12's non-residency-evidence nag) where a user should actually look. Unregistered stays grey either way, since that's genuinely nothing, not a special case.

**Client list tax badge — an honest label, not the mockup's compound figure.** `docs/screens/clients.png` shows a "GST + PST (12%)" style compound badge. What shipped (`Clients.tsx`'s `taxLabel()`) is `{region} — {rate}% HST` derived from the real seeded `tax_rate` table (e.g. `ON — 13% HST`), because PST/RST is an invoice-level opt-in flag (`include_provincial_sales_tax`), not a stored per-client default — labelling every Ontario client with a PST rate they may never actually be charged would show data the record doesn't have. ⚠️ narrower than the original mockup, by design.

### 2.4 Semantic surfaces

```
--color-success-bg        #E6F4EC    --color-success-fg    #2F855A
--color-warning-bg        #FBF0DF    --color-warning-fg    #B7791F
--color-danger-bg         #FBEAEA    --color-danger-fg     #C53030
--color-info-bg           #E6ECF3    --color-info-fg       #1A365D
```

### 2.5 Dark mode

Still deferred, tokens still named so it is a value swap, not a rewrite. The invoice **document** never inverts — a printed invoice is always dark ink on white paper, regardless of app theme. This is a hard rule: the preview must show what the client will receive.

---

## 3. Typography

**Inter** for the interface, **JetBrains Mono** for data — designed for small sizes and dense data, both with excellent tabular figures. No display face, no serif, no pairing beyond these two. In a product where a misread digit costs money, personality in the type is a liability.

```
--font-ui        'Inter Variable', 'Inter', system-ui, -apple-system, sans-serif
--font-mono      'JetBrains Mono', ui-monospace, monospace
```

Both are self-hosted via `@fontsource-variable/inter` and `@fontsource/jetbrains-mono` (no external network dependency — verified against the packages' own `@font-face` declarations, not assumed) rather than the Roboto Mono reference this document originally specified, which was never actually loaded by any build before the Sovereign Ledger redesign shipped a font pipeline for the first time. `--font-mono` backs the invoice document's dates/amounts and select high-attention figures (the Clients list's Outstanding column). It is not yet a blanket rule on every `.amount` cell app-wide — most ledger/table amounts still render in body Inter with `tabular-nums`, which is a reasonable next increment rather than a gap in what shipped.

### Type scale

Only `--text-display` exists as a literal CSS custom property (§13); the rest below are baked into per-selector rules in `index.css` rather than exposed as reusable tokens — the "Token" column names the concept, not something you can actually reference as `var(...)`.

| Concept | Size / line | Weight | Use |
|---|---|---|---|
| `--text-display` | 32 / 40 | **700** | Dashboard headline figure — and, as of the Sovereign Ledger redesign, page `<h1>` too (see below) |
| `--text-h1` (`h1` selector) | 32 / 40 | **700** | Page title — promoted to display size/weight 2026-08-10; the original 24/32/600 spec was superseded rather than kept as a distinct smaller size |
| `--text-h2` (`h2` selector) | 18 / 24 | 600 | Block header — unchanged |
| `--text-body` | 13 / 20 | 400 | Default body, table cells — unchanged |
| `--text-label` (`label` selector) | 11 / 16 | 500 | Field labels — unchanged |
| `--text-caption` (`.caption` class) | 11 / 16 | 400 | Helper text, timestamps — unchanged |

`--text-h3`/`--text-body-strong` from the original spec were never implemented as distinct rules either before or after this redesign — not a regression, just never built.

13px body is deliberate. It reads as a tool rather than a website, and it lets a ledger row fit meaningfully more information without scrolling.

### Numeric typography — non-negotiable rules

- **All money and quantities use tabular figures** (`font-variant-numeric: tabular-nums`). Columns of numbers must align on the decimal or the user cannot scan them.
- Amounts are **right-aligned**, always.
- Currency is shown as `CAD 7,200.00`, not `$7,200.00`, wherever both CAD and USD can appear in the same view. Ambiguous dollar signs are how people misread a total by 40%.
- Negative amounts use a minus sign and `--color-status-overdue`, never parentheses and never colour alone.
- Tax rates render to their true precision: `13%`, `9.975%` — never rounded to `10%`.

### Label case

Sentence case throughout, including buttons and column headers. `Invoice date`, not `Invoice Date`. Title case in a data-dense UI adds visual noise without adding information.

---

## 4. Spacing, radius, elevation

### 8pt grid with a 4pt half-step

```
--space-1   4px     --space-5   24px
--space-2   8px     --space-6   32px
--space-3   12px    --space-7   48px
--space-4   16px    --space-8   64px
```

Block padding is `--space-4` (16px) on mobile, `--space-5` (24px) on desktop. Gap between blocks is always `--space-4`. Field-to-field vertical rhythm is `--space-3`.

### Radius — per-component-type, not one shared scale

```
--radius-xs    2px     small chips
--radius-badge 2px     badges — a sharper, "stamped" look for status indicators
--radius-sm    4px     buttons, inputs
--radius-md    8px     blocks, cards, panels, the invoice document
--radius-lg    8px     modals, popovers (shares --radius-md's value)
--radius-full  9999px  avatars, count pills, circular icon buttons
```

Small radii read as precision. A 16px radius on a financial record looks like a consumer app and undermines the document's seriousness. Sovereign Ledger widened blocks/cards from the original 6px to 8px (still tight relative to consumer norms) and gave badges their own 2px token distinct from buttons/inputs — a badge is a stamp, not an affordance, and reads more like one at a sharper corner than a shared 4px would give it.

### Elevation — borders first, shadows last

```
--elev-0   border: 1px solid var(--color-border-default)      blocks (default)
--elev-1   0 1px 3px rgba(0,0,0,0.06)  + border                dropdowns
--elev-2   0 4px 12px rgba(0,0,0,0.10) + border                popovers, toasts
--elev-3   0 12px 32px rgba(0,0,0,0.14)                        modals
```

Surfaces separate with hairlines, not shadows. Blocks in this product sit flat on `--color-bg-secondary` with a single-pixel border. Shadow appears only when something genuinely floats above the plane. ⚠️ `--elev-*` values above were never implemented as CSS custom properties in any shipped version of this app (Figma-era or Sovereign Ledger) — they describe an intent that shadows-when-floating still roughly matches in practice (modals/dropdowns do use inline box-shadow), but there's no token to point to.

---

## 5. The block system

Every screen is a vertical or grid stack of **blocks**. A block is the only container primitive. There are no cards, panels, wells, or sections — one abstraction, used everywhere.

### Anatomy

```
┌──────────────────────────────────────────────────────┐
│  Block header          [optional action] [overflow ⋯]│  48px, border-bottom
├──────────────────────────────────────────────────────┤
│                                                      │
│  Block body                                          │  padding 24px
│                                                      │
├──────────────────────────────────────────────────────┤
│  Block footer (optional)                     [action]│  56px, border-top
└──────────────────────────────────────────────────────┘
   radius 8px · border 1px #E2E8F0 · background #FFFFFF
```

### Block variants

| Variant | Purpose | Distinguishing treatment |
|---|---|---|
| `block/default` | Everything | Neutral border, white surface |
| `block/metric` | A single figure with a label and delta | `--text-display` figure, sparkline slot |
| `block/table` | Ledger, list views | Body padding removed; table meets the border |
| `block/form` | Grouped input fields | Two-column label/field on desktop, stacked on mobile |
| `block/alert` | Threshold warnings, missing evidence | Left border 3px in the semantic colour, tinted background |
| `block/document` | Invoice preview | Fixed paper aspect, always light, inner shadow |

### Grid

12 columns, `--space-4` gutter, max content width 1280px.
Standard layouts: `12` (full), `8 + 4` (content + sidebar), `6 + 6` (comparison), `3 × 4` (metric row), `4 × 3` (template gallery).

Breakpoints: `sm 640` · `md 768` · `lg 1024` · `xl 1280`. Below `md`, all grids collapse to a single column and blocks go edge-to-edge with 16px page padding.

---

## 6. Component specifications

### Buttons

| Variant | Fill | Text | Border | Use |
|---|---|---|---|---|
| Primary | `--color-accent-default` | white | none | One per view. `Issue invoice`, `Save` |
| Secondary | white | `--color-text-primary` | `--color-border-strong` | `Cancel`, `Preview` |
| Ghost | transparent | `--color-text-secondary` | none | Toolbar, table row actions |
| Danger | white | `--color-status-overdue` | `--color-status-overdue` (`#C53030`) | `Cancel invoice`, `Delete` |
| Danger solid | `--color-status-overdue` | white | none | Confirmation modal only |

Sizes: `sm 28px` · `md 32px` (default) · `lg 40px` (primary page actions). Radius `--radius-sm`. Horizontal padding `--space-3`. Icon-only buttons are square at the same heights.

**Focus:** 2px `--color-accent-default` ring at 2px offset. Visible on keyboard focus, always, no exceptions for aesthetics.

### Inputs

32px height, `--radius-xs`, 1px `--color-border-strong`, 8px horizontal padding, `--text-body`. Focus replaces the border with `--color-accent-default` and adds the ring. Error state uses `--color-status-overdue` border with the message below in `--text-caption`.

Labels sit above the field in `--text-label` / `--color-text-secondary`. Required fields are marked by an asterisk in `--color-status-overdue` and announced to assistive tech — never by colour alone.

**Money inputs**: right-aligned, tabular figures, currency prefix in a non-editable adornment, formats on blur, accepts paste with symbols and separators and strips them silently.

### Badges — tax treatment and status

Height 20px, `--radius-badge` (2px — sharper than buttons/inputs, see §4), `--text-label`, uppercase, 6px horizontal padding, tinted background with the full-strength colour as text.

```
● Taxable / Paid        Compliance Green  #2F855A on #E6F4EC
● Zero-rated / Attention  Set-aside Gold  #B7791F on #FBF0DF
○ Not registered / Draft   neutral grey  #64748B on #F1F5F9
● Overdue                Error Red       #C53030 on #FBEAEA
```

Three semantic hues, not the original five (§2.3's history note) — filled dot for an active/attention-worthy state, hollow dot for its absence. Colour is never the only carrier — the label always states the treatment (e.g. the Clients list's honest `ON — 13% HST` region+rate label, not a bare colour swatch, §2.3).

### Tables

Row height 44px (48px on touch). Header row `--text-label`, `--color-text-secondary`, `--color-bg-secondary` background, sticky on scroll. Rules between rows are `--color-border-subtle`; the outer boundary is `--color-border-default`. Hover fills `--color-bg-hover`. Row actions reveal on hover on desktop and live in an overflow menu on touch.

**Amount columns are always the rightmost columns and always right-aligned.** Totals rows use `--text-body-strong` with a 2px top border.

### Toasts and alerts

Toasts bottom-right, `--elev-2`, auto-dismiss 5s, never for errors that need action. Persistent alerts use `block/alert` inline where the problem is, not floating.

---

## 7. Application shell *(shipped 2026-08-10 — Sovereign Ledger Phase B)*

```
┌────────────┬──────────────────────────────────────────────────┐
│  Logo      │  Topbar — page title · Create Invoice · 🔔 ? 👤   │
│            ├──────────────────────────────────────────────────┤
│ +Add       │                                                  │
│  Expense   │   Page background #F8FAFC                        │
│            │   ┌────────────────────────────────────────────┐ │
│  Dashboard │   │  block                                     │ │
│  Invoices  │   └────────────────────────────────────────────┘ │
│  Expenses  │   ┌──────────────────┐ ┌───────────────────────┐ │
│  Clients   │   │  block           │ │  block                │ │
│  Reports   │   └──────────────────┘ └───────────────────────┘ │
│  Settings  │                                                  │
│            │                                                  │
│  Sign out  │                                                  │
└────────────┴──────────────────────────────────────────────────┘
```

Business profile, Email accounts, and Recurring invoices — each a top-level nav item in the original brief — consolidated under **Settings** as of the Phase H re-skin sweep, matching `docs/screens/DESIGN.md`'s leaner sidebar; each is still one click away via a Settings hub page rather than buried. Templates (new/edit) nest under Settings too, since they're only ever reached from within Business profile, never a standalone destination. lucide-react icons replace the earlier icon-font assumption, `lucide-react` having been picked specifically for this redesign (no icon library existed before it).

Sidebar collapses to a slide-in menu below `md` (mobile topbar shows a plain text wordmark rather than the full logo lockup — tested and found illegible at 28px, full logo used only where it has room). ⚠️ **Deviation from the original brief:** the topbar does not show a persistent tax-registration-status chip (`Not registered` / `Registered · ...`) as this section originally specified — that never got built in this redesign and remains a real gap, not a deliberate cut. The Dashboard's onboarding block and Business profile page are still the only places that state is visible. Bell and Help icons ship as visual placeholders only (`title="...(coming soon)"`, no click handler) — no notifications backend or support destination exists yet to wire them to.

---

## 8. Key screens

### 8.1 Dashboard *(shipped 2026-08-08 — `implementation_plan.md` 3.2-3.9, 3.12; remapped 2026-08-10 — Sovereign Ledger Phase D)*

**2026-08-10 remap, on top of the 2026-08-08 shipment below:** the headline became **"How much is mine?"** (adopting this document's own §8.1 speculative phrase) with a "Year-to-date projection for {year}" subtitle. The instalment warning moved from a small bordered tile into a full-width Error Red banner above the tiles, so it reads as urgent rather than as one metric among several. Two new top tiles — **Total invoiced** and **Estimated expenses** — read `income_service.ytd_actuals()`, a figure the projection service already computed internally for its extrapolation ratio but had previously discarded rather than exposed; no new aggregation logic, just plumbing. The set-aside tile keeps its expand-in-place assumptions disclosure from the original ship, restyled with the gold left-border treatment and "View logic"/"Hide logic" copy. The quarterly GST/HST table (below) is joined, not replaced, by a new **Recent invoices** table sourced from the existing `GET /invoices` (now carrying `client_name` via a small join added specifically so this tile wouldn't show a raw client UUID — a real gap the original endpoint had, caught while building this table, not part of the original plan).

Metric tiles across the top in a responsive grid, then a quarterly GST/HST table, then Reports.

```
┌──────────┐┌──────────┐┌──────────┐┌──────────┐
│ Set aside││ Threshold││ GST/HST  ││Instalment│
│ for tax  ││ tracker  ││ held for ││ reminder │
│ $21,400  ││ 72%      ││ CRA      ││(only when│
│ estimate ││ ▓▓▓▓▓░░  ││ $6,500   ││ it       │
└──────────┘└──────────┘└──────────┘│ applies) │
                                     └──────────┘
```

Shipped with four tiles built directly from Phase 3's own deliverables (set-aside, threshold, GST/HST net-owing, instalment warning) rather than the two additional revenue tiles (**Billed YTD**, **Collected**) originally sketched here — those read from ordinary invoice/payment aggregates already available elsewhere (Reports, Clients roll-up) and weren't part of what Phase 3 was building. Worth revisiting as a Dashboard polish pass later, not a gap in Phase 3 itself.

The **set-aside block** is the product's signature element. It answers the question the user actually has — *how much of this is mine* — and it is the only place `--text-display` appears. It expands **in place** (not a modal, not a separate page — the tile grows to full width so the assumptions have room) to show net business income, estimated federal tax, estimated provincial tax, estimated CPP, the recommended set-aside percentage, and a plain accrual-basis / estimate disclaimer. From there, a **declared income** option is always one click away — entering a figure switches the whole block to declared mode, shows the gap against the derived (extrapolated) estimate, and "Use derived instead" reverts it, matching P3's "show both, never silently prefer one."

The **threshold tracker** uses a progress bar that shifts grey → `--color-status-attention` at 75% → `--color-status-overdue` at 90%, with copy that names the consequence rather than the number: *"$8,400 from the $30,000 registration threshold. Crossing it changes what you must charge."* A second line discloses that the figure is this account only (S9) — the threshold is legally shared across any associated businesses the product can't see.

The **instalment reminder** tile only renders when it applies (projected net income tax + CPP owing over the CRA's $3,000 threshold) — it never occupies dashboard space with a "no reminder" state. It is deliberately silent about GST/HST net-owing, which is a separate remittance with its own mechanics, not part of the same $3,000 test.

A **year selector** (← / →) sits above the tiles, defaulting to the current calendar year — this is Phase 3's answer to keeping the income-tax calendar (always calendar-year) and the GST filing calendar (quarterly, shown in the table below the tiles) visibly separate without needing distinct navigation for each.

The **year-end accountant pack** *(shipped 2026-08-08 — `implementation_plan.md` 3.11)* lives in the Reports block below the tiles, alongside the existing P&L CSV export: a year picker (defaulting to last year, the natural "closing out" case) and a **Generate pack** button. There's no separate progress UI for the zip assembly — it's fast enough at this data scale to just be the button's loading state — and the result is a plain download link plus a one-line reminder of what's inside and that the link expires in 7 days. A storage failure surfaces in the same red error-text style as everything else on this screen, never a blank retry with no explanation.

### 8.2 Invoice builder *(rebuilt 2026-08-10 — Sovereign Ledger Phase F, on top of the pre-existing single-column form)*

Split view: form left, live document preview right (sticky, `max-width: 480px`). The right-hand preview is not a bespoke mini-layout — it's the same `<InvoiceDocument>` component §9 describes, rendering real backend-computed data (`POST /invoices/preview-document`, debounced ~300ms) rather than a client-side approximation, so what the user sees while building is byte-for-byte the shape they'll get once issued.

A **Compliance checklist** (§8.9) sits below the form, tracking Business name / BN number / Client address / Tax breakdown. Below `lg`, the preview and form both go single-column (checklist stays below the form) rather than moving behind a toggle as originally specified — the toggle was never built; scrolling was judged sufficient at this data density.

Form blocks in order: **Client** → **Dates & terms** → **Line items** → **Notes**, followed by the checklist. ⚠️ The **read-only Tax block** with inline override described below was not built as its own dedicated block — tax lines render inside the live document preview itself (subtotal/tax breakdown/total), and any `tax/engine.compute()` warnings (e.g. X12's missing non-residency evidence) surface as alert blocks above the checklist, but there is no `[Override]` affordance in the UI yet. Overriding a derived tax treatment today requires setting `treatment_override_reason` directly on the client record (§2.3, `edgecases.md` X19) rather than at the point of invoicing — a real gap, not a deliberate cut.

The **tax block is read-only and always visible.** It states the derived treatment, the jurisdiction it came from, and why:

```
┌───────────────────────────────────────────────────────┐
│ Tax                                        [Override] │
├───────────────────────────────────────────────────────┤
│  ● Zero-rated 0%                                      │
│                                                       │
│  Born West Inc. is in the United States, so this      │
│  supply is a zero-rated export. It still counts       │
│  toward your $30,000 registration threshold.          │
│                                                       │
│  ⚠ No non-residency evidence on file.  [Upload]       │
└───────────────────────────────────────────────────────┘
```

Overriding requires a typed reason, which is stored on the client record and audited. Making the override *slightly* effortful is the point — the derived value is right far more often than the user's assumption.

**The line item table** switches layout by unit: choosing `hours` reveals `Hours × Rate` columns and an optional `Pull from time log` action. This directly serves the CRA-defensibility requirement — hours and rate must be visible on the document.

**The issue action** lives in a sticky footer bar with the total, and opens a confirmation summarizing what cannot be undone: number allocated, tax frozen, corrections require a credit note.

⚠️ **None of the three paragraphs above (dedicated Tax block with inline override UI, the hours/rate unit-switching line-item table, the sticky confirming footer) have been built** — this was true before the Sovereign Ledger redesign and remains true after it; the redesign rebuilt the surrounding layout (this section's opening paragraphs) without adding these specific pieces. Line items today are a flat description/qty/amount row set (the schema's `unit` field exists and is sent as `"fixed"` but has no picker), and `POST /invoices/{id}/issue` enforces compliance server-side (`invoices_service.issue_invoice`'s `ComplianceError`) with no confirmation dialog client-side — verified fail-safe (§8.9) but not the guided experience described here. Worth scoping as real future work, not re-litigated by this redesign.

### 8.3 Ledger *(tokens/classes re-skinned to Sovereign Ledger 2026-08-10 — Phase H; layout otherwise unchanged by this redesign)*

Filter bar above a table block. Filters as removable chips: date range, client, status, tax treatment, amount range, currency. Filter state lives in the URL so a view is shareable and survives refresh. Saved presets appear as a row of chips beneath.

Columns: `Number · Date · Client · Service period · Tax · Amount · Status`. The tax column shows the treatment badge, not a percentage — this is what makes a year's work readable at a glance.

Group-by-month is on by default with sticky month headers carrying that month's subtotal, which answers the *"in which month, how much"* requirement without a separate report.

### 8.4 Client detail *(list view remapped 2026-08-10 — Sovereign Ledger Phase C; detail view itself re-skinned only, layout unchanged)*

Header block (name, address, tax treatment, evidence status), then a period roll-up table (month / invoices / billed / collected / outstanding), then an aging block, then the invoice list scoped to the client.

The **Clients list** (one level up from this detail page) gained a new **Outstanding** column and pagination as part of this redesign — `GET /clients/summary`, a `LEFT JOIN` aggregate deliberately not reusing `rollup_service.tenant_aging_report` (which excludes zero-balance and not-yet-due clients; the list needs every client to appear, aging report doesn't). This is the same "amount owed" concept the client detail page's aging block already showed per-client — the list view now surfaces it without a click-through, coloured Error Red when any invoice is overdue.

### 8.5 Expenses

**Receipt-first.** The primary surface is a large drop zone occupying the whole block, not a form:

```
┌───────────────────────────────────────────────────────┐
│                                                       │
│                    ⇪  Drop a receipt                  │
│              or take a photo · or enter manually      │
│                                                       │
└───────────────────────────────────────────────────────┘
```

After upload, a three-field confirmation appears — vendor, date, amount — with OCR values pre-filled and low-confidence fields highlighted in `--color-status-attention`. Category is a single dropdown grouped by T2125 line. Everything else is behind `More details`.

The whole flow is three taps and one glance. If it takes longer than fifteen seconds, expenses do not get logged, and the entire projection layer has nothing to work with.

### 8.6 Template editor *(shipped 2026-08-08 — `implementation_plan.md` 4.2)*

Left: block list with drag handles and visibility toggles. Centre: live document. Right: theme controls — brand colour, accent, font size scale, logo size and position, margins, show/hide optional blocks.

The **compliance block is pinned, marked with a lock icon, and cannot be reordered out or hidden.** Its tooltip explains why: *"Required on every invoice — your client's accountant needs these fields."* Constraint stated as a service to the user rather than as a restriction imposed on them.

**As shipped:** the "compliance block" is the 5 required block types (`supplier`, `document`, `bill_to`, `services`, `totals`) shown as one pinned, undraggable group — their *relative order among themselves* was never meaningful (`pdf_renderer.py` always renders them in a fixed sequence regardless of `blocks` array order), so there was nothing to preserve by letting them be dragged individually. `payment` and `footer` are the two blocks with a drag handle and a visibility toggle; reordering them is the one thing block order actually changes in the rendered PDF. Font scale is a slider (85%-115%, matching `templates/service.py`'s validated range); margins likewise (12mm-30mm). Logo position is a select (`top_left`/`top_center`/`top_right`/`none`) rather than a freeform drag, since the header layout has exactly those three anchor points. The live preview renders against the tenant's real business profile and logo but canned sample client/line-item data (`POST /templates/preview`), debounced ~500ms after the last change, and is never persisted.

### 8.7 Send invoice (compose window) *(shipped 2026-08-07 — `implementation_plan.md` 2.16/2.17)*

A modal, opened from "Email invoice" on an issued invoice's detail view. Never a silent action — opening it never sends anything, and it always ends on an explicit **Send** press, never an implicit one on close.

Layout, top to bottom: **From** (the tenant's configured SMTP account — a select if more than one is set up), **To** and **Cc** as chip inputs (To defaults to the client's on-file email), **Subject** (pre-filled, editable), **Body** (pre-filled plain-text default, editable, generous height), then an **attachments row** — the invoice PDF as a removable chip (checked by default, per `edgecases.md` O5), plus an "Add attachment" control for arbitrary extra documents. Sticky footer: **Cancel** and **Send**, the same irreversibility weight as the invoice builder's issue footer (§8.2) — sending is a real action, styled with the same intent as issuing, not a throwaway toast-dismiss button.

No SMTP account configured: the modal still opens, but the From/To/Cc/Subject/Body fields are replaced with a single message — "No email account configured yet" plus a link to the Email accounts settings page (§8.8) — rather than opening on a dead-end compose form with nowhere to send from.

Unchecking the PDF with no other attachments added doesn't silently send an empty-handed email: **Send** asks for confirmation first (`edgecases.md` O5) — a reminder-only email is legitimate, but never sent without the user seeing that's what's about to happen.

### 8.8 Email accounts (settings) *(shipped 2026-08-07 — `implementation_plan.md` 2.16/2.17)*

A settings page, reachable via **Settings → Email accounts** (moved under the Settings hub 2026-08-10, previously a top-level nav item — see §7). Lists configured SMTP accounts as a table: label, from address, server, and a verified/unverified badge, each row with **Test** (connects and authenticates, sends nothing — the mechanism for confirming a saved password still works, since it is never shown again) and **Remove**. Below the list, an add-account form: label, from name/address, SMTP host/port/security/username, password, and a "default account" checkbox. Credentials are write-only from the moment they're saved — see `edgecases.md` O4.

### 8.9 Compliance checklist (component) *(shipped 2026-08-10 — Sovereign Ledger Phase F)*

A vertical stepper on the invoice builder (§8.2), tracking four items against the invoice currently being built:

```
✓ Business name        Acme Consulting
✓ BN number             123456789RT0001
✓ Client address        On file.
○ Tax breakdown         Pending tax selection.
```

Incomplete items show a hollow dot in `--color-text-secondary`; complete items get a filled Compliance Green circle with a checkmark. **BN number** is treated as complete (not merely skipped) when the business isn't GST/HST-registered at all — an unregistered sole proprietor has nothing to enter here, and showing it as an outstanding task would be actively wrong, not just unhelpful.

**This is advisory UX only, by explicit design, and this was verified rather than assumed.** `POST /invoices/{id}/issue`'s server-side `ComplianceError` (`invoices_service.issue_invoice`) remains the sole enforcement. The checklist has no due-date-ordering check at all, so a due date set before the invoice date shows all four items green — issuing was confirmed to still fail server-side with `Due date can't be before the invoice date.` in this exact state, proving the split fails safe rather than merely looking like it does.

A real, pre-existing gap this component's verification surfaced: the Clients "Add client" form never collected `address_line1`/`city` at all (the schema supported them; nothing in the UI wrote them), which meant **Client address** could never show complete for any client created through the product. Fixed by adding optional address/city fields to client creation — a one-line schema-already-supports-it addition, not a new backend capability.

---

## 9. Invoice document design *(web-rendered preview shipped 2026-08-10 — Sovereign Ledger Phases E-G, alongside the pre-existing PDF renderer)*

**Now genuinely one design, rendered twice, not two designs that happen to agree.** `assemble_invoice_document`/`assemble_preview_document` (`api/src/tallyquo/billing/invoices_service.py`) extract the exact data-assembly logic `render_pdf` already used (draft-vs-issued branching, `template_version_history` pin resolution, payment-instruction/logo rules) into functions shared by the PDF renderer and three new JSON endpoints (`GET /invoices/:id/document`, `GET /public/invoices/:token/document`, `POST /invoices/preview-document`). A single `<InvoiceDocument>` React component (`web/src/components/InvoiceDocument.tsx`) consumes that shape everywhere a human views an invoice in the browser: the builder's live preview (§8.2), the authenticated invoice detail page, and the public share-link page — all three showed a flat subtotal/tax/total table before this redesign; all three now show the same document layout the PDF produces.

**The X4/L14 byte-identical-forever guarantee extends to this new surface**, not just the PDF: an issued invoice's document view was verified — through the actual browser UI, not just the API-level test — to keep showing the original frozen supplier snapshot even after the business profile is edited afterward. Same test performed against the public share-link page with an unauthenticated browser context, same result.

The generated document is a separate design system from the app, sharing only tokens. It is a printed business document, not a web page.

**Layout:** A4 and US Letter, 20mm margins by default (12-30mm, template-configurable since 4.2), single column, logo top-left by default (position configurable since 4.2), document metadata top-right, then bill-to, then services, then totals right-aligned, then payment instructions, then footer.

**Type:** Inter throughout, 10pt body, 9pt tabular figures for the amount table, 18pt document title. Labels `#757575` (verified against `pdf_renderer.py`'s actual `Label` style); body colour is reportlab's default black rather than a deliberately chosen `#1E1E1E` — a pre-existing inaccuracy in this document caught while reconciling it, not a Sovereign Ledger regression; `pdf_renderer.py` itself was untouched by this redesign.

**Colour is minimal by default.** One accent colour, user-chosen, applied to the document title, the table header rule, and the totals rule. Nothing else is coloured. New templates default to Financial Blue `#1A365D` (updated 2026-08-10 from the earlier Figma-blue default — existing templates and already-issued invoices are untouched, since template colour is pinned per-invoice at issue time, not live-computed).

**The tax line renders one of three forms**, exactly as in the reference invoice:

```
GST/HST — 13%:                                    CAD   936.00
GST/HST — 0% zero-rated supply:                   CAD     0.00
GST/HST: Not charged — supplier not yet registered
```

The third form has no amount column at all — it is a statement, not a figure, and formatting it as `CAD 0.00` would imply a tax calculation happened.

**System templates:**

| Template | Character |
|---|---|
| Classic | Serif-free, rule-heavy, conservative. The default. |
| Minimal | Hairlines only, generous whitespace, no fills |
| Modern | Accent-filled header band, sans headings |
| Consulting | Prominent service period and project reference, built for retainer work |
| Trades | Larger line item area, materials/labour split |

---

## 10. Motion

Restrained to the point of near-invisibility. This is an instrument.

```
--motion-fast    120ms cubic-bezier(0.2, 0, 0, 1)    hover, focus, toggles
--motion-base    180ms cubic-bezier(0.2, 0, 0, 1)    dropdowns, expansion
--motion-slow    240ms cubic-bezier(0.2, 0, 0, 1)    modals, drawers
```

Permitted: state transitions, panel expansion, toast entry, skeleton loading, the threshold progress bar animating on data change. Not permitted: scroll-triggered reveals, parallax, entrance animations on page load, animated numbers counting up. A money figure that animates from zero is a money figure the user has to wait to read.

`prefers-reduced-motion: reduce` disables all of it except opacity fades.

⚠️ Like `--elev-*` (§4), `--motion-*` were never implemented as CSS custom properties. The handful of shipped transitions (sidebar slide, settings-card hover) use plain `0.15s`/`0.2s ease` rather than these exact durations/curves — close in spirit, not literally these tokens. `prefers-reduced-motion` is not currently handled anywhere in `index.css`.

---

## 11. Voice and copy

**Errors state what happened and what to do.** They do not apologize and they are never vague.

| Situation | Copy |
|---|---|
| Missing required field on issue | `Add a service period before issuing. Your client's accountant needs it to match the invoice to a period.` |
| Attempt to edit an issued invoice | `Issued invoices can't be edited. Create a credit note or issue a revision instead.` |
| Client has no province | `Add a province for Acme Ltd. The tax rate depends on where your client is, not where you are.` |
| Threshold crossed | `You've passed $30,000 in taxable revenue over the last four quarters. You now need to register for GST/HST and start charging it. Zero-rated exports count toward this total.` |
| OCR uncertain | `Check the amount — the receipt was hard to read.` |
| OTP failed | `That code didn't match. You have 3 attempts left.` |

**Empty states are invitations with a single action.**

| Screen | Copy |
|---|---|
| No invoices | `No invoices yet. Add a client, then bill them — most people are done in about two minutes.` → `Add your first client` |
| No expenses | `Nothing logged yet. Drop in a receipt and we'll pull out the details.` → `Add a receipt` |
| No clients | `Add the people you bill. We'll work out the right tax treatment for each one.` → `Add a client` |

**Every estimated figure is labelled.** The word is *estimate*, always, in `--text-caption` directly beneath the number, with the assumptions one click away. Never "you owe", never "your tax bill". The product prepares; it does not advise.

---

## 12. Accessibility

WCAG 2.1 AA as a floor, with these specifics. **Re-verified 2026-08-10 against the actual shipped Sovereign Ledger values** (computed via the WCAG relative-luminance formula, not estimated):

- `--color-text-secondary` / `--color-text-caption` `#64748B` on white is **4.76:1** — clears AA's 4.5:1 for normal text, but only just; the shipped tokens reuse the same value for both secondary and caption text rather than the original spec's approach of a separately-darkened caption colour, so there's less safety margin than this document originally called for.
- `--color-accent-default` `#1A365D` on white is **12.14:1** — a large improvement over the old accent blue's 2.9:1 (which failed for text and needed a separate darker link colour). Financial Blue is dark enough to use directly as link/focus/body-emphasis text; `--color-text-link` is the same value, no separate variant needed.
- `--color-text-primary` `#0F172A` on white is **17.85:1**.
- ⚠️ **Badge text-on-tint contrast was checked for the first time during this reconciliation and two of three fail AA at the badge's 11px size:** `--color-secondary-default` (Compliance Green) `#2F855A` on `--color-secondary-subtle` `#E6F4EC` is **4.00:1**; `--color-tertiary-default` (Set-aside Gold) `#B7791F` on `--color-tertiary-subtle` `#FBF0DF` is **3.23:1**. Only `--color-status-overdue` (Error Red) on its own subtle background clears the bar at **4.70:1**. This is a real gap introduced by the redesign's badge-tint values, not previously caught because the original Figma-era badges were never audited either — worth a follow-up pass (darken the tint background or the text colour on the two failing badges) before treating badge legibility as verified.
- Never colour alone: every tax badge, status, and error carries a text label; the threshold bar carries a percentage.
- Full keyboard operation of the invoice builder including the line item table (Tab between cells, Enter to add a row, Cmd/Ctrl+Enter to issue).
- Visible focus everywhere, at 2px, never suppressed.
- Money announced to screen readers with currency spelled out: `seven thousand two hundred Canadian dollars`.
- Touch targets 44×44 minimum on mobile; the receipt drop zone is deliberately oversized.
- Form errors associated with fields via `aria-describedby`, and the error summary receives focus on failed submit.

---

## 13. Token reference

**This block is copied verbatim from the shipped `web/src/index.css` `:root` rule (2026-08-10), not re-derived** — it's the actual source of truth, not a paper description of it. `--elev-*` and `--motion-*` tokens from earlier revisions of this document were never implemented as CSS custom properties (elevation/motion values are still expressed inline per-component where used, if at all) — they're omitted below rather than listed as if they exist. Same for `--text-h1` through `--text-caption`: only `--text-display` exists as a literal custom property; the rest of the type scale is baked directly into per-selector rules (`h1`, `h2`, `label`, `th`, `.caption`, etc. in `index.css`) rather than exposed as reusable tokens.

```css
:root {
  /* surface */
  --color-bg-default: #ffffff;
  --color-bg-secondary: #f8fafc;
  --color-bg-tertiary: #f1f5f9;
  --color-bg-hover: #f1f5f9;
  --color-bg-pressed: #e2e8f0;
  --color-bg-selected: #e6ecf3;

  /* border */
  --color-border-default: #e2e8f0;
  --color-border-strong: #cbd5e1;
  --color-border-subtle: #f1f5f9;
  --color-border-focus: #1a365d;

  /* text */
  --color-text-primary: #0f172a;
  --color-text-secondary: #64748b;
  --color-text-tertiary: #94a3b8;
  --color-text-caption: #64748b;
  --color-text-link: #1a365d;
  --color-text-onbrand: #ffffff;

  /* accent -- Financial Blue: interactive elements, focus, app chrome */
  --color-accent-default: #1a365d;
  --color-accent-hover: #15294a;
  --color-accent-pressed: #0f1d36;
  --color-accent-subtle: #e6ecf3;
  --color-accent-border: #b8c7da;

  /* secondary (Compliance Green) / tertiary (Set-aside Gold) */
  --color-secondary-default: #2f855a;
  --color-secondary-subtle: #e6f4ec;
  --color-tertiary-default: #b7791f;
  --color-tertiary-subtle: #fbf0df;

  /* tax + status semantics -- see §2.3 for the full remap rationale */
  --color-state-taxable: #2f855a;       --color-state-taxable-bg: #e6f4ec;
  --color-state-zero-rated: #b7791f;    --color-state-zero-rated-bg: #fbf0df;
  --color-state-unregistered: #64748b;  --color-state-unregistered-bg: #f1f5f9;
  --color-status-paid: #2f855a;         --color-status-paid-bg: #e6f4ec;
  --color-status-overdue: #c53030;      --color-status-overdue-bg: #fbeaea;
  --color-status-attention: #b7791f;    --color-status-attention-bg: #fbf0df;

  /* type */
  --font-ui: 'Inter Variable', 'Inter', system-ui, -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, monospace;
  --text-display: 700 32px/40px var(--font-ui);

  /* space -- only 1 through 6 are defined; nothing shipped needed 7/8 */
  --space-1: 4px;  --space-2: 8px;  --space-3: 12px;
  --space-4: 16px; --space-5: 24px; --space-6: 32px;

  /* radius -- per component type, see §4 */
  --radius-xs: 2px;    --radius-badge: 2px; --radius-sm: 4px;
  --radius-md: 8px;    --radius-lg: 8px;    --radius-full: 9999px;
}
```

Template `theme` JSON (`datamodel.md` §8) is a constrained subset of these tokens: accent colour, font scale multiplier, logo dimensions and position, margins, and block visibility flags. Users pick from the system; they do not extend it. New templates default to `#1A365D` (§9); existing templates keep whatever accent they were saved with.
