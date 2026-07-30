import type { CSSProperties, FormEvent, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import heroUrl from "../../../assets/brand/login-hero.webp";
import logoUrl from "../../../assets/brand/griddefence-logo.webp";
import { Button } from "../../../components/ui/Button";
import { TextField } from "../../../components/ui/TextField";
import { tokens } from "../../../theme/tokens";
import { ApiError } from "../../../api/client";
import { useAuth } from "../AuthContext";

/**
 * GridDefence login page — a faithful implementation of the approved mockup
 * (docs/design/mockups/login_page.png) over the existing, unchanged IAM
 * authentication wiring (AuthContext.login → POST /api/v1/auth/login).
 *
 * Intentional, contract-driven differences from the mockup (see completion
 * report): the credential field submits a **username** (the real backend
 * contract is username/password — LoginRequest), not an email; and SSO,
 * "Forgot password" and the legal links are presented faithfully but are
 * honestly not-yet-available, because the backend implements none of them and
 * this task must not invent a new authentication model.
 */

// --- decorative inline icons (hidden from assistive tech by their container) ---
function PersonIcon(): ReactNode {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20c0-3.6 3.1-6 7-6s7 2.4 7 6" strokeLinecap="round" />
    </svg>
  );
}
function LockIcon(): ReactNode {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="4" y="10" width="16" height="10" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" strokeLinecap="round" />
    </svg>
  );
}
function EyeIcon({ off }: { off: boolean }): ReactNode {
  return off ? (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M3 3l18 18" strokeLinecap="round" />
      <path d="M10.6 6.1A9.7 9.7 0 0 1 12 6c5 0 9 4.5 9 6a11 11 0 0 1-2.4 3.1M6.3 6.9C3.9 8.3 3 11 3 12c0 1.5 4 6 9 6 1.2 0 2.3-.2 3.3-.6" strokeLinecap="round" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" strokeLinecap="round" />
    </svg>
  ) : (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M3 12s3.6-6 9-6 9 6 9 6-3.6 6-9 6-9-6-9-6Z" />
      <circle cx="12" cy="12" r="2.6" />
    </svg>
  );
}
function ShieldIcon(): ReactNode {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M12 3 5 5.7v5.6C5 16 8 19.4 12 21c4-1.6 7-5 7-9.7V5.7L12 3Z" strokeLinejoin="round" />
      <path d="m9 12 2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const NOT_AVAILABLE = "This isn't available yet — please contact your GridDefence administrator.";

export function LoginPage() {
  const { token, login } = useAuth();
  const navigate = useNavigate();
  const usernameRef = useRef<HTMLInputElement>(null);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Login is a strict single-viewport page — lock document scrolling while it is
  // mounted, then restore it so every other (scrollable) route is unaffected.
  useEffect(() => {
    const root = document.documentElement;
    const prevRoot = root.style.overflow;
    const prevBody = document.body.style.overflow;
    root.style.overflow = "hidden";
    document.body.style.overflow = "hidden";
    return () => {
      root.style.overflow = prevRoot;
      document.body.style.overflow = prevBody;
    };
  }, []);

  if (token !== null) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (isSubmitting) return; // guard against duplicate submissions
    setError(null);
    setNotice(null);
    setIsSubmitting(true);
    try {
      await login(username, password, remember);
      navigate("/", { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setError("Invalid username or password.");
      } else {
        setError("Sign in failed. Please check your connection and try again.");
      }
      usernameRef.current?.focus();
    } finally {
      setIsSubmitting(false);
    }
  }

  const linkButtonStyle: CSSProperties = {
    border: "none",
    background: "none",
    padding: 0,
    cursor: "pointer",
    color: tokens.color.link,
    fontFamily: tokens.typography.fontFamily,
    fontSize: tokens.typography.size.small,
    fontWeight: tokens.typography.weight.semibold,
    textDecoration: "underline",
  };

  // Layout is expressed with pure CSS min()/clamp() so it stays fully
  // responsive (desktop → mobile) without a stylesheet, media queries, or JS
  // matchMedia. The card's `min(panelMaxWidth, 100%)` plus border-box sizing
  // guarantees it can never exceed the viewport — no horizontal scroll/clip.
  // Adaptive Composition: a single-viewport engineering page. The hero owns the
  // page; the card is a bounded, right-aligned complement. Additional screen
  // space is redistributed into horizontal gutter (hero + breathing room) via
  // the clamped padding, never into a larger card (see cardStyle max width).
  // Strict single-viewport page: exactly the effective CSS viewport (100dvh),
  // never taller. All internal sizing is viewport-HEIGHT responsive (dvh) so the
  // whole composition fits from tall desktops down to ~445px-tall laptop/zoom
  // viewports without vertical scrolling or clipping.
  const pageStyle: CSSProperties = {
    height: "100dvh",
    maxHeight: "100dvh",
    width: "100%",
    maxWidth: "100%",
    boxSizing: "border-box",
    position: "relative",
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    alignItems: "flex-end",
    // Vertical padding collapses on short viewports (dvh); horizontal max grows
    // so wider monitors give the hero more presence, never a bigger card.
    padding: "clamp(10px, 3dvh, 64px) clamp(16px, 7vw, 160px)",
    fontFamily: tokens.typography.fontFamily,
    color: tokens.color.textPrimary,
    backgroundImage: `url(${heroUrl})`,
    backgroundSize: "cover",
    backgroundPosition: "center",
    backgroundColor: "#1a2f52", // solid fallback while the hero loads / if unavailable
  };

  const cardStyle: CSSProperties = {
    // Bounded, non-growing, and viewport-HEIGHT responsive: the card becomes
    // narrower AND less padded on short screens even when width is available
    // (Adaptive Composition — short viewports get a smaller card, not a clipped
    // one). Still never exceeds the viewport width via the outer min(…, 100%).
    width: "min(clamp(330px, 40dvh, 380px), 100%)",
    boxSizing: "border-box",
    backgroundColor: tokens.color.surfacePanel,
    borderRadius: tokens.radius.panel,
    boxShadow: tokens.shadow.panel,
    padding: "clamp(10px, 2.6dvh, 30px)",
  };

  return (
    <main style={pageStyle}>
      {/* Brand — the approved authoritative logo (meaningful to assistive tech),
          with a soft, local light scrim so the grey portion of the wordmark stays
          legible over bright regions of the hero. The scrim is a radial gradient
          that fades to transparent (soft falloff, no hard edge) — deliberately
          not a card/panel/badge, and not a global overlay on the hero. */}
      <div
        style={{
          position: "absolute",
          top: "clamp(8px, 2.2dvh, 26px)",
          left: "clamp(12px, 5vw, 44px)",
          padding: "clamp(4px, 1dvh, 12px) clamp(14px, 2vw, 24px)",
          background:
            "radial-gradient(ellipse at center, rgba(255,255,255,0.55) 0%, rgba(255,255,255,0.34) 46%, rgba(255,255,255,0) 76%)",
          pointerEvents: "none",
        }}
      >
        <img
          src={logoUrl}
          alt="GridDefence"
          style={{ display: "block", height: "clamp(22px, 3.6dvh, 40px)", width: "auto" }}
        />
      </div>

      <section aria-labelledby="login-heading" style={cardStyle}>
        <h1
          id="login-heading"
          style={{
            margin: 0,
            textAlign: "center",
            fontSize: "clamp(1.05rem, 3dvh, 1.7rem)",
            fontWeight: tokens.typography.weight.bold,
            color: tokens.color.textPrimary,
            letterSpacing: "-0.2px",
          }}
        >
          Welcome back
        </h1>
        <p
          style={{
            margin: `${tokens.space[2]} 0 clamp(6px, 1.5dvh, 22px)`,
            textAlign: "center",
            fontSize: tokens.typography.size.subhead,
            color: tokens.color.textSecondary,
          }}
        >
          Sign in to access your engineering workspace.
        </p>

        <form onSubmit={handleSubmit} noValidate style={{ display: "flex", flexDirection: "column", gap: "clamp(5px, 1.25dvh, 16px)" }}>
          <TextField
            ref={usernameRef}
            id="username"
            name="username"
            label="Username"
            type="text"
            autoComplete="username"
            placeholder="Enter your username"
            leadingIcon={<PersonIcon />}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoFocus
          />

          <TextField
            id="password"
            name="password"
            label="Password"
            type={showPassword ? "text" : "password"}
            autoComplete="current-password"
            placeholder="Enter your password"
            leadingIcon={<LockIcon />}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            trailing={
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
                style={{
                  border: "none",
                  background: "none",
                  padding: tokens.space[1],
                  margin: 0,
                  cursor: "pointer",
                  color: tokens.color.fieldIcon,
                  display: "inline-flex",
                }}
              >
                <EyeIcon off={showPassword} />
              </button>
            }
          />

          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: tokens.space[3] }}>
            <label style={{ display: "inline-flex", alignItems: "center", gap: tokens.space[2], fontSize: tokens.typography.size.small, color: tokens.color.textSecondary, cursor: "pointer" }}>
              <input
                type="checkbox"
                name="remember"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                style={{ width: "16px", height: "16px", accentColor: tokens.color.actionPrimary }}
              />
              Remember me
            </label>
            <button
              type="button"
              style={linkButtonStyle}
              onClick={() => {
                setError(null);
                setNotice(`Password reset ${NOT_AVAILABLE.slice(NOT_AVAILABLE.indexOf("isn't"))}`);
              }}
            >
              Forgot password?
            </button>
          </div>

          {error !== null && (
            <p
              role="alert"
              style={{
                margin: 0,
                padding: `${tokens.space[3]} ${tokens.space[4]}`,
                borderRadius: tokens.radius.sm,
                backgroundColor: "#FDECEA",
                border: `1px solid #F3C0BB`,
                color: tokens.color.feedbackError,
                fontSize: tokens.typography.size.small,
                fontWeight: tokens.typography.weight.medium,
              }}
            >
              {error}
            </p>
          )}

          <Button type="submit" variant="primary" fullWidth loading={isSubmitting}>
            {isSubmitting ? "Signing in…" : "Sign in"}
          </Button>

          {/* Divider */}
          <div style={{ display: "flex", alignItems: "center", gap: tokens.space[3], color: tokens.color.dividerText }} aria-hidden="true">
            <span style={{ flex: 1, height: "1px", backgroundColor: tokens.color.borderDivider }} />
            <span style={{ fontSize: tokens.typography.size.small }}>or continue with</span>
            <span style={{ flex: 1, height: "1px", backgroundColor: tokens.color.borderDivider }} />
          </div>

          <Button
            type="button"
            variant="secondary"
            fullWidth
            leadingIcon={<span aria-hidden="true" style={{ display: "inline-flex", color: tokens.color.actionPrimary }}><ShieldIcon /></span>}
            title="Single sign-on is not yet available"
            onClick={() => {
              setError(null);
              setNotice(`Single sign-on ${NOT_AVAILABLE.slice(NOT_AVAILABLE.indexOf("isn't"))}`);
            }}
          >
            Single Sign-On (SSO)
          </Button>

          {/* Honest, non-blocking status for the not-yet-available affordances. */}
          <p aria-live="polite" style={{ margin: 0, textAlign: "center", fontSize: tokens.typography.size.small, color: tokens.color.textSecondary }}>
            {notice}
          </p>

          <p style={{ margin: 0, textAlign: "center", fontSize: tokens.typography.size.footnote, color: tokens.color.textSecondary }}>
            By signing in, you agree to our{" "}
            <button type="button" style={linkButtonStyle} onClick={() => setNotice(NOT_AVAILABLE)}>
              Terms of Use
            </button>{" "}
            and{" "}
            <button type="button" style={linkButtonStyle} onClick={() => setNotice(NOT_AVAILABLE)}>
              Privacy Policy
            </button>
            .
          </p>
        </form>
      </section>

      <p
        style={{
          position: "absolute",
          bottom: "clamp(8px, 2dvh, 24px)",
          left: "clamp(20px, 6vw, 56px)",
          margin: 0,
          fontSize: tokens.typography.size.footnote,
          color: tokens.color.textOnHero,
        }}
      >
        © {new Date().getFullYear()} GridDefence. All rights reserved.
      </p>
    </main>
  );
}
