/**
 * Frontend-only display derivations (CLAUDE.md A12 — display-only
 * derivations are permitted, authoritative engineering logic is not).
 *
 * The backend remains the single source of truth: it continues to store
 * `ufls_function`/`uvls_function` as two independent booleans, and every
 * read DTO reports `substation_mnemonic`/`voltage_level_label`/`bay_label`
 * as separate fields (never a pre-formatted combined string). These
 * helpers only compose those already-provided values into the
 * presentation an engineer reviews — nothing here is persisted or sent
 * back to the API.
 */

export type FunctionDisplayLabel = "UFLS" | "UVLS" | "UFLS & UVLS";

/** A terminal always has at least one of the two flags true (module
 * document §9 rule 3 / `ck_alsf_function_flags`) — "neither" never occurs. */
export function deriveFunctionLabel(ufls: boolean, uvls: boolean): FunctionDisplayLabel {
  if (ufls && uvls) return "UFLS & UVLS";
  return ufls ? "UFLS" : "UVLS";
}

export type FunctionFilterValue = "" | "UFLS" | "UVLS" | "BOTH";

/** Maps the single combined "Automatic Load Shedding Function" filter
 * dropdown back onto the two independent boolean query params the backend
 * already supports (`ufls_function`/`uvls_function` are AND-combined at
 * the repository layer, so requesting both `true` already means "UFLS &
 * UVLS" — no backend filter-logic change was needed for this). */
export function functionFilterToParams(
  value: FunctionFilterValue,
): { ufls_function?: boolean; uvls_function?: boolean } {
  switch (value) {
    case "UFLS":
      return { ufls_function: true };
    case "UVLS":
      return { uvls_function: true };
    case "BOTH":
      return { ufls_function: true, uvls_function: true };
    default:
      return {};
  }
}

/** Full engineering identity of a Bay Terminal, in the pipe-separated
 * format engineers use to disambiguate terminals unambiguously (e.g.
 * "IGBK | 33kV | Transformer T1", "IGBK | 132kV | Line IGBK–ROMEO No.1").
 * Composed from three already-separate fields every read DTO in this
 * module reports (`substation_mnemonic`, `voltage_level_label`,
 * `bay_label`) — never stored as its own column, so it can never drift
 * out of sync with the Equipment Registry data it names. */
export function formatTerminalIdentity(
  substationMnemonic: string,
  voltageLevelLabel: string,
  bayLabel: string,
): string {
  return `${substationMnemonic} | ${voltageLevelLabel} | ${bayLabel}`;
}
