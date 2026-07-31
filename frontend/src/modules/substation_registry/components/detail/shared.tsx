import type { ReactNode } from "react";

import { tokens } from "../../../../theme/tokens";

/**
 * Structural building blocks for the Substation Detail lower workspace, so the
 * embedded sections read as one coherent engineering workspace. Style constants
 * live in ./styles.ts; this file exports components only.
 */

/** A titled group of related section cards (e.g. "Engineering Information"). */
export function WorkspaceGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section style={{ display: "flex", flexDirection: "column", gap: tokens.space[3] }}>
      <h2
        style={{
          margin: 0,
          fontFamily: tokens.typography.fontFamily,
          fontSize: "11px",
          fontWeight: tokens.typography.weight.bold,
          letterSpacing: "0.11em",
          textTransform: "uppercase",
          color: tokens.color.textFaint,
        }}
      >
        {title}
      </h2>
      {children}
    </section>
  );
}

/** A quiet count/summary line for a section (e.g. "3 transformers installed"). */
export function SectionMeta({ children }: { children: ReactNode }) {
  return (
    <p style={{ margin: 0, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.size.small, color: tokens.color.textSecondary }}>
      {children}
    </p>
  );
}
