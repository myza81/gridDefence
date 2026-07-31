import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ApiError } from "../../../../api/client";
import { Badge } from "../../../../components/ui/Badge";
import { Button } from "../../../../components/ui/Button";
import { Card } from "../../../../components/ui/Card";
import { ConfirmActionDialog } from "../../../../components/ui/ConfirmActionDialog";
import { DetailSection } from "../../../../components/ui/DetailSection";
import { EmptyState } from "../../../../components/ui/EmptyState";
import { ErrorState } from "../../../../components/ui/ErrorState";
import { MetadataList } from "../../../../components/ui/MetadataList";
import { SelectField } from "../../../../components/ui/SelectField";
import { TextField } from "../../../../components/ui/TextField";
import { tokens } from "../../../../theme/tokens";
import { useAuth } from "../../../iam/AuthContext";
import { useReferenceData } from "../../../../reference_data/useReferenceData";
import { equipmentRegistryApi } from "../../../equipment_registry/api";
import type { VoltageYardSummary } from "../../../equipment_registry/types";
import { toneForStatusCode } from "../../lifecycle";
import { mutedSmall } from "./styles";

type DialogAction = { yard: VoltageYardSummary; kind: "enter-error" | "restore" } | null;

/**
 * Switchyards — the authoritative representation of a substation's voltage
 * level(s) (ADR-009: one record per voltage level). Modernised into structured
 * record cards with the shared Badge, intentional (disclosed) metadata editing,
 * and audited lifecycle actions via ConfirmActionDialog (mark Entered in Error /
 * Restore — ADR-027). No hard delete. Owned by Equipment Registry, gated on
 * `equipment_registry.write`.
 */
export function SwitchyardsSection({ substationId }: { substationId: string }) {
  const { permissions } = useAuth();
  const canWrite = permissions.has("equipment_registry.write");
  const referenceData = useReferenceData();
  const queryClient = useQueryClient();

  const [showEnteredInError, setShowEnteredInError] = useState(false);
  const [editingYardId, setEditingYardId] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [dialog, setDialog] = useState<DialogAction>(null);

  const yardsQuery = useQuery({
    queryKey: ["substation", substationId, "voltage-yards"],
    queryFn: () => equipmentRegistryApi.listVoltageYards({ substation_id: substationId, include_entered_in_error: true }),
  });
  const invalidate = () => void queryClient.invalidateQueries({ queryKey: ["substation", substationId, "voltage-yards"] });

  const enteredInErrorStatusId = referenceData.operationalStatuses.find((s) => s.code === "ENTERED_IN_ERROR")?.operational_status_id;
  const allYards = yardsQuery.data ?? [];
  const visibleYards = allYards.filter((y) => showEnteredInError || y.operational_status_id !== enteredInErrorStatusId);
  const usedLevelIds = new Set(allYards.map((y) => y.voltage_level_id));
  const availableLevels = referenceData.voltageLevels.filter((l) => !usedLevelIds.has(l.voltage_level_id));

  const dialogMutation = useMutation({
    mutationFn: (action: NonNullable<DialogAction> & { reason: string }) =>
      action.kind === "enter-error"
        ? equipmentRegistryApi.updateVoltageYard(action.yard.voltage_yard_id, { operational_status_id: enteredInErrorStatusId, change_reason: action.reason })
        : equipmentRegistryApi.restoreVoltageYard(action.yard.voltage_yard_id, { change_reason: action.reason }),
    onSuccess: () => {
      invalidate();
      setDialog(null);
      setDialogReason("");
      setDialogError(null);
    },
    onError: (err: unknown) => setDialogError(err instanceof ApiError ? err.message : "Action failed."),
  });
  const [dialogReason, setDialogReason] = useState("");
  const [dialogError, setDialogError] = useState<string | null>(null);

  function statusBadge(statusId: number) {
    const status = referenceData.operationalStatusesById.get(statusId);
    return <Badge label={status?.label ?? String(statusId)} tone={toneForStatusCode(status?.code)} />;
  }

  const addAction = canWrite && availableLevels.length > 0 && !addOpen ? (
    <Button variant="secondary" onClick={() => setAddOpen(true)}>Add switchyard</Button>
  ) : undefined;

  return (
    <DetailSection title="Switchyards" headingLevel={3} actions={addAction}>
      <label htmlFor="show-entered-in-error-yards" style={{ display: "inline-flex", alignItems: "center", gap: tokens.space[2], fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.size.small, color: tokens.color.textSecondary }}>
        <input id="show-entered-in-error-yards" type="checkbox" checked={showEnteredInError} onChange={(e) => setShowEnteredInError(e.target.checked)} /> Show entered-in-error switchyards
      </label>

      {canWrite && addOpen && (
        <AddSwitchyardForm
          substationId={substationId}
          availableLevels={availableLevels}
          onCancel={() => setAddOpen(false)}
          onAdded={() => {
            invalidate();
            setAddOpen(false);
          }}
        />
      )}

      {yardsQuery.isError ? (
        <ErrorState title="Couldn't load switchyards" message={yardsQuery.error instanceof ApiError ? yardsQuery.error.message : undefined} onRetry={() => void yardsQuery.refetch()} />
      ) : yardsQuery.isPending ? (
        <p style={mutedSmall}>Loading switchyards…</p>
      ) : (
        <div data-testid="voltage-yards-list" style={{ display: "flex", flexDirection: "column", gap: tokens.space[2] }}>
          {visibleYards.length === 0 ? (
            <EmptyState title="No switchyards registered" description="Each voltage level physically present is registered here as one switchyard." />
          ) : (
            visibleYards.map((yard) => (
              <SwitchyardCard
                key={yard.voltage_yard_id}
                yard={yard}
                canWrite={canWrite}
                isEnteredInError={yard.operational_status_id === enteredInErrorStatusId}
                statusBadge={statusBadge(yard.operational_status_id)}
                isEditing={editingYardId === yard.voltage_yard_id}
                onEdit={() => setEditingYardId(yard.voltage_yard_id)}
                onCancelEdit={() => setEditingYardId(null)}
                onSaved={() => {
                  invalidate();
                  setEditingYardId(null);
                }}
                onEnterError={() => setDialog({ yard, kind: "enter-error" })}
                onRestore={() => setDialog({ yard, kind: "restore" })}
              />
            ))
          )}
          {canWrite && availableLevels.length === 0 && allYards.length > 0 && (
            <p style={mutedSmall}>This substation already has a switchyard at every known voltage level.</p>
          )}
        </div>
      )}

      <ConfirmActionDialog
        open={dialog !== null}
        title={dialog?.kind === "restore" ? "Restore switchyard" : "Mark switchyard as Entered in Error"}
        description={
          dialog?.kind === "restore" ? (
            <>Restore the <strong>{dialog?.yard.voltage_level_label}</strong> switchyard to <strong>Active</strong>. Its audit history is preserved; the original correction entry is kept.</>
          ) : (
            <>Mark the <strong>{dialog?.yard.voltage_level_label}</strong> switchyard as Entered in Error. It remains in the audit history but is hidden from active views and must no longer be used. This is not a delete.</>
          )
        }
        confirmLabel={dialog?.kind === "restore" ? "Restore switchyard" : "Mark as Entered in Error"}
        confirmTone={dialog?.kind === "restore" ? "primary" : "danger"}
        error={dialogError}
        pending={dialogMutation.isPending}
        confirmDisabled={dialogReason.trim() === ""}
        onCancel={() => {
          setDialog(null);
          setDialogReason("");
          setDialogError(null);
        }}
        onConfirm={() => {
          if (dialog === null || dialogReason.trim() === "") return;
          setDialogError(null);
          dialogMutation.mutate({ ...dialog, reason: dialogReason.trim() });
        }}
      >
        <TextField label="Reason" placeholder="Recorded in the audit log" value={dialogReason} onChange={(e) => setDialogReason(e.target.value)} />
      </ConfirmActionDialog>
    </DetailSection>
  );
}

interface SwitchyardCardProps {
  yard: VoltageYardSummary;
  canWrite: boolean;
  isEnteredInError: boolean;
  statusBadge: React.ReactNode;
  isEditing: boolean;
  onEdit: () => void;
  onCancelEdit: () => void;
  onSaved: () => void;
  onEnterError: () => void;
  onRestore: () => void;
}

function SwitchyardCard({ yard, canWrite, isEnteredInError, statusBadge, isEditing, onEdit, onCancelEdit, onSaved, onEnterError, onRestore }: SwitchyardCardProps) {
  const label = yard.voltage_level_label;
  return (
    <Card padding="16px" style={{ display: "flex", flexDirection: "column", gap: tokens.space[3] }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: tokens.space[3], flexWrap: "wrap" }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: tokens.space[2] }}>
          <span style={{ fontFamily: tokens.typography.fontFamily, fontWeight: tokens.typography.weight.bold, fontSize: "14px", color: tokens.color.textPrimary }}>{label}</span>
          {statusBadge}
        </span>
        {canWrite && (
          <span style={{ display: "inline-flex", gap: tokens.space[2], flexWrap: "wrap" }}>
            {!isEditing && (
              <Button variant="secondary" onClick={onEdit} aria-label={`Edit ${label} switchyard`} style={smallButtonStyle}>Edit</Button>
            )}
            {isEnteredInError ? (
              <Button variant="secondary" onClick={onRestore} aria-label={`Restore ${label} switchyard`} style={smallButtonStyle}>Restore</Button>
            ) : (
              <Button variant="secondary" onClick={onEnterError} aria-label={`Mark ${label} switchyard as entered in error`} style={{ ...smallButtonStyle, color: "#B23A1B", borderColor: "#E6C3BA" }}>Enter in error</Button>
            )}
          </span>
        )}
      </div>

      <MetadataList
        items={[
          { term: "Commissioned", value: yard.commissioning_date ?? "—" },
          { term: "Latitude", value: yard.latitude ?? "—" },
          { term: "Longitude", value: yard.longitude ?? "—" },
        ]}
      />

      {isEditing && <SwitchyardEditForm yard={yard} onCancel={onCancelEdit} onSaved={onSaved} />}
    </Card>
  );
}

function SwitchyardEditForm({ yard, onCancel, onSaved }: { yard: VoltageYardSummary; onCancel: () => void; onSaved: () => void }) {
  const [commissioningDate, setCommissioningDate] = useState(yard.commissioning_date ?? "");
  const [latitude, setLatitude] = useState(yard.latitude === null ? "" : String(yard.latitude));
  const [longitude, setLongitude] = useState(yard.longitude === null ? "" : String(yard.longitude));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setCommissioningDate(yard.commissioning_date ?? "");
    setLatitude(yard.latitude === null ? "" : String(yard.latitude));
    setLongitude(yard.longitude === null ? "" : String(yard.longitude));
  }, [yard.commissioning_date, yard.latitude, yard.longitude]);

  const mutation = useMutation({
    mutationFn: () =>
      equipmentRegistryApi.updateVoltageYard(yard.voltage_yard_id, {
        commissioning_date: commissioningDate || null,
        latitude: latitude === "" ? null : Number(latitude),
        longitude: longitude === "" ? null : Number(longitude),
      }),
    onSuccess: () => {
      setError(null);
      onSaved();
    },
    onError: (err: unknown) => setError(err instanceof ApiError ? err.message : "Failed to update switchyard."),
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        mutation.mutate();
      }}
      style={{ display: "flex", flexDirection: "column", gap: tokens.space[3], borderTop: `1px solid ${tokens.color.borderDivider}`, paddingTop: tokens.space[3] }}
    >
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(180px, 100%), 1fr))", gap: tokens.space[3] }}>
        <TextField label="Commissioning date" type="date" value={commissioningDate} onChange={(e) => setCommissioningDate(e.target.value)} />
        <TextField label="Latitude" inputMode="decimal" value={latitude} onChange={(e) => setLatitude(e.target.value)} />
        <TextField label="Longitude" inputMode="decimal" value={longitude} onChange={(e) => setLongitude(e.target.value)} />
      </div>
      {error && <p role="alert" style={{ margin: 0, color: tokens.color.feedbackError, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.size.small }}>{error}</p>}
      <div style={{ display: "flex", gap: tokens.space[2] }}>
        <Button type="submit" loading={mutation.isPending} style={smallButtonStyle}>Save</Button>
        <Button type="button" variant="secondary" onClick={onCancel} disabled={mutation.isPending} style={smallButtonStyle}>Cancel</Button>
      </div>
    </form>
  );
}

function AddSwitchyardForm({
  substationId,
  availableLevels,
  onCancel,
  onAdded,
}: {
  substationId: string;
  availableLevels: { voltage_level_id: number; label: string }[];
  onCancel: () => void;
  onAdded: () => void;
}) {
  const [voltageLevelId, setVoltageLevelId] = useState("");
  const [commissioningDate, setCommissioningDate] = useState("");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      equipmentRegistryApi.createVoltageYard({
        substation_id: substationId,
        voltage_level_id: Number(voltageLevelId),
        commissioning_date: commissioningDate || null,
        latitude: latitude === "" ? null : Number(latitude),
        longitude: longitude === "" ? null : Number(longitude),
      }),
    onSuccess: () => {
      setError(null);
      onAdded();
    },
    onError: (err: unknown) => setError(err instanceof ApiError ? err.message : "Failed to add switchyard."),
  });

  return (
    <Card padding="16px" style={{ display: "flex", flexDirection: "column", gap: tokens.space[3], background: tokens.color.surfaceSubtle }}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!voltageLevelId) {
            setError("Select a voltage level.");
            return;
          }
          mutation.mutate();
        }}
        noValidate
        style={{ display: "flex", flexDirection: "column", gap: tokens.space[3] }}
      >
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(180px, 100%), 1fr))", gap: tokens.space[3] }}>
          <SelectField label="New switchyard voltage level" value={voltageLevelId} onChange={(e) => setVoltageLevelId(e.target.value)} required>
            <option value="">Select voltage level…</option>
            {availableLevels.map((level) => (
              <option key={level.voltage_level_id} value={level.voltage_level_id}>{level.label}</option>
            ))}
          </SelectField>
          <TextField label="New switchyard commissioning date" type="date" value={commissioningDate} onChange={(e) => setCommissioningDate(e.target.value)} />
          <TextField label="New switchyard latitude" inputMode="decimal" value={latitude} onChange={(e) => setLatitude(e.target.value)} />
          <TextField label="New switchyard longitude" inputMode="decimal" value={longitude} onChange={(e) => setLongitude(e.target.value)} />
        </div>
        {error && <p role="alert" style={{ margin: 0, color: tokens.color.feedbackError, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.size.small }}>{error}</p>}
        <div style={{ display: "flex", gap: tokens.space[2] }}>
          <Button type="submit" loading={mutation.isPending} style={smallButtonStyle}>Add switchyard</Button>
          <Button type="button" variant="secondary" onClick={onCancel} disabled={mutation.isPending} style={smallButtonStyle}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}

const smallButtonStyle = { height: "32px", padding: "0 12px", fontSize: "12.5px" } as const;
