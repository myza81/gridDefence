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
import { equipmentRegistryApi } from "../../equipment_registry/api";
import { substationRegistryApi } from "../api";
import type { SubstationSummary } from "../types";

const columnHelper = createColumnHelper<SubstationSummary>();

export function SubstationListPage() {
  const { permissions } = useAuth();
  const canWrite = permissions.has("substation_registry.write");
  const referenceData = useReferenceData();

  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [regionId, setRegionId] = useState<string>("");
  const [gmZoneId, setGmZoneId] = useState<string>("");
  const [statusId, setStatusId] = useState<string>("");
  const pageSize = 20;

  const substationsQuery = useQuery({
    queryKey: ["substations", { page, search, regionId, gmZoneId, statusId }],
    queryFn: () =>
      substationRegistryApi.listSubstations({
        page,
        page_size: pageSize,
        search: search || undefined,
        region_id: regionId ? Number(regionId) : undefined,
        gm_zone_id: gmZoneId ? Number(gmZoneId) : undefined,
        operational_status_id: statusId ? Number(statusId) : undefined,
      }),
  });

  // Voltage level is no longer a Substation attribute (ADR-009) — it is
  // represented exclusively by SubstationVoltageYard, owned by Equipment
  // Registry. Composed client-side, not via a backend join: Substation
  // Registry (Master Data) must never depend on Equipment Registry
  // (Network Data), per CLAUDE.md A2/F2.
  const voltageYardsQuery = useQuery({
    queryKey: ["voltage-yards"],
    queryFn: () => equipmentRegistryApi.listVoltageYards(),
  });
  // Substation lifecycle statuses (substation-registry.md §10, ADR-014) —
  // Planned/Mothballed/Retired remain seeded `operational_status` rows for
  // Equipment Registry's own, independent status model and may still
  // appear on legacy Substation rows created before this filter list was
  // tightened, but are no longer offered as a *filter* choice going
  // forward — "All statuses" (no filter) still returns any legacy rows.
  const substationStatusFilterOptions = referenceData.operationalStatuses.filter((status) =>
    ["UNDER_CONSTRUCTION", "ACTIVE", "DECOMMISSIONED", "ENTERED_IN_ERROR"].includes(status.code),
  );
  const voltageYardLabelsBySubstationId = new Map<string, string[]>();
  for (const yard of voltageYardsQuery.data ?? []) {
    const existing = voltageYardLabelsBySubstationId.get(yard.substation_id) ?? [];
    existing.push(yard.voltage_level_label);
    voltageYardLabelsBySubstationId.set(yard.substation_id, existing);
  }

  const columns = [
    columnHelper.accessor("mnemonic", { header: "Mnemonic" }),
    columnHelper.accessor("official_name", { header: "Name" }),
    columnHelper.display({
      id: "voltage_yards",
      header: "Switchyards",
      cell: (info) =>
        (voltageYardLabelsBySubstationId.get(info.row.original.substation_id) ?? []).join(", ") ||
        "—",
    }),
    columnHelper.accessor("region_id", {
      header: "Region",
      cell: (info) => referenceData.regionsById.get(info.getValue())?.label ?? info.getValue(),
    }),
    columnHelper.accessor("gm_zone_id", {
      header: "GM Zone",
      cell: (info) => referenceData.gmZonesById.get(info.getValue())?.label ?? info.getValue(),
    }),
    columnHelper.accessor("grid_owner_id", {
      header: "Owner",
      cell: (info) => referenceData.gridOwnersById.get(info.getValue())?.label ?? info.getValue(),
    }),
    columnHelper.accessor("operational_status_id", {
      header: "Status",
      cell: (info) =>
        referenceData.operationalStatusesById.get(info.getValue())?.label ?? info.getValue(),
    }),
    columnHelper.display({
      id: "actions",
      header: "",
      cell: (info) => <Link to={`/substations/${info.row.original.substation_id}`}>View</Link>,
    }),
  ];

  const table = useReactTable({
    data: substationsQuery.data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <section>
      <h2>Substations</h2>

      <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap" }}>
        <input
          aria-label="Search substations"
          placeholder="Search mnemonic or name..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
        />
        <select
          aria-label="Filter by region"
          value={regionId}
          onChange={(e) => {
            setRegionId(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All regions</option>
          {referenceData.regions.map((region) => (
            <option key={region.region_id} value={region.region_id}>
              {region.label}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter by GM Zone"
          value={gmZoneId}
          onChange={(e) => {
            setGmZoneId(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All GM Zones</option>
          {referenceData.gmZones.map((zone) => (
            <option key={zone.gm_zone_id} value={zone.gm_zone_id}>
              {zone.label}
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
          {substationStatusFilterOptions.map((status) => (
            <option key={status.operational_status_id} value={status.operational_status_id}>
              {status.label}
            </option>
          ))}
        </select>
        {canWrite && <Link to="/substations/new">Create substation</Link>}
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
                  <td colSpan={columns.length}>No substations found.</td>
                </tr>
              )}
            </tbody>
          </table>

          <div style={{ marginTop: "1rem", display: "flex", gap: "0.75rem", alignItems: "center" }}>
            <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            <span>
              Page {page} of {Math.max(1, Math.ceil(substationsQuery.data.total / pageSize))}
            </span>
            <button
              type="button"
              disabled={page * pageSize >= substationsQuery.data.total}
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
