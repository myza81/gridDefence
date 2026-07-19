import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LifecycleBadge } from "../../../src/components/scheme-platform/LifecycleBadge";
import type { SchemeVersionLifecycleStatus } from "../../../src/components/scheme-platform/types";

describe("LifecycleBadge", () => {
  const cases: Array<[SchemeVersionLifecycleStatus, string]> = [
    ["DRAFT", "Draft"],
    ["PUBLISHED", "Published"],
    ["SUPERSEDED", "Superseded"],
    ["ENTERED_IN_ERROR", "Entered in Error"],
  ];

  it.each(cases)("renders the correct label for %s", (status, label) => {
    render(<LifecycleBadge status={status} />);
    expect(screen.getByTestId("lifecycle-badge")).toHaveTextContent(label);
  });

  it("never renders an Under Review or Approved label", () => {
    render(<LifecycleBadge status="DRAFT" />);
    expect(screen.queryByText("Under Review")).not.toBeInTheDocument();
    expect(screen.queryByText("Approved")).not.toBeInTheDocument();
    expect(screen.queryByText("Active")).not.toBeInTheDocument();
    expect(screen.queryByText("Archived")).not.toBeInTheDocument();
  });
});
