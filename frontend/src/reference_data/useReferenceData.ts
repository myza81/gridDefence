import { useQuery } from "@tanstack/react-query";

import { referenceDataApi } from "./api";
import type {
  GmZoneSummary,
  GridOwnerSummary,
  LineTypeSummary,
  OperationalStatusSummary,
  RegionSummary,
  StateSummary,
  VoltageLevelSummary,
} from "./types";

function byId<T>(items: T[], idKey: keyof T): Map<number, T> {
  return new Map(items.map((item) => [item[idKey] as number, item]));
}

/**
 * Fetches every Core Platform reference table once and exposes both the raw
 * lists (for `<select>` options) and id -> row maps (for display lookups,
 * e.g. rendering a substation's `region_id` as "Northern" in a table cell).
 */
export function useReferenceData() {
  const voltageLevels = useQuery({
    queryKey: ["reference-data", "voltage-levels"],
    queryFn: referenceDataApi.listVoltageLevels,
  });
  const regions = useQuery({
    queryKey: ["reference-data", "regions"],
    queryFn: referenceDataApi.listRegions,
  });
  const gmZones = useQuery({
    queryKey: ["reference-data", "gm-zones"],
    queryFn: referenceDataApi.listGmZones,
  });
  const states = useQuery({
    queryKey: ["reference-data", "states"],
    queryFn: referenceDataApi.listStates,
  });
  const gridOwners = useQuery({
    queryKey: ["reference-data", "grid-owners"],
    queryFn: referenceDataApi.listGridOwners,
  });
  const operationalStatuses = useQuery({
    queryKey: ["reference-data", "operational-statuses"],
    queryFn: referenceDataApi.listOperationalStatuses,
  });
  const lineTypes = useQuery({
    queryKey: ["reference-data", "line-types"],
    queryFn: referenceDataApi.listLineTypes,
  });

  const isLoading =
    voltageLevels.isLoading ||
    regions.isLoading ||
    gmZones.isLoading ||
    states.isLoading ||
    gridOwners.isLoading ||
    operationalStatuses.isLoading ||
    lineTypes.isLoading;

  const voltageLevelItems: VoltageLevelSummary[] = voltageLevels.data ?? [];
  const regionItems: RegionSummary[] = regions.data ?? [];
  const gmZoneItems: GmZoneSummary[] = gmZones.data ?? [];
  const stateItems: StateSummary[] = states.data ?? [];
  const gridOwnerItems: GridOwnerSummary[] = gridOwners.data ?? [];
  const operationalStatusItems: OperationalStatusSummary[] = operationalStatuses.data ?? [];
  const lineTypeItems: LineTypeSummary[] = lineTypes.data ?? [];

  return {
    isLoading,
    voltageLevels: voltageLevelItems,
    regions: regionItems,
    gmZones: gmZoneItems,
    states: stateItems,
    gridOwners: gridOwnerItems,
    operationalStatuses: operationalStatusItems,
    lineTypes: lineTypeItems,
    voltageLevelsById: byId(voltageLevelItems, "voltage_level_id"),
    regionsById: byId(regionItems, "region_id"),
    gmZonesById: byId(gmZoneItems, "gm_zone_id"),
    statesById: byId(stateItems, "state_id"),
    gridOwnersById: byId(gridOwnerItems, "grid_owner_id"),
    operationalStatusesById: byId(operationalStatusItems, "operational_status_id"),
    lineTypesById: byId(lineTypeItems, "line_type_id"),
  };
}
