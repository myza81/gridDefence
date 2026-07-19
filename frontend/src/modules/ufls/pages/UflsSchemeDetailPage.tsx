import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { LifecycleBadge } from "../../../components/scheme-platform/LifecycleBadge";
import { VersionBadge } from "../../../components/scheme-platform/VersionBadge";
import { useAuth } from "../../iam/AuthContext";
import { uflsApi } from "../api";

/**
 * UFLS Scheme Detail — the scheme lineage's own identity plus its full
 * version history (task Frontend Scope §"UFLS Scheme Detail"). Creating a
 * new Draft version — optionally copied from an existing version's own
 * structure (shared-defence-scheme-domain-model.md §5) — requires
 * `ufls.manage`.
 */
export function UflsSchemeDetailPage() {
  const { schemeId } = useParams<{ schemeId: string }>();
  const navigate = useNavigate();
  const { permissions, isLoadingCurrentUser } = useAuth();
  const canManage = permissions.has("ufls.manage");

  const [copyFromVersionId, setCopyFromVersionId] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const schemeQuery = useQuery({
    queryKey: ["ufls", "scheme", schemeId],
    queryFn: () => uflsApi.getScheme(schemeId!),
    enabled: !!schemeId,
  });

  const versionsQuery = useQuery({
    queryKey: ["ufls", "scheme", schemeId, "versions"],
    queryFn: () => uflsApi.listSchemeVersions(schemeId!),
    enabled: !!schemeId,
  });

  const handleCreateDraft = async () => {
    if (!schemeId) return;
    setIsCreating(true);
    setCreateError(null);
    try {
      const version = await uflsApi.createDraftVersion(schemeId, {
        copied_from_version_id: copyFromVersionId || null,
      });
      navigate(`/ufls/versions/${version.version_id}`);
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "Failed to create Draft version.");
    } finally {
      setIsCreating(false);
    }
  };

  if (schemeQuery.isLoading) return <p>Loading scheme...</p>;
  if (schemeQuery.isError || !schemeQuery.data) return <p role="alert">Failed to load scheme.</p>;

  const scheme = schemeQuery.data;
  const versions = versionsQuery.data ?? [];

  return (
    <section>
      <h2>{scheme.name}</h2>
      <p>{scheme.description ?? "No description."}</p>

      <h3>Versions</h3>
      {versionsQuery.isLoading && <p>Loading versions...</p>}
      {versionsQuery.isError && <p role="alert">Failed to load versions.</p>}
      {versionsQuery.data && (
        <table>
          <thead>
            <tr>
              <th>Version</th>
              <th>Status</th>
              <th>Published At</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {versions.map((version) => (
              <tr key={version.version_id}>
                <td>
                  <VersionBadge versionNumber={version.version_number} />
                </td>
                <td>
                  <LifecycleBadge status={version.lifecycle_status} />
                </td>
                <td>{version.published_at ? new Date(version.published_at).toLocaleString() : "—"}</td>
                <td>
                  <Link to={`/ufls/versions/${version.version_id}`}>Open</Link>
                </td>
              </tr>
            ))}
            {versions.length === 0 && (
              <tr>
                <td colSpan={4}>No versions yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      )}

      {!isLoadingCurrentUser && canManage && (
        <div style={{ marginTop: "1.5rem" }}>
          <h3>Create Draft Version</h3>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <select
              aria-label="Copy structure from an existing version"
              value={copyFromVersionId}
              onChange={(e) => setCopyFromVersionId(e.target.value)}
            >
              <option value="">Start blank (no copy)</option>
              {versions.map((version) => (
                <option key={version.version_id} value={version.version_id}>
                  Copy structure from v{version.version_number}
                </option>
              ))}
            </select>
            <button type="button" onClick={handleCreateDraft} disabled={isCreating}>
              {isCreating ? "Creating..." : "Create Draft Version"}
            </button>
          </div>
          {createError && <p role="alert">{createError}</p>}
          <p style={{ color: "#555", fontSize: "0.85rem" }}>
            Copying carries over the selected Stage Setting Set, stages, and assignments — never
            target MW, publication status, acknowledgements, or findings (shared-defence-scheme-
            domain-model.md §5).
          </p>
        </div>
      )}
    </section>
  );
}
