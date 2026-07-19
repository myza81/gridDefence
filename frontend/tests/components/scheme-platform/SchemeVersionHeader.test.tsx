import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SchemeVersionHeader } from "../../../src/components/scheme-platform/SchemeVersionHeader";

describe("SchemeVersionHeader", () => {
  it("renders the caller-supplied title, version badge, and lifecycle badge", () => {
    render(
      <SchemeVersionHeader
        title="Synthetic Scheme — Test Substation"
        versionNumber={2}
        lifecycleStatus="PUBLISHED"
      />,
    );

    const header = screen.getByTestId("scheme-version-header");
    expect(header).toHaveTextContent("Synthetic Scheme — Test Substation");
    expect(screen.getByTestId("version-badge")).toHaveTextContent("Version 2");
    expect(screen.getByTestId("lifecycle-badge")).toHaveTextContent("Published");
  });

  it("never references UFLS, UVLS, or EMLS in its own rendered output", () => {
    render(
      <SchemeVersionHeader title="Generic Title" versionNumber={1} lifecycleStatus="DRAFT" />,
    );
    const header = screen.getByTestId("scheme-version-header");
    expect(header.textContent?.toLowerCase()).not.toContain("ufls");
    expect(header.textContent?.toLowerCase()).not.toContain("uvls");
    expect(header.textContent?.toLowerCase()).not.toContain("emls");
  });
});
