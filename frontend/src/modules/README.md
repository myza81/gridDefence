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

## substation_registry (Phase 2)

Substation list (TanStack Table), detail/edit, create, status-change, alias
history, and audit log views — `docs/architecture/substation-registry.md`
§13. Status-change and field validation (mnemonic/name uniqueness,
geolocation pairing, transition legality) are enforced only by the backend;
the frontend submits requests and surfaces the backend's error messages
verbatim, never re-implementing the rules itself (CLAUDE.md A12).

## reference_data (not a module — shared Core Platform lookup data)

`useReferenceData()` fetches the five Core Platform reference tables
(voltage_level, region, state, grid_owner, operational_status) once and
exposes both option lists (for `<select>`s) and id -> row maps (for display
lookups). Lives alongside `modules/`, not inside any one module's folder,
because every future module's forms will need the same lookups —
mirroring `backend/app/reference_data/`'s own non-module placement.
