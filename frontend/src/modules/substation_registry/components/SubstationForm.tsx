import type { FormEvent, ReactNode } from "react";
import { useEffect, useState } from "react";

import { Button } from "../../../components/ui/Button";
import { SelectField } from "../../../components/ui/SelectField";
import { TextField } from "../../../components/ui/TextField";
import { tokens } from "../../../theme/tokens";
import type { useReferenceData } from "../../../reference_data/useReferenceData";
import { initialStatuses } from "../lifecycle";
import type { SubstationCreate, SubstationDetail, SubstationUpdate } from "../types";

type ReferenceData = ReturnType<typeof useReferenceData>;

interface SubstationFormProps {
  mode: "create" | "edit";
  referenceData: ReferenceData;
  /** Current record, for preloading the edit form. */
  initial?: SubstationDetail;
  submitting: boolean;
  /** Form-level backend error (business rule / conflict) — shown as a summary. */
  error: string | null;
  onSubmit: (payload: SubstationCreate | SubstationUpdate) => void;
  onCancel?: () => void;
}

interface FieldErrors {
  mnemonic?: string;
  official_name?: string;
  region_id?: string;
  gm_zone_id?: string;
  grid_owner_id?: string;
  operational_status_id?: string;
  geolocation?: string;
}

/**
 * Grouped create/edit form for a Substation (Create §9, Edit §11). Fields are
 * organised by engineering meaning, use accessible reference-data selectors,
 * mark mandatory inputs, surface the mnemonic identity rule, prevent duplicate
 * submission, and preserve entered values when the server rejects the request
 * (the parent keeps this mounted and passes `error`).
 *
 * Edit mode intentionally manages the same fields the registry has always
 * allowed editing here (identity, classification, remarks). Latitude/longitude/
 * commissioning are managed per switchyard (ADR-009), and operational status is
 * changed through the dedicated, audited lifecycle action — never a silent edit.
 */
export function SubstationForm({ mode, referenceData, initial, submitting, error, onSubmit, onCancel }: SubstationFormProps) {
  const isEdit = mode === "edit";

  const [mnemonic, setMnemonic] = useState("");
  const [officialName, setOfficialName] = useState("");
  const [regionId, setRegionId] = useState("");
  const [gmZoneId, setGmZoneId] = useState("");
  const [stateId, setStateId] = useState("");
  const [gridOwnerId, setGridOwnerId] = useState("");
  const [operationalStatusId, setOperationalStatusId] = useState("");
  const [psseBusNumber, setPsseBusNumber] = useState("");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [commissionedDate, setCommissionedDate] = useState("");
  const [remarks, setRemarks] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  // Preload the edit form from the current record.
  useEffect(() => {
    if (!initial) return;
    setMnemonic(initial.mnemonic);
    setOfficialName(initial.official_name);
    setRegionId(String(initial.region_id));
    setGmZoneId(String(initial.gm_zone_id));
    setStateId(initial.state_id === null ? "" : String(initial.state_id));
    setGridOwnerId(String(initial.grid_owner_id));
    setRemarks(initial.remarks ?? "");
  }, [initial]);

  function validate(): FieldErrors {
    const errors: FieldErrors = {};
    if (!mnemonic.trim()) errors.mnemonic = "Mnemonic is required.";
    if (!officialName.trim()) errors.official_name = "Official name is required.";
    if (!regionId) errors.region_id = "Region is required.";
    if (!gmZoneId) errors.gm_zone_id = "GM Zone is required.";
    if (!gridOwnerId) errors.grid_owner_id = "Grid owner is required.";
    if (!isEdit && !operationalStatusId) errors.operational_status_id = "Initial status is required.";
    // Geolocation must be both-or-neither (substation-registry.md §8 rule 4).
    if (!isEdit && (latitude !== "") !== (longitude !== "")) {
      errors.geolocation = "Latitude and longitude must both be provided, or both left blank.";
    }
    return errors;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const errors = validate();
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    if (isEdit) {
      const payload: SubstationUpdate = {
        mnemonic: mnemonic.trim(),
        official_name: officialName.trim(),
        region_id: Number(regionId),
        gm_zone_id: Number(gmZoneId),
        // Explicit null clears the State; a value sets it (ADR-026).
        state_id: stateId === "" ? null : Number(stateId),
        grid_owner_id: Number(gridOwnerId),
        remarks: remarks.trim() === "" ? null : remarks.trim(),
      };
      onSubmit(payload);
      return;
    }

    const payload: SubstationCreate = {
      mnemonic: mnemonic.trim(),
      official_name: officialName.trim(),
      region_id: Number(regionId),
      gm_zone_id: Number(gmZoneId),
      grid_owner_id: Number(gridOwnerId),
      operational_status_id: Number(operationalStatusId),
      // Optional fields are omitted entirely when blank (never sent as a placeholder).
      ...(stateId ? { state_id: Number(stateId) } : {}),
      ...(psseBusNumber ? { psse_bus_number: Number(psseBusNumber) } : {}),
      ...(latitude && longitude ? { latitude: Number(latitude), longitude: Number(longitude) } : {}),
      ...(commissionedDate ? { commissioned_date: commissionedDate } : {}),
      ...(remarks.trim() ? { remarks: remarks.trim() } : {}),
    };
    onSubmit(payload);
  }

  const statusOptions = initialStatuses(referenceData.operationalStatuses);

  return (
    <form onSubmit={handleSubmit} noValidate style={{ display: "flex", flexDirection: "column", gap: tokens.space[6], maxWidth: "760px" }}>
      {/* Edit mode drops the "Identity" legend/description — the field labels
          already carry the meaning; create mode keeps the fuller framing. */}
      <FieldGroup legend={isEdit ? undefined : "Identity"} description={isEdit ? undefined : "How this substation is uniquely referenced across GridDefence."}>
        <TextField
          label="Mnemonic"
          value={mnemonic}
          onChange={(e) => setMnemonic(e.target.value)}
          maxLength={10}
          required
          error={fieldErrors.mnemonic}
          aria-describedby={isEdit ? undefined : "mnemonic-rule"}
        />
        {/* Create keeps the full mnemonic rule as inline help. The edit form
            has no permanent helper text — the field label, the enforced
            maxLength, and backend validation/error messages convey the rule
            when it is actually relevant. (aria-describedby is dropped in edit
            so there is no dangling reference; the field's own error linkage is
            unaffected.) */}
        {!isEdit && (
          <p id="mnemonic-rule" style={hintStyle}>
            Up to 10 characters. The mnemonic is an authoritative engineering identifier: it must be
            unique, and once assigned it is never reused for a different substation. It is stored
            exactly as entered.
          </p>
        )}
        <TextField
          label="Official name"
          value={officialName}
          onChange={(e) => setOfficialName(e.target.value)}
          maxLength={150}
          required
          error={fieldErrors.official_name}
        />
      </FieldGroup>

      {/* Edit mode drops the "Engineering classification" heading too — the
          field labels already convey it; create mode keeps the fuller framing. */}
      <FieldGroup legend={isEdit ? undefined : "Engineering classification"} description={isEdit ? undefined : "Reference classifications owned by Core Platform reference data."}>
        <div style={twoColStyle}>
          <SelectField label="Region" value={regionId} onChange={(e) => setRegionId(e.target.value)} required error={fieldErrors.region_id}>
            <option value="">Select…</option>
            {referenceData.regions.map((region) => (
              <option key={region.region_id} value={region.region_id}>
                {region.label}
              </option>
            ))}
          </SelectField>
          <SelectField label="GM Zone" value={gmZoneId} onChange={(e) => setGmZoneId(e.target.value)} required error={fieldErrors.gm_zone_id}>
            <option value="">Select…</option>
            {referenceData.gmZones.map((zone) => (
              <option key={zone.gm_zone_id} value={zone.gm_zone_id}>
                {zone.label}
              </option>
            ))}
          </SelectField>
          <SelectField label="State (Optional)" value={stateId} onChange={(e) => setStateId(e.target.value)}>
            <option value="">None</option>
            {referenceData.states.map((state) => (
              <option key={state.state_id} value={state.state_id}>
                {state.label}
              </option>
            ))}
          </SelectField>
          <SelectField label="Grid owner" value={gridOwnerId} onChange={(e) => setGridOwnerId(e.target.value)} required error={fieldErrors.grid_owner_id}>
            <option value="">Select…</option>
            {referenceData.gridOwners.map((owner) => (
              <option key={owner.grid_owner_id} value={owner.grid_owner_id}>
                {owner.label}
              </option>
            ))}
          </SelectField>
        </div>
        {!isEdit && (
          <SelectField
            label="Initial status"
            hint="A newly registered substation may only start Under Construction or Active (ADR-014)."
            value={operationalStatusId}
            onChange={(e) => setOperationalStatusId(e.target.value)}
            required
            error={fieldErrors.operational_status_id}
          >
            <option value="">Select…</option>
            {statusOptions.map((status) => (
              <option key={status.operational_status_id} value={status.operational_status_id}>
                {status.label}
              </option>
            ))}
          </SelectField>
        )}
      </FieldGroup>

      {!isEdit && (
        <FieldGroup legend="Location & metadata (optional)" description="Left blank if not yet known; latitude and longitude must be provided together.">
          <div style={twoColStyle}>
            <TextField label="PSS/E bus number" value={psseBusNumber} onChange={(e) => setPsseBusNumber(e.target.value)} inputMode="numeric" />
            <TextField label="Commissioned date" type="date" value={commissionedDate} onChange={(e) => setCommissionedDate(e.target.value)} />
            <TextField label="Latitude" value={latitude} onChange={(e) => setLatitude(e.target.value)} inputMode="decimal" error={fieldErrors.geolocation} />
            <TextField label="Longitude" value={longitude} onChange={(e) => setLongitude(e.target.value)} inputMode="decimal" />
          </div>
        </FieldGroup>
      )}

      <FieldGroup legend={isEdit ? undefined : "Remarks (optional)"}>
        <label htmlFor="substation-remarks" style={labelStyle}>
          Remarks
        </label>
        <textarea
          id="substation-remarks"
          value={remarks}
          onChange={(e) => setRemarks(e.target.value)}
          rows={3}
          style={textareaStyle}
        />
      </FieldGroup>

      {error != null && error !== "" && (
        <p role="alert" style={{ margin: 0, color: tokens.color.feedbackError, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.size.label, fontWeight: tokens.typography.weight.medium }}>
          {error}
        </p>
      )}

      <div style={{ display: "flex", gap: tokens.space[3], flexWrap: "wrap" }}>
        <Button type="submit" loading={submitting}>
          {isEdit ? "Save changes" : "Create substation"}
        </Button>
        {onCancel && (
          <Button type="button" variant="secondary" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}

/**
 * Groups related fields. With a `legend` it renders a labelled `<fieldset>`;
 * without one (the simplified edit form, where field labels already carry the
 * meaning) it renders a plain container — never an empty, unlabelled fieldset.
 */
function FieldGroup({ legend, description, children }: { legend?: string; description?: string; children: ReactNode }) {
  const groupStyle = { border: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: tokens.space[3] } as const;
  if (legend == null) {
    return <div style={groupStyle}>{children}</div>;
  }
  return (
    <fieldset style={groupStyle}>
      <legend style={{ padding: 0, fontFamily: tokens.typography.fontFamily, fontSize: "13px", fontWeight: tokens.typography.weight.bold, color: tokens.color.textPrimary, textTransform: "uppercase", letterSpacing: "0.06em" }}>
        {legend}
      </legend>
      {description && <p style={{ ...hintStyle, marginTop: `-${tokens.space[1]}` }}>{description}</p>}
      {children}
    </fieldset>
  );
}

const hintStyle = {
  margin: 0,
  fontFamily: tokens.typography.fontFamily,
  fontSize: tokens.typography.size.small,
  color: tokens.color.textSecondary,
  lineHeight: tokens.typography.lineHeight.normal,
} as const;

const labelStyle = {
  display: "block",
  fontFamily: tokens.typography.fontFamily,
  fontSize: tokens.typography.size.label,
  fontWeight: tokens.typography.weight.bold,
  color: tokens.color.textPrimary,
} as const;

const twoColStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(220px, 100%), 1fr))",
  gap: tokens.space[4],
} as const;

const textareaStyle = {
  width: "100%",
  boxSizing: "border-box",
  padding: tokens.space[3],
  border: `1px solid ${tokens.color.borderDefault}`,
  borderRadius: tokens.radius.md,
  fontFamily: tokens.typography.fontFamily,
  fontSize: tokens.typography.size.input,
  color: tokens.color.textPrimary,
  resize: "vertical",
} as const;
