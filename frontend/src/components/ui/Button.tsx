import { forwardRef, useState } from "react";
import type { ButtonHTMLAttributes, CSSProperties, ReactNode } from "react";

import { tokens } from "../../theme/tokens";

type Variant = "primary" | "secondary";

interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  /** Visual role. `primary` is the strong blue action; `secondary` is outlined. */
  variant?: Variant;
  fullWidth?: boolean;
  /** Pending state — disables activation and exposes `aria-busy` to assistive tech. */
  loading?: boolean;
  leadingIcon?: ReactNode;
  children: ReactNode;
}

/**
 * Minimal, accessible button primitive built on the shared design tokens and
 * the existing inline-style architecture (no CSS variables, no stylesheet).
 * It exists because the login page has more than one button (primary submit +
 * secondary SSO) that would otherwise duplicate sizing, disabled handling, the
 * loading/`aria-busy` behaviour, and the keyboard focus ring.
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "primary",
    fullWidth = false,
    loading = false,
    leadingIcon,
    children,
    disabled,
    type = "button",
    style,
    onFocus,
    onBlur,
    ...rest
  },
  ref,
) {
  const [focused, setFocused] = useState(false);
  const isDisabled = disabled === true || loading;

  const palette: Record<Variant, CSSProperties> = {
    primary: {
      backgroundColor: tokens.color.actionPrimary,
      color: tokens.color.actionPrimaryText,
      border: `1px solid ${tokens.color.actionPrimary}`,
    },
    secondary: {
      backgroundColor: tokens.color.surfacePanel,
      color: tokens.color.textPrimary,
      border: `1px solid ${tokens.color.borderStrong}`,
    },
  };

  const composed: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: tokens.space[2],
    width: fullWidth ? "100%" : undefined,
    height: tokens.control.height,
    padding: `0 ${tokens.space[5]}`,
    borderRadius: tokens.radius.md,
    fontFamily: tokens.typography.fontFamily,
    fontSize: tokens.typography.size.button,
    fontWeight: tokens.typography.weight.semibold,
    cursor: isDisabled ? "not-allowed" : "pointer",
    opacity: isDisabled ? 0.6 : 1,
    outline: "none",
    boxShadow: focused ? tokens.focus.ring : "none",
    transition: `background-color ${tokens.transition.base}, box-shadow ${tokens.transition.base}`,
    ...palette[variant],
    ...style,
  };

  return (
    <button
      ref={ref}
      type={type}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      style={composed}
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
      {leadingIcon}
      {children}
    </button>
  );
});
