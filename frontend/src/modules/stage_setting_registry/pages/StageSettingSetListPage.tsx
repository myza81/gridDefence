import { useQuery } from "@tanstack/react-query";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useAuth } from "../../iam/AuthContext";
import { stageSettingRegistryApi } from "../api";
import type { SchemeType, StageSettingSetStatus, StageSettingSetSummary } from "../types";

const columnHelper = createColumnHelper<StageSettingSetSummary>();

const STATUS_LABELS: Record<StageSettingSetStatus, string> = {
  DRAFT: "Draft",
  PUBLISHED: "Published",
  ENTERED_IN_ERROR: "Entered in Error",
};

/**
 * Stage Setting Registry list (stage-setting-set-architecture.md §10) —
 * every Stage Setting Set, filterable by scheme type (UFLS/UVLS — EMLS has
 * none, §2) and lifecycle status. Creating a new Draft set requires
 * `stage_setting_registry.manage`.
 */
export function StageSettingSetListPage() {
  const { permissions, isLoadingCurrentUser } = useAuth();
  const canManage = permissions.has("stage_setting_registry.manage");
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialSchemeType = searchParams.get("scheme_type");

  const [schemeType, setSchemeType] = useState<SchemeType | "">(
    initialSchemeType === "UFLS" || initialSchemeType === "UVLS" ? initialSchemeType : "",
  );
  const [status, setStatus] = useState<StageSettingSetStatus | "">("");
  const [newSchemeType, setNewSchemeType] = useState<SchemeType>(
    initialSchemeType === "UVLS" ? "UVLS" : "UFLS",
  );
  const [newDescription, setNewDescription] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const listQuery = useQuery({
    queryKey: ["stage-setting-sets", "list", { schemeType, status }],
    queryFn: () =>
      stageSettingRegistryApi.list({
        scheme_type: schemeType || undefined,
        status_filter: status || undefined,
        page_size: 200,
      }),
  });

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    setCreateError(null);
    setIsCreating(true);
    try {
      const created = await stageSettingRegistryApi.create({
        scheme_type: newSchemeType,
        description: newDescription || null,
      });
      navigate(`/stage-setting-sets/${created.stage_setting_set_id}`);
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "Failed to create Stage Setting Set.");
    } finally {
      setIsCreating(false);
    }
  };

  const columns = [
    columnHelper.accessor("scheme_type", { header: "Scheme Type" }),
    columnHelper.accessor("description", {
      header: "Description",
      cell: (info) => (
        <Link to={`/stage-setting-sets/${info.row.original.stage_setting_set_id}`}>
          {info.getValue() ?? "(no description)"}
        </Link>
      ),
    }),
    columnHelper.accessor("status", {
      header: "Status",
      cell: (info) => STATUS_LABELS[info.getValue()],
    }),
    columnHelper.accessor("setting_count", { header: "Stages" }),
    columnHelper.accessor("updated_at", {
      header: "Last Updated",
      cell: (info) => new Date(info.getValue()).toLocaleString(),
    }),
  ];

  const table = useReactTable({
    data: listQuery.data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <section>
      <h2>Stage Setting Registry</h2>
      <p>
        Reusable, independently-versioned stage structures (thresholds and time delays) for UFLS
        and UVLS. A Stage Setting Set is referenced — never copied — by any number of Scheme
        Versions of the matching scheme type. GridDefence does not calculate or suggest threshold
        values; they are entered here as external engineering policy.
      </p>

      <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap" }}>
        <select
          aria-label="Filter by scheme type"
          value={schemeType}
          onChange={(e) => setSchemeType(e.target.value as SchemeType | "")}
        >
          <option value="">All scheme types</option>
          <option value="UFLS">UFLS</option>
          <option value="UVLS">UVLS</option>
        </select>
        <select
          aria-label="Filter by status"
          value={status}
          onChange={(e) => setStatus(e.target.value as StageSettingSetStatus | "")}
        >
          <option value="">All statuses</option>
          <option value="DRAFT">Draft</option>
          <option value="PUBLISHED">Published</option>
          <option value="ENTERED_IN_ERROR">Entered in Error</option>
        </select>
      </div>

      {listQuery.isLoading && <p>Loading Stage Setting Sets...</p>}
      {listQuery.isError && <p role="alert">Failed to load Stage Setting Sets.</p>}

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
                <td colSpan={columns.length}>No Stage Setting Sets match your filters.</td>
              </tr>
            )}
          </tbody>
        </table>
      )}

      {!isLoadingCurrentUser && canManage && (
        <form onSubmit={handleCreate} style={{ marginTop: "1.5rem", maxWidth: "28rem" }}>
          <h3>Create Stage Setting Set</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <label>
              Scheme Type
              <select
                value={newSchemeType}
                onChange={(e) => setNewSchemeType(e.target.value as SchemeType)}
              >
                <option value="UFLS">UFLS</option>
                <option value="UVLS">UVLS</option>
              </select>
            </label>
            <label>
              Description
              <input value={newDescription} onChange={(e) => setNewDescription(e.target.value)} />
            </label>
            {createError && <p role="alert">{createError}</p>}
            <button type="submit" disabled={isCreating}>
              {isCreating ? "Creating..." : "Create Draft Stage Setting Set"}
            </button>
          </div>
        </form>
      )}
      {!isLoadingCurrentUser && !canManage && (
        <p style={{ color: "#555", fontSize: "0.9rem" }}>
          Creating Stage Setting Sets requires Stage Setting Registry manage permission.
        </p>
      )}
    </section>
  );
}
