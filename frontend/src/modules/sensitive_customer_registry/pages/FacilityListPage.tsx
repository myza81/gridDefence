import { useQuery } from "@tanstack/react-query";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../../iam/AuthContext";
import { sensitiveCustomerRegistryApi } from "../api";
import { describeTerminalResolution, formatTerminalIdentity } from "../displayHelpers";
import type { SensitiveFacilityTerminalAssociation } from "../types";
import type {
  LifecycleStatus,
  SensitiveFacilitySummary,
  TransformerTerminalResolution,
} from "../types";

const columnHelper = createColumnHelper<SensitiveFacilitySummary>();

/** Registry list page (implementation spec §14, Increment 7/11). Shows
 * engineering facts only — name, sector, sensitivity, associated
 * substation/transformer/terminal, lifecycle, last-modified. No defence-
 * scheme controls, no scheme-assignment buttons, no compliance/blocking
 * indicator of any kind (task's explicit non-goal). Includes a lightweight
 * in-module summary strip (Increment 11) — this module's own read of its
 * own data, not the future cross-module Dashboard. */
export function FacilityListPage() {
  const { permissions, isLoadingCurrentUser } = useAuth();
  // Corrected permission model (Correction 1): facility mutation is
  // Administrator-only via `.write`; Engineer holds `.read` only.
  const canWrite = permissions.has("sensitive_customer_registry.write");

  const [page, setPage] = useState(1);
  const [sectorId, setSectorId] = useState("");
  const [classificationId, setClassificationId] = useState("");
  const [lifecycleStatus, setLifecycleStatus] = useState<LifecycleStatus | "">("");
  const [terminalResolution, setTerminalResolution] = useState<
    TransformerTerminalResolution | ""
  >("");
  const pageSize = 20;

  const sectorsQuery = useQuery({
    queryKey: ["sensitive-customer-registry", "facility-sectors"],
    queryFn: sensitiveCustomerRegistryApi.listFacilitySectors,
  });
  const classificationsQuery = useQuery({
    queryKey: ["sensitive-customer-registry", "sensitivity-classifications"],
    queryFn: sensitiveCustomerRegistryApi.listSensitivityClassifications,
  });
  const summaryQuery = useQuery({
    queryKey: ["sensitive-customer-registry", "summary"],
    queryFn: sensitiveCustomerRegistryApi.getSummary,
  });

  const listQuery = useQuery({
    queryKey: [
      "sensitive-customer-registry",
      "facilities",
      "list",
      { page, sectorId, classificationId, lifecycleStatus, terminalResolution },
    ],
    queryFn: () =>
      sensitiveCustomerRegistryApi.listFacilities({
        page,
        page_size: pageSize,
        facility_sector_id: sectorId ? Number(sectorId) : undefined,
        sensitivity_classification_id: classificationId ? Number(classificationId) : undefined,
        lifecycle_status: lifecycleStatus || undefined,
        transformer_terminal_resolution: terminalResolution || undefined,
      }),
  });

  const columns = [
    columnHelper.accessor("name", { header: "Facility Name" }),
    columnHelper.display({
      id: "sector",
      header: "Sector",
      cell: (info) => info.row.original.facility_sector.label,
    }),
    columnHelper.display({
      id: "sensitivity",
      header: "Sensitivity",
      cell: (info) => info.row.original.sensitivity_classification.label,
    }),
    columnHelper.display({
      id: "terminal_identity",
      header: "Supply Point(s)",
      // Correction 4, generalised by ADR-013 — a facility is never
      // omitted for an unresolved terminal; every currently associated
      // terminal is listed, with its own resolved identity or an
      // explanation of why it could not be resolved.
      cell: (info) => {
        const associations = info.row.original.transformer_terminals;
        if (associations.length === 0) {
          return describeTerminalResolution(info.row.original.transformer_terminal_resolution);
        }
        return (
          <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
            {associations.map((association: SensitiveFacilityTerminalAssociation) => {
              const identity = formatTerminalIdentity(
                association.substation_mnemonic,
                association.voltage_level_label,
                association.bay_label,
                association.side,
              );
              return (
                <li key={association.transformer_terminal_id}>
                  {identity ?? "Terminal could not be resolved"}
                </li>
              );
            })}
          </ul>
        );
      },
    }),
    columnHelper.accessor("lifecycle_status", { header: "Lifecycle" }),
    columnHelper.display({
      id: "actions",
      header: "",
      cell: (info) => (
        <Link to={`/sensitive-customer-registry/${info.row.original.id}`}>View</Link>
      ),
    }),
  ];

  const table = useReactTable({
    data: listQuery.data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <section>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1rem",
        }}
      >
        <h2>Sensitive Customer Registry</h2>
        {!isLoadingCurrentUser &&
          (canWrite ? (
            <Link
              to="/sensitive-customer-registry/new"
              style={{
                padding: "0.5rem 1rem",
                backgroundColor: "#1a73e8",
                color: "#fff",
                borderRadius: "4px",
                textDecoration: "none",
                fontWeight: 600,
              }}
            >
              Add Sensitive Facility
            </Link>
          ) : (
            // UI-gating explanation only, never a bypass — the backend
            // still re-checks `sensitive_customer_registry.write` on every
            // request (CLAUDE.md A10).
            <p style={{ color: "#555", margin: 0, fontSize: "0.9rem" }}>
              Adding sensitive facility records requires administrator privileges.
            </p>
          ))}
      </div>
      <p>
        Records which physical facilities require special engineering consideration if their
        Transformer Terminal supply point is interrupted, and their engineering sector and
        sensitivity classification. Not a customer-relationship-management system, and never a
        record of any defence-scheme decision.
      </p>

      {summaryQuery.data && (
        <div
          style={{
            display: "flex",
            gap: "1.5rem",
            marginBottom: "1rem",
            padding: "0.75rem 1rem",
            backgroundColor: "#f5f5f5",
            borderRadius: "4px",
          }}
        >
          <span>Active: {summaryQuery.data.active_count}</span>
          <span>Archived: {summaryQuery.data.archived_count}</span>
          <span>Entered in Error: {summaryQuery.data.entered_in_error_count}</span>
          <span>Unresolved terminal: {summaryQuery.data.unresolved_terminal_count}</span>
        </div>
      )}

      <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap" }}>
        <select
          aria-label="Filter by sector"
          value={sectorId}
          onChange={(e) => {
            setSectorId(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All sectors</option>
          {sectorsQuery.data?.map((sector) => (
            <option key={sector.id} value={sector.id}>
              {sector.label}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter by sensitivity classification"
          value={classificationId}
          onChange={(e) => {
            setClassificationId(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All sensitivity classifications</option>
          {classificationsQuery.data?.map((classification) => (
            <option key={classification.id} value={classification.id}>
              {classification.label}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter by lifecycle status"
          value={lifecycleStatus}
          onChange={(e) => {
            setLifecycleStatus(e.target.value as LifecycleStatus | "");
            setPage(1);
          }}
        >
          <option value="">All lifecycle statuses</option>
          <option value="ACTIVE">Active</option>
          <option value="ARCHIVED">Archived</option>
          <option value="ENTERED_IN_ERROR">Entered in Error</option>
        </select>
        <select
          aria-label="Filter by terminal resolution"
          value={terminalResolution}
          onChange={(e) => {
            setTerminalResolution(e.target.value as TransformerTerminalResolution | "");
            setPage(1);
          }}
        >
          <option value="">All supply-point states</option>
          <option value="RESOLVED">Resolved</option>
          <option value="NOT_ASSIGNED">No supply point recorded</option>
          <option value="UNRESOLVED">Terminal could not be resolved</option>
        </select>
      </div>

      {listQuery.isLoading && <p>Loading sensitive facility records...</p>}
      {listQuery.isError && <p role="alert">Failed to load sensitive facility records.</p>}

      {listQuery.data && (
        <>
          <table>
            <thead>
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th key={header.id}>
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
                  ))}
                </tr>
              ))}
              {table.getRowModel().rows.length === 0 && (
                <tr>
                  <td colSpan={columns.length}>
                    No sensitive facility records match your filters.
                    {!isLoadingCurrentUser &&
                      (canWrite ? (
                        <>
                          {" "}
                          <Link to="/sensitive-customer-registry/new">Add Sensitive Facility</Link>
                        </>
                      ) : (
                        <> You do not have permission to add sensitive facility records.</>
                      ))}
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          <div style={{ marginTop: "1rem", display: "flex", gap: "0.75rem", alignItems: "center" }}>
            <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            <span>
              Page {page} of {Math.max(1, Math.ceil(listQuery.data.total / pageSize))}
            </span>
            <button
              type="button"
              disabled={page * pageSize >= listQuery.data.total}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </section>
  );
}
