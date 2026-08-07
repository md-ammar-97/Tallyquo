"""Billing module (ADR-002).

Owns: clients, projects, invoices, line items, issuance, numbering, credit
notes, payments, recurring rules. The invoice issuance transaction
(architecture.md §6) lives here and is the highest-blast-radius write path
in the product. Phase 1 workstreams 1.6-1.7, 1.12-1.17; Phase 2 workstreams
2.1-2.7.
"""
