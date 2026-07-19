import { apiClient } from "../../api/client";
import type {
  LoginRequest,
  LoginResponse,
  PermissionCreate,
  PermissionSummary,
  RoleCreate,
  RoleSummary,
  UserCreate,
  UserPage,
  UserRoleSummary,
  UserStatusChange,
  UserSummary,
} from "./types";

/** Endpoint shapes per docs/architecture/iam-module.md §12. */
export const iamApi = {
  login: (payload: LoginRequest) => apiClient.post<LoginResponse>("/api/v1/auth/login", payload),
  logout: () => apiClient.post<void>("/api/v1/auth/logout"),
  getCurrentUser: () => apiClient.get<UserSummary>("/api/v1/users/me"),

  listUsers: (page = 1, pageSize = 50) =>
    apiClient.get<UserPage>(`/api/v1/users?page=${page}&page_size=${pageSize}`),
  createUser: (payload: UserCreate) => apiClient.post<UserSummary>("/api/v1/users", payload),
  changeUserStatus: (userId: string, payload: UserStatusChange) =>
    apiClient.post<UserSummary>(`/api/v1/users/${userId}/status`, payload),

  listUserRoles: (userId: string) => apiClient.get<UserRoleSummary[]>(`/api/v1/users/${userId}/roles`),
  grantUserRole: (userId: string, roleId: string) =>
    apiClient.post<UserRoleSummary>(`/api/v1/users/${userId}/roles`, { role_id: roleId }),
  revokeUserRole: (userId: string, roleId: string) =>
    apiClient.delete<void>(`/api/v1/users/${userId}/roles/${roleId}`),

  listRoles: () => apiClient.get<RoleSummary[]>("/api/v1/roles"),
  createRole: (payload: RoleCreate) => apiClient.post<RoleSummary>("/api/v1/roles", payload),

  listRolePermissions: (roleId: string) =>
    apiClient.get<PermissionSummary[]>(`/api/v1/roles/${roleId}/permissions`),
  grantRolePermission: (roleId: string, permissionId: string) =>
    apiClient.post<PermissionSummary[]>(`/api/v1/roles/${roleId}/permissions`, {
      permission_id: permissionId,
    }),
  revokeRolePermission: (roleId: string, permissionId: string) =>
    apiClient.delete<void>(`/api/v1/roles/${roleId}/permissions/${permissionId}`),

  listPermissions: () => apiClient.get<PermissionSummary[]>("/api/v1/permissions"),
  registerPermission: (payload: PermissionCreate) =>
    apiClient.post<PermissionSummary>("/api/v1/permissions", payload),
};
