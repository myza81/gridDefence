import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { Badge } from "../../../components/ui/Badge";
import { Card } from "../../../components/ui/Card";
import { EmptyState } from "../../../components/ui/EmptyState";
import { ErrorState } from "../../../components/ui/ErrorState";
import { MetadataList } from "../../../components/ui/MetadataList";
import { EngineeringMap } from "../../../components/map/EngineeringMap";
import type { EngineeringMapLayer } from "../../../components/map/EngineeringMap";
import { PENINSULAR_MALAYSIA_BOUNDS, styleById } from "../../../components/map/mapConfig";
import { isLocalMapAsset, probeLocalStandardInstalled } from "../../../components/map/mapAssets";
import { useIsMobile } from "../../../components/layout/useIsMobile";
import { tokens } from "../../../theme/tokens";
import { useReferenceData } from "../../../reference_data/useReferenceData";
import type { SubstationListFilters } from "../api";
import { useSubstationMapQuery } from "../hooks";
import { markerColorForStatusCode, substationStatuses, toneForStatusCode } from "../lifecycle";
import type { SubstationMapFeature } from "../types";

type MapFilters = Omit<SubstationListFilters, "page" | "page_size">;

/**
 * Substation geographic map view (Phase E.1). A complementary presentation of
 * the SAME authoritative registry records the table shows — it is not a PSS/E
 * topology viewer, a live operational map, or an electrical-connectivity model,
 * and it draws no lines (geographic proximity is not electrical connectivity).
 *
 * The map is a progressive enhancement over the always-present accessible
 * record list: every mapped substation is reachable and openable without the
 * map, and records without usable coordinates are counted and listed, never
 * silently dropped.
 */
export function SubstationMapView({ filters }: { filters: MapFilters }) {
  const referenceData = useReferenceData();
  const navigate = useNavigate();
  const query = useSubstationMapQuery(filters);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusId, setFocusId] = useState<string | null>(null);
  const [basemapAvailable, setBasemapAvailable] = useState(true);
  const [basemapNotice, setBasemapNotice] = useState<string | null>(null);

  // Structural (not cosmetic) layout switch — inline styles cannot express a
  // media query. Desktop: large map + side details. Tablet: balanced stack.
  // Mobile: bounded map height so the page never overflows.
  const isNarrow = useIsMobile(tokens.breakpoint.tablet);
  const isMobile = useIsMobile(tokens.breakpoint.mobile);
  const mapHeight = isMobile ? "380px" : isNarrow ? "460px" : "min(70vh, 680px)";

  // When the Standard basemap is the LOCAL offline package, bounded-probe once
  // whether its PMTiles archive is installed, so we can guide setup instead of
  // silently degrading. Only runs when a local /map-assets style is configured
  // (no probe in connected-only or unconfigured deployments).
  const localStandardConfigured = isLocalMapAsset(styleById("standard")?.styleUrl);
  const [offlineAssetsMissing, setOfflineAssetsMissing] = useState(false);
  useEffect(() => {
    if (!localStandardConfigured) return;
    let alive = true;
    void probeLocalStandardInstalled().then((ok) => {
      if (alive) setOfflineAssetsMissing(!ok);
    });
    return () => {
      alive = false;
    };
  }, [localStandardConfigured]);

  const items = useMemo(() => query.data?.items ?? [], [query.data]);
  const mapped = query.data?.mapped_count ?? 0;
  const missing = query.data?.missing_coordinate_count ?? 0;

  const withCoords = useMemo(() => items.filter((f) => f.coordinate_status === "present"), [items]);
  const withoutCoords = useMemo(() => items.filter((f) => f.coordinate_status !== "present"), [items]);

  // A search that resolves to exactly one record locates/highlights it. If that
  // record has no coordinates, it is still found — surfaced honestly, not hidden.
  const searchTerm = (filters.search ?? "").trim();
  const soleMatch = searchTerm !== "" && items.length === 1 ? items[0] : null;
  useEffect(() => {
    if (soleMatch) {
      setSelectedId(soleMatch.substation_id);
      setFocusId(soleMatch.coordinate_status === "present" ? soleMatch.substation_id : null);
    }
  }, [soleMatch?.substation_id, soleMatch?.coordinate_status]); // eslint-disable-line react-hooks/exhaustive-deps

  const statusOptions = substationStatuses(referenceData.operationalStatuses);
  const layer: EngineeringMapLayer = useMemo(() => {
    const colorByCategory: Record<string, string> = {};
    for (const status of referenceData.operationalStatuses) {
      colorByCategory[String(status.operational_status_id)] = markerColorForStatusCode(status.code);
    }
    return {
      id: "substations",
      fallbackColor: "#8B98AD",
      colorByCategory,
      markers: withCoords.map((f) => ({
        id: f.substation_id,
        longitude: f.longitude as number,
        latitude: f.latitude as number,
        category: String(f.operational_status_id),
        label: `${f.mnemonic} — ${f.official_name}`,
        popupHtml: buildPopupHtml(f, referenceData.operationalStatusesById.get(f.operational_status_id)?.label),
      })),
    };
  }, [withCoords, referenceData.operationalStatuses, referenceData.operationalStatusesById]);

  const selected = items.find((f) => f.substation_id === selectedId) ?? null;

  if (query.isError) {
    return (
      <ErrorState
        title="Couldn't load the substation map"
        message={query.error instanceof ApiError ? query.error.message : "The map data could not be reached. The table view remains available."}
        onRetry={() => void query.refetch()}
      />
    );
  }
  if (query.isPending) {
    return <p style={mutedSmall}>Loading substation map…</p>;
  }
  if (items.length === 0) {
    return (
      <EmptyState
        title={searchTerm || filters.region_id || filters.gm_zone_id || filters.state_id || filters.operational_status_id ? "No substations match the current filters" : "No substations registered"}
        description="Adjust or clear the filters to see more of the registry."
      />
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: tokens.space[3] }}>
      {/* Honest coordinate accounting + the geographic/electrical boundary. */}
      <Card padding="14px" style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: tokens.space[4], justifyContent: "space-between" }}>
        <span data-testid="map-coordinate-summary" style={{ fontFamily: tokens.typography.fontFamily, fontSize: "13px", color: tokens.color.textPrimary }}>
          <strong>{mapped}</strong> mapped · <strong>{missing}</strong> without coordinates
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: tokens.space[3], flexWrap: "wrap" }}>
          <Legend statusOptions={statusOptions} />
        </span>
      </Card>
      <p style={{ ...mutedSmall, display: "flex", alignItems: "center", gap: tokens.space[2] }}>
        <InfoIcon /> Geographic proximity does not represent electrical connectivity. This view shows registered locations only, not network topology or PSS/E operational context.
      </p>
      {soleMatch && soleMatch.coordinate_status !== "present" && (
        <p role="status" style={{ ...mutedSmall, color: "#8A5A00" }}>
          <strong>{soleMatch.mnemonic}</strong> is registered but has no coordinates, so it cannot be shown on the map. It is listed below.
        </p>
      )}

      {offlineAssetsMissing && (
        <div role="status" style={{ padding: "12px 14px", borderRadius: tokens.radius.lg, background: "#FFF7E6", border: "1px solid #F0D48A", fontFamily: tokens.typography.fontFamily, fontSize: "13px", color: "#6B4E00", lineHeight: tokens.typography.lineHeight.normal }}>
          <strong>Offline Standard map assets are not installed.</strong> The map basemap will fall back to a neutral canvas, but every substation is still plotted and listed, and the Table view remains available. To install the offline Peninsular Malaysia basemap, run <code>python scripts/fetch_map_assets.py</code> from the repository root (see DEVELOPMENT.md → “Offline map assets”).
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: isNarrow ? "1fr" : "minmax(0, 1.7fr) minmax(300px, 1fr)", gap: tokens.space[3], alignItems: "start" }}>
        <div style={{ minWidth: 0 }}>
          <EngineeringMap
            layers={[layer]}
            bounds={PENINSULAR_MALAYSIA_BOUNDS}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onBasemapStatus={setBasemapAvailable}
            onBasemapNotice={setBasemapNotice}
            onOpen={(id) => navigate(`/substations/${id}`)}
            focusId={focusId}
            height={mapHeight}
          />
          {basemapAvailable && basemapNotice && (
            <p role="status" style={{ ...mutedSmall, marginTop: tokens.space[2], color: "#8A5A00" }}>{basemapNotice}</p>
          )}
          {!basemapAvailable && (
            <p style={{ ...mutedSmall, marginTop: tokens.space[2] }}>
              The map is unavailable, but every substation remains reachable from the list.
            </p>
          )}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: tokens.space[3], minWidth: 0 }}>
          {selected && <SelectedPanel feature={selected} referenceData={referenceData} onClose={() => setSelectedId(null)} />}
          <Card padding="0" style={{ overflow: "hidden" }}>
            <div style={{ padding: "10px 14px", background: tokens.color.surfaceSubtle, borderBottom: `1px solid ${tokens.color.borderDivider}`, fontFamily: tokens.typography.fontFamily, fontSize: "11px", fontWeight: tokens.typography.weight.bold, letterSpacing: "0.06em", textTransform: "uppercase", color: tokens.color.textSecondary }}>
              Substations ({items.length})
            </div>
            <ul aria-label="Substations" style={{ listStyle: "none", margin: 0, padding: 0, maxHeight: "440px", overflowY: "auto" }}>
              {items.map((feature) => (
                <li key={feature.substation_id}>
                  <RecordRow
                    feature={feature}
                    referenceData={referenceData}
                    selected={feature.substation_id === selectedId}
                    onSelect={() => {
                      setSelectedId(feature.substation_id);
                      setFocusId(feature.coordinate_status === "present" ? feature.substation_id : null);
                    }}
                  />
                </li>
              ))}
            </ul>
          </Card>
          {withoutCoords.length > 0 && (
            <p style={mutedSmall}>
              {withoutCoords.length} substation{withoutCoords.length === 1 ? "" : "s"} without coordinates are listed above and can still be opened; add coordinates on each record to place it on the map.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

type ReferenceData = ReturnType<typeof useReferenceData>;

function Legend({ statusOptions }: { statusOptions: ReferenceData["operationalStatuses"] }) {
  return (
    <span style={{ display: "inline-flex", gap: tokens.space[3], flexWrap: "wrap", fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.size.small, color: tokens.color.textSecondary }}>
      {statusOptions.map((status) => (
        <span key={status.operational_status_id} style={{ display: "inline-flex", alignItems: "center", gap: "5px" }}>
          <span aria-hidden="true" style={{ width: "10px", height: "10px", borderRadius: "50%", background: markerColorForStatusCode(status.code), border: "1px solid #fff", boxShadow: "0 0 0 1px rgba(15,30,61,0.15)" }} />
          {status.label}
        </span>
      ))}
    </span>
  );
}

function RecordRow({ feature, referenceData, selected, onSelect }: { feature: SubstationMapFeature; referenceData: ReferenceData; selected: boolean; onSelect: () => void }) {
  const status = referenceData.operationalStatusesById.get(feature.operational_status_id);
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      style={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: tokens.space[2],
        padding: "9px 14px",
        border: "none",
        borderBottom: `1px solid ${tokens.color.borderDivider}`,
        background: selected ? tokens.color.primaryWash : "transparent",
        cursor: "pointer",
        textAlign: "left",
        fontFamily: tokens.typography.fontFamily,
      }}
    >
      <span style={{ minWidth: 0 }}>
        <span style={{ fontWeight: tokens.typography.weight.bold, fontVariantNumeric: "tabular-nums", color: tokens.color.textPrimary }}>{feature.mnemonic}</span>
        <span style={{ display: "block", fontSize: "12px", color: tokens.color.textSecondary, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{feature.official_name}</span>
      </span>
      <span style={{ display: "inline-flex", alignItems: "center", gap: "6px", flex: "none" }}>
        {feature.coordinate_status !== "present" && (
          <span title="No coordinates" style={{ fontSize: "10px", fontWeight: tokens.typography.weight.semibold, color: tokens.color.textFaint, border: `1px solid ${tokens.color.borderDefault}`, borderRadius: "4px", padding: "0 5px" }}>NO COORDS</span>
        )}
        <Badge label={status?.label ?? String(feature.operational_status_id)} tone={toneForStatusCode(status?.code)} />
      </span>
    </button>
  );
}

function SelectedPanel({ feature, referenceData, onClose }: { feature: SubstationMapFeature; referenceData: ReferenceData; onClose: () => void }) {
  const status = referenceData.operationalStatusesById.get(feature.operational_status_id);
  const dash = (v: string | undefined) => (v && v.length > 0 ? v : "—");
  return (
    <Card padding="16px" style={{ display: "flex", flexDirection: "column", gap: tokens.space[3] }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: tokens.space[2] }}>
        <div>
          <div style={{ fontFamily: tokens.typography.fontFamily, fontWeight: tokens.typography.weight.bold, fontSize: "15px", fontVariantNumeric: "tabular-nums", color: tokens.color.textPrimary }}>{feature.mnemonic}</div>
          <div style={{ fontFamily: tokens.typography.fontFamily, fontSize: "13px", color: tokens.color.textSecondary }}>{feature.official_name}</div>
        </div>
        <button type="button" onClick={onClose} aria-label="Close details" style={{ border: "none", background: "transparent", cursor: "pointer", color: tokens.color.textSecondary, fontSize: "18px", lineHeight: 1 }}>×</button>
      </div>
      <MetadataList
        items={[
          { term: "Lifecycle", value: <Badge label={status?.label ?? String(feature.operational_status_id)} tone={toneForStatusCode(status?.code)} /> },
          { term: "Region", value: dash(referenceData.regionsById.get(feature.region_id)?.label) },
          { term: "GM Zone", value: dash(referenceData.gmZonesById.get(feature.gm_zone_id)?.label) },
          { term: "Grid owner", value: dash(referenceData.gridOwnersById.get(feature.grid_owner_id)?.code) },
          { term: "State", value: feature.state_id === null ? "—" : dash(referenceData.statesById.get(feature.state_id)?.label) },
          { term: "Coordinate", value: formatCoordinate(feature.latitude, feature.longitude) },
        ]}
      />
      <Link to={`/substations/${feature.substation_id}`} style={{ color: tokens.color.link, fontWeight: tokens.typography.weight.semibold, textDecoration: "none", fontFamily: tokens.typography.fontFamily, fontSize: "13px" }}>
        Open substation →
      </Link>
    </Card>
  );
}

function formatCoordinate(lat: number | null, lng: number | null): string {
  if (lat === null || lng === null) return "—";
  return `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] as string));
}

/** Compact, pre-escaped popup for the on-map selected marker. Registry data
 *  (mnemonic/name) is user-entered, so every value is HTML-escaped. Voltage is
 *  intentionally absent — it is a switchyard composition, not part of the
 *  geographic registry projection (documented in engineering-map.md). The full
 *  record + Open action live in the accessible side panel. */
function buildPopupHtml(feature: SubstationMapFeature, statusLabel: string | undefined): string {
  const line = (label: string, value: string) =>
    `<div style="display:flex;justify-content:space-between;gap:12px;font-size:12px;line-height:1.5"><span style="color:#5A6A85">${escapeHtml(label)}</span><span style="color:#0F2340;font-weight:600">${escapeHtml(value)}</span></div>`;
  return [
    `<div style="font-family:'Inter',system-ui,sans-serif;min-width:180px">`,
    `<div style="font-weight:700;font-size:13px;color:#0F2340">${escapeHtml(feature.mnemonic)}</div>`,
    `<div style="font-size:12px;color:#5A6A85;margin-bottom:6px">${escapeHtml(feature.official_name)}</div>`,
    line("Lifecycle", statusLabel ?? String(feature.operational_status_id)),
    line("Coordinate", formatCoordinate(feature.latitude, feature.longitude)),
    `<a data-map-open href="/substations/${escapeHtml(feature.substation_id)}" style="display:inline-block;margin-top:8px;color:#2B5BE6;font-weight:600;font-size:12px;text-decoration:none">Open substation →</a>`,
    `</div>`,
  ].join("");
}

function InfoIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true" style={{ flex: "none" }}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" strokeLinecap="round" />
    </svg>
  );
}

const mutedSmall = { margin: 0, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.size.small, color: tokens.color.textSecondary, lineHeight: tokens.typography.lineHeight.normal } as const;
