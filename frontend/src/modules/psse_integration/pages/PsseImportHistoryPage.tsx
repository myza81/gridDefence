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
import { psseIntegrationApi } from "../api";
import type { BatchSummary } from "../types";

const columnHelper = createColumnHelper<BatchSummary>();

/** Import batch audit history (Workflow 8, §8.11) — every upload/commit
 * action, regardless of outcome, is a permanent, queryable record. */
export function PsseImportHistoryPage() {
  const { permissions } = useAuth();
  const canImport = permissions.has("psse_integration.import");

  const [page, setPage] = useState(1);
  const pageSize = 20;

  const batchesQuery = useQuery({
    queryKey: ["psse-integration", "batches", { page }],
    queryFn: () => psseIntegrationApi.listBatches({ page, page_size: pageSize }),
  });

  const columns = [
    columnHelper.accessor("source_file_reference", { header: "File" }),
    columnHelper.accessor("import_type", { header: "Type" }),
    columnHelper.accessor("status", { header: "Status" }),
    columnHelper.accessor("imported_by", {
      header: "Imported by",
      cell: (info) => info.getValue().username,
    }),
    columnHelper.accessor("created_at", { header: "Created" }),
    columnHelper.display({
      id: "actions",
      header: "",
      cell: (info) => (
        <Link to={`/psse-integration/batches/${info.row.original.batch_id}`}>View</Link>
      ),
    }),
  ];

  const table = useReactTable({
    data: batchesQuery.data?.items ?? [],
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
        <h2>PSS/E import history</h2>
        {canImport && <Link to="/psse-integration/import">New import</Link>}
      </div>

      {batchesQuery.isLoading && <p>Loading import history...</p>}
      {batchesQuery.isError && <p role="alert">Failed to load import history.</p>}

      {batchesQuery.data && batchesQuery.data.total === 0 && (
        <div style={{ padding: "2rem", textAlign: "center", border: "1px dashed #ccc" }}>
          <p>No PSS/E imports have been made yet.</p>
          {canImport && <Link to="/psse-integration/import">Start your first import</Link>}
        </div>
      )}

      {batchesQuery.data && batchesQuery.data.total > 0 && (
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
            </tbody>
          </table>

          <div style={{ marginTop: "1rem", display: "flex", gap: "0.75rem", alignItems: "center" }}>
            <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            <span>
              Page {page} of {Math.max(1, Math.ceil(batchesQuery.data.total / pageSize))}
            </span>
            <button
              type="button"
              disabled={page * pageSize >= batchesQuery.data.total}
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
