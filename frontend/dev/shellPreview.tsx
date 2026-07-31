/**
 * Authenticated visual-preview harness (Phase D §18, extended in Phase E) —
 * DEV/SCREENSHOT ONLY.
 *
 * Renders the REAL Application Shell V2 and real module pages as a signed-in
 * engineer by seeding a session token and stubbing the backend read/write
 * endpoints the pages call — the same idea as tests/authFixture.tsx, reused for
 * a browser. Production routing (src/app/router.tsx) is never modified to take
 * screenshots. Not referenced by index.html, so `vite build` never bundles it.
 *
 * Usage: npm run dev → http://localhost:5173/shell-preview.html
 *   ?route=/substations                     registry list
 *   ?route=/substations/new                 create form
 *   ?route=/substations/PREVIEW-1           detail workspace
 *   ?route=/substations?state=empty         empty registry
 */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { AppShell } from "../src/components/layout/AppShell";
import { AuthProvider } from "../src/modules/iam/AuthContext";
import { EngineeringHomePage } from "../src/modules/home/pages/EngineeringHomePage";
import { SubstationCreatePage } from "../src/modules/substation_registry/pages/SubstationCreatePage";
import { SubstationDetailPage } from "../src/modules/substation_registry/pages/SubstationDetailPage";
import { SubstationListPage } from "../src/modules/substation_registry/pages/SubstationListPage";
import { resolveBreadcrumbs } from "../src/app/breadcrumbs";
import { authStorage } from "../src/modules/iam/authStorage";
import { tokens } from "../src/theme/tokens";

const PREVIEW_USER = { user_id: "preview-1", username: "sfong", display_name: "Su Fong", email: "su.fong@example.gov", status: "active" };
const PREVIEW_ROLE = {
  role: { role_id: "r1", name: "System Planning Engineer", description: null, is_system_role: true, status: "active" },
  granted_at: "2026-01-01T00:00:00Z",
  permissions: ["substation_registry.write", "equipment_registry.write"],
};

const REF = {
  regions: [
    { region_id: 1, code: "NORTH", label: "Northern" },
    { region_id: 2, code: "CENTRAL", label: "Central" },
    { region_id: 3, code: "SOUTH", label: "Southern" },
  ],
  "gm-zones": [
    { gm_zone_id: 1, code: "KL", label: "Kuala Lumpur" },
    { gm_zone_id: 2, code: "SEL", label: "Shah Alam" },
    { gm_zone_id: 3, code: "PNG", label: "Butterworth" },
  ],
  states: [
    { state_id: 1, code: "SEL", label: "Selangor" },
    { state_id: 2, code: "KUL", label: "Kuala Lumpur" },
    { state_id: 3, code: "PNG", label: "Pulau Pinang" },
  ],
  "grid-owners": [{ grid_owner_id: 1, code: "TNB", label: "Tenaga Nasional Berhad (TNB)" }],
  "operational-statuses": [
    { operational_status_id: 1, code: "UNDER_CONSTRUCTION", label: "Under Construction", is_terminal: false },
    { operational_status_id: 2, code: "ACTIVE", label: "Active", is_terminal: false },
    { operational_status_id: 5, code: "DECOMMISSIONED", label: "Decommissioned", is_terminal: false },
    { operational_status_id: 7, code: "ENTERED_IN_ERROR", label: "Entered in Error", is_terminal: true },
  ],
  "voltage-levels": [
    { voltage_level_id: 1, label: "500kV", nominal_kv: 500, sort_order: 1 },
    { voltage_level_id: 2, label: "275kV", nominal_kv: 275, sort_order: 2 },
    { voltage_level_id: 3, label: "132kV", nominal_kv: 132, sort_order: 3 },
  ],
  "line-types": [{ line_type_id: 1, code: "OVERHEAD", label: "Overhead Line" }],
};

const SUBSTATIONS = [
  { substation_id: "PREVIEW-1", mnemonic: "AMPG", official_name: "Ampang", region_id: 2, gm_zone_id: 1, state_id: 1, grid_owner_id: 1, operational_status_id: 2, psse_bus_number: 4021 },
  { substation_id: "PREVIEW-2", mnemonic: "BTRK", official_name: "Bukit Tarek", region_id: 2, gm_zone_id: 2, state_id: 1, grid_owner_id: 1, operational_status_id: 2, psse_bus_number: 4033 },
  { substation_id: "PREVIEW-3", mnemonic: "KPAR", official_name: "Kapar", region_id: 2, gm_zone_id: 2, state_id: 1, grid_owner_id: 1, operational_status_id: 1, psse_bus_number: null },
  { substation_id: "PREVIEW-4", mnemonic: "PCHG", official_name: "Puchong", region_id: 2, gm_zone_id: 1, state_id: 1, grid_owner_id: 1, operational_status_id: 5, psse_bus_number: 4055 },
  { substation_id: "PREVIEW-5", mnemonic: "SGBS", official_name: "Sungai Besi", region_id: 2, gm_zone_id: 1, state_id: 2, grid_owner_id: 1, operational_status_id: 7, psse_bus_number: null },
  { substation_id: "PREVIEW-6", mnemonic: "PENG", official_name: "Prai Energy", region_id: 3, gm_zone_id: 3, state_id: 3, grid_owner_id: 1, operational_status_id: 2, psse_bus_number: 6011 },
];

const YARDS = [
  { voltage_yard_id: "vy-1", substation_id: "PREVIEW-1", substation_mnemonic: "AMPG", substation_official_name: "Ampang", voltage_level_id: 3, voltage_level_label: "132kV", display_label: "AMPG — 132kV", operational_status_id: 2, commissioning_date: "2004-05-01", latitude: 3.14, longitude: 101.7 },
  { voltage_yard_id: "vy-2", substation_id: "PREVIEW-2", substation_mnemonic: "BTRK", substation_official_name: "Bukit Tarek", voltage_level_id: 2, voltage_level_label: "275kV", display_label: "BTRK — 275kV", operational_status_id: 2, commissioning_date: null, latitude: null, longitude: null },
  { voltage_yard_id: "vy-3", substation_id: "PREVIEW-6", substation_mnemonic: "PENG", substation_official_name: "Prai Energy", voltage_level_id: 1, voltage_level_label: "500kV", display_label: "PENG — 500kV", operational_status_id: 2, commissioning_date: null, latitude: null, longitude: null },
];

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
}

const realFetch = window.fetch.bind(window);
window.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
  const url = typeof input === "string" ? input : input.toString();
  const path = url.replace(/^https?:\/\/[^/]+/, "");
  if (/\/api\/v1\/users\/me$/.test(path)) return Promise.resolve(json(PREVIEW_USER));
  if (/\/api\/v1\/users\/[^/]+\/roles$/.test(path)) return Promise.resolve(json([PREVIEW_ROLE]));
  if (/\/api\/v1\/auth\/logout$/.test(path)) return Promise.resolve(json(null));
  const ref = path.match(/\/api\/v1\/reference-data\/([a-z-]+)/);
  if (ref) return Promise.resolve(json((REF as Record<string, unknown>)[ref[1]] ?? []));
  const detail = path.match(/\/api\/v1\/substations\/([^/?]+)$/);
  if (detail) {
    const found = SUBSTATIONS.find((s) => s.substation_id === detail[1]) ?? SUBSTATIONS[0];
    return Promise.resolve(json({ ...found, latitude: 3.1478, longitude: 101.6953, commissioned_date: "2004-05-01", remarks: "Primary intake for the eastern KL corridor.", created_at: "2004-05-01T00:00:00Z", updated_at: "2026-06-12T09:12:00Z", created_by: PREVIEW_USER, updated_by: PREVIEW_USER }));
  }
  if (/\/aliases$/.test(path)) return Promise.resolve(json([{ alias_id: 1, alias_mnemonic: "AMPANG", alias_name: null, valid_from: "2004-05-01T00:00:00Z", valid_to: "2012-01-01T00:00:00Z" }]));
  if (/\/audit-log/.test(path)) return Promise.resolve(json({ items: [{ log_id: 1, field_name: "official_name", old_value: "Ampang SSU", new_value: "Ampang", changed_at: "2026-06-12T09:12:00Z", changed_by: PREVIEW_USER, change_reason: "Naming standardisation" }], page: 1, page_size: 50, total: 1 }));
  if (/\/api\/v1\/substations\?/.test(path)) {
    const empty = /state=empty/.test(path);
    const items = empty ? [] : SUBSTATIONS;
    return Promise.resolve(json({ items, page: 1, page_size: 20, total: items.length }));
  }
  if (/\/api\/v1\/voltage-yards/.test(path)) return Promise.resolve(json(YARDS));
  if (/\/api\/v1\/transformers\?/.test(path)) {
    const items = /PREVIEW-1/.test(path)
      ? [
          { transformer_id: "txf-1", substation_id: "PREVIEW-1", substation_mnemonic: "AMPG", substation_official_name: "Ampang", transformer_number: "1", generated_short_name: "AMPG-GT1", hv_voltage_level_label: "275kV", lv_voltage_level_label: "132kV", capacity_mva: 240, operational_status_id: 2 },
          { transformer_id: "txf-2", substation_id: "PREVIEW-1", substation_mnemonic: "AMPG", substation_official_name: "Ampang", transformer_number: "2", generated_short_name: "AMPG-GT2", hv_voltage_level_label: "275kV", lv_voltage_level_label: "132kV", capacity_mva: 240, operational_status_id: 2 },
        ]
      : [];
    return Promise.resolve(json({ items, page: 1, page_size: 200, total: items.length }));
  }
  if (/\/api\/v1\/circuits\?/.test(path)) {
    const items = /PREVIEW-1/.test(path)
      ? [
          { circuit_id: "c-1", bay_number: "1", circuit_name: "AMPG–KLNG", voltage_level_id: 2, line_type_id: 1, operational_status_id: 2, is_interconnector: false, terminal_count: 2 },
          { circuit_id: "c-2", bay_number: "2", circuit_name: "AMPG–BTRK", voltage_level_id: 3, line_type_id: 1, operational_status_id: 2, is_interconnector: false, terminal_count: 2 },
        ]
      : [];
    return Promise.resolve(json({ items, page: 1, page_size: 200, total: items.length }));
  }
  return realFetch(input as RequestInfo, init);
}) as typeof window.fetch;

authStorage.setToken("preview-session-token", false);

const params = new URLSearchParams(window.location.search);
const route = params.get("page") === "home" ? "/" : params.get("route") ?? "/";

function PreviewWorkspace({ pathname }: { pathname: string }) {
  const crumbs = resolveBreadcrumbs(pathname);
  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", fontFamily: tokens.typography.fontFamily, color: tokens.color.textPrimary }}>
      <h1 style={{ margin: "0 0 6px", fontSize: "19px" }}>{crumbs[crumbs.length - 1]?.label ?? "Workspace"}</h1>
      <p style={{ color: tokens.color.textSecondary, fontSize: "13px" }}>Preview placeholder for <code>{pathname}</code>.</p>
    </div>
  );
}

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route
              path="*"
              element={
                <AppShell>
                  <Routes>
                    <Route path="/" element={<EngineeringHomePage />} />
                    <Route path="/substations" element={<SubstationListPage />} />
                    <Route path="/substations/new" element={<SubstationCreatePage />} />
                    <Route path="/substations/:substationId" element={<SubstationDetailPage />} />
                    <Route path="*" element={<PreviewWorkspace pathname={route} />} />
                  </Routes>
                </AppShell>
              }
            />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);

window.setTimeout(() => {
  const el = document.documentElement;
  document.title = `sw=${el.scrollWidth} cw=${el.clientWidth} sh=${el.scrollHeight} ch=${el.clientHeight}`;
}, 700);
