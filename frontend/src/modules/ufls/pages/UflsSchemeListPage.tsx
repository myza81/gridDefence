import { useQuery } from "@tanstack/react-query";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../../iam/AuthContext";
import { uflsApi } from "../api";
import type { UflsSchemeSummary } from "../types";

const columnHelper = createColumnHelper<UflsSchemeSummary>();

/**
 * UFLS Scheme List (task Frontend Scope §"UFLS Scheme List") — every UFLS
 * scheme lineage, its currently Published version number (if any), and
 * its latest Draft version number (if any). Creating a scheme lineage
 * requires `ufls.manage`.
 */
export function UflsSchemeListPage() {
  const { permissions, isLoadingCurrentUser } = useAuth();
  const canManage = permissions.has("ufls.manage");

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  const listQuery = useQuery({
    queryKey: ["ufls", "schemes"],
    queryFn: () => uflsApi.listSchemes(),
  });

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    setCreateError(null);
    try {
      await uflsApi.createScheme({ name, description: description || null });
      setName("");
      setDescription("");
      await listQuery.refetch();
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "Failed to create scheme.");
    }
  };

  const columns = [
    columnHelper.accessor("name", {
      header: "Scheme",
      cell: (info) => (
        <Link to={`/ufls/schemes/${info.row.original.ufls_scheme_id}`}>{info.getValue()}</Link>
      ),
    }),
    columnHelper.accessor("description", {
      header: "Description",
      cell: (info) => info.getValue() ?? "—",
    }),
    columnHelper.accessor("published_version_number", {
      header: "Published Version",
      cell: (info) => (info.getValue() !== null ? `v${info.getValue()}` : "None"),
    }),
    columnHelper.accessor("latest_draft_version_number", {
      header: "Latest Draft",
      cell: (info) => (info.getValue() !== null ? `v${info.getValue()}` : "None"),
    }),
  ];

  const table = useReactTable({
    data: listQuery.data ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <section>
      <h2>UFLS Schemes</h2>
      <p>
        Under-Frequency Load Shedding scheme lineages. GridDefence records, validates, and
        publishes UFLS engineering schemes — it does not calculate the required shedding quantum
        or design the stage structure; those are external-study engineering decisions.
      </p>

      {listQuery.isLoading && <p>Loading UFLS schemes...</p>}
      {listQuery.isError && <p role="alert">Failed to load UFLS schemes.</p>}

      {listQuery.data && (
        <table>
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id}>{flexRender(header.column.columnDef.header, header.getContext())}</th>
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
                <td colSpan={columns.length}>No UFLS schemes exist yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      )}

      {!isLoadingCurrentUser && canManage && (
        <form onSubmit={handleCreate} style={{ marginTop: "1.5rem", maxWidth: "28rem" }}>
          <h3>Create UFLS Scheme</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <label>
              Name
              <input value={name} onChange={(e) => setName(e.target.value)} required />
            </label>
            <label>
              Description
              <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
            </label>
            {createError && <p role="alert">{createError}</p>}
            <button type="submit" disabled={!name.trim()}>
              Create Scheme
            </button>
          </div>
        </form>
      )}
      {!isLoadingCurrentUser && !canManage && (
        <p style={{ color: "#555", fontSize: "0.9rem" }}>
          Creating UFLS schemes requires UFLS manage permission.
        </p>
      )}
    </section>
  );
}
