import type { TransformerBreakerNumberingConventionSummary } from "../../reference_data/types";

/**
 * Breaker-number suggestion (Transformer Registry) — display-only
 * convenience (CLAUDE.md A12), a pure function, never validated or enforced
 * by the backend, and always overridable by the user.
 *
 * The numbering convention itself (which pattern applies to which
 * transformation pair and side) is now backend reference data —
 * `transformer_breaker_numbering_convention`, seeded by
 * `app/reference_data/seed.py` and served via
 * `GET /api/v1/reference-data/transformer-breaker-numbering-conventions` —
 * not hardcoded here. This function only looks up the matching convention
 * row (keyed by HV/LV voltage level id and side) and applies its `pattern`,
 * replacing the literal substring `{N}` with the transformer/bay number.
 * Moving the convention to the database means a new transformation pair, or
 * a corrected pattern, is a data change, not a frontend code change.
 *
 * A row with `pattern === null` (e.g. the 500kV side of a 500/275kV
 * transformer — non-standard, per the convention) or no matching row at all
 * both mean "no automatic suggestion" — the caller shows nothing and lets
 * the user type the breaker number manually.
 */
export function suggestBreakerNumber(
  conventions: TransformerBreakerNumberingConventionSummary[],
  hvVoltageLevelId: number,
  lvVoltageLevelId: number,
  side: "HV" | "LV",
  transformerNumber: string,
): string | null {
  const trimmed = transformerNumber.trim();
  if (!/^\d+$/.test(trimmed)) {
    return null;
  }
  const convention = conventions.find(
    (c) =>
      c.hv_voltage_level_id === hvVoltageLevelId &&
      c.lv_voltage_level_id === lvVoltageLevelId &&
      c.side === side,
  );
  if (!convention || convention.pattern === null) {
    return null;
  }
  return convention.pattern.replace("{N}", trimmed);
}
