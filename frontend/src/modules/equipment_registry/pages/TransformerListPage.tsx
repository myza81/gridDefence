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
import { useReferenceData } from "../../../reference_data/useReferenceData";
import { equipmentRegistryApi } from "../api";
import type { TransformerSummary } from "../types";

const columnHelper = createColumnHelper<TransformerSummary>();

export function TransformerListPage() {
  const { permissions } = useAuth();
  const canWrite = permissions.has("equipment_registry.write");
  const referenceData = useReferenceData();

  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusId, setStatusId] = useState<string>("");
  // Deletion/correction policy (Phase 3 follow-up): Entered-in-Error
  // transformers are hidden by default; this is the audit-facing toggle
  // to reveal them, mirroring the equivalent toggle on Circuit's own list
  // page and the Substation Detail page's Switchyards section.
  const [showEnteredInError, setShowEnteredInError] = useState(false);
  const pageSize = 20;

  const transformersQuery = useQuery({
    queryKey: ["transformers", { page, search, statusId, showEnteredInError }],
    queryFn: () =>
      equipmentRegistryApi.listTransformers({
        page,
        page_size: pageSize,
        search: search || undefined,
        operational_status_id: statusId ? Number(statusId) : undefined,
        include_entered_in_error: showEnteredInError,
      }),
  });

  const columns = [
    columnHelper.accessor("substation_mnemonic", {
      header: "Substation",
      cell: (info) =>
        `${info.getValue()} — ${info.row.original.substation_official_name}`,
    }),
    columnHelper.accessor("generated_short_name", { header: "Short Name" }),
    columnHelper.display({
      id: "voltage_transformation",
      header: "Voltage Transformation",
      cell: (info) =>
        `${info.row.original.hv_voltage_level_label} ↔ ${info.row.original.lv_voltage_level_label}`,
    }),
    columnHelper.accessor("capacity_mva", {
      header: "Capacity (MVA)",
      cell: (info) => info.getValue() ?? "—",
    }),
    columnHelper.accessor("operational_status_id", {
      header: "Status",
      cell: (info) =>
        referenceData.operationalStatusesById.get(info.getValue())?.label ?? info.getValue(),
    }),
    columnHelper.display({
      id: "actions",
      header: "",
      cell: (info) => <Link to={`/transformers/${info.row.original.transformer_id}`}>View</Link>,
    }),
  ];

  const table = useReactTable({
    data: transformersQuery.data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const isFiltered = Boolean(search || statusId);
  const hasNoTransformersAtAll = transformersQuery.data?.total === 0 && !isFiltered;

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
        <h2>Transformers</h2>
        {canWrite && (
          <Link
            to="/transformers/new"
            style={{
              padding: "0.5rem 1rem",
              backgroundColor: "#1a73e8",
              color: "#fff",
              borderRadius: "4px",
              textDecoration: "none",
              fontWeight: 600,
            }}
          >
            New Transformer
          </Link>
        )}
      </div>

      <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap" }}>
        <input
          aria-label="Search transformers"
          placeholder="Search transformer number or substation..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
        />
        <select
          aria-label="Filter by status"
          value={statusId}
          onChange={(e) => {
            setStatusId(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          {referenceData.operationalStatuses.map((status) => (
            <option key={status.operational_status_id} value={status.operational_status_id}>
              {status.label}
            </option>
          ))}
        </select>
        <label htmlFor="show-entered-in-error-transformers">
          <input
            id="show-entered-in-error-transformers"
            type="checkbox"
            checked={showEnteredInError}
            onChange={(e) => {
              setShowEnteredInError(e.target.checked);
              setPage(1);
            }}
          />{" "}
          Show entered-in-error transformers
        </label>
      </div>

      {transformersQuery.isLoading && <p>Loading transformers...</p>}
      {transformersQuery.isError && <p role="alert">Failed to load transformers.</p>}

      {transformersQuery.data && (
        <>
          {hasNoTransformersAtAll ? (
            <div style={{ padding: "2rem", textAlign: "center", border: "1px dashed #ccc" }}>
              <p>No transformers have been registered yet.</p>
              {canWrite && <Link to="/transformers/new">Register your first transformer</Link>}
            </div>
          ) : (
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
                      <td key={cell.id}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
                {table.getRowModel().rows.length === 0 && (
                  <tr>
                    <td colSpan={columns.length}>No transformers match your search or filters.</td>
                  </tr>
                )}
              </tbody>
            </table>
          )}

          {!hasNoTransformersAtAll && (
            <div
              style={{ marginTop: "1rem", display: "flex", gap: "0.75rem", alignItems: "center" }}
            >
              <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                Previous
              </button>
              <span>
                Page {page} of {Math.max(1, Math.ceil(transformersQuery.data.total / pageSize))}
              </span>
              <button
                type="button"
                disabled={page * pageSize >= transformersQuery.data.total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
