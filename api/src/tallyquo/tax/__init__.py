"""Tax module (ADR-003).

Owns: the tax engine as a pure, in-process library — `compute(supply_context,
rate_table_snapshot) -> tax_result` with no I/O — plus the `tax_rate` /
`tax_rate_version` reference tables and the human-reviewed rate update
pipeline. Never touches invoice persistence directly; billing calls into
this module, not the other way around. Phase 1 workstreams 1.8-1.11.
See architecture.md §7, edgecases.md §4 (the P1 zone).
"""
