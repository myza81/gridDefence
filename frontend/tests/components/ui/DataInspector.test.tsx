import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { DataInspector } from "../../../src/components/ui/DataInspector";

describe("DataInspector", () => {
  it("renders the first tab's content by default", () => {
    render(
      <DataInspector
        title="Example Inspector"
        tabs={[
          { key: "a", label: "Tab A", content: <p>Content A</p> },
          { key: "b", label: "Tab B", content: <p>Content B</p> },
        ]}
      />,
    );

    expect(screen.getByText("Example Inspector")).toBeInTheDocument();
    expect(screen.getByText("Content A")).toBeInTheDocument();
    expect(screen.queryByText("Content B")).not.toBeInTheDocument();
  });

  it("switches tabs on click, showing only the active tab's content", async () => {
    render(
      <DataInspector
        title="Example Inspector"
        tabs={[
          { key: "a", label: "Tab A", content: <p>Content A</p> },
          { key: "b", label: "Tab B", content: <p>Content B</p> },
        ]}
      />,
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole("tab", { name: "Tab B" }));

    expect(screen.getByText("Content B")).toBeInTheDocument();
    expect(screen.queryByText("Content A")).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Tab B" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Tab A" })).toHaveAttribute("aria-selected", "false");
  });
});
