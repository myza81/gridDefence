import type { ReactNode } from "react";

import { tokens } from "../../theme/tokens";
import { Button } from "./Button";

interface ErrorStateProps {
  /** Short, honest heading (e.g. "Couldn't load substations"). */
  title: string;
  /** The backend's own message where available — never a raw stack trace. */
  message?: ReactNode;
  onRetry?: () => void;
}

/**
 * Page/section-level failure surface (Error handling §13). Shows the backend's
 * own words when supplied (never "Something went wrong"), with an optional
 * safe retry for idempotent reads. `role="alert"` announces it to assistive tech.
 */
export function ErrorState({ title, message, onRetry }: ErrorStateProps) {
  return (
    <div
      role="alert"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: tokens.space[3],
        padding: tokens.space[5],
        border: `1px solid ${tokens.color.feedbackError}`,
        borderRadius: tokens.radius.lg,
        background: "#FCEEEC",
        fontFamily: tokens.typography.fontFamily,
      }}
    >
      <p style={{ margin: 0, fontWeight: tokens.typography.weight.semibold, color: tokens.color.textPrimary }}>{title}</p>
      {message != null && (
        <p style={{ margin: 0, fontSize: tokens.typography.size.small, color: tokens.color.textSecondary, lineHeight: tokens.typography.lineHeight.normal }}>
          {message}
        </p>
      )}
      {onRetry && (
        <div>
          <Button variant="secondary" onClick={onRetry}>
            Try again
          </Button>
        </div>
      )}
    </div>
  );
}
