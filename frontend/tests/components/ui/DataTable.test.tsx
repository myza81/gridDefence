import { createColumnHelper } from "@tanstack/react-table";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { DataTable } from "../../../src/components/ui/DataTable";

interface Row {
  id: number;
  name: string;
}

const columns = [
  createColumnHelper<Row>().accessor("id", { header: "ID" }),
  createColumnHelper<Row>().accessor("name", { header: "Name" }),
];

const ROWS: Row[] = [
  { id: 3, name: "Charlie" },
  { id: 1, name: "Alice" },
  { id: 2, name: "Bob" },
];

describe("DataTable", () => {
  it("shows the empty message and renders no table when there are no rows", () => {
    render(<DataTable data={[]} columns={columns} emptyMessage="Nothing here." />);

    expect(screen.getByText("Nothing here.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("defaults to 'No records available.' when no emptyMessage is given", () => {
    render(<DataTable data={[]} columns={columns} />);

    expect(screen.getByText("No records available.")).toBeInTheDocument();
  });

  it("renders every row and a matching row count", () => {
    render(<DataTable data={ROWS} columns={columns} />);

    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
    expect(screen.getByText("Charlie")).toBeInTheDocument();
    expect(screen.getByText("3 of 3 records")).toBeInTheDocument();
  });

  it("sorts by column when its header is clicked", async () => {
    render(<DataTable data={ROWS} columns={columns} />);
    const user = userEvent.setup();

    await user.click(screen.getByText("Name"));

    const cells = screen.getAllByRole("cell");
    // First data row's Name cell (column order: ID, Name — index 1, 3, 5...)
    expect(cells[1]).toHaveTextContent("Alice");
  });

  it("filters rows via the search input and reports a reduced row count", async () => {
    render(<DataTable data={ROWS} columns={columns} />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Search table"), "Bob");

    expect(screen.getByText("1 of 3 records")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
    expect(screen.queryByText("Alice")).not.toBeInTheDocument();
  });

  it("shows a no-match message when a search filters out every row", async () => {
    render(<DataTable data={ROWS} columns={columns} />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Search table"), "nonexistent");

    expect(screen.getByText("No records match your search.")).toBeInTheDocument();
  });
});
