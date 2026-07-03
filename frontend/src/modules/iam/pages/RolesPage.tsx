import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";

import { ApiError } from "../../../api/client";
import { useAuth } from "../AuthContext";
import { iamApi } from "../api";
import type { RoleSummary } from "../types";

function RolePermissionsPanel({ role }: { role: RoleSummary }) {
  const queryClient = useQueryClient();
  const { permissions: myPermissions } = useAuth();
  const canManage = myPermissions.has("iam.role.manage");

  const rolePermissionsQuery = useQuery({
    queryKey: ["iam", "rolePermissions", role.role_id],
    queryFn: () => iamApi.listRolePermissions(role.role_id),
  });

  const catalogQuery = useQuery({
    queryKey: ["iam", "permissions"],
    queryFn: iamApi.listPermissions,
  });

  const [selectedPermissionId, setSelectedPermissionId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const grantMutation = useMutation({
    mutationFn: (permissionId: string) => iamApi.grantRolePermission(role.role_id, permissionId),
    onSuccess: () => {
      setError(null);
      setSelectedPermissionId("");
      void queryClient.invalidateQueries({ queryKey: ["iam", "rolePermissions", role.role_id] });
    },
    onError: (err: unknown) => setError(err instanceof ApiError ? err.message : "Grant failed"),
  });

  const revokeMutation = useMutation({
    mutationFn: (permissionId: string) => iamApi.revokeRolePermission(role.role_id, permissionId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["iam", "rolePermissions", role.role_id] });
    },
  });

  const grantedIds = new Set((rolePermissionsQuery.data ?? []).map((p) => p.permission_id));
  const available = (catalogQuery.data ?? []).filter((p) => !grantedIds.has(p.permission_id));

  return (
    <div style={{ paddingLeft: "1rem", borderLeft: "2px solid #e2e2e2" }}>
      <h4>Permissions for {role.name}</h4>
      {rolePermissionsQuery.isLoading && <p>Loading permissions...</p>}
      <ul>
        {(rolePermissionsQuery.data ?? []).map((permission) => (
          <li key={permission.permission_id}>
            {permission.permission_id} — {permission.label}
            {canManage && (
              <button
                type="button"
                onClick={() => revokeMutation.mutate(permission.permission_id)}
                disabled={revokeMutation.isPending}
                style={{ marginLeft: "0.5rem" }}
              >
                Revoke
              </button>
            )}
          </li>
        ))}
        {rolePermissionsQuery.data?.length === 0 && <li>No permissions granted.</li>}
      </ul>

      {canManage && (
        <div>
          <select
            aria-label={`Grant permission to ${role.name}`}
            value={selectedPermissionId}
            onChange={(e) => setSelectedPermissionId(e.target.value)}
          >
            <option value="">Select a permission...</option>
            {available.map((permission) => (
              <option key={permission.permission_id} value={permission.permission_id}>
                {permission.permission_id} — {permission.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={!selectedPermissionId || grantMutation.isPending}
            onClick={() => grantMutation.mutate(selectedPermissionId)}
          >
            Grant
          </button>
          {error && <p role="alert">{error}</p>}
        </div>
      )}
    </div>
  );
}

function CreateRoleForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () => iamApi.createRole({ name, description: description || null }),
    onSuccess: () => {
      setName("");
      setDescription("");
      setError(null);
      onCreated();
    },
    onError: (err: unknown) => setError(err instanceof ApiError ? err.message : "Create failed"),
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    createMutation.mutate();
  }

  return (
    <form onSubmit={handleSubmit}>
      <h3>Create role</h3>
      <div>
        <label htmlFor="role-name">Name</label>
        <br />
        <input id="role-name" value={name} onChange={(e) => setName(e.target.value)} required />
      </div>
      <div>
        <label htmlFor="role-description">Description</label>
        <br />
        <input
          id="role-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={createMutation.isPending}>
        Create role
      </button>
    </form>
  );
}

export function RolesPage() {
  const { permissions: myPermissions } = useAuth();
  const canManage = myPermissions.has("iam.role.manage");
  const queryClient = useQueryClient();
  const [expandedRoleId, setExpandedRoleId] = useState<string | null>(null);

  const rolesQuery = useQuery({
    queryKey: ["iam", "roles"],
    queryFn: iamApi.listRoles,
  });

  return (
    <section>
      <h2>Roles</h2>
      {rolesQuery.isLoading && <p>Loading roles...</p>}
      {rolesQuery.isError && <p role="alert">Failed to load roles.</p>}
      <ul>
        {(rolesQuery.data ?? []).map((role) => (
          <li key={role.role_id}>
            <button
              type="button"
              onClick={() => setExpandedRoleId(expandedRoleId === role.role_id ? null : role.role_id)}
            >
              {role.name} ({role.status}) {role.is_system_role ? "[system]" : ""}
            </button>
            {expandedRoleId === role.role_id && <RolePermissionsPanel role={role} />}
          </li>
        ))}
      </ul>

      {canManage && (
        <CreateRoleForm
          onCreated={() => void queryClient.invalidateQueries({ queryKey: ["iam", "roles"] })}
        />
      )}
    </section>
  );
}
