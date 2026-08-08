# Design System

**Companion to:** `problem-statement.md`, `architecture.md`, `datamodel.md`
**Direction:** Figma UI design system — block-based composition, Figma colour scheme
**Status:** Draft v0.1

---

## 1. Design thesis

The product handles money that isn't the user's, on documents that are legal records. The interface should feel like a **precision instrument, not a marketing site**. Figma's own UI is the right reference for exactly this reason: it is dense without being cluttered, it uses colour as signal rather than decoration, and it never asks the user to admire it.

Three principles carried through every decision below:

**Blocks, not pages.** Every surface is composed of self-contained blocks with a consistent anatomy — header row, body, optional footer action. This mirrors the invoice itself, which is also a stack of blocks. The same mental model runs from the app chrome down into the document being produced.

**Colour is meaning.** Figma's palette is bright and saturated, which would be noise if used freely. Here it is rationed: the accent blue for interactive elements only, and the brand spectrum reserved for tax states and status. A user must be able to glance at a list of thirty invoices and read their tax treatment by colour alone.

**Quiet by default, loud on consequence.** Issuing an invoice is irreversible. Crossing the small supplier threshold changes a legal obligation. These moments get the only visual weight in the product; everything else is neutral greys and hairlines.

---

## 2. Colour tokens

### 2.1 Foundation — Figma UI neutrals

```
--color-bg-default        #FFFFFF   app canvas, block surfaces
--color-bg-secondary      #F5F5F5   page background behind blocks
--color-bg-tertiary       #EBEBEB   input wells, table zebra
--color-bg-hover          #F5F5F5   row and button hover
--color-bg-pressed        #E6E6E6
--color-bg-selected       #E5F4FF   selected row (accent-tinted)
--color-bg-disabled       #F5F5F5

--color-border-default    #E6E6E6   the workhorse hairline
--color-border-strong     #D9D9D9   input borders
--color-border-focus      #0D99FF   focus ring
--color-border-subtle     #F0F0F0   internal table rules

--color-text-primary      #1E1E1E   headings, values, amounts
--color-text-secondary    #757575   labels, metadata, helper text
--color-text-tertiary     #B3B3B3   placeholders, disabled
--color-text-onbrand      #FFFFFF
--color-text-link         #0D99FF
```

### 2.2 Accent — Figma blue

```
--color-accent-default    #0D99FF   primary actions, focus, selection
--color-accent-hover      #007BE5
--color-accent-pressed    #0066CC
--color-accent-subtle     #E5F4FF   backgrounds for accent surfaces
--color-accent-border     #B3E0FF
```

Used **only** for interactive affordances and the current selection. Never for decoration, never for illustration, never for a hero gradient.

### 2.3 Figma brand spectrum — semantic assignments

Figma's five brand colours map onto the five things this product needs to distinguish at a glance. This is the one place the palette gets to be bright, and it earns it: these are the states a user must never misread.

| Token | Hex | Figma name | Assigned meaning |
|---|---|---|---|
| `--color-state-taxable` | `#A259FF` | Purple | **Taxable** — tax is being collected and is owed to CRA |
| `--color-state-zero-rated` | `#1ABCFE` | Blue | **Zero-rated export** — 0%, but counts toward threshold, ITCs allowed |
| `--color-state-unregistered` | `#B3B3B3` | (neutral) | **Not charged, not registered** — deliberately grey, not a colour |
| `--color-status-paid` | `#0ACF83` | Green | Paid / collected |
| `--color-status-overdue` | `#F24E1E` | Red | Overdue / error / destructive |
| `--color-status-attention` | `#FF7262` | Orange | Warning, threshold approaching, missing evidence |

**Why unregistered is grey and zero-rated is blue.** Both render `$0.00`. Giving zero-rated a real colour and unregistered a neutral encodes the actual difference: one is an active tax position, the other is the absence of one. A user scanning their ledger sees at a glance that their US work is *doing something* in the tax system, which is exactly the misconception §5.1 of the problem statement is fighting.

### 2.4 Semantic surfaces

```
--color-success-bg        #E8FBF3    --color-success-fg    #048A57
--color-warning-bg        #FFF0ED    --color-warning-fg    #C4472A
--color-danger-bg         #FEECE7    --color-danger-fg     #D13A12
--color-info-bg           #E5F4FF    --color-info-fg       #0066CC
```

### 2.5 Dark mode

Deferred past Phase 1, but tokens are named so it is a value swap, not a rewrite. The invoice **document** never inverts — a printed invoice is always dark ink on white paper, regardless of app theme. This is a hard rule: the preview must show what the client will receive.

---

## 3. Typography

**Inter** for the entire interface — Figma's own UI face, designed for small sizes and dense data, with excellent tabular figures. No display face, no serif, no pairing. In a product where a misread digit costs money, personality in the type is a liability.

```
--font-ui        'Inter', system-ui, -apple-system, sans-serif
--font-mono      'Roboto Mono', ui-monospace, monospace
```

### Type scale (Figma UI proportions)

| Token | Size / line | Weight | Use |
|---|---|---|---|
| `--text-display` | 32 / 40 | 600 | Dashboard headline figure only |
| `--text-h1` | 24 / 32 | 600 | Page title |
| `--text-h2` | 18 / 24 | 600 | Block header |
| `--text-h3` | 14 / 20 | 600 | Sub-section, table group header |
| `--text-body` | 13 / 20 | 400 | Default body, table cells |
| `--text-body-strong` | 13 / 20 | 500 | Emphasis, selected labels |
| `--text-label` | 11 / 16 | 500 | Field labels, column headers, eyebrows |
| `--text-caption` | 11 / 16 | 400 | Helper text, timestamps |

13px body is deliberate and Figma-native. It reads as a tool rather than a website, and it lets a ledger row fit meaningfully more information without scrolling.

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

### Radius — Figma-tight

```
--radius-xs   2px    inputs, checkboxes, small chips
--radius-sm   4px    buttons, badges
--radius-md   6px    blocks, cards, panels
--radius-lg   8px    modals, popovers
--radius-full 999px  avatars, count pills
```

Small radii read as precision. A 16px radius on a financial record looks like a consumer app and undermines the document's seriousness.

### Elevation — borders first, shadows last

```
--elev-0   border: 1px solid var(--color-border-default)      blocks (default)
--elev-1   0 1px 3px rgba(0,0,0,0.06)  + border                dropdowns
--elev-2   0 4px 12px rgba(0,0,0,0.10) + border                popovers, toasts
--elev-3   0 12px 32px rgba(0,0,0,0.14)                        modals
```

Figma's interface separates surfaces with hairlines, not shadows. Blocks in this product sit flat on `--color-bg-secondary` with a single-pixel border. Shadow appears only when something genuinely floats above the plane.

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
   radius 6px · border 1px #E6E6E6 · background #FFFFFF
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
| Danger | white | `--color-status-overdue` | `#F24E1E` | `Cancel invoice`, `Delete` |
| Danger solid | `--color-status-overdue` | white | none | Confirmation modal only |

Sizes: `sm 28px` · `md 32px` (default) · `lg 40px` (primary page actions). Radius `--radius-sm`. Horizontal padding `--space-3`. Icon-only buttons are square at the same heights.

**Focus:** 2px `--color-accent-default` ring at 2px offset. Visible on keyboard focus, always, no exceptions for aesthetics.

### Inputs

32px height, `--radius-xs`, 1px `--color-border-strong`, 8px horizontal padding, `--text-body`. Focus replaces the border with `--color-accent-default` and adds the ring. Error state uses `--color-status-overdue` border with the message below in `--text-caption`.

Labels sit above the field in `--text-label` / `--color-text-secondary`. Required fields are marked by an asterisk in `--color-status-overdue` and announced to assistive tech — never by colour alone.

**Money inputs**: right-aligned, tabular figures, currency prefix in a non-editable adornment, formats on blur, accepts paste with symbols and separators and strips them silently.

### Badges — tax treatment and status

Height 20px, `--radius-sm`, `--text-label`, 6px horizontal padding, tinted background at ~12% with the full-strength colour as text.

```
● Taxable 13%          purple    #A259FF on #F4EBFF
● Zero-rated 0%        blue      #1ABCFE on #E5F8FF
○ Not registered       grey      #757575 on #F0F0F0
● Paid                 green     #0ACF83 on #E8FBF3
● Overdue 12d          red       #F24E1E on #FEECE7
● Draft                grey      outline only, no fill
```

Filled dot for an active tax position, hollow dot for its absence. Colour is never the only carrier — the label always states the treatment.

### Tables

Row height 44px (48px on touch). Header row `--text-label`, `--color-text-secondary`, `--color-bg-secondary` background, sticky on scroll. Rules between rows are `--color-border-subtle`; the outer boundary is `--color-border-default`. Hover fills `--color-bg-hover`. Row actions reveal on hover on desktop and live in an overflow menu on touch.

**Amount columns are always the rightmost columns and always right-aligned.** Totals rows use `--text-body-strong` with a 2px top border.

### Toasts and alerts

Toasts bottom-right, `--elev-2`, auto-dismiss 5s, never for errors that need action. Persistent alerts use `block/alert` inline where the problem is, not floating.

---

## 7. Application shell

```
┌────────────┬──────────────────────────────────────────────────┐
│            │  Topbar 56px — page title · search · account     │
│  Sidebar   ├──────────────────────────────────────────────────┤
│  240px     │                                                  │
│            │   Page background #F5F5F5                        │
│  Dashboard │   ┌────────────────────────────────────────────┐ │
│  Invoices  │   │  block                                     │ │
│  Clients   │   └────────────────────────────────────────────┘ │
│  Expenses  │   ┌──────────────────┐ ┌───────────────────────┐ │
│  Reports   │   │  block           │ │  block                │ │
│  Templates │   └──────────────────┘ └───────────────────────┘ │
│            │                                                  │
│  ────────  │                                                  │
│  Settings  │                                                  │
└────────────┴──────────────────────────────────────────────────┘
```

Sidebar collapses to icons below `lg` and becomes a bottom tab bar below `md`. The topbar always shows the current tax registration state as a small persistent chip — `Not registered` / `Registered · 123456789RT0001` — because it changes the meaning of everything else on screen.

---

## 8. Key screens

### 8.1 Dashboard *(shipped 2026-08-08 — `implementation_plan.md` 3.2-3.9, 3.12)*

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

### 8.2 Invoice builder

Split view: form left (`8` cols), live document preview right (`4` cols, sticky). Below `lg`, the preview moves behind a `Preview` toggle.

Form blocks in order: **Client** → **Dates & terms** → **Line items** → **Tax** → **Payment** → **Notes**.

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

### 8.3 Ledger

Filter bar above a table block. Filters as removable chips: date range, client, status, tax treatment, amount range, currency. Filter state lives in the URL so a view is shareable and survives refresh. Saved presets appear as a row of chips beneath.

Columns: `Number · Date · Client · Service period · Tax · Amount · Status`. The tax column shows the treatment badge, not a percentage — this is what makes a year's work readable at a glance.

Group-by-month is on by default with sticky month headers carrying that month's subtotal, which answers the *"in which month, how much"* requirement without a separate report.

### 8.4 Client detail

Header block (name, address, tax treatment, evidence status), then a period roll-up table (month / invoices / billed / collected / outstanding), then an aging block, then the invoice list scoped to the client.

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

A settings page, not part of the invoice flow — reachable from the main nav ("Email accounts") independent of any single invoice. Lists configured SMTP accounts as a table: label, from address, server, and a verified/unverified badge, each row with **Test** (connects and authenticates, sends nothing — the mechanism for confirming a saved password still works, since it is never shown again) and **Remove**. Below the list, an add-account form: label, from name/address, SMTP host/port/security/username, password, and a "default account" checkbox. Credentials are write-only from the moment they're saved — see `edgecases.md` O4.

---

## 9. Invoice document design

The generated document is a separate design system from the app, sharing only tokens. It is a printed business document, not a web page.

**Layout:** A4 and US Letter, 20mm margins by default (12-30mm, template-configurable since 4.2), single column, logo top-left by default (position configurable since 4.2), document metadata top-right, then bill-to, then services, then totals right-aligned, then payment instructions, then footer.

**Type:** Inter throughout, 10pt body, 9pt tabular figures for the amount table, 18pt document title. Body colour `#1E1E1E`, labels `#757575`.

**Colour is minimal by default.** One accent colour, user-chosen, applied to the document title, the table header rule, and the totals rule. Nothing else is coloured. The system templates ship with accents drawn from the Figma spectrum, but muted 20% for print legibility.

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

WCAG 2.1 AA as a floor, with these specifics:

- Contrast: `--color-text-secondary` `#757575` on white is 4.6:1 — passes for body, **fails for text below 13px**, so `--text-caption` uses `#616161`. Verified per pairing, not assumed.
- `--color-accent-default` `#0D99FF` on white is 2.9:1 — **fails for text**. It is used for fills, borders, and focus rings only. Link text uses `#0066CC` (5.1:1).
- Never colour alone: every tax badge, status, and error carries a text label; the threshold bar carries a percentage.
- Full keyboard operation of the invoice builder including the line item table (Tab between cells, Enter to add a row, Cmd/Ctrl+Enter to issue).
- Visible focus everywhere, at 2px, never suppressed.
- Money announced to screen readers with currency spelled out: `seven thousand two hundred Canadian dollars`.
- Touch targets 44×44 minimum on mobile; the receipt drop zone is deliberately oversized.
- Form errors associated with fields via `aria-describedby`, and the error summary receives focus on failed submit.

---

## 13. Token reference

```css
:root {
  /* surface */
  --color-bg-default:#FFFFFF; --color-bg-secondary:#F5F5F5;
  --color-bg-tertiary:#EBEBEB; --color-bg-hover:#F5F5F5;
  --color-bg-pressed:#E6E6E6;  --color-bg-selected:#E5F4FF;

  /* border */
  --color-border-default:#E6E6E6; --color-border-strong:#D9D9D9;
  --color-border-subtle:#F0F0F0;  --color-border-focus:#0D99FF;

  /* text */
  --color-text-primary:#1E1E1E; --color-text-secondary:#757575;
  --color-text-tertiary:#B3B3B3; --color-text-caption:#616161;
  --color-text-link:#0066CC;     --color-text-onbrand:#FFFFFF;

  /* accent */
  --color-accent-default:#0D99FF; --color-accent-hover:#007BE5;
  --color-accent-pressed:#0066CC; --color-accent-subtle:#E5F4FF;
  --color-accent-border:#B3E0FF;

  /* tax + status (Figma brand spectrum) */
  --color-state-taxable:#A259FF;      --color-state-taxable-bg:#F4EBFF;
  --color-state-zero-rated:#1ABCFE;   --color-state-zero-rated-bg:#E5F8FF;
  --color-state-unregistered:#757575; --color-state-unregistered-bg:#F0F0F0;
  --color-status-paid:#0ACF83;        --color-status-paid-bg:#E8FBF3;
  --color-status-overdue:#F24E1E;     --color-status-overdue-bg:#FEECE7;
  --color-status-attention:#FF7262;   --color-status-attention-bg:#FFF0ED;

  /* type */
  --font-ui:'Inter',system-ui,sans-serif;
  --font-mono:'Roboto Mono',ui-monospace,monospace;
  --text-display:600 32px/40px var(--font-ui);
  --text-h1:600 24px/32px var(--font-ui);
  --text-h2:600 18px/24px var(--font-ui);
  --text-h3:600 14px/20px var(--font-ui);
  --text-body:400 13px/20px var(--font-ui);
  --text-body-strong:500 13px/20px var(--font-ui);
  --text-label:500 11px/16px var(--font-ui);
  --text-caption:400 11px/16px var(--font-ui);

  /* space */
  --space-1:4px;  --space-2:8px;  --space-3:12px; --space-4:16px;
  --space-5:24px; --space-6:32px; --space-7:48px; --space-8:64px;

  /* radius */
  --radius-xs:2px; --radius-sm:4px; --radius-md:6px;
  --radius-lg:8px; --radius-full:999px;

  /* elevation */
  --elev-1:0 1px 3px rgba(0,0,0,.06);
  --elev-2:0 4px 12px rgba(0,0,0,.10);
  --elev-3:0 12px 32px rgba(0,0,0,.14);

  /* motion */
  --motion-fast:120ms cubic-bezier(.2,0,0,1);
  --motion-base:180ms cubic-bezier(.2,0,0,1);
  --motion-slow:240ms cubic-bezier(.2,0,0,1);
}
```

Template `theme` JSON (`datamodel.md` §8) is a constrained subset of these tokens: accent colour, font scale multiplier, logo dimensions and position, margins, and block visibility flags. Users pick from the system; they do not extend it.
