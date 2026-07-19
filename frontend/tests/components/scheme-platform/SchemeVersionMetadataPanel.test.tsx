import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SchemeVersionMetadataPanel } from "../../../src/components/scheme-platform/SchemeVersionMetadataPanel";
import type { SchemeVersionLifecycleInfo } from "../../../src/components/scheme-platform/types";

const BASE_METADATA: SchemeVersionLifecycleInfo = {
  versionId: "11111111-1111-1111-1111-111111111111",
  schemeId: "22222222-2222-2222-2222-222222222222",
  versionNumber: 1,
  lifecycleStatus: "DRAFT",
  publishedAt: null,
  publishedBy: null,
  supersededAt: null,
  enteredInErrorAt: null,
  enteredInErrorBy: null,
  enteredInErrorReason: null,
  engineeringRemarks: null,
  createdAt: "2026-07-01T00:00:00Z",
  updatedAt: "2026-07-02T00:00:00Z",
};

describe("SchemeVersionMetadataPanel", () => {
  it("renders em-dashes for every unset optional field", () => {
    render(<SchemeVersionMetadataPanel metadata={BASE_METADATA} />);
    const panel = screen.getByTestId("scheme-version-metadata-panel");
    expect(panel.textContent).toContain("—");
  });

  it("renders the publisher's display name when published", () => {
    render(
      <SchemeVersionMetadataPanel
        metadata={{
          ...BASE_METADATA,
          publishedAt: "2026-07-03T00:00:00Z",
          publishedBy: { displayName: "Jane Engineer" },
        }}
      />,
    );
    expect(screen.getByTestId("scheme-version-metadata-panel")).toHaveTextContent(
      "by Jane Engineer",
    );
  });

  it("renders the entered-in-error reason when present", () => {
    render(
      <SchemeVersionMetadataPanel
        metadata={{
          ...BASE_METADATA,
          enteredInErrorAt: "2026-07-04T00:00:00Z",
          enteredInErrorReason: "Published against the wrong scheme.",
        }}
      />,
    );
    expect(screen.getByTestId("scheme-version-metadata-panel")).toHaveTextContent(
      "Published against the wrong scheme.",
    );
  });

  it("renders engineering remarks when present", () => {
    render(
      <SchemeVersionMetadataPanel
        metadata={{ ...BASE_METADATA, engineeringRemarks: "Reviewed with regional office." }}
      />,
    );
    expect(screen.getByTestId("scheme-version-metadata-panel")).toHaveTextContent(
      "Reviewed with regional office.",
    );
  });
});
