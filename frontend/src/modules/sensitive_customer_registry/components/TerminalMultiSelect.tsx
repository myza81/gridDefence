import { useMemo, useState } from "react";

import type { TransformerTerminalIdentity } from "../../equipment_registry/types";
import { formatTerminalPickerLabel } from "../displayHelpers";

interface TerminalMultiSelectProps {
  identities: TransformerTerminalIdentity[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
  isLoading?: boolean;
}

/** Searchable multi-select for a Sensitive Facility's currently associated
 * Transformer Terminal(s) (ADR-013 UAT change request). Deliberately flat
 * — sourced from every Transformer Terminal across every substation — so
 * it never requires a Substation or Transformer to be chosen first (the
 * cascading picker this replaces). Each option's label already carries
 * full engineering context ("Substation | Voltage | Transformer Tn
 * (side)"), so no separate Transformer step is needed. Selected terminals
 * are shown below as a compact Substation / Voltage / Transformer /
 * Terminal table, per the task's explicit UI requirement. */
export function TerminalMultiSelect({
  identities,
  selectedIds,
  onChange,
  isLoading,
}: TerminalMultiSelectProps) {
  const [search, setSearch] = useState("");

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (term === "") {
      return identities;
    }
    return identities.filter((identity) =>
      formatTerminalPickerLabel(identity).toLowerCase().includes(term),
    );
  }, [identities, search]);

  const selectedIdentities = useMemo(
    () => identities.filter((identity) => selectedSet.has(identity.transformer_terminal_id)),
    [identities, selectedSet],
  );

  function toggle(id: string): void {
    if (selectedSet.has(id)) {
      onChange(selectedIds.filter((existing) => existing !== id));
    } else {
      onChange([...selectedIds, id]);
    }
  }

  return (
    <div>
      <label htmlFor="scr-terminal-search">Transformer Terminal(s)</label>
      <br />
      <input
        id="scr-terminal-search"
        type="text"
        placeholder="Search by substation, voltage, or transformer..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      {isLoading && <p>Loading transformer terminals...</p>}
      <div
        style={{
          maxHeight: "220px",
          overflowY: "auto",
          border: "1px solid #ccc",
          borderRadius: "4px",
          padding: "0.5rem",
          marginTop: "0.25rem",
        }}
      >
        {filtered.length === 0 && (
          <p style={{ margin: 0, color: "#666" }}>No matching Transformer Terminals.</p>
        )}
        {filtered.map((identity) => (
          <label
            key={identity.transformer_terminal_id}
            style={{ display: "block", padding: "0.15rem 0" }}
          >
            <input
              type="checkbox"
              checked={selectedSet.has(identity.transformer_terminal_id)}
              onChange={() => toggle(identity.transformer_terminal_id)}
            />{" "}
            {formatTerminalPickerLabel(identity)}
          </label>
        ))}
      </div>

      {selectedIdentities.length > 0 && (
        <table style={{ marginTop: "0.75rem" }}>
          <thead>
            <tr>
              <th>Substation</th>
              <th>Voltage</th>
              <th>Transformer</th>
              <th>Terminal</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {selectedIdentities.map((identity) => (
              <tr key={identity.transformer_terminal_id}>
                <td>{identity.substation_mnemonic}</td>
                <td>{identity.voltage_level_label}</td>
                <td>Transformer {identity.generated_short_name}</td>
                <td>{identity.side}</td>
                <td>
                  <button type="button" onClick={() => toggle(identity.transformer_terminal_id)}>
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
