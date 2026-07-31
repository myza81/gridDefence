import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { ApiError } from "../../../../api/client";
import { Badge } from "../../../../components/ui/Badge";
import { DetailSection } from "../../../../components/ui/DetailSection";
import { EmptyState } from "../../../../components/ui/EmptyState";
import { ErrorState } from "../../../../components/ui/ErrorState";
import { tokens } from "../../../../theme/tokens";
import { useReferenceData } from "../../../../reference_data/useReferenceData";
import { equipmentRegistryApi } from "../../../equipment_registry/api";
import { toneForStatusCode } from "../../lifecycle";
import { rowBorder, rowLinkStyle, tableStyle, tableWrapStyle, tdStyle, thStyle } from "./styles";

/**
 * Engineering Connectivity — circuits connected to this substation, derived
 * from the Circuit Registry's own Circuit/CircuitTerminal records. This is the
 * manually-maintained engineering baseline; it is deliberately NOT PSS/E-derived
 * operational topology (a future snapshot view would be separate and comparable).
 */
export function ConnectivitySection({ substationId, substationMnemonic }: { substationId: string; substationMnemonic: string }) {
  const referenceData = useReferenceData();
  const query = useQuery({
    queryKey: ["substation", substationId, "circuits"],
    queryFn: () => equipmentRegistryApi.listCircuits({ substation_id: substationId, page_size: 200 }),
  });
  const circuits = query.data?.items ?? [];

  return (
    <DetailSection title="Engineering Connectivity" headingLevel={3} description="Manually-maintained engineering baseline — not PSS/E operational topology.">
      <p data-testid="connected-circuits-count" style={{ margin: 0, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.size.small, color: tokens.color.textSecondary }}>
        Connected Circuits: {query.data?.total ?? 0}
      </p>

      {query.isError ? (
        <ErrorState title="Couldn't load connectivity" message={query.error instanceof ApiError ? query.error.message : undefined} onRetry={() => void query.refetch()} />
      ) : query.isPending ? (
        <p style={mutedSmall}>Loading connectivity…</p>
      ) : circuits.length === 0 ? (
        <EmptyState title="No connected circuits recorded in the engineering registry." />
      ) : (
        <div style={tableWrapStyle}>
          <table data-testid="engineering-connectivity-table" style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle} scope="col">Circuit</th>
                <th style={thStyle} scope="col">Bay Number</th>
                <th style={thStyle} scope="col">Voltage Level</th>
                <th style={thStyle} scope="col">Line Type</th>
                <th style={thStyle} scope="col">Status</th>
                <th style={thStyle} scope="col">Other Connected Substations</th>
                <th style={thStyle} scope="col"></th>
              </tr>
            </thead>
            <tbody>
              {circuits.map((circuit) => {
                const otherSubstations = circuit.circuit_name
                  .split("–")
                  .map((m) => m.trim())
                  .filter((m) => m !== "" && m !== substationMnemonic);
                const status = referenceData.operationalStatusesById.get(circuit.operational_status_id);
                return (
                  <tr key={circuit.circuit_id} style={{ borderTop: rowBorder }}>
                    <td style={{ ...tdStyle, fontWeight: tokens.typography.weight.semibold }}>{circuit.circuit_name}</td>
                    <td style={tdStyle}>{circuit.bay_number}</td>
                    <td style={tdStyle}>{referenceData.voltageLevelsById.get(circuit.voltage_level_id)?.label}</td>
                    <td style={tdStyle}>{referenceData.lineTypesById.get(circuit.line_type_id)?.label}</td>
                    <td style={tdStyle}><Badge label={status?.label ?? String(circuit.operational_status_id)} tone={toneForStatusCode(status?.code)} /></td>
                    <td style={tdStyle}>{otherSubstations.length > 0 ? otherSubstations.join(", ") : "—"}</td>
                    <td style={{ ...tdStyle, textAlign: "right" }}>
                      <Link to={`/circuits/${circuit.circuit_id}`} style={rowLinkStyle} aria-label={`Open circuit ${circuit.circuit_name}`}>View</Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </DetailSection>
  );
}

const mutedSmall = { margin: 0, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.size.small, color: tokens.color.textSecondary } as const;
