"""Substation Registry — the platform's master data anchor.

Owns Substation identity and static/slowly-changing engineering attributes
(docs/architecture/substation-registry.md). Every other module references a
substation by `substation_id` (FK) — never by copying its attributes
(CLAUDE.md §5.1, §8).
"""
