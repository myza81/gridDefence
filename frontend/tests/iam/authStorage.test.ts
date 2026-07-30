import { afterEach, describe, expect, it } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";

describe("authStorage", () => {
  afterEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("returns null when no token has been stored", () => {
    expect(authStorage.getToken()).toBeNull();
  });

  it("round-trips a stored token (persistent by default)", () => {
    authStorage.setToken("example-token");
    expect(authStorage.getToken()).toBe("example-token");
    expect(window.localStorage.getItem("griddefence.iam.access_token")).toBe("example-token");
  });

  it("stores a session-only token in sessionStorage when persist is false", () => {
    authStorage.setToken("session-token", false);
    expect(authStorage.getToken()).toBe("session-token");
    expect(window.sessionStorage.getItem("griddefence.iam.access_token")).toBe("session-token");
    expect(window.localStorage.getItem("griddefence.iam.access_token")).toBeNull();
  });

  it("clears a stored token from both stores", () => {
    authStorage.setToken("example-token");
    authStorage.clearToken();
    expect(authStorage.getToken()).toBeNull();
    authStorage.setToken("session-token", false);
    authStorage.clearToken();
    expect(authStorage.getToken()).toBeNull();
  });
});
