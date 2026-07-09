import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../../src/modules/iam/AuthContext";
import { authStorage } from "../../src/modules/iam/authStorage";
import { PsseImportUploadPage } from "../../src/modules/psse_integration/pages/PsseImportUploadPage";
import { PsseOperationalContextInspectorPage } from "../../src/modules/psse_integration/pages/PsseOperationalContextInspectorPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

function renderWithInspectorRoute(route: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path="/psse-integration/import" element={<PsseImportUploadPage />} />
            <Route
              path="/psse-integration/import/inspect"
              element={<PsseOperationalContextInspectorPage />}
            />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "engineer1",
  display_name: "Engineer One",
  email: null,
  status: "active" as const,
};

const SESSION_HANDLERS = (myPermissions: string[]): FetchHandler[] => [
  {
    method: "GET",
    pattern: /\/api\/v1\/users\/me$/,
    respond: () => ({ status: 200, body: CURRENT_USER }),
  },
  {
    method: "GET",
    pattern: new RegExp(`/api/v1/users/${CURRENT_USER.user_id}/roles$`),
    respond: () => ({
      status: 200,
      body: [
        {
          role: {
            role_id: "22222222-2222-2222-2222-222222222222",
            name: "Engineer",
            description: null,
            is_system_role: true,
            status: "active",
          },
          granted_at: "2026-01-01T00:00:00Z",
          permissions: myPermissions,
        },
      ],
    }),
  },
];

function makeRawFile(): File {
  return new File(["0,100.0,34,0,1,50.0\nQ\n"], "case1.raw", { type: "text/plain" });
}

describe("PsseImportUploadPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("denies access to a user without psse_integration.import", async () => {
    authStorage.setToken("token");
    stubFetch(SESSION_HANDLERS([]));

    renderWithProviders(<PsseImportUploadPage />, { route: "/psse-integration/import" });

    await waitFor(() => {
      expect(
        screen.getByText("You do not have permission to import PSS/E files."),
      ).toBeInTheDocument();
    });
  });

  function previewHandler(body: unknown): FetchHandler {
    return {
      method: "POST",
      pattern: /\/api\/v1\/psse-integration\/imports\/preview$/,
      respond: () => ({ status: 200, body }),
    };
  }

  const FULL_TOPOLOGY_PREVIEW = {
    import_type: "FULL_TOPOLOGY_WITH_LOAD",
    raw_version: 34,
    bus_count: 2,
    branch_count: 1,
    transformer_count: 0,
    load_count: 0,
    generator_count: 0,
    computed_signature: "abc123",
    topology_reused: false,
    matched_bus_count: 2,
    unmatched_bus_count: 0,
    coverage_percent: 100.0,
    warnings: [],
    // Operational Context Inspector fields (§8.9e) — the same parsed
    // records Preview already computed.
    source_file_reference: "case1.raw",
    base_mva: 100.0,
    buses: [],
    branches: [],
    transformers: [],
    loads: [],
    generators: [],
    // RAW File Information (Phase 7 discovery-support enhancement).
    frequency_hz: 50.0,
    case_description: "CPF_03 JAN 2025",
    raw_created: "WED, FEB 11 2026 14:43",
  };

  const COMMIT_BATCH_RESULT = {
    batch_id: "33333333-3333-3333-3333-333333333333",
    source_file_reference: "case1.raw",
    import_type: "FULL_TOPOLOGY_WITH_LOAD",
    status: "Completed",
    computed_signature: "abc123",
    topology_version_id: "44444444-4444-4444-4444-444444444444",
    load_snapshot_id: "55555555-5555-5555-5555-555555555555",
    warnings: [],
    fatal_error: null,
  };

  it("previews then commits a selected file, using engineering terminology throughout (Direct execution mode)", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS(["psse_integration.import"]),
      // Preview executes synchronously (§8.9a) — a direct 200 with the
      // PreviewResult body, never a job to poll.
      previewHandler(FULL_TOPOLOGY_PREVIEW),
      // Direct execution mode (the backend's default, §8.9c) — Commit
      // also completes immediately, with a 200 and the batch result body,
      // never a job id.
      {
        method: "POST",
        pattern: /\/api\/v1\/psse-integration\/imports\/commit$/,
        respond: () => ({ status: 200, body: COMMIT_BATCH_RESULT }),
      },
    ]);

    renderWithProviders(<PsseImportUploadPage />, { route: "/psse-integration/import" });

    const user = userEvent.setup();
    const fileInput = await screen.findByLabelText("RAW file");
    await user.upload(fileInput, makeRawFile());

    await user.click(screen.getByRole("button", { name: "Preview" }));

    await waitFor(() => {
      expect(screen.getByText("Full Network Topology + Load Snapshot")).toBeInTheDocument();
    });
    // Never raw enum values.
    expect(screen.queryByText("FULL_TOPOLOGY_WITH_LOAD")).not.toBeInTheDocument();
    expect(screen.getByText("Introduces a new network topology")).toBeInTheDocument();
    expect(screen.getByText("Registered Substations Matched")).toBeInTheDocument();
    expect(screen.getByText("No engineering findings detected.")).toBeInTheDocument();
    expect(
      screen.getByText("Preview completed successfully — this snapshot appears ready for import."),
    ).toBeInTheDocument();
    // Network size, read from the already-parsed case.
    expect(screen.getByText("Transmission Lines (Branches)")).toBeInTheDocument();
    // Implementation detail is collapsed, not primary.
    expect(screen.getByText("Advanced Information").closest("summary")).not.toBeNull();

    await user.click(screen.getByRole("button", { name: "Commit" }));

    // No "Committing import..." polling message should linger once the
    // (already-complete) result has rendered.
    await waitFor(() => {
      expect(screen.getByText("Import committed")).toBeInTheDocument();
    });
    expect(screen.queryByText("Committing import...")).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "review and activate this batch" }),
    ).toHaveAttribute("href", "/psse-integration/batches/33333333-3333-3333-3333-333333333333");
  });

  it("displays RAW File Information before the object counts (Phase 7 discovery-support enhancement)", async () => {
    authStorage.setToken("token");
    stubFetch([...SESSION_HANDLERS(["psse_integration.import"]), previewHandler(FULL_TOPOLOGY_PREVIEW)]);

    renderWithProviders(<PsseImportUploadPage />, { route: "/psse-integration/import" });

    const user = userEvent.setup();
    const fileInput = await screen.findByLabelText("RAW file");
    await user.upload(fileInput, makeRawFile());
    await user.click(screen.getByRole("button", { name: "Preview" }));

    await waitFor(() => {
      expect(screen.getByText("RAW File Information")).toBeInTheDocument();
    });
    expect(screen.getByText("PSS®E Version")).toBeInTheDocument();
    expect(screen.getByText("Base MVA")).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
    expect(screen.getByText("Frequency")).toBeInTheDocument();
    expect(screen.getByText("50 Hz")).toBeInTheDocument();
    expect(screen.getByText("Study Case")).toBeInTheDocument();
    expect(screen.getByText("CPF_03 JAN 2025")).toBeInTheDocument();
    expect(screen.getByText("RAW Created")).toBeInTheDocument();
    expect(screen.getByText("WED, FEB 11 2026 14:43")).toBeInTheDocument();

    // Must appear before the object counts (Buses, Branches, etc.).
    const infoHeading = screen.getByText("RAW File Information");
    const networkSizeHeading = screen.getByText("Network Size");
    expect(
      infoHeading.compareDocumentPosition(networkSizeHeading) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("commits via Queue execution mode, polling a job to completion", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS(["psse_integration.import"]),
      previewHandler(FULL_TOPOLOGY_PREVIEW),
      // Queue execution mode (§8.9c) — Commit returns 202 + a job id,
      // unchanged from before the Execution Engine refactor.
      {
        method: "POST",
        pattern: /\/api\/v1\/psse-integration\/imports\/commit$/,
        respond: () => ({ status: 202, body: { job_id: "commit-job-1" } }),
      },
      {
        method: "GET",
        pattern: /\/api\/v1\/psse-integration\/imports\/jobs\/commit-job-1$/,
        respond: () => ({
          status: 200,
          body: { job_id: "commit-job-1", status: "finished", result: COMMIT_BATCH_RESULT, error: null },
        }),
      },
    ]);

    renderWithProviders(<PsseImportUploadPage />, { route: "/psse-integration/import" });

    const user = userEvent.setup();
    const fileInput = await screen.findByLabelText("RAW file");
    await user.upload(fileInput, makeRawFile());
    await user.click(screen.getByRole("button", { name: "Preview" }));
    await screen.findByText("Full Network Topology + Load Snapshot");

    await user.click(screen.getByRole("button", { name: "Commit" }));

    await waitFor(() => {
      expect(screen.getByText("Import committed")).toBeInTheDocument();
    });
    expect(
      screen.getByRole("link", { name: "review and activate this batch" }),
    ).toHaveAttribute("href", "/psse-integration/batches/33333333-3333-3333-3333-333333333333");
  });

  it("labels Registry Matching for a load-only snapshot differently from a full topology snapshot", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS(["psse_integration.import"]),
      previewHandler({
        import_type: "LOAD_ONLY",
        raw_version: null,
        bus_count: 0,
        branch_count: 0,
        transformer_count: 0,
        load_count: 2,
        generator_count: 0,
        computed_signature: null,
        topology_reused: false,
        matched_bus_count: 2,
        unmatched_bus_count: 0,
        coverage_percent: 100.0,
        warnings: [],
        // A load-only file's header is frequently absent entirely (§8.7) —
        // every RAW File Information field is gracefully null.
        base_mva: null,
        frequency_hz: null,
        case_description: null,
        raw_created: null,
      }),
    ]);

    renderWithProviders(<PsseImportUploadPage />, { route: "/psse-integration/import" });

    const user = userEvent.setup();
    const fileInput = await screen.findByLabelText("RAW file");
    await user.upload(fileInput, makeRawFile());
    await user.click(screen.getByRole("button", { name: "Preview" }));

    await waitFor(() => {
      expect(screen.getByText("Load Snapshot Only")).toBeInTheDocument();
    });
    expect(
      screen.getByText("References the currently registered network topology"),
    ).toBeInTheDocument();
    expect(screen.getByText("Load Buses Matched Against Current Topology")).toBeInTheDocument();
    expect(screen.getByText("Unmatched Load Buses")).toBeInTheDocument();
    expect(screen.queryByText("Registered Substations Matched")).not.toBeInTheDocument();
    // PSS/E Version, Base MVA, Frequency, Study Case, RAW Created — all
    // gracefully "Not available" when the RAW file has no header at all.
    expect(screen.getAllByText("Not available")).toHaveLength(5);
  });

  it("displays the Load Synchronisation summary and bus identity mismatches (Phase 7B)", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS(["psse_integration.import"]),
      previewHandler({
        import_type: "LOAD_ONLY",
        raw_version: null,
        bus_count: 0,
        branch_count: 0,
        transformer_count: 0,
        load_count: 2,
        generator_count: 0,
        computed_signature: null,
        topology_reused: false,
        matched_bus_count: 2,
        unmatched_bus_count: 0,
        coverage_percent: 100.0,
        warnings: [],
        base_mva: null,
        frequency_hz: null,
        case_description: null,
        raw_created: null,
        sync_validation: {
          total_load_records: 2,
          total_distinct_load_buses: 2,
          matched_load_buses: 2,
          unmatched_load_buses: 0,
          missing_topology_buses: 1,
          identity_mismatch_buses: 1,
          unmatched_load_bus_numbers: [],
          missing_topology_bus_numbers: [200],
          identity_mismatches: [
            {
              bus_number: 100,
              active_bus_name: "PKLG132",
              incoming_bus_name: "RENAMED_BUS",
              active_base_kv: 132.0,
              incoming_base_kv: 132.0,
              mismatch_reason: "bus_name",
            },
          ],
        },
      }),
    ]);

    renderWithProviders(<PsseImportUploadPage />, { route: "/psse-integration/import" });

    const user = userEvent.setup();
    const fileInput = await screen.findByLabelText("RAW file");
    await user.upload(fileInput, makeRawFile());
    await user.click(screen.getByRole("button", { name: "Preview" }));

    await waitFor(() => {
      expect(screen.getByText("Load Synchronisation")).toBeInTheDocument();
    });
    expect(screen.getByText("Missing From Current Topology")).toBeInTheDocument();
    expect(screen.getAllByText("Bus Identity Mismatches").length).toBeGreaterThan(0);
    expect(screen.getByText(/Bus 100: current topology reports/)).toBeInTheDocument();
    expect(screen.getByText(/"PKLG132" at 132 kV/)).toBeInTheDocument();
    expect(screen.getByText(/"RENAMED_BUS" at 132 kV/)).toBeInTheDocument();
  });

  it("does not show a Load Synchronisation section for a full topology import", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS(["psse_integration.import"]),
      previewHandler({ ...FULL_TOPOLOGY_PREVIEW, sync_validation: null }),
    ]);

    renderWithProviders(<PsseImportUploadPage />, { route: "/psse-integration/import" });

    const user = userEvent.setup();
    const fileInput = await screen.findByLabelText("RAW file");
    await user.upload(fileInput, makeRawFile());
    await user.click(screen.getByRole("button", { name: "Preview" }));

    await waitFor(() => {
      expect(screen.getByText("Full Network Topology + Load Snapshot")).toBeInTheDocument();
    });
    expect(screen.queryByText("Load Synchronisation")).not.toBeInTheDocument();
  });

  it("shows a plain explanation, not a coverage number, when no current network topology exists yet", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS(["psse_integration.import"]),
      previewHandler({
        import_type: "LOAD_ONLY",
        raw_version: null,
        bus_count: 0,
        branch_count: 0,
        transformer_count: 0,
        load_count: 2,
        generator_count: 0,
        computed_signature: null,
        topology_reused: false,
        matched_bus_count: 0,
        unmatched_bus_count: 2,
        coverage_percent: 0,
        warnings: ["No Current TopologyVersion exists to validate load buses against."],
      }),
    ]);

    renderWithProviders(<PsseImportUploadPage />, { route: "/psse-integration/import" });

    const user = userEvent.setup();
    const fileInput = await screen.findByLabelText("RAW file");
    await user.upload(fileInput, makeRawFile());
    await user.click(screen.getByRole("button", { name: "Preview" }));

    await waitFor(() => {
      expect(
        screen.getByText("No current network topology exists yet — load buses could not be validated."),
      ).toBeInTheDocument();
    });
    expect(screen.queryByText("Load Match Coverage")).not.toBeInTheDocument();
  });

  it("separates findings requiring attention from purely informational notices", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS(["psse_integration.import"]),
      previewHandler({
        ...FULL_TOPOLOGY_PREVIEW,
        unmatched_bus_count: 1,
        matched_bus_count: 1,
        coverage_percent: 50,
        warnings: [
          "Could not parse LOAD DATA line: 'garbled'",
          "Section 'OWNER DATA' is not recognized by this parser — its data (if any) was skipped.",
        ],
      }),
    ]);

    renderWithProviders(<PsseImportUploadPage />, { route: "/psse-integration/import" });

    const user = userEvent.setup();
    const fileInput = await screen.findByLabelText("RAW file");
    await user.upload(fileInput, makeRawFile());
    await user.click(screen.getByRole("button", { name: "Preview" }));

    await waitFor(() => {
      expect(screen.getByText("Requires Attention")).toBeInTheDocument();
    });
    const attentionHeading = screen.getByText("Requires Attention");
    expect(attentionHeading.nextElementSibling).toHaveTextContent("Could not parse LOAD DATA line");

    expect(screen.getByText("Informational")).toBeInTheDocument();
    const informationalHeading = screen.getByText("Informational");
    expect(informationalHeading.nextElementSibling).toHaveTextContent("OWNER DATA");

    expect(screen.getByText("Review the findings above before importing.")).toBeInTheDocument();
  });

  it("surfaces a preview validation failure directly, with no job to poll", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS(["psse_integration.import"]),
      {
        method: "POST",
        pattern: /\/api\/v1\/psse-integration\/imports\/preview$/,
        respond: () => ({
          status: 400,
          body: { detail: { code: "validation_error", message: "The uploaded file is empty." } },
        }),
      },
    ]);

    renderWithProviders(<PsseImportUploadPage />, { route: "/psse-integration/import" });

    const user = userEvent.setup();
    const fileInput = await screen.findByLabelText("RAW file");
    await user.upload(fileInput, makeRawFile());
    await user.click(screen.getByRole("button", { name: "Preview" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("The uploaded file is empty.");
    });
  });

  it("navigates to the Operational Context Inspector with the already-fetched preview data, no second request", async () => {
    authStorage.setToken("token");
    stubFetch([...SESSION_HANDLERS(["psse_integration.import"]), previewHandler(FULL_TOPOLOGY_PREVIEW)]);

    renderWithInspectorRoute("/psse-integration/import");

    const user = userEvent.setup();
    const fileInput = await screen.findByLabelText("RAW file");
    await user.upload(fileInput, makeRawFile());
    await user.click(screen.getByRole("button", { name: "Preview" }));

    await screen.findByRole("button", { name: "Inspect Imported Data" });
    await user.click(screen.getByRole("button", { name: "Inspect Imported Data" }));

    await waitFor(() => {
      expect(screen.getByText("Operational Context Inspector")).toBeInTheDocument();
    });
    // Same import type carried straight from the Preview response — no
    // second network call was needed (only one preview stub was registered
    // above, and stubFetch throws on any unregistered call).
    expect(screen.getByText("Full Network Topology + Load Snapshot")).toBeInTheDocument();
  });

  it("disables the Preview button until a file is selected", async () => {
    authStorage.setToken("token");
    stubFetch(SESSION_HANDLERS(["psse_integration.import"]));

    renderWithProviders(<PsseImportUploadPage />, { route: "/psse-integration/import" });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Preview" })).toBeDisabled();
    });
  });
});
