import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppShell } from "../src/components/layout/AppShell";
import { EngineeringHomePage } from "../src/modules/home/pages/EngineeringHomePage";
import { renderWithProviders } from "./testUtils";

describe("App renders", () => {
  it("renders the Engineering Home landing inside the app shell without crashing", () => {
    renderWithProviders(
      <AppShell>
        <EngineeringHomePage />
      </AppShell>,
      { route: "/" },
    );

    // The root landing is the engineering workspace, not a stats dashboard.
    expect(screen.getByRole("heading", { level: 1, name: /welcome back/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Engineering modules" })).toBeInTheDocument();
  });
});
