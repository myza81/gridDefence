import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { Badge } from "../../../components/ui/Badge";
import { Button } from "../../../components/ui/Button";
import { ConfirmActionDialog } from "../../../components/ui/ConfirmActionDialog";
import { DetailSection } from "../../../components/ui/DetailSection";
import { ErrorState } from "../../../components/ui/ErrorState";
import { MetadataList } from "../../../components/ui/MetadataList";
import { PageHeader } from "../../../components/ui/PageHeader";
import { SelectField } from "../../../components/ui/SelectField";
import { TextField } from "../../../components/ui/TextField";
import { useIsMobile } from "../../../components/layout/useIsMobile";
import { tokens } from "../../../theme/tokens";
import { useAuth } from "../../iam/AuthContext";
import { useReferenceData } from "../../../reference_data/useReferenceData";
import { SubstationForm } from "../components/SubstationForm";
import { AliasHistorySection } from "../components/detail/AliasHistorySection";
import { AuditLogSection } from "../components/detail/AuditLogSection";
import { ConnectivitySection } from "../components/detail/ConnectivitySection";
import { SwitchyardsSection } from "../components/detail/SwitchyardsSection";
import { TransformersSection } from "../components/detail/TransformersSection";
import { WorkspaceGroup } from "../components/detail/shared";
import { useChangeStatusMutation, useSubstationQuery, useUpdateSubstationMutation } from "../hooks";
import { allowedTargetStatuses, toneForStatusCode } from "../lifecycle";
import type { SubstationCreate, SubstationUpdate } from "../types";

/**
 * Substation Detail — one coherent engineering workspace. A stable 2×2 summary
 * grid, an accessible collapsed-by-default edit disclosure, and three grouped
 * lower sections (Engineering Information / History / Governance) whose embedded
 * Equipment-Registry and history views share the same modern design language.
 * The detail page composes the sections; each section owns its own data and
 * behaviour (see components/detail/*). This is the reference workspace pattern
 * for future GridDefence registries (substation-registry-frontend.md).
 */
export function SubstationDetailPage() {
  const { substationId } = useParams<{ substationId: string }>();
  const id = substationId ?? "";
  const { permissions } = useAuth();
  const canWrite = permissions.has("substation_registry.write");
  const referenceData = useReferenceData();
  const isMobile = useIsMobile();

  const substationQuery = useSubstationQuery(substationId);

  // --- Substation edit (disclosure — collapsed by default) ---
  const [editError, setEditError] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const editTriggerRef = useRef<HTMLButtonElement>(null);
  const editPanelRef = useRef<HTMLDivElement>(null);
  const editWasOpen = useRef(false);
  const lifecycleButtonRef = useRef<HTMLButtonElement>(null);
  const updateMutation = useUpdateSubstationMutation(id);

  useEffect(() => {
    if (editOpen && !editWasOpen.current) {
      editPanelRef.current?.focus();
    } else if (!editOpen && editWasOpen.current) {
      editTriggerRef.current?.focus();
    }
    editWasOpen.current = editOpen;
  }, [editOpen]);

  function handleEditSubmit(payload: SubstationCreate | SubstationUpdate): void {
    setEditError(null);
    updateMutation.mutate(payload as SubstationUpdate, {
      onSuccess: () => setEditOpen(false),
      onError: (err: unknown) => setEditError(err instanceof ApiError ? err.message : "Failed to update substation."),
    });
  }

  function focusLifecycle(): void {
    const button = lifecycleButtonRef.current;
    if (!button) return;
    button.focus();
    try {
      button.scrollIntoView({ behavior: "smooth", block: "center" });
    } catch {
      /* jsdom / unsupported environments: no-op */
    }
  }

  // --- Lifecycle status change (confirm dialog offering only legal transitions) ---
  const [statusDialogOpen, setStatusDialogOpen] = useState(false);
  const [targetStatusId, setTargetStatusId] = useState("");
  const [changeReason, setChangeReason] = useState("");
  const [statusError, setStatusError] = useState<string | null>(null);
  const changeStatusMutation = useChangeStatusMutation(id);

  if (substationQuery.isPending) {
    return <p style={{ fontFamily: tokens.typography.fontFamily, color: tokens.color.textSecondary }}>Loading substation…</p>;
  }
  if (substationQuery.isError || !substationQuery.data) {
    const notFound = substationQuery.error instanceof ApiError && substationQuery.error.status === 404;
    return (
      <div style={{ maxWidth: "720px", margin: "0 auto" }}>
        <ErrorState
          title={notFound ? "Substation not found" : "Couldn't load this substation"}
          message={
            notFound
              ? "This substation record does not exist, or the link is out of date."
              : substationQuery.error instanceof ApiError
                ? substationQuery.error.message
                : "The record could not be reached."
          }
        />
        <p style={{ marginTop: tokens.space[4] }}>
          <Link to="/substations" style={{ color: tokens.color.link, fontFamily: tokens.typography.fontFamily }}>← Back to Substation Registry</Link>
        </p>
      </div>
    );
  }

  const substation = substationQuery.data;
  const currentStatus = referenceData.operationalStatusesById.get(substation.operational_status_id);
  const targetStatusOptions = allowedTargetStatuses(substation.operational_status_id, referenceData.operationalStatuses);

  const displayOrDash = (value: string | undefined) => (value && value.length > 0 ? value : "—");

  function closeStatusDialog(): void {
    setStatusDialogOpen(false);
    setTargetStatusId("");
    setChangeReason("");
    setStatusError(null);
  }

  function confirmStatusChange(): void {
    setStatusError(null);
    changeStatusMutation.mutate(
      { operational_status_id: Number(targetStatusId), change_reason: changeReason.trim() || null },
      {
        onSuccess: () => closeStatusDialog(),
        onError: (err: unknown) => setStatusError(err instanceof ApiError ? err.message : "Status change was rejected."),
      },
    );
  }

  return (
    <div style={{ maxWidth: "1100px", margin: "0 auto" }}>
      <div style={{ marginBottom: tokens.space[3] }}>
        <Link to="/substations" style={backLinkStyle}>← Back to Registry</Link>
      </div>
      <PageHeader
        title={substation.official_name}
        description={
          <span style={{ display: "inline-flex", flexDirection: "column", gap: tokens.space[2], alignItems: "flex-start" }}>
            <span style={identityMnemonicStyle}>{substation.mnemonic}</span>
            <Badge label={currentStatus?.label ?? String(substation.operational_status_id)} tone={toneForStatusCode(currentStatus?.code)} size="md" />
          </span>
        }
        actions={
          canWrite ? (
            <>
              <Button variant="secondary" aria-expanded={editOpen} aria-controls="substation-edit-panel" onClick={() => setEditOpen((open) => !open)} leadingIcon={<PencilIcon />}>
                Edit
              </Button>
              {targetStatusOptions.length > 0 && (
                <Button variant="secondary" onClick={focusLifecycle}>Change status</Button>
              )}
            </>
          ) : undefined
        }
      />

      {/* Stable 2×2 summary grid on desktop (single column on mobile) — the four
          cards always align predictably; Audit never floats alone in a 3rd row. */}
      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(2, minmax(0, 1fr))", gap: tokens.space[3], marginBottom: tokens.space[3] }}>
        <DetailSection title="Identity">
          <MetadataList
            items={[
              { term: "Mnemonic", value: <span style={identityMnemonicValueStyle}>{substation.mnemonic}</span> },
              { term: "Official name", value: substation.official_name },
            ]}
          />
        </DetailSection>

        <DetailSection title="Engineering Classification">
          <MetadataList
            items={[
              { term: "Region", value: displayOrDash(referenceData.regionsById.get(substation.region_id)?.label) },
              { term: "GM Zone", value: displayOrDash(referenceData.gmZonesById.get(substation.gm_zone_id)?.label) },
              { term: "State", value: substation.state_id === null ? "—" : displayOrDash(referenceData.statesById.get(substation.state_id)?.label) },
              { term: "Grid owner", value: displayOrDash(referenceData.gridOwnersById.get(substation.grid_owner_id)?.label) },
            ]}
          />
        </DetailSection>

        <DetailSection
          title="Lifecycle"
          actions={
            canWrite && targetStatusOptions.length > 0 ? (
              <Button ref={lifecycleButtonRef} variant="secondary" onClick={() => setStatusDialogOpen(true)}>Change status</Button>
            ) : undefined
          }
        >
          <MetadataList
            items={[
              { term: "Current status", value: <Badge label={currentStatus?.label ?? String(substation.operational_status_id)} tone={toneForStatusCode(currentStatus?.code)} size="md" /> },
            ]}
          />
          {canWrite && targetStatusOptions.length === 0 && (
            <p style={mutedSmall}>No status changes are available from the current state.</p>
          )}
        </DetailSection>

        <DetailSection title="Audit & Revision">
          <MetadataList
            items={[
              { term: "Created", value: <AuditValue at={substation.created_at} actor={substation.created_by?.display_name ?? substation.created_by?.username ?? "—"} /> },
              { term: "Last updated", value: <AuditValue at={substation.updated_at} actor={substation.updated_by?.display_name ?? substation.updated_by?.username ?? "—"} /> },
            ]}
          />
        </DetailSection>
      </div>

      {/* Edit is an accessible disclosure — collapsed by default so an engineer
          can inspect without facing a large form; editing is intentionally
          invoked (here or via the header "Edit" action). */}
      {canWrite && (
        <div style={{ marginBottom: tokens.space[5], paddingTop: tokens.space[4], borderTop: `1px solid ${tokens.color.borderDivider}` }}>
          {!editOpen && (
            <Button ref={editTriggerRef} variant="secondary" fullWidth aria-expanded={false} aria-controls="substation-edit-panel" onClick={() => setEditOpen(true)} leadingIcon={<PencilIcon />}>
              Edit substation
            </Button>
          )}
          <div id="substation-edit-panel" ref={editPanelRef} tabIndex={-1} role="region" aria-label="Edit substation" hidden={!editOpen} style={{ outline: "none" }}>
            {editOpen && (
              <DetailSection title="Edit substation">
                <SubstationForm mode="edit" referenceData={referenceData} initial={substation} submitting={updateMutation.isPending} error={editError} onSubmit={handleEditSubmit} onCancel={() => setEditOpen(false)} />
              </DetailSection>
            )}
          </div>
        </div>
      )}

      {/* ---- Lower workspace: grouped, consistently-styled sections ---- */}
      <div style={{ display: "flex", flexDirection: "column", gap: tokens.space[6] }}>
        <WorkspaceGroup title="Engineering Information">
          <SwitchyardsSection substationId={id} />
          <TransformersSection substationId={id} />
          <ConnectivitySection substationId={id} substationMnemonic={substation.mnemonic} />
        </WorkspaceGroup>

        <WorkspaceGroup title="Engineering History">
          <AliasHistorySection substationId={id} />
        </WorkspaceGroup>

        <WorkspaceGroup title="Governance">
          <AuditLogSection substationId={id} />
        </WorkspaceGroup>
      </div>

      <ConfirmActionDialog
        open={statusDialogOpen}
        title="Change substation status"
        description={
          <>
            Changing the operational status is an audited engineering action that follows the defined
            lifecycle transitions. The current status is <strong>{currentStatus?.label}</strong>.
          </>
        }
        confirmLabel="Change status"
        confirmTone={targetStatusOptions.find((s) => s.operational_status_id === Number(targetStatusId))?.code === "ENTERED_IN_ERROR" ? "danger" : "primary"}
        error={statusError}
        pending={changeStatusMutation.isPending}
        confirmDisabled={targetStatusId === ""}
        onCancel={closeStatusDialog}
        onConfirm={confirmStatusChange}
      >
        <SelectField label="New status" value={targetStatusId} onChange={(e) => setTargetStatusId(e.target.value)} required>
          <option value="">Select new status…</option>
          {targetStatusOptions.map((status) => (
            <option key={status.operational_status_id} value={status.operational_status_id}>{status.label}</option>
          ))}
        </SelectField>
        <TextField label="Change reason" placeholder="Recorded in the audit log (optional)" value={changeReason} onChange={(e) => setChangeReason(e.target.value)} />
      </ConfirmActionDialog>
    </div>
  );
}

/** Compact audit value: date · time on one line, actor beneath. */
function AuditValue({ at, actor }: { at: string; actor: string }) {
  const date = new Date(at);
  const valid = !Number.isNaN(date.getTime());
  const day = valid ? date.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" }) : at;
  const time = valid ? date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : "";
  return (
    <span style={{ display: "inline-flex", flexDirection: "column", lineHeight: 1.4 }}>
      <span style={{ fontVariantNumeric: "tabular-nums" }}>{time ? `${day} · ${time}` : day}</span>
      <span style={{ color: tokens.color.textSecondary, fontSize: tokens.typography.size.small }}>{actor}</span>
    </span>
  );
}

function PencilIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M4 20h4L18.5 9.5a2.1 2.1 0 0 0-3-3L5 17v3Z" strokeLinejoin="round" />
      <path d="M13.5 6.5l3 3" strokeLinecap="round" />
    </svg>
  );
}

const backLinkStyle = {
  color: tokens.color.link,
  textDecoration: "none",
  fontFamily: tokens.typography.fontFamily,
  fontSize: tokens.typography.size.small,
  fontWeight: tokens.typography.weight.semibold,
} as const;

const identityMnemonicStyle = {
  fontFamily: tokens.typography.fontFamily,
  fontVariantNumeric: "tabular-nums",
  fontWeight: tokens.typography.weight.bold,
  fontSize: "16px",
  letterSpacing: "0.04em",
  color: tokens.color.textPrimary,
} as const;

const identityMnemonicValueStyle = {
  fontVariantNumeric: "tabular-nums",
  fontWeight: tokens.typography.weight.bold,
  fontSize: "15px",
  letterSpacing: "0.03em",
  color: tokens.color.textPrimary,
} as const;

const mutedSmall = {
  margin: 0,
  fontFamily: tokens.typography.fontFamily,
  fontSize: tokens.typography.size.small,
  color: tokens.color.textSecondary,
} as const;
