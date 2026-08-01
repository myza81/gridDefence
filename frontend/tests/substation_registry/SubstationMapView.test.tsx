import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { SubstationMapView } from "../../src/modules/substation_registry/components/SubstationMapView";
import { SubstationListPage } from "../../src/modules/substation_registry/pages/SubstationListPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

// Stub the MapLibre-backed framework (no WebGL in jsdom). The stub renders one
// button per marker (so selection via the map path is exercised), reports
// basemap availability from `mockBasemapOk`, and surfaces the focused id.
let mockBasemapOk = true;
vi.mock("../../src/components/map/EngineeringMap", async () => {
  const React = await import("react");
  return {
    EngineeringMap: ({ layers, onSelect, onBasemapStatus, focusId }: {
      layers: { markers: { id: string; label: string }[] }[];
      onSelect?: (id: string) => void;
      onBasemapStatus?: (ok: boolean) => void;
      focusId?: string | null;
    }) => {
      React.useEffect(() => {
        onBasemapStatus?.(mockBasemapOk);
      }, [onBasemapStatus]);
      return React.createElement(
        "div",
        { "data-testid": "engineering-map-stub" },
        ...layers
          .flatMap((l) => l.markers)
          .map((m) => React.createElement("button", { key: m.id, onClick: () => onSelect?.(m.id) }, `marker:${m.label}`)),
        focusId ? React.createElement("span", { "data-testid": "map-focus" }, focusId) : null,
      );
    },
  };
});

const REFERENCE_DATA_HANDLERS: FetchHandler[] = [
  { method: "GET", pattern: /\/reference-data\/voltage-levels$/, respond: () => ({ body: [{ voltage_level_id: 1, label: "500kV", nominal_kv: 500, sort_order: 1 }] }) },
  { method: "GET", pattern: /\/reference-data\/regions$/, respond: () => ({ body: [{ region_id: 1, code: "SOUTH", label: "Southern" }] }) },
  { method: "GET", pattern: /\/reference-data\/gm-zones$/, respond: () => ({ body: [{ gm_zone_id: 1, code: "MLK", label: "Melaka" }] }) },
  { method: "GET", pattern: /\/reference-data\/states$/, respond: () => ({ body: [{ state_id: 4, code: "MLK", label: "Melaka" }] }) },
  { method: "GET", pattern: /\/reference-data\/grid-owners$/, respond: () => ({ body: [{ grid_owner_id: 1, code: "TNB", label: "Tenaga Nasional Berhad (TNB)" }] }) },
  {
    method: "GET",
    pattern: /\/reference-data\/operational-statuses$/,
    respond: () => ({
      body: [
        { operational_status_id: 2, code: "ACTIVE", label: "Active", is_terminal: false },
        { operational_status_id: 1, code: "UNDER_CONSTRUCTION", label: "Under Construction", is_terminal: false },
        { operational_status_id: 5, code: "DECOMMISSIONED", label: "Decommissioned", is_terminal: false },
        { operational_status_id: 7, code: "ENTERED_IN_ERROR", label: "Entered in Error", is_terminal: true },
      ],
    }),
  },
  { method: "GET", pattern: /\/reference-data\/line-types$/, respond: () => ({ body: [{ line_type_id: 1, code: "OVERHEAD", label: "Overhead Line" }] }) },
];

const FEATURE = (over: Record<string, unknown>) => ({
  substation_id: "id-x",
  mnemonic: "ABBA",
  official_name: "A Famosa",
  operational_status_id: 2,
  region_id: 1,
  gm_zone_id: 1,
  state_id: 4,
  grid_owner_id: 1,
  latitude: 2.43,
  longitude: 102.28,
  coordinate_status: "present",
  ...over,
});

function stubMap(items: Record<string, unknown>[], opts: { status?: number; capture?: (url: string) => void } = {}) {
  const mapped = items.filter((f) => f.coordinate_status === "present").length;
  stubFetch([
    {
      method: "GET",
      pattern: /\/api\/v1\/substations\/map/,
      respond: (url) => {
        opts.capture?.(url);
        if (opts.status && opts.status >= 400) return { status: opts.status, body: { detail: { code: "app_error", message: "Map unavailable." } } };
        return { status: 200, body: { items, mapped_count: mapped, missing_coordinate_count: items.length - mapped, total: items.length } };
      },
    },
    ...REFERENCE_DATA_HANDLERS,
  ]);
}

describe("SubstationMapView", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
    mockBasemapOk = true;
  });

  it("summarises coordinate coverage, lists records, and opens a selected substation", async () => {
    stubMap([
      FEATURE({ substation_id: "id-1", mnemonic: "ABBA", official_name: "A Famosa" }),
      FEATURE({ substation_id: "id-2", mnemonic: "NOCO", official_name: "No Coords", latitude: null, longitude: null, coordinate_status: "missing" }),
    ]);

    renderWithProviders(<SubstationMapView filters={{}} />, { route: "/substations?view=map" });

    // Honest coordinate accounting.
    const summary = await screen.findByTestId("map-coordinate-summary");
    expect(summary).toHaveTextContent("1 mapped · 1 without coordinates");
    // Geographic/electrical boundary copy.
    expect(screen.getByText(/does not represent electrical connectivity/i)).toBeInTheDocument();

    const list = screen.getByRole("list", { name: "Substations" });
    // Record without coordinates is listed and flagged (never silently dropped).
    expect(within(list).getByText("NOCO")).toBeInTheDocument();
    expect(within(list).getByText("NO COORDS")).toBeInTheDocument();

    // Selecting from the accessible list opens a details panel with an Open link.
    const user = userEvent.setup();
    await user.click(within(list).getByText("A Famosa"));
    expect(screen.getByText("Open substation →").closest("a")).toHaveAttribute("href", "/substations/id-1");
    // The selected details panel exposes the canonical coordinate.
    expect(screen.getByText("2.43000, 102.28000")).toBeInTheDocument();
    expect(within(list).getByRole("button", { name: /A Famosa/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("renders lifecycle via the shared mapping and marks entered-in-error distinctly", async () => {
    stubMap([FEATURE({ substation_id: "id-eie", mnemonic: "EIEX", official_name: "Corrected", operational_status_id: 7 })]);

    renderWithProviders(<SubstationMapView filters={{}} />, { route: "/substations?view=map" });

    const list = await screen.findByRole("list", { name: "Substations" });
    // "Entered in Error" label from the shared status mapping (not colour-only).
    expect(within(list).getByText("Entered in Error")).toBeInTheDocument();
  });

  it("selects a substation when its map marker is clicked", async () => {
    stubMap([FEATURE({ substation_id: "id-1", mnemonic: "ABBA", official_name: "A Famosa" })]);

    renderWithProviders(<SubstationMapView filters={{}} />, { route: "/substations?view=map" });

    const user = userEvent.setup();
    await user.click(await screen.findByText("marker:ABBA — A Famosa"));
    expect(screen.getByText("Open substation →").closest("a")).toHaveAttribute("href", "/substations/id-1");
  });

  it("locates and focuses a searched mnemonic that has coordinates", async () => {
    stubMap([FEATURE({ substation_id: "id-1", mnemonic: "ABBA", official_name: "A Famosa" })]);

    renderWithProviders(<SubstationMapView filters={{ search: "ABBA" }} />, { route: "/substations?view=map&q=ABBA" });

    // The sole search hit is auto-selected and the map is asked to focus it.
    expect(await screen.findByText("Open substation →")).toBeInTheDocument();
    expect(screen.getByTestId("map-focus")).toHaveTextContent("id-1");
  });

  it("handles a searched record that has no coordinates honestly", async () => {
    stubMap([FEATURE({ substation_id: "id-1", mnemonic: "ABBA", official_name: "A Famosa", latitude: null, longitude: null, coordinate_status: "missing" })]);

    renderWithProviders(<SubstationMapView filters={{ search: "ABBA" }} />, { route: "/substations?view=map&q=ABBA" });

    expect(await screen.findByRole("status")).toHaveTextContent(/registered but has no coordinates/i);
    // Not focused on the map (no coordinates).
    expect(screen.queryByTestId("map-focus")).toBeNull();
  });

  it("shows a safe state and keeps the list when the basemap is unavailable", async () => {
    mockBasemapOk = false;
    stubMap([FEATURE({ substation_id: "id-1", mnemonic: "ABBA", official_name: "A Famosa" })]);

    renderWithProviders(<SubstationMapView filters={{}} />, { route: "/substations?view=map" });

    expect(await screen.findByText(/the map is unavailable, but every substation remains reachable/i)).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Substations" })).getByText("ABBA")).toBeInTheDocument();
  });

  it("shows a retryable error when the map data fails", async () => {
    stubMap([], { status: 500 });

    renderWithProviders(<SubstationMapView filters={{}} />, { route: "/substations?view=map" });

    expect(await screen.findByText("Couldn't load the substation map")).toBeInTheDocument();
    expect(screen.getByText("Map unavailable.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});

describe("Substation Registry view switch", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
    mockBasemapOk = true;
  });

  function stubList(mapCapture?: (url: string) => void) {
    stubFetch([
      { method: "GET", pattern: /\/api\/v1\/users\/me$/, respond: () => ({ body: { user_id: "u1", username: "e", display_name: "E", email: null, status: "active" } }) },
      { method: "GET", pattern: /\/api\/v1\/users\/u1\/roles$/, respond: () => ({ body: [] }) },
      {
        method: "GET",
        pattern: /\/api\/v1\/substations\/map/,
        respond: (url) => {
          mapCapture?.(url);
          return { status: 200, body: { items: [FEATURE({ substation_id: "id-1" })], mapped_count: 1, missing_coordinate_count: 0, total: 1 } };
        },
      },
      { method: "GET", pattern: /\/api\/v1\/substations\?/, respond: () => ({ body: { items: [{ substation_id: "id-1", mnemonic: "ABBA", official_name: "A Famosa", region_id: 1, gm_zone_id: 1, state_id: 4, grid_owner_id: 1, operational_status_id: 2, psse_bus_number: null }], page: 1, page_size: 20, total: 1 } }) },
      { method: "GET", pattern: /\/api\/v1\/voltage-yards$/, respond: () => ({ body: [] }) },
      ...REFERENCE_DATA_HANDLERS,
    ]);
  }

  it("defaults to the table view and switches to the map, sharing filters", async () => {
    authStorage.setToken("token");
    let mapUrl = "";
    stubList((url) => (mapUrl = url));

    const user = userEvent.setup();
    // Default (no view param) → table.
    renderWithProviders(<SubstationListPage />, { route: "/substations?status=2" });
    expect(await screen.findByRole("columnheader", { name: "Mnemonic" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Table" })).toHaveAttribute("aria-pressed", "true");

    // Switch to Map → the map data request carries the active filter.
    await user.click(screen.getByRole("button", { name: "Map" }));
    await waitFor(() => expect(screen.getByRole("list", { name: "Substations" })).toBeInTheDocument());
    expect(mapUrl).toContain("operational_status_id=2");
    expect(screen.queryByRole("columnheader", { name: "Mnemonic" })).toBeNull();

    // Back to Table remains usable.
    await user.click(screen.getByRole("button", { name: "Table" }));
    expect(await screen.findByRole("columnheader", { name: "Mnemonic" })).toBeInTheDocument();
  });
});
