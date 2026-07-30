import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { AppShell } from "../components/layout/AppShell";
import { EngineeringHomePage } from "../modules/home/pages/EngineeringHomePage";
import { FunctionalityCandidatePage } from "../modules/automatic_load_shedding_functionality/pages/FunctionalityCandidatePage";
import { FunctionalityCreatePage } from "../modules/automatic_load_shedding_functionality/pages/FunctionalityCreatePage";
import { FunctionalityDetailPage } from "../modules/automatic_load_shedding_functionality/pages/FunctionalityDetailPage";
import { FunctionalityListPage } from "../modules/automatic_load_shedding_functionality/pages/FunctionalityListPage";
import { CircuitCreatePage } from "../modules/equipment_registry/pages/CircuitCreatePage";
import { CircuitDetailPage } from "../modules/equipment_registry/pages/CircuitDetailPage";
import { CircuitListPage } from "../modules/equipment_registry/pages/CircuitListPage";
import { TransformerCreatePage } from "../modules/equipment_registry/pages/TransformerCreatePage";
import { TransformerDetailPage } from "../modules/equipment_registry/pages/TransformerDetailPage";
import { TransformerListPage } from "../modules/equipment_registry/pages/TransformerListPage";
import { LoginPage } from "../modules/iam/pages/LoginPage";
import { PermissionsPage } from "../modules/iam/pages/PermissionsPage";
import { RolesPage } from "../modules/iam/pages/RolesPage";
import { UsersPage } from "../modules/iam/pages/UsersPage";
import { ProtectedRoute } from "../modules/iam/ProtectedRoute";
import { BayViewPage } from "../modules/network_model/pages/BayViewPage";
import { BoundaryPocketEvaluatorPage } from "../modules/network_model/pages/BoundaryPocketEvaluatorPage";
import { ConnectivityViewPage } from "../modules/network_model/pages/ConnectivityViewPage";
import { NetworkOverviewPage } from "../modules/network_model/pages/NetworkOverviewPage";
import { NetworkTraversalPage } from "../modules/network_model/pages/NetworkTraversalPage";
import { OperationalSnapshotVerificationPage } from "../modules/network_model/pages/OperationalSnapshotVerificationPage";
import { SubstationExplorerDetailPage } from "../modules/network_model/pages/SubstationExplorerDetailPage";
import { SubstationExplorerListPage } from "../modules/network_model/pages/SubstationExplorerListPage";
import { PsseBatchDetailPage } from "../modules/psse_integration/pages/PsseBatchDetailPage";
import { PsseCurrentStatusPage } from "../modules/psse_integration/pages/PsseCurrentStatusPage";
import { PsseEquipmentTopologyMapPage } from "../modules/psse_integration/pages/PsseEquipmentTopologyMapPage";
import { PsseImportHistoryPage } from "../modules/psse_integration/pages/PsseImportHistoryPage";
import { PsseImportUploadPage } from "../modules/psse_integration/pages/PsseImportUploadPage";
import { PsseOperationalContextInspectorPage } from "../modules/psse_integration/pages/PsseOperationalContextInspectorPage";
import { FacilityCreatePage } from "../modules/sensitive_customer_registry/pages/FacilityCreatePage";
import { FacilityDetailPage } from "../modules/sensitive_customer_registry/pages/FacilityDetailPage";
import { FacilityListPage } from "../modules/sensitive_customer_registry/pages/FacilityListPage";
import { FacilitySectorAdminPage } from "../modules/sensitive_customer_registry/pages/FacilitySectorAdminPage";
import { SensitivityClassificationAdminPage } from "../modules/sensitive_customer_registry/pages/SensitivityClassificationAdminPage";
import { StageSettingSetDetailPage } from "../modules/stage_setting_registry/pages/StageSettingSetDetailPage";
import { StageSettingSetListPage } from "../modules/stage_setting_registry/pages/StageSettingSetListPage";
import { SubstationCreatePage } from "../modules/substation_registry/pages/SubstationCreatePage";
import { SubstationDetailPage } from "../modules/substation_registry/pages/SubstationDetailPage";
import { SubstationListPage } from "../modules/substation_registry/pages/SubstationListPage";
import { UflsDraftEditorPage } from "../modules/ufls/pages/UflsDraftEditorPage";
import { UflsPublicationReviewPage } from "../modules/ufls/pages/UflsPublicationReviewPage";
import { UflsSchemeDetailPage } from "../modules/ufls/pages/UflsSchemeDetailPage";
import { UflsSchemeListPage } from "../modules/ufls/pages/UflsSchemeListPage";

/**
 * Root route table. Each business module registers its own routes here once
 * it exists (docs/architecture/implementation-plan.md §3). IAM (Phase 1)
 * adds /login plus its protected management pages; Substation Registry
 * (Phase 2) adds /substations; Equipment Registry (Phase 3) adds /circuits;
 * Transformer Registry (Phase 3.5) adds /transformers; PSS/E Integration
 * (Phase 4) adds /psse-integration/*; the static Network Model (Phase 5B)
 * adds /network-model/* — an engineering navigation interface, not a
 * topology visualization (network-model-module.md §19). The root route `/`
 * is the authenticated Engineering Home (Phase C), inside AppShell +
 * ProtectedRoute (it superseded the public Phase 0 status landing).
 */
const router = createBrowserRouter([
  {
    // The approved login mockup is a full-bleed page with its own branding —
    // it is deliberately rendered outside AppShell (no app header/nav chrome).
    path: "/login",
    element: <LoginPage />,
  },
  {
    // The root route IS the Engineering Home — the authenticated landing
    // workspace (Phase C), not a top-level /dashboard.
    path: "/",
    element: (
      <AppShell>
        <ProtectedRoute>
          <EngineeringHomePage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/users",
    element: (
      <AppShell>
        <ProtectedRoute>
          <UsersPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/roles",
    element: (
      <AppShell>
        <ProtectedRoute>
          <RolesPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/permissions",
    element: (
      <AppShell>
        <ProtectedRoute>
          <PermissionsPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/substations",
    element: (
      <AppShell>
        <ProtectedRoute>
          <SubstationListPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/substations/new",
    element: (
      <AppShell>
        <ProtectedRoute>
          <SubstationCreatePage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/substations/:substationId",
    element: (
      <AppShell>
        <ProtectedRoute>
          <SubstationDetailPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/circuits",
    element: (
      <AppShell>
        <ProtectedRoute>
          <CircuitListPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/circuits/new",
    element: (
      <AppShell>
        <ProtectedRoute>
          <CircuitCreatePage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/circuits/:circuitId",
    element: (
      <AppShell>
        <ProtectedRoute>
          <CircuitDetailPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/automatic-load-shedding-functionality",
    element: (
      <AppShell>
        <ProtectedRoute>
          <FunctionalityListPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/automatic-load-shedding-functionality/candidates",
    element: (
      <AppShell>
        <ProtectedRoute>
          <FunctionalityCandidatePage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/automatic-load-shedding-functionality/new",
    element: (
      <AppShell>
        <ProtectedRoute>
          <FunctionalityCreatePage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/automatic-load-shedding-functionality/:functionalityId",
    element: (
      <AppShell>
        <ProtectedRoute>
          <FunctionalityDetailPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/sensitive-customer-registry",
    element: (
      <AppShell>
        <ProtectedRoute>
          <FacilityListPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/sensitive-customer-registry/new",
    element: (
      <AppShell>
        <ProtectedRoute>
          <FacilityCreatePage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/sensitive-customer-registry/reference-data/facility-sectors",
    element: (
      <AppShell>
        <ProtectedRoute>
          <FacilitySectorAdminPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/sensitive-customer-registry/reference-data/sensitivity-classifications",
    element: (
      <AppShell>
        <ProtectedRoute>
          <SensitivityClassificationAdminPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/sensitive-customer-registry/:facilityId",
    element: (
      <AppShell>
        <ProtectedRoute>
          <FacilityDetailPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/transformers",
    element: (
      <AppShell>
        <ProtectedRoute>
          <TransformerListPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/transformers/new",
    element: (
      <AppShell>
        <ProtectedRoute>
          <TransformerCreatePage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/transformers/:transformerId",
    element: (
      <AppShell>
        <ProtectedRoute>
          <TransformerDetailPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/psse-integration/import",
    element: (
      <AppShell>
        <ProtectedRoute>
          <PsseImportUploadPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/psse-integration/import/inspect",
    element: (
      <AppShell>
        <ProtectedRoute>
          <PsseOperationalContextInspectorPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/psse-integration/history",
    element: (
      <AppShell>
        <ProtectedRoute>
          <PsseImportHistoryPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/psse-integration/batches/:batchId",
    element: (
      <AppShell>
        <ProtectedRoute>
          <PsseBatchDetailPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/psse-integration/current-status",
    element: (
      <AppShell>
        <ProtectedRoute>
          <PsseCurrentStatusPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/psse-integration/topology-versions/:topologyVersionId/equipment-map",
    element: (
      <AppShell>
        <ProtectedRoute>
          <PsseEquipmentTopologyMapPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/network-model",
    element: (
      <AppShell>
        <ProtectedRoute>
          <NetworkOverviewPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/network-model/substations",
    element: (
      <AppShell>
        <ProtectedRoute>
          <SubstationExplorerListPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/network-model/substations/:substationId",
    element: (
      <AppShell>
        <ProtectedRoute>
          <SubstationExplorerDetailPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/network-model/substations/:substationId/bays",
    element: (
      <AppShell>
        <ProtectedRoute>
          <BayViewPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/network-model/substations/:substationId/connectivity",
    element: (
      <AppShell>
        <ProtectedRoute>
          <ConnectivityViewPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/network-model/traversal",
    element: (
      <AppShell>
        <ProtectedRoute>
          <NetworkTraversalPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/network-model/verification",
    element: (
      <AppShell>
        <ProtectedRoute>
          <OperationalSnapshotVerificationPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    // Foundation Hardening Sprint A.1 — diagnostic tool only, per
    // docs/architecture/boundary-pocket-architecture.md. Not the future
    // Scheme Engineering Workspace's Pocket Builder.
    path: "/network-model/boundary-pocket-evaluator",
    element: (
      <AppShell>
        <ProtectedRoute>
          <BoundaryPocketEvaluatorPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/stage-setting-sets",
    element: (
      <AppShell>
        <ProtectedRoute>
          <StageSettingSetListPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/stage-setting-sets/:stageSettingSetId",
    element: (
      <AppShell>
        <ProtectedRoute>
          <StageSettingSetDetailPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/ufls/schemes",
    element: (
      <AppShell>
        <ProtectedRoute>
          <UflsSchemeListPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/ufls/schemes/:schemeId",
    element: (
      <AppShell>
        <ProtectedRoute>
          <UflsSchemeDetailPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/ufls/versions/:versionId",
    element: (
      <AppShell>
        <ProtectedRoute>
          <UflsDraftEditorPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/ufls/versions/:versionId/publication-review",
    element: (
      <AppShell>
        <ProtectedRoute>
          <UflsPublicationReviewPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
