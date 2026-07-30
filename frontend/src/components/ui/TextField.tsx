import { forwardRef, useId, useState } from "react";
import type { CSSProperties, InputHTMLAttributes, ReactNode } from "react";

import { tokens } from "../../theme/tokens";

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  /** Visible, associated label text (never placeholder-only). */
  label: string;
  id?: string;
  /** Decorative leading glyph (e.g. person / lock) — hidden from assistive tech. */
  leadingIcon?: ReactNode;
  /** Trailing interactive slot (e.g. the password show/hide toggle). */
  trailing?: ReactNode;
  /** Inline validation message, linked to the input via `aria-describedby`. */
  error?: string;
}

/**
 * Minimal, accessible labelled text input built on the shared design tokens and
 * the existing inline-style architecture. It exists because the login page has
 * two structurally identical fields (username, password) that would otherwise
 * duplicate the label/id association, the `aria-invalid`/`aria-describedby`
 * error linkage, the leading-icon layout, and the keyboard focus ring.
 */
export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, id, leadingIcon, trailing, error, style, onFocus, onBlur, ...rest },
  ref,
) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const errorId = `${inputId}-error`;
  const [focused, setFocused] = useState(false);
  const invalid = typeof error === "string" && error.length > 0;

  const wrapperStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: tokens.space[2],
    height: tokens.control.height,
    padding: `0 ${tokens.control.paddingX}`,
    backgroundColor: tokens.color.surfacePanel,
    border: `1px solid ${invalid ? tokens.color.feedbackError : tokens.color.borderDefault}`,
    borderRadius: tokens.radius.md,
    boxShadow: focused ? tokens.focus.ring : "none",
    transition: `border-color ${tokens.transition.base}, box-shadow ${tokens.transition.base}`,
  };

  const inputStyle: CSSProperties = {
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
  };

  return (
    <div>
      <label
        htmlFor={inputId}
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
      <div style={wrapperStyle}>
        {leadingIcon != null && (
          <span aria-hidden="true" style={{ display: "inline-flex", color: tokens.color.fieldIcon }}>
            {leadingIcon}
          </span>
        )}
        <input
          ref={ref}
          id={inputId}
          aria-invalid={invalid || undefined}
          aria-describedby={invalid ? errorId : undefined}
          style={inputStyle}
          onFocus={(e) => {
            setFocused(true);
            onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocused(false);
            onBlur?.(e);
          }}
          {...rest}
        />
        {trailing}
      </div>
      {invalid && (
        <p
          id={errorId}
          style={{
            margin: `${tokens.space[2]} 0 0`,
            fontFamily: tokens.typography.fontFamily,
            fontSize: tokens.typography.size.small,
            color: tokens.color.feedbackError,
          }}
        >
          {error}
        </p>
      )}
    </div>
  );
});
