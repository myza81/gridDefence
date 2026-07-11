import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";

import { ApiError } from "../../../api/client";
import { useAuth } from "../../iam/AuthContext";
import { sensitiveCustomerRegistryApi } from "../api";
import type { FacilitySectorSummary } from "../types";

/** Facility Sector reference-data administration (implementation spec
 * §8, §14 Increment 8). Gated by `sensitive_customer_registry.
 * manage_reference_data` — deliberately Administrator-only, distinct from
 * `.write` (facility mutation). `code` is never editable here — immutable
 * after creation (implementation spec §8); only `label`/`sort_order`/
 * `description`/`is_active` may be changed. No delete action exists —
 * deactivation is the only retirement path. */
export function FacilitySectorAdminPage() {
  const { permissions, isLoadingCurrentUser } = useAuth();
  const canManage = permissions.has("sensitive_customer_registry.manage_reference_data");
  const queryClient = useQueryClient();

  const sectorsQuery = useQuery({
    queryKey: ["sensitive-customer-registry", "facility-sectors"],
    queryFn: sensitiveCustomerRegistryApi.listFacilitySectors,
  });

  const invalidate = () =>
    void queryClient.invalidateQueries({
      queryKey: ["sensitive-customer-registry", "facility-sectors"],
    });

  const [code, setCode] = useState("");
  const [label, setLabel] = useState("");
  const [sortOrder, setSortOrder] = useState("0");
  const [createError, setCreateError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      sensitiveCustomerRegistryApi.createFacilitySector({
        code,
        label,
        sort_order: Number(sortOrder),
      }),
    onSuccess: () => {
      setCreateError(null);
      setCode("");
      setLabel("");
      setSortOrder("0");
      invalidate();
    },
    onError: (err: unknown) =>
      setCreateError(err instanceof ApiError ? err.message : "Failed to create facility sector."),
  });

  function handleCreateSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    createMutation.mutate();
  }

  const toggleActiveMutation = useMutation({
    mutationFn: (sector: FacilitySectorSummary) =>
      sensitiveCustomerRegistryApi.updateFacilitySector(sector.id, {
        is_active: !sector.is_active,
      }),
    onSuccess: invalidate,
  });

  if (!isLoadingCurrentUser && !canManage) {
    return (
      <section>
        <h2>Facility Sector Administration</h2>
        <p>You do not have permission to manage facility sector reference data.</p>
      </section>
    );
  }

  return (
    <section>
      <h2>Facility Sector Administration</h2>
      <p>
        Module-owned reference data (implementation spec §8) — a new sector can be added, or an
        existing one relabeled or retired, without a code deployment.
      </p>

      <table>
        <thead>
          <tr>
            <th>Code</th>
            <th>Label</th>
            <th>Sort Order</th>
            <th>Active</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {sectorsQuery.data?.map((sector) => (
            <tr key={sector.id}>
              <td>{sector.code}</td>
              <td>{sector.label}</td>
              <td>{sector.sort_order}</td>
              <td>{sector.is_active ? "Yes" : "No"}</td>
              <td>
                <button
                  type="button"
                  onClick={() => toggleActiveMutation.mutate(sector)}
                  disabled={toggleActiveMutation.isPending}
                >
                  {sector.is_active ? "Deactivate" : "Activate"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Add Facility Sector</h3>
      <form onSubmit={handleCreateSubmit}>
        <div style={{ marginBottom: "0.5rem" }}>
          <label htmlFor="new-sector-code">Code (immutable after creation)</label>
          <br />
          <input id="new-sector-code" value={code} onChange={(e) => setCode(e.target.value)} required />
        </div>
        <div style={{ marginBottom: "0.5rem" }}>
          <label htmlFor="new-sector-label">Label</label>
          <br />
          <input
            id="new-sector-label"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            required
          />
        </div>
        <div style={{ marginBottom: "0.5rem" }}>
          <label htmlFor="new-sector-sort-order">Sort Order</label>
          <br />
          <input
            id="new-sector-sort-order"
            type="number"
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value)}
          />
        </div>
        {createError && <p role="alert">{createError}</p>}
        <button type="submit" disabled={createMutation.isPending}>
          Add Sector
        </button>
      </form>
    </section>
  );
}
