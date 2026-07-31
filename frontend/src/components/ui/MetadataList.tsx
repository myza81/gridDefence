import type { ReactNode } from "react";

import { tokens } from "../../theme/tokens";

export interface MetadataItem {
  term: string;
  value: ReactNode;
}

interface MetadataListProps {
  items: MetadataItem[];
}

/**
 * Term/value engineering metadata as a real `<dl>` (each `<dt>` directly
 * followed by its `<dd>` so the pairing is semantic and screen-reader
 * navigable). Two-column on wider space, single-column when narrow.
 */
export function MetadataList({ items }: MetadataListProps) {
  return (
    <dl
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(120px, max-content) 1fr",
        columnGap: tokens.space[5],
        rowGap: tokens.space[3],
        margin: 0,
        fontFamily: tokens.typography.fontFamily,
      }}
    >
      {items.map((item) => (
        // Fragment keeps <dt> and <dd> as direct <dl> children (dt.nextElementSibling === dd).
        <div key={item.term} style={{ display: "contents" }}>
          <dt style={{ fontSize: tokens.typography.size.small, fontWeight: tokens.typography.weight.semibold, color: tokens.color.textSecondary }}>
            {item.term}
          </dt>
          <dd style={{ margin: 0, fontSize: tokens.typography.size.label, color: tokens.color.textPrimary, minWidth: 0, overflowWrap: "anywhere" }}>
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
