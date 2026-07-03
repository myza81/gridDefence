/**
 * Mirrors backend/app/modules/iam/schemas.py exactly. The frontend performs
 * no authoritative engineering logic (CLAUDE.md A12) — these types exist only
 * to describe the API contract that the backend already enforces.
 */

export type UserStatus = "active" | "suspended" | "deactivated";
export type RoleStatus = "active" | "retired";

export interface UserSummary {
  user_id: string;
  username: string;
  display_name: string;
  email: string | null;
  status: UserStatus;
}

export interface UserPage {
  items: UserSummary[];
  page: number;
  page_size: number;
  total: number;
}

export interface UserCreate {
  username: string;
  display_name: string;
  email?: string | null;
  password: string;
}

export interface RoleSummary {
  role_id: string;
  name: string;
  description: string | null;
  is_system_role: boolean;
  status: RoleStatus;
}

export interface RoleCreate {
  name: string;
  description?: string | null;
}

export interface PermissionSummary {
  permission_id: string;
  label: string;
  description: string | null;
  module_scope: string;
}

export interface PermissionCreate {
  permission_id: string;
  label: string;
  description?: string | null;
  module_scope: string;
}

export interface UserRoleSummary {
  role: RoleSummary;
  granted_at: string;
  permissions: string[];
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserSummary;
}
