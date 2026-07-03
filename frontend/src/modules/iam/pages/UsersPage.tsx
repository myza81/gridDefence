import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";

import { ApiError } from "../../../api/client";
import { useAuth } from "../AuthContext";
import { iamApi } from "../api";
import type { UserSummary } from "../types";

function UserRolesPanel({ user }: { user: UserSummary }) {
  const queryClient = useQueryClient();
  const { permissions: myPermissions } = useAuth();
  const canManage = myPermissions.has("iam.user.manage");

  const userRolesQuery = useQuery({
    queryKey: ["iam", "userRoles", user.user_id],
    queryFn: () => iamApi.listUserRoles(user.user_id),
  });

  const rolesQuery = useQuery({
    queryKey: ["iam", "roles"],
    queryFn: iamApi.listRoles,
  });

  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const grantMutation = useMutation({
    mutationFn: (roleId: string) => iamApi.grantUserRole(user.user_id, roleId),
    onSuccess: () => {
      setError(null);
      setSelectedRoleId("");
      void queryClient.invalidateQueries({ queryKey: ["iam", "userRoles", user.user_id] });
    },
    onError: (err: unknown) => setError(err instanceof ApiError ? err.message : "Grant failed"),
  });

  const revokeMutation = useMutation({
    mutationFn: (roleId: string) => iamApi.revokeUserRole(user.user_id, roleId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["iam", "userRoles", user.user_id] });
    },
  });

  const assignedIds = new Set((userRolesQuery.data ?? []).map((ur) => ur.role.role_id));
  const available = (rolesQuery.data ?? []).filter(
    (r) => !assignedIds.has(r.role_id) && r.status === "active",
  );

  return (
    <div style={{ paddingLeft: "1rem", borderLeft: "2px solid #e2e2e2" }}>
      <h4>Roles for {user.username}</h4>
      {userRolesQuery.isLoading && <p>Loading roles...</p>}
      <ul>
        {(userRolesQuery.data ?? []).map((userRole) => (
          <li key={userRole.role.role_id}>
            {userRole.role.name}
            {canManage && (
              <button
                type="button"
                onClick={() => revokeMutation.mutate(userRole.role.role_id)}
                disabled={revokeMutation.isPending}
                style={{ marginLeft: "0.5rem" }}
              >
                Revoke
              </button>
            )}
          </li>
        ))}
        {userRolesQuery.data?.length === 0 && <li>No roles assigned.</li>}
      </ul>

      {canManage && (
        <div>
          <select
            aria-label={`Grant role to ${user.username}`}
            value={selectedRoleId}
            onChange={(e) => setSelectedRoleId(e.target.value)}
          >
            <option value="">Select a role...</option>
            {available.map((role) => (
              <option key={role.role_id} value={role.role_id}>
                {role.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={!selectedRoleId || grantMutation.isPending}
            onClick={() => grantMutation.mutate(selectedRoleId)}
          >
            Grant
          </button>
          {error && <p role="alert">{error}</p>}
        </div>
      )}
    </div>
  );
}

function CreateUserForm({ onCreated }: { onCreated: () => void }) {
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      iamApi.createUser({
        username,
        display_name: displayName,
        email: email || null,
        password,
      }),
    onSuccess: () => {
      setUsername("");
      setDisplayName("");
      setEmail("");
      setPassword("");
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
      <h3>Create user</h3>
      <div>
        <label htmlFor="user-username">Username</label>
        <br />
        <input
          id="user-username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          minLength={3}
        />
      </div>
      <div>
        <label htmlFor="user-display-name">Display name</label>
        <br />
        <input
          id="user-display-name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          required
        />
      </div>
      <div>
        <label htmlFor="user-email">Email</label>
        <br />
        <input id="user-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      </div>
      <div>
        <label htmlFor="user-password">Password</label>
        <br />
        <input
          id="user-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
        />
      </div>
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={createMutation.isPending}>
        Create user
      </button>
    </form>
  );
}

export function UsersPage() {
  const { permissions: myPermissions } = useAuth();
  const canManage = myPermissions.has("iam.user.manage");
  const queryClient = useQueryClient();
  const [expandedUserId, setExpandedUserId] = useState<string | null>(null);

  const usersQuery = useQuery({
    queryKey: ["iam", "users"],
    queryFn: () => iamApi.listUsers(),
    enabled: canManage,
  });

  if (!canManage) {
    return (
      <section>
        <h2>Users</h2>
        <p>You do not have permission to manage users.</p>
      </section>
    );
  }

  return (
    <section>
      <h2>Users</h2>
      {usersQuery.isLoading && <p>Loading users...</p>}
      {usersQuery.isError && <p role="alert">Failed to load users.</p>}
      <ul>
        {(usersQuery.data?.items ?? []).map((user) => (
          <li key={user.user_id}>
            <button
              type="button"
              onClick={() => setExpandedUserId(expandedUserId === user.user_id ? null : user.user_id)}
            >
              {user.username} ({user.status})
            </button>
            {expandedUserId === user.user_id && <UserRolesPanel user={user} />}
          </li>
        ))}
      </ul>

      <CreateUserForm
        onCreated={() => void queryClient.invalidateQueries({ queryKey: ["iam", "users"] })}
      />
    </section>
  );
}
