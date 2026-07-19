import { LifecycleBadge } from "./LifecycleBadge";
import type { SchemeVersionLifecycleStatus } from "./types";
import { VersionBadge } from "./VersionBadge";

interface SchemeVersionHeaderProps {
  /** Scheme-specific display title (e.g. a future UFLS module's own
   * "UFLS — <substation name>" heading) — supplied by the concrete
   * module; this shared header never invents or assumes scheme
   * terminology (scheme-future-extensibility.md §"organisational
   * terminology never leaks into the Scheme Engine"). */
  title: string;
  versionNumber: number;
  lifecycleStatus: SchemeVersionLifecycleStatus;
}

/**
 * The shared Scheme Version header block every concrete scheme module
 * reuses directly: a caller-supplied title plus the version and
 * lifecycle badges. Never references UFLS, UVLS, or EMLS itself.
 */
export function SchemeVersionHeader({
  title,
  versionNumber,
  lifecycleStatus,
}: SchemeVersionHeaderProps) {
  return (
    <div
      data-testid="scheme-version-header"
      style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}
    >
      <h2 style={{ margin: 0 }}>{title}</h2>
      <VersionBadge versionNumber={versionNumber} />
      <LifecycleBadge status={lifecycleStatus} />
    </div>
  );
}
