import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";

import { ApiError } from "../../../api/client";
import { useAuth } from "../AuthContext";
import { iamApi } from "../api";

function RegisterPermissionForm({ onRegistered }: { onRegistered: () => void }) {
  const [permissionId, setPermissionId] = useState("");
  const [label, setLabel] = useState("");
  const [moduleScope, setModuleScope] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  const registerMutation = useMutation({
    mutationFn: () =>
      iamApi.registerPermission({
        permission_id: permissionId,
        label,
        module_scope: moduleScope,
        description: description || null,
      }),
    onSuccess: () => {
      setPermissionId("");
      setLabel("");
      setModuleScope("");
      setDescription("");
      setError(null);
      onRegistered();
    },
    onError: (err: unknown) => setError(err instanceof ApiError ? err.message : "Registration failed"),
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    registerMutation.mutate();
  }

  return (
    <form onSubmit={handleSubmit}>
      <h3>Register permission</h3>
      <div>
        <label htmlFor="permission-id">Permission ID</label>
        <br />
        <input
          id="permission-id"
          value={permissionId}
          onChange={(e) => setPermissionId(e.target.value)}
          placeholder="module.resource.action"
          required
        />
      </div>
      <div>
        <label htmlFor="permission-label">Label</label>
        <br />
        <input id="permission-label" value={label} onChange={(e) => setLabel(e.target.value)} required />
      </div>
      <div>
        <label htmlFor="permission-module-scope">Module scope</label>
        <br />
        <input
          id="permission-module-scope"
          value={moduleScope}
          onChange={(e) => setModuleScope(e.target.value)}
          required
        />
      </div>
      <div>
        <label htmlFor="permission-description">Description</label>
        <br />
        <input
          id="permission-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={registerMutation.isPending}>
        Register permission
      </button>
    </form>
  );
}

export function PermissionsPage() {
  const { permissions: myPermissions } = useAuth();
  const canManage = myPermissions.has("iam.role.manage");
  const queryClient = useQueryClient();

  const permissionsQuery = useQuery({
    queryKey: ["iam", "permissions"],
    queryFn: iamApi.listPermissions,
  });

  return (
    <section>
      <h2>Permission catalog</h2>
      {permissionsQuery.isLoading && <p>Loading permissions...</p>}
      {permissionsQuery.isError && <p role="alert">Failed to load permissions.</p>}
      <ul>
        {(permissionsQuery.data ?? []).map((permission) => (
          <li key={permission.permission_id}>
            <strong>{permission.permission_id}</strong> — {permission.label} ({permission.module_scope})
          </li>
        ))}
      </ul>

      {canManage && (
        <RegisterPermissionForm
          onRegistered={() => void queryClient.invalidateQueries({ queryKey: ["iam", "permissions"] })}
        />
      )}
    </section>
  );
}
