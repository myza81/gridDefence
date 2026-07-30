import type { HomeIconKey } from "../types";

/**
 * Presentation-only icon registry — resolves a serialisable {@link HomeIconKey}
 * to a restrained line SVG in the shared stroke style (no decorative graphics).
 * Icons live here (not in the mock data) so the data stays API-swap friendly.
 */
export function HomeIcon({ name, size = 18 }: { name: HomeIconKey; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };
  switch (name) {
    case "registries":
    case "substation":
      return (
        <svg {...common}>
          <ellipse cx="12" cy="5.5" rx="8" ry="3" />
          <path d="M4 5.5v13c0 1.7 3.6 3 8 3s8-1.3 8-3v-13" />
          <path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
        </svg>
      );
    case "network":
    case "snapshot":
      return (
        <svg {...common}>
          <circle cx="5" cy="6" r="2.2" />
          <circle cx="19" cy="6" r="2.2" />
          <circle cx="12" cy="18" r="2.2" />
          <path d="M6.7 7.4 10.8 16M17.3 7.4 13.2 16M7 6h10" />
        </svg>
      );
    case "schemes":
    case "create-scheme":
    case "approve":
      return (
        <svg {...common}>
          <path d="M12 3 5 5.7v5.6C5 16 8 19.4 12 21c4-1.6 7-5 7-9.7V5.7L12 3Z" />
          <path d="m9 12 2 2 4-4" />
        </svg>
      );
    case "validation":
    case "publish":
      return (
        <svg {...common}>
          <path d="M3 12h3l2.5 6 4-13L18 12h3" />
        </svg>
      );
    case "reports":
      return (
        <svg {...common}>
          <path d="M6 3h9l5 5v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
          <path d="M14 3v6h6M9 13h6M9 17h4" />
        </svg>
      );
    case "administration":
      return (
        <svg {...common}>
          <path d="M4 6h10M18 6h2M4 12h2M10 12h10M4 18h8M16 18h4" />
          <circle cx="16" cy="6" r="2" />
          <circle cx="8" cy="12" r="2" />
          <circle cx="14" cy="18" r="2" />
        </svg>
      );
    case "import":
      return (
        <svg {...common}>
          <path d="M12 3v12m0 0-4-4m4 4 4-4M4 21h16" />
        </svg>
      );
    case "register":
      return (
        <svg {...common}>
          <path d="M12 5v14M5 12h14" />
        </svg>
      );
    case "equipment":
    case "transformer":
      return (
        <svg {...common}>
          <rect x="3" y="3" width="8" height="8" rx="1.5" />
          <rect x="13" y="13" width="8" height="8" rx="1.5" />
          <path d="M11 7h6v6" />
        </svg>
      );
    case "draft":
      return (
        <svg {...common}>
          <path d="M12 20h9M3 20l1-4 11-11 3 3-11 11-4 1Z" />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" />
        </svg>
      );
  }
}
