# Design System

**Companion to:** `problem-statement.md`, `architecture.md`, `datamodel.md`
**Direction:** IBM Carbon Design System v11 — zero-radius flat structure, Financial Blue + Set-aside Gold as the two retained brand accents, Carbon's real Support Green/Red for financial polarity, a full Framer Motion cinematic layer
**Status:** Shipped 2026-08-11 (`implementation_plan.md` §8's IBM Carbon redesign, phases CB.A-CB.K)

**2026-08-11 note:** This document previously specified "Sovereign Ledger" (financial-blue/compliance-green/set-aside-gold, 4-8px radius, block-based composition), which shipped 2026-08-10 and ran in production. It has since been fully replaced by the **IBM Carbon** redesign described below. Sovereign Ledger's own token brief lived in `docs/screens/DESIGN.md`; this redesign's dashboard brief lives in `docs/screens/dashboard_design.md`, now marked merged/superseded-but-kept at its own header. This document is the merged, living spec — sections below reflect what actually shipped, including deliberate deviations from both Carbon's own conventions and this redesign's own plan (noted inline with ⚠️, matching this file's long-standing convention).

---

## 1. Design thesis

The product still handles money that isn't the user's, on documents that are legal records — that thesis hasn't changed. What changed is the visual language expressing it. Sovereign Ledger read as "precision instrument" through soft rounded blocks and a single blue-green-gold palette; Carbon reads the same intent through a harder, more literal structural honesty — **zero border-radius everywhere** (the one visual trait that most immediately signals "this is Carbon, not a generic SaaS dashboard"), flat bordered panels with no shadow, IBM Plex's slightly technical typographic voice, and colour applied with Carbon's own systematic discipline rather than a bespoke three-hue system.

The user's explicit brief for this redesign was two things at once, in tension: **"do not make everything black and white"** (keep real brand colour) and **make it "extremely polished, smooth, cinematic"** via animation. Both survive as first-class constraints below, not just the zero-radius structural change:

**Two brand accents survive Carbon's own neutral palette.** Financial Blue `#1A365D` replaces Carbon's default Blue 60 everywhere an accent appears — buttons, focus rings, links, active nav, the primary chart series — because it's the one hue tied to the actual product logo. Set-aside Gold `#B7791F` is *also* kept, not converted to Carbon's own (yellow) warning colour, because it already carries a specific "tax liability held aside" meaning distinct from Carbon's generic warning concept (§2.3). Genuine Carbon Green 50 / Red 60 carry financial polarity throughout — profit/loss, receivable/payable — exactly the "relevant numbers" the brief called out by name.

**Motion is real, not decorative, and it is Carbon-timed.** Every animation in the app — route transitions, staggered tile entrance, KPI count-ups, chart draw-ins, hover/press feedback — sources its duration and easing from `@carbon/motion`'s actual published tokens (§10), not hand-picked values. This is a real reversal of the prior system's explicit "never animate numbers from zero" rule (§10's history note) — the user asked for cinematic polish this time, and got it, deliberately and by name.

**Charts exist for the first time.** Every prior Dashboard iteration was 100% text/table/progress-bar. This redesign adds Recharts-based visualisation throughout — trend lines, a waterfall, donuts, aging/concentration bars — hand-themed to Carbon tokens rather than the heavier `@carbon/charts-react` package (§6's chart section explains why).

---

## 2. Colour tokens

### 2.1 Foundation — Carbon Gray neutrals

Pulled directly from `@carbon/themes`' White theme and `@carbon/colors`, verified via `node -e "require('@carbon/themes')..."` against the actually-installed packages during implementation — not hand-transcribed from memory or from a screenshot.

```
--color-bg-default        #FFFFFF   panel/card surfaces
--color-bg-secondary      #F4F4F4   page background behind panels (Carbon Gray 10)
--color-bg-tertiary       #E8E8E8   input wells, hover fills, disabled fills
--color-bg-hover          #E8E8E8   row and button hover
--color-bg-pressed        #C6C6C6
--color-bg-selected       #E6ECF3   selected row (Financial-Blue-tinted, not Carbon Gray)

--color-border-default    #E0E0E0   the workhorse hairline
--color-border-strong     #8D8D8D   input borders
--color-border-focus      #1A365D   focus ring (Financial Blue, not Carbon Blue 60)
--color-border-subtle     #E0E0E0   internal table rules

--color-text-primary      #161616   headings, values, amounts
--color-text-secondary    #525252   labels, metadata, helper text
--color-text-tertiary     #8D8D8D   placeholders, disabled
--color-text-caption      #525252   helper text, timestamps
--color-text-onbrand      #FFFFFF
--color-text-link         #1A365D
```

This is a genuinely different neutral scale from Sovereign Ledger's, not a re-hex of the same values — Carbon's Gray 10 (`#F4F4F4`) reads distinctly flatter/cooler than Sovereign Ledger's `#F8FAFC`, and it shows: the PWA manifest's `background_color` needed a real update to match (§7, CB.J), not just the CSS tokens.

### 2.2 Accent — Financial Blue (unchanged from Sovereign Ledger, replacing Carbon Blue 60)

```
--color-accent-default    #1A365D   primary actions, focus, selection, active nav
--color-accent-hover      #15294A
--color-accent-pressed    #0F1D36
--color-accent-subtle     #E6ECF3   backgrounds for accent surfaces
--color-accent-border     #B8C7DA
```

Identical hex values to Sovereign Ledger's accent — this is the one token family the redesign deliberately left untouched, confirmed via the user's own AskUserQuestion selection ("Keep Financial Blue #1A365D") rather than assumed. It now also covers the sidebar's active-nav tint (§7), which Sovereign Ledger had assigned to green — green is no longer available for that role once it means something specific (positive financial polarity) everywhere else in the app.

### 2.3 Semantic assignments — genuine Carbon Support colours, plus one retained deviation

| Token | Hex | Source | Assigned meaning |
|---|---|---|---|
| `--color-secondary-default` / `--color-status-paid` / `--color-state-taxable` | `#24A148` | Carbon Support **Green 50**, real/unmodified | **Positive financial outcome** — net income ≥ 0, safe-to-spend, paid, taxable/active tax position |
| `--color-status-overdue` | `#DA1E28` | Carbon Support **Red 60**, real/unmodified | **Negative financial outcome** — overdue, net income < 0, cancelled |
| `--color-tertiary-default` / `--color-status-attention` / `--color-state-zero-rated` | `#B7791F` | **Set-aside Gold, kept — not Carbon's actual (yellow) warning colour** | Tax liability held aside, threshold/attention escalation, zero-rated export |
| `--color-state-unregistered` | `#525252` | Carbon Gray 90 | Not registered, exempt, draft — deliberately grey, the absence of a position |

**⚠️ The gold-for-warning deviation is deliberate and was decided without a separate user round-trip** (documented in the redesign's own plan as low-stakes): Carbon's actual Support "warning" colour is yellow (`#F1C21B`), not gold. Gold was kept because it already carries a specific, established "tax liability being set aside" meaning in this product (§8.1's Tax + CPP reserve tile) that Carbon's generic warning concept doesn't have a name for, and the user's own "keep some brand colours" instruction reads as plural, not limited to just blue. This is the one place the palette isn't "authentic Carbon" by the letter, done knowingly.

**The colour-polarity rule, stated once here since it governs every subsequent screen:** Green 50 / Red 60 are reserved **strictly** for genuine positive/negative financial *outcomes* — net income's sign, safe-to-spend, overdue amounts. They are never applied to neutral-magnitude figures that merely got bigger or smaller without a value judgment attached — GST/HST collected, the threshold percentage, or tax/CPP deductions (which use gold, since they're expected obligations, not errors). A user reading the Dashboard's eight hero tiles should be able to tell at a glance which four are "outcomes" and which four are "facts," purely from colour.

### 2.4 Chart categorical palette (new — no equivalent in Sovereign Ledger)

```
--color-chart-1  #8A3FFC     --color-chart-4  #D02670
--color-chart-2  #0072C3     --color-chart-5  #BA4E00
--color-chart-3  #007D79     --color-chart-6  #6F6F6F
```

Carbon's actual published dataviz categorical sequence (`@carbon/colors`), used **only** for neutral multi-category series — expense-by-category and revenue-by-client donuts/bars — where no category is inherently "good" or "bad" relative to another. Never mixed with the polarity rule above.

### 2.5 Dark mode

Still deferred, same as Sovereign Ledger — tokens stay named so it's a value swap later, not a rewrite. The invoice **document** still never inverts (§9, unchanged).

---

## 3. Typography

**IBM Plex Sans** for the interface, **IBM Plex Mono** for data — Carbon's own type family, replacing Inter/JetBrains Mono. Both self-hosted via `@fontsource-variable/ibm-plex-sans` and `@fontsource/ibm-plex-mono` (same self-hosted-fontsource pattern the app already used, no external network dependency — verified, not assumed).

```
--font-ui        'IBM Plex Sans Variable', 'IBM Plex Sans', system-ui, -apple-system, sans-serif
--font-mono      'IBM Plex Mono', ui-monospace, monospace
```

Plex Sans has a visibly different x-height and letterform than Inter at the same point sizes — the type scale below was re-verified to still read correctly in the new face rather than assuming the old point sizes transfer unchanged; no sizes actually needed to move.

### Type scale (unchanged sizes/weights from Sovereign Ledger; only the face changed)

| Concept | Size / line | Weight | Use |
|---|---|---|---|
| `--text-display` | 32 / 40 | **700** | Dashboard hero KPI figures — now eight tiles, not one (§8.1) |
| `h1` | 32 / 40 | 700 | Page title |
| `h2` | 18 / 24 | 600 | Block header |
| body | 13 / 20 | 400 | Default body, table cells |
| `label` | 11 / 16 | 500 | Field labels |
| `.caption` | 11 / 16 | 400 | Helper text, timestamps |

13px body stays deliberate for the same reason as before — it reads as a tool, not a website.

### Numeric typography — unchanged rules, still non-negotiable

All money/quantities use tabular figures, right-aligned, `CAD 7,200.00` not `$7,200.00`, negative amounts use a minus sign plus Red 60 (never parentheses, never colour alone), tax rates render to true precision. None of this changed with the redesign.

### Label case

Sentence case throughout — unchanged. Carbon's own convention (Tag components, buttons) is also sentence case, so this needed no reconciliation between the two systems.

---

## 4. Spacing, radius, elevation

### Carbon's real 2px-based spacing scale

```
--space-1   4px     --space-5   24px
--space-2   8px     --space-6   32px
--space-3   12px    --space-7   40px
--space-4   16px
```

Verified, not shifted: Sovereign Ledger's existing 4/8/12/16/24/32px values already land exactly on Carbon's `spacing-02` through `spacing-07`, so `--space-1..6` carried over unchanged. `--space-7` extends the range to Carbon's `spacing-08` (40px, was 48px under Sovereign Ledger) for the one place that needed it.

### Radius — zero everywhere, Carbon's single defining trait

```
--radius-xs    0
--radius-sm    0
--radius-md    0
--radius-lg    0
--radius-badge var(--radius-full)   Tags, the one real rounding exception
--radius-full  9999px               avatars, circular icon buttons
```

This is the single biggest visual departure from Sovereign Ledger, and the whole point of "IBM Carbon" as a request rather than just a colour change: buttons, inputs, panels, modals — all flat rectangles now. Carbon's actual rounding exceptions are Tags and circular elements (avatars, checklist dots), which is why `--radius-badge` reuses `--radius-full` rather than getting its own small value — verified against Carbon's real `_tag.scss` source (16px), which renders identically to a full pill at this app's 24px Tag height.

### Elevation — borders first, shadows last (unchanged philosophy — a genuine continuity point)

Blocks/panels sit flat with a single hairline border, no shadow — this was already Carbon-authentic in Sovereign Ledger before this redesign existed, so it needed no change. Modals/dropdowns still use inline `box-shadow` for genuine floating surfaces; `--elev-*` tokens still don't exist as CSS custom properties (unchanged gap, not new).

---

## 5. Motion tokens (new — @carbon/motion, replacing the never-implemented Sovereign Ledger values)

```
--motion-fast-01      70ms    hover/press micro-feedback
--motion-fast-02      110ms
--motion-moderate-01  150ms
--motion-moderate-02  240ms   tile/panel entrance
--motion-slow-01      400ms   page transitions, count-ups, chart draw-in
--motion-slow-02      700ms

--motion-ease-standard  cubic-bezier(0.2, 0, 0.38, 0.9)
--motion-ease-entrance  cubic-bezier(0, 0, 0.38, 0.9)
--motion-ease-exit      cubic-bezier(0.2, 0, 1, 0.9)
```

These are `@carbon/motion`'s actual published values (`durationFast01` etc. and `easings.standard/entrance/exit.productive`), verified via `node -e "require('@carbon/motion')..."` against the installed package, not invented. Unlike Sovereign Ledger's equivalent tokens — which were specified in this document but **never actually implemented** as CSS custom properties, with the handful of shipped transitions using plain `0.15s ease` instead — these are real, live in `index.css`'s `:root`, and are the literal source both the CSS-side hover transitions and the JS/Framer Motion layer (`web/src/motion/tokens.ts`) draw from. Full behaviour described in §10.

---

## 6. Component specifications

### Buttons

Same four variants as Sovereign Ledger (Primary/Secondary/Ghost/Danger), radius now 0 instead of `--radius-sm`'s old 4px. **New:** every button now has a real Carbon-timed hover/press transition (`background-color`/`border-color`/`color` at `--motion-fast-02`, plus a `scale(0.97)` press feedback at `--motion-fast-01`) — previously buttons snapped instantly with no `transition` property at all anywhere in the stylesheet.

### Inputs

32px height, 0 radius (was `--radius-xs`'s 2px), 1px `--color-border-strong`, unchanged otherwise.

### Tags — real Carbon proportions, not a re-skinned badge

Height 24px (was 20px), 8px horizontal padding (was 6px), **sentence case, not uppercase** (`Taxable`, not `TAXABLE`), `label-01` type style (12px/16px, weight 400, not the old bold-uppercase treatment), pill radius via `--radius-badge`. These exact proportions were verified against Carbon's actual `_tag.scss` source fetched from unpkg during implementation, not assumed to match the old badge's dimensions.

```
● Taxable / Paid          Green 50   #24A148 on #DEFBE6
● Zero-rated / Attention  Gold       #B7791F on #FBF0DF
○ Not registered / Draft  Gray 90    #525252 on #E8E8E8
● Overdue                 Red 60     #DA1E28 on #FFF1F1
```

**⚠️ Two of these four combinations fail WCAG AA at Tag text size — see §12, re-verified with real numbers as part of this reconciliation, not assumed to pass because the hexes are "official IBM."**

### Tables — dropped zebra striping

Real Carbon DataTables use hairline row dividers plus a hover state only, **no periodic zebra tint**. Sovereign Ledger's `tbody tr:nth-child(5n)` shading was removed — a deliberate, flagged behaviour change, not a silent regression. Table row hover now also has a real transition (`--motion-fast-02`) where previously — like buttons — there was none.

### Charts (new section — no equivalent existed before this redesign)

**Library: Recharts, hand-themed to Carbon tokens** — not `@carbon/charts-react`, decided directly with the user via AskUserQuestion before implementation. `@carbon/charts-react` was rejected for three concrete reasons: no native waterfall chart type (the Dashboard needed one — see below), a heavier D3-based runtime, and materially more limited animation control than a "cinematic" brief calls for. Recharts' SVG elements accept CSS custom properties directly as `fill`/`stroke` props and resolve them correctly (`getComputedStyle` confirmed, not assumed) — the same token system styles both plain CSS and every chart.

**Eight chart components ship, all under `web/src/components/dashboard/`:**

| Chart | Type | Colour treatment |
|---|---|---|
| Business performance | Composed (bar + line) | Revenue/Expenses bars neutral (Blue/Gray), Net income line neutral dashed — a single stroke can't change colour mid-line if it crosses zero across the year |
| Where your revenue goes | Custom waterfall | Start/end bars Financial Blue, deduction bars Gold (an expected obligation, not an error — not Red) |
| Actual vs. projected revenue | Line + reference line | Financial Blue actual (solid) + projected (dashed continuation) |
| GST/HST control center | Bar | Neutral Blue/Gray — collected and ITCs are magnitudes, not outcomes |
| Accounts receivable aging | Horizontal bar | Neutral buckets except 90+ days (Red 60) — the one bucket signalling a real collection problem |
| Invoice status | Donut | Per-status semantic colour (paid=Green, overdue=Red, draft=Gray, etc.) |
| Revenue by client | Horizontal bar | Neutral Financial Blue — which client bills most isn't a polarity question |
| Expenses by category | Donut | Categorical chart palette (§2.4) — no category is inherently good/bad |

**The waterfall has no native Recharts type.** Built via the standard technique: two stacked `<Bar>` elements sharing a `stackId`, an invisible "base" bar (transparent fill, `isAnimationActive={false}`) floats a visible "value" bar to the correct height, with per-step `<Cell>` colouring.

**⚠️ The waterfall's basis deliberately deviates from `dashboard_design.md` §5's own 5-step example**, which starts from raw Revenue. This app's waterfall starts from Net Business Income instead (Revenue → Federal tax → Provincial tax → CPP → Safe to spend, one fewer step) because `GET /projection`'s tax/CPP figures are computed from the *active projected annual* net-income basis, and there is no projected-annual-*expenses* figure available to bridge Revenue down to that same basis consistently — starting from net income keeps every step on one basis rather than forcing numbers that wouldn't actually reconcile.

**Every chart's `animationDuration`/`animationEasing` props are re-pointed at the same `@carbon/motion` tokens** (`src/motion/tokens.ts`'s `rechartsDurationMs`/`rechartsEasing` — 400ms, Carbon's entrance-expressive curve) rather than Recharts' own defaults, so chart draw-ins read as part of the same motion system as everything else, not a visually separate library's timing.

---

## 7. Application shell

```
┌────────────┬──────────────────────────────────────────────────┐
│  Logo      │  Topbar — page title · Create Invoice · 🔔 ? 👤   │
│            ├──────────────────────────────────────────────────┤
│ +Add       │                                                  │
│  Expense   │   Page background #F4F4F4 (Carbon Gray 10)       │
│            │   ┌────────────────────────────────────────────┐ │
│  Dashboard │   │  flat 0-radius panel                        │ │
│  Invoices  │   └────────────────────────────────────────────┘ │
│  Expenses  │                                                  │
│  Clients   │                                                  │
│  Reports   │                                                  │
│  Settings  │                                                  │
│  Sign out  │                                                  │
└────────────┴──────────────────────────────────────────────────┘
```

Layout/structure unchanged from Sovereign Ledger (Settings hub, nav item set, mobile slide-in). Three real changes:

1. **Icons: `@carbon/icons-react` replaces `lucide-react`** throughout (16 icon usages across `Shell.tsx`, `Dashboard.tsx`, `Settings.tsx`, `ComplianceChecklist.tsx`) — decided directly with the user, `lucide-react` having been the prior redesign's own first-ever icon library for this app.
2. **Active-nav tint moved from Compliance Green to Financial-Blue-subtle.** Green is no longer available for "current nav item" once it means something specific and load-bearing (positive financial polarity) throughout the rest of the app — Carbon's own convention for "current" is the interactive/accent colour anyway, not the success colour, so this is a correction toward Carbon-authenticity as much as a polarity-conflict fix.
3. **Sidebar/topbar entrance animation on load** (§10) — new, via the motion layer.

⚠️ Same pre-existing gaps as Sovereign Ledger, untouched by this redesign: no persistent tax-registration-status chip in the topbar, Bell/Help remain inert visual placeholders (`title="...(coming soon)"`, no backend to wire to).

---

## 8. Key screens

### 8.1 Dashboard — full rebuild against `docs/screens/dashboard_design.md`

The single largest deliverable of this redesign, shipped across three phases (CB.E/F/G) matching the one-phase-per-commit discipline the prior redesign used. Went from 100% text/table/progress-bar to a real charted financial control centre, per the brief's own ~30-section spec — most sections needed **zero new backend work** (`GET /projection` already carried the data), a handful needed new aggregate endpoints (§8.1.1).

**Hero KPI row** (`dashboard_design.md` §3): eight tiles across two rows — Revenue, Expenses, Net income, Safe to spend, Tax + CPP reserve, GST/HST owing, Outstanding, Projected annual revenue. Colour-polarity rule (§2.3) applied narrowly: only Net income, Safe to spend, and Outstanding carry Green/Red; GST/HST owing and the reserve/projected figures stay neutral even though `dashboard_design.md` itself doesn't explicitly forbid colouring them — this app's own polarity rule (stated once, §2.3) is stricter than the brief requires, deliberately.

A real UX gap was caught and fixed during CB.E's own browser verification, not by a later audit: "Safe to spend" (full-year-*projected*-income basis) originally sat directly next to "Net income" (year-to-date-*actual* basis) with Safe-to-spend counterintuitively showing higher — both figures were individually correct but juxtaposed with no distinguishing caption, reading as a bug. Fixed by adding a clarifying sub-caption ("full-year projected income, after recommended tax + CPP reserve") rather than leaving two correct-but-confusing numbers unexplained.

**Business performance** (§6 above): 12-month Revenue/Expenses/Net-income chart, from the new `GET /reports/pnl` JSON endpoint (a thin wrapper around already-existing `reporting/service.py: pnl_rows`, zero new aggregation).

**Where your revenue goes / Actual vs. projected revenue**: the waterfall and actual-vs-target line described in §6, both fully derivable from `GET /projection`'s existing fields.

**Tax Reserve progress**: recommended (existing `set_aside` figure) vs. actually-reserved, a genuinely new user-enterable field (`tax_reserve` table, migration 0022, RLS-scoped exactly like `income_declaration`).

**GST/HST control center + AR aging + Invoice status**: GST/HST and threshold tracker restyled from Sovereign Ledger's existing tiles plus a new quarterly chart; AR aging from a new `tenant_aging_summary` aggregate that adds a "not yet due" bucket the prior `tenant_aging_report` never surfaced (a real gap: `_aging_bucket()` returned `None`, silently excluded, for anything not yet past due); Invoice status is a **client-side tally** of the already-fetched `GET /invoices` list, deliberately not a new endpoint.

**Revenue by client / Expenses by category / Receipt completeness / Recurring revenue / Accountant readiness / Business momentum / Year-over-year / Needs your attention / Recent activity**: each backed by either a small new aggregate endpoint (§8.1.1) or a client-side composition over data already fetched elsewhere on the page — no duplicate fetching. **Accountant Readiness is computed client-side** from already-fetched pieces (receipt completeness, profile/registration completeness) rather than an opaque server-computed score, a deliberate choice so "why is my score X%" is always answerable by reading the component, not a black box.

#### 8.1.1 New backend endpoints (CB.D)

| Endpoint | Backing |
|---|---|
| `GET /reports/pnl` (JSON) | Wraps existing `pnl_rows`, no new logic |
| `GET /reports/aging/summary` | New `tenant_aging_summary`, adds the not-due bucket |
| `GET /reports/revenue-by-client` | New `tenant_revenue_by_client` |
| `GET /expenses/by-category` | New `expenses_by_category` |
| `GET /expenses/receipt-completeness` | New, sibling to existing `unprocessed_receipts()` |
| `GET /projection/recurring-forecast` | Refactor of existing `scheduled_recurring_income()` into period-bucketed rows |
| `GET /reports/payment-speed` | New `average_days_to_payment` — **v1 scope**: tenant-wide average only |
| `GET/PUT /projection/tax-reserve/{year}` | New `tax_reserve` table |

⚠️ **Deliberately deferred, not built**: payment-speed's trend sparkline and fastest/slowest-paying-client breakdown — both need real additional complexity (historical-period computation, a minimum-sample-size guard) beyond what a v1 tenant-wide average needed.

### 8.2-8.9 Everything else — cascaded automatically, verified not assumed

Every other page (Ledger, ClientDetail, Clients, InvoiceBuilder, Settings, Profile, TemplateEditor, EmailAccounts, Recurring, InvoiceDetail, PublicInvoice, Login) needed **zero code changes** for the Carbon re-skin (CB.H) — Sovereign Ledger's own class-reuse architecture (everything flows through shared classes like `.block`, `.badge`, `table`/`th`/`td` rather than bespoke per-page CSS) meant the token/class rewrite in §2-6 cascaded automatically. This was verified, not assumed: every page was grepped for hardcoded hex colours (found: 2, both the intentional `#1A365D` invoice-template default, correctly out of Carbon's scope) and for colour-bearing inline `style={{}}` props (confirmed: 100% already `var(--color-*)`-driven), then walked through in a real browser with seeded data before being marked done with no diff.

Business logic on every one of these pages is unchanged from whatever Sovereign Ledger or an earlier phase shipped — this redesign is a visual-system replacement, not a feature phase.

---

## 9. Invoice document design — unchanged, deliberately out of scope

The generated invoice document (`InvoiceDocument.tsx`, `pdf_renderer.py`) remains **a separate design system from the app, sharing only tokens** — same principle Sovereign Ledger's own §9 established, carried forward unchanged. Carbon's flat 0-radius software-UI language does not belong on a printed business document sent to clients; the document keeps its own print-appropriate rounded/serif-adjacent treatment. The two `#1A365D` hex literals found during CB.H's audit (`TemplateEditor.tsx`, `Profile.tsx`) are this document's intentional default accent colour, correctly untouched by the Carbon token rewrite.

---

## 10. Motion — the cinematic layer (CB.I)

This section was previously named "Motion" and specified `--motion-*` tokens that were **never actually implemented** as CSS custom properties or real transitions anywhere in the app, with an explicit rule against animating numbers from zero. Both of those are now different: the tokens are real (§5), and the "never animate from zero" rule is **deliberately overridden** per this redesign's own explicit brief — the user asked for "extremely polished, smooth, cinematic," which a Sovereign-Ledger-era instrument aesthetic doesn't deliver on its own.

**Library: `motion`** (the current npm package name for what was `framer-motion`), decided directly with the user via AskUserQuestion as a "full cinematic pass," not a restrained one.

**What actually animates**, all timed against `@carbon/motion`'s real tokens (§5), implemented in `web/src/motion/tokens.ts`:

- **Route transitions**: `AnimatePresence` in `Shell.tsx`, keyed on `location.pathname`, wrapping `<Outlet />` — fade + 8px vertical offset, `slow-01`/`entrance-productive` in, `moderate-01`/`exit-productive` out.
- **Shell entrance**: sidebar and topbar fade+slide in once on load.
- **Staggered tile/panel entrance**: every hero KPI tile, chart card, and metric tile across the Dashboard's CB.E/F/G sections, orchestrated from a single root `staggerContainer` per major section rather than each tile carrying its own `initial`/`animate` — Framer Motion's variant propagation cascades the timing down automatically.
- **KPI count-ups** (`useCountUp`, `web/src/motion/useCountUp.ts`): a tile's figure animates from its previously-displayed value to a newly-arrived one. **Deliberately does not animate on first mount** — the hook jumps straight to the real figure the first time it renders, since callers only mount it once real data exists. A money figure never climbs from zero or from a placeholder; it only ever tweens between two real, already-fetched values (e.g. after a period-selector change triggers a refetch).
- **Chart draw-ins**: every Recharts `animationDuration`/`animationEasing` re-pointed at the shared tokens (§6).
- **Hover/press feedback**: spring `whileHover`/`whileTap` on `KpiTile` (the shared dashboard-tile wrapper); plain-CSS Carbon-timed transitions on buttons, table rows, sidebar nav, and settings cards, which previously had no `transition` property at all and snapped instantly.

**`prefers-reduced-motion: reduce` — implemented for the first time in this app's history**, in two layers:
1. `<MotionConfig reducedMotion="user">` wraps the whole app (`main.tsx`), which every `motion.*` component and hook reads automatically.
2. A global CSS media-query fallback in `index.css` collapses every plain-CSS `transition`/`animation` to near-zero duration.

**⚠️ Verified nuance, not a bug:** under `reducedMotion="user"`, Framer Motion disables animation only for *positional* properties (`x`/`y`/`scale`/`rotate` — the actual vestibular-motion trigger WCAG 2.3.3 is concerned with) and deliberately **still animates simple opacity fades** at full duration — confirmed by reading Motion's own source (`motion-dom`'s `shouldReduceMotion && positionalKeys.has(key)` gate) after an initial screenshot comparison looked identical between reduced and non-reduced captures at the same early timestamp. This is Motion's own considered accessibility design, not an oversight this redesign introduced or failed to catch — a full opacity-and-transform-both-instant approach would arguably be *less* correct against the letter of the guideline, not more.

---

## 11. Voice and copy

Unchanged from Sovereign Ledger — error copy, empty states, and the "every estimated figure is labelled" rule all carry forward verbatim. This redesign touched visual language and motion, not product copy.

---

## 12. Accessibility

WCAG 2.1 AA as a floor, unchanged. **Re-verified 2026-08-11 against the actual shipped Carbon values** (computed via the WCAG relative-luminance formula, not estimated, not assumed to pass because the hexes are "official IBM colours") — this is the same discipline the Sovereign Ledger reconciliation used, which is what caught two real AA failures nobody had checked before that redesign. This pass caught different, also-real ones:

- `--color-accent-default` `#1A365D` on white: **12.14:1** — unchanged from Sovereign Ledger (same hex).
- `--color-text-primary` `#161616` on white: **18.10:1**. `--color-text-secondary` `#525252` on white: **7.81:1** — both comfortably clear AA, an improvement over Sovereign Ledger's tighter 4.76:1 secondary-text margin.
- **⚠️ Tag/badge text-on-tint, re-checked against the real Carbon hexes, not assumed to pass:**
  - Green 50 `#24A148` on its own paired Green-10-equivalent tint `#DEFBE6`: **3.04:1** — fails AA's 4.5:1 floor for the Tag's 12px/400 text, and is **worse** than Sovereign Ledger's already-failing Compliance Green (4.00:1). Carbon's real "50" and "10" steps, paired directly, simply don't clear AA at Tag text size — this is a property of the authentic Carbon palette itself, not a mistake in choosing it.
  - Gold `#B7791F` on `#FBF0DF`: **3.23:1** — still fails, an unchanged carry-over from Sovereign Ledger (same token, same failure, not newly introduced).
  - Red 60 `#DA1E28` on `#FFF1F1`: **4.55:1** — passes, though by a narrower margin than Sovereign Ledger's Error Red (4.70:1).
  - Recommendation for a follow-up pass, not applied in this reconciliation (review-only phase, per this redesign's own plan): darken the Green/Gold *text* colour specifically when paired with their light tint backgrounds, rather than reusing the same "default" token for both fill-on-white and text-on-tint roles — a real Carbon pattern elsewhere in IBM's own product UIs.
- **⚠️ New finding, outside the Tag component entirely:** Green 50 and Gold used as plain body/table text directly on white (not on a tint) fall under the *normal-text* 4.5:1 threshold, not the 3:1 *large-text* threshold the KPI hero figures get to use (§8.1's 32px/700 display type passes at 3.35:1/5.00:1). Two real usages fail at normal size: the Business Momentum table's year-over-year `%change` cells (Green 50 on white, **3.35:1**) and the "Needs your attention" list's medium-severity items (Gold on white, **3.64:1**). Both are genuine, previously-unchecked AA failures surfaced by this reconciliation's contrast pass, not by assumption. Flagged for the same follow-up as the Tag issue above, not fixed in this phase.
- Never colour alone: unchanged — every tax Tag, status, and error still carries a text label.
- Touch targets, focus rings, `aria-describedby` form-error association: unchanged from Sovereign Ledger.

---

## 13. Token reference

**Copied verbatim from the shipped `web/src/index.css` `:root` rule (2026-08-11), not re-derived.**

```css
:root {
  /* surface */
  --color-bg-default: #ffffff;
  --color-bg-secondary: #f4f4f4;
  --color-bg-tertiary: #e8e8e8;
  --color-bg-hover: #e8e8e8;
  --color-bg-pressed: #c6c6c6;
  --color-bg-selected: #e6ecf3;

  /* border */
  --color-border-default: #e0e0e0;
  --color-border-strong: #8d8d8d;
  --color-border-subtle: #e0e0e0;
  --color-border-focus: #1a365d;

  /* text */
  --color-text-primary: #161616;
  --color-text-secondary: #525252;
  --color-text-tertiary: #8d8d8d;
  --color-text-caption: #525252;
  --color-text-link: #1a365d;
  --color-text-onbrand: #ffffff;

  /* accent -- Financial Blue, unchanged from Sovereign Ledger */
  --color-accent-default: #1a365d;
  --color-accent-hover: #15294a;
  --color-accent-pressed: #0f1d36;
  --color-accent-subtle: #e6ecf3;
  --color-accent-border: #b8c7da;

  /* secondary (Carbon Green 50) / tertiary (Set-aside Gold, kept) -- see §2.3 */
  --color-secondary-default: #24a148;
  --color-secondary-subtle: #defbe6;
  --color-tertiary-default: #b7791f;
  --color-tertiary-subtle: #fbf0df;

  /* tax + status semantics */
  --color-state-taxable: #24a148;       --color-state-taxable-bg: #defbe6;
  --color-state-zero-rated: #b7791f;    --color-state-zero-rated-bg: #fbf0df;
  --color-state-unregistered: #525252;  --color-state-unregistered-bg: #e8e8e8;
  --color-status-paid: #24a148;         --color-status-paid-bg: #defbe6;
  --color-status-overdue: #da1e28;      --color-status-overdue-bg: #fff1f1;
  --color-status-attention: #b7791f;    --color-status-attention-bg: #fbf0df;

  /* chart categorical palette -- Carbon's real dataviz sequence, see §2.4 */
  --color-chart-1: #8a3ffc;  --color-chart-2: #0072c3;  --color-chart-3: #007d79;
  --color-chart-4: #d02670;  --color-chart-5: #ba4e00;  --color-chart-6: #6f6f6f;

  /* type */
  --font-ui: 'IBM Plex Sans Variable', 'IBM Plex Sans', system-ui, -apple-system, sans-serif;
  --font-mono: 'IBM Plex Mono', ui-monospace, monospace;
  --text-display: 700 32px/40px var(--font-ui);

  /* space -- Carbon's real 2px-based scale */
  --space-1: 4px;  --space-2: 8px;  --space-3: 12px;
  --space-4: 16px; --space-5: 24px; --space-6: 32px; --space-7: 40px;

  /* radius -- zero everywhere except Tags/circular elements, Carbon's defining trait */
  --radius-xs: 0; --radius-sm: 0; --radius-md: 0; --radius-lg: 0;
  --radius-badge: var(--radius-full); --radius-full: 9999px;

  /* motion -- @carbon/motion's real tokens, see §5/§10 */
  --motion-fast-01: 70ms;     --motion-fast-02: 110ms;
  --motion-moderate-01: 150ms; --motion-moderate-02: 240ms;
  --motion-slow-01: 400ms;    --motion-slow-02: 700ms;
  --motion-ease-standard: cubic-bezier(0.2, 0, 0.38, 0.9);
  --motion-ease-entrance: cubic-bezier(0, 0, 0.38, 0.9);
  --motion-ease-exit: cubic-bezier(0.2, 0, 1, 0.9);
}
```

Template `theme` JSON is unchanged — still a constrained subset of these tokens, still defaults new templates to `#1A365D`.

---

## 14. Known gaps carried into this redesign, not fixed by it

Stated plainly, matching this document's own long-standing convention of an honest record over a flattering one:

- **No frontend CI workflow exists in this repo.** `.github/workflows/` only has `api-ci.yml` (path-filtered to `api/**`) plus two scheduled jobs. Every frontend-only phase of this redesign (CB.A, B, C, E, F, G, H, I, J) was verified via local `npm run build`/`npm run lint` plus real Playwright browser walkthroughs with seeded data and screenshots read back — never a CI gate. Pre-existing gap, not introduced or fixed here.
- **Tag/badge and plain-text Green/Gold-on-white contrast failures** (§12) — flagged, not fixed; this redesign's own plan scoped the reconciliation phase as review-only.
- **Topbar tax-registration-status chip, Bell/Help notification backends** — unchanged gaps from Sovereign Ledger (§7).
- **Payment-speed trend sparkline and fastest/slowest-client breakdown** (§8.1.1) — deliberately deferred v1 scoping, not a cut feature.
