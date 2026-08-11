# Dashboard Design — Sole Proprietor Invoicing & Financial Record-Keeping App

**Working title:** SolePop  
**Document type:** Dashboard UX / Product Design Specification  
**Status:** Draft v0.1  
**Date:** August 2026  

**2026-08-11 note:** The dashboard described here shipped as part of the IBM Carbon redesign (`implementation_plan.md` §8, phases CB.E-CB.G; `design.md` §8.1 is now the merged, living spec for what actually shipped, including deliberate deviations flagged inline there — e.g. the waterfall's basis, which section 5 below sketches differently). This document is kept as the original source brief, not a second spec to keep in sync by hand — most of what's below shipped close to as written; where it didn't, `design.md` §8.1 says so.

---

## 1. Dashboard Design Principle

The dashboard should **not look like a traditional accounting dashboard**.

The target user is a Canadian sole proprietor who wants simple answers to a small number of important questions:

1. How much did I make?
2. How much did I spend?
3. How much can I safely spend?
4. How much should I reserve for income tax and CPP?
5. How much GST/HST do I currently owe?
6. Who still owes me money?
7. Am I on track to hit my annual income target?
8. Is my bookkeeping ready for my accountant?

The dashboard should therefore function as a **financial control center for a sole proprietor**, rather than as a bookkeeping or double-entry accounting interface.

The five hero concepts should be:

- **Revenue**
- **Net Business Income**
- **Safe to Spend**
- **Tax Reserve**
- **Money Owed to You**

Everything else on the dashboard should explain, forecast, or help the user act on one of these five.

---

## 2. Dashboard Information Hierarchy

Recommended desktop layout:

1. Date / reporting-period selector
2. Hero financial KPIs
3. Business performance chart
4. Safe-to-spend / tax overview
5. Revenue projection
6. GST/HST section
7. Accounts receivable / outstanding invoices
8. Client concentration
9. Expenses
10. Recurring income
11. Business momentum
12. Accountant readiness
13. Needs Your Attention
14. Recent activity

The dashboard should default to **Year to Date**, while allowing:

- This month
- Last month
- This quarter
- Last quarter
- Year to date
- Last year
- Custom range

---

# 3. Hero KPI Cards

These should appear immediately below the page title.

## 3.1 Revenue YTD

**Example:** `$84,000`

Definition:

> Total business revenue represented by issued invoices during the selected reporting period.

Secondary information:

- Change vs previous comparable period
- Number of issued invoices
- Projected annual revenue

Example:

> **$84,000**  
> Revenue YTD  
> ↑ 14% vs same period last year

---

## 3.2 Expenses YTD

**Example:** `$9,200`

Definition:

> Total recorded business expenses during the selected period after applying business-use percentages where applicable.

Secondary information:

- Month-over-month change
- Number of expenses
- Number missing receipts

---

## 3.3 Net Business Income

**Example:** `$74,800`

Formula:

```text
Revenue − Eligible Business Expenses
```

This should be clearly distinguished from cash in bank and from taxable income calculated on a personal tax return.

Example:

> **$74,800**  
> Estimated net business income

---

## 3.4 Safe to Spend

This should be one of the most important metrics in the entire product.

**Example:** `$53,400`

Conceptual calculation:

```text
Net Business Income
− Estimated Income Tax
− Estimated CPP
= Safe to Spend
```

GST/HST should remain outside this calculation because collected sales tax is not the user's income.

Example:

> **$53,400**  
> Estimated safe to spend  
> After recommended tax + CPP reserve

Expandable explanation:

```text
Revenue                         $84,000
Expenses                        -$9,200
Estimated Income Tax           -$14,900
Estimated CPP                   -$6,500
---------------------------------------
Estimated Safe to Spend         $53,400
```

Every displayed amount must clearly state that it is an estimate and not tax advice.

---

## 3.5 Estimated Tax + CPP Set-Aside

**Example:** `$21,400`

Breakdown:

- Estimated federal income tax
- Estimated provincial income tax
- Estimated CPP
- Recommended reserve percentage

Example:

> **$21,400**  
> Recommended set-aside  
> 28.6% of estimated net income

---

## 3.6 Outstanding Invoices

**Example:** `$12,750`

Secondary information:

> 4 invoices outstanding · 2 overdue

Clicking the card should open the invoice ledger pre-filtered to unpaid invoices.

---

## 3.7 GST/HST Net Owing

**Example:** `$5,180`

Conceptual calculation:

```text
GST/HST collected
− Eligible Input Tax Credits
= Estimated GST/HST net owing
```

This metric should always remain visually separate from income tax and CPP.

---

## 3.8 Projected Annual Revenue

**Example:** `$116,400`

Projection sources:

- Issued invoices
- Current YTD performance
- Scheduled recurring invoices
- Optional user-declared annual target

Secondary messaging:

> Projected annual revenue is $3,600 below your $120,000 target.

---

# 4. Business Performance Chart

## Chart: Revenue, Expenses & Net Income

This should be the main dashboard chart.

### Recommended visualization

Multi-series line or bar chart showing:

- Revenue
- Expenses
- Net business income

### Period options

- Monthly
- Quarterly
- Annual

Example dataset:

| Month | Revenue | Expenses | Net Income |
|---|---:|---:|---:|
| Jan | $9,500 | $1,400 | $8,100 |
| Feb | $10,000 | $1,650 | $8,350 |
| Mar | $11,500 | $2,000 | $9,500 |
| Apr | $9,800 | $1,300 | $8,500 |
| May | $12,400 | $2,100 | $10,300 |
| Jun | $13,000 | $1,950 | $11,050 |

Hover state should show exact values.

### User question answered

> Is my business getting better or worse?

---

# 5. Money Breakdown / Waterfall

## Chart: Where Your Revenue Goes

A waterfall chart should illustrate how revenue becomes usable income.

Example:

```text
Revenue                         $84,000
↓ Expenses                      -$9,200
↓ Estimated Income Tax         -$14,900
↓ Estimated CPP                 -$6,500
---------------------------------------
Safe to Spend                   $53,400
```

This visualization is preferable to a pie chart because the components are sequential deductions rather than equal categories.

### User question answered

> Of everything I earned, how much is actually mine?

---

# 6. Income Projection

## Chart: Actual vs Projected Annual Revenue

Display actual cumulative revenue as a solid line and projected revenue as a dashed continuation.

Example:

```text
$120k ┤                         ○ Projected
      │                       /
$100k ┤                    --/
      │                  /
 $80k ┤               ● Today
      │             /
 $60k ┤          /
      │       /
 $40k ┤    /
      └──────────────────────────
       Jan Mar May Jul Sep Nov Dec
```

### Supporting KPIs

- Revenue YTD
- Projected annual revenue
- User income target
- Forecast variance

Example:

> Projected: **$116,400**  
> Target: **$120,000**  
> Gap: **-$3,600**

Projection assumptions should be expandable.

---

# 7. Tax Reserve Progress

Users should optionally be able to enter how much money they have physically moved into a tax reserve account.

## KPI

**Recommended reserve:** `$21,400`

**Actual amount reserved:** `$16,000`

Progress:

```text
$16,000 / $21,400

████████████████░░░░ 75%
```

Supporting message:

> Your current reserve is approximately **$5,400 below** the recommended amount.

Avoid saying:

> You owe $5,400.

Use language such as:

- Recommended reserve
- Estimated shortfall
- Suggested tax set-aside

---

# 8. GST/HST Control Center

GST/HST deserves a dedicated dashboard section because the money is collected on behalf of government.

## Metrics

### GST/HST Collected

Example: `$7,350`

### Input Tax Credits

Example: `$2,170`

### Estimated Net GST/HST

Example: `$5,180`

Formula:

```text
$7,350 GST/HST collected
− $2,170 estimated ITCs
= $5,180 estimated GST/HST net owing
```

Additional information:

- Filing period
- Registration status
- Filing frequency
- Amount collected since previous filing period
- Expenses with claimable ITCs

---

# 9. GST/HST Small-Supplier Threshold Tracker

This should be one of the distinctive SolePop dashboard elements.

## Example

```text
GST/HST Registration Threshold

$24,600 / $30,000
████████████████░░░░ 82%
```

Threshold calculations should use the required rolling four-consecutive-calendar-quarter logic and include zero-rated taxable supplies where applicable.

### Alert states

#### Below 75%

Normal informational state.

#### 75%

> You have reached 75% of the GST/HST small-supplier threshold.

#### 90%

> You are approaching the GST/HST registration threshold.

#### Crossed

> Your taxable supplies have crossed the tracked threshold. Review your GST/HST registration obligations.

Do not provide definitive legal or tax advice.

---

# 10. Outstanding Invoices

## KPI

**Outstanding:** `$12,750`

Supporting:

> 4 unpaid invoices · 2 overdue

## Accounts Receivable Aging Chart

Recommended buckets:

- Not yet due
- 1–30 days overdue
- 31–60 days
- 61–90 days
- 90+ days

Example:

| Aging Bucket | Amount |
|---|---:|
| Not due | $4,000 |
| 1–30 days | $5,500 |
| 31–60 days | $2,000 |
| 61–90 days | $1,250 |
| 90+ days | $0 |

Primary callout:

> **$8,750 is currently overdue.**

Clicking a bucket should open the invoice ledger filtered to those invoices.

---

# 11. Invoice Status

A compact donut or small card can display the current invoice distribution.

Example:

### 54 invoices this year

- Paid — 38
- Outstanding — 9
- Overdue — 4
- Draft — 3

This should remain a secondary operational visualization rather than a hero chart.

---

# 12. Payment Collection Performance

## KPI: Average Days to Payment

Example:

> **17 days**  
> ↓ 4 days vs previous quarter

Chart the trend over time.

Additional useful metrics:

- Fastest-paying client
- Slowest-paying client
- Average days overdue
- Percentage of invoices paid on time

These become more valuable once payment history accumulates.

---

# 13. Revenue by Client

Because the primary persona usually has only a small number of recurring clients, client concentration is highly relevant.

## Recommended visualization

Horizontal bar chart.

Example:

```text
Born West       ███████████████  52%
ABC Consulting  ███████          24%
XYZ Inc         ████             14%
Others          ███              10%
```

Supporting metrics:

- Largest client
- Active clients
- Average revenue per client
- Percentage of total revenue from largest client

Example insight:

> 52% of your revenue currently comes from one client.

Avoid making this sound like financial advice; present it as business concentration information.

---

# 14. Client-Level Dashboard

Clicking a client should open a client-specific performance page.

Example:

## Born West

### Key metrics

- Total billed YTD
- Total collected
- Outstanding
- Average monthly billing
- Average days to payment
- Active recurring schedule
- Tax treatment
- Last invoice
- Next scheduled invoice

## Chart: Monthly Client Revenue

Example:

```text
$8k ┤ █   █   █   █   █   █
$6k ┤ █   █   █   █   █   █
$4k ┤
     └────────────────────────
       Feb Mar Apr May Jun Jul
```

Views:

- Monthly
- Quarterly
- Annual
- Custom

This directly answers:

> How much did I bill this client in each period?

---

# 15. Expense Category Breakdown

## Chart: Expenses by CRA/T2125 Category

Recommended donut chart when category count remains manageable.

Example categories:

- Travel
- Software
- Professional fees
- Meals & entertainment
- Office expenses
- Supplies
- Motor vehicle
- Business-use-of-home
- Advertising
- Other

Example summary:

> **$12,740 total expenses**

Supporting insight:

> $1,840 of GST/HST may be associated with recorded expenses.

Only show ITC language where relevant to the user's GST/HST registration state.

---

# 16. Monthly Expense Trend

Use a line or bar chart showing expenses over time.

Example:

```text
$4k ┤         █
$3k ┤         █
$2k ┤ █   █   █       █
$1k ┤ █   █   █   █   █
    └────────────────────
      Mar Apr May Jun Jul
```

Potential insight:

> July expenses were 38% higher than your recent monthly average.

Clicking the month should open the filtered expense ledger.

---

# 17. Receipt Completeness

A useful record-keeping KPI:

### Expenses with receipts

**91%**

Example:

```text
118 / 130 expenses supported
██████████████████░░ 91%
```

Secondary actions:

> 12 receipts missing

Clicking opens those expenses.

This supports the product's core year-end record-keeping value.

---

# 18. Recurring Revenue

## KPI

**Expected recurring revenue:** `$9,500 / month`

Secondary:

> 5 active recurring invoice schedules

## Upcoming Recurring Revenue

| Month | Expected |
|---|---:|
| August | $9,500 |
| September | $9,500 |
| October | $8,000 |

This data should feed the annual income forecast.

---

# 19. Business Momentum

Create a small comparison section showing current period vs previous comparable period.

Example:

| Metric | Current | Change |
|---|---:|---:|
| Revenue | $12,400 | ↑ 14% |
| Expenses | $2,100 | ↓ 8% |
| Net income | $10,300 | ↑ 20% |
| Outstanding | $4,500 | ↑ $1,500 |

This answers:

> How am I doing compared with last month?

---

# 20. Year-over-Year Performance

Once sufficient historical data exists:

## Example

### Revenue

**$84,000**  
↑ 18% vs previous year

### Expenses

**$12,400**  
↑ 7%

### Net Income

**$71,600**  
↑ 20%

Useful charts:

- Monthly revenue current year vs previous year
- Quarterly net income comparison
- Expense trend comparison

This section can remain hidden until at least one prior comparable year exists.

---

# 21. Accountant Readiness Score

This could become a distinctive SolePop feature.

## Example

### Year-End Readiness

**82% Ready**

```text
████████████████░░░░
```

Potential factors:

- Expenses with receipts
- Uncategorized expenses
- Unconfirmed OCR records
- Missing tax values
- Missing client addresses
- Missing non-residency evidence
- Invoice inconsistencies
- Outstanding draft corrections
- Missing payment statuses
- Incomplete business profile
- Missing tax registration details

Example details:

> 12 expenses need attention  
> 3 receipts are missing  
> 1 non-resident client is missing supporting evidence

The readiness score should remain explainable and should never imply CRA compliance certification.

---

# 22. Needs Your Attention

This should be one of the most valuable areas of the dashboard.

Rather than displaying only analytics, the product should surface actions.

## Example

### Needs Your Attention

🔴 **Invoice ORB-2026-018 is 23 days overdue**  
Send reminder / View invoice

🟠 **GST/HST threshold is 82% reached**  
Review threshold tracker

🟡 **4 receipts need review**  
Review expenses

🟡 **Tax reserve is $5,400 below recommendation**  
View calculation

🔵 **August recurring invoice for Born West is ready**  
Review draft

🔵 **Projected annual revenue increased to $116,400**  
View forecast

Recommended priority:

1. Critical financial/compliance risks
2. Overdue money
3. Missing records
4. Upcoming actions
5. Informational insights

---

# 23. Recent Activity

A lightweight recent activity feed can sit at the bottom of the dashboard.

Example:

```text
Today
Invoice ORB-2026-024 issued — $7,000
Receipt added — Adobe — $31.63
Invoice ORB-2026-019 marked paid

Yesterday
Recurring invoice draft generated — Born West
Expense categorized — Air Canada — Travel
```

This should not become a full audit-log UI. It is only a user-friendly activity summary.

---

# 24. Recommended Dashboard Layout

Conceptual desktop layout:

```text
────────────────────────────────────────────────────────────────
 Good afternoon                          2026 YTD ▼
────────────────────────────────────────────────────────────────

 Revenue      Expenses       Net Income      Safe to Spend
 $84,000      $9,200         $74,800         $53,400

 Tax + CPP Reserve           GST/HST Owing   Outstanding
 $21,400                     $5,180          $12,750

────────────────────────────────────────────────────────────────

 BUSINESS PERFORMANCE

 [ Revenue / Expenses / Net Income — 12-month chart ]

────────────────────────────────┬───────────────────────────────
 INCOME PROJECTION              │ TAX RESERVE
 $116,400 projected             │ $16k / $21.4k reserved
 Actual ━━━ Projected ┄┄        │ ███████████████░░
────────────────────────────────┼───────────────────────────────
 GST/HST THRESHOLD              │ OUTSTANDING
 $24,600 / $30,000              │ $12,750
 ████████████████░░             │ 2 invoices overdue
────────────────────────────────┴───────────────────────────────

 REVENUE BY CLIENT

 Born West       ███████████████
 ABC Consulting  ███████
 XYZ Inc         ████

────────────────────────────────────────────────────────────────

 EXPENSES

 [ Expense category chart ]     [ Monthly expense trend ]

────────────────────────────────────────────────────────────────

 YEAR-END READINESS

 82% ready
 ████████████████░░░

 12 expenses need attention
 3 receipts missing

────────────────────────────────────────────────────────────────

 NEEDS YOUR ATTENTION

 🔴 2 overdue invoices
 🟠 GST/HST threshold at 82%
 🟡 4 receipts require review
 🔵 August recurring invoice ready

────────────────────────────────────────────────────────────────

 RECENT ACTIVITY

 Invoice issued...
 Receipt uploaded...
 Payment recorded...

────────────────────────────────────────────────────────────────
```

---

# 25. Mobile Dashboard

The mobile experience should not attempt to reproduce every desktop card.

Recommended priority:

1. Safe to Spend
2. Revenue
3. Outstanding
4. Tax Reserve
5. GST/HST
6. Needs Your Attention
7. Business performance chart
8. Recent invoices
9. Receipt capture shortcut

Suggested top area:

```text
Safe to Spend
$53,400

Revenue
$84,000

Tax + CPP Reserve
$21,400

Outstanding
$12,750
```

Primary floating action:

**+ Add**

Options:

- Invoice
- Expense / Receipt
- Payment
- Client

Receipt capture should be reachable in one or two taps.

---

# 26. Dashboard by Product Phase

## Phase 1 — Correct Invoices

Dashboard should initially include:

- Revenue YTD
- Number of invoices issued
- Revenue trend
- Revenue by client
- Tax charged
- GST/HST registration threshold
- Recent invoices
- Important tax / profile alerts

The dashboard should intentionally remain small.

---

## Phase 2 — The Record

Add:

- Expenses YTD
- Expense trend
- Expense category breakdown
- Receipt completeness
- Net business income
- Outstanding invoices
- Aging report
- Invoice status
- Average days to payment
- Recurring revenue
- Client-level rollups

---

## Phase 3 — The Answer

This is where the dashboard becomes a major differentiating feature.

Add:

- Safe to Spend
- Estimated income tax
- Estimated CPP
- Recommended set-aside
- Tax reserve progress
- Annual income forecast
- Actual vs projected revenue
- GST/HST net owing
- Input tax credits
- Instalment warning
- Accountant readiness
- Year-end accountant-pack status

---

## Phase 4 — Advanced Insights

Potential additions:

- Multi-currency revenue
- FX impact
- Bank balance / transaction feed
- Cash-flow forecast
- Accounting integration status
- Historical year-over-year trends
- Advanced client concentration
- Estimated quarterly instalment schedule
- Accountant collaboration indicators

These should only be added if they do not compromise the product's simplicity.

---

# 27. Dashboard KPIs — Complete List

## Revenue

- Revenue YTD
- Revenue MTD
- Revenue QTD
- Projected annual revenue
- Recurring monthly revenue
- Revenue growth
- Revenue by client
- Revenue concentration
- Average invoice value
- Number of invoices issued

## Expenses

- Expenses YTD
- Expenses MTD
- Expenses by category
- Expense growth
- Expenses without receipts
- Receipt coverage
- Business-use adjusted expenses
- GST/HST paid on expenses
- Recurring expenses

## Profit / Income

- Net business income
- Net income margin
- Monthly net income
- Projected annual net income
- Safe to Spend

## Tax

- Income tax estimate
- CPP estimate
- Combined recommended reserve
- Recommended reserve %
- Actual reserve amount
- Reserve shortfall
- GST/HST collected
- Estimated ITCs
- Net GST/HST owing
- Small-supplier threshold progress
- Filing period
- Instalment warning

## Accounts Receivable

- Outstanding amount
- Overdue amount
- Outstanding invoice count
- Overdue invoice count
- Aging buckets
- Average days to pay
- On-time payment rate
- Client payment speed

## Clients

- Active clients
- Revenue per client
- Largest client
- Largest client revenue %
- Client concentration
- Client billing trend
- Client outstanding amount

## Record Quality

- Expenses with receipt %
- Uncategorized expenses
- OCR items requiring review
- Missing evidence documents
- Incomplete client records
- Accountant readiness score

---

# 28. Chart Inventory

Recommended chart types:

| Area | Visualization |
|---|---|
| Revenue / expenses / income | Multi-series line chart |
| Actual vs projected revenue | Line chart |
| Revenue deductions → safe to spend | Waterfall |
| Revenue by client | Horizontal bar |
| Client monthly revenue | Bar / line |
| Expense category share | Donut |
| Monthly expenses | Bar / line |
| Invoice aging | Horizontal stacked bar |
| Invoice status | Donut |
| Tax reserve progress | Progress bar |
| GST/HST threshold | Progress bar |
| Accountant readiness | Progress ring/bar |
| Average days to payment | Line |
| Year-over-year revenue | Multi-series line |
| Monthly business momentum | KPI comparison cards |

Avoid using pie/donut charts where more precise comparison is required.

---

# 29. Dashboard Interaction Rules

Every KPI should be actionable where possible.

Examples:

- Revenue → opens invoices filtered to selected period
- Expenses → opens expense ledger
- Outstanding → opens unpaid invoices
- Overdue → opens overdue invoices
- GST/HST collected → opens invoices with tax
- ITCs → opens eligible expenses
- Revenue by client → opens client view
- Missing receipts → opens only missing-receipt expenses
- Threshold tracker → opens detailed calculation
- Tax reserve → opens assumptions and calculation
- Forecast → opens projection settings

The dashboard should never become a dead analytics page.

---

# 30. Visual Design Principles

The visual system should reinforce clarity and trust.

### Principles

- Large typography for money
- Few hero KPIs
- Plenty of whitespace
- No unnecessary accounting jargon
- Plain-language labels
- Consistent positive/negative indicators
- Expandable calculations instead of dense formulas
- Tooltips explaining financial terminology
- Clear separation between:
  - Revenue
  - Collected GST/HST
  - Expenses
  - Income tax
  - CPP
  - Cash available to the proprietor

Avoid presenting everything as a green/red performance metric. A higher GST/HST payable balance, for example, is not necessarily negative performance.

---

# 31. Required Disclaimer Pattern

Tax-related metrics must carry a visible estimate indicator.

Example:

> **Estimated tax + CPP reserve: $21,400**

Supporting tooltip:

> This is an estimate based on the information currently recorded in SolePop and the assumptions shown here. It is not tax advice and may differ from your final tax liability.

The assumptions drawer should show:

- Province of residence
- Revenue
- Deductible expenses
- Tax year
- Applicable tax brackets
- CPP assumptions
- GST/HST status
- Projection methodology

---

# 32. Recommended North-Star Dashboard Experience

Within approximately five seconds of opening SolePop, the user should be able to answer:

> **I have generated $84,000 in revenue, spent $9,200, should reserve approximately $21,400 for income tax and CPP, can safely spend around $53,400, have $12,750 still outstanding, and approximately $5,180 of GST/HST currently set aside for remittance.**

If the dashboard delivers that level of clarity without requiring accounting knowledge, it is doing its job.

