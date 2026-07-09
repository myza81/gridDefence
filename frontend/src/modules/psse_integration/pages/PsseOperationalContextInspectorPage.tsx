import type { ColumnDef } from "@tanstack/react-table";
import { createColumnHelper } from "@tanstack/react-table";
import { Link, useLocation } from "react-router-dom";

import { DataInspector } from "../../../components/ui/DataInspector";
import { DataTable } from "../../../components/ui/DataTable";
import { formatBusClassification, formatCorrelationStatus, formatSnapshotType } from "../format";
import type {
  ParsedBranchRow,
  ParsedBusRow,
  ParsedGeneratorRow,
  ParsedLoadRow,
  ParsedTransformerRow,
  PreviewResult,
} from "../types";

const busColumns: ColumnDef<ParsedBusRow>[] = (() => {
  const helper = createColumnHelper<ParsedBusRow>();
  return [
    helper.accessor("bus_number", { header: "Bus Number" }),
    helper.accessor("bus_name", { header: "Bus Name", cell: (info) => info.getValue() ?? "—" }),
    helper.accessor("base_kv", { header: "Base kV" }),
    helper.accessor("ide", { header: "Type Code (IDE)" }),
    helper.accessor("area", { header: "Area", cell: (info) => info.getValue() ?? "—" }),
    helper.accessor("zone", { header: "Zone", cell: (info) => info.getValue() ?? "—" }),
    helper.accessor("owner", { header: "Owner", cell: (info) => info.getValue() ?? "—" }),
    helper.accessor("voltage_mag", {
      header: "Voltage Magnitude (p.u.)",
      cell: (info) => info.getValue() ?? "—",
    }),
    helper.accessor("voltage_angle", {
      header: "Voltage Angle (deg)",
      cell: (info) => info.getValue() ?? "—",
    }),
    helper.accessor("bus_classification", {
      header: "Classification",
      cell: (info) => formatBusClassification(info.getValue()),
    }),
    helper.accessor("substation_mnemonic", {
      header: "Correlated Substation",
      cell: (info) => info.getValue() ?? "—",
    }),
    helper.accessor("correlation_status", {
      header: "Correlation Status",
      cell: (info) => {
        const value = info.getValue();
        return value ? formatCorrelationStatus(value) : "—";
      },
    }),
  ] as ColumnDef<ParsedBusRow>[];
})();

const branchColumns: ColumnDef<ParsedBranchRow>[] = (() => {
  const helper = createColumnHelper<ParsedBranchRow>();
  return [
    helper.accessor("from_bus", { header: "From Bus" }),
    helper.accessor("to_bus", { header: "To Bus" }),
    helper.accessor("ckt_id", { header: "Circuit ID" }),
    helper.accessor("r", { header: "R (p.u.)" }),
    helper.accessor("x", { header: "X (p.u.)" }),
    helper.accessor("b", { header: "B (p.u.)" }),
    helper.accessor("rate_a", { header: "Rate A", cell: (info) => info.getValue() ?? "—" }),
    helper.accessor("rate_b", { header: "Rate B", cell: (info) => info.getValue() ?? "—" }),
    helper.accessor("rate_c", { header: "Rate C", cell: (info) => info.getValue() ?? "—" }),
    helper.accessor("status", { header: "In Service", cell: (info) => (info.getValue() ? "Yes" : "No") }),
  ] as ColumnDef<ParsedBranchRow>[];
})();

const transformerColumns: ColumnDef<ParsedTransformerRow>[] = (() => {
  const helper = createColumnHelper<ParsedTransformerRow>();
  return [
    helper.accessor("from_bus", { header: "From Bus" }),
    helper.accessor("to_bus", { header: "To Bus" }),
    helper.accessor("tertiary_bus", { header: "Tertiary Bus", cell: (info) => info.getValue() ?? "—" }),
    helper.accessor("ckt_id", { header: "Circuit ID" }),
    helper.accessor("r", { header: "R (p.u.)" }),
    helper.accessor("x", { header: "X (p.u.)" }),
    helper.accessor("rate_a", { header: "Rate A", cell: (info) => info.getValue() ?? "—" }),
    helper.accessor("status", { header: "In Service", cell: (info) => (info.getValue() ? "Yes" : "No") }),
  ] as ColumnDef<ParsedTransformerRow>[];
})();

const loadColumns: ColumnDef<ParsedLoadRow>[] = (() => {
  const helper = createColumnHelper<ParsedLoadRow>();
  return [
    helper.accessor("bus_number", { header: "Bus Number" }),
    helper.accessor("load_id", { header: "Load ID" }),
    helper.accessor("status", { header: "In Service", cell: (info) => (info.getValue() ? "Yes" : "No") }),
    helper.accessor("p_mw", { header: "P (MW)" }),
    helper.accessor("q_mvar", { header: "Q (MVAr)" }),
    helper.accessor("owner", { header: "Owner", cell: (info) => info.getValue() ?? "—" }),
  ] as ColumnDef<ParsedLoadRow>[];
})();

const generatorColumns: ColumnDef<ParsedGeneratorRow>[] = (() => {
  const helper = createColumnHelper<ParsedGeneratorRow>();
  return [
    helper.accessor("bus_number", { header: "Bus Number" }),
    helper.accessor("gen_id", { header: "Generator ID" }),
    helper.accessor("status", { header: "In Service", cell: (info) => (info.getValue() ? "Yes" : "No") }),
    helper.accessor("p_gen", { header: "P Gen (MW)" }),
    helper.accessor("q_gen", { header: "Q Gen (MVAr)" }),
    helper.accessor("p_max", { header: "P Max", cell: (info) => info.getValue() ?? "—" }),
    helper.accessor("p_min", { header: "P Min", cell: (info) => info.getValue() ?? "—" }),
    helper.accessor("q_max", { header: "Q Max", cell: (info) => info.getValue() ?? "—" }),
    helper.accessor("q_min", { header: "Q Min", cell: (info) => info.getValue() ?? "—" }),
  ] as ColumnDef<ParsedGeneratorRow>[];
})();

function OverviewTab({ result }: { result: PreviewResult }) {
  return (
    <dl>
      <dt>Source File</dt>
      <dd>{result.source_file_reference}</dd>
      <dt>PSS/E RAW Version</dt>
      <dd>{result.raw_version ?? "Not available"}</dd>
      <dt>Base MVA</dt>
      <dd>{result.base_mva ?? "Not available"}</dd>
      <dt>Snapshot Type</dt>
      <dd>{formatSnapshotType(result.import_type)}</dd>
      <dt>Buses</dt>
      <dd>{result.bus_count}</dd>
      <dt>Branches</dt>
      <dd>{result.branch_count}</dd>
      <dt>Transformers</dt>
      <dd>{result.transformer_count}</dd>
      <dt>Loads</dt>
      <dd>{result.load_count}</dd>
      <dt>Generators</dt>
      <dd>{result.generator_count}</dd>
    </dl>
  );
}

/**
 * Operational Context Inspector (psse-integration-module.md §8.9e) — a
 * structured, Excel-like view of exactly what the PSS/E parser produced
 * during Preview. This is an inspection tool, not an engineering analysis
 * tool: it never infers meaning, validates, recommends, or transforms the
 * imported data — it presents the same parsed records Preview already
 * computed, in memory, with zero re-parsing and zero additional backend
 * queries.
 *
 * Preview data is never persisted or addressable by ID (zero-persistence,
 * §8.9), so this page only has data when navigated to directly from a
 * successful Preview (`navigate(..., { state: { previewResult } })`) — a
 * direct visit or page refresh has nothing to show, and says so plainly
 * rather than guessing or re-fetching.
 */
export function PsseOperationalContextInspectorPage() {
  const location = useLocation();
  const previewResult = (location.state as { previewResult?: PreviewResult } | null)?.previewResult;

  if (!previewResult) {
    return (
      <section>
        <h2>Operational Context Inspector</h2>
        <p>
          No imported data is available to inspect.{" "}
          <Link to="/psse-integration/import">Run a Preview</Link> first, then choose "Inspect
          Imported Data."
        </p>
      </section>
    );
  }

  const tabs = [
    { key: "overview", label: "Overview", content: <OverviewTab result={previewResult} /> },
    {
      key: "buses",
      label: "Bus Data",
      content: <DataTable data={previewResult.buses} columns={busColumns} />,
    },
    {
      key: "branches",
      label: "Branch Data",
      content: <DataTable data={previewResult.branches} columns={branchColumns} />,
    },
    {
      key: "transformers",
      label: "Transformer Data",
      content: <DataTable data={previewResult.transformers} columns={transformerColumns} />,
    },
    {
      key: "loads",
      label: "Load Data",
      content: <DataTable data={previewResult.loads} columns={loadColumns} />,
    },
    {
      key: "generators",
      label: "Generator Data",
      content: <DataTable data={previewResult.generators} columns={generatorColumns} />,
    },
  ];

  return <DataInspector title="Operational Context Inspector" tabs={tabs} />;
}
