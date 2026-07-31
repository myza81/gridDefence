import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppShell } from "../src/components/layout/AppShell";
import { EngineeringHomePage } from "../src/modules/home/pages/EngineeringHomePage";
import { renderAuthenticated } from "./authFixture";

describe("App renders", () => {
  it("renders the Engineering Home landing inside Application Shell V2 without crashing", () => {
    renderAuthenticated(
      <AppShell>
        <EngineeringHomePage />
      </AppShell>,
      { route: "/" },
    );

    // The authenticated frame is present…
    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
    // …and the root landing is the engineering workspace, not a stats dashboard.
    expect(screen.getByRole("heading", { level: 1, name: /welcome back/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Engineering modules" })).toBeInTheDocument();
  });
});
