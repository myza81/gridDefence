import { forwardRef, useId, useState } from "react";
import type { CSSProperties, ReactNode, SelectHTMLAttributes } from "react";

import { tokens } from "../../theme/tokens";

interface SelectFieldProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "id"> {
  /** Visible, associated label text. */
  label: string;
  id?: string;
  /** Supporting description, linked via aria-describedby. */
  hint?: string;
  /** Inline validation message. */
  error?: string;
  children: ReactNode;
}

/**
 * Labelled `<select>` matching TextField's look and accessibility (label/id
 * association, aria-invalid/aria-describedby, focus ring). Used for every
 * controlled reference-data selector in the registry forms so they share one
 * accessible pattern instead of hand-wiring each `<select>`.
 */
export const SelectField = forwardRef<HTMLSelectElement, SelectFieldProps>(function SelectField(
  { label, id, hint, error, children, style, onFocus, onBlur, ...rest },
  ref,
) {
  const generatedId = useId();
  const selectId = id ?? generatedId;
  const errorId = `${selectId}-error`;
  const hintId = `${selectId}-hint`;
  const [focused, setFocused] = useState(false);
  const invalid = typeof error === "string" && error.length > 0;

  const wrapperStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    height: tokens.control.height,
    padding: `0 ${tokens.control.paddingX}`,
    backgroundColor: tokens.color.surfacePanel,
    border: `1px solid ${invalid ? tokens.color.feedbackError : tokens.color.borderDefault}`,
    borderRadius: tokens.radius.md,
    boxShadow: focused ? tokens.focus.ring : "none",
    transition: `border-color ${tokens.transition.base}, box-shadow ${tokens.transition.base}`,
  };

  return (
    <div>
      <label
        htmlFor={selectId}
        style={{
          display: "block",
          marginBottom: tokens.space[2],
          fontFamily: tokens.typography.fontFamily,
          fontSize: tokens.typography.size.label,
          fontWeight: tokens.typography.weight.bold,
          color: tokens.color.textPrimary,
        }}
      >
        {label}
      </label>
      {hint != null && (
        <p id={hintId} style={{ margin: `0 0 ${tokens.space[2]}`, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.size.small, color: tokens.color.textSecondary }}>
          {hint}
        </p>
      )}
      <div style={wrapperStyle}>
        <select
          ref={ref}
          id={selectId}
          aria-invalid={invalid || undefined}
          aria-describedby={invalid ? errorId : hint != null ? hintId : undefined}
          style={{
            flex: 1,
            minWidth: 0,
            height: "100%",
            border: "none",
            outline: "none",
            background: "transparent",
            fontFamily: tokens.typography.fontFamily,
            fontSize: tokens.typography.size.input,
            color: tokens.color.textPrimary,
            ...style,
          }}
          onFocus={(e) => {
            setFocused(true);
            onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocused(false);
            onBlur?.(e);
          }}
          {...rest}
        >
          {children}
        </select>
      </div>
      {invalid && (
        <p id={errorId} style={{ margin: `${tokens.space[2]} 0 0`, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.size.small, color: tokens.color.feedbackError }}>
          {error}
        </p>
      )}
    </div>
  );
});
