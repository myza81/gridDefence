import { describe, expect, it } from "vitest";

import { NAVIGATION, flattenNavItems, isGroupActive, isRouteActive, routedNavItems } from "../../src/app/navigation";
import { authenticatedRoutePaths } from "../../src/app/routes";

describe("navigation taxonomy integrity", () => {
  it("every routed navigation entry points at a real authenticated route (no dead links)", () => {
    for (const item of routedNavItems()) {
      expect(authenticatedRoutePaths, `nav '${item.id}' → ${item.route}`).toContain(item.route);
    }
  });

  it("coming-soon entries never carry a route", () => {
    for (const item of flattenNavItems()) {
      if (item.availability === "coming-soon") {
        expect(item.route, `coming-soon '${item.id}'`).toBeUndefined();
      }
    }
  });

  it("routed entries have unique destinations", () => {
    const routes = routedNavItems().map((item) => item.route);
    expect(new Set(routes).size).toBe(routes.length);
  });

  it("exposes the platform's engineering domains as groups, not a flat list", () => {
    const topLevelIds = NAVIGATION.flatMap((section) => section.items).map((item) => item.id);
    expect(topLevelIds).toContain("registries");
    expect(topLevelIds).toContain("network");
    expect(topLevelIds).toContain("defence-schemes");
    expect(topLevelIds).toContain("administration");
  });
});

describe("route-active resolution", () => {
  it("marks Home active only on the exact root path", () => {
    expect(isRouteActive("/", "/")).toBe(true);
    expect(isRouteActive("/", "/substations")).toBe(false);
  });

  it("keeps a module entry active on its detail routes", () => {
    expect(isRouteActive("/substations", "/substations")).toBe(true);
    expect(isRouteActive("/substations", "/substations/new")).toBe(true);
    expect(isRouteActive("/substations", "/substations/9f3a2b7c")).toBe(true);
    expect(isRouteActive("/substations", "/substations-archive")).toBe(false);
  });

  it("activates a parent group when one of its children is active", () => {
    const registries = NAVIGATION.flatMap((section) => section.items).find((item) => item.id === "registries")!;
    expect(isGroupActive(registries, "/substations/9f3a2b7c")).toBe(true);
    expect(isGroupActive(registries, "/ufls/schemes")).toBe(false);
  });
});
