"""IAM (Identity and Access Management) — Core Platform module.

Owns Users, Roles, Permissions, their assignments, and external identity
mappings, per docs/architecture/iam-module.md and
docs/adr/ADR-002-identity-and-access-management.md. The most foundational
module in GridDefence — every other module depends on it; it depends on
nothing else in the platform (CLAUDE.md A2).
"""
