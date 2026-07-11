/**
 * Frontend-only display derivations (CLAUDE.md A12 — display-only
 * derivations are permitted, authoritative engineering logic is not).
 *
 * The backend remains the single source of truth: every read DTO reports
 * `substation_mnemonic`/`voltage_level_label`/`bay_label`/`side` as
 * separate fields (never a pre-formatted combined string) — mirroring
 * ALSF's own established separation. These helpers only compose those
 * already-provided values into the presentation an engineer reviews.
 */

import type { TransformerTerminalIdentity } from "../equipment_registry/types";
import type { TransformerTerminalResolution } from "./types";

/** Full engineering identity of a Transformer Terminal, in the pipe-
 * separated format engineers use to disambiguate terminals unambiguously
 * (e.g. "IGBK | 33kV | Transformer T1 (LV)"). `null` when any component is
 * missing — the caller is expected to use `describeTerminalResolution` to
 * explain why, never to silently omit the facility itself (Correction 4). */
export function formatTerminalIdentity(
  substationMnemonic: string | null,
  voltageLevelLabel: string | null,
  bayLabel: string | null,
  side?: string | null,
): string | null {
  if (substationMnemonic === null || voltageLevelLabel === null || bayLabel === null) {
    return null;
  }
  const label = side ? `${bayLabel} (${side})` : bayLabel;
  return `${substationMnemonic} | ${voltageLevelLabel} | ${label}`;
}

/** Correction 4 — a short, human-readable explanation of
 * `transformer_terminal_resolution`, always rendered instead of a blank
 * cell so an unresolved reference is visible engineering information, not
 * a silent gap. */
export function describeTerminalResolution(resolution: TransformerTerminalResolution): string {
  switch (resolution) {
    case "NOT_ASSIGNED":
      return "No supply point recorded";
    case "UNRESOLVED":
      return "Terminal could not be resolved";
    case "RESOLVED":
    default:
      return "";
  }
}

/** The label shown for one selectable option in the Transformer
 * Terminal(s) multi-select (ADR-013) — already carries enough engineering
 * context (substation, voltage, transformer, side) that the picker never
 * requires a Substation or Transformer to be chosen first. */
export function formatTerminalPickerLabel(identity: TransformerTerminalIdentity): string {
  return `${identity.substation_mnemonic} | ${identity.voltage_level_label} | Transformer ${identity.generated_short_name} (${identity.side})`;
}

export type LifecycleFilterValue = "" | "ACTIVE" | "ARCHIVED" | "ENTERED_IN_ERROR";
