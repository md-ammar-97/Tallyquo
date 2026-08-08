// `new Date().toISOString().slice(0, 10)` is a classic trap: toISOString
// always converts to UTC, so anywhere behind UTC (all of Canada) it
// silently returns tomorrow's date in the evening. Every "default to
// today" field must use the browser's *local* calendar date instead --
// invoice_date, expense_date, and payment received_date all drive real
// tax/ITC-eligibility computations keyed to a specific calendar day.
export function todayLocal(): string {
  const d = new Date()
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}
