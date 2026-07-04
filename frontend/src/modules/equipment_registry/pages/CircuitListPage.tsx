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
import type { CircuitSummary } from "../types";

const columnHelper = createColumnHelper<CircuitSummary>();

export function CircuitListPage() {
  const { permissions } = useAuth();
  const canWrite = permissions.has("equipment_registry.write");
  const referenceData = useReferenceData();

  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [voltageLevelId, setVoltageLevelId] = useState<string>("");
  const [lineTypeId, setLineTypeId] = useState<string>("");
  const [statusId, setStatusId] = useState<string>("");
  const pageSize = 20;

  const circuitsQuery = useQuery({
    queryKey: ["circuits", { page, search, voltageLevelId, lineTypeId, statusId }],
    queryFn: () =>
      equipmentRegistryApi.listCircuits({
        page,
        page_size: pageSize,
        search: search || undefined,
        voltage_level_id: voltageLevelId ? Number(voltageLevelId) : undefined,
        line_type_id: lineTypeId ? Number(lineTypeId) : undefined,
        operational_status_id: statusId ? Number(statusId) : undefined,
      }),
  });

  const columns = [
    columnHelper.accessor("circuit_name", { header: "Circuit" }),
    columnHelper.accessor("bay_number", { header: "Bay / Circuit No." }),
    columnHelper.accessor("voltage_level_id", {
      header: "Voltage",
      cell: (info) => referenceData.voltageLevelsById.get(info.getValue())?.label ?? info.getValue(),
    }),
    columnHelper.accessor("line_type_id", {
      header: "Line type",
      cell: (info) => referenceData.lineTypesById.get(info.getValue())?.label ?? info.getValue(),
    }),
    columnHelper.accessor("terminal_count", { header: "Terminals" }),
    columnHelper.accessor("operational_status_id", {
      header: "Status",
      cell: (info) =>
        referenceData.operationalStatusesById.get(info.getValue())?.label ?? info.getValue(),
    }),
    columnHelper.accessor("is_interconnector", {
      header: "Interconnector",
      cell: (info) => (info.getValue() ? "Yes" : "No"),
    }),
    columnHelper.display({
      id: "actions",
      header: "",
      cell: (info) => <Link to={`/circuits/${info.row.original.circuit_id}`}>View</Link>,
    }),
  ];

  const table = useReactTable({
    data: circuitsQuery.data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const isFiltered = Boolean(search || voltageLevelId || lineTypeId || statusId);
  const hasNoCircuitsAtAll = circuitsQuery.data?.total === 0 && !isFiltered;

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
        <h2>Circuits</h2>
        {canWrite && (
          <Link
            to="/circuits/new"
            style={{
              padding: "0.5rem 1rem",
              backgroundColor: "#1a73e8",
              color: "#fff",
              borderRadius: "4px",
              textDecoration: "none",
              fontWeight: 600,
            }}
          >
            New Circuit
          </Link>
        )}
      </div>

      <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap" }}>
        <input
          aria-label="Search circuits"
          placeholder="Search bay/circuit no. or substation..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
        />
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
          aria-label="Filter by line type"
          value={lineTypeId}
          onChange={(e) => {
            setLineTypeId(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All line types</option>
          {referenceData.lineTypes.map((type) => (
            <option key={type.line_type_id} value={type.line_type_id}>
              {type.label}
            </option>
          ))}
        </select>
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
      </div>

      {circuitsQuery.isLoading && <p>Loading circuits...</p>}
      {circuitsQuery.isError && <p role="alert">Failed to load circuits.</p>}

      {circuitsQuery.data && (
        <>
          {hasNoCircuitsAtAll ? (
            <div style={{ padding: "2rem", textAlign: "center", border: "1px dashed #ccc" }}>
              <p>No circuits have been registered yet.</p>
              {canWrite && <Link to="/circuits/new">Register your first circuit</Link>}
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
                    <td colSpan={columns.length}>No circuits match your search or filters.</td>
                  </tr>
                )}
              </tbody>
            </table>
          )}

          {!hasNoCircuitsAtAll && (
            <div
              style={{ marginTop: "1rem", display: "flex", gap: "0.75rem", alignItems: "center" }}
            >
              <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                Previous
              </button>
              <span>
                Page {page} of {Math.max(1, Math.ceil(circuitsQuery.data.total / pageSize))}
              </span>
              <button
                type="button"
                disabled={page * pageSize >= circuitsQuery.data.total}
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
