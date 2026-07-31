import { ApiError } from "../../../../api/client";
import { Badge } from "../../../../components/ui/Badge";
import { DetailSection } from "../../../../components/ui/DetailSection";
import { EmptyState } from "../../../../components/ui/EmptyState";
import { ErrorState } from "../../../../components/ui/ErrorState";
import { tokens } from "../../../../theme/tokens";
import { useSubstationAliasesQuery } from "../../hooks";
import { rowBorder, tableStyle, tableWrapStyle, tdStyle, thStyle } from "./styles";

/**
 * Engineering History — retired mnemonics preserved when this substation was
 * renamed (identity history is never overwritten; substation-registry.md §8).
 * A compact historical table: each alias with the period it was valid, and an
 * "Alias/Retired" marker (an alias with no `valid_to` is still current).
 */
export function AliasHistorySection({ substationId }: { substationId: string }) {
  const query = useSubstationAliasesQuery(substationId);
  const aliases = query.data ?? [];

  return (
    <DetailSection title="Alias history" headingLevel={3}>
      {query.isError ? (
        <ErrorState
          title="Couldn't load alias history"
          message={query.error instanceof ApiError ? query.error.message : undefined}
          onRetry={() => void query.refetch()}
        />
      ) : query.isPending ? (
        <p style={mutedSmall}>Loading alias history…</p>
      ) : aliases.length === 0 ? (
        <EmptyState title="No aliases recorded" description="Former mnemonics appear here after a rename; this substation has never been renamed." />
      ) : (
        <div style={tableWrapStyle}>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle} scope="col">Alias</th>
                <th style={thStyle} scope="col">Valid from</th>
                <th style={thStyle} scope="col">Valid to</th>
                <th style={thStyle} scope="col">State</th>
              </tr>
            </thead>
            <tbody>
              {aliases.map((alias) => {
                const retired = alias.valid_to !== null;
                return (
                  <tr key={alias.alias_id} style={{ borderTop: rowBorder }}>
                    <td style={{ ...tdStyle, fontVariantNumeric: "tabular-nums", fontWeight: tokens.typography.weight.semibold }}>{alias.alias_mnemonic ?? alias.alias_name ?? "—"}</td>
                    <td style={{ ...tdStyle, color: tokens.color.textSecondary }}>{formatDate(alias.valid_from)}</td>
                    <td style={{ ...tdStyle, color: tokens.color.textSecondary }}>{alias.valid_to ? formatDate(alias.valid_to) : "present"}</td>
                    <td style={tdStyle}>
                      <Badge label={retired ? "Retired" : "Current"} tone={retired ? "neutral" : "success"} />
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

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
}

const mutedSmall = { margin: 0, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.size.small, color: tokens.color.textSecondary } as const;
