import type { SchemeVersionLifecycleInfo } from "./types";

interface SchemeVersionMetadataPanelProps {
  metadata: SchemeVersionLifecycleInfo;
}

function formatTimestamp(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "—";
}

/**
 * Displays a Scheme Version's shared lifecycle metadata — publish/
 * supersede/entered-in-error timestamps and actors, engineering remarks.
 * Display-only (CLAUDE.md A12): formats already-fetched values, computes
 * nothing. A concrete scheme module's own detail page renders its own
 * scheme-specific structure alongside this panel, never inside it.
 */
export function SchemeVersionMetadataPanel({ metadata }: SchemeVersionMetadataPanelProps) {
  return (
    <dl data-testid="scheme-version-metadata-panel">
      <dt>Published</dt>
      <dd>
        {formatTimestamp(metadata.publishedAt)}
        {metadata.publishedBy ? ` by ${metadata.publishedBy.displayName}` : ""}
      </dd>

      <dt>Superseded</dt>
      <dd>{formatTimestamp(metadata.supersededAt)}</dd>

      <dt>Entered in Error</dt>
      <dd>
        {formatTimestamp(metadata.enteredInErrorAt)}
        {metadata.enteredInErrorBy ? ` by ${metadata.enteredInErrorBy.displayName}` : ""}
        {metadata.enteredInErrorReason ? ` — ${metadata.enteredInErrorReason}` : ""}
      </dd>

      <dt>Engineering Remarks</dt>
      <dd>{metadata.engineeringRemarks ?? "—"}</dd>

      <dt>Created</dt>
      <dd>{formatTimestamp(metadata.createdAt)}</dd>

      <dt>Last Updated</dt>
      <dd>{formatTimestamp(metadata.updatedAt)}</dd>
    </dl>
  );
}
