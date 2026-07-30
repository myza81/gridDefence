/**
 * GridDefence design tokens — minimal, typed shared constants.
 *
 * WHY THIS SHAPE: the GridDefence frontend styles with inline `style={{}}`
 * objects (see components/ui/*, every module page) and has deliberately
 * deferred a formal design system (StatusBadge.tsx: "Not a design system;
 * that is a later decision"). This module is therefore a small set of typed
 * TypeScript constants — NOT CSS variables, NOT a global stylesheet, NOT a
 * className framework — so it composes with the existing inline-style
 * architecture instead of introducing a competing one.
 *
 * SCOPE: values are extracted from the approved login mockup
 * (docs/design/mockups/login_page.png) and kept to what the login page needs
 * plus values that are obviously reused (colours, spacing, radii). It is not
 * a speculative catalogue; extend it only as further approved screens require.
 *
 * The frontend performs no authoritative engineering logic (CLAUDE.md A12) —
 * these are presentation constants only.
 */

const color = {
  /** Deep navy — headings, labels, primary reading text. */
  textPrimary: "#0F2340",
  /** Muted supporting text and placeholders. */
  textSecondary: "#5A6A85",
  /** Light text used over the darker areas of the hero image. */
  textOnHero: "rgba(255, 255, 255, 0.88)",

  /** White working surface (the login card). */
  surfacePanel: "#FFFFFF",
  /** Very light blue-grey fill for subtle field/hover surfaces. */
  surfaceSubtle: "#F7F9FD",

  borderDefault: "#DCE3EF",
  borderStrong: "#C9D2E4",
  borderDivider: "#E6EAF2",

  /** Strong blue primary action (the Sign in button). */
  actionPrimary: "#2B47E0",
  actionPrimaryHover: "#2039C4",
  actionPrimaryText: "#FFFFFF",

  /** Interactive blue for links. */
  link: "#2B5BE6",

  /** Leading field icons (person / lock) — decorative, muted. */
  fieldIcon: "#98A2B3",
  /** "or continue with" divider label. */
  dividerText: "#6B7891",

  /** Authentication / validation error text. */
  feedbackError: "#C1121F",
} as const;

const focus = {
  /** Visible keyboard focus ring (WCAG 2.4.7). */
  ring: "0 0 0 3px rgba(43, 71, 224, 0.30)",
  ringColor: "#2B47E0",
} as const;

const typography = {
  fontFamily:
    "'Inter', 'Segoe UI', system-ui, -apple-system, Roboto, Arial, sans-serif",
  size: {
    heading: "1.75rem", // "Welcome back"
    subhead: "0.95rem",
    label: "0.9rem",
    input: "0.95rem",
    button: "0.95rem",
    small: "0.8rem",
    footnote: "0.8rem",
  },
  weight: {
    regular: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
    extrabold: 800,
  },
  lineHeight: {
    tight: 1.2,
    normal: 1.5,
  },
} as const;

/** 4px base spacing scale (string px values for direct use in style objects). */
const space = {
  1: "4px",
  2: "8px",
  3: "12px",
  4: "16px",
  5: "20px",
  6: "24px",
  8: "32px",
  10: "40px",
} as const;

const radius = {
  sm: "8px",
  md: "10px",
  lg: "12px",
  panel: "20px", // login card corners
  pill: "999px",
} as const;

const shadow = {
  /** Soft, restrained elevation for the floating login card — kept light so
   *  the card complements the hero rather than dominating it. */
  panel: "0 16px 40px rgba(15, 30, 61, 0.15)",
} as const;

/** Consistent control sizing for inputs and buttons. Height is viewport-height
 *  responsive so controls compact on short-height screens (login single-viewport
 *  fit); bounded 40–48px. Consumed only by the login primitives today. */
const control = {
  height: "clamp(36px, 5.6dvh, 48px)",
  paddingX: "14px",
} as const;

const layout = {
  // Adaptive Composition: the login card has a bounded MAX width and shrinks to
  // fit narrow screens (via min(panelMaxWidth, 100%)); it never grows with the
  // viewport. Extra desktop space becomes hero + whitespace, not a bigger card.
  panelMaxWidth: "380px",
  panelPadding: "40px",
  panelPaddingCompact: "28px",
} as const;

/** Min viewport widths at which the login layout adapts (for JS media checks). */
const breakpoint = {
  mobile: 640,
  tablet: 900,
} as const;

const transition = {
  base: "150ms ease",
} as const;

export const tokens = {
  color,
  focus,
  typography,
  space,
  radius,
  shadow,
  control,
  layout,
  breakpoint,
  transition,
} as const;

export type Tokens = typeof tokens;
