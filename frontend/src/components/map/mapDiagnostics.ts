/**
 * Rich-basemap failure diagnostics.
 *
 * The map reports *why* it fell back to neutral mode, using a small closed set
 * of reasons (no raw URLs, tokens, or MapLibre internals). The UI surfaces only
 * a short, human summary; a developer console line may carry more, but URLs are
 * redacted first so credentials/query parameters are never logged.
 */
export type RichFailureReason =
  | "configuration_missing"
  | "style_load_failed"
  | "timeout"
  | "unknown";

/** Short, user-safe explanation for a fallback reason (no secrets, no URLs). */
export function richFailureSummary(reason: RichFailureReason): string {
  switch (reason) {
    case "configuration_missing":
      return "No online basemap is configured.";
    case "style_load_failed":
      return "The online basemap could not be loaded (blocked, unreachable, or invalid).";
    case "timeout":
      return "The online basemap did not respond in time.";
    default:
      return "The online basemap is unavailable.";
  }
}

/**
 * Classify a MapLibre `error` event as an **essential** failure (the style
 * document itself did not load — fall back to neutral) or a **non-essential**
 * one (an optional sub-resource such as a sprite, glyph, or individual tile —
 * the style is still usable, so do NOT discard rich mode). Source/tile errors
 * carry a `sourceId`; sprite/glyph failures are non-fatal in MapLibre and still
 * allow `style.load` to fire.
 */
export function classifyStyleError(event: { error?: { message?: string }; sourceId?: string } | undefined): "essential" | "non-essential" {
  if (event == null) return "non-essential";
  if (event.sourceId != null && event.sourceId !== "") return "non-essential";
  const message = String(event.error?.message ?? "");
  // Ambiguous (no detail) ⇒ don't discard rich on it; the bounded timeout decides.
  if (message === "") return "non-essential";
  if (/sprite|glyph|tile|font/i.test(message)) return "non-essential";
  return "essential";
}

/**
 * Redact a URL for safe logging: drop the query string (tokens/keys/signatures
 * commonly live there) and any userinfo, keeping only origin + path. Non-URLs
 * or unparseable values collapse to a placeholder so nothing sensitive leaks.
 */
export function redactUrl(input: string): string {
  if (typeof input !== "string" || input.length === 0) return "";
  try {
    const url = new URL(input, "http://local.invalid");
    const origin = url.host === "local.invalid" ? "" : `${url.protocol}//${url.host}`;
    const suffix = url.search || url.username || url.password ? " [query redacted]" : "";
    return `${origin}${url.pathname}${suffix}`;
  } catch {
    // Not a URL — strip anything after a `?` defensively.
    return input.split("?")[0] + (input.includes("?") ? " [query redacted]" : "");
  }
}
