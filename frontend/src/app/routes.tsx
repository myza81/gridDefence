import type { RouteObject } from "react-router-dom";

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
import { PermissionsPage } from "../modules/iam/pages/PermissionsPage";
import { RolesPage } from "../modules/iam/pages/RolesPage";
import { UsersPage } from "../modules/iam/pages/UsersPage";
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
 * Every route rendered inside Application Shell V2 (the authenticated layout in
 * ./router.tsx). Each business module registers its routes here as it lands;
 * the module's navigation entry lives alongside in ./navigation.ts. The root
 * route `/` is the Engineering Home (Phase C).
 *
 * Detail/action routes (`/…/new`, `/…/:id`, verification/diagnostic tools) are
 * intentionally NOT navigation entry points (Route inventory §13); the sidebar
 * links only to stable module entries, and these are reached from within them.
 */
export const authenticatedRoutes: RouteObject[] = [
  { path: "/", element: <EngineeringHomePage /> },

  { path: "/users", element: <UsersPage /> },
  { path: "/roles", element: <RolesPage /> },
  { path: "/permissions", element: <PermissionsPage /> },

  { path: "/substations", element: <SubstationListPage /> },
  { path: "/substations/new", element: <SubstationCreatePage /> },
  { path: "/substations/:substationId", element: <SubstationDetailPage /> },

  { path: "/circuits", element: <CircuitListPage /> },
  { path: "/circuits/new", element: <CircuitCreatePage /> },
  { path: "/circuits/:circuitId", element: <CircuitDetailPage /> },

  { path: "/automatic-load-shedding-functionality", element: <FunctionalityListPage /> },
  { path: "/automatic-load-shedding-functionality/candidates", element: <FunctionalityCandidatePage /> },
  { path: "/automatic-load-shedding-functionality/new", element: <FunctionalityCreatePage /> },
  { path: "/automatic-load-shedding-functionality/:functionalityId", element: <FunctionalityDetailPage /> },

  { path: "/sensitive-customer-registry", element: <FacilityListPage /> },
  { path: "/sensitive-customer-registry/new", element: <FacilityCreatePage /> },
  { path: "/sensitive-customer-registry/reference-data/facility-sectors", element: <FacilitySectorAdminPage /> },
  { path: "/sensitive-customer-registry/reference-data/sensitivity-classifications", element: <SensitivityClassificationAdminPage /> },
  { path: "/sensitive-customer-registry/:facilityId", element: <FacilityDetailPage /> },

  { path: "/transformers", element: <TransformerListPage /> },
  { path: "/transformers/new", element: <TransformerCreatePage /> },
  { path: "/transformers/:transformerId", element: <TransformerDetailPage /> },

  { path: "/psse-integration/import", element: <PsseImportUploadPage /> },
  { path: "/psse-integration/import/inspect", element: <PsseOperationalContextInspectorPage /> },
  { path: "/psse-integration/history", element: <PsseImportHistoryPage /> },
  { path: "/psse-integration/batches/:batchId", element: <PsseBatchDetailPage /> },
  { path: "/psse-integration/current-status", element: <PsseCurrentStatusPage /> },
  { path: "/psse-integration/topology-versions/:topologyVersionId/equipment-map", element: <PsseEquipmentTopologyMapPage /> },

  { path: "/network-model", element: <NetworkOverviewPage /> },
  { path: "/network-model/substations", element: <SubstationExplorerListPage /> },
  { path: "/network-model/substations/:substationId", element: <SubstationExplorerDetailPage /> },
  { path: "/network-model/substations/:substationId/bays", element: <BayViewPage /> },
  { path: "/network-model/substations/:substationId/connectivity", element: <ConnectivityViewPage /> },
  { path: "/network-model/traversal", element: <NetworkTraversalPage /> },
  { path: "/network-model/verification", element: <OperationalSnapshotVerificationPage /> },
  // Foundation Hardening Sprint A.1 — diagnostic tool only, per
  // docs/architecture/boundary-pocket-architecture.md. Not the future Scheme
  // Engineering Workspace's Pocket Builder; deliberately not in the sidebar.
  { path: "/network-model/boundary-pocket-evaluator", element: <BoundaryPocketEvaluatorPage /> },

  { path: "/stage-setting-sets", element: <StageSettingSetListPage /> },
  { path: "/stage-setting-sets/:stageSettingSetId", element: <StageSettingSetDetailPage /> },

  { path: "/ufls/schemes", element: <UflsSchemeListPage /> },
  { path: "/ufls/schemes/:schemeId", element: <UflsSchemeDetailPage /> },
  { path: "/ufls/versions/:versionId", element: <UflsDraftEditorPage /> },
  { path: "/ufls/versions/:versionId/publication-review", element: <UflsPublicationReviewPage /> },
];

/**
 * Static (non-parameterised) paths of every authenticated route — the set a
 * navigation entry is allowed to point at. The navigation-integrity test uses
 * this to guarantee no sidebar/breadcrumb entry becomes a dead link.
 */
export const authenticatedRoutePaths: string[] = authenticatedRoutes
  .map((route) => route.path)
  .filter((path): path is string => typeof path === "string" && !path.includes(":"));
