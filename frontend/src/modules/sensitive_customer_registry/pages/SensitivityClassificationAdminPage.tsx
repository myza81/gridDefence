import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";

import { ApiError } from "../../../api/client";
import { useAuth } from "../../iam/AuthContext";
import { sensitiveCustomerRegistryApi } from "../api";
import type { SensitivityClassificationSummary } from "../types";

/** Sensitivity Classification reference-data administration — mirrors
 * FacilitySectorAdminPage.tsx exactly (implementation spec §8, §14
 * Increment 8). `sort_order` is semantically meaningful here (lower means
 * higher sensitivity, module document §7.2) — displayed, not enforced
 * client-side. */
export function SensitivityClassificationAdminPage() {
  const { permissions, isLoadingCurrentUser } = useAuth();
  const canManage = permissions.has("sensitive_customer_registry.manage_reference_data");
  const queryClient = useQueryClient();

  const classificationsQuery = useQuery({
    queryKey: ["sensitive-customer-registry", "sensitivity-classifications"],
    queryFn: sensitiveCustomerRegistryApi.listSensitivityClassifications,
  });

  const invalidate = () =>
    void queryClient.invalidateQueries({
      queryKey: ["sensitive-customer-registry", "sensitivity-classifications"],
    });

  const [code, setCode] = useState("");
  const [label, setLabel] = useState("");
  const [sortOrder, setSortOrder] = useState("0");
  const [createError, setCreateError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      sensitiveCustomerRegistryApi.createSensitivityClassification({
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
      setCreateError(
        err instanceof ApiError ? err.message : "Failed to create sensitivity classification.",
      ),
  });

  function handleCreateSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    createMutation.mutate();
  }

  const toggleActiveMutation = useMutation({
    mutationFn: (classification: SensitivityClassificationSummary) =>
      sensitiveCustomerRegistryApi.updateSensitivityClassification(classification.id, {
        is_active: !classification.is_active,
      }),
    onSuccess: invalidate,
  });

  if (!isLoadingCurrentUser && !canManage) {
    return (
      <section>
        <h2>Sensitivity Classification Administration</h2>
        <p>You do not have permission to manage sensitivity classification reference data.</p>
      </section>
    );
  }

  return (
    <section>
      <h2>Sensitivity Classification Administration</h2>
      <p>
        Module-owned reference data (implementation spec §8) — an engineering-importance tier,
        lower sort order meaning higher sensitivity (module document §7.2). Never encodes
        blocking, warning, stage, approval, or override behaviour (EDR-008).
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
          {classificationsQuery.data?.map((classification) => (
            <tr key={classification.id}>
              <td>{classification.code}</td>
              <td>{classification.label}</td>
              <td>{classification.sort_order}</td>
              <td>{classification.is_active ? "Yes" : "No"}</td>
              <td>
                <button
                  type="button"
                  onClick={() => toggleActiveMutation.mutate(classification)}
                  disabled={toggleActiveMutation.isPending}
                >
                  {classification.is_active ? "Deactivate" : "Activate"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Add Sensitivity Classification</h3>
      <form onSubmit={handleCreateSubmit}>
        <div style={{ marginBottom: "0.5rem" }}>
          <label htmlFor="new-classification-code">Code (immutable after creation)</label>
          <br />
          <input
            id="new-classification-code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            required
          />
        </div>
        <div style={{ marginBottom: "0.5rem" }}>
          <label htmlFor="new-classification-label">Label</label>
          <br />
          <input
            id="new-classification-label"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            required
          />
        </div>
        <div style={{ marginBottom: "0.5rem" }}>
          <label htmlFor="new-classification-sort-order">Sort Order</label>
          <br />
          <input
            id="new-classification-sort-order"
            type="number"
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value)}
          />
        </div>
        {createError && <p role="alert">{createError}</p>}
        <button type="submit" disabled={createMutation.isPending}>
          Add Classification
        </button>
      </form>
    </section>
  );
}
