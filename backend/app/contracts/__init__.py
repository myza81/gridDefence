"""GridDefence-owned contract publication.

GridDefence is the sole authority for the canonical Engineering Data Contract
consumed by external tools (today: the Engineering Data Workbench). Contract
artefacts are *derived deterministically* from GridDefence's own API DTOs
(Pydantic schemas) — never hand-maintained in the consumer — and published under
the repository-root ``contracts/`` directory.

See ``app.contracts.engineering_data.export`` and
``docs/architecture/engineering-data-contract-publication.md``.
"""
