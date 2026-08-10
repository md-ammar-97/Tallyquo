---
name: Sovereign Ledger
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#43474e'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#74777f'
  outline-variant: '#c4c6cf'
  surface-tint: '#455f88'
  primary: '#002045'
  on-primary: '#ffffff'
  primary-container: '#1a365d'
  on-primary-container: '#86a0cd'
  inverse-primary: '#adc7f7'
  secondary: '#0a6c44'
  on-secondary: '#ffffff'
  secondary-container: '#9ff5c1'
  on-secondary-container: '#167249'
  tertiary: '#311c00'
  on-tertiary: '#ffffff'
  tertiary-container: '#4e2f00'
  on-tertiary-container: '#d39137'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d6e3ff'
  primary-fixed-dim: '#adc7f7'
  on-primary-fixed: '#001b3c'
  on-primary-fixed-variant: '#2d476f'
  secondary-fixed: '#9ff5c1'
  secondary-fixed-dim: '#83d8a6'
  on-secondary-fixed: '#002111'
  on-secondary-fixed-variant: '#005231'
  tertiary-fixed: '#ffddb8'
  tertiary-fixed-dim: '#ffb95f'
  on-tertiary-fixed: '#2a1700'
  on-tertiary-fixed-variant: '#653e00'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
  financial-blue: '#1A365D'
  compliance-green: '#2F855A'
  set-aside-gold: '#B7791F'
  border-subtle: '#E2E8F0'
  text-main: '#0F172A'
  text-muted: '#64748B'
  error-red: '#C53030'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 8px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 40px
  container-max: 1200px
---

## Brand & Style

The design system is built on the pillars of **Professionalism, Reliability, and Clarity**. It serves as a "protective shield" for Canadian sole proprietors, moving away from the ephemeral trends of "fintech-playful" aesthetics toward an "accountant-approved" visual language. The brand personality is authoritative yet supportive—it doesn't just record data; it ensures correctness.

The chosen style is **Minimalist / Corporate Modern**. It prioritizes high-density information display and structural integrity. Every element is intentional, utilizing heavy whitespace and a strict grid to reduce the cognitive load associated with tax and compliance. The UI is designed to feel immutable and secure, reflecting the legal weight of the records it manages.

## Colors

The palette is anchored by **Financial Blue**, evoking the stability of a traditional institution. **Compliance Green** is used strictly for success states and "locked" records, signaling that a document meets regulatory standards. **Set-aside Gold** serves as a high-visibility warning color, specifically reserved for tax liabilities and "small supplier" threshold alerts.

Surface colors utilize a neutral slate scale to maintain high contrast with text. We avoid pure black for text, opting for a deep navy-slate (`#0F172A`) to maintain a sophisticated professional tone.

## Typography

Typography is focused on **legibility and document hierarchy**. **Inter** is the primary typeface for its exceptional clarity in digital interfaces. For numerical data, invoice numbers, and tax calculations, **JetBrains Mono** is introduced to provide a distinct "tabular" feel that aids in scanning columns of figures.

- **Headlines:** Use tight letter spacing and bold weights to establish clear section breaks.
- **Data Display:** All financial figures should use the `data-mono` style to ensure decimal points align perfectly in vertical columns.
- **Legal Labels:** Small, uppercase labels are used for metadata like "GST/HST NUMBER" to differentiate them from user-generated content.

## Layout & Spacing

This design system employs a **Fixed Grid** philosophy for desktop to mirror the structured nature of physical ledger books. 

- **Grid Model:** 12-column grid with a 24px gutter.
- **Ledger View:** Ledger tables should stretch to the full container width but maintain strict column proportions: `Date (120px) | Description (Fluid) | Category (150px) | Tax (100px) | Total (120px)`.
- **Responsive Behavior:** On mobile, complex tables reflow into "Summary Cards" where the Primary Amount and Status Label are prioritized in the top-right corner.

## Elevation & Depth

To maintain a "compliant and flat" feel, elevation is used sparingly. We utilize **Low-contrast outlines** over shadows to define structure.

- **Surface Tiers:** The main background is a soft neutral (`#F8FAFC`). Primary content containers use a white background with a 1px border (`#E2E8F0`).
- **Active States:** Subtle 2px "Financial Blue" borders indicate focused input fields.
- **Modals:** Use a heavy backdrop blur (12px) with no shadow to focus the user entirely on the data entry task, preventing peripheral distraction during high-stakes compliance workflows.

## Shapes

The shape language is **Soft (0.25rem)**. This provides a subtle hint of modern UI friendliness without compromising the professional, rigid structure required for financial documents. 

- **Buttons & Inputs:** 4px (0.25rem) radius.
- **Invoices & Large Cards:** 8px (0.5rem) radius to differentiate "Documents" from "UI Controls."
- **Data Badges:** 2px radius for a sharper, more "stamped" look on status indicators like "PAID" or "DRAFT."

## Components

### Structured Tables (Ledgers)
The core of the app. Rows must have a hover state using a subtle tint of Financial Blue. Every 5th row should have a slightly different background tint to aid horizontal eye-tracking across wide data sets.

### Set-aside Cards
Used for tax warnings. These cards feature a 4px left-border of "Set-aside Gold" and a "data-mono" figure for the amount to be saved. They must include a clear "Calculation Logic" tooltip explaining the percentage used.

### Invoices & Previews
Invoices should render with 0px borders in preview mode to simulate a printed page. High contrast is mandatory. The "Total Due" section must be highlighted with a subtle Financial Blue background to draw the eye instantly.

### Buttons & Inputs
- **Primary Action:** Solid Financial Blue with white text. No gradients.
- **Status Chips:** Small, uppercase text with a 10% opacity background of the status color (e.g., 10% Green for "Paid").
- **Input Fields:** Must include a persistent label. Ghost text is permitted only for format examples (e.g., "YYYY-MM-DD").

### Compliance Checklist
A vertical stepper component used during onboarding or invoice creation. Incomplete items use Text-muted; completed items use Compliance Green checkmarks.