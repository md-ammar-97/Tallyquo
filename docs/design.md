# Design System

**Companion to:** `problem-statement.md`, `architecture.md`, `datamodel.md`
**Direction:** Wise-inspired — lime-green `#9fe870` as the sole brand accent, near-black ink on a sage-tinted canvas, white cards as the only elevation cue (no shadows anywhere), a 24px pill radius on every card and button, heavy Manrope display type paired with Inter body text. Built on Tailwind CSS v4 + shadcn/ui, replacing every prior redesign's hand-rolled CSS custom properties.
**Status:** Shipped 2026-08-15 (`implementation_plan.md` §9's Wise-inspired redesign, phases WI.A-WI.H)

**2026-08-15 note:** This document previously specified "IBM Carbon" (zero-radius flat structure, Financial Blue + Set-aside Gold, a Framer Motion cinematic layer), which shipped 2026-08-11 and ran in production. It has since been fully replaced by the **Wise-inspired** redesign described below. Carbon's own token brief is no longer a separate file (it lived directly in this document, §2-§5 of the prior revision); this redesign's brief lives in `docs/screens/DESIGN (2).md`, now marked merged/superseded-but-kept at its own header, same convention as `DESIGN.md` and `dashboard_design.md` before it. This document is the merged, living spec — sections below reflect what actually shipped, including deliberate deviations from both the brief's own literal values and this redesign's own plan (noted inline with ⚠️, matching this file's long-standing convention).

---

## 1. Design thesis

The product still handles money that isn't the user's, on documents that are legal records — that thesis hasn't changed across three redesigns now. What changed again is the visual language expressing it, and this time also the *foundation* it's built on. Sovereign Ledger read as "precision instrument" through soft rounded blocks; Carbon read the same intent through zero-radius structural honesty. This redesign reads it through Wise's own real-world identity: a vivid lime-green CTA against a sage-tinted canvas, white cards whose only elevation cue is contrast against that canvas (no shadow anywhere in the system, a genuinely different elevation philosophy than Carbon's hairline-border approach), a generous 24px pill radius on every card and button, and an unusually heavy Manrope 900 display face carrying every headline.

**This is also the first redesign to change the app's styling foundation, not just its token values.** Sovereign Ledger and Carbon were both hand-rolled CSS custom properties consumed by plain classes (`.block`, `.badge`, `table`/`th`/`td`). This one moves onto **Tailwind CSS v4 + shadcn/ui** — utility classes inlined in JSX plus self-contained component source files, pulling several components from **Watermelon UI** (`ui.watermelon.sh`, a shadcn-compatible registry, confirmed real and reachable by the actual `shadcn` CLI, not assumed from its marketing site). This is a real, structural consequence for how the redesign itself had to be executed: Sovereign Ledger's own class-reuse architecture is what let Carbon's CB.H page-sweep cost **zero code changes** — every page already flowed through shared classes, so a token rewrite cascaded automatically. Tailwind's model doesn't cascade that way. **Every page's markup changed this time** (WI.E1/E2), not just its stylesheet.

**Two brand-new surfaces exist for the first time, not just re-skinned ones.** A public marketing homepage (`/`, WI.B) — the app went straight to `/login` before, with no page describing the product to a logged-out visitor. And a from-scratch, multi-stage OTP verification animation (WI.C) — on Verify, the six digit boxes animate into a circle and revolve together as a bespoke loading state, then either converge into a single checkmark box or un-circle into a red shake, confirmed directly with the user beyond the standard "type code, get zero or one shake" genre convention.

**Lime is the sole accent, and it is never repurposed.** Unlike Carbon's two retained accents (Financial Blue + Set-aside Gold) or Sovereign Ledger's three-hue system, this palette has exactly one brand colour — lime `#9fe870` — and the brief is explicit that it must never stand in for a status or dataviz colour, since it *is* the CTA identity. That rule is applied more broadly here than the brief itself spells out: it extends to every chart series (§6's chart section) and to `Progress`'s default fill (§12 — the stock shadcn default, `bg-primary`, violated this rule and was fixed during the WI.G reconciliation).

---

## 2. Colour tokens

### 2.1 Foundation — the brief's own tokens, plus shadcn's semantic re-export

Wise-inspired values from `docs/screens/DESIGN (2).md`, defined once in `web/src/styles/tailwind.css`'s `@theme` block and then re-exposed a second time under shadcn's own naming convention (`--background`/`--card`/`--primary`/etc., in a `:root` block plus a separate `@theme inline` block) so shadcn- and Watermelon-sourced components resolve them correctly — this two-layer structure is what shadcn's own generator produces, not a simplification this app chose to skip.

```
--color-canvas         #ffffff   card surfaces
--color-canvas-soft    #e8ebe6   page background behind cards (sage-tinted)
--color-ink            #0e0f0c   headings, values, primary text
--color-ink-deep       #163300   —
--color-body           #454745   secondary body text
--color-mute           #5f5e5a   captions, labels, secondary table columns — see the ⚠️ below
--color-divider        #d6dbd1   internal table/list row dividers — net-addition, see below
```

**⚠️ `--color-mute` is not the brief's literal value.** `DESIGN (2).md` specifies `#868685`; WI.G's real WCAG contrast re-check found that value fails AA as text against *both* app backgrounds (3.64:1 on the white card, 3.03:1 on the sage canvas — need 4.5:1), and it's used almost everywhere in the app as caption/secondary text, not as a fill. Darkened to `#5f5e5a` (5.40:1 / 6.49:1), the nearest value clearing AA on both surfaces with real margin — full numbers in §12.

**`--color-divider` is a net-addition beyond the literal brief.** The brief's only border token is a heavy 1px-solid-ink "Level 1" hairline meant for buttons/inputs/cards — too heavy for internal table row dividers or chart gridlines, which the brief has no dedicated token for. `#d6dbd1` is a softer tint used exactly there.

shadcn's own semantic layer, real hex values (not just references — the shipped `:root` block, verbatim):

```
--background: #e8ebe6      --card: #ffffff
--foreground: #0e0f0c      --card-foreground: #0e0f0c
--primary: #9fe870         --primary-foreground: #0e0f0c
--secondary: #e8ebe6       --secondary-foreground: #0e0f0c
--muted: #e2f6d5           --muted-foreground: #868685
--accent: #e2f6d5          --accent-foreground: #0e0f0c
--destructive: #d03238     --destructive-foreground: #ffffff
--border: #0e0f0c          --input: #0e0f0c
--ring: #9fe870
```

`--background`/`--card` is a genuinely good structural fit for the brief's own "surface contrast IS elevation" model — sage canvas behind, white cards on top, nothing else needed to read depth.

### 2.2 Accent — lime, sole and non-negotiable

```
--color-primary-active   #cdffad   pale lime, chart fill only — never a button
--color-primary-neutral  #c5edab
--color-primary-pale     #e2f6d5   same value as --muted, tint backgrounds
```

Unlike both prior redesigns, there is exactly one brand hue here. Lime `#9fe870` (shadcn's `--primary`) is the CTA identity — primary buttons, the active-nav tint's foreground pairing, focus rings. **It is never used as a status, chart-series, or progress-indicator colour** (§6, §12) — a rule stated once here since it governs the rest of this document, extending the brief's own explicit instruction ("never repurpose Wise green as a success indicator since it IS the brand CTA") further than the brief itself applies it.

### 2.3 Semantic assignments — the colour-polarity rule, unchanged in spirit across all three redesigns

| Token | Hex | Assigned meaning |
|---|---|---|
| `--color-positive` / `--color-positive-deep` | `#2ead4b` / `#054d28` | **Positive financial outcome** — net income ≥ 0, safe-to-spend, paid invoices, on-track progress |
| `--color-negative` / `--color-negative-deep` | `#d03238` / `#a72027` | **Negative financial outcome** — overdue, net income < 0, cancelled |
| `--color-warning` / `--color-warning-deep` / `--color-warning-content` | `#ffd11a` / `#b86700` / `#4a3b1c` | Tax/CPP liability held aside, threshold/attention escalation — an expected obligation, not an error |
| `--color-accent-orange` / `--color-accent-cyan` | `#ffc091` / `#38c8ff` | Neutral chart-series colours only — never polarity |

**The colour-polarity rule, same as both prior redesigns:** positive/negative are reserved strictly for genuine financial *outcomes*. Neutral-magnitude figures — GST/HST collected, the threshold percentage — never carry them.

**⚠️ Every one of these tokens has a `-deep` (or `-content`) sibling specifically because the base tone fails contrast as text or as a small icon fill, and this redesign uses the base tone for fills/large-surface use and the deep sibling for anything text-sized or icon-sized.** This is a genuine, deliberate pattern this redesign follows more strictly than either prior one — see §12 for the real numbers that drove it.

### 2.4 Chart categorical palette

```
--color-chart-1  #2ead4b (positive)      --color-chart-4  #ffd11a (warning)
--color-chart-2  #38c8ff (accent-cyan)   --color-chart-5  #868685 (mute, unshifted -- decorative fill only)
--color-chart-3  #ffc091 (accent-orange) --color-chart-6  #d03238 (negative)
```

Built from the semantic tokens above, **deliberately never `--color-primary`** — lime is the one hue this palette withholds from dataviz, per §2.2's rule. Two extra neutral shades (`--color-ink-deep`, `--color-body`) extend a sequence past six categories without repeating or falling back to lime.

**⚠️ Real bug found and fixed (WI.D3):** Recharts' pie-sector entrance animation runs `fill` through `react-smooth`'s colour interpolator, which cannot parse CSS custom properties — it silently resolves `var(--color-chart-2)` etc. to black once the animation settles, even though the SVG `fill` *attribute* still shows the correct `var()` string. Bar/Line charts never animate colour (only size/position), so `var()` renders correctly there via the browser's own CSS engine; only the two Pie-based donuts (Invoice status, Expenses by category) hit this. Fixed with literal hex values in those two components specifically — every other chart still references the CSS custom properties directly.

### 2.5 Dark mode

Still deferred, same stance as both prior redesigns — `.dark` currently mirrors `:root` exactly. The invoice **document** still never inverts (§9, unchanged across all three redesigns).

---

## 3. Typography

**Manrope** (display, weight 800/900) + **Inter** (body/UI, 400/600) — two faces, preserving the brief's own stated "brand's typographic story" contrast rather than collapsing to one face, per a direct decision with the user (Manrope substitutes for the brief's proprietary, unlicensable `Wise Sans`, at that token's own literal fallback chain of `Wise Sans, Inter, system-ui, ...`). Both self-hosted via `@fontsource-variable/manrope` / `@fontsource-variable/inter`, replacing IBM Plex Sans.

```
--font-display   'Manrope Variable', 'Manrope', system-ui, sans-serif
--font-sans      'Inter Variable', 'Inter', system-ui, sans-serif
--font-mono      'JetBrains Mono Variable', 'JetBrains Mono', ui-monospace, monospace
```

**A self-hosted monospace face is a net-addition beyond the literal brief**, which names no monospace token at all — added for tabular-nums money figures in dense tables, reused from the Sovereign Ledger era's own font choice.

### Type scale (verbatim from the brief's own token values)

| Token | Size / line | Weight | Use |
|---|---|---|---|
| `--text-display-mega` | 126 / 107.1px | 900 | reserved, unused at current screen sizes |
| `--text-display-xxl` | 96 / 81.6px | 900 | reserved |
| `--text-display-xl` | 64 / 54.4px | 900 | reserved |
| `--text-display-lg` | 47 / 70.5px | 400 | reserved |
| `--text-display-md` | 40 / 34px | 900 | reserved |
| `--text-display-sm` | 32 / 38.4px | 600 | page-level `h1` (e.g. Dashboard's "How much is mine?") |
| `--text-display-xs` | 24 / 31.2px | 600 | card-level heading (e.g. "Welcome back", every `CardTitle`) |
| `--text-body-lg` | 20 / 30px | — | — |
| `--text-body-md` | 16 / 24px | — | default body |
| `--text-body-sm` | 14 / 20px | — | table cells, labels, most UI text |
| `--text-caption` | 12 / 16px | — | secondary/helper text, timestamps |
| `--text-button-md` | 16 / 24px | 600 | button label |

Only `display-sm` and `display-xs` see real use at current screen sizes — the brief's larger display steps (mega/xxl/xl/lg/md) are specced for a marketing-site scale this app's own homepage hero doesn't reach for; kept in the token set rather than pruned, since the homepage may grow into them later.

### Numeric typography — unchanged rules, still non-negotiable

All money/quantities use tabular figures, right-aligned, `CAD 7,200.00` not `$7,200.00`, negative amounts use a minus sign plus the negative token (never parentheses, never colour alone), tax rates render to true precision. Unchanged across all three redesigns.

### Label case

Sentence case throughout — unchanged.

---

## 4. Spacing, radius, elevation

### Spacing — Tailwind's stock scale, no override needed

The brief's own 4px-based scale already lands exactly on Tailwind's default numeric spacing scale (`p-1` = 4px, `p-4` = 16px, etc.) — the only redesign of the three where this needed zero token work.

### Radius — a fixed per-component scale, the brief's defining trait

```
--radius-none  0px
--radius-sm    8px
--radius-md    12px    text-input specifically, not the canonical pill
--radius-lg    16px
--radius-xl    24px    canonical/signature -- every Card and Button
--radius-pill  9999px
--radius-full  9999px
```

**24px on every card and button is the single biggest visual departure from Carbon's zero-radius signature** — the whole point of "Wise-inspired" as a request. shadcn's own default component radius (`rounded-lg`, a smaller `calc()`-derived value) was overridden site-wide: `button.tsx`, `input.tsx`, `textarea.tsx` all patched from their stock `rounded-lg` down to `rounded-md` (12px, the brief's own text-input spec) or up to `rounded-xl` depending on component, rather than leaving shadcn's own defaults in place.

### Elevation — surface contrast IS elevation, no shadows anywhere

A genuinely different philosophy than either prior redesign's hairline-border-on-white-background approach: the sage canvas (`--background`) sits behind everything, and every card is a plain white surface (`--card`) with **no border, no shadow** — the colour contrast between the two is the entire depth cue. `Card`'s own shadcn styling (`ring-1 ring-foreground/10`) is the one visible seam, deliberately subtle. Modals (`Dialog`) are the one place a real elevation affordance still matters functionally (distinguishing an overlay from the page beneath it) and use a backdrop blur/dim instead of a shadow, matching Radix's own Dialog primitive default.

---

## 5. Motion tokens

```
--duration-fast01      0.07s    --duration-moderate01  0.15s
--duration-fast02      0.11s    --duration-moderate02  0.24s
--duration-slow01      0.4s     --duration-slow02      0.7s

ease.standard.productive   cubic-bezier(0.2, 0, 0.38, 0.9)
ease.entrance.productive   cubic-bezier(0, 0, 0.38, 0.9)
ease.exit.productive       cubic-bezier(0.2, 0, 1, 0.9)
```

**Decoupled from `@carbon/motion` (WI.D1), same numeric values.** `web/src/motion/tokens.ts`'s `duration`/`ease` are now static literals rather than reading from the `@carbon/motion` npm package (removed from `package.json` in WI.G, confirmed zero other imports first) — the actual millisecond/easing values are unchanged from what shipped under Carbon, since there was no reason to also re-tune timing while re-tuning colour and shape.

**The OTP verification animation (WI.C) is the one genuinely bespoke technique this redesign added**, not sourced from Watermelon or any off-the-shelf component: on Verify, each of the six digit boxes' `x`/`y` position is computed via `cos`/`sin` offsets around a shared centre point and animated into a circular arrangement, then the whole group revolves as one unit for the verifying state — built with the existing `motion` package's primitives, not a new dependency.

---

## 6. Component specifications

**shadcn/ui primitives, not hand-rolled component CSS** — the structural shift from both prior redesigns. Every component below is real source code living in `web/src/components/ui/`, generated by the `shadcn` CLI and then edited in place (shadcn's own philosophy: installed components are owned code, not a black-box dependency) rather than a CSS class defined once in a shared stylesheet.

### Button, Input, Label, Textarea

Radius-patched from shadcn's own defaults to the brief's fixed scale (§4). `destructive` variant's text colour patched from shadcn's stock `text-destructive` to `text-negative-deep` — WI.G's contrast re-check found the stock pairing fails AA at 4.33:1 (§12).

### Badge

Four variants in active use: `default` (lime, reserved for the one place brand-CTA-as-badge makes sense), `secondary` (canvas-soft, the default for tax-treatment/status tags), `destructive` (same negative-deep patch as Button), and an ad-hoc `bg-positive/15 text-positive-deep` override for "paid"/"active"/"verified" states — shadcn's default variant is lime, which stays reserved for the CTA identity per §2.2, so a genuinely positive status needs its own override rather than reusing `default`.

A shared `web/src/components/InvoiceBadges.tsx` (`InvoiceStatusBadge`, `TaxTreatmentBadge`) de-duplicates this logic — it was about to repeat identically across six files (Dashboard, Ledger, ClientDetail, PublicInvoice, InvoiceDetail, plus the invoice builder's success state).

### Table

shadcn's standard `Table`/`TableHeader`/`TableBody`/`TableRow`/`TableHead`/`TableCell` installed in WI.D3 specifically to de-duplicate four repeated raw `<table>` blocks in `Dashboard.tsx`, then reused across every other page's tables in WI.E1/E2 rather than hand-styling `<table>` per page.

### Progress

**⚠️ Patched from shadcn's stock default.** The installed component's indicator defaults to `bg-primary` (lime) — this both violates §2.2's "lime is never a status colour" rule and, WI.G's contrast re-check found, is nearly invisible against the `bg-muted` track regardless (1.29:1, need 3:1 — a light, high-luminance fill has poor contrast against almost any light track, not a track-color-specific problem). Patched to `bg-positive-deep` by default (8.76:1), with `bg-negative`/`bg-warning-deep` conditional overrides for escalation states (Tax reserve progress, Threshold tracker, Accountant readiness) — full numbers in §12.

### Dialog

Replaces the hand-rolled `.modal-backdrop`/`.modal`/`.modal-footer` pattern (InvoiceDetail's email-invoice modal, the only modal in the app) with shadcn's Radix-based `Dialog` — a real focus trap, ESC-to-close, and ARIA semantics that the hand-rolled version never had.

### Chart

`web/src/components/ui/chart.tsx`, shadcn's official Recharts wrapper (confirmed to be exactly what Watermelon's own `chart.json` registry item installs) — `ChartContainer`/`ChartConfig`/`ChartTooltip`/`ChartTooltipContent`/`ChartLegend`/`ChartLegendContent`, replacing hand-themed raw Recharts. **⚠️ Patched for a real Recharts v2-vs-v3 type incompatibility**: the vendored file's `ChartTooltipContent`/`ChartLegendContent` prop types were written against Recharts v2's `Tooltip`/`Legend` type signatures, which flowed `payload`/`label`/`active` through `React.ComponentProps<typeof RechartsPrimitive.Tooltip>` directly. Recharts v3 (this app's installed version, `^3.10.1`) splits that into a separate `TooltipContentProps` type meant for the render-prop path — `ComponentProps<typeof Tooltip>` no longer carries those fields at all. Fixed by retyping against `RechartsPrimitive.TooltipContentProps`/`DefaultLegendContentProps` directly, and switching a `key={item.dataKey}` to a precomputed string key (`DataKey<any>` in v3 can be a function, not assignable to React's `Key` type). Not all charts use `ChartContainer` — the simpler single-series/waterfall charts (`SafeToSpendWaterfall`, `ActualVsProjectedChart`, `GstQuarterlyChart`, `AgingChart`, `RevenueByClientChart`) stay on plain `ResponsiveContainer`, since there's no legend/multi-series config to gain from the wrapper.

### Select, radio, checkbox, file input

Left as styled native `<select>`/`<input type="radio">`/`<input type="checkbox">`/`<input type="file">` elements rather than installing shadcn's `Select`/`RadioGroup`/`Checkbox` primitives — a deliberate scope decision, not an oversight: none of the forms in this app need a custom-styled dropdown's affordances (multi-line options, icons, search), and installing three more primitives for markup that Tailwind utility classes already style adequately (`h-9 rounded-md border border-ink bg-canvas px-3 text-body-sm`) would be net-new surface area without matching need. Revisit if a future form genuinely needs it.

---

## 7. Application shell

```
┌────────────┬──────────────────────────────────────────────────┐
│  Logo      │  Topbar — page title · Create Invoice · 🔔 ? 👤   │
│            ├──────────────────────────────────────────────────┤
│ +Add       │                                                  │
│  Expense   │   Page background sage canvas-soft #e8ebe6        │
│            │   ┌────────────────────────────────────────────┐ │
│  Dashboard │   │  white 24px-radius card, no border/shadow   │ │
│  Invoices  │   └────────────────────────────────────────────┘ │
│  Expenses  │                                                  │
│  Clients   │                                                  │
│  Reports   │                                                  │
│  Settings  │                                                  │
│  Sign out  │                                                  │
└────────────┴──────────────────────────────────────────────────┘
```

Layout/structure unchanged from both prior redesigns (Settings hub, nav item set, mobile slide-in drawer). Active-nav tint is `bg-primary-pale text-positive-deep` — not lime itself (§2.2's rule), and not Carbon's Financial-Blue-subtle either, since that accent no longer exists in this palette.

⚠️ Same pre-existing gaps as both prior redesigns, untouched by this one: no persistent tax-registration-status chip in the topbar, Bell/Help remain inert visual placeholders.

---

## 8. Key screens

### 8.1 Homepage (`/`) — new surface, WI.B

Logged-out visitors previously had no page at all — the app went straight to `/login`. Composition: `NavBar` (logo + Login/Sign up, both pointing at the existing unified email-OTP flow) → hero band (sage canvas, Manrope 900 headline, a real product-mockup card — not the AI-document-parsing graphic originally attached to the request, whose own messaging describes a generic document-comprehension product rather than what Tallyquo does, confirmed directly with the user) → `FeatureGrid` (four cards varying tint per the brief's own "Do" guidance — sage/lime/dark/sage — covering the product's real capabilities) → dark `Footer` band. A `RootGate` component branches the literal `/` path between this page (logged out) and `Shell` (logged in) — see `implementation_plan.md` WI.B for why a repurposed auth guard wasn't the right shape for this.

### 8.2 Login + OTP verification — WI.C

Two-stage form: large email input → six-box OTP entry. The OTP animation is this redesign's single most novel deliverable — three real states, not just a neutral typing state:
1. **Typing**: each box glows/scale-pulses as its digit is entered.
2. **Verifying**: on Verify click, before the API responds, the six boxes animate from their row layout into a circle and revolve together as one unit — a bespoke loading state built from the boxes themselves, not a separate spinner element.
3. **Resolution**: success collapses the circle into a single box with a checkmark (all boxes, including the surviving one, animate to the same shared centre point — an early bug had the surviving box stay at its own row position instead, breaking the centering); failure un-circles into the same red-shake treatment a mistyped code gets, so there's one consistent "wrong" animation regardless of *why* it failed.

Respects `<MotionConfig reducedMotion="user">` — verified the circle-revolve state collapses to instant under reduced motion while the end state (tick or shake) stays reachable.

### 8.3 Dashboard — full rebuild, WI.D1-D3

Same ~30-section spec as the prior redesign's own Dashboard build (`dashboard_design.md`, still the underlying source brief — the *visual* system changed, the *information architecture* didn't), now on shadcn primitives throughout. Hero KPI tiles restyled onto `Card`; `useCountUp`'s "never animate a figure from zero on first mount" rule carried through unchanged. Every chart migrated per §6/§2.4's chart-library and colour-palette rules. Tax reserve/Threshold tracker/Accountant readiness use `Progress` with the patched default indicator colour (§6, §12).

### 8.4 Everything else — a real per-page sweep, not a free cascade (WI.E1/E2)

**⚠️ Unlike Carbon's CB.H, this sweep was not free.** Sovereign Ledger's own class-reuse architecture (`.block`, `.badge`, shared `table`/`th`/`td`) is what let Carbon's token rewrite cascade with zero code changes — Tailwind's utility-classes-in-JSX model doesn't cascade that way. Every page's markup changed: Settings, Reports, Ledger, Recurring, Clients, ClientDetail, EmailAccounts, Profile, PublicInvoice (WI.E1); ComplianceChecklist, InvoiceBuilder, InvoiceDetail, TemplateEditor (WI.E2); and **Expenses.tsx**, found missing from the original page inventory during WI.G's own pre-deletion grep sweep and migrated then rather than silently deleting the stylesheet it still depended on.

Business logic on every one of these pages is unchanged from whatever the prior redesign or an earlier functional phase shipped — this redesign is a visual-system-and-foundation replacement, not a feature phase.

---

## 9. Invoice document design — unchanged boundary, now genuinely self-contained

The generated invoice document (`InvoiceDocument.tsx`, `pdf_renderer.py`) remains **a separate design system from the app, sharing only tokens** — the same principle all three redesigns have carried forward from Sovereign Ledger's own original §9. Flat, high-contrast, print-appropriate — Wise's pill-radius/lime-accent software-UI language does not belong on a printed business document sent to clients, same reasoning that kept Carbon's zero-radius language off it too.

**⚠️ Genuinely new this round: the document's styling is now fully self-contained**, not sharing a stylesheet with the app at all. Both prior redesigns' `InvoiceDocument.tsx` read two classes (`.amount`, `.caption`) plus a dozen `.invoice-document*` rules from the same app-wide `index.css` every other page used — a real, if narrow, coupling. WI.G deleted `index.css` entirely (every page had migrated off it by then), which would have silently broken the document's rendering had its styling not been extracted first. It now lives in its own `web/src/components/InvoiceDocument.css`, imported directly by the component, with the *exact* frozen values (not `var()` references into a stylesheet that no longer exists) the document has always used — same fonts (already fallen back to `system-ui` since IBM Plex Sans/Mono were removed in WI.A, a pre-existing state, not newly introduced here), same spacing, same zero border-radius, same colours. Pixel-verified identical before/after the extraction via a real browser screenshot comparison.

This is a deliberate three-redesigns-running invariant, not an oversight: an invoice a client receives shouldn't change appearance every time the vendor's own dashboard gets re-skinned.

---

## 10. Motion — the cinematic layer, carried forward

Every animation category Carbon's own CB.I established still exists and still works the same way, just re-pointed at the decoupled tokens (§5): route transitions, staggered tile/panel entrance, KPI count-ups that never animate from zero on first mount, chart draw-ins, hover/press feedback. `prefers-reduced-motion: reduce` still implemented in the same two layers — `<MotionConfig reducedMotion="user">` (`main.tsx`) plus a global CSS fallback, now living in `styles/tailwind.css`'s own rules rather than `index.css` (carried forward explicitly during WI.G's cleanup, not lost when `index.css` was deleted — it's a universal `*` selector guard covering every plain-CSS `transition`, including this redesign's own Tailwind `transition-colors`/`transition-all` utility classes, not just Carbon-era ones).

**What's genuinely new is §5's OTP orbit animation** — the one place this redesign built a bespoke motion technique rather than reusing the existing tile-entrance/count-up/chart-draw-in vocabulary.

---

## 11. Voice and copy

Unchanged across all three redesigns — error copy, empty states, and the "every estimated figure is labelled" rule all carry forward verbatim. This redesign touched visual language, foundation, and two new surfaces, not product copy.

---

## 12. Accessibility

WCAG 2.1 AA as a floor, unchanged. **Re-verified 2026-08-15 against the actual shipped values** (computed via the WCAG relative-luminance formula, not estimated, not assumed to pass because the values come from a real brand's own design language) — the same discipline both prior redesigns' own reconciliation passes used, which is what caught real failures each time. This pass caught different, also-real ones:

- `--color-ink` `#0e0f0c` on white: **19.8:1**. `--color-body` `#454745` on canvas-soft: **7.79:1** — both comfortably clear AA.
- **⚠️ `--color-mute`, the brief's own literal `#868685`, fails AA as text against both app backgrounds**: 3.64:1 on the white card, 3.03:1 on the sage canvas (need 4.5:1) — and this token is used almost everywhere in the app as caption/secondary text (KPI sub-labels, empty-state copy, secondary table columns), not as a fill. Darkened to `#5f5e5a`: **6.49:1 / 5.40:1**, comfortable margin on both surfaces. This is the headline finding of this pass — a pervasive, previously-unchecked failure, not an isolated one.
- **⚠️ shadcn's stock `destructive` variant** (`text-destructive` on `bg-destructive/10`, used by both `Button` and `Badge`) fails at **4.33:1**. Patched to `text-negative-deep` on the same tint: **6.30:1**.
- **⚠️ `--color-positive` as text or a small icon fill** — not as a large fill — fails the relevant threshold everywhere it was tried: KPI hero figures (2.92:1 against the 4.5:1 text floor), the Business Momentum table's %-change cells (same), the Compliance checklist's done-icon circle (2.92:1 against the 3:1 non-text-UI floor), and the OTP success checkmark (same). All four now use `--color-positive-deep` instead: **10.01:1** in every case. `--color-positive` itself is untouched for large-surface fills (waterfall chart bars, the Actual-vs-projected line) where it already passes the non-text threshold comfortably.
- **⚠️ `--color-warning-deep` as text** fails at **4.22:1** (Needs-your-attention's medium-severity items, the FX-conversion-unavailable notice on non-CAD invoices). `--color-warning-content` instead: **10.86:1**.
- **⚠️ `Progress`'s stock default indicator** (`bg-primary`, lime) fails the 3:1 non-text floor against the muted track at **1.29:1** — and separately violates §2.2's "lime is never a status colour" rule. Default indicator patched to `bg-positive-deep`: **8.76:1**. The warning-escalation override (`bg-warning`) also failed at **1.28:1**; patched to `bg-warning-deep`: **3.69:1**. The negative-escalation override (`bg-negative`) already passed at 4.38:1 and was left as-is.
- **Reviewed and accepted, not fixed**: the Tax+CPP reserve card's decorative left-accent border (`border-l-warning`, 1.46:1) and `--color-divider` itself (1.41:1) — both purely decorative, non-text elements not required to identify or operate a UI component (WCAG 1.4.11's own exception for decorative content), same category as a plain divider line.
- Never colour alone: unchanged — every status/tax badge still carries a text label.
- Touch targets, focus rings, `aria-describedby` form-error association: unchanged.

All fixed pairs re-verified by recomputing every ratio after the change (all pass with real margin, not knife-edge) and via a real browser walkthrough confirming no visual regressions.

---

## 13. Token reference

**Copied verbatim from the shipped `web/src/styles/tailwind.css` `@theme` block (2026-08-15, post-WI.G contrast fixes), not re-derived.**

```css
@theme {
  --radius-none: 0px;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-xl: 24px;
  --radius-pill: 9999px;
  --radius-full: 9999px;

  --font-display: 'Manrope Variable', 'Manrope', system-ui, sans-serif;
  --font-sans: 'Inter Variable', 'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono Variable', 'JetBrains Mono', ui-monospace, monospace;

  --text-display-mega: 126px; --text-display-mega--line-height: 107.1px; --text-display-mega--font-weight: 900;
  --text-display-xxl: 96px;   --text-display-xxl--line-height: 81.6px;  --text-display-xxl--font-weight: 900;
  --text-display-xl: 64px;    --text-display-xl--line-height: 54.4px;  --text-display-xl--font-weight: 900;
  --text-display-lg: 47px;    --text-display-lg--line-height: 70.5px;  --text-display-lg--font-weight: 400;
  --text-display-md: 40px;    --text-display-md--line-height: 34px;    --text-display-md--font-weight: 900;
  --text-display-sm: 32px;    --text-display-sm--line-height: 38.4px;  --text-display-sm--font-weight: 600;
  --text-display-xs: 24px;    --text-display-xs--line-height: 31.2px;  --text-display-xs--font-weight: 600;

  --text-body-lg: 20px;   --text-body-lg--line-height: 30px;
  --text-body-md: 16px;   --text-body-md--line-height: 24px;
  --text-body-sm: 14px;   --text-body-sm--line-height: 20px;
  --text-caption: 12px;   --text-caption--line-height: 16px;
  --text-button-md: 16px; --text-button-md--line-height: 24px; --text-button-md--font-weight: 600;

  /* brand -- verbatim from the brief except --color-mute, see the ⚠️ in §2.1/§12 */
  --color-primary-active: #cdffad;
  --color-primary-neutral: #c5edab;
  --color-primary-pale: #e2f6d5;
  --color-ink: #0e0f0c;
  --color-ink-deep: #163300;
  --color-body: #454745;
  --color-mute: #5f5e5a;
  --color-canvas: #ffffff;
  --color-canvas-soft: #e8ebe6;
  --color-positive: #2ead4b;
  --color-positive-deep: #054d28;
  --color-warning: #ffd11a;
  --color-warning-deep: #b86700;
  --color-warning-content: #4a3b1c;
  --color-negative: #d03238;
  --color-negative-deep: #a72027;
  --color-negative-darkest: #a7000d;
  --color-negative-bg: #320707;
  --color-accent-orange: #ffc091;
  --color-accent-cyan: #38c8ff;

  /* net-addition, see §2.1 */
  --color-divider: #d6dbd1;
}

/* shadcn semantic layer -- :root, re-exposed via a separate @theme inline block */
:root {
  --background: #e8ebe6;      --foreground: #0e0f0c;
  --card: #ffffff;            --card-foreground: #0e0f0c;
  --popover: #ffffff;         --popover-foreground: #0e0f0c;
  --primary: #9fe870;         --primary-foreground: #0e0f0c;
  --secondary: #e8ebe6;       --secondary-foreground: #0e0f0c;
  --muted: #e2f6d5;           --muted-foreground: #868685;
  --accent: #e2f6d5;          --accent-foreground: #0e0f0c;
  --destructive: #d03238;     --destructive-foreground: #ffffff;
  --border: #0e0f0c;          --input: #0e0f0c;
  --ring: #9fe870;
  --chart-1: #2ead4b; --chart-2: #38c8ff; --chart-3: #ffc091;
  --chart-4: #ffd11a; --chart-5: #868685; --chart-6: #d03238;
  --sidebar: #ffffff; --sidebar-foreground: #0e0f0c;
  --sidebar-primary: #9fe870; --sidebar-primary-foreground: #0e0f0c;
  --sidebar-accent: #e2f6d5;  --sidebar-accent-foreground: #0e0f0c;
  --sidebar-border: #0e0f0c;  --sidebar-ring: #9fe870;
}
```

Template `theme` JSON is unchanged — still a constrained subset of tokens, still defaults new templates to `#1A365D` (the invoice document's own frozen accent, §9 — outside this redesign's scope by design).

---

## 14. Known gaps carried into this redesign, not fixed by it

Stated plainly, matching this document's own long-standing convention of an honest record over a flattering one:

- **No frontend CI workflow exists in this repo.** `.github/workflows/` only has `api-ci.yml` (path-filtered to `api/**`) plus two scheduled jobs. Every frontend-only phase of this redesign was verified via local `npm run build`/`npm run lint` plus real Playwright browser walkthroughs with seeded data and screenshots read back — never a CI gate. Pre-existing gap across all three redesigns, not introduced or fixed here.
- **Native `<select>`/checkbox/radio/file-input elements stay unstyled shadcn primitives** (§6) — a deliberate scope decision, revisit if a future form's needs outgrow plain Tailwind-styled native controls.
- **Topbar tax-registration-status chip, Bell/Help notification backends** — unchanged gaps carried from Sovereign Ledger through Carbon through this redesign (§7).
- **Payment-speed trend sparkline and fastest/slowest-client breakdown** — deliberately deferred v1 scoping from Carbon's own CB.D, untouched here.
- **Dark mode** — still deferred (§2.5), `.dark` still mirrors `:root`.
