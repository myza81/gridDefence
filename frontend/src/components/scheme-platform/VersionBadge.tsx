interface VersionBadgeProps {
  versionNumber: number;
}

/**
 * Displays a Scheme Version's sequential version number (e.g. "Version
 * 3"). Purely a display-only derivation of already-fetched data
 * (CLAUDE.md A12) — never computes or infers a version number itself.
 */
export function VersionBadge({ versionNumber }: VersionBadgeProps) {
  return (
    <span
      data-testid="version-badge"
      style={{
        display: "inline-block",
        padding: "0.15rem 0.6rem",
        borderRadius: "4px",
        fontSize: "0.85rem",
        fontWeight: 600,
        color: "#24292f",
        backgroundColor: "#eaeef2",
      }}
    >
      Version {versionNumber}
    </span>
  );
}
