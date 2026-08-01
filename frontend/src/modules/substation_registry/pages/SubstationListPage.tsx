import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { Badge } from "../../../components/ui/Badge";
import { Button } from "../../../components/ui/Button";
import { Card } from "../../../components/ui/Card";
import { EmptyState } from "../../../components/ui/EmptyState";
import { ErrorState } from "../../../components/ui/ErrorState";
import { PageHeader } from "../../../components/ui/PageHeader";
import { SelectField } from "../../../components/ui/SelectField";
import { TextField } from "../../../components/ui/TextField";
import { useIsMobile } from "../../../components/layout/useIsMobile";
import { useDebouncedValue } from "../../../hooks/useDebouncedValue";
import { tokens } from "../../../theme/tokens";
import { useReferenceData } from "../../../reference_data/useReferenceData";
import { useAuth } from "../../iam/AuthContext";
import { equipmentRegistryApi } from "../../equipment_registry/api";
import { SubstationMapView } from "../components/SubstationMapView";
import { useSubstationsQuery } from "../hooks";
import { substationStatuses, toneForStatusCode } from "../lifecycle";
import type { SubstationSummary } from "../types";

const PAGE_SIZE = 20;

export function SubstationListPage() {
  const { permissions } = useAuth();
  const canWrite = permissions.has("substation_registry.write");
  const referenceData = useReferenceData();
  const isMobile = useIsMobile();
  const [searchParams, setSearchParams] = useSearchParams();

  // Discrete filters + page live in the URL (shareable, deep-linkable); the
  // free-text search is a debounced local input mirrored into the URL.
  const regionId = searchParams.get("region") ?? "";
  const gmZoneId = searchParams.get("gm_zone") ?? "";
  const statusId = searchParams.get("status") ?? "";
  const page = Math.max(1, Number(searchParams.get("page") ?? "1") || 1);

  const [searchInput, setSearchInput] = useState(searchParams.get("q") ?? "");
  const debouncedSearch = useDebouncedValue(searchInput.trim(), 300);

  function updateParams(mutate: (next: URLSearchParams) => void, resetPage = true): void {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        mutate(next);
        if (resetPage) next.delete("page");
        return next;
      },
      { replace: true },
    );
  }

  // Mirror the debounced search into the URL without a render loop.
  useEffect(() => {
    if ((searchParams.get("q") ?? "") === debouncedSearch) return;
    updateParams((next) => (debouncedSearch ? next.set("q", debouncedSearch) : next.delete("q")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch]);

  const filters = useMemo(
    () => ({
      page,
      page_size: PAGE_SIZE,
      search: debouncedSearch || undefined,
      region_id: regionId ? Number(regionId) : undefined,
      gm_zone_id: gmZoneId ? Number(gmZoneId) : undefined,
      operational_status_id: statusId ? Number(statusId) : undefined,
    }),
    [page, debouncedSearch, regionId, gmZoneId, statusId],
  );

  // Table ↔ Map view via URL query (view=map) — filters are shared, so the two
  // views can never drift, and the view is deep-linkable / back-forward safe.
  const view = searchParams.get("view") === "map" ? "map" : "table";
  const mapFilters = useMemo(
    () => ({
      search: debouncedSearch || undefined,
      region_id: regionId ? Number(regionId) : undefined,
      gm_zone_id: gmZoneId ? Number(gmZoneId) : undefined,
      operational_status_id: statusId ? Number(statusId) : undefined,
    }),
    [debouncedSearch, regionId, gmZoneId, statusId],
  );

  const substationsQuery = useSubstationsQuery(filters);

  // Switchyard voltages are composed client-side (ADR-009; A2/F2 — Master Data
  // never depends on Equipment Registry, so this is a read-only compose, not a
  // backend join). Degrades to "—" if unavailable.
  const voltageYardsQuery = useQuery({
    queryKey: ["voltage-yards"],
    queryFn: () => equipmentRegistryApi.listVoltageYards(),
  });
  const voltageLabelsBySubstation = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const yard of voltageYardsQuery.data ?? []) {
      const existing = map.get(yard.substation_id) ?? [];
      existing.push(yard.voltage_level_label);
      map.set(yard.substation_id, existing);
    }
    return map;
  }, [voltageYardsQuery.data]);

  const statusOptions = substationStatuses(referenceData.operationalStatuses);
  const hasActiveFilters = Boolean(debouncedSearch || regionId || gmZoneId || statusId);

  const total = substationsQuery.data?.total ?? 0;
  const items = substationsQuery.data?.items ?? [];
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function resetFilters(): void {
    setSearchInput("");
    setSearchParams({}, { replace: true });
  }

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto" }}>
      <PageHeader
        title="Substation Registry"
        description="Authoritative registry of transmission substations referenced by equipment, network and defence-scheme workflows."
        meta={
          substationsQuery.isSuccess
            ? `${total} substation${total === 1 ? "" : "s"}${hasActiveFilters ? " matching the current filters" : " registered"}`
            : undefined
        }
        actions={
          <>
            <ViewSwitch view={view} onChange={(next) => updateParams((n) => (next === "map" ? n.set("view", "map") : n.delete("view")), false)} />
            {canWrite && <Link to="/substations/new" style={createActionStyle}><PlusIcon /> Register substation</Link>}
          </>
        }
      />

      <Card padding="16px" style={{ marginBottom: tokens.space[4] }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(200px, 100%), 1fr))", gap: tokens.space[3], alignItems: "end" }}>
          <TextField
            label="Search"
            placeholder="Search mnemonic or name…"
            aria-label="Search substations"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
          <SelectField label="Region" value={regionId} onChange={(e) => updateParams((n) => (e.target.value ? n.set("region", e.target.value) : n.delete("region")))}>
            <option value="">All regions</option>
            {referenceData.regions.map((region) => (
              <option key={region.region_id} value={region.region_id}>{region.label}</option>
            ))}
          </SelectField>
          <SelectField label="GM Zone" value={gmZoneId} onChange={(e) => updateParams((n) => (e.target.value ? n.set("gm_zone", e.target.value) : n.delete("gm_zone")))}>
            <option value="">All GM Zones</option>
            {referenceData.gmZones.map((zone) => (
              <option key={zone.gm_zone_id} value={zone.gm_zone_id}>{zone.label}</option>
            ))}
          </SelectField>
          <SelectField label="Lifecycle status" value={statusId} onChange={(e) => updateParams((n) => (e.target.value ? n.set("status", e.target.value) : n.delete("status")))}>
            <option value="">All statuses</option>
            {statusOptions.map((status) => (
              <option key={status.operational_status_id} value={status.operational_status_id}>{status.label}</option>
            ))}
          </SelectField>
        </div>
        {hasActiveFilters && (
          <div style={{ display: "flex", alignItems: "center", gap: tokens.space[2], marginTop: tokens.space[3], flexWrap: "wrap" }}>
            <span style={{ fontSize: tokens.typography.size.small, color: tokens.color.textSecondary, fontFamily: tokens.typography.fontFamily }}>Active filters applied.</span>
            <Button variant="secondary" onClick={resetFilters} style={{ height: "32px", padding: "0 12px", fontSize: "12.5px" }}>
              Reset filters
            </Button>
          </div>
        )}
      </Card>

      {view === "map" ? (
        <SubstationMapView filters={mapFilters} />
      ) : substationsQuery.isError ? (
        <ErrorState
          title="Couldn't load substations"
          message={substationsQuery.error instanceof ApiError ? substationsQuery.error.message : "The registry could not be reached. Check your connection and try again."}
          onRetry={() => void substationsQuery.refetch()}
        />
      ) : substationsQuery.isPending ? (
        <p style={mutedTextStyle}>Loading substations…</p>
      ) : items.length === 0 ? (
        hasActiveFilters ? (
          <EmptyState
            title="No substations match the current filters"
            description="Adjust or clear the filters to see more of the registry."
            action={<Button variant="secondary" onClick={resetFilters}>Reset filters</Button>}
          />
        ) : (
          <EmptyState
            title="No substations registered"
            description="The registry is empty. Register the first transmission substation to begin."
            action={canWrite ? <Link to="/substations/new" style={createActionStyle}><PlusIcon /> Register substation</Link> : undefined}
          />
        )
      ) : isMobile ? (
        <MobileList items={items} referenceData={referenceData} voltageLabelsBySubstation={voltageLabelsBySubstation} />
      ) : (
        <RegistryTable items={items} referenceData={referenceData} voltageLabelsBySubstation={voltageLabelsBySubstation} />
      )}

      {view === "table" && substationsQuery.isSuccess && items.length > 0 && (
        <nav aria-label="Pagination" style={{ display: "flex", alignItems: "center", gap: tokens.space[3], marginTop: tokens.space[4] }}>
          <Button variant="secondary" disabled={page <= 1} onClick={() => updateParams((n) => n.set("page", String(page - 1)), false)}>
            Previous
          </Button>
          <span style={mutedTextStyle}>Page {page} of {totalPages}</span>
          <Button variant="secondary" disabled={page >= totalPages} onClick={() => updateParams((n) => n.set("page", String(page + 1)), false)}>
            Next
          </Button>
        </nav>
      )}
    </div>
  );
}

interface RowsProps {
  items: SubstationSummary[];
  referenceData: ReturnType<typeof useReferenceData>;
  voltageLabelsBySubstation: Map<string, string[]>;
}

/** Segmented Table/Map view switch (accessible tablist-style buttons). */
function ViewSwitch({ view, onChange }: { view: "table" | "map"; onChange: (v: "table" | "map") => void }) {
  return (
    <span role="group" aria-label="Registry view" style={{ display: "inline-flex", border: `1px solid ${tokens.color.borderStrong}`, borderRadius: tokens.radius.md, overflow: "hidden" }}>
      {(["table", "map"] as const).map((option) => {
        const active = view === option;
        return (
          <button
            key={option}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option)}
            style={{
              height: tokens.control.height,
              padding: `0 ${tokens.space[4]}`,
              border: "none",
              background: active ? tokens.color.actionPrimary : tokens.color.surfacePanel,
              color: active ? tokens.color.actionPrimaryText : tokens.color.textPrimary,
              fontFamily: tokens.typography.fontFamily,
              fontSize: tokens.typography.size.button,
              fontWeight: tokens.typography.weight.semibold,
              cursor: "pointer",
            }}
          >
            {option === "table" ? "Table" : "Map"}
          </button>
        );
      })}
    </span>
  );
}

function StatusCell({ referenceData, statusId }: { referenceData: RowsProps["referenceData"]; statusId: number }) {
  const status = referenceData.operationalStatusesById.get(statusId);
  return <Badge label={status?.label ?? String(statusId)} tone={toneForStatusCode(status?.code)} />;
}

/**
 * The mnemonic rendered as the primary navigation affordance (the mnemonic is
 * the authoritative engineering identifier — engineers reason in mnemonics).
 * A real link (Enter-activatable, screen-reader-announced), styled as an
 * engineering identifier — semibold, primary blue, underline on hover/focus
 * only, tabular numerals — not a button or a decorated hyperlink.
 */
function MnemonicLink({ substationId, mnemonic, officialName, fontSize = "13px" }: { substationId: string; mnemonic: string; officialName: string; fontSize?: string }) {
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  return (
    <Link
      to={`/substations/${substationId}`}
      aria-label={`Open ${mnemonic} ${officialName}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
      style={{
        display: "inline-block",
        fontFamily: tokens.typography.fontFamily,
        fontSize,
        fontWeight: tokens.typography.weight.semibold,
        fontVariantNumeric: "tabular-nums",
        letterSpacing: "0.02em",
        color: tokens.color.link,
        textDecoration: hovered || focused ? "underline" : "none",
        cursor: "pointer",
        borderRadius: tokens.radius.sm,
        padding: "1px 3px",
        margin: "-1px -3px",
        outline: "none",
        boxShadow: focused ? tokens.focus.ring : "none",
      }}
    >
      {mnemonic}
    </Link>
  );
}

function RegistryTable({ items, referenceData, voltageLabelsBySubstation }: RowsProps) {
  return (
    <Card padding="0" style={{ overflowX: "auto" }}>
      {/* Columns are identity-first: the Mnemonic is the primary navigation
          target (engineers reason in mnemonics), so there is no generic "Open"
          action column. A future per-row overflow (⋮) menu can be added as a
          new trailing column here without restructuring the table. */}
      <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: tokens.typography.fontFamily, fontSize: "13px" }}>
        <thead>
          <tr>
            {["Mnemonic", "Substation", "Voltage", "Region", "GM Zone", "Grid Owner", "Status"].map((heading) => (
              <th key={heading} scope="col" style={thStyle}>
                {heading}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((substation) => (
            <tr key={substation.substation_id} style={{ borderTop: `1px solid ${tokens.color.borderDivider}` }}>
              <td style={tdStyle}>
                <MnemonicLink substationId={substation.substation_id} mnemonic={substation.mnemonic} officialName={substation.official_name} />
              </td>
              <td style={tdStyle}>{substation.official_name}</td>
              <td style={tdStyle}>{(voltageLabelsBySubstation.get(substation.substation_id) ?? []).join(", ") || "—"}</td>
              <td style={tdStyle}>{referenceData.regionsById.get(substation.region_id)?.label ?? substation.region_id}</td>
              <td style={tdStyle}>{referenceData.gmZonesById.get(substation.gm_zone_id)?.label ?? substation.gm_zone_id}</td>
              {/* Registry list shows the compact engineering abbreviation (the
                  reference-data `code`, e.g. "TNB"); the detail page keeps the
                  full engineering label. Presentation only — no data change. */}
              <td style={tdStyle}>{referenceData.gridOwnersById.get(substation.grid_owner_id)?.code ?? substation.grid_owner_id}</td>
              <td style={tdStyle}><StatusCell referenceData={referenceData} statusId={substation.operational_status_id} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function MobileList({ items, referenceData, voltageLabelsBySubstation }: RowsProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: tokens.space[3] }}>
      {items.map((substation) => (
        <Card key={substation.substation_id} padding="16px" style={{ display: "flex", flexDirection: "column", gap: tokens.space[2] }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: tokens.space[2] }}>
            <MnemonicLink substationId={substation.substation_id} mnemonic={substation.mnemonic} officialName={substation.official_name} fontSize="15px" />
            <StatusCell referenceData={referenceData} statusId={substation.operational_status_id} />
          </div>
          <span style={{ fontFamily: tokens.typography.fontFamily, fontSize: "13px", color: tokens.color.textPrimary }}>{substation.official_name}</span>
          <span style={{ fontFamily: tokens.typography.fontFamily, fontSize: "12.5px", color: tokens.color.textSecondary }}>
            {referenceData.gmZonesById.get(substation.gm_zone_id)?.label ?? "—"} · {(voltageLabelsBySubstation.get(substation.substation_id) ?? []).join(", ") || "no switchyards"}
          </span>
        </Card>
      ))}
    </div>
  );
}

function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M12 5v14M5 12h14" strokeLinecap="round" />
    </svg>
  );
}

// Header and body cells share identical padding, box-sizing and left alignment
// so every heading sits on the same vertical axis as its column values. The
// explicit `textAlign: "left"` overrides the browser's default centred <th>,
// which was the sole cause of the header/value misalignment (Status included:
// its header now starts at the left edge of the lifecycle badges).
const thStyle = {
  padding: "10px 14px",
  boxSizing: "border-box",
  textAlign: "left",
  verticalAlign: "middle",
  fontSize: "10.5px",
  letterSpacing: "0.05em",
  textTransform: "uppercase",
  color: tokens.color.textSecondary,
  fontWeight: tokens.typography.weight.bold,
  background: tokens.color.surfaceSubtle,
  whiteSpace: "nowrap",
} as const;

const tdStyle = {
  padding: "10px 14px",
  boxSizing: "border-box",
  textAlign: "left",
  color: tokens.color.textPrimary,
  verticalAlign: "middle",
  whiteSpace: "nowrap",
} as const;

const mutedTextStyle = {
  fontFamily: tokens.typography.fontFamily,
  fontSize: tokens.typography.size.label,
  color: tokens.color.textSecondary,
} as const;

/** Anchor styled as a primary button (avoids an interactive <button> nested in a <Link>). */
const createActionStyle = {
  display: "inline-flex",
  alignItems: "center",
  gap: tokens.space[2],
  height: tokens.control.height,
  padding: `0 ${tokens.space[5]}`,
  borderRadius: tokens.radius.md,
  background: tokens.color.actionPrimary,
  color: tokens.color.actionPrimaryText,
  border: `1px solid ${tokens.color.actionPrimary}`,
  fontFamily: tokens.typography.fontFamily,
  fontSize: tokens.typography.size.button,
  fontWeight: tokens.typography.weight.semibold,
  textDecoration: "none",
  whiteSpace: "nowrap",
} as const;
