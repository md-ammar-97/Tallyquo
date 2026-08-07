"""Templates module (ADR-002).

Owns: structured invoice templates (`{theme, blocks, locked_compliance_block}`)
and the deterministic PDF rendering pipeline (ADR-004). No user-authored
HTML/CSS/JS is ever accepted here — there is no injection surface because
there is no HTML input. Phase 1 workstreams 1.18-1.20.
See architecture.md §8, design.md §9.
"""
