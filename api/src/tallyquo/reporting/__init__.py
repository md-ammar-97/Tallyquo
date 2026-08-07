"""Reporting module (ADR-002).

Owns: the ledger view, client roll-ups, projection/set-aside engine, GST
position, small-supplier threshold tracker, year-end export. Reads billing
and expenses data; never mutates it. Phase 1 workstream 1.21; Phase 3
workstreams 3.1-3.12.
See architecture.md §16 (one materialized view is the entire read model).
"""
