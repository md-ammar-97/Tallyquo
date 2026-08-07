"""Notifications module (ADR-002).

Owns: OTP delivery, invoice sending, payment reminders. Transactional email
only — OTP delivery is the one hard dependency in Phase 1; invoice sending
and reminders are Phase 2 (2.12-2.13).
See architecture.md §2 (external dependencies table).
"""
