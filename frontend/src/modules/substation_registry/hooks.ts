/**
 * Module-owned TanStack Query hooks for the Substation Registry (Query and data
 * architecture §18). Pages consume these instead of calling `apiClient`
 * directly, so query keys and cache invalidation live in one place and cannot
 * drift between the list, create and detail workspaces.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { substationRegistryApi } from "./api";
import type { SubstationListFilters } from "./api";
import type { SubstationCreate, SubstationStatusChange, SubstationUpdate } from "./types";

/** Stable, hierarchical query keys — invalidating `all` refetches every registry view. */
export const substationKeys = {
  all: ["substations"] as const,
  lists: () => [...substationKeys.all, "list"] as const,
  list: (filters: SubstationListFilters) => [...substationKeys.lists(), filters] as const,
  details: () => [...substationKeys.all, "detail"] as const,
  detail: (id: string) => [...substationKeys.details(), id] as const,
  aliases: (id: string) => [...substationKeys.detail(id), "aliases"] as const,
  auditLog: (id: string) => [...substationKeys.detail(id), "audit-log"] as const,
};

export function useSubstationsQuery(filters: SubstationListFilters) {
  return useQuery({
    queryKey: substationKeys.list(filters),
    queryFn: () => substationRegistryApi.listSubstations(filters),
    placeholderData: (previous) => previous, // keep the last page visible during refetch (no flash)
  });
}

export function useSubstationQuery(substationId: string | undefined) {
  return useQuery({
    queryKey: substationKeys.detail(substationId ?? ""),
    queryFn: () => substationRegistryApi.getSubstation(substationId!),
    enabled: substationId !== undefined,
  });
}

export function useSubstationAliasesQuery(substationId: string | undefined) {
  return useQuery({
    queryKey: substationKeys.aliases(substationId ?? ""),
    queryFn: () => substationRegistryApi.listAliases(substationId!),
    enabled: substationId !== undefined,
  });
}

export function useSubstationAuditLogQuery(substationId: string | undefined) {
  return useQuery({
    queryKey: substationKeys.auditLog(substationId ?? ""),
    queryFn: () => substationRegistryApi.listAuditLog(substationId!),
    enabled: substationId !== undefined,
  });
}

export function useCreateSubstationMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SubstationCreate) => substationRegistryApi.createSubstation(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: substationKeys.lists() });
    },
  });
}

export function useUpdateSubstationMutation(substationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SubstationUpdate) => substationRegistryApi.updateSubstation(substationId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: substationKeys.detail(substationId) });
      void queryClient.invalidateQueries({ queryKey: substationKeys.lists() });
    },
  });
}

export function useChangeStatusMutation(substationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SubstationStatusChange) => substationRegistryApi.changeStatus(substationId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: substationKeys.detail(substationId) });
      void queryClient.invalidateQueries({ queryKey: substationKeys.lists() });
    },
  });
}
