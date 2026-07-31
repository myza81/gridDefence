import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { Card } from "../../../components/ui/Card";
import { PageHeader } from "../../../components/ui/PageHeader";
import { useReferenceData } from "../../../reference_data/useReferenceData";
import { SubstationForm } from "../components/SubstationForm";
import { useCreateSubstationMutation } from "../hooks";
import type { SubstationCreate, SubstationUpdate } from "../types";

/**
 * Register a new Substation. Uses the shared, grouped SubstationForm and the
 * module's create mutation (which invalidates the registry list on success),
 * then navigates to the new record's detail workspace.
 */
export function SubstationCreatePage() {
  const navigate = useNavigate();
  const referenceData = useReferenceData();
  const [error, setError] = useState<string | null>(null);

  const createMutation = useCreateSubstationMutation();

  function handleSubmit(payload: SubstationCreate | SubstationUpdate): void {
    setError(null);
    createMutation.mutate(payload as SubstationCreate, {
      onSuccess: (detail) => navigate(`/substations/${detail.substation_id}`, { replace: true }),
      onError: (err: unknown) => setError(err instanceof ApiError ? err.message : "Failed to create substation."),
    });
  }

  return (
    <div style={{ maxWidth: "820px", margin: "0 auto" }}>
      <PageHeader
        title="Register substation"
        description="Add a new transmission substation to the authoritative registry. Identity and classification are validated against Core Platform reference data before the record is created."
      />
      <Card padding="24px">
        <SubstationForm
          mode="create"
          referenceData={referenceData}
          submitting={createMutation.isPending}
          error={error}
          onSubmit={handleSubmit}
          onCancel={() => navigate("/substations")}
        />
      </Card>
    </div>
  );
}
