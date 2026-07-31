import { tokens } from "../../theme/tokens";

interface BrandMarkProps {
  /** Hide the wordmark (icon-rail / very small headers). */
  wordmark?: boolean;
}

/**
 * GridDefence identity — the shield mark plus wordmark, from the approved
 * Application Shell V2 direction. Shared by the header and the mobile drawer so
 * the brand is defined once. Restrained by design (Styling §15: no oversized
 * branding); the shell's job is to get out of the way.
 */
export function BrandMark({ wordmark = true }: BrandMarkProps) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "10px" }}>
      <svg width="26" height="26" viewBox="0 0 32 32" fill="none" aria-hidden="true" focusable="false" style={{ flex: "none" }}>
        <path
          d="M16 2 4 6.5v8.7C4 23 9.2 28.3 16 30c6.8-1.7 12-7 12-14.8V6.5L16 2Z"
          fill="#EEF2FE"
          stroke={tokens.color.actionPrimary}
          strokeWidth="1.8"
        />
        <path
          d="M16 8.5 11 22h2.6l.9-2.7h3l.9 2.7H21L16 8.5Zm-.9 6.9.9-2.8.9 2.8h-1.8Z"
          fill={tokens.color.textPrimary}
        />
        <path d="M12.5 12.5 16 10l3.5 2.5" stroke={tokens.color.actionPrimary} strokeWidth="1.3" strokeLinecap="round" />
      </svg>
      {wordmark && (
        <span
          style={{
            fontFamily: tokens.typography.fontFamily,
            fontWeight: tokens.typography.weight.extrabold,
            letterSpacing: "0.3px",
            fontSize: "15px",
            whiteSpace: "nowrap",
          }}
        >
          <span style={{ color: tokens.color.textPrimary }}>GRID</span>
          <span style={{ color: tokens.color.actionPrimary }}>DEFENCE</span>
        </span>
      )}
    </span>
  );
}
