import { afterEach, describe, expect, it } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";

describe("authStorage", () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it("returns null when no token has been stored", () => {
    expect(authStorage.getToken()).toBeNull();
  });

  it("round-trips a stored token", () => {
    authStorage.setToken("example-token");
    expect(authStorage.getToken()).toBe("example-token");
  });

  it("clears a stored token", () => {
    authStorage.setToken("example-token");
    authStorage.clearToken();
    expect(authStorage.getToken()).toBeNull();
  });
});
