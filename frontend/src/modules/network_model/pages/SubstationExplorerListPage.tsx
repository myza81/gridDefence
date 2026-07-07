import { useQuery } from "@tanstack/react-query";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { useState } from "react";
import { Link } from "react-router-dom";

import { substationRegistryApi } from "../../substation_registry/api";
import type { SubstationSummary } from "../../substation_registry/types";

const columnHelper = createColumnHelper<SubstationSummary>();
const PAGE_SIZE = 25;

/**
 * Browse entry point for the Network Model — reuses Substation Registry's
 * own list endpoint directly rather than duplicating substation data
 * (CLAUDE.md §5.1; network-model-module.md §19). Each row navigates into
 * this module's own Substation Explorer detail view, not Substation
 * Registry's edit-focused detail page.
 */
export function SubstationExplorerListPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  const substationsQuery = useQuery({
    queryKey: ["network-model", "substations", { page, search }],
    queryFn: () =>
      substationRegistryApi.listSubstations({
        page,
        page_size: PAGE_SIZE,
        search: search || undefined,
      }),
  });

  const columns = [
    columnHelper.accessor("mnemonic", { header: "Mnemonic" }),
    columnHelper.accessor("official_name", { header: "Substation" }),
    columnHelper.display({
      id: "actions",
      header: "",
      cell: (info) => (
        <Link to={`/network-model/substations/${info.row.original.substation_id}`}>Explore</Link>
      ),
    }),
  ];

  const table = useReactTable({
    data: substationsQuery.data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <section>
      <h2>Substation Explorer</h2>
      <p>Browse registered substations to explore their Bays and electrical connectivity.</p>

      <div style={{ marginBottom: "1rem" }}>
        <input
          aria-label="Search mnemonic or name"
          placeholder="Search mnemonic or name..."
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
        />
      </div>

      {substationsQuery.isLoading && <p>Loading substations...</p>}
      {substationsQuery.isError && <p role="alert">Failed to load substations.</p>}

      {substationsQuery.data && (
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
                  <td colSpan={columns.length}>No substations match your search.</td>
                </tr>
              )}
            </tbody>
          </table>

          <div style={{ marginTop: "1rem", display: "flex", gap: "0.75rem", alignItems: "center" }}>
            <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            <span>
              Page {page} of {Math.max(1, Math.ceil(substationsQuery.data.total / PAGE_SIZE))}
            </span>
            <button
              type="button"
              disabled={page * PAGE_SIZE >= substationsQuery.data.total}
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
