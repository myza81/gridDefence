import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { PsseBatchDetailPage } from "../../src/modules/psse_integration/pages/PsseBatchDetailPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "admin",
  display_name: "Administrator",
  email: null,
  status: "active" as const,
};

const BATCH_ID = "33333333-3333-3333-3333-333333333333";
const LOAD_SNAPSHOT_ID = "55555555-5555-5555-5555-555555555555";

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
            name: "Administrator",
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

function batchHandler(overrides: Record<string, unknown> = {}): FetchHandler {
  return {
    method: "GET",
    pattern: new RegExp(`/api/v1/psse-integration/imports/batches/${BATCH_ID}$`),
    respond: () => ({
      status: 200,
      body: {
        batch_id: BATCH_ID,
        source_file_reference: "case1.raw",
        imported_by: CURRENT_USER,
        import_type: "FULL_TOPOLOGY_WITH_LOAD",
        status: "Completed",
        computed_signature: "abc123",
        topology_version_id: "44444444-4444-4444-4444-444444444444",
        load_snapshot_id: LOAD_SNAPSHOT_ID,
        warnings: [],
        fatal_error: null,
        created_at: "2026-07-05T00:00:00Z",
        finding_groups: [],
        matched_count: 2,
        unmatched_count: 0,
        coverage_percent: 100.0,
        ...overrides,
      },
    }),
  };
}

function loadSnapshotHandler(status = "Imported"): FetchHandler {
  return {
    method: "GET",
    pattern: new RegExp(`/api/v1/psse-integration/load-snapshots/${LOAD_SNAPSHOT_ID}$`),
    respond: () => ({
      status: 200,
      body: {
        load_snapshot_id: LOAD_SNAPSHOT_ID,
        topology_version_id: "44444444-4444-4444-4444-444444444444",
        status,
        promoted_at: status === "Current" ? "2026-07-05T01:00:00Z" : null,
        superseded_at: null,
        created_at: "2026-07-05T00:00:00Z",
        load_count: 2,
        generator_count: 0,
      },
    }),
  };
}

function renderBatchDetail() {
  renderWithProviders(
    <Routes>
      <Route path="/psse-integration/batches/:batchId" element={<PsseBatchDetailPage />} />
    </Routes>,
    { route: `/psse-integration/batches/${BATCH_ID}` },
  );
}

describe("PsseBatchDetailPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders the Import Summary using engineering terminology, never a raw status enum", async () => {
    authStorage.setToken("token");
    stubFetch([...SESSION_HANDLERS([]), batchHandler(), loadSnapshotHandler()]);

    renderBatchDetail();

    await waitFor(() => {
      expect(screen.getByText("Import batch: case1.raw")).toBeInTheDocument();
    });
    expect(screen.getByText("Import Completed")).toBeInTheDocument();
    expect(screen.getByText("This snapshot is ready for engineering review.")).toBeInTheDocument();
    expect(screen.getByText("Full Network Topology + Load Snapshot")).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
    // Never the raw enum values.
    expect(screen.queryByText("FULL_TOPOLOGY_WITH_LOAD")).not.toBeInTheDocument();
    expect(screen.queryByText("CompletedWithWarnings", { exact: true })).not.toBeInTheDocument();
  });

  it("shows the Import Health trail reflecting real activation state", async () => {
    authStorage.setToken("token");
    stubFetch([...SESSION_HANDLERS([]), batchHandler(), loadSnapshotHandler("Imported")]);

    renderBatchDetail();

    await waitFor(() => {
      expect(screen.getByText("Import Health")).toBeInTheDocument();
    });
    expect(screen.getByText("Pending Activation")).toBeInTheDocument();
    expect(screen.getByText("Not Yet Performed")).toBeInTheDocument();
    expect(screen.getByText("Not Required")).toBeInTheDocument(); // Engineering Review, no findings
  });

  it("shows Import Health as Activated once the load snapshot is Current", async () => {
    authStorage.setToken("token");
    stubFetch([...SESSION_HANDLERS([]), batchHandler(), loadSnapshotHandler("Current")]);

    renderBatchDetail();

    await waitFor(() => {
      expect(screen.getByText("Current (Activated)")).toBeInTheDocument();
    });
    expect(screen.getByText("Activated")).toBeInTheDocument();
  });

  it("presents Registry Matching using engineering terminology", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS([]),
      batchHandler({ matched_count: 312, unmatched_count: 1087, coverage_percent: 22.31 }),
      loadSnapshotHandler(),
    ]);

    renderBatchDetail();

    await waitFor(() => {
      expect(screen.getByText("Registered Substations Matched")).toBeInTheDocument();
    });
    expect(screen.getByText("312")).toBeInTheDocument();
    expect(screen.getByText("Unmatched Buses")).toBeInTheDocument();
    expect(screen.getByText("1087")).toBeInTheDocument();
    expect(screen.getByText("22.31%")).toBeInTheDocument();
  });

  it("states plainly when no registry matching data is available, rather than a misleading percentage", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS([]),
      batchHandler({ matched_count: null, unmatched_count: null, coverage_percent: null }),
      loadSnapshotHandler(),
    ]);

    renderBatchDetail();

    await waitFor(() => {
      expect(
        screen.getByText("No registry matching data is available for this import."),
      ).toBeInTheDocument();
    });
  });

  it("aggregates many individual findings into one summarized, collapsible group", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS([]),
      batchHandler({
        status: "CompletedWithWarnings",
        matched_count: 312,
        unmatched_count: 1087,
        coverage_percent: 22.31,
        finding_groups: [
          {
            category: "unmatched_bus",
            group: "engineering_review_required",
            count: 1087,
            summary: "1087 buses could not be matched to the current Substation Registry.",
            details: Array.from({ length: 1087 }, (_, i) => `Bus ${100 + i} did not match any substation.`),
          },
          {
            category: "unrecognized_section",
            group: "parser_notices",
            count: 2,
            summary:
              "2 unsupported RAW sections were detected. These sections are currently not " +
              "required by GridDefence and were safely ignored.",
            details: ["Section 'OWNER DATA' is not recognized...", "Section 'SWITCHED SHUNT DATA'..."],
          },
        ],
      }),
      loadSnapshotHandler(),
    ]);

    renderBatchDetail();

    await waitFor(() => {
      expect(screen.getByText("Engineering Review Required")).toBeInTheDocument();
    });
    expect(
      screen.getByText("1087 buses could not be matched to the current Substation Registry."),
    ).toBeInTheDocument();
    // The full 1087-item list is collapsed, not shown directly on the page.
    expect(screen.getByText("Bus 100 did not match any substation.")).not.toBeVisible();
    expect(screen.getByText("Show details (1087)")).toBeInTheDocument();

    expect(screen.getByText("Parser Notices")).toBeInTheDocument();
    expect(screen.getByText(/2 unsupported RAW sections were detected/)).toBeInTheDocument();

    // Expanding reveals the individual detail.
    const user = userEvent.setup();
    await user.click(screen.getByText("Show details (1087)"));
    expect(screen.getByText("Bus 100 did not match any substation.")).toBeInTheDocument();
  });

  it("states plainly that no engineering findings were detected when the import was clean", async () => {
    authStorage.setToken("token");
    stubFetch([...SESSION_HANDLERS([]), batchHandler(), loadSnapshotHandler()]);

    renderBatchDetail();

    await waitFor(() => {
      expect(screen.getByText("No engineering findings detected.")).toBeInTheDocument();
    });
  });

  it("hides the Activate control from a user without psse_integration.activate", async () => {
    authStorage.setToken("token");
    stubFetch([...SESSION_HANDLERS([]), batchHandler(), loadSnapshotHandler()]);

    renderBatchDetail();

    await waitFor(() => {
      expect(screen.getByText("Import batch: case1.raw")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "Activate" })).not.toBeInTheDocument();
  });

  it("activates a batch when submitted by a privileged user", async () => {
    authStorage.setToken("token");
    let activateCalled = false;
    stubFetch([
      ...SESSION_HANDLERS(["psse_integration.activate"]),
      batchHandler(),
      loadSnapshotHandler(),
      {
        method: "POST",
        pattern: new RegExp(`/api/v1/psse-integration/imports/batches/${BATCH_ID}/activate$`),
        respond: () => {
          activateCalled = true;
          return { status: 200, body: batchHandler().respond("").body };
        },
      },
    ]);

    renderBatchDetail();

    const user = userEvent.setup();
    await waitFor(() => {
      expect(screen.getByLabelText("Reason for Activation")).toBeInTheDocument();
    });
    expect(
      screen.getByText("This information will be recorded in the engineering audit log."),
    ).toBeInTheDocument();
    await user.type(screen.getByLabelText("Reason for Activation"), "Go live");
    await user.click(screen.getByRole("button", { name: "Activate" }));

    await waitFor(() => {
      expect(activateCalled).toBe(true);
    });
    expect(screen.getByText("Operational Context successfully activated.")).toBeInTheDocument();
    expect(
      screen.getByText(
        "The imported Network Topology and Load Snapshot are now the Current Operational " +
          "Context used by GridDefence.",
      ),
    ).toBeInTheDocument();
  });

  it("does not offer activation for a batch that failed, and shows no Import Health/Registry Matching for it", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS(["psse_integration.activate"]),
      batchHandler({
        status: "Failed",
        fatal_error: "Zero loads matched.",
        load_snapshot_id: null,
        matched_count: null,
        unmatched_count: null,
        coverage_percent: null,
      }),
    ]);

    renderBatchDetail();

    await waitFor(() => {
      expect(screen.getByText("Import Failed")).toBeInTheDocument();
    });
    expect(screen.getByText("Zero loads matched.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Activate" })).not.toBeInTheDocument();
    expect(screen.queryByText("Import Health")).not.toBeInTheDocument();
    expect(screen.queryByText("Registry Matching")).not.toBeInTheDocument();
  });

  it("keeps the structural signature and topology version link collapsed under Advanced Information", async () => {
    authStorage.setToken("token");
    stubFetch([...SESSION_HANDLERS([]), batchHandler(), loadSnapshotHandler()]);

    renderBatchDetail();

    await waitFor(() => {
      expect(screen.getByText("Advanced Information")).toBeInTheDocument();
    });
    const advancedSummary = screen.getByText("Advanced Information");
    expect(advancedSummary.closest("details")).not.toBeNull();
    const details = advancedSummary.closest("details") as HTMLDetailsElement;
    expect(within(details).getByText("abc123")).toBeInTheDocument();
  });
});
