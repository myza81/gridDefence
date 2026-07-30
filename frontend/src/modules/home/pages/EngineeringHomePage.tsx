import type { CSSProperties } from "react";

import { tokens } from "../../../theme/tokens";
import { useAuth } from "../../iam/AuthContext";
import { AttentionCard } from "../components/AttentionCard";
import { ContinueWorkingCard } from "../components/ContinueWorkingCard";
import { ModuleCard } from "../components/ModuleCard";
import { QuickActionCard } from "../components/QuickActionCard";
import { RecentActivityCard } from "../components/RecentActivityCard";
import { SectionHeader } from "../components/SectionHeader";
import { WelcomePanel } from "../components/WelcomePanel";
import { useHomeData } from "../mockData";

/** Responsive grid that reflows from multi-column (desktop) to single (mobile)
 *  without media queries — inline-style friendly, no horizontal overflow. */
function autoGrid(minColPx: number): CSSProperties {
  return {
    display: "grid",
    gap: tokens.space[4],
    gridTemplateColumns: `repeat(auto-fit, minmax(min(${minColPx}px, 100%), 1fr))`,
  };
}

/**
 * Engineering Home (Phase C) — the engineer's landing workspace at `/`.
 *
 * Answers "what should I work on today?" through awareness, current work,
 * quick actions and navigation — NOT analytics/BI (no charts/KPIs/gauges;
 * those belong to future module dashboards). Mock-driven via useHomeData();
 * swapping to TanStack Query later touches only that hook.
 */
export function EngineeringHomePage() {
  const { currentUser } = useAuth();
  const { attention, continueWorking, quickActions, modules, recentActivity } = useHomeData();
  const userName = currentUser?.display_name ?? currentUser?.username ?? "Engineer";

  return (
    <div
      style={{
        maxWidth: "1200px",
        margin: "0 auto",
        display: "flex",
        flexDirection: "column",
        gap: tokens.space[8],
        fontFamily: tokens.typography.fontFamily,
        color: tokens.color.textPrimary,
      }}
    >
      <WelcomePanel userName={userName} />

      <section>
        <SectionHeader title="Quick actions" description="Start a common engineering task." />
        <div style={autoGrid(220)}>
          {quickActions.map((action) => (
            <QuickActionCard key={action.id} action={action} />
          ))}
        </div>
      </section>

      <div style={autoGrid(320)}>
        <section>
          <SectionHeader title="Requires attention" description="Engineering items awaiting your review." />
          <AttentionCard items={attention} />
        </section>
        <section>
          <SectionHeader title="Continue working" description="Pick up where you left off." />
          <ContinueWorkingCard items={continueWorking} />
        </section>
      </div>

      <section>
        <SectionHeader title="Engineering modules" description="The primary GridDefence engineering domains." />
        <div style={autoGrid(260)}>
          {modules.map((module) => (
            <ModuleCard key={module.id} module={module} />
          ))}
        </div>
      </section>

      <section>
        <SectionHeader title="Recent engineering activity" />
        <RecentActivityCard items={recentActivity} />
      </section>
    </div>
  );
}
