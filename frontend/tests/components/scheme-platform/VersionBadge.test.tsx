import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { VersionBadge } from "../../../src/components/scheme-platform/VersionBadge";

describe("VersionBadge", () => {
  it("renders the version number", () => {
    render(<VersionBadge versionNumber={3} />);
    expect(screen.getByTestId("version-badge")).toHaveTextContent("Version 3");
  });

  it("renders version 1 correctly", () => {
    render(<VersionBadge versionNumber={1} />);
    expect(screen.getByTestId("version-badge")).toHaveTextContent("Version 1");
  });
});
