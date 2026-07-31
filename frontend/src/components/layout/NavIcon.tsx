import type { NavIconName } from "../../app/navigation";

/**
 * Presentation-only icon registry for the application shell navigation.
 *
 * Icons are decorative reinforcement — they NEVER carry meaning alone
 * (Accessibility §14: the expanded shell always shows a text label beside the
 * icon; the collapsed rail exposes the label via tooltip + accessible name).
 * Line style, 1.8 stroke, matched to the approved Application Shell V2 language.
 */
const PATHS: Record<NavIconName, JSX.Element> = {
  home: (
    <path d="M4 11.5 12 4l8 7.5M6 10v9h4v-5h4v5h4v-9" strokeLinecap="round" strokeLinejoin="round" />
  ),
  registries: (
    <>
      <ellipse cx="12" cy="5.5" rx="8" ry="3" />
      <path d="M4 5.5v13c0 1.7 3.6 3 8 3s8-1.3 8-3v-13" />
      <path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
    </>
  ),
  substation: (
    <>
      <rect x="4" y="9" width="16" height="11" rx="1.5" />
      <path d="M8 9V6.5a4 4 0 0 1 8 0V9M9 20v-4h6v4" strokeLinecap="round" />
    </>
  ),
  circuit: (
    <>
      <circle cx="5" cy="6" r="2.2" />
      <circle cx="19" cy="6" r="2.2" />
      <circle cx="12" cy="18" r="2.2" />
      <path d="M6.7 7.4 10.8 16M17.3 7.4 13.2 16M7 6h10" strokeLinecap="round" />
    </>
  ),
  transformer: (
    <>
      <circle cx="9" cy="12" r="5" />
      <circle cx="15" cy="12" r="5" />
    </>
  ),
  relay: (
    <>
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <path d="M13 7l-4 6h3l-1 4 4-6h-3l1-4Z" strokeLinejoin="round" />
    </>
  ),
  sensitive: (
    <>
      <path d="M12 3 5 5.7v5.6C5 16 8 19.4 12 21c4-1.6 7-5 7-9.7V5.7L12 3Z" strokeLinejoin="round" />
      <path d="M12 9v4m0 3h.01" strokeLinecap="round" />
    </>
  ),
  network: (
    <>
      <circle cx="5" cy="6" r="2.2" />
      <circle cx="19" cy="6" r="2.2" />
      <circle cx="12" cy="18" r="2.2" />
      <path d="M6.7 7.4 10.8 16M17.3 7.4 13.2 16M7 6h10" strokeLinecap="round" />
    </>
  ),
  traversal: (
    <path
      d="M5 5h6a3 3 0 0 1 3 3v8m0 0 3-3m-3 3-3-3M5 5v0"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  ),
  verification: (
    <>
      <path d="M12 3 5 5.7v5.6C5 16 8 19.4 12 21c4-1.6 7-5 7-9.7V5.7L12 3Z" strokeLinejoin="round" />
      <path d="m9 12 2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  import: (
    <path d="M12 3v12m0 0-4-4m4 4 4-4M4 21h16" strokeLinecap="round" strokeLinejoin="round" />
  ),
  history: (
    <path d="M3 12a9 9 0 1 0 3-6.7M3 4v4h4M12 8v4l3 2" strokeLinecap="round" strokeLinejoin="round" />
  ),
  status: (
    <path d="M3 12h4l2.5 6 4-13L18 12h3" strokeLinecap="round" strokeLinejoin="round" />
  ),
  schemes: (
    <>
      <path d="M12 3 5 5.7v5.6C5 16 8 19.4 12 21c4-1.6 7-5 7-9.7V5.7L12 3Z" strokeLinejoin="round" />
      <path d="m9 12 2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  stage: (
    <path d="M4 20V8m5 12V4m5 16v-7m5 7V10" strokeLinecap="round" />
  ),
  uvls: (
    <path d="M6 4v10a6 6 0 0 0 12 0V4M9 20h6" strokeLinecap="round" strokeLinejoin="round" />
  ),
  emls: (
    <>
      <path d="M4 7h16M4 12h16M4 17h10" strokeLinecap="round" />
      <path d="M17 15l2 2 3-3" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  evaluation: (
    <path d="M3 12h3l2.5 6 4-13L18 12h3" strokeLinecap="round" strokeLinejoin="round" />
  ),
  reports: (
    <>
      <path d="M6 3h9l5 5v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
      <path d="M14 3v6h6M9 13h6M9 17h6" strokeLinecap="round" />
    </>
  ),
  administration: (
    <>
      <path d="M4 6h10M18 6h2M4 12h2M10 12h10M4 18h8M16 18h4" strokeLinecap="round" />
      <circle cx="16" cy="6" r="2" />
      <circle cx="8" cy="12" r="2" />
      <circle cx="14" cy="18" r="2" />
    </>
  ),
  users: (
    <>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3.5 20a5.5 5.5 0 0 1 11 0M16 5.5a3 3 0 0 1 0 5.8M17 14.5a5.5 5.5 0 0 1 3.5 5.1" strokeLinecap="round" />
    </>
  ),
  roles: (
    <>
      <path d="M12 3 5 5.7v5.6C5 16 8 19.4 12 21c4-1.6 7-5 7-9.7V5.7L12 3Z" strokeLinejoin="round" />
      <circle cx="12" cy="10" r="2" />
      <path d="M9 16a3 3 0 0 1 6 0" strokeLinecap="round" />
    </>
  ),
  permissions: (
    <>
      <rect x="5" y="10" width="14" height="10" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v2" strokeLinecap="round" />
    </>
  ),
};

interface NavIconProps {
  name: NavIconName;
  size?: number;
}

export function NavIcon({ name, size = 18 }: NavIconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      aria-hidden="true"
      focusable="false"
      style={{ flex: "none" }}
    >
      {PATHS[name]}
    </svg>
  );
}
