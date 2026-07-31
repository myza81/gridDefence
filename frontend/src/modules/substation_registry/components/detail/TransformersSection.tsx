import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { ApiError } from "../../../../api/client";
import { Badge } from "../../../../components/ui/Badge";
import { Card } from "../../../../components/ui/Card";
import { DetailSection } from "../../../../components/ui/DetailSection";
import { EmptyState } from "../../../../components/ui/EmptyState";
import { ErrorState } from "../../../../components/ui/ErrorState";
import { useIsMobile } from "../../../../components/layout/useIsMobile";
import { tokens } from "../../../../theme/tokens";
import { useReferenceData } from "../../../../reference_data/useReferenceData";
import { equipmentRegistryApi } from "../../../equipment_registry/api";
import type { TransformerSummary } from "../../../equipment_registry/types";
import { toneForStatusCode } from "../../lifecycle";
import { SectionMeta } from "./shared";
import { rowBorder, rowLinkStyle, tableStyle, tableWrapStyle, tdStyle, thStyle } from "./styles";

/**
 * Concise substation-local view of installed transformers (substation-owned
 * equipment — every transformer connects two of this substation's switchyards,
 * HV↔LV). Read-only here: the primary action opens the full Transformer record
 * in its own registry (this is NOT the Transformer Registry embedded whole).
 */
export function TransformersSection({ substationId }: { substationId: string }) {
  const referenceData = useReferenceData();
  const isMobile = useIsMobile();
  const query = useQuery({
    queryKey: ["substation", substationId, "transformers"],
    queryFn: () => equipmentRegistryApi.listTransformers({ substation_id: substationId, page_size: 200 }),
  });
  const transformers = query.data?.items ?? [];

  const statusBadge = (statusId: number) => {
    const status = referenceData.operationalStatusesById.get(statusId);
    return <Badge label={status?.label ?? String(statusId)} tone={toneForStatusCode(status?.code)} />;
  };

  return (
    <DetailSection title="Transformers" headingLevel={3} description="Installed at this substation — each connects an HV and an LV switchyard.">
      {query.isError ? (
        <ErrorState title="Couldn't load transformers" message={query.error instanceof ApiError ? query.error.message : undefined} onRetry={() => void query.refetch()} />
      ) : query.isPending ? (
        <p style={{ ...rowLinkStyle, color: tokens.color.textSecondary, fontWeight: 400 }}>Loading transformers…</p>
      ) : transformers.length === 0 ? (
        <EmptyState title="No transformers registered at this substation" />
      ) : (
        <>
          <SectionMeta>
            {transformers.length} transformer{transformers.length === 1 ? "" : "s"} installed
          </SectionMeta>
          <div data-testid="transformers-list">
            {isMobile ? (
              <div style={{ display: "flex", flexDirection: "column", gap: tokens.space[2] }}>
                {transformers.map((t) => (
                  <Card key={t.transformer_id} padding="14px" style={{ display: "flex", flexDirection: "column", gap: tokens.space[2] }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: tokens.space[2] }}>
                      <Link to={`/transformers/${t.transformer_id}`} style={rowLinkStyle}>{t.generated_short_name}</Link>
                      {statusBadge(t.operational_status_id)}
                    </div>
                    <span style={{ fontFamily: tokens.typography.fontFamily, fontSize: "12.5px", color: tokens.color.textSecondary }}>
                      {t.hv_voltage_level_label} ↔ {t.lv_voltage_level_label}
                      {t.capacity_mva != null ? ` · ${t.capacity_mva} MVA` : ""}
                    </span>
                  </Card>
                ))}
              </div>
            ) : (
              <div style={tableWrapStyle}>
                <table style={tableStyle}>
                  <thead>
                    <tr>
                      <th style={thStyle} scope="col">Transformer</th>
                      <th style={thStyle} scope="col">Windings (HV ↔ LV)</th>
                      <th style={thStyle} scope="col">Capacity</th>
                      <th style={thStyle} scope="col">Status</th>
                      <th style={thStyle} scope="col"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {transformers.map((t: TransformerSummary) => (
                      <tr key={t.transformer_id} style={{ borderTop: rowBorder }}>
                        <td style={{ ...tdStyle, fontWeight: tokens.typography.weight.semibold }}>
                          <Link to={`/transformers/${t.transformer_id}`} style={rowLinkStyle}>{t.generated_short_name}</Link>
                        </td>
                        <td style={tdStyle}>{t.hv_voltage_level_label} ↔ {t.lv_voltage_level_label}</td>
                        <td style={tdStyle}>{t.capacity_mva != null ? `${t.capacity_mva} MVA` : "—"}</td>
                        <td style={tdStyle}>{statusBadge(t.operational_status_id)}</td>
                        <td style={{ ...tdStyle, textAlign: "right" }}>
                          <Link to={`/transformers/${t.transformer_id}`} style={rowLinkStyle} aria-label={`Open transformer ${t.generated_short_name}`}>Open</Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </DetailSection>
  );
}
