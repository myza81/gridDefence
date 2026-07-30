"""Engineering Data Contract (v0.x) — narrow, versioned canonical boundary.

The first contract version is deliberately narrow: it covers only the Substation
and Transformer shapes the Engineering Data Workbench currently produces or
previews, plus the shared validation-error representation. Circuit, Circuit
Terminal, Line Connectivity, Relay/ALSF, Sensitive Customer, and scheme objects
are intentionally excluded until a current workflow requires them.

The generator lives in ``app.contracts.engineering_data.export`` (kept as a
submodule so ``python -m app.contracts.engineering_data.export`` runs cleanly
without an eager package-level import).
"""
