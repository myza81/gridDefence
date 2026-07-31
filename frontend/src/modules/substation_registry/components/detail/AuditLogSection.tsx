import { ApiError } from "../../../../api/client";
import { DetailSection } from "../../../../components/ui/DetailSection";
import { EmptyState } from "../../../../components/ui/EmptyState";
import { ErrorState } from "../../../../components/ui/ErrorState";
import { tokens } from "../../../../theme/tokens";
import { useSubstationAuditLogQuery } from "../../hooks";
import { rowBorder, tableStyle, tableWrapStyle, tdStyle, thStyle } from "./styles";

/**
 * Governance view — the substation's own field-level change history
 * (read-only). Deliberately distinct from the Audit & Revision summary card
 * (which shows only created/updated accountability). Newest entries follow the
 * API's own order; content is shown verbatim (never summarised or fabricated).
 */
export function AuditLogSection({ substationId }: { substationId: string }) {
  const query = useSubstationAuditLogQuery(substationId);
  const entries = query.data?.items ?? [];

  return (
    <DetailSection title="Audit log" headingLevel={3}>
      {query.isError ? (
        <ErrorState
          title="Couldn't load the audit log"
          message={query.error instanceof ApiError ? query.error.message : undefined}
          onRetry={() => void query.refetch()}
        />
      ) : query.isPending ? (
        <p style={mutedSmall}>Loading audit log…</p>
      ) : entries.length === 0 ? (
        <EmptyState title="No audit events available" description="Field-level changes to this record will appear here." />
      ) : (
        <div style={tableWrapStyle}>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle} scope="col">When</th>
                <th style={thStyle} scope="col">Actor</th>
                <th style={thStyle} scope="col">Change</th>
                <th style={thStyle} scope="col">Reason</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.log_id} style={{ borderTop: rowBorder }}>
                  <td style={{ ...tdStyle, color: tokens.color.textSecondary }}>{formatTimestamp(entry.changed_at)}</td>
                  <td style={tdStyle}>{entry.changed_by?.display_name ?? entry.changed_by?.username ?? "—"}</td>
                  <td style={{ ...tdStyle, whiteSpace: "normal" }}>
                    <span style={{ fontWeight: tokens.typography.weight.semibold }}>{entry.field_name}</span>
                    {": "}
                    <span style={{ color: tokens.color.textSecondary }}>{entry.old_value ?? "—"}</span>
                    {" → "}
                    <span>{entry.new_value ?? "—"}</span>
                  </td>
                  <td style={{ ...tdStyle, whiteSpace: "normal", color: tokens.color.textSecondary }}>{entry.change_reason ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </DetailSection>
  );
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" })} · ${date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`;
}

const mutedSmall = { margin: 0, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.size.small, color: tokens.color.textSecondary } as const;
