import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PublicationHistoryPanel } from "../../../src/components/scheme-platform/PublicationHistoryPanel";
import type { SchemeVersionLifecycleEvent } from "../../../src/components/scheme-platform/types";

describe("PublicationHistoryPanel", () => {
  it("shows an empty-state message when there is no history yet", () => {
    render(<PublicationHistoryPanel events={[]} />);
    expect(screen.getByTestId("publication-history-empty")).toHaveTextContent(
      "No lifecycle history yet.",
    );
  });

  it("renders each event with its action label, timestamp, and actor", () => {
    const events: SchemeVersionLifecycleEvent[] = [
      {
        action: "draft_created",
        occurredAt: "2026-07-01T00:00:00Z",
        actor: null,
        reason: null,
      },
      {
        action: "published",
        occurredAt: "2026-07-02T00:00:00Z",
        actor: { displayName: "Jane Engineer" },
        reason: null,
      },
    ];
    render(<PublicationHistoryPanel events={events} />);

    const panel = screen.getByTestId("publication-history-panel");
    expect(panel).toHaveTextContent("Draft created");
    expect(panel).toHaveTextContent("Published");
    expect(panel).toHaveTextContent("Jane Engineer");
  });

  it("renders the reason for an Entered in Error event", () => {
    const events: SchemeVersionLifecycleEvent[] = [
      {
        action: "entered_in_error",
        occurredAt: "2026-07-05T00:00:00Z",
        actor: { displayName: "Admin User" },
        reason: "Data entry mistake.",
      },
    ];
    render(<PublicationHistoryPanel events={events} />);
    expect(screen.getByTestId("publication-history-panel")).toHaveTextContent(
      "Data entry mistake.",
    );
  });

  it("never labels an event as Review or Approval", () => {
    const events: SchemeVersionLifecycleEvent[] = [
      { action: "published", occurredAt: "2026-07-02T00:00:00Z", actor: null, reason: null },
    ];
    render(<PublicationHistoryPanel events={events} />);
    const panel = screen.getByTestId("publication-history-panel");
    expect(panel.textContent).not.toContain("Review");
    expect(panel.textContent).not.toContain("Approval");
  });
});
