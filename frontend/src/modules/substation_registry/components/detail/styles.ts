import type { CSSProperties } from "react";

import { tokens } from "../../../../theme/tokens";

/**
 * Shared table/record styling for the Substation Detail lower workspace, so
 * every embedded section reads as one coherent engineering workspace
 * (Consistent section design §12). Presentation constants only.
 */
export const tableWrapStyle: CSSProperties = { overflowX: "auto" };

export const tableStyle: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontFamily: tokens.typography.fontFamily,
  fontSize: "13px",
};

export const thStyle: CSSProperties = {
  padding: "9px 12px",
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
};

export const tdStyle: CSSProperties = {
  padding: "9px 12px",
  boxSizing: "border-box",
  textAlign: "left",
  verticalAlign: "middle",
  color: tokens.color.textPrimary,
  whiteSpace: "nowrap",
};

export const rowBorder = `1px solid ${tokens.color.borderDivider}`;

export const rowLinkStyle: CSSProperties = {
  color: tokens.color.link,
  fontWeight: tokens.typography.weight.semibold,
  textDecoration: "none",
  fontFamily: tokens.typography.fontFamily,
};

export const mutedSmall: CSSProperties = {
  margin: 0,
  fontFamily: tokens.typography.fontFamily,
  fontSize: tokens.typography.size.small,
  color: tokens.color.textSecondary,
};
