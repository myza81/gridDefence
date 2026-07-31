import { tokens } from "../../theme/tokens";

/**
 * Reserved slot for future cross-platform engineering search (Application Shell
 * Architecture §6; Navigation Architecture §7) — resolving substations,
 * circuits, transformers, PSS/E objects, schemes and findings, and routing to
 * the owning workspace.
 *
 * PHASE D IS A PLACEHOLDER ONLY: no backend, no API call, no fabricated
 * results. It is a focusable, labelled button (not a text input that pretends
 * to accept a query) that clearly announces it is not yet available, so it is
 * keyboard/screen-reader accessible without misrepresenting capability.
 */
export function GlobalSearchPlaceholder() {
  return (
    <button
      type="button"
      aria-disabled="true"
      title="Global engineering search is coming soon"
      aria-label="Search GridDefence — coming soon"
      onClick={(event) => event.preventDefault()}
      style={{
        flex: 1,
        minWidth: 0,
        maxWidth: "520px",
        display: "flex",
        alignItems: "center",
        gap: tokens.space[2],
        background: tokens.color.surfaceSubtle,
        border: `1px solid ${tokens.color.borderDefault}`,
        borderRadius: tokens.radius.sm,
        padding: "7px 11px",
        color: tokens.color.textFaint,
        font: "inherit",
        fontFamily: tokens.typography.fontFamily,
        fontSize: tokens.typography.size.small,
        textAlign: "left",
        cursor: "not-allowed",
      }}
    >
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.2-3.2" strokeLinecap="round" />
      </svg>
      <span style={{ flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
        Search GridDefence
      </span>
      <span
        style={{
          flex: "none",
          fontSize: "10px",
          fontWeight: tokens.typography.weight.semibold,
          letterSpacing: "0.04em",
          textTransform: "uppercase",
          color: tokens.color.textFaint,
          border: `1px solid ${tokens.color.borderStrong}`,
          borderRadius: "4px",
          padding: "1px 5px",
        }}
      >
        Soon
      </span>
    </button>
  );
}
