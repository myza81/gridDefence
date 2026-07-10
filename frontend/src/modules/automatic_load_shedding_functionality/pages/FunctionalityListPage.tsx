import { useQuery } from "@tanstack/react-query";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useState } from "react";
import { Link } from "react-router-dom";

import { useReferenceData } from "../../../reference_data/useReferenceData";
import { substationRegistryApi } from "../../substation_registry/api";
import { useAuth } from "../../iam/AuthContext";
import { automaticLoadSheddingFunctionalityApi } from "../api";
import {
  deriveFunctionLabel,
  formatTerminalIdentity,
  functionFilterToParams,
  type FunctionFilterValue,
} from "../displayHelpers";
import type { FunctionalityStatus, FunctionalitySummary, TargetType } from "../types";

const columnHelper = createColumnHelper<FunctionalitySummary>();

/** Registry list page (module document §12) — filters by substation, bay
 * type/terminal type, voltage level, UFLS/UVLS function, and lifecycle
 * status. This page never computes scheme assignment status itself
 * (module document §4, §9 rule 7) — see FunctionalityCandidatePage for the
 * forward-looking candidate/assignment-aware view. */
export function FunctionalityListPage() {
  const { permissions, isLoadingCurrentUser } = useAuth();
  const canWrite = permissions.has("automatic_load_shedding_functionality.write");
  const referenceData = useReferenceData();

  const [page, setPage] = useState(1);
  const [substationId, setSubstationId] = useState("");
  const [targetType, setTargetType] = useState<TargetType | "">("");
  const [voltageLevelId, setVoltageLevelId] = useState("");
  const [functionFilter, setFunctionFilter] = useState<FunctionFilterValue>("");
  const [status, setStatus] = useState<FunctionalityStatus | "">("");
  const pageSize = 20;

  const substationsQuery = useQuery({
    queryKey: ["automatic-load-shedding-functionality", "substation-options"],
    queryFn: () => substationRegistryApi.listSubstations({ page_size: 500 }),
  });

  const listQuery = useQuery({
    queryKey: [
      "automatic-load-shedding-functionality",
      "list",
      { page, substationId, targetType, voltageLevelId, functionFilter, status },
    ],
    queryFn: () =>
      automaticLoadSheddingFunctionalityApi.list({
        page,
        page_size: pageSize,
        substation_id: substationId || undefined,
        target_type: targetType || undefined,
        voltage_level_id: voltageLevelId ? Number(voltageLevelId) : undefined,
        ...functionFilterToParams(functionFilter),
        status_filter: status || undefined,
      }),
  });

  const columns = [
    columnHelper.display({
      id: "terminal_identity",
      header: "Terminal Identity",
      // Full engineering identity, "Substation | Voltage | Bay", so the
      // engineer can identify the exact disconnection point without
      // ambiguity — composed here, never stored (CLAUDE.md A12).
      cell: (info) =>
        formatTerminalIdentity(
          info.row.original.substation_mnemonic,
          info.row.original.voltage_level_label,
          info.row.original.bay_label,
        ),
    }),
    columnHelper.accessor("target_type", {
      header: "Terminal Type",
      cell: (info) => (info.getValue() === "CIRCUIT_TERMINAL" ? "Circuit Terminal" : "Transformer Terminal"),
    }),
    columnHelper.display({
      id: "function",
      header: "Automatic Load Shedding Function",
      cell: (info) =>
        deriveFunctionLabel(info.row.original.ufls_function, info.row.original.uvls_function),
    }),
    columnHelper.accessor("status", { header: "Status" }),
    columnHelper.display({
      id: "actions",
      header: "",
      cell: (info) => (
        <Link to={`/automatic-load-shedding-functionality/${info.row.original.id}`}>View</Link>
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
        <h2>Automatic Load Shedding Functionality Registry</h2>
        {!isLoadingCurrentUser &&
          (canWrite ? (
            <Link
              to="/automatic-load-shedding-functionality/new"
              style={{
                padding: "0.5rem 1rem",
                backgroundColor: "#1a73e8",
                color: "#fff",
                borderRadius: "4px",
                textDecoration: "none",
                fontWeight: 600,
              }}
            >
              Add Functionality Record
            </Link>
          ) : (
            // Explain the gap rather than silently hiding all creation
            // paths (CLAUDE.md A10 — write still requires the permission;
            // this is UI-gating explanation only, never a bypass).
            <p style={{ color: "#555", margin: 0, fontSize: "0.9rem" }}>
              Adding functionality records requires automatic load shedding
              functionality write permission.
            </p>
          ))}
      </div>
      <p>
        Records which bay terminals have installed, wired, configured, commissioned, and
        available automatic load shedding functionality for UFLS and/or UVLS. Not a relay
        asset-management system, and never a record of scheme assignment status.
      </p>

      <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap" }}>
        <select
          aria-label="Filter by substation"
          value={substationId}
          onChange={(e) => {
            setSubstationId(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All substations</option>
          {substationsQuery.data?.items.map((substation) => (
            <option key={substation.substation_id} value={substation.substation_id}>
              {substation.mnemonic}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter by terminal type"
          value={targetType}
          onChange={(e) => {
            setTargetType(e.target.value as TargetType | "");
            setPage(1);
          }}
        >
          <option value="">All terminal (bay) types</option>
          <option value="CIRCUIT_TERMINAL">Circuit Terminal</option>
          <option value="TRANSFORMER_TERMINAL">Transformer Terminal</option>
        </select>
        <select
          aria-label="Filter by voltage level"
          value={voltageLevelId}
          onChange={(e) => {
            setVoltageLevelId(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All voltage levels</option>
          {referenceData.voltageLevels.map((level) => (
            <option key={level.voltage_level_id} value={level.voltage_level_id}>
              {level.label}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter by automatic load shedding function"
          value={functionFilter}
          onChange={(e) => {
            setFunctionFilter(e.target.value as FunctionFilterValue);
            setPage(1);
          }}
        >
          <option value="">Automatic Load Shedding Function: any</option>
          <option value="UFLS">UFLS</option>
          <option value="UVLS">UVLS</option>
          <option value="BOTH">UFLS &amp; UVLS</option>
        </select>
        <select
          aria-label="Filter by status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value as FunctionalityStatus | "");
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          <option value="AVAILABLE">Available</option>
          <option value="ASSIGNED">Assigned</option>
          <option value="DECOMMISSIONED">Decommissioned</option>
        </select>
      </div>

      {listQuery.isLoading && <p>Loading functionality records...</p>}
      {listQuery.isError && <p role="alert">Failed to load functionality records.</p>}

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
                    No functionality records match your filters.
                    {!isLoadingCurrentUser &&
                      (canWrite ? (
                        <>
                          {" "}
                          <Link to="/automatic-load-shedding-functionality/new">
                            Add Functionality Record
                          </Link>
                        </>
                      ) : (
                        <> You do not have permission to add functionality records.</>
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
