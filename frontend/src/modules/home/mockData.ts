import type { HomeData } from "./types";

/**
 * Local mock content for the Engineering Home (Phase C).
 *
 * NO API calls and NO backend logic (design-only, per the Phase C brief). The
 * data is exposed through `useHomeData()` so that a later phase can replace the
 * body with a TanStack Query (`useQuery`) call returning the same `HomeData`
 * shape — every consuming component stays unchanged.
 *
 * Routes point at real, already-registered application routes where one exists;
 * items without a destination yet omit `to` and render as "not yet available"
 * rather than a dead link.
 */
const HOME_MOCK: HomeData = {
  attention: [
    {
      id: "att-validation",
      tone: "warning",
      label: "3 validation findings",
      detail: "Continuous Evaluation · awaiting engineering review",
      to: "/network-model/verification",
    },
    {
      id: "att-reviews",
      tone: "info",
      label: "2 pending reviews",
      detail: "Stage Setting Sets submitted for review",
      to: "/stage-setting-sets",
    },
    {
      id: "att-import",
      tone: "info",
      label: "Latest PSS/E import available",
      detail: "Peak snapshot 2026-06-15 ready to activate",
      to: "/psse-integration/current-status",
    },
    {
      id: "att-alerts",
      tone: "ok",
      label: "No active critical alerts",
      detail: "No blocking engineering issues in scope",
    },
  ],
  continueWorking: [
    { id: "cw-ufls", title: "UFLS draft", meta: "Edited 2h ago", icon: "draft", to: "/ufls/schemes" },
    { id: "cw-substation", title: "Substation Registry", meta: "4 edits today", icon: "substation", to: "/substations" },
    { id: "cw-equipment", title: "Equipment Registry", meta: "Viewed today", icon: "equipment", to: "/circuits" },
    { id: "cw-transformer", title: "Transformer review", meta: "In progress", icon: "transformer", to: "/transformers" },
  ],
  quickActions: [
    { id: "qa-import", label: "Import PSS/E", icon: "import", to: "/psse-integration/import", primary: true },
    { id: "qa-substation", label: "Register substation", icon: "register", to: "/substations/new" },
    { id: "qa-equipment", label: "Open Equipment Registry", icon: "equipment", to: "/circuits" },
    { id: "qa-scheme", label: "Create defence scheme", icon: "create-scheme", to: "/ufls/schemes" },
  ],
  modules: [
    {
      id: "mod-registries",
      title: "Registries",
      description: "Substation, equipment, relay and sensitive-customer engineering identity.",
      icon: "registries",
      to: "/substations",
    },
    {
      id: "mod-network",
      title: "Network & PSS/E",
      description: "Operational snapshots, topology and correlation against the registries.",
      icon: "network",
      to: "/network-model",
    },
    {
      id: "mod-schemes",
      title: "Defence Schemes",
      description: "UFLS, UVLS and EMLS scheme design, review and publication.",
      icon: "schemes",
      to: "/ufls/schemes",
    },
    {
      id: "mod-validation",
      title: "Continuous Validation",
      description: "Ongoing checks of published schemes against the current network.",
      icon: "validation",
      to: "/network-model/verification",
    },
    {
      id: "mod-reports",
      title: "Reports",
      description: "Engineering reports and export of authoritative records.",
      icon: "reports",
      // No frontend route yet — rendered as "coming soon", never a dead link.
    },
    {
      id: "mod-admin",
      title: "Administration",
      description: "Users, roles and permissions (Identity & Access Management).",
      icon: "administration",
      to: "/users",
    },
  ],
  recentActivity: [
    { id: "act-ufls", title: "Published UFLS version 12", meta: "Today · 09:12 · System Planning", icon: "publish" },
    { id: "act-snapshot", title: "Imported Peak snapshot", meta: "Today · 08:40 · PSS/E Integration", icon: "snapshot" },
    { id: "act-transformer", title: "Updated Transformer Registry", meta: "Yesterday · Equipment Registry", icon: "transformer" },
    { id: "act-approve", title: "Approved substation draft", meta: "Yesterday · Substation Registry", icon: "approve" },
  ],
};

/**
 * Read the Home workspace content. Currently returns local mock data
 * synchronously; a later phase swaps the body for a TanStack Query call
 * returning the same `HomeData` shape.
 */
export function useHomeData(): HomeData {
  return HOME_MOCK;
}
