"""Core Platform shared reference data.

Owned by no single business module — every module references these lookup
tables read-only (voltage_level, region, state, grid_owner,
operational_status), per docs/architecture/substation-registry.md §6 and
docs/architecture/domain-model.md §2 (Core Platform domain).
"""
