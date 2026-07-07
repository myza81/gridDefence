import type { ReactNode } from "react";
import { useState } from "react";

export interface DataInspectorTab {
  key: string;
  label: string;
  content: ReactNode;
}

interface DataInspectorProps {
  title: string;
  tabs: DataInspectorTab[];
}

/**
 * Generic tab-switching shell (Operational Context Inspector,
 * psse-integration-module.md §8.9e) — has no knowledge of PSS/E, or of
 * tabular data at all. Each tab's `content` is fully caller-supplied,
 * which is what makes this reusable for future, non-tabular inspection
 * UIs (e.g. a future spatial/graphical view under EDR-006), not just this
 * phase's data tables.
 */
export function DataInspector({ title, tabs }: DataInspectorProps) {
  const [activeTab, setActiveTab] = useState(tabs[0]?.key);

  const active = tabs.find((tab) => tab.key === activeTab) ?? tabs[0];

  return (
    <section>
      <h2>{title}</h2>

      <div role="tablist" style={{ display: "flex", gap: "0.5rem", borderBottom: "1px solid #ccc", marginBottom: "1rem" }}>
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={tab.key === active?.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              padding: "0.5rem 1rem",
              border: "none",
              borderBottom: tab.key === active?.key ? "2px solid #0969da" : "2px solid transparent",
              background: "none",
              fontWeight: tab.key === active?.key ? "bold" : "normal",
              cursor: "pointer",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {active && (
        <div role="tabpanel" aria-label={active.label}>
          {active.content}
        </div>
      )}
    </section>
  );
}
