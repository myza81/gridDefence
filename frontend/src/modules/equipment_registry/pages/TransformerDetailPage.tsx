import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { useAuth } from "../../iam/AuthContext";
import { useReferenceData } from "../../../reference_data/useReferenceData";
import { equipmentRegistryApi } from "../api";

export function TransformerDetailPage() {
  const { transformerId } = useParams<{ transformerId: string }>();
  const { permissions } = useAuth();
  const canWrite = permissions.has("equipment_registry.write");
  const referenceData = useReferenceData();
  const queryClient = useQueryClient();

  const transformerQuery = useQuery({
    queryKey: ["transformer", transformerId],
    queryFn: () => equipmentRegistryApi.getTransformer(transformerId!),
    enabled: transformerId !== undefined,
  });

  const auditLogQuery = useQuery({
    queryKey: ["transformer", transformerId, "audit-log"],
    queryFn: () => equipmentRegistryApi.listTransformerAuditLog(transformerId!),
    enabled: transformerId !== undefined,
  });

  const invalidateTransformer = () => {
    void queryClient.invalidateQueries({ queryKey: ["transformer", transformerId] });
  };

  const [transformerNumber, setTransformerNumber] = useState("");
  const [hvBreakerNumber, setHvBreakerNumber] = useState("");
  const [lvBreakerNumber, setLvBreakerNumber] = useState("");
  const [capacityMva, setCapacityMva] = useState("");
  const [commissioningDate, setCommissioningDate] = useState("");
  const [operationalStatusId, setOperationalStatusId] = useState("");
  const [transformerType, setTransformerType] = useState("");
  const [manufacturer, setManufacturer] = useState("");
  const [remarks, setRemarks] = useState("");
  const [editError, setEditError] = useState<string | null>(null);

  useEffect(() => {
    if (transformerQuery.data) {
      const detail = transformerQuery.data;
      const hv = detail.terminals.find((t) => t.side === "HV");
      const lv = detail.terminals.find((t) => t.side === "LV");
      setTransformerNumber(detail.transformer_number);
      setHvBreakerNumber(hv?.breaker_number ?? "");
      setLvBreakerNumber(lv?.breaker_number ?? "");
      setCapacityMva(detail.capacity_mva !== null ? String(detail.capacity_mva) : "");
      setCommissioningDate(detail.commissioning_date ?? "");
      setOperationalStatusId(String(detail.operational_status_id));
      setTransformerType(detail.transformer_type ?? "");
      setManufacturer(detail.manufacturer ?? "");
      setRemarks(detail.remarks ?? "");
    }
  }, [transformerQuery.data]);

  const updateMutation = useMutation({
    mutationFn: () =>
      equipmentRegistryApi.updateTransformer(transformerId!, {
        transformer_number: transformerNumber,
        hv_breaker_number: hvBreakerNumber,
        lv_breaker_number: lvBreakerNumber,
        capacity_mva: capacityMva ? Number(capacityMva) : null,
        commissioning_date: commissioningDate || null,
        operational_status_id: Number(operationalStatusId),
        transformer_type: transformerType || null,
        manufacturer: manufacturer || null,
        remarks: remarks || null,
      }),
    onSuccess: () => {
      setEditError(null);
      invalidateTransformer();
    },
    onError: (err: unknown) =>
      setEditError(err instanceof ApiError ? err.message : "Failed to update transformer."),
  });

  function handleEditSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    updateMutation.mutate();
  }

  if (transformerQuery.isLoading) {
    return <p>Loading transformer...</p>;
  }
  if (transformerQuery.isError || !transformerQuery.data) {
    return <p role="alert">Transformer not found.</p>;
  }

  const transformer = transformerQuery.data;
  const hvTerminal = transformer.terminals.find((t) => t.side === "HV");
  const lvTerminal = transformer.terminals.find((t) => t.side === "LV");

  return (
    <section>
      {/* Generated short name (e.g. SGT1) is computed by the backend at read
          time, never stored (Architecture Decision Gate outcome) — the
          uniqueness constraint on hv_switchyard_id/lv_switchyard_id/
          transformer_number represents the physical transformer's identity,
          while this short name is a computed, user-facing label derived
          from the HV voltage level and transformer number. Two transformers
          at different substations may legitimately share the same short
          name (e.g. two "SGT1"s). */}
      <h2>
        Transformer: {transformer.generated_short_name} ({transformer.substation_mnemonic})
      </h2>
      <dl>
        <dt>Substation</dt>
        <dd>
          {transformer.substation_mnemonic} — {transformer.substation_official_name}
        </dd>
        <dt>Bay / Transformer Number</dt>
        <dd>{transformer.transformer_number}</dd>
        <dt>Voltage Transformation</dt>
        <dd>
          {hvTerminal?.voltage_level_label} ↔ {lvTerminal?.voltage_level_label}
        </dd>
        <dt>HV switchyard</dt>
        <dd>
          {hvTerminal
            ? `${hvTerminal.substation_mnemonic} — ${hvTerminal.voltage_level_label} (${hvTerminal.substation_official_name})`
            : "—"}
        </dd>
        <dt>LV switchyard</dt>
        <dd>
          {lvTerminal
            ? `${lvTerminal.substation_mnemonic} — ${lvTerminal.voltage_level_label} (${lvTerminal.substation_official_name})`
            : "—"}
        </dd>
        <dt>HV breaker</dt>
        <dd>{hvTerminal?.breaker_number ?? "—"}</dd>
        <dt>LV breaker</dt>
        <dd>{lvTerminal?.breaker_number ?? "—"}</dd>
        <dt>Capacity (MVA)</dt>
        <dd>{transformer.capacity_mva ?? "—"}</dd>
        <dt>Commissioning date</dt>
        <dd>{transformer.commissioning_date ?? "—"}</dd>
        <dt>Status</dt>
        <dd>
          {referenceData.operationalStatusesById.get(transformer.operational_status_id)?.label}
        </dd>
        <dt>Type</dt>
        <dd>{transformer.transformer_type ?? "—"}</dd>
        <dt>Manufacturer</dt>
        <dd>{transformer.manufacturer ?? "—"}</dd>
        <dt>Remarks</dt>
        <dd>{transformer.remarks ?? "—"}</dd>
        <dt>Created by</dt>
        <dd>{transformer.created_by?.username ?? "—"}</dd>
        <dt>Updated by</dt>
        <dd>{transformer.updated_by?.username ?? "—"}</dd>
      </dl>

      {canWrite && (
        <>
          <h3>Edit</h3>
          <form onSubmit={handleEditSubmit}>
            <div>
              <label htmlFor="edit-transformer-number">Bay / Transformer Number</label>
              <br />
              <input
                id="edit-transformer-number"
                value={transformerNumber}
                onChange={(e) => setTransformerNumber(e.target.value)}
                maxLength={20}
              />
            </div>
            <div>
              <label htmlFor="edit-hv-breaker">HV breaker number</label>
              <br />
              <input
                id="edit-hv-breaker"
                value={hvBreakerNumber}
                onChange={(e) => setHvBreakerNumber(e.target.value)}
                maxLength={20}
              />
            </div>
            <div>
              <label htmlFor="edit-lv-breaker">LV breaker number</label>
              <br />
              <input
                id="edit-lv-breaker"
                value={lvBreakerNumber}
                onChange={(e) => setLvBreakerNumber(e.target.value)}
                maxLength={20}
              />
            </div>
            <div>
              <label htmlFor="edit-capacity-mva">Capacity (MVA)</label>
              <br />
              <input
                id="edit-capacity-mva"
                type="number"
                step="0.01"
                min="0"
                value={capacityMva}
                onChange={(e) => setCapacityMva(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="edit-commissioning-date">Commissioning date</label>
              <br />
              <input
                id="edit-commissioning-date"
                type="date"
                value={commissioningDate}
                onChange={(e) => setCommissioningDate(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="edit-operational-status">Status</label>
              <br />
              <select
                id="edit-operational-status"
                value={operationalStatusId}
                onChange={(e) => setOperationalStatusId(e.target.value)}
              >
                {referenceData.operationalStatuses.map((status) => (
                  <option key={status.operational_status_id} value={status.operational_status_id}>
                    {status.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="edit-transformer-type">Type</label>
              <br />
              <input
                id="edit-transformer-type"
                value={transformerType}
                onChange={(e) => setTransformerType(e.target.value)}
                maxLength={50}
              />
            </div>
            <div>
              <label htmlFor="edit-manufacturer">Manufacturer</label>
              <br />
              <input
                id="edit-manufacturer"
                value={manufacturer}
                onChange={(e) => setManufacturer(e.target.value)}
                maxLength={100}
              />
            </div>
            <div>
              <label htmlFor="edit-remarks">Remarks</label>
              <br />
              <textarea
                id="edit-remarks"
                value={remarks}
                onChange={(e) => setRemarks(e.target.value)}
              />
            </div>
            {editError && <p role="alert">{editError}</p>}
            <button type="submit" disabled={updateMutation.isPending}>
              Save changes
            </button>
          </form>
        </>
      )}

      <h3>Audit log</h3>
      <ul>
        {(auditLogQuery.data?.items ?? []).map((entry) => (
          <li key={entry.log_id}>
            {entry.field_name}: {entry.old_value ?? "—"} → {entry.new_value ?? "—"} (
            {entry.changed_by?.username ?? "unknown"}, {entry.changed_at})
            {entry.change_reason ? ` — ${entry.change_reason}` : ""}
          </li>
        ))}
        {auditLogQuery.data?.items.length === 0 && <li>No changes recorded yet.</li>}
      </ul>
    </section>
  );
}
