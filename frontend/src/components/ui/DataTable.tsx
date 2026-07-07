import type { ColumnDef, SortingState } from "@tanstack/react-table";
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useState } from "react";

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

interface DataTableProps<T> {
  data: T[];
  columns: ColumnDef<T>[];
  emptyMessage?: string;
}

/**
 * Generic, fully client-side sortable/searchable/paginated table
 * (Operational Context Inspector, psse-integration-module.md §8.9e).
 *
 * Every other list page in this project paginates/sorts server-side,
 * because its data is never fully loaded at once. This component is for
 * the opposite case — a dataset already held entirely in memory (e.g. an
 * already-fetched Preview response) — where a further backend query is
 * neither possible nor wanted. Reusable by any future feature with the
 * same shape: caller supplies rows and column definitions; this component
 * owns no domain knowledge of what the rows represent.
 */
export function DataTable<T>({ data, columns, emptyMessage = "No records available." }: DataTableProps<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState("");
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize: 25 });

  const table = useReactTable({
    data,
    columns,
    state: { sorting, globalFilter, pagination },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  if (data.length === 0) {
    return <p>{emptyMessage}</p>;
  }

  const filteredCount = table.getFilteredRowModel().rows.length;
  const rows = table.getRowModel().rows;

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "0.5rem",
          gap: "1rem",
        }}
      >
        <input
          type="search"
          placeholder="Search..."
          aria-label="Search table"
          value={globalFilter}
          onChange={(e) => setGlobalFilter(e.target.value)}
        />
        <span>
          {filteredCount} of {data.length} records
        </span>
      </div>

      <table>
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th
                  key={header.id}
                  onClick={header.column.getToggleSortingHandler()}
                  style={{ cursor: header.column.getCanSort() ? "pointer" : undefined, textAlign: "left" }}
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                  {header.column.getIsSorted() === "asc" && " ▲"}
                  {header.column.getIsSorted() === "desc" && " ▼"}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length}>No records match your search.</td>
            </tr>
          )}
          {rows.map((row) => (
            <tr key={row.id}>
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.75rem", alignItems: "center" }}>
        <button type="button" disabled={!table.getCanPreviousPage()} onClick={() => table.previousPage()}>
          Previous
        </button>
        <span>
          Page {pagination.pageIndex + 1} of {Math.max(1, table.getPageCount())}
        </span>
        <button type="button" disabled={!table.getCanNextPage()} onClick={() => table.nextPage()}>
          Next
        </button>
        <label>
          Page size{" "}
          <select value={pagination.pageSize} onChange={(e) => table.setPageSize(Number(e.target.value))}>
            {PAGE_SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}
