import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EngineeringHomePage } from "../../src/modules/home/pages/EngineeringHomePage";
import { renderWithProviders } from "../testUtils";

describe("EngineeringHomePage", () => {
  it("renders the welcome workspace, not an analytics dashboard", () => {
    renderWithProviders(<EngineeringHomePage />, { route: "/" });

    // Welcome (falls back to "Engineer" with no active session in the test).
    expect(screen.getByRole("heading", { level: 1, name: /welcome back, engineer/i })).toBeInTheDocument();
    expect(screen.getByText(/transmission grid defence engineering platform/i)).toBeInTheDocument();

    // The engineering sections are present.
    for (const title of ["Quick actions", "Requires attention", "Continue working", "Engineering modules", "Recent engineering activity"]) {
      expect(screen.getByRole("heading", { level: 2, name: title })).toBeInTheDocument();
    }
  });

  it("exposes quick actions and modules as links to existing routes", () => {
    renderWithProviders(<EngineeringHomePage />, { route: "/" });

    expect(screen.getByRole("link", { name: /import pss\/e/i })).toHaveAttribute("href", "/psse-integration/import");
    expect(screen.getByRole("link", { name: /register substation/i })).toHaveAttribute("href", "/substations/new");
    // Anchored names: module link accessible names include their description text.
    expect(screen.getByRole("link", { name: /^Registries/ })).toHaveAttribute("href", "/substations");
    expect(screen.getByRole("link", { name: /^Network & PSS\/E/ })).toHaveAttribute("href", "/network-model");
  });

  it("surfaces attention items and recent activity from mock data", () => {
    renderWithProviders(<EngineeringHomePage />, { route: "/" });

    expect(screen.getByText("3 validation findings")).toBeInTheDocument();
    expect(screen.getByText("Published UFLS version 12")).toBeInTheDocument();
    // Continue Working resume points are clickable.
    expect(screen.getByRole("link", { name: /^Substation Registry/ })).toHaveAttribute("href", "/substations");
  });

  it("renders a module without a route yet as 'Coming soon', not a dead link", () => {
    renderWithProviders(<EngineeringHomePage />, { route: "/" });

    expect(screen.getByText("Coming soon")).toBeInTheDocument();
    // Reports has no route → it must NOT be a link.
    expect(screen.queryByRole("link", { name: /reports/i })).not.toBeInTheDocument();
    // But its title and description are still shown.
    expect(screen.getByText("Reports")).toBeInTheDocument();
    expect(screen.getByText(/engineering reports and export/i)).toBeInTheDocument();
  });
});
