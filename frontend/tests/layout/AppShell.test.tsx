import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { AppShell } from "../../src/components/layout/AppShell";
import { EngineeringHomePage } from "../../src/modules/home/pages/EngineeringHomePage";
import { LoginPage } from "../../src/modules/iam/pages/LoginPage";
import { authStorage } from "../../src/modules/iam/authStorage";
import { renderAuthenticated } from "../authFixture";
import { renderWithProviders } from "../testUtils";

function Workspace() {
  return <div>Workspace content</div>;
}

describe("Application Shell V2", () => {
  it("wraps authenticated content in a grouped navigation frame", () => {
    renderAuthenticated(
      <AppShell>
        <Workspace />
      </AppShell>,
      { route: "/" },
    );

    const nav = screen.getByRole("navigation", { name: "Primary" });
    expect(within(nav).getByRole("link", { name: "Home" })).toBeInTheDocument();
    // Domain grouping, not a flat list of every route.
    expect(within(nav).getByText("Engineering Domains")).toBeInTheDocument();
    expect(within(nav).getByText("System")).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: /Registries/ })).toBeInTheDocument();
    expect(screen.getByText("Workspace content")).toBeInTheDocument();
  });

  it("renders the Engineering Home at the root route inside the shell", () => {
    renderAuthenticated(
      <AppShell>
        <EngineeringHomePage />
      </AppShell>,
      { route: "/" },
    );

    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: /welcome back/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Engineering modules" })).toBeInTheDocument();
  });

  it("marks the active route and auto-expands its parent group", () => {
    renderAuthenticated(
      <AppShell>
        <Workspace />
      </AppShell>,
      { route: "/substations" },
    );

    const activeLink = screen.getByRole("link", { name: "Substations" });
    expect(activeLink).toHaveAttribute("aria-current", "page");

    // Parent group is expanded (its child route is active); a sibling group is not.
    expect(screen.getByRole("button", { name: /Registries/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /Network & PSS\/E/ })).toHaveAttribute("aria-expanded", "false");
  });

  it("renders coming-soon modules as clearly unavailable, never as dead links", () => {
    renderAuthenticated(
      <AppShell>
        <Workspace />
      </AppShell>,
      { route: "/" },
    );

    const nav = screen.getByRole("navigation", { name: "Primary" });
    expect(within(nav).getByText("Reports")).toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "Reports" })).toBeNull();
    expect(within(nav).getAllByText("Soon").length).toBeGreaterThan(0);
  });

  it("shows the authenticated user and signs out", async () => {
    const user = userEvent.setup();
    renderAuthenticated(
      <AppShell>
        <Workspace />
      </AppShell>,
      { route: "/" },
    );

    // Identity resolves from the mocked /users/me.
    const accountButton = await screen.findByRole("button", { name: /Account menu for Su Fong/ });
    await user.click(accountButton);
    await user.click(screen.getByRole("menuitem", { name: /Sign out/ }));

    await waitFor(() => expect(authStorage.getToken()).toBeNull());
  });

  it("presents search and notifications as placeholders, not live engineering data", async () => {
    const user = userEvent.setup();
    renderAuthenticated(
      <AppShell>
        <Workspace />
      </AppShell>,
      { route: "/" },
    );

    expect(screen.getByRole("button", { name: /Search GridDefence — coming soon/ })).toHaveAttribute(
      "aria-disabled",
      "true",
    );

    const bell = screen.getByRole("button", { name: /Notifications — none yet/ });
    await user.click(bell);
    expect(screen.getByText("No notifications")).toBeInTheDocument();
  });

  it("derives breadcrumbs from the route hierarchy", () => {
    renderAuthenticated(
      <AppShell>
        <Workspace />
      </AppShell>,
      { route: "/psse-integration/history" },
    );

    const breadcrumb = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(within(breadcrumb).getByText("Network & PSS/E")).toBeInTheDocument();
    expect(within(breadcrumb).getByText("PSS/E History")).toBeInTheDocument();
  });

  it("keeps the login page outside the shell", () => {
    renderWithProviders(<LoginPage />, { route: "/login" });
    expect(screen.queryByRole("navigation", { name: "Primary" })).toBeNull();
  });
});

describe("Application Shell V2 — mobile", () => {
  it("opens the drawer, closes it after navigation, and on Escape", async () => {
    window.innerWidth = 480;
    const user = userEvent.setup();
    renderAuthenticated(
      <AppShell>
        <Workspace />
      </AppShell>,
      { route: "/" },
    );

    // No persistent sidebar on mobile; the drawer starts closed.
    expect(screen.queryByRole("dialog", { name: "Navigation" })).toBeNull();

    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    const drawer = screen.getByRole("dialog", { name: "Navigation" });
    expect(drawer).toBeInTheDocument();

    // Closes after a destination is followed (expand the group, then navigate).
    await user.click(within(drawer).getByRole("button", { name: /Registries/ }));
    await user.click(within(drawer).getByRole("link", { name: "Substations" }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Navigation" })).toBeNull());

    // Reopen and close via Escape.
    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    expect(screen.getByRole("dialog", { name: "Navigation" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Navigation" })).toBeNull());
  });
});
