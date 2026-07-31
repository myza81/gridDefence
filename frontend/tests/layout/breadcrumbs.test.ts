import { describe, expect, it } from "vitest";

import { resolveBreadcrumbs } from "../../src/app/breadcrumbs";

const labels = (pathname: string) => resolveBreadcrumbs(pathname).map((crumb) => crumb.label);

describe("resolveBreadcrumbs", () => {
  it("renders Home as a single non-link crumb at the root", () => {
    const crumbs = resolveBreadcrumbs("/");
    expect(crumbs).toHaveLength(1);
    expect(crumbs[0].label).toBe("Home");
    expect(crumbs[0].to).toBeUndefined();
  });

  it("builds Home / group / item for a module entry, with the last crumb non-navigable", () => {
    const crumbs = resolveBreadcrumbs("/substations");
    expect(crumbs.map((c) => c.label)).toEqual(["Home", "Registries", "Substations"]);
    expect(crumbs[0].to).toBe("/");
    expect(crumbs[crumbs.length - 1].to).toBeUndefined();
  });

  it("links the module entry and adds a named terminal crumb on an action route", () => {
    const crumbs = resolveBreadcrumbs("/substations/new");
    expect(crumbs.map((c) => c.label)).toEqual(["Home", "Registries", "Substations", "New"]);
    expect(crumbs.find((c) => c.label === "Substations")?.to).toBe("/substations");
  });

  it("uses a generic terminal label for a dynamic record (no record fetch)", () => {
    expect(labels("/substations/9f3a2b7c")).toEqual(["Home", "Registries", "Substations", "Details"]);
  });

  it("resolves a cross-module domain entry (Network & PSS/E)", () => {
    expect(labels("/psse-integration/history")).toEqual(["Home", "Network & PSS/E", "PSS/E History"]);
  });

  it("falls back to a domain label for an orphan route with no navigation entry", () => {
    expect(labels("/ufls/versions/abc123")).toEqual(["Home", "Defence Schemes"]);
  });
});
