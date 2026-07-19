import type { SchemeVersionLifecycleEvent } from "./types";

interface PublicationHistoryPanelProps {
  events: SchemeVersionLifecycleEvent[];
}

const ACTION_LABELS: Record<SchemeVersionLifecycleEvent["action"], string> = {
  draft_created: "Draft created",
  published: "Published",
  superseded: "Superseded",
  entered_in_error: "Entered in Error",
};

/**
 * Displays a Scheme Version's own lifecycle event history.
 *
 * Named "Publication History," not "Review History" or "Approval
 * History" — ADR-015/EDR-009 define no separate Under Review or
 * Approved state, so no separate review/approval history exists to
 * display. Review and approval are evidence-gathering activity that
 * happens *within* Draft (continuously-visible findings), not a
 * recorded state transition this panel would show.
 */
export function PublicationHistoryPanel({ events }: PublicationHistoryPanelProps) {
  if (events.length === 0) {
    return <p data-testid="publication-history-empty">No lifecycle history yet.</p>;
  }

  return (
    <ul data-testid="publication-history-panel">
      {events.map((event, index) => (
        <li key={`${event.action}-${event.occurredAt}-${index}`}>
          <strong>{ACTION_LABELS[event.action]}</strong> — {new Date(event.occurredAt).toLocaleString()}
          {event.actor ? ` by ${event.actor.displayName}` : ""}
          {event.reason ? ` (${event.reason})` : ""}
        </li>
      ))}
    </ul>
  );
}
