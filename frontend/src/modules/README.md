# Business Modules

Each GridDefence backend module gets a matching frontend feature folder here
once its implementation phase begins (iam, substation_registry,
equipment_registry, psse_integration, network_model, ufls, uvls, emls,
critical_infrastructure, cross_scheme_compliance, dashboard) — see
`docs/architecture/implementation-plan.md` §3.

## iam (Phase 1)

Local username/password authentication, current-user display, role
management, permission catalog management, and user-role assignment —
`docs/architecture/iam-module.md` §12. All authorization decisions are
re-checked by the backend on every request (CLAUDE.md A12, A10); the
`permissions` set exposed by `AuthContext` only gates which UI controls are
shown, it is never itself the authority.
