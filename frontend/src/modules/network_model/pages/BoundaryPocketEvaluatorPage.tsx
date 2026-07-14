import { useMutation, useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";

import { ApiError } from "../../../api/client";
import { DataTable } from "../../../components/ui/DataTable";
import { StatusBadge } from "../../../components/ui/StatusBadge";
import { equipmentRegistryApi } from "../../equipment_registry/api";
import type { CircuitTerminalIdentity } from "../../equipment_registry/types";
import { networkModelApi } from "../api";
import type { BoundaryPocketEvaluation } from "../types";

/**
 * Foundation Hardening Sprint C — a thin, read-only diagnostic UI over
 * `NetworkModelService.evaluate_boundary` (docs/architecture/boundary-pocket-
 * architecture.md §7, as corrected by ADR-019's connected-component
 * discovery). This is **not** the future Scheme Engineering Workspace's
 * Pocket Builder — it creates no Boundary Pocket entity, no Scheme Version,
 * no assignment, and no engineering finding. Every evaluation is transient
 * and freely repeatable; nothing here is persisted.
 *
 * The engineer selects only Circuit Terminal opening points — never an
 * "Inside Substation" or a "Rest-of-Grid Override" (both removed by
 * ADR-019): the Main Grid and every isolated island are discovered from the
 * topology itself and reported exactly as the backend returns them
 * (CLAUDE.md A12).
 *
 * Circuit Terminal candidates are fetched once and filtered/grouped
 * client-side (display-only derivation, mirroring `NetworkTraversalPage`'s
 * own "Transmission Lines Traversed" precedent) — the backend never
 * re-derives or reinterprets these results.
 */
export function BoundaryPocketEvaluatorPage() {
  const [selectedTerminalIds, setSelectedTerminalIds] = useState<string[]>([]);
  const [result, setResult] = useState<BoundaryPocketEvaluation | null>(null);

  const snapshotSummaryQuery = useQuery({
    queryKey: ["network-model", "boundary-pocket-evaluator", "snapshot-summary"],
    queryFn: () => networkModelApi.getSnapshotSummary(),
  });

  const circuitTerminalsQuery = useQuery({
    queryKey: ["network-model", "boundary-pocket-evaluator", "circuit-terminal-options"],
    queryFn: () => equipmentRegistryApi.listCircuitTerminalIdentities(),
  });

  const terminalsById = useMemo(
    () => new Map((circuitTerminalsQuery.data ?? []).map((t) => [t.circuit_terminal_id, t])),
    [circuitTerminalsQuery.data],
  );

  // Sibling terminals sharing the same Circuit — used only to derive
  // "opposite substation" display context (no engineering calculation).
  const siblingsByCircuit = useMemo(() => {
    const map = new Map<string, CircuitTerminalIdentity[]>();
    for (const terminal of circuitTerminalsQuery.data ?? []) {
      const list = map.get(terminal.circuit_id) ?? [];
      list.push(terminal);
      map.set(terminal.circuit_id, list);
    }
    return map;
  }, [circuitTerminalsQuery.data]);

  function oppositeSubstations(terminal: CircuitTerminalIdentity): string {
    const siblings = siblingsByCircuit.get(terminal.circuit_id) ?? [];
    const others = siblings.filter((t) => t.circuit_terminal_id !== terminal.circuit_terminal_id);
    const distinct = Array.from(new Set(others.map((t) => t.substation_mnemonic)));
    return distinct.length > 0 ? distinct.join(", ") : "—";
  }

  const evaluateMutation = useMutation({
    mutationFn: () =>
      networkModelApi.evaluateBoundary({
        circuit_terminal_ids: selectedTerminalIds,
      }),
    onSuccess: (data) => setResult(data),
  });

  function toggleTerminal(circuitTerminalId: string) {
    setResult(null);
    setSelectedTerminalIds((previous) =>
      previous.includes(circuitTerminalId)
        ? previous.filter((id) => id !== circuitTerminalId)
        : [...previous, circuitTerminalId],
    );
  }

  function removeTerminal(circuitTerminalId: string) {
    setResult(null);
    setSelectedTerminalIds((previous) => previous.filter((id) => id !== circuitTerminalId));
  }

  function resetForm() {
    setSelectedTerminalIds([]);
    setResult(null);
    evaluateMutation.reset();
  }

  const columns: ColumnDef<CircuitTerminalIdentity>[] = [
    {
      id: "select",
      header: "Select",
      cell: ({ row }) => {
        const terminal = row.original;
        const isSelected = selectedTerminalIds.includes(terminal.circuit_terminal_id);
        return (
          <input
            type="checkbox"
            aria-label={`Select opening point ${terminal.substation_mnemonic} ${terminal.breaker_number}`}
            checked={isSelected}
            onChange={() => toggleTerminal(terminal.circuit_terminal_id)}
          />
        );
      },
    },
    { header: "Substation", accessorKey: "substation_mnemonic" },
    { header: "Circuit", accessorKey: "circuit_name" },
    { header: "Voltage", accessorKey: "voltage_level_label" },
    { header: "Breaker / Bay", accessorKey: "breaker_number" },
    {
      id: "opposite",
      header: "Opposite Substation(s)",
      cell: ({ row }) => oppositeSubstations(row.original),
    },
  ];

  const canEvaluate = selectedTerminalIds.length > 0 && !evaluateMutation.isPending;

  return (
    <section>
      <h2>Boundary Pocket Evaluator</h2>
      <p style={{ fontWeight: "bold" }}>
        Diagnostic tool — results are transient and are not Scheme assignments.
      </p>
      <p>
        Manually exercises the Network Model&apos;s Boundary Pocket evaluation
        (docs/architecture/boundary-pocket-architecture.md §7, ADR-019) for engineering UAT before
        the Engineering Workspace exists. This page never creates a Boundary Pocket entity, a
        Scheme Version, an assignment, or an engineering finding — every evaluation below is
        transient and may be repeated freely.
      </p>

      <h3>1. Evaluation Context</h3>
      {snapshotSummaryQuery.isLoading && <p>Loading snapshot context...</p>}
      {snapshotSummaryQuery.isError && (
        <p role="alert">Unable to load current snapshot context.</p>
      )}
      {snapshotSummaryQuery.data && (
        <ul>
          <li>
            Current Topology Version:{" "}
            {snapshotSummaryQuery.data.topology_version_id ?? "None imported/activated yet"}
          </li>
          <li>Topology Status: {snapshotSummaryQuery.data.topology_version_status ?? "—"}</li>
          <li>
            Bus / Branch / Transformer counts: {snapshotSummaryQuery.data.bus_count} /{" "}
            {snapshotSummaryQuery.data.branch_count} / {snapshotSummaryQuery.data.transformer_count}
          </li>
        </ul>
      )}
      <p>
        The Main Grid and every isolated island are discovered from this active topology — there
        is no nominated substation to select, and no rest-of-grid reference to configure.
      </p>

      <h3>2. Selected Opening Points</h3>
      {circuitTerminalsQuery.isLoading && <p>Loading Circuit Terminals...</p>}
      {circuitTerminalsQuery.isError && (
        <p role="alert">Unable to load Circuit Terminal identities.</p>
      )}
      {circuitTerminalsQuery.data && (
        <DataTable
          data={circuitTerminalsQuery.data}
          columns={columns}
          emptyMessage="No Circuit Terminals are registered yet."
        />
      )}

      <h4>Selected Opening Points ({selectedTerminalIds.length})</h4>
      {selectedTerminalIds.length === 0 && <p>No opening points selected yet.</p>}
      {selectedTerminalIds.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Substation</th>
              <th>Circuit</th>
              <th>Breaker / Bay</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {selectedTerminalIds.map((circuitTerminalId) => {
              const terminal = terminalsById.get(circuitTerminalId);
              return (
                <tr key={circuitTerminalId}>
                  <td>{terminal?.substation_mnemonic ?? circuitTerminalId}</td>
                  <td>{terminal?.circuit_name ?? "—"}</td>
                  <td>{terminal?.breaker_number ?? "—"}</td>
                  <td>
                    <button type="button" onClick={() => removeTerminal(circuitTerminalId)}>
                      Remove
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      <h3>3. Evaluate</h3>
      <button
        type="button"
        disabled={!canEvaluate}
        onClick={() => {
          setResult(null);
          evaluateMutation.mutate();
        }}
      >
        {evaluateMutation.isPending ? "Evaluating..." : "Evaluate Boundary"}
      </button>
      <button type="button" onClick={resetForm} style={{ marginLeft: "0.75rem" }}>
        Reset
      </button>
      {selectedTerminalIds.length === 0 && (
        <p>Select at least one opening point before evaluating.</p>
      )}

      <h3>4. Result</h3>
      {evaluateMutation.isError && (
        <p role="alert">
          Evaluation Error:{" "}
          {evaluateMutation.error instanceof ApiError
            ? evaluateMutation.error.message
            : "Failed to evaluate boundary."}
        </p>
      )}
      {result && (
        <div>
          <StatusBadge
            label={result.is_boundary_effective ? "Boundary Effective" : "Boundary Ineffective"}
            tone={result.is_boundary_effective ? "ok" : "pending"}
          />
          <p>Selected opening-point count: {result.circuit_terminal_ids.length}</p>
          <p>Topology/snapshot context used: {result.topology_version_id}</p>
          <p>
            Baseline Main Grid:{" "}
            {result.baseline_has_single_main_grid
              ? `one connected Main Grid (${result.baseline_main_grid_substation_count} substations)`
              : `abnormal — ${result.baseline_component_count} baseline components detected, Main ` +
                `Grid has ${result.baseline_main_grid_substation_count} substations`}
          </p>

          {result.uncorrelated_circuit_terminal_ids.length > 0 && (
            <p role="alert">
              Uncorrelated opening points (excluded nothing):{" "}
              {result.uncorrelated_circuit_terminal_ids
                .map((id) => terminalsById.get(id)?.substation_mnemonic ?? id)
                .join(", ")}
            </p>
          )}

          <h4>Isolated Islands ({result.isolated_islands.length})</h4>
          {result.isolated_islands.length === 0 && <p>No new isolated island was formed.</p>}
          {result.isolated_islands.map((island, index) => (
            <ul key={index}>
              {island.substations.map((substation) => (
                <li key={substation.substation_id}>{substation.substation_mnemonic}</li>
              ))}
            </ul>
          ))}

          <p>{result.reason}</p>
          {!result.is_boundary_effective && (
            <p>
              This selection cannot become a Scheme assignment in this state — only a boundary
              that forms at least one isolated island may ever become an assignable Boundary
              Pocket.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
