/**
 * Engineering Home (Phase C) view-model types.
 *
 * These describe the shape the Home workspace renders. They are intentionally
 * serialisable (icons are referenced by a string key, not a component) so the
 * mock source in `mockData.ts` can later be replaced by a TanStack Query
 * response with minimal change — the components consume these types, not the
 * data source.
 */

/** Icon keys resolved to SVGs by the presentation-only icon registry. */
export type HomeIconKey =
  | "registries"
  | "network"
  | "schemes"
  | "validation"
  | "reports"
  | "administration"
  | "import"
  | "register"
  | "equipment"
  | "create-scheme"
  | "draft"
  | "substation"
  | "transformer"
  | "publish"
  | "snapshot"
  | "approve";

/** Severity/tone for an engineering-attention item — text label always accompanies it (no colour-only meaning). */
export type AttentionTone = "critical" | "warning" | "info" | "ok";

export interface AttentionItem {
  id: string;
  tone: AttentionTone;
  label: string;
  detail?: string;
  /** Where reviewing this item leads (an existing route, or undefined if not yet available). */
  to?: string;
}

export interface ContinueWorkingItem {
  id: string;
  title: string;
  meta?: string;
  icon: HomeIconKey;
  to: string;
}

export interface QuickAction {
  id: string;
  label: string;
  icon: HomeIconKey;
  to: string;
  /** The single most common action is highlighted as primary. */
  primary?: boolean;
}

export interface EngineeringModule {
  id: string;
  title: string;
  description: string;
  icon: HomeIconKey;
  /** Undefined ⇒ module has no frontend route yet (rendered as "coming soon", not a dead link). */
  to?: string;
}

export interface ActivityItem {
  id: string;
  title: string;
  meta: string;
  icon: HomeIconKey;
}

export interface HomeData {
  attention: AttentionItem[];
  continueWorking: ContinueWorkingItem[];
  quickActions: QuickAction[];
  modules: EngineeringModule[];
  recentActivity: ActivityItem[];
}
